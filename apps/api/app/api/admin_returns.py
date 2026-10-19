"""
apps/api/app/api/admin_returns.py

API Quản trị Quy trình Đổi / Trả Hàng (Admin & Staff After-Sales Management) H4CARE:
1. Danh sách yêu cầu lọc theo trạng thái, loại yêu cầu, từ khóa tìm kiếm (GET /api/v1/admin/returns).
2. Chi tiết yêu cầu đổi/trả toàn diện (GET /api/v1/admin/returns/{return_code}).
3. Tiếp nhận xử lý / Yêu cầu bổ sung thông tin (POST /api/v1/admin/returns/{return_code}/review).
4. Phê duyệt & Hướng dẫn gửi hàng (POST /api/v1/admin/returns/{return_code}/approve).
5. Từ chối yêu cầu kèm lý do bắt buộc (POST /api/v1/admin/returns/{return_code}/reject).
6. Kho dược xác nhận nhận hàng từ bưu tá (POST /api/v1/admin/returns/{return_code}/receive).
7. Dược sĩ kiểm định chất lượng & phân luồng tồn kho (POST /api/v1/admin/returns/{return_code}/inspect).
8. Đóng hồ sơ đổi trả (POST /api/v1/admin/returns/{return_code}/close).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Order, User
from app.models.inventory import UserWarehouseMembership, Warehouse
from app.models.enums import UserRole
from app.models.inventory import OrderFulfillment, OrderItemBatchAllocation
from app.models.returns import (
    ItemCondition,
    Refund,
    RefundStatus,
    RestockDestination,
    ReturnInspection,
    ReturnItem,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
    WarehouseReturnCase,
)
from app.services.refund_calculation_service import RefundCalculationService
from app.services.return_service import ReturnService
from app.services.warehouse_return_service import WarehouseReturnService

router = APIRouter(prefix="/admin/returns", tags=["Admin Returns Management"])


# --- Schemas ---

class AdminOverridePayload(BaseModel):
    new_status: str
    override_reason: str = Field(..., min_length=5, description="Lý do can thiệp khẩn cấp bắt buộc")
    notes: Optional[str] = None


class AdminReassignPayload(BaseModel):
    new_warehouse_id: int
    case_code: Optional[str] = None
    reason: str = Field(..., min_length=5, description="Lý do điều chuyển kho bắt buộc")

class ReviewPayload(BaseModel):
    status: str = Field(..., description="REVIEWING hoặc NEEDS_CUSTOMER_INFO")
    admin_note: Optional[str] = None
    customer_visible_note: Optional[str] = None


class ApprovePayload(BaseModel):
    warehouse_address: Optional[str] = None
    admin_note: Optional[str] = None
    customer_visible_note: Optional[str] = None


class RejectPayload(BaseModel):
    rejection_reason: str = Field(..., min_length=5, description="Lý do từ chối bắt buộc")
    admin_note: Optional[str] = None


class ReceivePayload(BaseModel):
    note: Optional[str] = None


class ItemInspectionPayload(BaseModel):
    return_item_id: int = Field(..., description="ID sản phẩm đổi/trả bắt buộc")
    condition: str = Field(..., min_length=1, description="Tình trạng thực tế của sản phẩm bắt buộc (không mặc định)")
    package_condition: str = Field(..., min_length=1, description="Trạng thái bao bì bắt buộc (không mặc định)")
    seal_intact: bool = Field(..., description="Tem niêm phong nguyên vẹn bắt buộc (True/False)")
    batch_matched: bool = Field(..., description="Khớp số lô đã xuất bắt buộc (True/False)")
    expiry_matched: bool = Field(..., description="Khớp hạn sử dụng bắt buộc (True/False)")
    storage_condition_ok: bool = Field(..., description="Điều kiện bảo quản đạt bắt buộc (True/False)")
    accepted_quantity: int = Field(..., ge=0, description="Số lượng chấp nhận bắt buộc")
    rejected_quantity: int = Field(..., ge=0, description="Số lượng loại bỏ bắt buộc")
    restock_destination: str = Field(..., min_length=1, description="Phân luồng kho bắt buộc (không mặc định)")
    restock_quantity: Optional[int] = Field(default=None, ge=0, description="Số lượng nhập lại kho bán")
    rejection_reason: Optional[str] = Field(default=None, description="Lý do từ chối nếu có rejected_quantity > 0")
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_inspection(self):
        # 1. Tổng số lượng kiểm định phải > 0
        if self.accepted_quantity + self.rejected_quantity <= 0:
            raise ValueError(f"Tổng số lượng chấp nhận ({self.accepted_quantity}) và từ chối ({self.rejected_quantity}) phải lớn hơn 0.")

        # 2. Bắt buộc có lý do từ chối nếu có rejected_quantity > 0
        if self.rejected_quantity > 0 and (not self.rejection_reason or not str(self.rejection_reason).strip()):
            raise ValueError(f"Sản phẩm có {self.rejected_quantity} đơn vị bị loại bỏ, bắt buộc phải nêu rõ lý do từ chối (rejection_reason).")

        # 3. Chặn phân loại RESTOCK hoặc đưa về SELLABLE_STOCK nếu bất kỳ điều kiện an toàn nào là False
        dest_upper = self.restock_destination.upper()
        if dest_upper in [RestockDestination.SELLABLE_STOCK.value, "RESTOCK"]:
            # Bắt buộc phải nhập restock_quantity rõ ràng
            if self.restock_quantity is None:
                raise ValueError("Bắt buộc phải chỉ định 'restock_quantity' khi phân luồng vào kho bán (SELLABLE_STOCK/RESTOCK). Tuyệt đối không tự động mặc định.")
            if self.restock_quantity <= 0:
                raise ValueError("Số lượng nhập lại kho bán (restock_quantity) phải lớn hơn 0 khi phân luồng vào kho bán.")
            if self.restock_quantity > self.accepted_quantity:
                raise ValueError(f"Số lượng nhập kho bán ({self.restock_quantity}) không được lớn hơn số lượng chấp nhận ({self.accepted_quantity}).")

            failed_criteria = []
            if not self.seal_intact:
                failed_criteria.append("tem niêm phong không nguyên vẹn (seal_intact=False)")
            if not self.batch_matched:
                failed_criteria.append("số lô không khớp đã xuất (batch_matched=False)")
            if not self.expiry_matched:
                failed_criteria.append("hạn sử dụng không khớp hoặc hết hạn (expiry_matched=False)")
            if not self.storage_condition_ok:
                failed_criteria.append("điều kiện bảo quản không đạt chuẩn GSP (storage_condition_ok=False)")

            if failed_criteria:
                raise ValueError(
                    f"Sản phẩm không đạt chuẩn an toàn dược phẩm ({', '.join(failed_criteria)}). "
                    "Tuyệt đối không được phân loại RESTOCK hoặc đưa về SELLABLE_STOCK. Bắt buộc chuyển sang QUARANTINE hoặc DISPOSAL."
                )

            pkg_lower = self.package_condition.lower()
            if any(bad in pkg_lower for bad in ["rách", "móp", "vỡ", "hỏng", "damaged", "broken", "torn"]):
                raise ValueError(f"Bao bì '{self.package_condition}' bị hư hại, không đạt chuẩn nhập lại kho bán.")

            gsp_compliant = [ItemCondition.GOOD_CONDITION.value, ItemCondition.SEALED.value]
            if self.condition not in gsp_compliant:
                raise ValueError(f"Sản phẩm có tình trạng '{self.condition}', không đạt tiêu chuẩn an toàn GSP để nhập lại kho bán (SELLABLE_STOCK).")
        return self


class InspectionPayload(BaseModel):
    general_inspection_note: Optional[str] = None
    items: List[ItemInspectionPayload]


# --- Endpoints ---

@router.get("/overview")
def get_admin_returns_overview(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Dashboard đơn hoàn toàn hệ thống:
    - Tổng yêu cầu hoàn
    - Chờ kho tiếp nhận, Đang vận chuyển, Đang kiểm tra, Chờ quản lý duyệt, Đã duyệt, Từ chối,
      Hoàn tiền thành công/thất bại, Quá hạn SLA, Tổng tiền hoàn.
    """
    now = datetime.now(UTC)
    all_cases = db.scalars(select(WarehouseReturnCase)).all()
    all_requests = db.scalars(select(ReturnRequest)).all()

    total_returns = len(all_requests)
    waiting_receive = 0
    in_transit = 0
    inspecting = 0
    waiting_approval = 0
    approved = 0
    rejected = 0
    refund_pending = 0
    refund_processing = 0
    refund_succeeded = 0
    refund_failed = 0
    overdue = 0

    for c in all_cases:
        st = c.status
        if st in [ReturnStatus.REQUESTED.value, ReturnStatus.ASSIGNED_TO_WAREHOUSE.value, ReturnStatus.WAITING_CUSTOMER_SHIPMENT.value]:
            waiting_receive += 1
        elif st in [ReturnStatus.IN_TRANSIT.value, ReturnStatus.RETURN_IN_TRANSIT.value]:
            in_transit += 1
        elif st in [ReturnStatus.RECEIVED.value, ReturnStatus.INSPECTING.value]:
            inspecting += 1
        elif st == ReturnStatus.WAITING_MANAGER_APPROVAL.value:
            waiting_approval += 1
        elif st == ReturnStatus.APPROVED.value:
            approved += 1
        elif st == ReturnStatus.REJECTED.value:
            rejected += 1
        elif st == ReturnStatus.REFUND_PENDING.value:
            refund_pending += 1
        elif st == ReturnStatus.REFUND_PROCESSING.value:
            refund_processing += 1
        elif st in [ReturnStatus.REFUNDED.value, ReturnStatus.RESTOCKED.value, ReturnStatus.QUARANTINED.value, ReturnStatus.DISPOSED.value, ReturnStatus.CLOSED.value]:
            refund_succeeded += 1
        elif st == ReturnStatus.REFUND_FAILED.value:
            refund_failed += 1

        if st not in [ReturnStatus.CLOSED.value, ReturnStatus.REJECTED.value] and c.created_at:
            c_tz = c.created_at.replace(tzinfo=UTC if c.created_at.tzinfo is None else c.created_at.tzinfo)
            if (now - c_tz).total_seconds() > 172800:
                overdue += 1

    total_refunded_amount = db.scalar(
        select(func.sum(Refund.amount)).where(Refund.status == RefundStatus.SUCCEEDED.value)
    ) or Decimal("0.0")

    total_pending_refund_amount = db.scalar(
        select(func.sum(Refund.amount)).where(
            Refund.status.in_([RefundStatus.PENDING.value, RefundStatus.APPROVED.value, RefundStatus.PROCESSING.value])
        )
    ) or Decimal("0.0")

    return {
        "total_returns": total_returns,
        "waiting_warehouse_receive": waiting_receive,
        "in_transit": in_transit,
        "inspecting": inspecting,
        "waiting_manager_approval": waiting_approval,
        "approved": approved,
        "rejected": rejected,
        "refund_pending": refund_pending,
        "refund_processing": refund_processing,
        "refund_succeeded": refund_succeeded,
        "refund_failed": refund_failed,
        "overdue": overdue,
        "total_refunded_amount": float(total_refunded_amount),
        "total_pending_refund_amount": float(total_pending_refund_amount),
    }


