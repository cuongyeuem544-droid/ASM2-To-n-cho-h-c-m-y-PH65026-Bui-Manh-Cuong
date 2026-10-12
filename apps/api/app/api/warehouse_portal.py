"""Warehouse Portal API.
Comprehensive portal backend for Warehouse Managers and Warehouse Staff with strict multi-warehouse RBAC:
- Strict Data Isolation & Anti-IDOR Defense: warehouse_id is validated against the authenticated session token.
- Warehouse Manager Scope: Overview KPIs, Orders Fulfillment, Batch Management, Stock Receipts, Inventory Checks & Adjustments with mandatory reasons, Transfers, Staff Management, Warehouse Audits, and Customer Reviews.
- Warehouse Staff Scope: Today's Tasks, Fast Picking & Packing Workflow, Read-only Stock Lookup, Report Missing/Defect Issues, and Personal History.
"""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, or_, select
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
    AuditLog,
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderItemBatchAllocation,
    ProductReview,
    ProductSku,
    StockAdjustment,
    StockAdjustmentItem,
    StockMovement,
    StockReceipt,
    StockReceiptItem,
    StockReservation,
    StockTransfer,
    StockTransferItem,
    Supplier,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import FulfillmentStatus, UserRole
from app.models.inventory import UserWarehouseMembership
from app.schemas.auth import UserOut
from app.services.audit import write_audit
from app.services.fulfillment_service import FulfillmentRoutingService

router = APIRouter(prefix="/warehouse-portal", tags=["Cổng Quản Lý Kho & Nhân Viên Kho"])


def utcnow() -> datetime:
    return datetime.now(UTC)


