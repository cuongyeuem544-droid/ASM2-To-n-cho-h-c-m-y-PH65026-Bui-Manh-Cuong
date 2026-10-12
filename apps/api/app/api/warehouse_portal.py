"""Warehouse Portal API.
Provides scoped operations for Warehouse Managers and Staff:
- Warehouse Profile & Live KPIs
- Assigned Orders & Fulfillment State Machine (PICKING -> PACKED -> SHIPPED -> DELIVERED)
- Inventory & FEFO Batch Breakdown
- Inter-warehouse Transfers (Inbound receiving / Consolidation / Failure Auto-Refund)
- Subordinate Staff Management
"""
from datetime import UTC, date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import (
    check_warehouse_permission,
    get_current_user,
    get_user_warehouse_membership,
    require_warehouse_manager,
    require_warehouse_staff_or_manager,
)
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    InventoryBatch,
    Order,
    OrderFulfillment,
    ProductSku,
    StockReservation,
    StockTransfer,
    StockTransferItem,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import FulfillmentStatus, UserRole
from app.models.inventory import UserWarehouseMembership
from app.schemas.auth import UserOut
from app.services.audit import write_audit
from app.services.fulfillment_service import FulfillmentRoutingService

router = APIRouter(prefix="/warehouse-portal", tags=["Cổng Quản Lý Kho (Portal)"])


def utcnow() -> datetime:
    return datetime.now(UTC)


def _resolve_caller_warehouse(user: User, db: Session, warehouse_id_override: Optional[int] = None) -> Warehouse:
    """
    Xác định kho hợp lệ của người dùng:
    - Nếu là ADMIN: có thể truyền warehouse_id_override hoặc mặc định là kho trung tâm đầu tiên.
    - Nếu là WAREHOUSE_MANAGER / WAREHOUSE_STAFF: bắt buộc theo membership đã được gán.
    """
    if user.role == UserRole.ADMIN:
        if warehouse_id_override:
            wh = db.get(Warehouse, warehouse_id_override)
            if wh:
                return wh
        central = db.scalar(select(Warehouse).where(Warehouse.is_central == True).limit(1))
        if central:
            return central
        first_wh = db.scalar(select(Warehouse).order_by(Warehouse.id.asc()).limit(1))
        if first_wh:
            return first_wh
        raise HTTPException(status_code=404, detail="Không tìm thấy kho hàng trong hệ thống")

    membership = get_user_warehouse_membership(user, db)
    if not membership:
        raise HTTPException(status_code=403, detail="Tài khoản chưa được gán vào kho hàng cụ thể")
    wh = db.get(Warehouse, membership.warehouse_id)
    if not wh or not wh.is_active:
        raise HTTPException(status_code=403, detail="Kho hàng được gán hiện không hoạt động")
    return wh


# ==============================================================================
# SCHEMAS
# ==============================================================================

class FulfillmentTransitionPayload(BaseModel):
    fulfillment_status: str = Field(..., description="PICKING | PACKED | SHIPPED | DELIVERED | CANCELLED")
    note: Optional[str] = None


