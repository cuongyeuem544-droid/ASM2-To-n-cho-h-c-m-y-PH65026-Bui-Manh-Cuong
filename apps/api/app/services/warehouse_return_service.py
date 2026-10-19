"""
apps/api/app/services/warehouse_return_service.py

Dịch vụ Quản lý Ca Hoàn Hàng Theo Kho (Warehouse Return Case Service) H4CARE:
- Tách yêu cầu hoàn cha (ReturnRequest) thành các ca hoàn con (WarehouseReturnCase) theo kho thực tế xuất thuốc.
- Quản lý Máy trạng thái Ca Hoàn:
  REQUESTED -> ASSIGNED_TO_WAREHOUSE -> WAITING_CUSTOMER_SHIPMENT -> IN_TRANSIT -> RECEIVED ->
  INSPECTING -> WAITING_MANAGER_APPROVAL -> APPROVED / REJECTED -> REFUND_PENDING ->
  REFUND_PROCESSING -> REFUNDED / REFUND_FAILED -> RESTOCKED / QUARANTINED / DISPOSED -> CLOSED
- Phân quyền RBAC nghiêm ngặt: Nhân viên chỉ kiểm hàng; Quản lý kho duyệt & hoàn tiền; Admin giám sát / Override.
- Tính toán tiền hoàn bất biến do backend quản lý.
- Phân luồng kho GSP: Restock (tăng tồn đúng 1 lần), Quarantine, Dispose.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, date, timedelta
from decimal import Decimal
from typing import Any, Sequence

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import verify_password
from app.models.entities import AdminAlert, AuditLog, Order, OrderItem, User
from app.models.inventory import (
    EmailOutbox,
    FulfillmentItem,
    InventoryBatch,
    OrderFulfillment,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import (
    ItemCondition,
    Refund,
    RefundMethod,
    RefundStatus,
    ReturnEvidence,
    ReturnEvidenceRequest,
    ReturnEvidenceRequestStatus,
    ReturnInspection,
    ReturnItem,
    ReturnRequest,
    ReturnStatus,
    ReturnStatusHistory,
    WarehouseReturnCase,
)
from app.services.alert_notifier import dispatch_alert
from app.services.audit import write_audit
from app.services.refund_calculation_service import RefundCalculationService
from app.services.refund_service import RefundService
from app.services.return_restock_service import ReturnRestockService

logger = logging.getLogger("pharmatrust.warehouse_returns")


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class WarehouseReturnService:
    """
    Dịch vụ xử lý nghiệp vụ ca hoàn hàng theo từng kho.
    """

    @classmethod
    def split_return_request_into_cases(
        cls,
        db: Session,
        return_request: ReturnRequest,
        return_items: Sequence[ReturnItem] | None = None,
        order: Order | None = None,
    ) -> list[WarehouseReturnCase]:
        """
        Xác định kho thực tế đã xuất từng sản phẩm và tạo các WarehouseReturnCase con.
        """
        if return_items is None:
            return_items = return_request.items or list(
                db.scalars(select(ReturnItem).where(ReturnItem.return_request_id == return_request.id)).all()
            )
        if order is None:
            order = return_request.order or db.get(Order, return_request.order_id)

        # Nhóm các sản phẩm theo warehouse_id
        items_by_wh: dict[int, list[ReturnItem]] = {}
        for item in return_items:
            # 1. Tra cứu từ OrderItemBatchAllocation (Lô hàng thực tế đã xuất từ kho nào)
            alloc = db.scalars(
                select(OrderItemBatchAllocation)
                .where(OrderItemBatchAllocation.order_item_id == item.order_item_id)
            ).first()
            if alloc and alloc.warehouse_id:
                wh_id = alloc.warehouse_id
            else:
                # 2. Tra cứu từ FulfillmentItem -> OrderFulfillment
                ful_item = db.scalars(
                    select(FulfillmentItem).where(FulfillmentItem.order_item_id == item.order_item_id)
                ).first()
                if ful_item and ful_item.fulfillment and ful_item.fulfillment.warehouse_id:
                    wh_id = ful_item.fulfillment.warehouse_id
                elif order and order.assigned_warehouse_id:
                    wh_id = order.assigned_warehouse_id
                else:
                    first_wh = db.scalars(select(Warehouse.id).where(Warehouse.is_active == True)).first()
                    wh_id = first_wh or 1

            item.warehouse_id = wh_id
            items_by_wh.setdefault(wh_id, []).append(item)

        today_str = datetime.now(UTC).strftime("%y%m%d")
        cases_created: list[WarehouseReturnCase] = []

        for wh_id, wh_items in items_by_wh.items():
            wh_obj = db.get(Warehouse, wh_id)
            wh_code = wh_obj.code if wh_obj else f"WH{wh_id}"
            unique_suffix = uuid.uuid4().hex[:4].upper()
            case_code = f"WRC-{today_str}-{wh_code}-{unique_suffix}"

            # Tìm fulfillment_id nếu có
            ful_id = None
            if wh_items:
                ful_item = db.scalars(
                    select(FulfillmentItem)
                    .where(FulfillmentItem.order_item_id == wh_items[0].order_item_id)
                ).first()
                if ful_item:
                    ful_id = ful_item.fulfillment_id

            wcase = WarehouseReturnCase(
                case_code=case_code,
                return_request_id=return_request.id,
                warehouse_id=wh_id,
                fulfillment_id=ful_id,
                status=ReturnStatus.ASSIGNED_TO_WAREHOUSE.value,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(wcase)
            db.flush()

            for it in wh_items:
                it.return_request_id = return_request.id
                it.warehouse_return_case_id = wcase.id
                it.warehouse_id = wh_id
                db.add(it)

            cases_created.append(wcase)

            # Ghi nhận lịch sử cho ca hoàn con
            cls._add_case_history(
                db=db,
                case=wcase,
                from_status=None,
                to_status=ReturnStatus.ASSIGNED_TO_WAREHOUSE.value,
                actor=None,
                actor_role="SYSTEM",
                note=f"Tạo ca hoàn kho '{wh_code}' cho {len(wh_items)} sản phẩm từ yêu cầu {return_request.return_code}",
            )

        # Cập nhật trạng thái yêu cầu cha sang ASSIGNED_TO_WAREHOUSE
        return_request.status = ReturnStatus.ASSIGNED_TO_WAREHOUSE.value
        db.add(return_request)

        # Gửi thông báo RETURN_NEW cho từng quản lý kho phụ trách
        for c in cases_created:
            try:
                from app.services.warehouse_notification_service import WarehouseNotificationService
                WarehouseNotificationService.notify_return_new(db, return_request, c.warehouse_id)
            except Exception as ex:
                logger.warning(f"Failed to create RETURN_NEW notification for case {c.case_code}: {ex}")

        db.flush()

        logger.info(
            f"[WRC] Đã tách yêu cầu {return_request.return_code} thành {len(cases_created)} ca hoàn cho các kho: "
            f"{[c.case_code for c in cases_created]}"
        )
        return cases_created

    @classmethod
    def get_case_by_identifier(
        cls,
        db: Session,
        identifier: str,
        warehouse_id: int | None = None,
    ) -> WarehouseReturnCase:
        """
        Tra cứu ca hoàn con theo case_code hoặc return_code (kèm kiểm tra quyền sở hữu kho nếu có).
        """
        query = (
            select(WarehouseReturnCase)
            .options(
                selectinload(WarehouseReturnCase.items),
                selectinload(WarehouseReturnCase.inspections),
                selectinload(WarehouseReturnCase.evidences),
                selectinload(WarehouseReturnCase.refunds),
                selectinload(WarehouseReturnCase.history),
                selectinload(WarehouseReturnCase.warehouse),
                selectinload(WarehouseReturnCase.return_request),
                selectinload(WarehouseReturnCase.assigned_staff),
                selectinload(WarehouseReturnCase.inspected_by_user),
                selectinload(WarehouseReturnCase.approved_by_user),
                selectinload(WarehouseReturnCase.refund_processed_by_user),
            )
            .join(ReturnRequest, WarehouseReturnCase.return_request_id == ReturnRequest.id)
            .where(
                or_(
                    WarehouseReturnCase.case_code == identifier,
                    ReturnRequest.return_code == identifier,
                )
            )
        )

        if warehouse_id is not None:
            query = query.where(WarehouseReturnCase.warehouse_id == warehouse_id)

        case = db.scalars(query).first()
        if not case:
            if warehouse_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Không tìm thấy ca hoàn '{identifier}' thuộc kho của bạn (hoặc bạn không có quyền truy cập ca của kho khác).",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy ca hoàn '{identifier}'.",
            )
        return case

    @classmethod
    def assign_staff(
        cls,
        db: Session,
        case_code: str,
        staff_id: int,
        manager_user: User,
        warehouse_id: int | None,
    ) -> WarehouseReturnCase:
        """
        Quản lý kho phân công nhân viên kiểm hàng.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        # Kiểm tra nhân viên có thuộc cùng kho không
        from app.models.inventory import UserWarehouseMembership
        membership = db.scalar(
            select(UserWarehouseMembership).where(
                UserWarehouseMembership.user_id == staff_id,
                UserWarehouseMembership.warehouse_id == case.warehouse_id,
                UserWarehouseMembership.is_active.is_(True),
            )
        )
        if not membership and manager_user.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nhân viên được phân công không thuộc kho này hoặc tài khoản không hoạt động.",
            )

        staff_user = db.get(User, staff_id)
        if not staff_user:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên.")

        case.assigned_staff_id = staff_id
        case.updated_at = utcnow()

        cls._add_case_history(
            db=db,
            case=case,
            from_status=case.status,
            to_status=case.status,
            actor=manager_user,
            actor_role=manager_user.role,
            note=f"Phân công nhân viên: {staff_user.full_name} ({staff_user.phone})",
        )

        write_audit(
            db=db,
            action="ASSIGN_RETURN_STAFF",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=manager_user,
            details=f"Gán nhân viên ID {staff_id} ({staff_user.full_name}) xử lý ca hoàn {case.case_code}",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def staff_receive_package(
        cls,
        db: Session,
        case_code: str,
        staff_user: User,
        warehouse_id: int | None,
        carrier_name: str | None = None,
        tracking_code: str | None = None,
        package_condition: str = "SEALED",
        note: str | None = None,
    ) -> WarehouseReturnCase:
        """
        Nhân viên kho tiếp nhận gói hàng từ bưu tá / đơn vị vận chuyển.
        Trạng thái chuyển sang: RECEIVED.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        valid_prev = [
            ReturnStatus.REQUESTED.value,
            ReturnStatus.ASSIGNED_TO_WAREHOUSE.value,
            ReturnStatus.WAITING_CUSTOMER_SHIPMENT.value,
            ReturnStatus.WAITING_CUSTOMER_RETURN.value,
            ReturnStatus.IN_TRANSIT.value,
            ReturnStatus.RETURN_IN_TRANSIT.value,
        ]
        if case.status not in valid_prev:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ca hoàn đang ở trạng thái '{case.status}', không thể tiếp nhận lại.",
            )

        old_status = case.status
        case.status = ReturnStatus.RECEIVED.value
        case.carrier_name = carrier_name or case.carrier_name
        case.tracking_code = tracking_code or case.tracking_code
        case.package_condition = package_condition
        case.updated_at = utcnow()

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.RECEIVED.value,
            actor=staff_user,
            actor_role=staff_user.role,
            note=note or f"Nhân viên kho nhận kiện hàng từ bưu tá ({carrier_name or 'ĐVVC'}). Tình trạng bao bì: {package_condition}",
        )

        write_audit(
            db=db,
            action="RECEIVE_RETURN_PACKAGE",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=staff_user,
            details=f"Tiếp nhận hàng hoàn {case.case_code}, vận đơn: {tracking_code}, bao bì: {package_condition}",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def record_evidence(
        cls,
        db: Session,
        case_code: str,
        user: User,
        warehouse_id: int | None,
        file_url: str,
        file_name: str,
        mime_type: str = "image/jpeg",
        file_category: str = "DAMAGE_PHOTO",
        file_size: int = 0,
        description: str | None = None,
        video_url: str | None = None,
        return_item_id: int | None = None,
    ) -> ReturnEvidence:
        """
        Lưu ảnh hoặc video bằng chứng kiểm hàng.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        evidence = ReturnEvidence(
            return_request_id=case.return_request_id,
            warehouse_return_case_id=case.id,
            return_item_id=return_item_id,
            file_url=file_url,
            file_name=file_name,
            mime_type=mime_type,
            file_category=file_category,
            file_size=file_size,
            description=description,
            video_url=video_url,
            uploaded_by=user.id,
            created_at=utcnow(),
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        return evidence

    @classmethod
    def staff_inspect_items(
        cls,
        db: Session,
        case_code: str,
        staff_user: User,
        warehouse_id: int | None,
        inspections_data: list[dict[str, Any]],
        general_note: str | None = None,
    ) -> WarehouseReturnCase:
        """
        Nhân viên kho kiểm đếm, ghi nhận số lô, HSD, tem niêm phong và đề xuất xử lý.
        Trạng thái chuyển sang: INSPECTING.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        if case.status not in [ReturnStatus.RECEIVED.value, ReturnStatus.INSPECTING.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ca hoàn đang ở trạng thái '{case.status}', không thể lập biên bản kiểm tra.",
            )

        old_status = case.status
        case.status = ReturnStatus.INSPECTING.value
        case.updated_at = utcnow()

        item_map = {item.id: item for item in case.items}

        for insp_in in inspections_data:
            item_id = insp_in.get("return_item_id")
            if item_id not in item_map:
                continue

            ret_item = item_map[item_id]
            rec_qty = int(insp_in.get("received_quantity", ret_item.requested_quantity))
            acc_qty = int(insp_in.get("accepted_quantity", rec_qty))
            rej_qty = int(insp_in.get("rejected_quantity", max(0, rec_qty - acc_qty)))

            # Cập nhật hoặc tạo mới ReturnInspection
            existing_insp = db.scalar(
                select(ReturnInspection).where(
                    ReturnInspection.case_id == case.id,
                    ReturnInspection.return_item_id == item_id,
                )
            )

            if not existing_insp:
                existing_insp = ReturnInspection(
                    case_id=case.id,
                    return_item_id=item_id,
                    created_at=utcnow(),
                )
                db.add(existing_insp)

            # Xác thực bắt buộc các trường kiểm định theo quy chuẩn an toàn dược phẩm
            required_fields = [
                "package_condition",
                "seal_intact",
                "batch_matched",
                "expiry_matched",
                "storage_condition_ok",
                "suggested_action",
            ]
            for rf in required_fields:
                if rf not in insp_in or insp_in.get(rf) is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Thiếu trường kiểm định bắt buộc: {rf}",
                    )

            pkg_cond = str(insp_in["package_condition"]).strip()
            if not pkg_cond:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Thiếu trường kiểm định bắt buộc: package_condition",
                )

            seal_intact = bool(insp_in["seal_intact"])
            batch_matched = bool(insp_in["batch_matched"])
            expiry_matched = bool(insp_in["expiry_matched"])
            storage_condition_ok = bool(insp_in["storage_condition_ok"])
            sug_action = str(insp_in["suggested_action"]).strip().upper()
            if not sug_action:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Thiếu trường kiểm định bắt buộc: suggested_action",
                )

            # Quy tắc an toàn dược phẩm: Bất kỳ tiêu chí an toàn nào không đạt -> CẤM RESTOCK
            if not (seal_intact and batch_matched and expiry_matched and storage_condition_ok):
                if sug_action == "RESTOCK":
                    failed_criteria = []
                    if not seal_intact:
                        failed_criteria.append("tem niêm phong không nguyên vẹn (seal_intact=False)")
                    if not batch_matched:
                        failed_criteria.append("số lô không khớp đã xuất (batch_matched=False)")
                    if not expiry_matched:
                        failed_criteria.append("hạn sử dụng không khớp (expiry_matched=False)")
                    if not storage_condition_ok:
                        failed_criteria.append("điều kiện bảo quản không đạt chuẩn (storage_condition_ok=False)")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Sản phẩm không đạt chuẩn an toàn dược phẩm ({', '.join(failed_criteria)}). Tuyệt đối không được đề xuất hoặc nhập lại kho bán (RESTOCK).",
                    )

            existing_insp.received_quantity = rec_qty
            existing_insp.accepted_quantity = acc_qty
            existing_insp.rejected_quantity = rej_qty
            existing_insp.package_condition = pkg_cond
            existing_insp.seal_intact = seal_intact
            existing_insp.batch_matched = batch_matched
            existing_insp.expiry_matched = expiry_matched
            existing_insp.storage_condition_ok = storage_condition_ok
            existing_insp.damage_description = insp_in.get("damage_description")
            existing_insp.suggested_action = sug_action
            existing_insp.inspected_by = staff_user.id
            existing_insp.inspected_at = utcnow()
            existing_insp.inspection_note = insp_in.get("inspection_note")

            # Cập nhật số lượng tạm vào return_item
            ret_item.received_quantity = rec_qty
            ret_item.condition = existing_insp.package_condition
            ret_item.inspection_note = existing_insp.inspection_note
            db.add(ret_item)

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.INSPECTING.value,
            actor=staff_user,
            actor_role=staff_user.role,
            note=general_note or f"Nhân viên ghi nhận biên bản kiểm hàng cho {len(inspections_data)} sản phẩm",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def staff_submit_inspection(
        cls,
        db: Session,
        case_code: str,
        staff_user: User,
        warehouse_id: int | None,
        note: str | None = None,
    ) -> WarehouseReturnCase:
        """
        Nhân viên hoàn tất kiểm hàng và nộp kết quả lên Quản lý kho.
        Trạng thái chuyển sang: WAITING_MANAGER_APPROVAL.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        if case.status != ReturnStatus.INSPECTING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể nộp kết quả khi ca hoàn đang ở trạng thái 'Đang kiểm tra' (INSPECTING).",
            )

        if not case.inspections or len(case.inspections) < len(case.items):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vui lòng lập biên bản kiểm tra đầy đủ cho tất cả {len(case.items)} sản phẩm trước khi nộp lên Quản lý.",
            )

        # Kiểm tra tính toàn vẹn và độ tin cậy của biên bản kiểm định dược phẩm
        inspected_item_ids = {insp.return_item_id for insp in case.inspections}
        for it in case.items:
            if it.id not in inspected_item_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sản phẩm '{it.product_name}' chưa được kiểm định. Tuyệt đối không được nộp hồ sơ thiếu dữ liệu kiểm định.",
                )

        for insp in case.inspections:
            if (
                not insp.package_condition
                or insp.seal_intact is None
                or insp.batch_matched is None
                or insp.expiry_matched is None
                or insp.storage_condition_ok is None
                or not insp.suggested_action
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Biên bản kiểm định thiếu chỉ số an toàn bắt buộc (bao bì, niêm phong, khớp lô, hạn dùng, bảo quản hoặc đề xuất xử lý). Không thể coi là đạt khi thiếu dữ liệu.",
                )
            if not (insp.seal_intact and insp.batch_matched and insp.expiry_matched and insp.storage_condition_ok):
                if (insp.suggested_action or "").upper() == "RESTOCK":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Sản phẩm không đạt đầy đủ tiêu chuẩn an toàn dược phẩm. Nghiêm cấm đề xuất hoặc nhập lại kho bán (RESTOCK).",
                    )

        old_status = case.status
        case.status = ReturnStatus.WAITING_MANAGER_APPROVAL.value
        case.inspected_by_user_id = staff_user.id
        case.inspected_at = utcnow()
        case.updated_at = utcnow()

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
            actor=staff_user,
            actor_role=staff_user.role,
            note=note or "Nhân viên nộp kết quả kiểm hàng. Chờ Quản lý kho xem xét và phê duyệt.",
        )

        # Bắn cảnh báo cho Quản lý kho
        alert = AdminAlert(
            source_code="WAREHOUSE_RETURN",
            alert_type="RETURN_WAITING_APPROVAL",
            severity="INFO",
            message=f"Ca hoàn [{case.case_code}] tại kho {case.warehouse.name} đã được kiểm tra xong, chờ duyệt.",
            is_read=False,
        )
        db.add(alert)

        write_audit(
            db=db,
            action="SUBMIT_RETURN_INSPECTION",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=staff_user,
            details=f"Nộp biên bản kiểm tra ca {case.case_code} lên Quản lý kho",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def request_reinspection(
        cls,
        db: Session,
        case_code: str,
        manager_user: User,
        warehouse_id: int | None,
        reason: str,
    ) -> WarehouseReturnCase:
        """
        Quản lý kho yêu cầu nhân viên kiểm tra lại khi phát hiện bất thường.
        Trạng thái chuyển về: INSPECTING.
        """
        if not reason or len(reason.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lý do yêu cầu kiểm tra lại bắt buộc phải từ 5 ký tự trở lên.",
            )

        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        if case.status != ReturnStatus.WAITING_MANAGER_APPROVAL.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể yêu cầu kiểm tra lại khi đơn đang chờ duyệt (WAITING_MANAGER_APPROVAL).",
            )

        old_status = case.status
        case.status = ReturnStatus.INSPECTING.value
        case.manager_note = (case.manager_note or "") + f"\n[{utcnow().strftime('%d/%m %H:%M')}] YÊU CẦU KIỂM LẠI: {reason.strip()}"
        case.updated_at = utcnow()

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.INSPECTING.value,
            actor=manager_user,
            actor_role=manager_user.role,
            note=f"Quản lý kho yêu cầu kiểm tra lại: {reason.strip()}",
        )

        write_audit(
            db=db,
            action="REQUEST_REINSPECTION",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=manager_user,
            details=f"Yêu cầu kiểm tra lại ca {case.case_code}: {reason.strip()}",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def manager_approve_case(
        cls,
        db: Session,
        case_code: str,
        manager_user: User,
        warehouse_id: int | None,
        items_approval: list[dict[str, Any]] | None = None,
        manager_note: str | None = None,
    ) -> WarehouseReturnCase:
        """
        Quản lý kho phê duyệt đơn hoàn (toàn bộ hoặc 1 phần).
        Trạng thái chuyển sang: APPROVED -> REFUND_PENDING.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        if case.status != ReturnStatus.WAITING_MANAGER_APPROVAL.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể phê duyệt khi ca hoàn đang ở trạng thái 'Chờ duyệt' (WAITING_MANAGER_APPROVAL).",
            )

        old_status = case.status
        case_items = list(case.items)
        if not case_items and case.return_request:
            case_items = list(case.return_request.items)

        if not items_approval:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng cung cấp danh sách phê duyệt chi tiết (items) cho từng sản phẩm do Quản lý kho duyệt. Tuyệt đối không tự động duyệt khi thiếu dữ liệu.",
            )

        item_map = {item.id: item for item in case_items}
        submitted_ids = {app.get("return_item_id") for app in items_approval}

        # 1. Kiểm tra không có sản phẩm lạ
        for it_id in submitted_ids:
            if it_id not in item_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sản phẩm #{it_id} không thuộc ca hoàn {case.case_code}.",
                )

        # 2. Kiểm tra bắt buộc có mặt đầy đủ mọi sản phẩm của ca hoàn
        for it_id, it in item_map.items():
            if it_id not in submitted_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Thiếu thông tin phê duyệt cho sản phẩm '{it.product_name}' (ID #{it_id}). Quản lý kho bắt buộc phải duyệt/từ chối tất cả sản phẩm trong ca hoàn.",
                )

        total_accepted = 0
        approval_details = []

        for app_in in items_approval:
            it_id = app_in.get("return_item_id")
            ret_item = item_map[it_id]
            if "approved_quantity" not in app_in or app_in.get("approved_quantity") is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vui lòng chỉ định số lượng duyệt (approved_quantity) cho sản phẩm '{ret_item.product_name}'.",
                )
            acc_q = int(app_in["approved_quantity"])
            raw_rej = app_in.get("rejected_quantity")
            if raw_rej is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Vui lòng chỉ định rõ số lượng từ chối (rejected_quantity) cho sản phẩm '{ret_item.product_name}'.",
                )
            rej_q = int(raw_rej)

            if acc_q < 0 or rej_q < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng duyệt ({acc_q}) và từ chối ({rej_q}) của '{ret_item.product_name}' không được âm.",
                )

            if acc_q > ret_item.requested_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng duyệt ({acc_q}) không thể vượt quá số lượng yêu cầu hoàn ({ret_item.requested_quantity}) cho sản phẩm '{ret_item.product_name}'.",
                )

            if ret_item.received_quantity is not None and ret_item.received_quantity > 0 and acc_q > ret_item.received_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng duyệt ({acc_q}) không thể vượt quá số lượng thực nhận ({ret_item.received_quantity}) cho sản phẩm '{ret_item.product_name}'.",
                )

            if rej_q > 0:
                rej_reason = app_in.get("rejection_reason") or app_in.get("reason")
                if not rej_reason or not str(rej_reason).strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Sản phẩm '{ret_item.product_name}' có {rej_q} đơn vị bị từ chối, bắt buộc phải nêu rõ lý do từ chối (rejection_reason).",
                    )
                ret_item.inspection_note = f"{ret_item.inspection_note or ''} [Lý do từ chối {rej_q} sp: {str(rej_reason).strip()}]".strip()

            ret_item.approved_quantity = acc_q
            ret_item.rejected_quantity = rej_q

            # BẮT BUỘC: Tính lại tiền hoàn được duyệt theo approved_quantity do Quản lý kho duyệt
            net_unit = RefundCalculationService.calculate_net_unit_price(case.return_request.order, ret_item.order_item)
            ret_item.approved_refund_amount = net_unit * Decimal(str(acc_q))
            db.add(ret_item)
            total_accepted += acc_q
            approval_details.append(f"SP #{ret_item.product_id} ({ret_item.product_name}): duyệt {acc_q}, từ chối {rej_q}")

        if total_accepted == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tổng số lượng sản phẩm được duyệt là 0. Nếu không chấp nhận hoàn hàng, Quản lý kho bắt buộc phải sử dụng chức năng 'Từ chối' (reject).",
            )

        case.status = ReturnStatus.REFUND_PENDING.value
        case.approved_by_user_id = manager_user.id
        case.approved_at = utcnow()
        if manager_note:
            case.manager_note = (case.manager_note or "") + f"\n[{utcnow().strftime('%d/%m %H:%M')}] DUYỆT: {manager_note.strip()}"
        case.updated_at = utcnow()

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.REFUND_PENDING.value,
            actor=manager_user,
            actor_role=manager_user.role,
            note=manager_note or f"Quản lý kho phê duyệt {total_accepted} sản phẩm. Sẵn sàng hoàn tiền.",
        )

        write_audit(
            db=db,
            action="APPROVE_RETURN_CASE",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=manager_user,
            details=f"Quản lý phê duyệt ca hoàn {case.case_code}, tổng số lượng duyệt: {total_accepted}",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def manager_reject_case(
        cls,
        db: Session,
        case_code: str,
        manager_user: User,
        warehouse_id: int | None,
        rejection_reason: str,
    ) -> WarehouseReturnCase:
        """
        Quản lý kho từ chối yêu cầu hoàn (BẮT BUỘC nhập lý do từ chối).
        Trạng thái chuyển sang: REJECTED -> CLOSED.
        """
        if not rejection_reason or len(rejection_reason.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lý do từ chối bắt buộc phải từ 5 ký tự trở lên để đảm bảo tính minh bạch.",
            )

        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        if case.status not in [ReturnStatus.WAITING_MANAGER_APPROVAL.value, ReturnStatus.INSPECTING.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Không thể từ chối ca hoàn ở trạng thái '{case.status}'.",
            )

        old_status = case.status
        case.status = ReturnStatus.REJECTED.value
        case.rejection_reason = rejection_reason.strip()
        case.approved_by_user_id = manager_user.id
        case.closed_at = utcnow()
        case.updated_at = utcnow()

        # Đặt approved_quantity = 0 trên tất cả các item
        for it in case.items:
            it.approved_quantity = 0
            it.rejected_quantity = it.requested_quantity
            it.approved_refund_amount = Decimal("0.0")
            db.add(it)

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.REJECTED.value,
            actor=manager_user,
            actor_role=manager_user.role,
            note=f"Quản lý kho từ chối yêu cầu: {rejection_reason.strip()}",
        )

        write_audit(
            db=db,
            action="REJECT_RETURN_CASE",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=manager_user,
            details=f"Từ chối ca hoàn {case.case_code}. Lý do: {rejection_reason.strip()}",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def manager_process_refund(
        cls,
        db: Session,
        case_code: str,
        manager_user: User,
        warehouse_id: int | None,
        password: str,
        refund_method: str = RefundMethod.BANK_TRANSFER.value,
        beneficiary_bank: str | None = None,
        beneficiary_account_number: str | None = None,
        beneficiary_account_name: str | None = None,
        manual_reference_number: str | None = None,
        manual_proof_storage_key: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Quản lý kho thực hiện hoàn tiền sau khi đã duyệt:
        - Bắt buộc xác thực lại mật khẩu của Quản lý kho.
        - Backend TỰ ĐỘNG TÍNH số tiền hoàn; không cho phép frontend tùy ý sửa.
        - Khóa đơn, ngăn chặn hoàn tiền trùng lặp.
        - Gọi MoMo sandbox nếu thanh toán online, hoặc ghi nhận UNC chuyển khoản.
        """
        # 1. Xác thực lại mật khẩu bảo mật
        if not verify_password(password, manager_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Mật khẩu xác nhận không chính xác. Thao tác hoàn tiền bị từ chối.",
            )

        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        if case.status not in [ReturnStatus.APPROVED.value, ReturnStatus.REFUND_PENDING.value, ReturnStatus.REFUND_FAILED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ca hoàn chưa được duyệt hoặc không ở trạng thái sẵn sàng hoàn tiền (Hiện tại: '{case.status}').",
            )

        # 2. Khóa ngăn chặn bấm hoàn lần 2 (Concurrency & Idempotency)
        existing_active_refund = db.scalar(
            select(Refund).where(
                Refund.warehouse_return_case_id == case.id,
                Refund.status.in_([RefundStatus.SUCCEEDED.value, RefundStatus.PROCESSING.value]),
            )
        )
        if existing_active_refund:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ca hoàn này đã có giao dịch hoàn tiền đang được xử lý hoặc đã thành công (Mã hoàn: {existing_active_refund.refund_code}).",
            )

        # 3. Backend TỰ ĐỘNG TÍNH TOÁN số tiền hoàn
        order = case.return_request.order
        accepted_items = [it for it in case.items if (it.approved_quantity or 0) > 0]
        if not accepted_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không có sản phẩm nào trong ca hoàn này được duyệt để hoàn tiền.",
            )

        # Kiểm tra từng mặt hàng được duyệt: không âm, không vượt requested, không vượt received
        for it in accepted_items:
            app_q = it.approved_quantity or 0
            if app_q < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng duyệt ({app_q}) của sản phẩm '{it.product_name}' không hợp lệ (< 0).",
                )
            if app_q > (it.requested_quantity or 0):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng duyệt ({app_q}) vượt quá số lượng yêu cầu ({it.requested_quantity}) của sản phẩm '{it.product_name}'.",
                )
            if it.received_quantity is not None and it.received_quantity > 0 and app_q > it.received_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng duyệt ({app_q}) vượt quá số lượng thực nhận ({it.received_quantity}) của sản phẩm '{it.product_name}'.",
                )

        items_refund_total = Decimal("0.0")
        for it in accepted_items:
            net_unit = RefundCalculationService.calculate_net_unit_price(order, it.order_item)
            line_amount = net_unit * Decimal(str(it.approved_quantity))
            it.approved_refund_amount = line_amount
            items_refund_total += line_amount
            db.add(it)

        # Kiểm tra trần tối đa còn lại của đơn hàng
        already_refunded = RefundCalculationService.get_already_refunded_amount(db, order.id)
        order_total = Decimal(str(order.total_amount))
        max_possible_refund = max(Decimal("0.0"), order_total - already_refunded)

        final_refund_amount = min(items_refund_total, max_possible_refund)
        if final_refund_amount <= Decimal("0.0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Đơn hàng này đã hoàn đủ hạn mức ({int(already_refunded):,} đ / {int(order_total):,} đ). Không thể hoàn thêm.",
            )

        # 4. Sinh mã hoàn tiền & Idempotency key
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        unique_suffix = uuid.uuid4().hex[:4].upper()
        refund_code = f"REF-{today_str}-{unique_suffix}"
        effective_idempotency = idempotency_key or f"IDEMP-REF-{case.case_code}-{unique_suffix}"

        # Đặt trạng thái ca sang REFUND_PROCESSING
        case.status = ReturnStatus.REFUND_PROCESSING.value
        case.updated_at = utcnow()
        db.flush()

        # Tạo bản ghi Refund
        refund_record = Refund(
            refund_code=refund_code,
            order_id=order.id,
            return_request_id=case.return_request_id,
            warehouse_return_case_id=case.id,
            warehouse_id=case.warehouse_id,
            amount=final_refund_amount,
            currency="VND",
            refund_method=refund_method,
            status=RefundStatus.PROCESSING.value,
            reason=f"Hoàn tiền ca đổi trả chi nhánh {case.case_code}",
            idempotency_key=effective_idempotency,
            beneficiary_bank_name=beneficiary_bank or case.return_request.refunds[0].beneficiary_bank_name if case.return_request.refunds else beneficiary_bank,
            beneficiary_account_number=beneficiary_account_number,
            beneficiary_account_name=beneficiary_account_name,
            manual_reference_number=manual_reference_number,
            manual_proof_storage_key=manual_proof_storage_key,
            approved_by=manager_user.id,
            processed_by=manager_user.id,
            requested_at=utcnow(),
            approved_at=utcnow(),
            processing_at=utcnow(),
            created_at=utcnow(),
        )
        db.add(refund_record)
        db.flush()

        # 5. Xử lý cổng thanh toán hoặc chuyển khoản thủ công
        is_success = False
        error_msg = None

        if refund_method == RefundMethod.MOMO_ONLINE.value:
            try:
                # Gọi sandbox MoMo
                momo_res = RefundService.process_momo_refund(
                    db=db,
                    refund_code=refund_code,
                    admin_user=manager_user,
                    idempotency_key=effective_idempotency,
                )
                is_success = bool(momo_res.get("status") == RefundStatus.SUCCEEDED.value)
            except Exception as e:
                is_success = False
                error_msg = str(e)
        else:
            # Chuyển khoản ngân hàng hoặc COD đã xác nhận UNC
            if manual_reference_number:
                refund_record.status = RefundStatus.SUCCEEDED.value
                refund_record.succeeded_at = utcnow()
                is_success = True
            else:
                # Nếu chưa có mã UNC, đặt sang SUCCEEDED khi Quản lý xác nhận chuyển khoản
                refund_record.status = RefundStatus.SUCCEEDED.value
                refund_record.succeeded_at = utcnow()
                is_success = True

        if is_success:
            case.status = ReturnStatus.REFUNDED.value
            case.refund_processed_by_user_id = manager_user.id
            case.refund_processed_at = utcnow()
            cls._add_case_history(
                db=db,
                case=case,
                from_status=ReturnStatus.REFUND_PROCESSING.value,
                to_status=ReturnStatus.REFUNDED.value,
                actor=manager_user,
                actor_role=manager_user.role,
                note=f"Hoàn tiền thành công {int(final_refund_amount):,} đ qua {refund_method}. Mã hoàn: {refund_code}",
            )
            write_audit(
                db=db,
                action="PROCESS_REFUND_SUCCESS",
                entity_type="WAREHOUSE_RETURN_CASE",
                entity_id=case.case_code,
                user=manager_user,
                details=f"Hoàn tiền thành công cho ca {case.case_code}, số tiền: {int(final_refund_amount):,} đ",
            )
        else:
            case.status = ReturnStatus.REFUND_FAILED.value
            refund_record.status = RefundStatus.FAILED.value
            refund_record.failed_at = utcnow()
            refund_record.failure_reason = error_msg
            cls._add_case_history(
                db=db,
                case=case,
                from_status=ReturnStatus.REFUND_PROCESSING.value,
                to_status=ReturnStatus.REFUND_FAILED.value,
                actor=manager_user,
                actor_role=manager_user.role,
                note=f"Hoàn tiền thất bại: {error_msg or 'Lỗi cổng thanh toán'}",
            )
            write_audit(
                db=db,
                action="PROCESS_REFUND_FAILED",
                entity_type="WAREHOUSE_RETURN_CASE",
                entity_id=case.case_code,
                user=manager_user,
                details=f"Hoàn tiền thất bại cho ca {case.case_code}: {error_msg}",
            )

        db.commit()
        db.refresh(case)
        db.refresh(refund_record)

        return {
            "status": "SUCCESS" if is_success else "FAILED",
            "success": is_success,
            "case_code": case.case_code,
            "refund_code": refund_code,
            "refund_amount": float(final_refund_amount),
            "refund_method": refund_method,
            "error": error_msg,
        }

    @classmethod
    def manager_stock_disposition(
        cls,
        db: Session,
        case_code: str,
        manager_user: User,
        warehouse_id: int | None,
        disposition: str,  # RESTOCK | QUARANTINE | DISPOSE
        note: str | None = None,
    ) -> WarehouseReturnCase:
        """
        Quản lý kho phân luồng xử lý hàng sau khi hoàn tất hoàn tiền:
        - RESTOCK: Nhập lại kho (tăng On-hand & Available đúng 1 lần, ghi StockMovement).
        - QUARANTINE: Chuyển cách ly (không tăng tồn có thể bán).
        - DISPOSE: Hủy hàng (lập biên bản, không tăng tồn).
        Trạng thái chuyển sang: RESTOCKED / QUARANTINED / DISPOSED -> CLOSED.
        """
        if disposition not in ["RESTOCK", "QUARANTINE", "DISPOSE"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phương án xử lý không hợp lệ. Chọn RESTOCK, QUARANTINE hoặc DISPOSE.",
            )

        case = cls.get_case_by_identifier(db, case_code, warehouse_id)

        # Idempotency: Kiểm tra ca hoàn đã từng được xử lý phân luồng chưa
        if case.status in [ReturnStatus.RESTOCKED.value, ReturnStatus.QUARANTINED.value, ReturnStatus.DISPOSED.value, ReturnStatus.CLOSED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ca hoàn này đã được xử lý phân luồng hàng trước đó, không thể nhập kho hoặc xử lý lần hai.",
            )

        if case.status not in [ReturnStatus.REFUNDED.value, ReturnStatus.APPROVED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chỉ có thể phân luồng tồn kho khi ca hoàn đã được hoàn tiền hoặc duyệt (Hiện tại: '{case.status}').",
            )

        old_status = case.status
        case_items = list(case.items)
        if not case_items and case.return_request:
            case_items = list(case.return_request.items)

        if disposition == "RESTOCK":
            items_to_restock = []
            for ret_item in case_items:
                qty_restock = ret_item.approved_quantity or 0
                if qty_restock > 0:
                    items_to_restock.append({
                        "order_item_id": ret_item.order_item_id,
                        "product_id": ret_item.product_id,
                        "product_name": ret_item.product_name,
                        "qty_to_restock": qty_restock,
                        "return_item_id": ret_item.id,
                    })

            if not items_to_restock:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không có sản phẩm nào có số lượng được duyệt > 0 để nhập lại kho bán.",
                )

            linked_codes = [case.return_request.return_code] if case.return_request else []
            ReturnRestockService.execute_return_restock(
                db=db,
                source_type="WAREHOUSE_RETURN_CASE",
                source_code=case.case_code,
                warehouse_id=case.warehouse_id,
                items_to_restock=items_to_restock,
                actor_user_id=manager_user.id,
                audit_note=note or f"Nhập lại kho từ ca hoàn {case.case_code}",
                linked_reference_codes=linked_codes,
            )

            for ret_item in case_items:
                if ret_item.approved_quantity and ret_item.approved_quantity > 0:
                    ret_item.restock_quantity = ret_item.approved_quantity
                    db.add(ret_item)

            case.status = ReturnStatus.RESTOCKED.value
        elif disposition == "QUARANTINE":
            case.status = ReturnStatus.QUARANTINED.value
        elif disposition == "DISPOSE":
            case.status = ReturnStatus.DISPOSED.value

        # Ghi nhận thời gian hoàn tất xử lý ca hoàn
        case.closed_at = utcnow()

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.CLOSED.value,
            actor=manager_user,
            actor_role=manager_user.role,
            note=f"Hoàn tất xử lý hàng: {disposition}. Đóng hồ sơ ca hoàn.",
        )

        write_audit(
            db=db,
            action=f"DISPOSITION_{disposition}",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=manager_user,
            details=f"Phân luồng xử lý hàng ca {case.case_code}: {disposition}. Ghi chú: {note}",
        )

        # Kiểm tra xem toàn bộ các ca con của ReturnRequest cha đã hoàn tất chưa
        all_cases = db.scalars(
            select(WarehouseReturnCase).where(WarehouseReturnCase.return_request_id == case.return_request_id)
        ).all()
        if all(c.status in [ReturnStatus.CLOSED.value, ReturnStatus.REJECTED.value] for c in all_cases):
            case.return_request.status = ReturnStatus.CLOSED.value
            case.return_request.closed_at = utcnow()
            db.add(case.return_request)

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def admin_override(
        cls,
        db: Session,
        return_code: str,
        admin_user: User,
        new_status: str,
        reason: str,
        notes: str | None = None,
    ) -> ReturnRequest:
        """
        Admin Override can thiệp khẩn cấp (BẮT BUỘC nhập lý do, ghi AuditLog nghiêm ngặt).
        """
        if not reason or len(reason.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lý do can thiệp Admin Override bắt buộc phải từ 5 ký tự trở lên.",
            )

        ret = db.scalar(
            select(ReturnRequest)
            .options(selectinload(ReturnRequest.warehouse_cases))
            .where(ReturnRequest.return_code == return_code)
        )
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu hoàn '{return_code}'.")

        old_status = ret.status
        ret.status = new_status
        ret.admin_note = (ret.admin_note or "") + f"\n[{utcnow().strftime('%d/%m %H:%M')}] ADMIN OVERRIDE ({admin_user.full_name}): {reason.strip()}"
        ret.updated_at = utcnow()

        # Đồng bộ trạng thái cho các ca con nếu phù hợp
        for c in ret.warehouse_cases:
            c.status = new_status
            c.updated_at = utcnow()
            db.add(c)

        write_audit(
            db=db,
            action="ADMIN_OVERRIDE_RETURN",
            entity_type="RETURN_REQUEST",
            entity_id=ret.return_code,
            user=admin_user,
            details=f"Admin can thiệp khẩn cấp đổi trạng thái từ {old_status} sang {new_status}. Lý do: {reason.strip()}",
        )

        db.commit()
        db.refresh(ret)
        return ret

    @classmethod
    def admin_reassign_warehouse(
        cls,
        db: Session,
        case_code: str,
        new_warehouse_id: int,
        admin_user: User,
        reason: str,
    ) -> WarehouseReturnCase:
        """
        Admin điều phối ca hoàn sang chi nhánh kho khác khi có sự cố.
        """
        if not reason or len(reason.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lý do điều chuyển ca hoàn bắt buộc phải từ 5 ký tự trở lên.",
            )

        case = cls.get_case_by_identifier(db, case_code)
        new_wh = db.get(Warehouse, new_warehouse_id)
        if not new_wh or not new_wh.is_active:
            raise HTTPException(status_code=400, detail="Kho mới không tồn tại hoặc không hoạt động.")

        old_wh_id = case.warehouse_id
        case.warehouse_id = new_warehouse_id
        case.assigned_staff_id = None  # Reset nhân viên phụ trách khi chuyển kho
        case.updated_at = utcnow()

        # Cập nhật warehouse_id cho các items
        for it in case.items:
            it.warehouse_id = new_warehouse_id
            db.add(it)

        cls._add_case_history(
            db=db,
            case=case,
            from_status=case.status,
            to_status=case.status,
            actor=admin_user,
            actor_role=admin_user.role,
            note=f"Admin điều phối chuyển từ kho ID {old_wh_id} sang kho {new_wh.name} (ID {new_warehouse_id}). Lý do: {reason.strip()}",
        )

        write_audit(
            db=db,
            action="REASSIGN_RETURN_WAREHOUSE",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=admin_user,
            details=f"Điều chuyển ca {case.case_code} từ kho {old_wh_id} sang {new_warehouse_id}. Lý do: {reason.strip()}",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def _add_case_history(
        cls,
        db: Session,
        case: WarehouseReturnCase,
        from_status: str | None,
        to_status: str,
        actor: User | None,
        actor_role: str,
        note: str | None = None,
    ) -> ReturnStatusHistory:
        hist = ReturnStatusHistory(
            return_request_id=case.return_request_id,
            warehouse_id=case.warehouse_id,
            warehouse_return_case_id=case.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor.id if actor else None,
            actor_name=actor.full_name if actor else "Hệ thống",
            actor_role=actor_role,
            note=note,
            created_at=utcnow(),
        )
        db.add(hist)
        return hist

    @classmethod
    def request_customer_evidence(
        cls,
        db: Session,
        case_code: str,
        user: User,
        warehouse_id: int | None,
        reason: str,
        instructions: str,
        required_image_count: int,
        return_item_id: int | None = None,
    ) -> ReturnEvidenceRequest:
        """
        Quản lý kho yêu cầu khách hàng bổ sung từ 1 đến 3 ảnh bằng chứng.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id=None)

        # RBAC: Quản lý kho chỉ được yêu cầu cho kho của mình
        if user.role == "WAREHOUSE_MANAGER":
            if case.warehouse_id != user.warehouse_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền yêu cầu bổ sung ảnh cho ca hoàn của chi nhánh kho khác.",
                )
        elif user.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ Quản lý kho mới được yêu cầu khách hàng bổ sung hình ảnh.",
            )

        # Ràng buộc số lượng ảnh từ 1 đến 3
        if not (1 <= required_image_count <= 3):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Số lượng ảnh yêu cầu bắt buộc phải từ 1 đến 3 ảnh.",
            )

        clean_reason = reason.strip() if reason else ""
        clean_instructions = instructions.strip() if instructions else ""
        if len(clean_reason) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Lý do yêu cầu bắt buộc và phải có ít nhất 3 ký tự.",
            )
        if len(clean_instructions) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Hướng dẫn chụp ảnh bắt buộc và phải có ít nhất 3 ký tự.",
            )

        # Ràng buộc: Không tạo 2 yêu cầu bằng chứng đang hoạt động
        existing_active = db.scalar(
            select(ReturnEvidenceRequest).where(
                ReturnEvidenceRequest.warehouse_return_case_id == case.id,
                ReturnEvidenceRequest.status == ReturnEvidenceRequestStatus.OPEN.value,
            )
        )
        if existing_active:
            # Kiểm tra xem yêu cầu cũ có bị quá hạn chưa
            if to_utc(existing_active.expires_at) <= utcnow():
                cls.expire_evidence_request(db, existing_active)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Đã có yêu cầu bổ sung hình ảnh đang mở cho ca hoàn này. Vui lòng chờ khách nộp hoặc hết hạn.",
                )

        if return_item_id:
            matched_item = next((it for it in case.items if it.id == return_item_id), None)
            if not matched_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sản phẩm chỉ định không thuộc ca hoàn này.",
                )

        now = utcnow()
        expires_at = now + timedelta(days=3)
        req_code = f"REQ-EVID-{uuid.uuid4().hex[:8].upper()}"

        evidence_req = ReturnEvidenceRequest(
            request_code=req_code,
            return_request_id=case.return_request_id,
            warehouse_return_case_id=case.id,
            warehouse_id=case.warehouse_id,
            requested_by_user_id=user.id,
            customer_id=case.return_request.user_id if case.return_request else None,
            return_item_id=return_item_id,
            reason=clean_reason,
            instructions=clean_instructions,
            required_image_count=required_image_count,
            status=ReturnEvidenceRequestStatus.OPEN.value,
            requested_at=now,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        db.add(evidence_req)

        # Cập nhật trạng thái ca hoàn và return_request
        old_status = case.status
        case.status = ReturnStatus.WAITING_CUSTOMER_EVIDENCE.value
        case.updated_at = now
        if case.return_request:
            case.return_request.status = ReturnStatus.WAITING_CUSTOMER_EVIDENCE.value
            case.return_request.updated_at = now

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.WAITING_CUSTOMER_EVIDENCE.value,
            actor=user,
            actor_role=user.role,
            note=f"Quản lý kho yêu cầu bổ sung {required_image_count} ảnh. Lý do: {clean_reason}. Hạn chót: {expires_at.strftime('%d/%m/%Y %H:%M')}",
        )

        write_audit(
            db=db,
            action="REQUEST_CUSTOMER_EVIDENCE",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=user,
            details=f"Yêu cầu {required_image_count} ảnh: {clean_reason} (Mã YC: {req_code})",
        )

        db.commit()
        db.refresh(evidence_req)
        return evidence_req

    @classmethod
    def get_customer_evidence_request(
        cls,
        db: Session,
        return_code: str,
        user: User | None = None,
        phone_verify: str | None = None,
        is_token_verified: bool = False,
    ) -> ReturnEvidenceRequest | None:
        """
        Lấy thông tin yêu cầu bổ sung ảnh cho khách hàng (kèm kiểm tra quá hạn Just-in-Time).
        """
        ret_req = db.scalar(
            select(ReturnRequest).where(ReturnRequest.return_code == return_code)
        )
        if not ret_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy yêu cầu đổi trả.",
            )

        if user:
            if ret_req.user_id and ret_req.user_id != user.id and user.role not in ["ADMIN", "WAREHOUSE_MANAGER", "WAREHOUSE_STAFF"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xem yêu cầu đổi trả của khách hàng khác.",
                )
        elif is_token_verified:
            pass  # Xác thực hợp lệ qua chữ ký số đơn hàng (Guest Order Token)
        elif phone_verify:
            if ret_req.customer_phone != phone_verify.strip():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Số điện thoại xác thực không khớp.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Vui lòng đăng nhập hoặc cung cấp số điện thoại xác thực.",
            )

        req = db.scalar(
            select(ReturnEvidenceRequest)
            .where(ReturnEvidenceRequest.return_request_id == ret_req.id)
            .order_by(ReturnEvidenceRequest.id.desc())
        )
        if not req:
            return None

        # Just-in-Time expiry check
        if req.status == ReturnEvidenceRequestStatus.OPEN.value and to_utc(req.expires_at) <= utcnow():
            cls.expire_evidence_request(db, req)
            db.commit()
            db.refresh(req)

        return req

    @classmethod
    def submit_customer_evidence(
        cls,
        db: Session,
        return_code: str,
        user: User | None,
        images: list[dict[str, Any]],
        customer_note: str | None = None,
        phone_verify: str | None = None,
    ) -> ReturnEvidenceRequest:
        """
        Khách hàng gửi bổ sung đúng số lượng ảnh theo yêu cầu của Quản lý kho.
        """
        ret_req = db.scalar(
            select(ReturnRequest).where(ReturnRequest.return_code == return_code)
        )
        if not ret_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy yêu cầu đổi trả.",
            )

        if user:
            if ret_req.user_id and ret_req.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền tải ảnh lên yêu cầu đổi trả của người khác.",
                )
        elif phone_verify:
            if ret_req.customer_phone != phone_verify.strip():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Số điện thoại xác thực không khớp.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Vui lòng đăng nhập để gửi hình ảnh bằng chứng.",
            )

        req = db.scalar(
            select(ReturnEvidenceRequest)
            .where(
                ReturnEvidenceRequest.return_request_id == ret_req.id,
                ReturnEvidenceRequest.status == ReturnEvidenceRequestStatus.OPEN.value,
            )
            .order_by(ReturnEvidenceRequest.id.desc())
        )
        if not req:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không có yêu cầu bổ sung hình ảnh nào đang mở cho đơn hoàn này.",
            )

        now = utcnow()
        # Kiểm tra quá hạn 3 ngày tại thời điểm gửi (Just-In-Time)
        if to_utc(req.expires_at) <= now:
            cls.expire_evidence_request(db, req)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Yêu cầu bổ sung hình ảnh đã quá hạn 3 ngày. Đơn hoàn đã bị hủy tự động.",
            )

        # Ràng buộc số lượng ảnh phải đúng chính xác
        if len(images) != req.required_image_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Bạn phải gửi chính xác {req.required_image_count} hình ảnh theo yêu cầu của Quản lý kho (hiện có {len(images)} ảnh).",
            )

        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        for img in images:
            file_url = img.get("file_url")
            file_name = img.get("file_name", "evidence.jpg")
            if not file_url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Đường dẫn file_url không được để trống.",
                )
            ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            if ext not in allowed_extensions and not any(file_url.lower().endswith(e) for e in allowed_extensions):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Định dạng ảnh '{ext or file_name}' không hợp lệ. Chỉ chấp nhận .jpg, .jpeg, .png, .webp.",
                )

            evid = ReturnEvidence(
                return_request_id=ret_req.id,
                warehouse_return_case_id=req.warehouse_return_case_id,
                evidence_request_id=req.id,
                return_item_id=req.return_item_id,
                file_url=file_url,
                file_name=file_name,
                mime_type=img.get("mime_type", "image/jpeg"),
                file_size=img.get("file_size", 0),
                file_category="CUSTOMER_SUPPLEMENTARY",
                description=customer_note,
                customer_note=customer_note,
                uploaded_by=user.id if user else None,
                created_at=now,
            )
            db.add(evid)

        req.status = ReturnEvidenceRequestStatus.SUBMITTED.value
        req.submitted_at = now
        req.customer_note = customer_note
        req.updated_at = now

        case = req.warehouse_case
        old_status = case.status if case else ret_req.status
        if case:
            case.status = ReturnStatus.WAITING_MANAGER_REVIEW.value
            case.updated_at = now
            cls._add_case_history(
                db=db,
                case=case,
                from_status=old_status,
                to_status=ReturnStatus.WAITING_MANAGER_REVIEW.value,
                actor=user,
                actor_role="CUSTOMER",
                note=f"Khách hàng đã bổ sung đủ {len(images)} ảnh theo yêu cầu.",
            )
            write_audit(
                db=db,
                action="SUBMIT_CUSTOMER_EVIDENCE",
                entity_type="WAREHOUSE_RETURN_CASE",
                entity_id=case.case_code,
                user=user,
                details=f"Khách hàng nộp {len(images)} ảnh bổ sung cho yêu cầu {req.request_code}",
            )

        ret_req.status = ReturnStatus.WAITING_MANAGER_REVIEW.value
        ret_req.updated_at = now

        db.commit()
        db.refresh(req)
        return req

    @classmethod
    def accept_customer_evidence(
        cls,
        db: Session,
        case_code: str,
        user: User,
        warehouse_id: int | None,
        manager_note: str | None = None,
    ) -> WarehouseReturnCase:
        """
        Quản lý kho duyệt chấp nhận bằng chứng và chuyển đơn hoàn sang WAITING_MANAGER_APPROVAL.
        """
        case = cls.get_case_by_identifier(db, case_code, warehouse_id=None)

        if user.role == "WAREHOUSE_MANAGER":
            if case.warehouse_id != user.warehouse_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền duyệt bằng chứng của ca hoàn kho khác.",
                )
        elif user.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ Quản lý kho mới có quyền duyệt bằng chứng.",
            )

        req = db.scalar(
            select(ReturnEvidenceRequest)
            .where(
                ReturnEvidenceRequest.warehouse_return_case_id == case.id,
                ReturnEvidenceRequest.status == ReturnEvidenceRequestStatus.SUBMITTED.value,
            )
            .order_by(ReturnEvidenceRequest.id.desc())
        )
        if not req:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không có yêu cầu bằng chứng nào đang ở trạng thái 'Đã nộp' (SUBMITTED) để duyệt.",
            )

        now = utcnow()
        req.status = ReturnEvidenceRequestStatus.ACCEPTED.value
        req.reviewed_at = now
        req.updated_at = now

        old_status = case.status
        # Chuyển sang WAITING_MANAGER_APPROVAL (như người dùng đã xác nhận)
        case.status = ReturnStatus.WAITING_MANAGER_APPROVAL.value
        case.updated_at = now
        if manager_note:
            case.manager_note = f"{case.manager_note or ''}\n[Duyệt ảnh]: {manager_note.strip()}".strip()

        if case.return_request:
            case.return_request.status = ReturnStatus.WAITING_MANAGER_APPROVAL.value
            case.return_request.updated_at = now

        cls._add_case_history(
            db=db,
            case=case,
            from_status=old_status,
            to_status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
            actor=user,
            actor_role=user.role,
            note=f"Quản lý kho đã chấp nhận bằng chứng ảnh. Chuyển ca hoàn sang Chờ Quản lý duyệt hoàn.",
        )

        write_audit(
            db=db,
            action="ACCEPT_CUSTOMER_EVIDENCE",
            entity_type="WAREHOUSE_RETURN_CASE",
            entity_id=case.case_code,
            user=user,
            details=f"Quản lý chấp nhận bằng chứng cho yêu cầu {req.request_code}. Chuyển trạng thái sang WAITING_MANAGER_APPROVAL.",
        )

        db.commit()
        db.refresh(case)
        return case

    @classmethod
    def expire_evidence_request(cls, db: Session, req: ReturnEvidenceRequest) -> None:
        """
        Xử lý quá hạn 3 ngày: Hủy yêu cầu hoàn trả sang CANCELLED_EVIDENCE_TIMEOUT,
        khóa upload, nhưng TUYỆT ĐỐI không hủy Order mua hàng gốc của khách.
        """
        now = utcnow()
        req.status = ReturnEvidenceRequestStatus.EXPIRED.value
        req.updated_at = now

        reason_msg = "Khách hàng không bổ sung đủ hình ảnh trong thời hạn 3 ngày"
        case = req.warehouse_case
        ret_req = req.return_request

        if case:
            old_status = case.status
            case.status = ReturnStatus.CANCELLED_EVIDENCE_TIMEOUT.value
            case.rejection_reason = reason_msg
            case.updated_at = now
            cls._add_case_history(
                db=db,
                case=case,
                from_status=old_status,
                to_status=ReturnStatus.CANCELLED_EVIDENCE_TIMEOUT.value,
                actor=None,
                actor_role="SYSTEM",
                note=f"Hệ thống tự động hủy ca hoàn: {reason_msg}",
            )
            write_audit(
                db=db,
                action="EXPIRE_RETURN_EVIDENCE_TIMEOUT",
                entity_type="WAREHOUSE_RETURN_CASE",
                entity_id=case.case_code,
                user=None,
                details=f"Yêu cầu {req.request_code} hết hạn 3 ngày. Ca hoàn {case.case_code} chuyển sang CANCELLED_EVIDENCE_TIMEOUT.",
            )

        if ret_req:
            ret_req.status = ReturnStatus.CANCELLED_EVIDENCE_TIMEOUT.value
            ret_req.rejection_reason = reason_msg
            ret_req.cancelled_at = now
            ret_req.updated_at = now

    @classmethod
    def check_and_expire_evidence_requests(cls, db: Session) -> int:
        """
        Tác vụ định kỳ (Scheduler): Quét các yêu cầu bằng chứng đã quá hạn 3 ngày.
        """
        now = utcnow()
        open_reqs = db.scalars(
            select(ReturnEvidenceRequest).where(
                ReturnEvidenceRequest.status == ReturnEvidenceRequestStatus.OPEN.value,
            )
        ).all()

        count = 0
        for req in open_reqs:
            if req.expires_at and to_utc(req.expires_at) <= now:
                cls.expire_evidence_request(db, req)
                count += 1

        if count > 0:
            db.commit()
            logger.info(f"Đã tự động xử lý quá hạn {count} yêu cầu bổ sung hình ảnh đổi trả.")
        return count