def _resolve_caller_warehouse(user: User, db: Session, warehouse_id_override: Optional[int] = None) -> Warehouse:
    """
    Xác định kho hợp lệ của người dùng:
    - Nếu là ADMIN: có thể truyền warehouse_id_override để xem theo kho hoặc mặc định kho trung tâm.
    - Nếu là WAREHOUSE_MANAGER / WAREHOUSE_STAFF: bắt buộc theo membership đã được gán.
    - PHÒNG THỦ IDOR: nếu non-admin cố tình truyền warehouse_id_override khác kho của mình -> 403 Forbidden ngay lập tức.
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

    # Kiểm tra phòng thủ IDOR
    if warehouse_id_override is not None and int(warehouse_id_override) != int(membership.warehouse_id):
        raise HTTPException(
            status_code=403,
            detail="Truy cập bị từ chối: Vi phạm phân quyền kho (IDOR violation) - Bạn không thể truy cập dữ liệu của kho khác",
        )

    wh = db.get(Warehouse, membership.warehouse_id)
    if not wh or not wh.is_active:
        raise HTTPException(status_code=403, detail="Kho hàng được gán hiện không hoạt động")
    return wh


# ==============================================================================
# PYDANTIC SCHEMAS
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


class TransferCreatePayload(BaseModel):
    to_warehouse_id: int
    note: Optional[str] = None
    items: List[dict] = Field(..., description="[{'sku_id': int, 'batch_id': int, 'quantity': int}]")


class ReceiptItemPayload(BaseModel):
    sku_id: int
    batch_number: str
    manufacture_date: Optional[str] = None
    expiry_date: str
    quantity: int = Field(gt=0)
    purchase_unit_price: float = Field(ge=0)


class ReceiptCreatePayload(BaseModel):
    supplier_id: int
    received_date: Optional[str] = None
    note: Optional[str] = None
    items: List[ReceiptItemPayload]


class AdjustmentItemPayload(BaseModel):
    batch_id: int
    actual_quantity: int = Field(ge=0)
    reason: Optional[str] = None


class StockAdjustmentPayload(BaseModel):
    reason: str = Field(..., min_length=5, max_length=255, description="Lý do điều chỉnh (bắt buộc)")
    items: List[AdjustmentItemPayload]


class OrderIssuePayload(BaseModel):
    issue_type: str = Field(..., description="OUT_OF_STOCK | DAMAGED_PRODUCT | EXPIRED_BATCH | OTHER")
    reason: str = Field(..., min_length=5, max_length=500)


# ==============================================================================
# TỔNG QUAN KHO & KPIS (Dành cho Quản Lý Kho & Nhân Viên)
# ==============================================================================

@router.get("/me")
def get_my_warehouse_info(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Xem thông tin kho đang làm việc và thống kê vận hành (KPIs):
    - Đơn hàng theo trạng thái
    - Tổng lô, tổng tồn kho khả dụng
    - Lô thuốc cận hạn (< 180 ngày)
    - Số lệnh điều chuyển đang xử lý
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    today = date.today()
    fefo_cutoff = today + timedelta(days=180)

    # Thống kê tồn kho
    total_batches = db.scalar(
        select(func.count(WarehouseBatchStock.id)).where(WarehouseBatchStock.warehouse_id == wh.id)
    ) or 0
    total_available_qty = db.scalar(
        select(func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0)).where(
            WarehouseBatchStock.warehouse_id == wh.id
        )
    ) or 0
    total_on_hand_qty = db.scalar(
        select(func.coalesce(func.sum(WarehouseBatchStock.quantity_on_hand), 0)).where(
            WarehouseBatchStock.warehouse_id == wh.id
        )
    ) or 0

    # Lô cận hạn (< 180 ngày)
    near_expiry_batches = db.scalar(
        select(func.count(WarehouseBatchStock.id))
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(
            WarehouseBatchStock.warehouse_id == wh.id,
            WarehouseBatchStock.quantity_on_hand > 0,
            InventoryBatch.expiry_date <= fefo_cutoff,
        )
    ) or 0

    # Thống kê đơn hàng theo order_status
    order_status_counts = {}
    for st in ["PENDING", "PROCESSING", "CONFIRMED", "SHIPPING", "COMPLETED", "CANCELLED"]:
        cnt = db.scalar(
            select(func.count(Order.id)).where(Order.assigned_warehouse_id == wh.id, Order.order_status == st)
        ) or 0
        order_status_counts[st] = cnt

    # Thống kê đơn hàng theo fulfillment_status
    fulfillment_counts = {}
    for fs in ["ALLOCATED", "WAITING_INTERNAL_TRANSFER", "CONSOLIDATED", "PICKING", "PACKED", "SHIPPED", "DELIVERED"]:
        cnt = db.scalar(
            select(func.count(Order.id)).where(Order.assigned_warehouse_id == wh.id, Order.fulfillment_status == fs)
        ) or 0
        fulfillment_counts[fs] = cnt

    # Đơn cần soạn & đóng gói ngay hôm nay
    pending_fulfillment_count = db.scalar(
        select(func.count(Order.id)).where(
            Order.assigned_warehouse_id == wh.id,
            Order.fulfillment_status.in_(["ALLOCATED", "CONSOLIDATED", "PICKING"]),
        )
    ) or 0

    # Số lượng nhân viên kho trực thuộc
    staff_count = db.scalar(
        select(func.count(UserWarehouseMembership.id)).where(
            UserWarehouseMembership.warehouse_id == wh.id,
            UserWarehouseMembership.is_active == True,
            UserWarehouseMembership.role == UserRole.WAREHOUSE_STAFF.value,
        )
    ) or 0

    # Số lệnh điều chuyển đang chờ tiếp nhận
    inbound_transfers = db.scalar(
        select(func.count(StockTransfer.id)).where(
            StockTransfer.to_warehouse_id == wh.id,
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
            "total_on_hand_quantity": int(total_on_hand_qty),
            "near_expiry_batches": near_expiry_batches,
            "pending_fulfillment_count": pending_fulfillment_count,
            "staff_count": staff_count,
            "inbound_transfers": inbound_transfers,
            "order_status_counts": order_status_counts,
            "fulfillment_counts": fulfillment_counts,
        },
    }


# ==============================================================================
# QUẢN LÝ ĐƠN HÀNG TẠI KHO (Orders & Fulfillment)
# ==============================================================================

@router.get("/orders")
def get_warehouse_orders(
    fulfillment_status: Optional[str] = None,
    order_status: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Danh sách đơn hàng được phân bổ cho kho này.
    Bảo vệ chống IDOR: nhân viên hoặc quản lý chỉ xem được đơn thuộc kho mình.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = select(Order).options(selectinload(Order.items)).where(Order.assigned_warehouse_id == wh.id)

    if fulfillment_status and fulfillment_status != "ALL":
        query = query.where(Order.fulfillment_status == fulfillment_status)
    if order_status and order_status != "ALL":
        query = query.where(Order.order_status == order_status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Order.order_code.ilike(term),
                Order.customer_name.ilike(term),
                Order.customer_phone.ilike(term),
            )
        )

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
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items_count": len(o.items),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.get("/orders/{order_id}/pick-details")
def get_order_picking_details(
    order_id: int,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Chi tiết dòng hàng cần soạn cho nhân viên kho (Picking Slip):
    - Tên thuốc, hình ảnh, đơn vị đóng gói
    - Số lượng cần lấy
    - Đề xuất mã lô thuốc theo tiêu chuẩn FEFO (hạn sử dụng >= 180 ngày)
    """
    user, _ = current_user
    order = db.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    if not check_warehouse_permission(user, order.assigned_warehouse_id or -1, db):
        raise HTTPException(status_code=403, detail="Đơn hàng không thuộc phạm vi xử lý của kho bạn")

    wh = db.get(Warehouse, order.assigned_warehouse_id)
    today = date.today()
    fefo_cutoff = today + timedelta(days=180)

    order_lines = []
    for item in order.items:
        # Lấy thông tin SKU và Product
        sku = db.get(ProductSku, item.sku_id)
        product = db.get(CanonicalProduct, sku.product_id) if sku else None

        # Tìm các lô khả dụng tại kho này theo FEFO
        available_batches = db.scalars(
            select(WarehouseBatchStock)
            .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
            .where(
                WarehouseBatchStock.warehouse_id == wh.id,
                InventoryBatch.sku_id == item.sku_id,
                WarehouseBatchStock.quantity_available > 0,
                InventoryBatch.status == "ACTIVE",
                InventoryBatch.expiry_date >= fefo_cutoff,
            )
            .order_by(InventoryBatch.expiry_date.asc())
        ).all()

        batches_info = []
        for b_stock in available_batches:
            ib = b_stock.batch
            batches_info.append({
                "batch_id": ib.id,
                "batch_number": ib.batch_number,
                "expiry_date": ib.expiry_date.isoformat(),
                "quantity_available": b_stock.quantity_available,
            })

        order_lines.append({
            "order_item_id": item.id,
            "sku_id": item.sku_id,
            "product_name": product.canonical_name if product else item.product_name,
            "unit": sku.unit_name if sku else "Hộp",
            "quantity_required": item.quantity,
            "unit_price": float(item.unit_price),
            "line_total": float(item.line_total),
            "suggested_batches": batches_info,
        })

    return {
        "order_id": order.id,
        "order_code": order.order_code,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "shipping_address": order.shipping_address,
        "order_status": order.order_status,
        "fulfillment_status": order.fulfillment_status,
        "warehouse_code": wh.code if wh else None,
        "lines": order_lines,
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
    Cập nhật tiến trình chuẩn bị hàng tại kho:
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


@router.post("/orders/{order_id}/report-issue")
def report_order_fulfillment_issue(
    order_id: int,
    payload: OrderIssuePayload,
    request: Request,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Nhân viên kho báo thiếu hàng hoặc thuốc lỗi trong quá trình soạn hàng.
    """
    user, _ = current_user
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    if not check_warehouse_permission(user, order.assigned_warehouse_id or -1, db):
        raise HTTPException(status_code=403, detail="Đơn hàng không thuộc kho của bạn")

    write_audit(
        db,
        "REPORT_ORDER_ISSUE",
        "Order",
        order.id,
        user=user,
        request=request,
        after={"issue_type": payload.issue_type, "reason": payload.reason},
    )
    db.commit()

    return {
        "success": True,
        "message": "Đã ghi nhận sự cố soạn hàng. Quản lý kho sẽ nhận được thông báo để xử lý.",
        "order_code": order.order_code,
    }


# ==============================================================================
# TỒN KHO & LÔ THUỐC (Stock & Batches Breakdown)
# ==============================================================================

@router.get("/stock")
def get_warehouse_stock(
    warehouse_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Xem tồn kho theo sản phẩm & SKU tại kho hiện tại.
    Chế độ chỉ đọc cho Nhân Viên Kho, chi tiết cho Quản Lý Kho.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = (
        select(
            CanonicalProduct.id.label("product_id"),
            CanonicalProduct.canonical_name,
            CanonicalProduct.registration_number,
            CanonicalProduct.product_type,
            ProductSku.id.label("sku_id"),
            ProductSku.sku_code,
            ProductSku.unit_name,
            func.coalesce(func.sum(WarehouseBatchStock.quantity_on_hand), 0).label("total_on_hand"),
            func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0).label("total_available"),
            func.coalesce(func.sum(WarehouseBatchStock.quantity_reserved), 0).label("total_reserved"),
            func.count(WarehouseBatchStock.id).label("batches_count"),
        )
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .join(ProductSku, InventoryBatch.sku_id == ProductSku.id)
        .join(CanonicalProduct, ProductSku.product_id == CanonicalProduct.id)
        .where(WarehouseBatchStock.warehouse_id == wh.id)
        .group_by(
            CanonicalProduct.id,
            CanonicalProduct.canonical_name,
            CanonicalProduct.registration_number,
            CanonicalProduct.product_type,
            ProductSku.id,
            ProductSku.sku_code,
            ProductSku.unit_name,
        )
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                CanonicalProduct.canonical_name.ilike(term),
                CanonicalProduct.registration_number.ilike(term),
                ProductSku.sku_code.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(CanonicalProduct.canonical_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for r in rows:
        items.append({
            "product_id": r.product_id,
            "product_name": r.canonical_name,
            "registration_number": r.registration_number,
            "product_type": r.product_type,
            "sku_id": r.sku_id,
            "sku_code": r.sku_code,
            "unit_name": r.unit_name,
            "total_on_hand": int(r.total_on_hand),
            "total_available": int(r.total_available),
            "total_reserved": int(r.total_reserved),
            "batches_count": int(r.batches_count),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.get("/batches")
def get_warehouse_batches(
    warehouse_id: Optional[int] = None,
    sku_id: Optional[int] = None,
    near_expiry_only: bool = False,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Quản lý mã lô, hạn dùng, ngày nhập và số lượng tồn chi tiết tại kho.
    Gắn cờ cảnh báo lô cận hạn (< 180 ngày).
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    today = date.today()
    fefo_cutoff = today + timedelta(days=180)

    query = (
        select(WarehouseBatchStock)
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .join(ProductSku, InventoryBatch.sku_id == ProductSku.id)
        .join(CanonicalProduct, ProductSku.product_id == CanonicalProduct.id)
        .where(WarehouseBatchStock.warehouse_id == wh.id)
        .options(
            selectinload(WarehouseBatchStock.batch).selectinload(InventoryBatch.sku).selectinload(ProductSku.product)
        )
    )

    if sku_id:
        query = query.where(InventoryBatch.sku_id == sku_id)
    if near_expiry_only:
        query = query.where(
            WarehouseBatchStock.quantity_on_hand > 0,
            InventoryBatch.expiry_date <= fefo_cutoff,
        )
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                InventoryBatch.batch_number.ilike(term),
                CanonicalProduct.canonical_name.ilike(term),
                ProductSku.sku_code.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    stocks = db.scalars(
        query.order_by(InventoryBatch.expiry_date.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for s in stocks:
        b = s.batch
        sku = b.sku if b else None
        prod = sku.product if sku else None
        is_near_exp = bool(b.expiry_date <= fefo_cutoff) if b else False
        is_exp = bool(b.expiry_date < today) if b else False

        items.append({
            "id": s.id,
            "batch_id": b.id if b else None,
            "batch_number": b.batch_number if b else "",
            "product_name": prod.canonical_name if prod else "",
            "sku_code": sku.sku_code if sku else "",
            "unit_name": sku.unit_name if sku else "",
            "manufacture_date": b.manufacture_date.isoformat() if b and b.manufacture_date else None,
            "expiry_date": b.expiry_date.isoformat() if b else None,
            "quantity_on_hand": s.quantity_on_hand,
            "quantity_available": s.quantity_available,
            "quantity_reserved": s.quantity_reserved,
            "status": b.status if b else "UNKNOWN",
            "is_near_expiry": is_near_exp,
            "is_expired": is_exp,
            "fefo_eligible": bool(not is_near_exp and not is_exp and b.status == "ACTIVE"),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


# ==============================================================================
# NHẬP KHO (Stock Receipts & Inbound Flow)
# ==============================================================================

@router.get("/receipts")
def get_warehouse_receipts(
    warehouse_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Danh sách phiếu nhập kho GSP.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = select(StockReceipt).options(
        selectinload(StockReceipt.supplier),
        selectinload(StockReceipt.items),
    ).where(StockReceipt.warehouse_id == wh.id)

    if status_filter and status_filter != "ALL":
        query = query.where(StockReceipt.status == status_filter.upper())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    receipts = db.scalars(
        query.order_by(StockReceipt.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for r in receipts:
        items.append({
            "id": r.id,
            "receipt_code": r.receipt_code,
            "supplier_name": r.supplier.name if r.supplier else "Nội bộ",
            "status": r.status,
            "total_amount": float(r.total_amount),
            "received_date": r.received_date.isoformat() if r.received_date else None,
            "note": r.note,
            "items_count": len(r.items),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.post("/receipts", status_code=status.HTTP_201_CREATED)
def create_warehouse_receipt(
    payload: ReceiptCreatePayload,
    request: Request,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Quản lý kho tạo phiếu nhập thuốc mới theo lô.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db)

    supplier = db.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà cung cấp")

    receipt_code = f"REC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    received_dt = datetime.fromisoformat(payload.received_date) if payload.received_date else utcnow()

    new_receipt = StockReceipt(
        receipt_code=receipt_code,
        warehouse_id=wh.id,
        supplier_id=supplier.id,
        status="CONFIRMED",  # Hoàn tất nhập kho ngay
        received_date=received_dt,
        total_amount=Decimal("0.0"),
        note=payload.note,
        created_by=user.id,
        confirmed_by=user.id,
    )
    db.add(new_receipt)
    db.flush()

    total_amount = Decimal("0.0")
    for item_data in payload.items:
        sku = db.get(ProductSku, item_data.sku_id)
        if not sku:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy SKU id={item_data.sku_id}")

        exp_date = date.fromisoformat(item_data.expiry_date)
        mfg_date = date.fromisoformat(item_data.manufacture_date) if item_data.manufacture_date else None
        line_total = Decimal(str(item_data.purchase_unit_price)) * item_data.quantity
        total_amount += line_total

        # Tìm hoặc tạo InventoryBatch
        batch = db.scalar(
            select(InventoryBatch).where(
                InventoryBatch.sku_id == sku.id,
                InventoryBatch.batch_number == item_data.batch_number.strip(),
            )
        )
        if not batch:
            batch = InventoryBatch(
                batch_number=item_data.batch_number.strip(),
                sku_id=sku.id,
                supplier_id=supplier.id,
                manufacture_date=mfg_date,
                expiry_date=exp_date,
                status="ACTIVE",
            )
            db.add(batch)
            db.flush()

        # Tạo ReceiptItem
        r_item = StockReceiptItem(
            receipt_id=new_receipt.id,
            sku_id=sku.id,
            batch_number=batch.batch_number,
            manufacture_date=mfg_date,
            expiry_date=exp_date,
            quantity=item_data.quantity,
            purchase_unit_price=Decimal(str(item_data.purchase_unit_price)),
            line_total=line_total,
            batch_id=batch.id,
        )
        db.add(r_item)

        # Cập nhật tồn kho tại kho này (WarehouseBatchStock)
        batch_stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh.id,
                WarehouseBatchStock.batch_id == batch.id,
            )
        )
        if batch_stock:
            batch_stock.quantity_on_hand += item_data.quantity
            batch_stock.quantity_available += item_data.quantity
        else:
            batch_stock = WarehouseBatchStock(
                warehouse_id=wh.id,
                batch_id=batch.id,
                quantity_on_hand=item_data.quantity,
                quantity_available=item_data.quantity,
                quantity_reserved=0,
            )
            db.add(batch_stock)
        db.flush()

        # Ghi StockMovement
        movement_code = f"MOV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        movement = StockMovement(
            movement_code=movement_code,
            movement_type="RECEIPT",
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity=item_data.quantity,
            balance_after=batch_stock.quantity_on_hand,
            reference_type="STOCK_RECEIPT",
            reference_id=receipt_code,
            created_by=user.id,
            note=f"Nhập kho theo phiếu {receipt_code}",
        )
        db.add(movement)

    new_receipt.total_amount = total_amount
    write_audit(
        db,
        "CREATE_STOCK_RECEIPT",
        "StockReceipt",
        new_receipt.id,
        user=user,
        request=request,
        after={"receipt_code": receipt_code, "warehouse_id": wh.id, "total_amount": float(total_amount)},
    )
    db.commit()
    db.refresh(new_receipt)

    return {
        "success": True,
        "receipt_code": new_receipt.receipt_code,
        "total_amount": float(new_receipt.total_amount),
        "status": new_receipt.status,
    }


# ==============================================================================
# KIỂM KÊ & ĐIỀU CHỈNH TỒN KHO (Bắt Buộc Nhập Lý Do)
# ==============================================================================

@router.get("/adjustments")
def get_warehouse_adjustments(
    warehouse_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Lịch sử kiểm kê và phiếu điều chỉnh tồn kho.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = select(StockAdjustment).options(
        selectinload(StockAdjustment.items).selectinload(StockAdjustmentItem.batch)
    ).where(StockAdjustment.warehouse_id == wh.id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    adjs = db.scalars(
        query.order_by(StockAdjustment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for a in adjs:
        items.append({
            "id": a.id,
            "adjustment_code": a.adjustment_code,
            "reason": a.reason,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "items_count": len(a.items),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.post("/adjustments", status_code=status.HTTP_201_CREATED)
def create_stock_adjustment(
    payload: StockAdjustmentPayload,
    request: Request,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Điều chỉnh tồn kho nhưng BẮT BUỘC nhập lý do (vỡ hỏng, hết hạn, chênh lệch kiểm kê).
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db)

    if not payload.reason or len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Bắt buộc phải nhập lý do điều chỉnh tồn kho (tối thiểu 5 ký tự)")

    adj_code = f"ADJ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    adjustment = StockAdjustment(
        adjustment_code=adj_code,
        warehouse_id=wh.id,
        reason=payload.reason.strip(),
        status="CONFIRMED",
        created_by=user.id,
        confirmed_by=user.id,
    )
    db.add(adjustment)
    db.flush()

    for it in payload.items:
        batch_stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh.id,
                WarehouseBatchStock.batch_id == it.batch_id,
            )
        )
        if not batch_stock:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tồn kho cho lô id={it.batch_id}")

        system_qty = batch_stock.quantity_on_hand
        actual_qty = it.actual_quantity
        delta_qty = actual_qty - system_qty

        # Cập nhật tồn kho
        batch_stock.quantity_on_hand = actual_qty
        batch_stock.quantity_available = max(0, actual_qty - batch_stock.quantity_reserved)

        adj_item = StockAdjustmentItem(
            adjustment_id=adjustment.id,
            batch_id=it.batch_id,
            system_quantity=system_qty,
            actual_quantity=actual_qty,
            delta_quantity=delta_qty,
            reason=it.reason or payload.reason,
        )
        db.add(adj_item)

        # Ghi StockMovement
        mov_type = "ADJUST_INC" if delta_qty >= 0 else "ADJUST_DEC"
        movement_code = f"MOV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        movement = StockMovement(
            movement_code=movement_code,
            movement_type=mov_type,
            warehouse_id=wh.id,
            batch_id=it.batch_id,
            quantity=delta_qty,
            balance_after=actual_qty,
            reference_type="ADJUSTMENT",
            reference_id=adj_code,
            created_by=user.id,
            note=f"Điều chỉnh tồn kho: {payload.reason}",
        )
        db.add(movement)

    write_audit(
        db,
        "STOCK_ADJUSTMENT",
        "StockAdjustment",
        adjustment.id,
        user=user,
        request=request,
        after={"adjustment_code": adj_code, "reason": payload.reason, "warehouse_id": wh.id},
    )
    db.commit()
    db.refresh(adjustment)

    return {
        "success": True,
        "adjustment_code": adjustment.adjustment_code,
        "reason": adjustment.reason,
        "status": adjustment.status,
    }


# ==============================================================================
# ĐIỀU CHUYỂN KHO (Transfers & Consolidation)
# ==============================================================================

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
            "shipped_at": t.shipped_at.isoformat() if t.shipped_at else None,
            "received_at": t.received_at.isoformat() if t.received_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "items_count": len(t.items),
        }
        for t in transfers
    ]


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
def create_warehouse_transfer(
    payload: TransferCreatePayload,
    request: Request,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Khởi tạo yêu cầu điều chuyển hàng từ kho hiện tại sang kho khác.
    """
    user, _ = current_user
    wh_from = _resolve_caller_warehouse(user, db)

    wh_to = db.get(Warehouse, payload.to_warehouse_id)
    if not wh_to:
        raise HTTPException(status_code=404, detail="Không tìm thấy kho đích")

    if wh_from.id == wh_to.id:
        raise HTTPException(status_code=400, detail="Kho xuất và kho đích không được trùng nhau")

    transfer_code = f"TRF-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    transfer = StockTransfer(
        transfer_code=transfer_code,
        from_warehouse_id=wh_from.id,
        to_warehouse_id=wh_to.id,
        status="IN_TRANSIT",
        shipped_at=utcnow(),
        note=payload.note,
    )
    db.add(transfer)
    db.flush()

    for it in payload.items:
        batch_stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh_from.id,
                WarehouseBatchStock.batch_id == it["batch_id"],
            )
        )
        qty = int(it["quantity"])
        if not batch_stock or batch_stock.quantity_available < qty:
            raise HTTPException(status_code=400, detail=f"Không đủ tồn kho khả dụng cho lô id={it['batch_id']}")

        # Trừ kho xuất
        batch_stock.quantity_on_hand -= qty
        batch_stock.quantity_available -= qty

        trf_item = StockTransferItem(
            transfer_id=transfer.id,
            sku_id=it["sku_id"],
            batch_id=it["batch_id"],
            quantity=qty,
        )
        db.add(trf_item)

    write_audit(
        db,
        "CREATE_STOCK_TRANSFER",
        "StockTransfer",
        transfer.id,
        user=user,
        request=request,
        after={"transfer_code": transfer_code, "from_warehouse_id": wh_from.id, "to_warehouse_id": wh_to.id},
    )
    db.commit()
    db.refresh(transfer)

    return {
        "success": True,
        "transfer_code": transfer.transfer_code,
        "status": transfer.status,
    }


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