class StaffCreatePayload(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = None
    password: str = Field(min_length=8, max_length=128)


class TransferFailurePayload(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.get("/me")
def get_my_warehouse_info(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Xem thông tin kho đang làm việc và thống kê nhanh (KPIs).
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    today = date.today()
    fefo_cutoff = today + timedelta(days=180)

    # Thống kê
    total_batches = db.scalar(
        select(func.count(WarehouseBatchStock.id)).where(WarehouseBatchStock.warehouse_id == wh.id)
    ) or 0
    total_available_qty = db.scalar(
        select(func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0)).where(WarehouseBatchStock.warehouse_id == wh.id)
    ) or 0

    assigned_orders_count = db.scalar(
        select(func.count(Order.id)).where(Order.assigned_warehouse_id == wh.id)
    ) or 0
    pending_fulfillment_count = db.scalar(
        select(func.count(Order.id)).where(
            Order.assigned_warehouse_id == wh.id,
            Order.fulfillment_status.in_(["ALLOCATED", "WAITING_INTERNAL_TRANSFER", "CONSOLIDATED", "PICKING"]),
        )
    ) or 0

    active_transfers_count = db.scalar(
        select(func.count(StockTransfer.id)).where(
            or_(StockTransfer.from_warehouse_id == wh.id, StockTransfer.to_warehouse_id == wh.id),
            StockTransfer.status.in_(["DRAFT", "IN_TRANSIT"]),
        )
    ) or 0

    return {
        "warehouse": {
            "id": wh.id,
            "code": wh.code,
            "name": wh.name,
            "address": wh.address,
            "district": wh.district,
            "province": wh.province,
            "phone": wh.phone,
            "email": wh.email,
            "lat": wh.lat,
            "lng": wh.lng,
            "service_radius_km": wh.service_radius_km,
            "is_central": wh.is_central,
        },
        "user_role": user.role.value,
        "kpi": {
            "total_batches": total_batches,
            "total_available_quantity": int(total_available_qty),
            "assigned_orders_count": assigned_orders_count,
            "pending_fulfillment_count": pending_fulfillment_count,
            "active_transfers_count": active_transfers_count,
        },
    }


@router.get("/orders")
def get_warehouse_orders(
    fulfillment_status: Optional[str] = None,
    order_status: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Danh sách đơn hàng được gán cho kho hiện tại.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = select(Order).where(Order.assigned_warehouse_id == wh.id)

    if fulfillment_status:
        query = query.where(Order.fulfillment_status == fulfillment_status)
    if order_status:
        query = query.where(Order.order_status == order_status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    orders = db.scalars(
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for o in orders:
        items.append({
            "id": o.id,
            "order_code": o.order_code,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "shipping_address": o.shipping_address,
            "total_amount": float(o.total_amount),
            "payment_method": o.payment_method,
            "payment_status": o.payment_status,
            "order_status": o.order_status,
            "fulfillment_status": o.fulfillment_status,
            "assignment_method": o.assignment_method,
            "assignment_distance_km": o.assignment_distance_km,
            "created_at": o.created_at,
            "items_count": len(o.items),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.patch("/orders/{order_id}/fulfillment")
def update_order_fulfillment_status(
    order_id: int,
    payload: FulfillmentTransitionPayload,
    request: Request,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Cập nhật tiến trình chuẩn bị hàng:
    PICKING -> PACKED -> SHIPPED -> DELIVERED
    """
    user, _ = current_user
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    if not check_warehouse_permission(user, order.assigned_warehouse_id or -1, db):
        raise HTTPException(status_code=403, detail="Đơn hàng này không thuộc phạm vi xử lý của kho bạn")

    new_status = payload.fulfillment_status.upper()
    valid_statuses = {"PICKING", "PACKED", "SHIPPED", "DELIVERED", "CANCELLED", "CONSOLIDATED"}
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Trạng thái '{new_status}' không hợp lệ")

    before_status = order.fulfillment_status
    order.fulfillment_status = new_status

    if new_status == "PICKING":
        order.order_status = "PROCESSING"
    elif new_status == "PACKED":
        order.order_status = "PROCESSING"
    elif new_status == "SHIPPED":
        order.order_status = "SHIPPING"
    elif new_status == "DELIVERED":
        order.order_status = "COMPLETED"
    elif new_status == "CANCELLED":
        order.order_status = "CANCELLED"
        # Release reservations
        FulfillmentRoutingService.release_order_reservations(db, order.id, reason=payload.note or "WAREHOUSE_CANCELLED")

    write_audit(
        db,
        "UPDATE_FULFILLMENT_STATUS",
        "Order",
        order.id,
        user=user,
        request=request,
        before={"fulfillment_status": before_status},
        after={"fulfillment_status": new_status, "note": payload.note},
    )
    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "order_code": order.order_code,
        "fulfillment_status": order.fulfillment_status,
        "order_status": order.order_status,
    }


@router.get("/transfers")
def get_warehouse_transfers(
    direction: Optional[str] = Query(None, description="inbound | outbound | all"),
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Danh sách phiếu điều chuyển hàng nội bộ liên quan đến kho này.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = select(StockTransfer).options(
        selectinload(StockTransfer.from_warehouse),
        selectinload(StockTransfer.to_warehouse),
        selectinload(StockTransfer.items),
    )

    if direction == "inbound":
        query = query.where(StockTransfer.to_warehouse_id == wh.id)
    elif direction == "outbound":
        query = query.where(StockTransfer.from_warehouse_id == wh.id)
    else:
        query = query.where(or_(StockTransfer.from_warehouse_id == wh.id, StockTransfer.to_warehouse_id == wh.id))

    transfers = db.scalars(query.order_by(StockTransfer.created_at.desc())).all()

    return [
        {
            "id": t.id,
            "transfer_code": t.transfer_code,
            "order_id": t.order_id,
            "from_warehouse": {"id": t.from_warehouse.id, "name": t.from_warehouse.name, "code": t.from_warehouse.code},
            "to_warehouse": {"id": t.to_warehouse.id, "name": t.to_warehouse.name, "code": t.to_warehouse.code},
            "status": t.status,
            "note": t.note,
            "shipped_at": t.shipped_at,
            "received_at": t.received_at,
            "created_at": t.created_at,
            "items_count": len(t.items),
        }
        for t in transfers
    ]


@router.post("/transfers/{transfer_id}/receive")
def receive_internal_transfer(
    transfer_id: int,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Tiếp nhận hàng điều chuyển đến kho đích.
    Nếu gom đủ hàng cho đơn, chuyển trạng thái đơn sang CONSOLIDATED.
    """
    user, _ = current_user
    transfer = db.get(StockTransfer, transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu điều chuyển kho")

    if not check_warehouse_permission(user, transfer.to_warehouse_id, db):
        raise HTTPException(status_code=403, detail="Chỉ kho nhận mới có quyền xác nhận tiếp nhận hàng")

    return FulfillmentRoutingService.receive_transfer_and_consolidate(db, transfer_id, user_id=user.id)


@router.post("/transfers/{transfer_id}/fail")
def report_transfer_failure_and_refund(
    transfer_id: int,
    payload: TransferFailurePayload,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Quyết định Q6: Báo cáo sự cố điều chuyển hàng thất bại (hỏng, mất hàng).
    Tự động hủy đơn hàng và hoàn tiền 100% cho khách hàng.
    """
    user, _ = current_user
    transfer = db.get(StockTransfer, transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu điều chuyển kho")

    if user.role != UserRole.ADMIN:
        membership = get_user_warehouse_membership(user, db)
        if not membership or membership.warehouse_id not in (transfer.from_warehouse_id, transfer.to_warehouse_id):
            raise HTTPException(status_code=403, detail="Bạn không thuộc kho liên quan đến đợt chuyển hàng này")

    return FulfillmentRoutingService.cancel_transfer_and_refund_order(
        db=db,
        transfer_id=transfer_id,
        reason=payload.reason,
        user_id=user.id,
    )


@router.get("/staff", response_model=list[UserOut])
def list_warehouse_staff(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Xem danh sách nhân viên cấp dưới trực thuộc kho.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    staff_ids = db.scalars(
        select(UserWarehouseMembership.user_id).where(
            UserWarehouseMembership.warehouse_id == wh.id,
            UserWarehouseMembership.is_active == True,
        )
    ).all()

    return db.scalars(select(User).where(User.id.in_(staff_ids)).order_by(User.created_at.desc())).all()


@router.post("/staff", response_model=UserOut, status_code=201)
def create_warehouse_staff(
    payload: StaffCreatePayload,
    request: Request,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Quyết định Q5: Quản lý kho được phép tạo tài khoản Nhân Viên Kho (WAREHOUSE_STAFF)
    trực thuộc kho của mình.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db)

    email = payload.email.lower().strip()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email này đã tồn tại trong hệ thống")

    new_staff = User(
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.WAREHOUSE_STAFF,
        is_active=True,
    )
    db.add(new_staff)
    db.flush()

    membership = UserWarehouseMembership(
        user_id=new_staff.id,
        warehouse_id=wh.id,
        role=UserRole.WAREHOUSE_STAFF.value,
        is_active=True,
        assigned_by=user.id,
    )
    db.add(membership)
    db.flush()

    write_audit(
        db,
        "CREATE_WAREHOUSE_STAFF",
        "User",
        new_staff.id,
        user=user,
        request=request,
        after={"email": email, "warehouse_id": wh.id, "role": UserRole.WAREHOUSE_STAFF.value},
    )
    db.commit()
    db.refresh(new_staff)
    return new_staff