@router.get("/by-warehouse")
def get_admin_returns_by_warehouse(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Bảng theo dõi ca hoàn theo từng kho:
    - Tên kho, Quản lý kho, Tổng đơn hoàn, Đang kiểm tra, Chờ duyệt, Đã duyệt, Đã từ chối,
      Hoàn thành, Hoàn thất bại, Số tiền đã hoàn, Thời gian xử lý TB, Đơn quá SLA.
    """
    now = datetime.now(UTC)
    warehouses = db.scalars(select(Warehouse).order_by(Warehouse.id.asc())).all()

    result = []
    for wh in warehouses:
        cases = db.scalars(
            select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh.id)
        ).all()

        total_cases = len(cases)
        inspecting = 0
        waiting_approval = 0
        approved = 0
        rejected = 0
        completed = 0
        failed = 0
        overdue_sla = 0
        total_time_seconds = 0
        completed_count = 0

        for c in cases:
            st = c.status
            if st in [ReturnStatus.RECEIVED.value, ReturnStatus.INSPECTING.value]:
                inspecting += 1
            elif st == ReturnStatus.WAITING_MANAGER_APPROVAL.value:
                waiting_approval += 1
            elif st in [ReturnStatus.APPROVED.value, ReturnStatus.REFUND_PENDING.value, ReturnStatus.REFUND_PROCESSING.value]:
                approved += 1
            elif st == ReturnStatus.REJECTED.value:
                rejected += 1
            elif st in [ReturnStatus.REFUNDED.value, ReturnStatus.RESTOCKED.value, ReturnStatus.QUARANTINED.value, ReturnStatus.DISPOSED.value, ReturnStatus.CLOSED.value]:
                completed += 1
                if c.created_at and (c.closed_at or c.refund_processed_at):
                    fin = c.closed_at or c.refund_processed_at
                    c_tz = c.created_at.replace(tzinfo=UTC if c.created_at.tzinfo is None else c.created_at.tzinfo)
                    f_tz = fin.replace(tzinfo=UTC if fin.tzinfo is None else fin.tzinfo)
                    total_time_seconds += (f_tz - c_tz).total_seconds()
                    completed_count += 1
            elif st == ReturnStatus.REFUND_FAILED.value:
                failed += 1

            if st not in [ReturnStatus.CLOSED.value, ReturnStatus.REJECTED.value] and c.created_at:
                c_tz = c.created_at.replace(tzinfo=UTC if c.created_at.tzinfo is None else c.created_at.tzinfo)
                if (now - c_tz).total_seconds() > 172800:
                    overdue_sla += 1

        avg_hours = round(total_time_seconds / (completed_count * 3600), 1) if completed_count > 0 else 0.0

        refunded_amount = db.scalar(
            select(func.sum(Refund.amount)).where(
                Refund.warehouse_id == wh.id,
                Refund.status == RefundStatus.SUCCEEDED.value,
            )
        ) or Decimal("0.0")

        result.append({
            "warehouse_id": wh.id,
            "warehouse_code": wh.code,
            "warehouse_name": wh.name,
            "province": wh.province or "N/A",
            "total_cases": total_cases,
            "inspecting": inspecting,
            "waiting_approval": waiting_approval,
            "approved": approved,
            "rejected": rejected,
            "completed": completed,
            "failed": failed,
            "refunded_amount": float(refunded_amount),
            "avg_resolution_hours": avg_hours,
            "overdue_sla": overdue_sla,
        })

    return result


@router.get("")
def list_admin_returns(
    status_filter: Optional[str] = Query(None, alias="status"),
    request_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Danh sách yêu cầu đổi/trả cho nhân viên & ban quản trị.
    """
    query = select(ReturnRequest).join(Order, ReturnRequest.order_id == Order.id)

    if warehouse_id is not None:
        query = (
            query.outerjoin(ReturnItem, ReturnItem.return_request_id == ReturnRequest.id)
            .outerjoin(OrderItemBatchAllocation, OrderItemBatchAllocation.order_item_id == ReturnItem.order_item_id)
            .outerjoin(OrderFulfillment, OrderFulfillment.order_id == Order.id)
            .where(
                or_(
                    OrderItemBatchAllocation.warehouse_id == warehouse_id,
                    OrderFulfillment.warehouse_id == warehouse_id,
                )
            )
            .distinct()
        )

    if status_filter:
        query = query.where(ReturnRequest.status == status_filter)

    if request_type:
        query = query.where(ReturnRequest.request_type == request_type)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ReturnRequest.return_code.ilike(search_term),
                Order.order_code.ilike(search_term),
                ReturnRequest.customer_name.ilike(search_term),
                ReturnRequest.customer_phone.ilike(search_term),
                ReturnRequest.tracking_code.ilike(search_term),
            )
        )

    # Đếm tổng
    total_count = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    # Lấy phân trang
    offset = (page - 1) * page_size
    records = db.scalars(query.order_by(ReturnRequest.id.desc()).offset(offset).limit(page_size)).all()

    items_out = []
    for r in records:
        items_out.append({
            "id": r.id,
            "return_code": r.return_code,
            "order_code": r.order.order_code if r.order else "",
            "request_type": r.request_type,
            "status": r.status,
            "reason_code": r.reason_code,
            "reason_text": r.reason_text,
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
            "carrier_name": r.carrier_name,
            "tracking_code": r.tracking_code,
            "items_count": len(r.items),
            "requested_at": r.requested_at.isoformat() if r.requested_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "inspected_at": r.inspected_at.isoformat() if r.inspected_at else None,
        })

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "items": items_out,
        "returns": items_out,
    }


