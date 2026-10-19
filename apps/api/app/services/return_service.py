"""
apps/api/app/services/return_service.py

Dịch vụ Quản lý Vòng đời Yêu cầu Đổi / Trả Hàng (Return Lifecycle Management) H4CARE:
1. Tiếp nhận & Thẩm định yêu cầu từ Khách hàng.
2. Quản lý luồng trạng thái chuẩn hóa:
   REQUESTED -> REVIEWING -> APPROVED -> WAITING_CUSTOMER_RETURN -> RETURN_IN_TRANSIT -> RECEIVED -> INSPECTING -> INSPECTION_COMPLETED -> REFUND_PENDING / EXCHANGE_PENDING -> CLOSED.
3. Kiểm tra thực tế tại kho dược (Warehouse Inspection & Quarantine / Restock).
4. Cập nhật tồn kho (Stock Movement & Batch Stock) tuân thủ GSP.
5. Ghi nhận lịch sử trạng thái (ReturnStatusHistory) và Nhật ký kiểm toán (AuditLog).
6. Thông báo tự động qua Email & Alert Notification.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Sequence

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AdminAlert, AuditLog, Order, OrderItem, User
from app.models.inventory import (
    EmailOutbox,
    InventoryBatch,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import (
    ExchangeStatus,
    ItemCondition,
    RefundMethod,
    RefundStatus,
    RestockDestination,
    ReturnEvidence,
    ReturnItem,
    ReturnMethod,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
    ReturnStatusHistory,
)
from app.services.alert_notifier import dispatch_alert
from app.services.audit import write_audit
from app.services.refund_calculation_service import RefundCalculationService
from app.services.return_policy_service import ReturnPolicyService
from app.services.return_restock_service import ReturnRestockService

logger = logging.getLogger("pharmatrust.returns")


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReturnService:
    """
    Service quản lý toàn bộ quy trình đổi trả hàng.
    """

    @classmethod
    def generate_return_code(cls, db: Session) -> str:
        """
        Sinh mã yêu cầu đổi trả theo format RET-YYYYMMDD-XXXX (VD: RET-20261008-0001).
        """
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"RET-{today_str}-"

        # Đếm số lượng return trong ngày
        count = db.scalar(
            select(func.count(ReturnRequest.id)).where(
                ReturnRequest.return_code.like(f"{prefix}%")
            )
        ) or 0
        return f"{prefix}{count + 1:04d}"

    @classmethod
    def create_return_request(
        cls,
        db: Session,
        order_code: str,
        request_type: str,
        reason_code: str,
        reason_text: str,
        items_payload: list[dict[str, Any]],
        customer_note: str | None = None,
        return_method: str = ReturnMethod.CUSTOMER_SHIP.value,
        evidences_payload: list[dict[str, Any]] | None = None,
        current_user: User | None = None,
        customer_phone_verify: str | None = None,
        customer_email_verify: str | None = None,
    ) -> ReturnRequest:
        """
        Khởi tạo yêu cầu đổi/trả hàng mới từ khách hàng.
        """
        # 1. Tìm đơn hàng
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        if not order:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{order_code}'.")

        # 2. Xác thực quyền sở hữu (Nếu đã đăng nhập phải trùng user_id, nếu khách vãng lai phải khớp số điện thoại)
        if current_user and current_user.role == "CUSTOMER":
            if order.user_id and order.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Bạn không có quyền yêu cầu đổi/trả cho đơn hàng này.")
        elif not (current_user and current_user.role in ["ADMIN", "PHARMACIST"]):
            if not customer_phone_verify or not customer_phone_verify.strip():
                raise HTTPException(status_code=403, detail="Vui lòng cung cấp số điện thoại đặt hàng để xác minh quyền sở hữu.")
            clean_input = customer_phone_verify.strip().replace(" ", "").replace(".", "")
            clean_order_phone = (order.customer_phone or "").strip().replace(" ", "").replace(".", "")
            if clean_input != clean_order_phone:
                raise HTTPException(status_code=403, detail="Số điện thoại xác nhận không khớp với thông tin đơn hàng.")
            if customer_email_verify and customer_email_verify.strip():
                clean_email = customer_email_verify.strip().lower()
                clean_order_email = (order.customer_email or "").strip().lower()
                if clean_order_email and clean_email != clean_order_email:
                    raise HTTPException(status_code=403, detail="Email xác nhận không khớp với thông tin đơn hàng.")

        # 3. Thẩm định điều kiện đổi trả đơn hàng
        eligibility = ReturnPolicyService.evaluate_order_eligibility(db, order)
        if not eligibility.can_request_return:
            raise HTTPException(
                status_code=400,
                detail=eligibility.rejection_reason or "Đơn hàng không đủ điều kiện yêu cầu đổi trả.",
            )

        if not items_payload:
            raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất một sản phẩm cần đổi/trả.")

        # 4. Xác thực từng sản phẩm yêu cầu
        eligibility_items_map = {item.order_item_id: item for item in eligibility.items}
        order_items_map = {item.id: item for item in order.items}

        validated_return_items: list[ReturnItem] = []

        for item_in in items_payload:
            order_item_id = item_in.get("order_item_id")
            requested_qty = int(item_in.get("requested_quantity", 1))

            if order_item_id not in order_items_map:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sản phẩm (ID {order_item_id}) không thuộc đơn hàng '{order_code}'.",
                )

            elig_item = eligibility_items_map.get(order_item_id)
            if not elig_item or not elig_item.is_eligible:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sản phẩm '{elig_item.product_name if elig_item else order_item_id}' không đủ điều kiện đổi trả: {elig_item.message if elig_item else ''}",
                )

            if requested_qty <= 0 or requested_qty > elig_item.returnable_quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số lượng yêu cầu ({requested_qty}) không hợp lệ. Số lượng còn có thể đổi trả: {elig_item.returnable_quantity}.",
                )

            order_item = order_items_map[order_item_id]
            net_unit = RefundCalculationService.calculate_net_unit_price(order, order_item)
            unit_p = Decimal(str(order_item.price))
            discount = max(Decimal("0.0"), unit_p - net_unit)
            net_paid = net_unit * Decimal(str(requested_qty))
            requested_refund = net_paid

            ret_item = ReturnItem(
                order_item_id=order_item.id,
                product_id=order_item.product_id or 0,
                product_name=order_item.product_name,
                original_quantity=order_item.quantity,
                requested_quantity=requested_qty,
                unit_price_at_purchase=unit_p,
                allocated_discount=discount * Decimal(str(requested_qty)),
                net_paid_amount=net_paid,
                requested_refund_amount=requested_refund,
                customer_reason=item_in.get("customer_reason") or reason_text,
                condition_reported=item_in.get("condition_reported", ItemCondition.SEALED.value),
                condition=item_in.get("condition_reported", ItemCondition.SEALED.value),
            )
            validated_return_items.append(ret_item)

        # 5. Khởi tạo mã phiếu và ReturnRequest
        return_code = cls.generate_return_code(db)
        ret_request = ReturnRequest(
            return_code=return_code,
            order_id=order.id,
            user_id=current_user.id if current_user else order.user_id,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            customer_email=order.customer_email,
            request_type=request_type if request_type in [ReturnRequestType.RETURN.value, ReturnRequestType.EXCHANGE.value] else ReturnRequestType.RETURN.value,
            status=ReturnStatus.REQUESTED.value,
            reason_code=reason_code,
            reason_text=reason_text,
            customer_note=customer_note,
            return_method=return_method,
            return_address_snapshot=order.shipping_address,
            requested_at=utcnow(),
        )
        db.add(ret_request)
        db.flush()

        # 6. Tách ca hoàn theo từng chi nhánh kho đã xuất hàng
        from app.services.warehouse_return_service import WarehouseReturnService
        created_cases = WarehouseReturnService.split_return_request_into_cases(
            db=db,
            return_request=ret_request,
            return_items=validated_return_items,
            order=order,
        )
        primary_case_id = created_cases[0].id if created_cases else None

        # 7. Gắn bằng chứng (nếu có)
        if evidences_payload:
            for ev in evidences_payload:
                file_url = ev.get("file_url")
                if file_url:
                    evidence = ReturnEvidence(
                        return_request_id=ret_request.id,
                        warehouse_return_case_id=primary_case_id,
                        file_url=file_url,
                        file_name=ev.get("file_name") or os.path.basename(file_url),
                        mime_type=ev.get("mime_type") or ev.get("file_type") or "image/jpeg",
                        file_category=ev.get("file_category") or "DAMAGE_PHOTO",
                        file_size=ev.get("file_size") or 0,
                        description=ev.get("description"),
                        uploaded_by=current_user.id if current_user else None,
                    )
                    db.add(evidence)

        # 8. Ghi nhận lịch sử trạng thái ban đầu
        cls._add_status_history(
            db=db,
            return_request=ret_request,
            from_status=None,
            to_status=ret_request.status,
            actor=current_user,
            actor_role="CUSTOMER" if (current_user and current_user.role == "CUSTOMER") else "GUEST",
            note=f"Khách hàng gửi yêu cầu {request_type}: {reason_text}. Đã phân bổ {len(created_cases)} ca hoàn về kho xuất hàng.",
        )

        # 8.1. Lưu cảnh báo nội bộ vào database (AdminAlert) để Admin nhận thông báo trên bảng điều khiển
        alert = AdminAlert(
            source_code="STOREFRONT_RETURN",
            alert_type="RETURN_REQUESTED",
            severity="WARNING",
            message=f"Yêu cầu đổi/trả mới [{ret_request.return_code}] cho đơn hàng {order.order_code} từ khách {ret_request.customer_name} ({ret_request.customer_phone}). Lý do: {ret_request.reason_text}",
            is_read=False,
        )
        db.add(alert)

        # 8.2. Lưu thư thông báo gửi Admin (EmailOutbox)
        try:
            email_admin = EmailOutbox(
                recipient_email=settings.smtp_user or "admin@pharmatrust.vn",
                recipient_name="Dược sĩ Quản trị H4CARE",
                subject=f"[H4CARE] Thông báo yêu cầu đổi/trả mới cần duyệt: {ret_request.return_code} (Đơn {order.order_code})",
                body_html=(
                    f"<h3>Thông báo: Khách hàng vừa gửi yêu cầu đổi/trả thuốc</h3>"
                    f"<p>Hệ thống H4CARE ghi nhận yêu cầu mới cần Dược sĩ thẩm định:</p>"
                    f"<ul>"
                    f"<li><b>Mã yêu cầu:</b> {ret_request.return_code}</li>"
                    f"<li><b>Mã đơn hàng:</b> {order.order_code}</li>"
                    f"<li><b>Khách hàng:</b> {ret_request.customer_name} (SĐT: {ret_request.customer_phone})</li>"
                    f"<li><b>Hình thức:</b> {'Trả hàng & Hoàn tiền' if request_type == 'RETURN' else 'Đổi sản phẩm khác'}</li>"
                    f"<li><b>Lý do:</b> {reason_text}</li>"
                    f"<li><b>Ghi chú của khách:</b> {customer_note or 'Không có'}</li>"
                    f"</ul>"
                    f"<p>Vui lòng đăng nhập Cổng Quản Trị H4CARE (<a href='http://localhost:5173/returns'>http://localhost:5173/returns</a>) để duyệt đơn.</p>"
                ),
                body_text=f"Yêu cầu đổi trả mới: {ret_request.return_code} cho đơn {order.order_code}",
                status="PENDING",
                reference_type="RETURN_REQUEST",
                reference_id=ret_request.return_code,
            )
            db.add(email_admin)
        except Exception as e:
            logger.warning(f"[RETURN] Không thể tạo EmailOutbox thông báo đổi/trả: {e}")

        db.commit()
        db.refresh(ret_request)

        # 9. Gửi cảnh báo hệ thống & Admin
        dispatch_alert(
            title=f"YÊU CẦU {request_type} MỚI: {ret_request.return_code}",
            message=(
                f"Mã phiếu: <b>{ret_request.return_code}</b>\n"
                f"Đơn hàng: <b>{order.order_code}</b>\n"
                f"Khách hàng: <b>{ret_request.customer_name}</b> ({ret_request.customer_phone})\n"
                f"Lý do: <i>{ret_request.reason_text}</i>\n"
                f"Số lượng sản phẩm: <b>{len(validated_return_items)}</b>"
            ),
            severity="WARNING",
            alert_type="RETURN_REQUESTED",
            details={
                "Mã phiếu": ret_request.return_code,
                "Mã đơn": order.order_code,
                "Loại": request_type,
                "Lý do": reason_text,
            },
        )

        logger.info(f"[RETURN] Đã tạo thành công yêu cầu {ret_request.return_code} cho đơn {order.order_code}")
        return ret_request

    @classmethod
    def review_return_request(
        cls,
        db: Session,
        return_code: str,
        admin_user: User,
        status: str,  # REVIEWING hoặc NEEDS_CUSTOMER_INFO
        admin_note: str | None = None,
        customer_visible_note: str | None = None,
    ) -> ReturnRequest:
        """
        Nhân viên bắt đầu tiếp nhận xem xét hoặc yêu cầu khách cung cấp thêm thông tin.
        """
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

        old_status = ret.status
        ret.status = status
        ret.reviewed_by = admin_user.id
        ret.reviewed_at = utcnow()
        if admin_note:
            ret.admin_note = (ret.admin_note or "") + f"\n[{utcnow().strftime('%d/%m %H:%M')}] {admin_note}"
        if customer_visible_note:
            ret.customer_visible_note = customer_visible_note

        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=old_status,
            to_status=status,
            actor=admin_user,
            actor_role=admin_user.role,
            note=customer_visible_note or admin_note or f"Chuyển trạng thái sang {status}",
        )

        write_audit(
            db=db,
            action="REVIEW_RETURN",
            entity_type="RETURN_REQUEST",
            entity_id=ret.return_code,
            user=admin_user,
            before={"status": old_status},
            after={"status": status, "admin_note": admin_note},
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def approve_return_request(
        cls,
        db: Session,
        return_code: str,
        admin_user: User,
        warehouse_address: str | None = None,
        admin_note: str | None = None,
        customer_visible_note: str | None = None,
    ) -> ReturnRequest:
        """
        Duyệt yêu cầu đổi/trả hàng -> Hướng dẫn khách gửi hàng về kho (WAITING_CUSTOMER_RETURN).
        """
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

        if ret.status in [ReturnStatus.REJECTED.value, ReturnStatus.CANCELLED.value, ReturnStatus.CLOSED.value]:
            raise HTTPException(status_code=400, detail=f"Không thể duyệt phiếu ở trạng thái '{ret.status}'.")

        old_status = ret.status
        ret.status = ReturnStatus.WAITING_CUSTOMER_RETURN.value
        ret.approved_by = admin_user.id
        ret.approved_at = utcnow()

        # Địa chỉ kho nhận hàng hoàn
        default_wh_addr = (
            "Trung tâm Dược phẩm H4CARE - Kho Tổng GSP\n"
            "Địa chỉ: Số 123 Đường Nguyễn Trãi, Thanh Xuân, Hà Nội\n"
            "Người nhận: Bộ phận Tiếp nhận Đổi trả H4CARE (ĐT: 0988.123.456)"
        )
        dest_address = warehouse_address or default_wh_addr

        guide_note = (
            f"Yêu cầu đổi/trả đã được phê duyệt. Quý khách vui lòng đóng gói sản phẩm và gửi về:\n"
            f"{dest_address}\n"
            f"Vui lòng ghi rõ mã phiếu '{ret.return_code}' bên ngoài kiện hàng và cập nhật mã vận đơn lên hệ thống."
        )

        ret.customer_visible_note = customer_visible_note or guide_note
        if admin_note:
            ret.admin_note = (ret.admin_note or "") + f"\n[{utcnow().strftime('%d/%m %H:%M')}] {admin_note}"

        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=old_status,
            to_status=ReturnStatus.WAITING_CUSTOMER_RETURN.value,
            actor=admin_user,
            actor_role=admin_user.role,
            note="Phê duyệt yêu cầu đổi/trả, chờ khách hàng gửi hàng về kho.",
        )

        write_audit(
            db=db,
            action="APPROVE_RETURN",
            entity_type="RETURN_REQUEST",
            entity_id=ret.return_code,
            user=admin_user,
            before={"status": old_status},
            after={"status": ret.status},
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def reject_return_request(
        cls,
        db: Session,
        return_code: str,
        admin_user: User,
        rejection_reason: str,
        admin_note: str | None = None,
    ) -> ReturnRequest:
        """
        Từ chối yêu cầu đổi/trả hàng kèm lý do rõ ràng.
        """
        if not rejection_reason or not rejection_reason.strip():
            raise HTTPException(status_code=400, detail="Vui lòng nhập lý do từ chối cụ thể để phản hồi tới khách hàng.")

        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

        old_status = ret.status
        ret.status = ReturnStatus.REJECTED.value
        ret.reviewed_by = admin_user.id
        ret.rejection_reason = rejection_reason.strip()
        ret.customer_visible_note = f"Yêu cầu đổi/trả bị từ chối: {rejection_reason.strip()}"
        if admin_note:
            ret.admin_note = (ret.admin_note or "") + f"\n[{utcnow().strftime('%d/%m %H:%M')}] {admin_note}"

        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=old_status,
            to_status=ReturnStatus.REJECTED.value,
            actor=admin_user,
            actor_role=admin_user.role,
            note=f"Từ chối yêu cầu đổi/trả: {rejection_reason.strip()}",
        )

        write_audit(
            db=db,
            action="REJECT_RETURN",
            entity_type="RETURN_REQUEST",
            entity_id=ret.return_code,
            user=admin_user,
            before={"status": old_status},
            after={"status": ret.status, "rejection_reason": rejection_reason},
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def update_customer_shipping(
        cls,
        db: Session,
        return_code: str,
        carrier_name: str,
        tracking_code: str,
        current_user: User | None = None,
    ) -> ReturnRequest:
        """
        Khách hàng cập nhật thông tin vận chuyển hàng trả về (Carrier & Tracking).
        """
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

        valid_statuses = [
            ReturnStatus.APPROVED.value,
            ReturnStatus.WAITING_CUSTOMER_RETURN.value,
            ReturnStatus.RETURN_IN_TRANSIT.value,
        ]
        if ret.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Chỉ có thể cập nhật vận đơn khi yêu cầu ở trạng thái đã duyệt (Hiện tại: {ret.status}).",
            )

        old_status = ret.status
        ret.carrier_name = carrier_name.strip()
        ret.tracking_code = tracking_code.strip()
        ret.status = ReturnStatus.RETURN_IN_TRANSIT.value

        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=old_status,
            to_status=ReturnStatus.RETURN_IN_TRANSIT.value,
            actor=current_user,
            actor_role="CUSTOMER" if (current_user and current_user.role == "CUSTOMER") else "GUEST",
            note=f"Khách hàng đã gửi hàng qua đơn vị {carrier_name}, Mã vận đơn: {tracking_code}",
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def confirm_receipt(
        cls,
        db: Session,
        return_code: str,
        warehouse_user: User,
        note: str | None = None,
    ) -> ReturnRequest:
        """
        Kho dược xác nhận đã nhận kiện hàng trả về từ bưu tá -> Chuyển sang INSPECTING.
        """
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

        # 1. Kiểm tra trạng thái hợp lệ trước khi nhận hàng (ngăn thao tác lặp / sai quy trình)
        valid_receipt_statuses = [
            ReturnStatus.APPROVED.value,
            ReturnStatus.WAITING_CUSTOMER_RETURN.value,
            ReturnStatus.RETURN_IN_TRANSIT.value,
        ]
        if ret.status not in valid_receipt_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Chỉ có thể tiếp nhận kiện hàng khi yêu cầu đã được phê duyệt và đang vận chuyển về kho (Hiện tại: {ret.status}). Không thể tiếp nhận hàng khi phiếu còn đang chờ duyệt hoặc đang thẩm định.",
            )

        old_status = ret.status
        ret.status = ReturnStatus.RECEIVED.value
        ret.received_by = warehouse_user.id
        ret.received_at = utcnow()

        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=old_status,
            to_status=ReturnStatus.RECEIVED.value,
            actor=warehouse_user,
            actor_role=warehouse_user.role,
            note=note or "Kho đã nhận kiện hàng hoàn trả, chuyển sang bộ phận Dược sĩ kiểm định chất lượng.",
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def inspect_return_items(
        cls,
        db: Session,
        return_code: str,
        inspector_user: User,
        inspection_payload: list[dict[str, Any]],
        general_inspection_note: str | None = None,
    ) -> ReturnRequest:
        """
        Kiểm định chất lượng hàng hoàn trả (Pharmacist Inspection):
        - Đánh giá tình trạng bao bì, seal, hạn sử dụng của từng sản phẩm.
        - Phân luồng tồn kho:
            + SELLABLE_STOCK: Nhập lại kho bán được (tăng quantity_available, log RETURN_RESTOCK).
              BẮT BUỘC ĐIỀU KIỆN GSP: Chỉ áp dụng khi condition là GOOD_CONDITION hoặc SEALED.
            + QUARANTINE: Đưa vào khu vực biệt trữ cách ly (log RETURN_QUARANTINE).
            + NON_SELLABLE_DISPOSE: Hủy bỏ / tiêu hủy dược phẩm không đạt (log DISPOSAL).
        - Chuyển trạng thái sang INSPECTION_COMPLETED, sau đó tự động sang REFUND_PENDING hoặc EXCHANGE_PENDING.
        """
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

        # 1. Kiểm tra trạng thái hợp lệ trước khi kiểm định (chống thao tác lặp gây nhân đôi tồn kho)
        if ret.status not in [ReturnStatus.RECEIVED.value, ReturnStatus.INSPECTING.value]:
            raise HTTPException(
                status_code=400,
                detail=f"Yêu cầu phải ở trạng thái Đã nhận hàng (RECEIVED) hoặc Đang kiểm định (INSPECTING) để thẩm định chất lượng (Hiện tại: {ret.status}).",
            )

        if not inspection_payload:
            raise HTTPException(status_code=400, detail="Dữ liệu kiểm định sản phẩm không được để trống.")

        ret_items_map = {item.id: item for item in ret.items}
        order = ret.order

        # Idempotency chéo: Kiểm tra phiếu hoàn hoặc ca hoàn kho liên quan đã từng được restock chưa
        linked_case_codes = [c.case_code for c in ret.warehouse_cases] if hasattr(ret, "warehouse_cases") and ret.warehouse_cases else []
        existing_restock_conditions = [
            and_(
                StockMovement.movement_type == "RETURN_RESTOCK",
                StockMovement.reference_type == "RETURN_REQUEST",
                StockMovement.reference_id == ret.return_code,
            )
        ]
        if linked_case_codes:
            existing_restock_conditions.append(
                and_(
                    StockMovement.movement_type == "RETURN_RESTOCK",
                    StockMovement.reference_type == "WAREHOUSE_RETURN_CASE",
                    StockMovement.reference_id.in_(linked_case_codes),
                )
            )
        existing_restock_mv = db.scalar(
            select(StockMovement).where(or_(*existing_restock_conditions))
        )
        if existing_restock_mv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phiếu hoàn '{ret.return_code}' hoặc ca hoàn kho liên quan đã được nhập lại kho bán trước đó. Không thể thực hiện nhập kho trùng lặp.",
            )

        if hasattr(ret, "warehouse_cases") and ret.warehouse_cases:
            for c in ret.warehouse_cases:
                if c.status in [ReturnStatus.RESTOCKED.value, ReturnStatus.CLOSED.value] and c.disposition == "RESTOCK":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ca hoàn kho '{c.case_code}' của phiếu hoàn này đã được nhập lại kho bán trước đó. Không thể thực hiện nhập kho trùng lặp.",
                    )

        # Xác định kho kỳ vọng tiếp nhận hàng hoàn
        expected_wh_id: int | None = None
        if hasattr(ret, "warehouse_cases") and ret.warehouse_cases:
            expected_wh_id = ret.warehouse_cases[0].warehouse_id
        elif ret.order and ret.order.assigned_warehouse_id:
            expected_wh_id = ret.order.assigned_warehouse_id

        # BƯỚC 1: Tiền kiểm định (Pre-validation) toàn bộ sản phẩm TRƯỚC KHI cập nhật bất kỳ tồn kho nào
        seen_item_ids: set[int] = set()
        items_plan: list[dict[str, Any]] = []

        for insp in inspection_payload:
            item_id = insp.get("return_item_id")
            if not item_id or item_id not in ret_items_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sản phẩm đổi/trả (ID {item_id}) không hợp lệ hoặc không thuộc phiếu '{return_code}'.",
                )

            if item_id in seen_item_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sản phẩm #{item_id} bị trùng lặp trong dữ liệu kiểm định.",
                )
            seen_item_ids.add(item_id)

            item = ret_items_map[item_id]
            condition = insp.get("condition")
            if not condition:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vui lòng chỉ định tình trạng sản phẩm (condition) cho sản phẩm '{item.product_name}'.",
                )

            destination = insp.get("restock_destination")
            if not destination:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vui lòng chỉ định phân luồng kho (restock_destination) cho sản phẩm '{item.product_name}'.",
                )

            valid_dests = [
                RestockDestination.SELLABLE_STOCK.value,
                RestockDestination.QUARANTINE.value,
                RestockDestination.NON_SELLABLE_DISPOSE.value,
            ]
            if destination not in valid_dests:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Phân luồng kho '{destination}' không hợp lệ. Phải là một trong: {valid_dests}",
                )

            raw_accepted = insp.get("accepted_quantity")
            if raw_accepted is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vui lòng chỉ định số lượng chấp nhận (accepted_quantity) cho sản phẩm '{item.product_name}'.",
                )
            accepted_qty = int(raw_accepted)

            raw_rejected = insp.get("rejected_quantity")
            if raw_rejected is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vui lòng chỉ định số lượng loại bỏ (rejected_quantity) cho sản phẩm '{item.product_name}'.",
                )
            rejected_qty = int(raw_rejected)

            if accepted_qty < 0 or rejected_qty < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng chấp nhận và loại bỏ của '{item.product_name}' không được âm.",
                )

            if accepted_qty + rejected_qty <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vui lòng nhập số lượng kiểm định cho sản phẩm '{item.product_name}' (tổng số lượng phải > 0).",
                )

            raw_restock = insp.get("restock_quantity")
            if destination == RestockDestination.SELLABLE_STOCK.value:
                if raw_restock is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Bắt buộc phải chỉ định số lượng nhập lại kho bán (restock_quantity) khi phân luồng vào kho bán (SELLABLE_STOCK) cho sản phẩm '{item.product_name}'.",
                    )
                restock_qty = int(raw_restock)
                if restock_qty <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Số lượng nhập lại kho bán (restock_quantity) phải lớn hơn 0 khi phân luồng vào kho bán cho sản phẩm '{item.product_name}'.",
                    )
            else:
                restock_qty = int(raw_restock) if raw_restock is not None else 0

            if restock_qty < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng nhập lại kho bán của '{item.product_name}' không được âm.",
                )

            # Kiểm tra điều kiện chuyên môn GSP Dược
            if destination == RestockDestination.SELLABLE_STOCK.value:
                gsp_compliant_conditions = [ItemCondition.GOOD_CONDITION.value, ItemCondition.SEALED.value]
                if condition not in gsp_compliant_conditions:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Sản phẩm '{item.product_name}' có tình trạng '{condition}', không đáp ứng tiêu chuẩn chất lượng GSP để nhập lại kho bán. Vui lòng phân luồng sang Biệt trữ (QUARANTINE) hoặc Tiêu hủy (NON_SELLABLE_DISPOSE).",
                    )

            if accepted_qty + rejected_qty > item.requested_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tổng số lượng chấp nhận ({accepted_qty}) và loại bỏ ({rejected_qty}) vượt quá số lượng yêu cầu đổi/trả ({item.requested_quantity}) của sản phẩm '{item.product_name}'.",
                )

            if destination == RestockDestination.SELLABLE_STOCK.value and restock_qty > accepted_qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng nhập lại kho bán ({restock_qty}) không được lớn hơn số lượng chấp nhận ({accepted_qty}).",
                )

            # Truy xuất và tiền kiểm định OrderItemBatchAllocation của order_item này
            allocations = db.scalars(
                select(OrderItemBatchAllocation)
                .where(OrderItemBatchAllocation.order_item_id == item.order_item_id)
                .order_by(OrderItemBatchAllocation.id.asc())
            ).all()

            if not allocations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Không tìm thấy thông tin lô xuất kho gốc cho sản phẩm {item.product_name} (order_item #{item.order_item_id}). Không thể nhập lại kho bán được để đảm bảo toàn vẹn dữ liệu thuốc.",
                )

            grouped_allocations: list[dict[str, Any]] = []
            seen_batches: dict[int, dict[str, Any]] = {}

            for alloc in allocations:
                if not alloc.batch_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Thông tin phân bổ lô xuất kho bị thiếu batch_id cho sản phẩm #{item.product_name}.",
                    )

                batch = db.scalar(select(InventoryBatch).where(InventoryBatch.id == alloc.batch_id))
                if not batch:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Lô xuất gốc #{alloc.batch_id} không tồn tại trong hệ thống.",
                    )

                sku = db.scalar(select(ProductSku).where(ProductSku.id == batch.sku_id))
                prod_id = item.order_item.product_id if item.order_item else (getattr(item, 'product_id', None))
                if prod_id and (not sku or sku.canonical_product_id != prod_id):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Lô xuất gốc #{alloc.batch_id} (SKU #{batch.sku_id}) không thuộc sản phẩm #{prod_id}.",
                    )

                # Kiểm tra khớp kho sở hữu nếu có kho kỳ vọng
                if expected_wh_id and alloc.warehouse_id != expected_wh_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Kho của lô xuất gốc #{alloc.batch_id} (Kho #{alloc.warehouse_id}) không khớp với kho xử lý (Kho #{expected_wh_id}).",
                    )

                # Gộp allocation theo batch_id
                if alloc.batch_id not in seen_batches:
                    entry = {
                        "batch_id": alloc.batch_id,
                        "warehouse_id": alloc.warehouse_id,
                        "allocated_quantity": alloc.allocated_quantity,
                    }
                    seen_batches[alloc.batch_id] = entry
                    grouped_allocations.append(entry)
                else:
                    seen_batches[alloc.batch_id]["allocated_quantity"] += alloc.allocated_quantity

            total_allocated = sum(g["allocated_quantity"] for g in grouped_allocations)
            qty_to_verify = restock_qty if destination == RestockDestination.SELLABLE_STOCK.value else accepted_qty
            if qty_to_verify > total_allocated:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng hoàn ({qty_to_verify}) vượt quá tổng số lượng đã xuất từ các lô gốc ({total_allocated}) cho sản phẩm '{item.product_name}'.",
                )

            items_plan.append({
                "item": item,
                "condition": condition,
                "destination": destination,
                "accepted_qty": accepted_qty,
                "rejected_qty": rejected_qty,
                "restock_qty": restock_qty,
                "notes": insp.get("notes"),
                "grouped_allocations": grouped_allocations,
            })

        # BƯỚC 2: Thực thi cập nhật khi 100% kiểm định thành công
        restock_by_wh: dict[int, list[dict[str, Any]]] = {}

        for plan in items_plan:
            item = plan["item"]
            condition = plan["condition"]
            destination = plan["destination"]
            accepted_qty = plan["accepted_qty"]
            rejected_qty = plan["rejected_qty"]
            restock_qty = plan["restock_qty"]
            grouped_allocations = plan["grouped_allocations"]

            item.inspected_condition = condition
            item.restock_destination = destination
            item.accepted_quantity = accepted_qty
            item.rejected_quantity = rejected_qty
            item.restock_quantity = restock_qty
            item.inspection_notes = plan["notes"]

            item_wh_id = grouped_allocations[0]["warehouse_id"]

            # Xử lý cập nhật tồn kho nếu có số lượng nhập lại (Restock)
            if destination == RestockDestination.SELLABLE_STOCK.value and restock_qty > 0:
                prod_id = item.order_item.product_id if item.order_item else (getattr(item, 'product_id', None))
                restock_by_wh.setdefault(item_wh_id, []).append({
                    "order_item_id": item.order_item_id,
                    "product_id": prod_id,
                    "product_name": item.product_name,
                    "qty_to_restock": restock_qty,
                    "return_item_id": item.id,
                })
            elif destination == RestockDestination.QUARANTINE.value and accepted_qty > 0:
                cls._process_restock_movement(
                    db=db,
                    order_item_id=item.order_item_id,
                    warehouse_id=item_wh_id,
                    quantity=accepted_qty,
                    return_code=ret.return_code,
                    actor=inspector_user,
                    movement_type="RETURN_QUARANTINE",
                    note=f"Biệt trữ kiểm nghiệm từ phiếu hoàn {ret.return_code} (Tình trạng: {condition})",
                    grouped_allocations=grouped_allocations,
                )
            elif destination == RestockDestination.NON_SELLABLE_DISPOSE.value and accepted_qty > 0:
                cls._process_restock_movement(
                    db=db,
                    order_item_id=item.order_item_id,
                    warehouse_id=item_wh_id,
                    quantity=accepted_qty,
                    return_code=ret.return_code,
                    actor=inspector_user,
                    movement_type="RETURN_DISPOSE",
                    note=f"Tiêu hủy dược phẩm hỏng từ phiếu hoàn {ret.return_code} (Tình trạng: {condition})",
                    grouped_allocations=grouped_allocations,
                )

        # Gom và thực thi nhập kho nguyên tử 1 lần duy nhất cho mỗi kho
        for wh_id, wh_items in restock_by_wh.items():
            ReturnRestockService.execute_return_restock(
                db=db,
                source_type="RETURN_REQUEST",
                source_code=ret.return_code,
                warehouse_id=wh_id,
                items_to_restock=wh_items,
                actor_user_id=inspector_user.id,
                audit_note=f"Nhập lại kho bán từ phiếu hoàn {ret.return_code}",
                linked_reference_codes=linked_case_codes,
            )

        old_status = ret.status
        ret.status = ReturnStatus.INSPECTION_COMPLETED.value
        ret.inspected_by = inspector_user.id
        ret.inspected_at = utcnow()

        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=old_status,
            to_status=ReturnStatus.INSPECTION_COMPLETED.value,
            actor=inspector_user,
            actor_role=inspector_user.role,
            note=general_inspection_note or "Dược sĩ hoàn tất kiểm định chất lượng hàng hoàn trả.",
        )

        # Chuyển tiếp luồng tiếp theo:
        # Kiểm định chỉ ghi nhận mặt kỹ thuật; KHÔNG được tự ý biến thành phê duyệt của Quản lý kho và KHÔNG được kích hoạt hoàn tiền.
        if ret.request_type == ReturnRequestType.EXCHANGE.value:
            next_status = ReturnStatus.EXCHANGE_PENDING.value
            next_note = "Chuyển tiếp: Đang chờ tạo đơn đổi hàng mới."
        else:
            next_status = ReturnStatus.WAITING_MANAGER_APPROVAL.value
            next_note = "Chuyển tiếp: Kiểm định hoàn tất, đang chờ Quản lý kho xem xét và phê duyệt hoàn tiền."

        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=ReturnStatus.INSPECTION_COMPLETED.value,
            to_status=next_status,
            actor=inspector_user,
            actor_role="SYSTEM",
            note=next_note,
        )
        ret.status = next_status

        write_audit(
            db=db,
            action="INSPECT_RETURN_ITEMS",
            entity_type="RETURN_REQUEST",
            entity_id=ret.return_code,
            user=inspector_user,
            before={"status": old_status},
            after={"status": ret.status, "inspected_items_count": len(inspection_payload)},
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def cancel_return_request(
        cls,
        db: Session,
        return_code: str,
        actor_user: User | None,
        reason: str | None = None,
    ) -> ReturnRequest:
        """
        Hủy yêu cầu đổi/trả hàng (Chỉ cho phép trước khi kho nhận hàng).
        """
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

        non_cancellable = [
            ReturnStatus.RECEIVED.value,
            ReturnStatus.INSPECTING.value,
            ReturnStatus.INSPECTION_COMPLETED.value,
            ReturnStatus.REFUNDED.value,
            ReturnStatus.EXCHANGED.value,
            ReturnStatus.CLOSED.value,
            ReturnStatus.CANCELLED.value,
        ]
        if ret.status in non_cancellable:
            raise HTTPException(
                status_code=400,
                detail=f"Không thể hủy yêu cầu ở trạng thái '{ret.status}'.",
            )

        old_status = ret.status
        ret.status = ReturnStatus.CANCELLED.value

        role_str = actor_user.role if actor_user else "CUSTOMER"
        cls._add_status_history(
            db=db,
            return_request=ret,
            from_status=old_status,
            to_status=ReturnStatus.CANCELLED.value,
            actor=actor_user,
            actor_role=role_str,
            note=f"Hủy yêu cầu đổi/trả: {reason or 'Người dùng hoặc quản trị viên hủy.'}",
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def _process_restock_movement(
        cls,
        db: Session,
        order_item_id: int,
        warehouse_id: int,
        quantity: int,
        return_code: str,
        actor: User,
        movement_type: str,
        note: str,
        grouped_allocations: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Xử lý ghi nhận biến động kho và cập nhật số lượng tồn kho theo lô.
        Hỗ trợ phân bổ đơn hàng nhiều lô (multi-batch) và gộp lô.
        """
        if quantity <= 0:
            return

        if movement_type == "RETURN_RESTOCK":
            ReturnRestockService.execute_return_restock(
                db=db,
                source_type="RETURN_REQUEST",
                source_code=return_code,
                warehouse_id=warehouse_id,
                items_to_restock=[{
                    "order_item_id": order_item_id,
                    "qty_to_restock": quantity,
                }],
                actor_user_id=actor.id,
                audit_note=note,
            )
            return

        if not grouped_allocations:
            allocations = db.scalars(
                select(OrderItemBatchAllocation)
                .where(OrderItemBatchAllocation.order_item_id == order_item_id)
                .order_by(OrderItemBatchAllocation.id.asc())
            ).all()

            if not allocations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Không tìm thấy thông tin lô xuất kho gốc cho sản phẩm (order_item #{order_item_id}). Không thể nhập lại kho bán được để đảm bảo toàn vẹn dữ liệu thuốc.",
                )

            grouped_allocations = []
            seen_batches: dict[int, dict[str, Any]] = {}
            for alloc in allocations:
                if not alloc.batch_id:
                    continue
                if alloc.batch_id not in seen_batches:
                    entry = {
                        "batch_id": alloc.batch_id,
                        "warehouse_id": alloc.warehouse_id,
                        "allocated_quantity": alloc.allocated_quantity,
                    }
                    seen_batches[alloc.batch_id] = entry
                    grouped_allocations.append(entry)
                else:
                    seen_batches[alloc.batch_id]["allocated_quantity"] += alloc.allocated_quantity

        remaining_qty = quantity
        for g in grouped_allocations:
            if remaining_qty <= 0:
                break
            portion = min(remaining_qty, g["allocated_quantity"])
            remaining_qty -= portion

            batch_id = g["batch_id"]
            batch_wh_id = g["warehouse_id"]

            batch = db.scalar(select(InventoryBatch).where(InventoryBatch.id == batch_id))
            if not batch:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Lô xuất gốc #{batch_id} không tồn tại trong hệ thống.",
                )

            batch_stock = db.scalar(
                select(WarehouseBatchStock).where(
                    WarehouseBatchStock.warehouse_id == batch_wh_id,
                    WarehouseBatchStock.batch_id == batch_id,
                )
            )

            current_balance = batch_stock.quantity_on_hand if batch_stock else 0
            new_balance = current_balance

            if movement_type == "RETURN_RESTOCK":
                # Chỉ tăng tồn khi nhập lại kho bán được
                if not batch_stock:
                    batch_stock = WarehouseBatchStock(
                        warehouse_id=batch_wh_id,
                        batch_id=batch_id,
                        quantity_on_hand=portion,
                        quantity_available=portion,
                        quantity_reserved=0,
                    )
                    db.add(batch_stock)
                    new_balance = portion
                else:
                    batch_stock.quantity_on_hand += portion
                    batch_stock.quantity_available += portion
                    new_balance = batch_stock.quantity_on_hand

            # Ghi nhận StockMovement
            movement_code = f"MOV-{movement_type}-{uuid.uuid4().hex[:6].upper()}"
            mv = StockMovement(
                movement_code=movement_code,
                movement_type=movement_type,
                warehouse_id=batch_wh_id,
                batch_id=batch_id,
                quantity=portion,
                balance_after=new_balance,
                reference_type="RETURN_REQUEST",
                reference_id=return_code,
                created_by=actor.id,
                note=note,
            )
            db.add(mv)

    @classmethod
    def _add_status_history(
        cls,
        db: Session,
        return_request: ReturnRequest,
        from_status: str | None,
        to_status: str,
        actor: User | None,
        actor_role: str,
        note: str | None = None,
    ) -> ReturnStatusHistory:
        """
        Thêm bản ghi lịch sử trạng thái đổi/trả.
        """
        history = ReturnStatusHistory(
            return_request_id=return_request.id,
            from_status=from_status or "INITIAL",
            to_status=to_status,
            actor_id=actor.id if actor else None,
            actor_name=actor.full_name if actor and actor.full_name else (actor.username if actor else "Hệ thống"),
            actor_role=actor_role,
            note=note,
            created_at=utcnow(),
        )
        db.add(history)
        return history