# ==============================================================================
# QUẢN LÝ NHÂN VIÊN KHO TRỰC THUỘC (Subordinate Staff)
# ==============================================================================

@router.get("/staff", response_model=list[UserOut])
def list_warehouse_staff(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Xem danh sách nhân viên cấp dưới trực thuộc kho của mình.
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


@router.patch("/staff/{staff_id}/toggle-status")
def toggle_warehouse_staff_status(
    staff_id: int,
    request: Request,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Quản lý kho khóa hoặc mở khóa nhân viên trong kho của mình.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db)

    target_staff = db.get(User, staff_id)
    if not target_staff:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")

    # Kiểm tra quyền: nhân viên phải thuộc kho này
    membership = db.scalar(
        select(UserWarehouseMembership).where(
            UserWarehouseMembership.user_id == staff_id,
            UserWarehouseMembership.warehouse_id == wh.id,
        )
    )
    if not membership and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Nhân viên này không thuộc kho của bạn")

    target_staff.is_active = not target_staff.is_active
    action_label = "MỞ KHÓA" if target_staff.is_active else "KHÓA"

    write_audit(
        db,
        "TOGGLE_STAFF_STATUS",
        "User",
        target_staff.id,
        user=user,
        request=request,
        after={"is_active": target_staff.is_active, "action": action_label},
    )
    db.commit()
    db.refresh(target_staff)

    return {
        "success": True,
        "staff_id": target_staff.id,
        "is_active": target_staff.is_active,
        "message": f"Đã {action_label.lower()} nhân viên {target_staff.full_name} thành công",
    }


# ==============================================================================
# NHẬT KÝ THAO TÁC & PHẢN HỒI ĐƠN HÀNG
# ==============================================================================

@router.get("/audit-logs")
def get_warehouse_audit_logs(
    warehouse_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Nhật ký thao tác và audit log của các nhân viên và quản lý trong kho này.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    # Lấy danh sách user_id thuộc kho
    user_ids = db.scalars(
        select(UserWarehouseMembership.user_id).where(UserWarehouseMembership.warehouse_id == wh.id)
    ).all()

    query = select(AuditLog).where(
        or_(
            AuditLog.user_id.in_(user_ids),
            AuditLog.after_json.ilike(f'%"warehouse_id": {wh.id}%'),
        )
    )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    logs = db.scalars(
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for l in logs:
        u = db.get(User, l.user_id) if l.user_id else None
        items.append({
            "id": l.id,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "user_email": u.email if u else "Hệ thống",
            "user_name": u.full_name if u else "Hệ thống",
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "details": l.after_json or l.before_json,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.get("/reviews")
def get_warehouse_reviews(
    warehouse_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Xem phản hồi và đánh giá liên quan đến các đơn hàng do kho mình xử lý.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    # Đơn hàng thuộc kho
    order_ids = db.scalars(select(Order.id).where(Order.assigned_warehouse_id == wh.id)).all()

    query = select(ProductReview).where(ProductReview.order_id.in_(order_ids))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    reviews = db.scalars(
        query.order_by(ProductReview.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for r in reviews:
        prod = db.get(CanonicalProduct, r.product_id) if r.product_id else None
        items.append({
            "id": r.id,
            "order_id": r.order_id,
            "product_name": prod.canonical_name if prod else "",
            "rating": r.rating,
            "comment": r.comment,
            "is_verified_purchase": r.is_verified_purchase,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


# ==============================================================================
# NHÂN VIÊN KHO (Warehouse Staff Specialized Endpoints)
# ==============================================================================

@router.get("/staff/today-tasks")
def get_staff_today_tasks(
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Giao diện làm việc hôm nay cho nhân viên kho (Task Overview):
    - Đơn hàng cần lấy (Picking)
    - Đơn hàng chờ đóng gói (Packed)
    - Kiện hàng luân chuyển cần kiểm đếm
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db)

    # Danh sách đơn cần soạn (ALLOCATED, CONSOLIDATED, PICKING)
    orders_to_pick = db.scalars(
        select(Order).options(selectinload(Order.items)).where(
            Order.assigned_warehouse_id == wh.id,
            Order.fulfillment_status.in_(["ALLOCATED", "CONSOLIDATED", "PICKING"]),
        ).order_by(Order.created_at.asc()).limit(20)
    ).all()

    # Danh sách đơn đã soạn xong, chờ đóng gói (PICKING -> PACKED)
    orders_to_pack = db.scalars(
        select(Order).options(selectinload(Order.items)).where(
            Order.assigned_warehouse_id == wh.id,
            Order.fulfillment_status == "PICKING",
        ).order_by(Order.created_at.asc()).limit(20)
    ).all()

    # Kiện hàng điều chuyển đến kho cần tiếp nhận
    inbound_transfers = db.scalars(
        select(StockTransfer).options(
            selectinload(StockTransfer.from_warehouse),
            selectinload(StockTransfer.items),
        ).where(
            StockTransfer.to_warehouse_id == wh.id,
            StockTransfer.status.in_(["DRAFT", "IN_TRANSIT"]),
        ).order_by(StockTransfer.created_at.asc()).limit(10)
    ).all()

    return {
        "warehouse": {"id": wh.id, "code": wh.code, "name": wh.name},
        "picking_tasks": [
            {
                "order_id": o.id,
                "order_code": o.order_code,
                "customer_name": o.customer_name,
                "customer_phone": o.customer_phone,
                "items_count": len(o.items),
                "fulfillment_status": o.fulfillment_status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders_to_pick
        ],
        "packing_tasks": [
            {
                "order_id": o.id,
                "order_code": o.order_code,
                "customer_name": o.customer_name,
                "items_count": len(o.items),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders_to_pack
        ],
        "inbound_transfers": [
            {
                "transfer_id": t.id,
                "transfer_code": t.transfer_code,
                "from_warehouse_name": t.from_warehouse.name,
                "items_count": len(t.items),
                "status": t.status,
            }
            for t in inbound_transfers
        ],
    }


@router.get("/staff/my-history")
def get_staff_personal_history(
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Lịch sử thao tác công việc của chính nhân viên kho.
    """
    user, _ = current_user
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    ).all()

    return [
        {
            "id": l.id,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "details": l.after_json or l.before_json,
        }
        for l in logs
    ]