@router.get("/{return_code}")
def get_admin_return_detail(
    return_code: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Chi tiết đầy đủ của một yêu cầu đổi/trả cho ban quản trị.
    """
    ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
    if not ret:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

    # Danh sách sản phẩm đổi trả
    items_data = []
    for it in ret.items:
        items_data.append({
            "id": it.id,
            "order_item_id": it.order_item_id,
            "product_id": it.product_id,
            "product_name": it.product_name,
            "original_quantity": it.original_quantity,
            "requested_quantity": it.requested_quantity,
            "accepted_quantity": it.accepted_quantity,
            "rejected_quantity": it.rejected_quantity,
            "restock_quantity": it.restock_quantity,
            "unit_price": float(it.unit_price_at_purchase or Decimal("0.0")),
            "subtotal": float(it.net_paid_amount or ((it.unit_price_at_purchase or Decimal("0.0")) * it.requested_quantity)),
            "inspected_condition": it.inspected_condition,
            "restock_destination": it.restock_destination,
            "inspection_notes": it.inspection_notes,
            "customer_reason": it.customer_reason,
            "condition_reported": it.condition_reported,
        })

    # Dòng thời gian lịch sử
    timeline = []
    for h in sorted(ret.history, key=lambda x: x.created_at or datetime.min):
        timeline.append({
            "id": h.id,
            "from_status": h.from_status,
            "to_status": h.to_status,
            "actor_name": h.actor_name,
            "actor_role": h.actor_role,
            "note": h.note,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        })

    # Bằng chứng
    evidences = [
        {
            "id": e.id,
            "file_url": e.file_url,
            "file_name": e.file_name,
            "file_type": e.file_type,
            "file_size": e.file_size,
            "description": e.description,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in ret.evidences
    ]

    # Phiếu hoàn tiền liên kết
    refunds_data = [
        {
            "id": rf.id,
            "refund_code": rf.refund_code,
            "refund_amount": float(rf.refund_amount),
            "refund_method": rf.refund_method,
            "status": rf.status,
            "reconciliation_status": rf.reconciliation_status,
            "bank_transfer_ref": rf.bank_transfer_ref,
            "gateway_trans_id": rf.gateway_trans_id,
            "beneficiary_bank": rf.beneficiary_bank,
            "beneficiary_account_number": rf.beneficiary_account_number,
            "beneficiary_account_name": rf.beneficiary_account_name,
            "proof_document_url": rf.proof_document_url,
            "notes": rf.notes,
            "processed_at": rf.processed_at.isoformat() if rf.processed_at else None,
        }
        for rf in ret.refunds
    ]

    # Đơn đổi hàng liên kết
    exchanges_data = [
        {
            "id": ex.id,
            "exchange_code": ex.exchange_code,
            "returned_items_value": float(ex.returned_items_value),
            "replacement_items_value": float(ex.replacement_items_value),
            "price_difference": float(ex.price_difference),
            "status": ex.status,
            "carrier_name": ex.carrier_name,
            "tracking_code": ex.tracking_code,
            "shipping_address": ex.shipping_address,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
        }
        for ex in ret.exchange_orders
    ]

    # Tính toán số tiền hoàn dự kiến
    refund_calc = RefundCalculationService.calculate_return_refund(
        db=db,
        order=ret.order,
        return_items=ret.items,
        reason_code=ret.reason_code,
    )

    # Ca hoàn chi nhánh kho
    cases_data = [
        {
            "id": c.id,
            "case_code": c.case_code,
            "warehouse_id": c.warehouse_id,
            "warehouse_code": c.warehouse.code if c.warehouse else "",
            "warehouse_name": c.warehouse.name if c.warehouse else "",
            "status": c.status,
            "carrier_name": c.carrier_name,
            "tracking_code": c.tracking_code,
            "assigned_staff": c.assigned_staff.full_name if c.assigned_staff else None,
            "manager_note": c.manager_note,
            "rejection_reason": c.rejection_reason,
            "disposition": c.disposition,
            "disposition_note": c.disposition_note,
            "inspected_at": c.inspected_at.isoformat() if c.inspected_at else None,
            "approved_at": c.approved_at.isoformat() if c.approved_at else None,
            "refund_processed_at": c.refund_processed_at.isoformat() if c.refund_processed_at else None,
            "items": [
                {
                    "id": it.id,
                    "product_id": it.product_id,
                    "product_name": it.product_name,
                    "requested_quantity": it.requested_quantity,
                    "accepted_quantity": it.accepted_quantity,
                    "rejected_quantity": it.rejected_quantity,
                    "approved_refund_amount": float(it.approved_refund_amount),
                    "condition": it.condition,
                }
                for it in c.items
            ],
            "inspections": [
                {
                    "id": insp.id,
                    "return_item_id": insp.return_item_id,
                    "received_quantity": insp.received_quantity,
                    "accepted_quantity": insp.accepted_quantity,
                    "rejected_quantity": insp.rejected_quantity,
                    "package_condition": insp.package_condition,
                    "seal_intact": insp.seal_intact,
                    "batch_matched": insp.batch_matched,
                    "expiry_matched": insp.expiry_matched,
                    "suggested_action": insp.suggested_action,
                    "inspector_name": insp.inspector.full_name if insp.inspector else None,
                    "inspection_note": insp.inspection_note,
                    "inspected_at": insp.inspected_at.isoformat() if insp.inspected_at else None,
                }
                for insp in c.inspections
            ],
        }
        for c in ret.warehouse_cases
    ]

    return {
        "id": ret.id,
        "return_code": ret.return_code,
        "order_code": ret.order.order_code if ret.order else "",
        "order_total": float(ret.order.total_amount) if ret.order else 0,
        "request_type": ret.request_type,
        "status": ret.status,
        "reason_code": ret.reason_code,
        "reason_text": ret.reason_text,
        "customer_name": ret.customer_name,
        "customer_phone": ret.customer_phone,
        "customer_email": ret.customer_email,
        "customer_note": ret.customer_note,
        "return_method": ret.return_method,
        "carrier_name": ret.carrier_name,
        "tracking_code": ret.tracking_code,
        "return_address_snapshot": ret.return_address_snapshot,
        "admin_note": ret.admin_note,
        "customer_visible_note": ret.customer_visible_note,
        "rejection_reason": ret.rejection_reason,
        "requested_at": ret.requested_at.isoformat() if ret.requested_at else None,
        "reviewed_at": ret.reviewed_at.isoformat() if ret.reviewed_at else None,
        "approved_at": ret.approved_at.isoformat() if ret.approved_at else None,
        "received_at": ret.received_at.isoformat() if ret.received_at else None,
        "inspected_at": ret.inspected_at.isoformat() if ret.inspected_at else None,
        "items": items_data,
        "warehouse_cases": cases_data,
        "timeline": timeline,
        "evidences": evidences,
        "refunds": refunds_data,
        "exchanges": exchanges_data,
        "refund_calculation": {
            "items_refund_amount": float(refund_calc["items_refund_amount"]),
            "shipping_fee_refund": float(refund_calc["shipping_fee_refund"]),
            "final_refund_amount": float(refund_calc["final_refund_amount"]),
            "max_possible_refund": float(refund_calc["max_possible_refund"]),
            "already_refunded": float(refund_calc["already_refunded"]),
        },
    }


@router.post("/{return_code}/review")
def review_return(
    return_code: str,
    payload: ReviewPayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Tiếp nhận xem xét hoặc yêu cầu khách bổ sung thông tin.
    """
    ret = ReturnService.review_return_request(
        db=db,
        return_code=return_code,
        admin_user=admin_user,
        status=payload.status,
        admin_note=payload.admin_note,
        customer_visible_note=payload.customer_visible_note,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": f"Đã chuyển trạng thái yêu cầu sang {ret.status}.",
    }


@router.post("/{return_code}/approve")
def approve_return(
    return_code: str,
    payload: ApprovePayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Phê duyệt yêu cầu đổi/trả và hướng dẫn khách gửi hàng về kho.
    """
    ret = ReturnService.approve_return_request(
        db=db,
        return_code=return_code,
        admin_user=admin_user,
        warehouse_address=payload.warehouse_address,
        admin_note=payload.admin_note,
        customer_visible_note=payload.customer_visible_note,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": "Đã phê duyệt yêu cầu đổi/trả hàng. Hệ thống đang chờ khách gửi hàng.",
    }


@router.post("/{return_code}/reject")
def reject_return(
    return_code: str,
    payload: RejectPayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Từ chối yêu cầu đổi/trả hàng kèm lý do giải thích.
    """
    ret = ReturnService.reject_return_request(
        db=db,
        return_code=return_code,
        admin_user=admin_user,
        rejection_reason=payload.rejection_reason,
        admin_note=payload.admin_note,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": f"Đã từ chối yêu cầu: {payload.rejection_reason}",
    }


@router.post("/{return_code}/receive")
def confirm_return_receipt(
    return_code: str,
    payload: ReceivePayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Kho xác nhận đã nhận kiện hàng hoàn trả từ bưu tá.
    """
    ret = ReturnService.confirm_receipt(
        db=db,
        return_code=return_code,
        warehouse_user=admin_user,
        note=payload.note,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": "Kho đã nhận kiện hàng hoàn, sẵn sàng cho công tác kiểm định dược phẩm.",
    }


@router.post("/{return_code}/inspect")
def inspect_return(
    return_code: str,
    payload: InspectionPayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Dược sĩ kiểm định chất lượng hàng hoàn và phân luồng tồn kho (Nhập kho bán / Biệt trữ / Hủy).
    """
    ret = ReturnService.inspect_return_items(
        db=db,
        return_code=return_code,
        inspector_user=admin_user,
        inspection_payload=[it.model_dump() for it in payload.items],
        general_inspection_note=payload.general_inspection_note,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": "Hoàn tất kiểm định chất lượng dược phẩm hoàn trả và cập nhật tồn kho.",
    }


@router.post("/{return_code}/close")
def close_return(
    return_code: str,
    admin_note: Optional[str] = None,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Đóng hồ sơ đổi trả sau khi hoàn tiền hoặc hoàn tất đổi hàng.
    """
    ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
    if not ret:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

    old_status = ret.status
    ret.status = ReturnStatus.CLOSED.value
    if admin_note:
        ret.admin_note = (ret.admin_note or "") + f"\n[Đóng hồ sơ] {admin_note}"

    db.commit()
    db.refresh(ret)

    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": "Đã đóng hồ sơ đổi trả hàng.",
    }


@router.get("/notifications/stats")
def get_return_notifications_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Thống kê số lượng đơn đổi/trả chờ duyệt và danh sách các đơn mới gửi cần xử lý ngay cho Admin.
    """
    pending_count = db.scalar(
        select(func.count(ReturnRequest.id)).where(ReturnRequest.status == ReturnStatus.REQUESTED.value)
    ) or 0

    reviewing_count = db.scalar(
        select(func.count(ReturnRequest.id)).where(ReturnRequest.status == ReturnStatus.REVIEWING.value)
    ) or 0

    inspecting_count = db.scalar(
        select(func.count(ReturnRequest.id)).where(
            ReturnRequest.status.in_([
                ReturnStatus.RECEIVED.value,
                ReturnStatus.INSPECTING.value,
            ])
        )
    ) or 0

    recent_pending = db.scalars(
        select(ReturnRequest)
        .where(ReturnRequest.status == ReturnStatus.REQUESTED.value)
        .order_by(ReturnRequest.id.desc())
        .limit(6)
    ).all()

    return {
        "pending_count": pending_count,
        "reviewing_count": reviewing_count,
        "inspecting_count": inspecting_count,
        "total_action_needed": pending_count + inspecting_count,
        "recent_pending": [
            {
                "id": r.id,
                "return_code": r.return_code,
                "customer_name": r.customer_name,
                "customer_phone": r.customer_phone,
                "reason_text": r.reason_text,
                "request_type": r.request_type,
                "requested_at": r.requested_at.isoformat() if r.requested_at else None,
            }
            for r in recent_pending
        ],
    }


@router.post("/{return_code}/override")
def admin_override_return(
    return_code: str,
    payload: AdminOverridePayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin can thiệp khẩn cấp (ADMIN_OVERRIDE). Bắt buộc nhập lý do, ghi Audit Log đầy đủ.
    """
    ret = WarehouseReturnService.admin_override(
        db=db,
        return_code=return_code,
        admin_user=admin_user,
        new_status=payload.new_status,
        reason=payload.override_reason,
        notes=payload.notes,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": f"Admin Override thành công. Trạng thái mới: {ret.status}.",
    }


@router.post("/{return_code}/reassign")
def admin_reassign_return(
    return_code: str,
    payload: AdminReassignPayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin điều phối ca hoàn sang chi nhánh kho khác khi có sự cố.
    """
    case_ident = payload.case_code or return_code
    wcase = WarehouseReturnService.admin_reassign_warehouse(
        db=db,
        case_code=case_ident,
        new_warehouse_id=payload.new_warehouse_id,
        admin_user=admin_user,
        reason=payload.reason,
    )
    return {
        "success": True,
        "case_code": wcase.case_code,
        "warehouse_id": wcase.warehouse_id,
        "message": f"Đã điều chuyển ca hoàn {wcase.case_code} sang kho ID {wcase.warehouse_id}.",
    }
