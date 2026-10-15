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

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Order, User
from app.models.enums import UserRole
from app.models.inventory import OrderFulfillment, OrderItemBatchAllocation
from app.models.returns import (
    ItemCondition,
    RestockDestination,
    ReturnItem,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
)
from app.services.refund_calculation_service import RefundCalculationService
from app.services.return_service import ReturnService

router = APIRouter(prefix="/admin/returns", tags=["Admin Returns Management"])


# --- Schemas ---

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
    return_item_id: int
    condition: str = Field(default=ItemCondition.GOOD_CONDITION.value)
    restock_destination: str = Field(default=RestockDestination.SELLABLE_STOCK.value)
    accepted_quantity: int = Field(ge=0)
    rejected_quantity: int = Field(default=0, ge=0)
    restock_quantity: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class InspectionPayload(BaseModel):
    general_inspection_note: Optional[str] = None
    items: List[ItemInspectionPayload]


# --- Endpoints ---

@router.get("")
def list_admin_returns(
    status_filter: Optional[str] = Query(None, alias="status"),
    request_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
    admin_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.PHARMACIST)),
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
