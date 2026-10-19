"""Warehouse Portal API.
Comprehensive portal backend for Warehouse Managers and Warehouse Staff with strict multi-warehouse RBAC:
- Strict Data Isolation & Anti-IDOR Defense: warehouse_id is validated against the authenticated session token.
- Warehouse Manager Scope: Overview KPIs, Orders Fulfillment, Batch Management, Stock Receipts, Inventory Checks & Adjustments with mandatory reasons, Transfers, Staff Management, Warehouse Audits, and Customer Reviews.
- Warehouse Staff Scope: Today's Tasks, Fast Picking & Packing Workflow, Read-only Stock Lookup, Report Missing/Defect Issues, and Personal History.
"""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import io
import csv
import json
import hashlib
import logging
from typing import Any, List, Optional
import uuid

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import (
    check_warehouse_permission,
    get_current_user,
    get_user_warehouse_membership,
    require_admin,
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
    ProductCandidate,
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
    WarehouseAlert,
    WarehouseBatchStock,
    WarehouseImportJob,
    WarehouseNotification,
)
from app.models.enums import FulfillmentStatus, ProcessingStatus, UserRole
from app.models.inventory import UserWarehouseMembership
from app.schemas.auth import UserOut
from app.services.audit import write_audit
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.warehouse_notification_service import WarehouseNotificationService

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
    fulfillment_status: Optional[str] = None
    status: Optional[str] = None
    note: Optional[str] = None
    fulfillment_id: Optional[int] = None


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
@router.get("/me/dashboard")
def get_my_warehouse_info(
    warehouse_id: Optional[int] = None,
    time_range: Optional[str] = Query("30days", description="today | 7days | 30days | custom"),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Dashboard riêng cho WAREHOUSE_MANAGER & WAREHOUSE_STAFF:
    - Hiển thị đầy đủ các thẻ số liệu theo Section 2
    - Cho phép lọc theo Hôm nay, 7 ngày, 30 ngày hoặc Tùy chọn
    - Phạm vi dữ liệu gắn chặt vào warehouse_id của tài khoản đăng nhập
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    today = date.today()
    now = datetime.now(UTC)
    fefo_cutoff = today + timedelta(days=180)

    # Xác định khoảng thời gian lọc đơn hàng
    filter_start = None
    filter_end = None
    if time_range == "today":
        filter_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
        filter_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=UTC)
    elif time_range == "7days":
        filter_start = now - timedelta(days=7)
    elif time_range == "30days":
        filter_start = now - timedelta(days=30)
    elif time_range == "custom" and from_date:
        try:
            filter_start = datetime.fromisoformat(from_date).replace(tzinfo=UTC)
            if to_date:
                filter_end = datetime.fromisoformat(to_date).replace(tzinfo=UTC)
        except Exception:
            pass

    # Thống kê tồn kho & sản phẩm
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
    total_reserved_qty = db.scalar(
        select(func.coalesce(func.sum(WarehouseBatchStock.quantity_reserved), 0)).where(
            WarehouseBatchStock.warehouse_id == wh.id
        )
    ) or 0

    # Tổng số loại thuốc / SKU riêng biệt tại kho
    total_skus = db.scalar(
        select(func.count(func.distinct(InventoryBatch.sku_id)))
        .join(WarehouseBatchStock, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(WarehouseBatchStock.warehouse_id == wh.id)
    ) or 0

    # Lô cận hạn (<= 180 ngày)
    near_expiry_batches = db.scalar(
        select(func.count(WarehouseBatchStock.id))
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(
            WarehouseBatchStock.warehouse_id == wh.id,
            WarehouseBatchStock.quantity_on_hand > 0,
            InventoryBatch.expiry_date > today,
            InventoryBatch.expiry_date <= fefo_cutoff,
        )
    ) or 0

    # Lô đã hết hạn (<= today)
    expired_batches = db.scalar(
        select(func.count(WarehouseBatchStock.id))
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(
            WarehouseBatchStock.warehouse_id == wh.id,
            WarehouseBatchStock.quantity_on_hand > 0,
            InventoryBatch.expiry_date <= today,
        )
    ) or 0

    # Lô đang cách ly
    quarantined_batches = db.scalar(
        select(func.count(WarehouseBatchStock.id))
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(
            WarehouseBatchStock.warehouse_id == wh.id,
            WarehouseBatchStock.quantity_on_hand > 0,
            InventoryBatch.status == "QUARANTINED",
        )
    ) or 0

    # Số thuốc sắp hết hàng (tồn khả dụng <= 10)
    low_stock_query = (
        select(InventoryBatch.sku_id)
        .join(WarehouseBatchStock, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(WarehouseBatchStock.warehouse_id == wh.id)
        .group_by(InventoryBatch.sku_id)
        .having(func.sum(WarehouseBatchStock.quantity_available) <= 10)
    )
    low_stock_count = db.scalar(select(func.count()).select_from(low_stock_query.subquery())) or 0

    # Thống kê đơn hàng gắn với thời gian lọc
    order_base_query = select(Order).where(Order.assigned_warehouse_id == wh.id)
    if filter_start:
        order_base_query = order_base_query.where(Order.created_at >= filter_start)
    if filter_end:
        order_base_query = order_base_query.where(Order.created_at <= filter_end)

    total_assigned_orders = db.scalar(select(func.count()).select_from(order_base_query.subquery())) or 0

    order_status_counts = {}
    for st in ["PENDING", "PROCESSING", "CONFIRMED", "SHIPPING", "COMPLETED", "CANCELLED", "RETURNED"]:
        q = order_base_query.where(Order.order_status == st)
        order_status_counts[st] = db.scalar(select(func.count()).select_from(q.subquery())) or 0

    fulfillment_counts = {}
    for fs in ["ALLOCATED", "WAITING_INTERNAL_TRANSFER", "CONSOLIDATED", "PICKING", "PACKED", "READY_TO_SHIP", "SHIPPED", "DELIVERED"]:
        q = order_base_query.where(Order.fulfillment_status == fs)
        fulfillment_counts[fs] = db.scalar(select(func.count()).select_from(q.subquery())) or 0

    pending_fulfillment_count = db.scalar(
        select(func.count(Order.id)).where(
            Order.assigned_warehouse_id == wh.id,
            Order.order_status != "CANCELLED",
            Order.fulfillment_status.in_(["ALLOCATED", "CONSOLIDATED", "PICKING"]),
        )
    ) or 0

    staff_count = db.scalar(
        select(func.count(UserWarehouseMembership.id)).where(
            UserWarehouseMembership.warehouse_id == wh.id,
            UserWarehouseMembership.is_active == True,
            UserWarehouseMembership.role == UserRole.WAREHOUSE_STAFF.value,
        )
    ) or 0

    inbound_transfers = db.scalar(
        select(func.count(StockTransfer.id)).where(
            StockTransfer.to_warehouse_id == wh.id,
            StockTransfer.status.in_(["DRAFT", "IN_TRANSIT"]),
        )
    ) or 0

    pending_receipts_count = db.scalar(
        select(func.count(StockReceipt.id)).where(
            StockReceipt.warehouse_id == wh.id,
            StockReceipt.status == "DRAFT",
        )
    ) or 0

    # Số cảnh báo chưa đọc
    unread_alerts_count = db.scalar(
        select(func.count(WarehouseAlert.id)).where(
            WarehouseAlert.warehouse_id == wh.id,
            WarehouseAlert.is_read == False,
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
        "time_range": time_range,
        "kpi": {
            "total_assigned_orders": total_assigned_orders,
            "total_skus": total_skus,
            "total_batches": total_batches,
            "total_available_quantity": int(total_available_qty),
            "total_on_hand_quantity": int(total_on_hand_qty),
            "total_reserved_quantity": int(total_reserved_qty),
            "low_stock_count": low_stock_count,
            "near_expiry_batches": near_expiry_batches,
            "expired_batches": expired_batches,
            "quarantined_batches": quarantined_batches,
            "pending_receipts_count": pending_receipts_count,
            "pending_fulfillment_count": pending_fulfillment_count,
            "staff_count": staff_count,
            "inbound_transfers": inbound_transfers,
            "unread_alerts_count": unread_alerts_count,
            "order_status_counts": order_status_counts,
            "fulfillment_counts": fulfillment_counts,
        },
    }


# ==============================================================================
# QUẢN LÝ ĐƠN HÀNG TẠI KHO (Orders & Fulfillment)
# ==============================================================================

@router.get("/orders")
def get_warehouse_orders(
    status: Optional[str] = None,
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

    effective_tab = (status or fulfillment_status or "").upper()
    if effective_tab == "CANCELLED" or (order_status and order_status.upper() == "CANCELLED"):
        query = query.where(
            or_(
                Order.fulfillment_status == "CANCELLED",
                Order.order_status == "CANCELLED",
            )
        )
    elif effective_tab and effective_tab != "ALL":
        # Với các tab hoạt động (ALLOCATED, PICKING, PACKED, SHIPPED, DELIVERED), không hiển thị đơn đã hủy
        query = query.where(
            Order.fulfillment_status == effective_tab,
            Order.order_status != "CANCELLED",
        )
    elif order_status and order_status.upper() != "ALL":
        query = query.where(Order.order_status == order_status.upper())
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
    - Đề xuất mã lô thuốc theo tiêu chuẩn FEFO (ưu tiên lô cận hạn nhất còn hiệu lực)
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

    order_lines = []
    for item in order.items:
        # Lấy thông tin SKU và Product từ OrderItem
        sku = None
        if item.product_sku:
            sku = db.query(ProductSku).filter(ProductSku.sku_code == item.product_sku).first()
        if not sku and item.product_id:
            sku = db.query(ProductSku).filter(ProductSku.canonical_product_id == item.product_id).first()

        product = None
        if item.product_id:
            product = db.get(CanonicalProduct, item.product_id)
        elif sku and sku.canonical_product_id:
            product = db.get(CanonicalProduct, sku.canonical_product_id)

        # Tìm các lô khả dụng tại kho này theo FEFO (ưu tiên lô cận hạn trước, chưa hết hạn)
        batches_info = []
        if sku and wh:
            available_batches = db.scalars(
                select(WarehouseBatchStock)
                .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
                .where(
                    WarehouseBatchStock.warehouse_id == wh.id,
                    InventoryBatch.sku_id == sku.id,
                    WarehouseBatchStock.quantity_available > 0,
                    InventoryBatch.status == "ACTIVE",
                    InventoryBatch.expiry_date > today,
                )
                .order_by(InventoryBatch.expiry_date.asc())
            ).all()

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
            "sku_id": sku.id if sku else (item.product_id or 0),
            "product_name": item.product_name or (product.canonical_name if product else "Sản phẩm"),
            "unit": sku.uom if sku else "Hộp",
            "quantity_required": item.quantity,
            "unit_price": float(item.price) if item.price is not None else 0.0,
            "line_total": float(item.subtotal) if item.subtotal is not None else (float(item.price or 0.0) * item.quantity),
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
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "warehouse_code": wh.code if wh else None,
        "lines": order_lines,
    }


@router.patch("/orders/{order_id}/fulfillment")
@router.patch("/orders/{order_id}/status")
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

    raw_status = payload.fulfillment_status or payload.status
    if not raw_status:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp trạng thái thực hiện đơn hàng (fulfillment_status)")

    new_status = raw_status.upper()
    valid_statuses = {"ALLOCATED", "PICKING", "PICKED", "PACKED", "SHIPPED", "DELIVERED", "CANCELLED", "CONSOLIDATED"}
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Trạng thái '{new_status}' không hợp lệ")

    # Chặn xuất kho / soạn hàng cho đơn thanh toán online chưa thanh toán tiền thật
    if new_status in ["PICKING", "PICKED", "PACKED", "SHIPPED", "DELIVERED"]:
        if order.payment_method != "COD" and order.payment_status != "PAID":
            raise HTTPException(
                status_code=400,
                detail=f"Đơn hàng thanh toán trực tuyến ({order.payment_method}) chưa thanh toán thành công (Trạng thái: {order.payment_status}). Không thể xử lý soạn hàng hoặc xuất kho khi chưa nhận được tiền.",
            )

    # Lấy danh sách kiện hàng của đơn hàng này
    fulfillments = db.scalars(
        select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)
    ).all()
    if not fulfillments:
        raise HTTPException(status_code=404, detail="Đơn hàng chưa có kiện hàng fulfillment nào.")

    # Xử lý đơn hàng có nhiều fulfillment:
    # Nếu đơn hàng có nhiều hơn 1 fulfillment, bắt buộc payload phải chỉ định rõ fulfillment_id
    if len(fulfillments) > 1 and not payload.fulfillment_id:
        raise HTTPException(
            status_code=400,
            detail="Đơn hàng có nhiều kiện hàng fulfillment. Vui lòng chỉ định rõ 'fulfillment_id' cần cập nhật tiến trình.",
        )

    if payload.fulfillment_id:
        target_ff = next((ff for ff in fulfillments if ff.id == payload.fulfillment_id), None)
        if not target_ff:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy kiện hàng #{payload.fulfillment_id} trong đơn hàng.")
        # Kiểm tra quyền sở hữu kho
        if user.role != UserRole.ADMIN and target_ff.warehouse_id != user.warehouse_id:
            raise HTTPException(status_code=403, detail="Kiện hàng này không thuộc phạm vi kho của bạn.")
        target_ffs = [target_ff]
    else:
        single_ff = fulfillments[0]
        if user.role != UserRole.ADMIN and single_ff.warehouse_id != user.warehouse_id:
            raise HTTPException(status_code=403, detail="Đơn hàng này không có kiện hàng thuộc phạm vi xử lý của kho bạn.")
        target_ffs = [single_ff]

    before_status = order.fulfillment_status

    # Chuyển trạng thái từng kiện hàng qua FulfillmentRoutingService để tuân thủ State Machine và xuất kho thực tế
    for ff in target_ffs:
        FulfillmentRoutingService.transition_fulfillment_status(
            db=db,
            fulfillment_id=ff.id,
            new_status=new_status,
            user_id=user.id,
        )

    db.refresh(order)

    write_audit(
        db,
        "UPDATE_FULFILLMENT_STATUS",
        "Order",
        order.id,
        user=user,
        request=request,
        before={"fulfillment_status": before_status},
        after={"fulfillment_status": order.fulfillment_status, "note": payload.note},
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
            ProductSku.uom.label("unit_name"),
            func.coalesce(func.sum(WarehouseBatchStock.quantity_on_hand), 0).label("total_on_hand"),
            func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0).label("total_available"),
            func.coalesce(func.sum(WarehouseBatchStock.quantity_reserved), 0).label("total_reserved"),
            func.count(WarehouseBatchStock.id).label("batches_count"),
        )
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .join(ProductSku, InventoryBatch.sku_id == ProductSku.id)
        .join(CanonicalProduct, ProductSku.canonical_product_id == CanonicalProduct.id)
        .where(WarehouseBatchStock.warehouse_id == wh.id)
        .group_by(
            CanonicalProduct.id,
            CanonicalProduct.canonical_name,
            CanonicalProduct.registration_number,
            CanonicalProduct.product_type,
            ProductSku.id,
            ProductSku.sku_code,
            ProductSku.uom,
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
        .join(CanonicalProduct, ProductSku.canonical_product_id == CanonicalProduct.id)
        .where(WarehouseBatchStock.warehouse_id == wh.id)
        .options(
            selectinload(WarehouseBatchStock.batch).selectinload(InventoryBatch.sku).selectinload(ProductSku.canonical_product)
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
        prod = sku.canonical_product if sku else None
        is_near_exp = bool(b.expiry_date <= fefo_cutoff) if b else False
        is_exp = bool(b.expiry_date < today) if b else False

        items.append({
            "id": s.id,
            "batch_id": b.id if b else None,
            "batch_number": b.batch_number if b else "",
            "product_name": prod.canonical_name if prod else "",
            "sku_code": sku.sku_code if sku else "",
            "unit_name": sku.uom if sku else "",
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
            "is_large_adjustment": getattr(a, "is_large_adjustment", False),
            "total_quantity_variance": getattr(a, "total_quantity_variance", 0),
            "total_amount_variance": float(getattr(a, "total_amount_variance", 0.0) or 0.0),
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
    Nếu chênh lệch lớn (>= 50 sản phẩm hoặc >= 10.000.000 VNĐ) -> PENDING_ADMIN_APPROVAL.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db)

    if not payload.reason or len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Bắt buộc phải nhập lý do điều chỉnh tồn kho (tối thiểu 5 ký tự)")

    # Tính toán chênh lệch số lượng và giá trị
    total_variance_qty = 0
    total_variance_amount = Decimal("0.0")
    items_plan = []

    for it in payload.items:
        batch_stock = db.scalar(
            select(WarehouseBatchStock)
            .options(selectinload(WarehouseBatchStock.batch).selectinload(InventoryBatch.sku))
            .where(
                WarehouseBatchStock.warehouse_id == wh.id,
                WarehouseBatchStock.batch_id == it.batch_id,
            )
        )
        if not batch_stock:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tồn kho cho lô id={it.batch_id}")

        system_qty = batch_stock.quantity_on_hand
        actual_qty = it.actual_quantity
        delta_qty = actual_qty - system_qty
        diff = abs(delta_qty)

        total_variance_qty += diff
        unit_price = Decimal("0.0")
        if batch_stock.batch and batch_stock.batch.sku and batch_stock.batch.sku.base_price:
            unit_price = batch_stock.batch.sku.base_price
        total_variance_amount += Decimal(diff) * unit_price

        items_plan.append((it, batch_stock, system_qty, actual_qty, delta_qty))

    is_large = (total_variance_qty >= 50) or (total_variance_amount >= Decimal("10000000.0"))
    adj_status = "PENDING_ADMIN_APPROVAL" if is_large else "CONFIRMED"

    adj_code = f"ADJ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    adjustment = StockAdjustment(
        adjustment_code=adj_code,
        warehouse_id=wh.id,
        reason=payload.reason.strip(),
        status=adj_status,
        is_large_adjustment=is_large,
        total_quantity_variance=total_variance_qty,
        total_amount_variance=total_variance_amount,
        created_by=user.id,
        confirmed_by=user.id if not is_large else None,
    )
    db.add(adjustment)
    db.flush()

    for it, batch_stock, system_qty, actual_qty, delta_qty in items_plan:
        adj_item = StockAdjustmentItem(
            adjustment_id=adjustment.id,
            batch_id=it.batch_id,
            system_quantity=system_qty,
            actual_quantity=actual_qty,
            delta_quantity=delta_qty,
            reason=it.reason or payload.reason,
        )
        db.add(adj_item)

        # Nếu không vượt ngưỡng lớn thì cập nhật ngay
        if not is_large:
            batch_stock.quantity_on_hand = actual_qty
            batch_stock.quantity_available = max(0, actual_qty - batch_stock.quantity_reserved)

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

    if is_large:
        # Tạo cảnh báo kho
        alert = WarehouseAlert(
            warehouse_id=wh.id,
            alert_type="STOCK_MISMATCH",
            title=f"Kiểm kê {adj_code} cần Admin phê duyệt",
            message=f"Chênh lệch kiểm kê lớn: {total_variance_qty} đơn vị (~{float(total_variance_amount):,.0f} VNĐ). Đã gửi yêu cầu tới Admin.",
            severity="CRITICAL",
            reference_type="ADJUSTMENT",
            reference_id=adj_code,
        )
        db.add(alert)

    write_audit(
        db,
        "STOCK_ADJUSTMENT",
        "StockAdjustment",
        adjustment.id,
        user=user,
        request=request,
        after={
            "adjustment_code": adj_code,
            "reason": payload.reason,
            "status": adj_status,
            "is_large": is_large,
            "total_variance_qty": total_variance_qty,
            "total_variance_amount": float(total_variance_amount),
            "warehouse_id": wh.id,
        },
    )
    db.commit()
    db.refresh(adjustment)

    return {
        "success": True,
        "adjustment_code": adjustment.adjustment_code,
        "reason": adjustment.reason,
        "status": adjustment.status,
        "is_large_adjustment": is_large,
        "total_quantity_variance": total_variance_qty,
        "total_amount_variance": float(total_variance_amount),
        "message": "Phiếu điều chỉnh vượt ngưỡng lớn (>= 50 SP hoặc >= 10.000.000 VNĐ) và đang chờ Admin phê duyệt." if is_large else "Đã cập nhật tồn kho thành công.",
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
        warehouse_id=wh.id,
        is_active=True,
        must_change_password=True,
        created_by_user_id=user.id,
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
    if not target_staff.is_active:
        target_staff.token_version = (target_staff.token_version or 1) + 1
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
            Order.order_status != "CANCELLED",
            Order.fulfillment_status.in_(["ALLOCATED", "CONSOLIDATED", "PICKING"]),
        ).order_by(Order.created_at.asc()).limit(20)
    ).all()

    # Danh sách đơn đã soạn xong, chờ đóng gói (PICKING -> PACKED)
    orders_to_pack = db.scalars(
        select(Order).options(selectinload(Order.items)).where(
            Order.assigned_warehouse_id == wh.id,
            Order.order_status != "CANCELLED",
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


# ==============================================================================
# QUẢN LÝ THUỐC TRONG KHO & CHI TIẾT 5 TABS (Products & 5-Tab Detail Drawer)
# ==============================================================================

@router.get("/products")
def get_warehouse_products(
    warehouse_id: Optional[int] = None,
    search: Optional[str] = None,
    status_filter: Optional[str] = Query("ALL", description="ALL | IN_STOCK | LOW_STOCK | OUT_OF_STOCK | NEAR_EXPIRY"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Danh sách thuốc trong kho (Section 5) kèm bộ lọc chi tiết.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)
    today = date.today()
    fefo_cutoff = today + timedelta(days=180)

    query = (
        select(
            CanonicalProduct.id.label("product_id"),
            CanonicalProduct.canonical_name,
            CanonicalProduct.registration_number,
            CanonicalProduct.product_type,
            CanonicalProduct.image_url,
            ProductSku.id.label("sku_id"),
            ProductSku.sku_code,
            ProductSku.uom,
            func.coalesce(func.sum(WarehouseBatchStock.quantity_on_hand), 0).label("total_on_hand"),
            func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0).label("total_available"),
            func.coalesce(func.sum(WarehouseBatchStock.quantity_reserved), 0).label("total_reserved"),
            func.count(WarehouseBatchStock.id).label("batches_count"),
            func.min(InventoryBatch.expiry_date).label("earliest_expiry"),
        )
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .join(ProductSku, InventoryBatch.sku_id == ProductSku.id)
        .join(CanonicalProduct, ProductSku.canonical_product_id == CanonicalProduct.id)
        .where(WarehouseBatchStock.warehouse_id == wh.id)
        .group_by(
            CanonicalProduct.id,
            CanonicalProduct.canonical_name,
            CanonicalProduct.registration_number,
            CanonicalProduct.product_type,
            CanonicalProduct.image_url,
            ProductSku.id,
            ProductSku.sku_code,
            ProductSku.uom,
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

    if status_filter == "OUT_OF_STOCK":
        query = query.having(func.sum(WarehouseBatchStock.quantity_on_hand) == 0)
    elif status_filter == "LOW_STOCK":
        query = query.having(func.sum(WarehouseBatchStock.quantity_available) <= 10)
    elif status_filter == "IN_STOCK":
        query = query.having(func.sum(WarehouseBatchStock.quantity_available) > 10)
    elif status_filter == "NEAR_EXPIRY":
        query = query.having(func.min(InventoryBatch.expiry_date) <= fefo_cutoff)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(CanonicalProduct.canonical_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for r in rows:
        on_hand = int(r.total_on_hand)
        available = int(r.total_available)
        st = "OUT_OF_STOCK" if on_hand == 0 else ("LOW_STOCK" if available <= 10 else "IN_STOCK")
        items.append({
            "product_id": r.product_id,
            "product_name": r.canonical_name,
            "registration_number": r.registration_number,
            "product_type": r.product_type,
            "image_url": r.image_url,
            "sku_id": r.sku_id,
            "sku_code": r.sku_code,
            "uom": r.uom,
            "unit_name": r.uom,
            "total_on_hand": on_hand,
            "total_available": available,
            "total_reserved": int(r.total_reserved),
            "batches_count": int(r.batches_count),
            "earliest_expiry": r.earliest_expiry.isoformat() if r.earliest_expiry else None,
            "stock_status": st,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.get("/products/{sku_id}")
def get_warehouse_product_detail(
    sku_id: int,
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Chi tiết từng thuốc trong kho (Section 6) với đầy đủ 5 tabs.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    sku = db.get(ProductSku, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="Không tìm thấy SKU")

    product = db.get(CanonicalProduct, sku.canonical_product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy thuốc gốc")

    batch_stocks = db.scalars(
        select(WarehouseBatchStock)
        .options(
            selectinload(WarehouseBatchStock.batch).selectinload(InventoryBatch.supplier),
            selectinload(WarehouseBatchStock.location),
        )
        .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(
            WarehouseBatchStock.warehouse_id == wh.id,
            InventoryBatch.sku_id == sku.id,
        )
    ).all()

    total_on_hand = sum(bs.quantity_on_hand for bs in batch_stocks)
    total_available = sum(bs.quantity_available for bs in batch_stocks)
    total_reserved = sum(bs.quantity_reserved for bs in batch_stocks)
    quarantined_batches = [bs for bs in batch_stocks if bs.batch.status == "QUARANTINED"]
    total_quarantined = sum(bs.quantity_on_hand for bs in quarantined_batches)

    today = date.today()
    batches_data = []
    for bs in batch_stocks:
        b = bs.batch
        days_left = (b.expiry_date - today).days if b.expiry_date else 0
        batches_data.append({
            "batch_id": b.id,
            "batch_number": b.batch_number,
            "manufacture_date": b.manufacture_date.isoformat() if b.manufacture_date else None,
            "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
            "quantity_on_hand": bs.quantity_on_hand,
            "quantity_available": bs.quantity_available,
            "quantity_reserved": bs.quantity_reserved,
            "location_name": bs.location.name if bs.location else "Khu A - Kệ 01",
            "status": b.status,
            "supplier_name": b.supplier.name if b.supplier else "DHG Pharma",
            "days_left": days_left,
            "is_near_expiry": 0 < days_left <= 180,
            "is_expired": days_left <= 0,
        })
    batches_data.sort(key=lambda x: x["expiry_date"] or "")

    batch_ids = [bs.batch_id for bs in batch_stocks]
    movements_data = []
    if batch_ids:
        movs = db.scalars(
            select(StockMovement)
            .options(selectinload(StockMovement.batch))
            .where(
                StockMovement.warehouse_id == wh.id,
                StockMovement.batch_id.in_(batch_ids),
            )
            .order_by(StockMovement.created_at.desc())
            .limit(50)
        ).all()
        for m in movs:
            movements_data.append({
                "id": m.id,
                "movement_code": m.movement_code,
                "movement_type": m.movement_type,
                "batch_number": m.batch.batch_number if m.batch else "—",
                "quantity": m.quantity,
                "balance_after": m.balance_after,
                "reference_type": m.reference_type,
                "reference_id": m.reference_id,
                "note": m.note,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })

    orders_data = []
    if batch_ids:
        allocs = db.scalars(
            select(OrderItemBatchAllocation)
            .options(selectinload(OrderItemBatchAllocation.batch))
            .where(
                OrderItemBatchAllocation.warehouse_id == wh.id,
                OrderItemBatchAllocation.batch_id.in_(batch_ids),
            )
            .order_by(OrderItemBatchAllocation.created_at.desc())
            .limit(50)
        ).all()
        for a in allocs:
            order_item = db.get(OrderItem, a.order_item_id)
            order = db.get(Order, order_item.order_id) if order_item else None
            if order:
                orders_data.append({
                    "order_id": order.id,
                    "order_code": order.order_code,
                    "customer_name": order.customer_name,
                    "allocated_quantity": a.allocated_quantity,
                    "batch_number": a.batch.batch_number if a.batch else "—",
                    "order_status": order.order_status,
                    "fulfillment_status": order.fulfillment_status,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                })

    return {
        "sku_id": sku.id,
        "product_id": product.id,
        "general_info": {
            "canonical_name": product.canonical_name,
            "registration_number": product.registration_number or "—",
            "active_ingredients": ", ".join(f"{ing.ingredient.normalized_name} {ing.original_strength_text or ''}".strip() for ing in product.ingredients if getattr(ing, 'ingredient', None)) if product.ingredients else "—",
            "dosage_form": product.dosage_form or "—",
            "route_of_administration": product.route or "Uống",
            "manufacturer": product.manufacturer or "—",
            "country_of_origin": product.manufacturing_country or "Việt Nam",
            "package_description": product.package_description or sku.uom,
            "is_prescription": getattr(product.rx_otc_status, "value", str(product.rx_otc_status)) == "PRESCRIPTION",
            "regulatory_status": getattr(product.regulatory_status, "value", str(product.regulatory_status)),
            "primary_image_url": product.image_url,
            "description": product.description or "",
            "sku_code": sku.sku_code,
            "uom": sku.uom,
            "base_price": float(sku.base_price or 0),
        },
        "stock_levels": {
            "total_on_hand": total_on_hand,
            "total_available": total_available,
            "total_reserved": total_reserved,
            "total_quarantined": total_quarantined,
            "min_stock": 20,
            "max_stock": 500,
            "reorder_point": 30,
        },
        "batches": batches_data,
        "movements": movements_data,
        "related_orders": orders_data,
    }


# ==============================================================================
# NHẬP FILE THUỐC TẠI MỖI KHO (CSV / XLSX Multi-Step Import Pipeline)
# ==============================================================================

CSV_IMPORT_HEADERS = [
    "registration_number",
    "sku_code",
    "batch_number",
    "manufacturing_date",
    "expiry_date",
    "quantity",
    "uom",
    "unit_cost",
    "supplier_code",
    "invoice_number",
    "receipt_date",
    "storage_location",
    "storage_condition",
    "note",
]

@router.get("/imports/template")
def download_import_template():
    """
    Tải file mẫu nhập kho CSV có đầy đủ 14 cột tiêu chuẩn và hướng dẫn (Section 7).
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_IMPORT_HEADERS)
    writer.writerow([
        "VN-21589-19",
        "SKU-VN-21589-19-BOX",
        "LOT-EFF-2026-X1",
        "2026-01-15",
        "2028-06-30",
        "100",
        "Hộp",
        "12500",
        "NCC-DHG",
        "HD-2026-0089",
        "2026-10-12",
        "Khu A - Kệ 01",
        "Nhiệt độ phòng < 30°C",
        "Lô hàng nhập đợt 3",
    ])
    writer.writerow([
        "VN-29177-17",
        "SKU-VN-29177-17-BOX",
        "LOT-STR-2026-Y2",
        "2026-02-10",
        "2028-08-20",
        "80",
        "Hộp",
        "26000",
        "NCC-DHG",
        "HD-2026-0090",
        "2026-10-12",
        "Khu B - Kệ 02",
        "Khô ráo thoáng mát",
        "Lô bổ sung kho",
    ])
    content = output.getvalue().encode("utf-8-sig")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=h4care_warehouse_import_template.csv"},
    )


@router.post("/imports/preview")
async def preview_import_file(
    file: UploadFile = File(...),
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Đọc và kiểm tra file nhập (CSV/XLSX), phân loại dòng và lưu bản xem trước (Section 7-10).
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File rỗng, vui lòng chọn file có dữ liệu")

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_job = db.scalar(
        select(WarehouseImportJob).where(
            WarehouseImportJob.warehouse_id == wh.id,
            WarehouseImportJob.file_hash == file_hash,
        )
    )
    if existing_job:
        raise HTTPException(
            status_code=400,
            detail=f"File này đã được tải lên trước đó (Mã phiên: {existing_job.import_code}). Để tránh cộng dồn tồn kho nhiều lần, hệ thống chặn tải lại file trùng.",
        )

    filename = file.filename or "import.csv"
    raw_rows = []
    if filename.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active
        headers = [str(cell.value or "").strip().lower() for cell in sheet[1]]
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if any(row):
                row_dict = {headers[i]: str(row[i] or "").strip() for i in range(min(len(headers), len(row)))}
                raw_rows.append(row_dict)
    else:
        text = file_bytes.decode("utf-8-sig", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            cleaned = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            if any(cleaned.values()):
                raw_rows.append(cleaned)

    if not raw_rows:
        raise HTTPException(status_code=400, detail="Không tìm thấy dòng dữ liệu hợp lệ trong file")

    today = date.today()
    min_shelf_life_days = 180  # Rule 1: Tối thiểu 180 ngày

    valid_rows = []
    warning_rows = []
    invalid_rows = []
    candidate_rows = []
    seen_batches = set()

    for idx, r in enumerate(raw_rows, start=2):
        reg_num = r.get("registration_number", "").strip().upper()
        sku_code = r.get("sku_code", "").strip()
        batch_num = r.get("batch_number", "").strip()
        mfg_date_str = r.get("manufacturing_date", "").strip().split(" ")[0].split("T")[0]
        exp_date_str = r.get("expiry_date", "").strip().split(" ")[0].split("T")[0]
        qty_str = r.get("quantity", "").strip()
        uom_str = r.get("uom", "").strip() or "Hộp"
        cost_str = r.get("unit_cost", "").strip() or "0"
        supp_code = r.get("supplier_code", "").strip()
        invoice = r.get("invoice_number", "").strip()
        loc_str = r.get("storage_location", "").strip() or "Khu A"
        note_str = r.get("note", "").strip()

        row_info = {
            "row_index": idx,
            "registration_number": reg_num,
            "sku_code": sku_code,
            "batch_number": batch_num,
            "manufacturing_date": mfg_date_str,
            "expiry_date": exp_date_str,
            "quantity": 0,
            "uom": uom_str,
            "unit_cost": 0.0,
            "supplier_code": supp_code,
            "invoice_number": invoice,
            "storage_location": loc_str,
            "note": note_str,
            "errors": [],
            "warnings": [],
            "product_name": None,
        }

        if not batch_num:
            row_info["errors"].append("Số lô thuốc không được để trống")
        elif batch_num in seen_batches:
            row_info["warnings"].append(f"Số lô {batch_num} xuất hiện nhiều lần trong file")
        if batch_num:
            seen_batches.add(batch_num)

        try:
            qty = int(qty_str)
            if qty <= 0:
                row_info["errors"].append("Số lượng nhập phải lớn hơn 0")
            row_info["quantity"] = qty
        except ValueError:
            row_info["errors"].append("Số lượng nhập không hợp lệ")

        try:
            cost = float(cost_str)
            if cost < 0:
                row_info["errors"].append("Giá nhập không được âm")
            row_info["unit_cost"] = cost
        except ValueError:
            row_info["errors"].append("Giá nhập không hợp lệ")

        exp_date = None
        try:
            exp_date = date.fromisoformat(exp_date_str)
            if exp_date <= today:
                row_info["errors"].append(f"Lô thuốc đã hết hạn ({exp_date_str})")
            else:
                remaining_days = (exp_date - today).days
                if remaining_days < min_shelf_life_days:
                    row_info["errors"].append(f"Hạn sử dụng còn {remaining_days} ngày, không đủ tiêu chuẩn tối thiểu 180 ngày để nhập kho (Rule 1)")
        except Exception:
            row_info["errors"].append("Hạn sử dụng không đúng định dạng YYYY-MM-DD")

        if mfg_date_str:
            try:
                mfg_date = date.fromisoformat(mfg_date_str)
                if exp_date and mfg_date >= exp_date:
                    row_info["errors"].append("Ngày sản xuất phải trước hạn sử dụng")
            except Exception:
                row_info["warnings"].append("Ngày sản xuất không đúng định dạng YYYY-MM-DD")

        product = db.scalar(select(CanonicalProduct).where(CanonicalProduct.registration_number == reg_num)) if reg_num else None
        sku = db.scalar(select(ProductSku).where(ProductSku.sku_code == sku_code)) if sku_code else None

        if not product and not sku:
            row_info["status"] = "WAITING_ADMIN_REVIEW"
            row_info["warnings"].append("Thuốc chưa có trong dữ liệu Admin. Dòng nhập chuyển vào hàng chờ Admin phê duyệt.")
            candidate_rows.append(row_info)
            continue

        if product:
            row_info["product_name"] = product.canonical_name
        elif sku and sku.canonical_product:
            row_info["product_name"] = sku.canonical_product.canonical_name

        if row_info["errors"]:
            row_info["status"] = "INVALID"
            invalid_rows.append(row_info)
        elif row_info["warnings"]:
            row_info["status"] = "WARNING"
            warning_rows.append(row_info)
        else:
            row_info["status"] = "VALID"
            valid_rows.append(row_info)

    import_code = f"IMP-{wh.code}-{datetime.now().strftime('%y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    job = WarehouseImportJob(
        warehouse_id=wh.id,
        import_code=import_code,
        file_hash=file_hash,
        filename=filename,
        file_size=len(file_bytes),
        imported_by=user.id,
        total_rows=len(raw_rows),
        valid_rows=len(valid_rows),
        warning_rows=len(warning_rows),
        invalid_rows=len(invalid_rows),
        candidate_rows=len(candidate_rows),
        status="PREVIEW",
        preview_data=json.dumps(valid_rows + warning_rows, ensure_ascii=False),
        error_details=json.dumps(invalid_rows + candidate_rows, ensure_ascii=False),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "import_id": job.id,
        "import_code": job.import_code,
        "filename": filename,
        "total_rows": job.total_rows,
        "valid_count": len(valid_rows),
        "warning_count": len(warning_rows),
        "invalid_count": len(invalid_rows),
        "candidate_count": len(candidate_rows),
        "can_commit": len(valid_rows) + len(warning_rows) > 0,
        "preview_rows": (valid_rows + warning_rows)[:50],
        "invalid_rows": invalid_rows[:50],
        "candidate_rows": candidate_rows[:50],
    }


@router.post("/imports/{import_id}/commit")
def commit_import_job(
    import_id: int,
    request: Request,
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Xác nhận ghi dữ liệu nhập kho từ bản xem trước hợp lệ (Section 11).
    Chỉ Quản lý kho được thực hiện (Rule 3).
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    job = db.get(WarehouseImportJob, import_id)
    if not job or job.warehouse_id != wh.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên nhập kho")

    if job.status != "PREVIEW":
        raise HTTPException(status_code=400, detail="Phiên nhập kho này đã được xử lý hoặc không hợp lệ")

    rows_to_import = []
    if job.preview_data:
        try:
            rows_to_import = json.loads(job.preview_data)
        except Exception:
            rows_to_import = []

    if not rows_to_import:
        raise HTTPException(status_code=400, detail="Không có dòng dữ liệu hợp lệ nào để ghi nhận vào kho")

    receipt_code = f"REC-{wh.code}-{datetime.now().strftime('%y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    supplier = db.scalar(select(Supplier).where(Supplier.is_active == True))
    if not supplier:
        supplier = Supplier(
            code="SUPP-DEFAULT",
            name="Nhà Cung Cấp Mặc Định",
            is_active=True,
        )
        db.add(supplier)
        db.flush()

    receipt = StockReceipt(
        receipt_code=receipt_code,
        warehouse_id=wh.id,
        supplier_id=supplier.id,
        status="CONFIRMED",
        received_date=utcnow(),
        total_amount=Decimal("0.0"),
        note=f"Nhập kho tự động từ file {job.filename} (Mã phiên: {job.import_code})",
        created_by=user.id,
        confirmed_by=user.id,
    )
    db.add(receipt)
    db.flush()

    total_amount = Decimal("0.0")
    total_items = 0

    for r in rows_to_import:
        sku = db.scalar(select(ProductSku).where(ProductSku.sku_code == r["sku_code"]))
        if not sku:
            prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.registration_number == r["registration_number"]))
            if prod:
                sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id))

        if not sku:
            continue

        exp_d = date.fromisoformat(r["expiry_date"].split(" ")[0].split("T")[0])
        mfg_d = date.fromisoformat(r["manufacturing_date"].split(" ")[0].split("T")[0]) if r.get("manufacturing_date") else None
        qty = int(r["quantity"])
        unit_cost = Decimal(str(r["unit_cost"]))
        line_total = Decimal(qty) * unit_cost
        total_amount += line_total
        total_items += qty

        batch = db.scalar(
            select(InventoryBatch).where(
                InventoryBatch.sku_id == sku.id,
                InventoryBatch.batch_number == r["batch_number"],
            )
        )
        if not batch:
            batch = InventoryBatch(
                sku_id=sku.id,
                batch_number=r["batch_number"],
                manufacture_date=mfg_d,
                expiry_date=exp_d,
                supplier_id=supplier.id if supplier else None,
                initial_quantity=qty,
                status="ACTIVE",
            )
            db.add(batch)
            db.flush()

        batch_stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh.id,
                WarehouseBatchStock.batch_id == batch.id,
            )
        )
        if batch_stock:
            batch_stock.quantity_on_hand += qty
            batch_stock.quantity_available += qty
        else:
            batch_stock = WarehouseBatchStock(
                warehouse_id=wh.id,
                batch_id=batch.id,
                quantity_on_hand=qty,
                quantity_available=qty,
                quantity_reserved=0,
            )
            db.add(batch_stock)
        db.flush()

        rc_item = StockReceiptItem(
            receipt_id=receipt.id,
            sku_id=sku.id,
            batch_number=batch.batch_number,
            manufacture_date=mfg_d,
            expiry_date=exp_d,
            quantity=qty,
            purchase_unit_price=unit_cost,
            line_total=line_total,
            batch_id=batch.id,
        )
        db.add(rc_item)

        mov_code = f"MOV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        mov = StockMovement(
            movement_code=mov_code,
            movement_type="RECEIPT",
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity=qty,
            balance_after=batch_stock.quantity_on_hand,
            reference_type="STOCK_RECEIPT",
            reference_id=receipt.receipt_code,
            created_by=user.id,
            note=f"Nhập file {job.filename}",
        )
        db.add(mov)

    receipt.total_amount = total_amount
    job.status = "COMMITTED"
    job.receipt_id = receipt.id
    job.committed_at = utcnow()

    write_audit(
        db,
        "IMPORT_WAREHOUSE_FILE",
        "WarehouseImportJob",
        job.id,
        user=user,
        request=request,
        after={
            "import_code": job.import_code,
            "receipt_code": receipt.receipt_code,
            "total_items": total_items,
            "total_amount": float(total_amount),
            "warehouse_id": wh.id,
        },
    )
    db.commit()

    return {
        "success": True,
        "message": f"Đã nhập kho thành công {total_items} sản phẩm qua phiếu nhập {receipt.receipt_code}",
        "receipt_code": receipt.receipt_code,
        "import_code": job.import_code,
        "total_amount": float(total_amount),
        "total_items": total_items,
    }


@router.get("/imports")
def list_warehouse_imports(
    warehouse_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Lịch sử các phiên nhập file vào kho.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = (
        select(WarehouseImportJob)
        .options(selectinload(WarehouseImportJob.user))
        .where(WarehouseImportJob.warehouse_id == wh.id)
    )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    jobs = db.scalars(
        query.order_by(WarehouseImportJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for j in jobs:
        items.append({
            "id": j.id,
            "import_code": j.import_code,
            "filename": j.filename,
            "total_rows": j.total_rows,
            "valid_rows": j.valid_rows,
            "invalid_rows": j.invalid_rows,
            "candidate_rows": j.candidate_rows,
            "status": j.status,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "committed_at": j.committed_at.isoformat() if j.committed_at else None,
            "imported_by_name": j.user.full_name if j.user else "—",
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


# ==============================================================================
# CẢNH BÁO KHO (Warehouse Alerts & Real-time Anomalies)
# ==============================================================================

@router.get("/alerts")
def get_warehouse_alerts(
    severity: Optional[str] = None,
    is_read: Optional[bool] = None,
    warehouse_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Danh sách cảnh báo kho (Section 13): hết hàng, cận hạn, tồn kho bất thường, kiểm kê lớn.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    today = date.today()
    fefo_cutoff = today + timedelta(days=180)

    near_expiry_batches = db.scalars(
        select(InventoryBatch)
        .join(WarehouseBatchStock, WarehouseBatchStock.batch_id == InventoryBatch.id)
        .where(
            WarehouseBatchStock.warehouse_id == wh.id,
            WarehouseBatchStock.quantity_available > 0,
            InventoryBatch.expiry_date > today,
            InventoryBatch.expiry_date <= fefo_cutoff,
        )
    ).all()

    for b in near_expiry_batches:
        alert_exists = db.scalar(
            select(WarehouseAlert).where(
                WarehouseAlert.warehouse_id == wh.id,
                WarehouseAlert.reference_id == b.batch_number,
                WarehouseAlert.alert_type == "NEAR_EXPIRY",
            )
        )
        if not alert_exists:
            days_left = (b.expiry_date - today).days
            db.add(WarehouseAlert(
                warehouse_id=wh.id,
                alert_type="NEAR_EXPIRY",
                title=f"Lô {b.batch_number} sắp hết hạn",
                message=f"Lô thuốc còn {days_left} ngày sử dụng (HSD: {b.expiry_date}). Cần ưu tiên xuất kho FEFO.",
                severity="WARNING" if days_left > 90 else "CRITICAL",
                reference_type="BATCH",
                reference_id=b.batch_number,
            ))
    db.commit()

    query = select(WarehouseAlert).where(WarehouseAlert.warehouse_id == wh.id)
    if severity:
        query = query.where(WarehouseAlert.severity == severity.upper())
    if is_read is not None:
        query = query.where(WarehouseAlert.is_read == is_read)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    unread_total = db.scalar(
        select(func.count()).where(WarehouseAlert.warehouse_id == wh.id, WarehouseAlert.is_read == False)
    ) or 0

    alerts = db.scalars(
        query.order_by(WarehouseAlert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for a in alerts:
        items.append({
            "id": a.id,
            "alert_type": a.alert_type,
            "title": a.title,
            "message": a.message,
            "severity": a.severity,
            "reference_type": a.reference_type,
            "reference_id": a.reference_id,
            "is_read": a.is_read,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "unread_total": unread_total,
        "page": page,
        "page_size": page_size,
        "warehouse_code": wh.code,
    }


@router.patch("/alerts/{alert_id}/read")
def mark_alert_as_read(
    alert_id: int,
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Xác nhận đã xem cảnh báo (Section 13).
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    alert = db.get(WarehouseAlert, alert_id)
    if not alert or alert.warehouse_id != wh.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh báo")

    alert.is_read = True
    alert.read_by = user.id
    alert.read_at = utcnow()
    db.commit()

    return {"success": True, "alert_id": alert.id, "is_read": True}


@router.post("/alerts/mark-all-read")
def mark_all_alerts_as_read(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Đánh dấu tất cả cảnh báo của kho là đã đọc.
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)

    alerts = db.scalars(
        select(WarehouseAlert).where(WarehouseAlert.warehouse_id == wh.id, WarehouseAlert.is_read == False)
    ).all()

    for a in alerts:
        a.is_read = True
        a.read_by = user.id
        a.read_at = utcnow()

    db.commit()
    return {"success": True, "marked_count": len(alerts)}


# ==============================================================================
# ADMIN DUYỆT ĐIỀU CHỈNH TỒN KHO LỚN (Governance & Admin Approval)
# ==============================================================================

@router.post("/adjustments/{adjustment_id}/admin-approve")
def admin_approve_stock_adjustment(
    adjustment_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin phê duyệt phiếu điều chỉnh tồn kho lớn (Section 12).
    """
    admin_user = current_user
    adj = db.get(StockAdjustment, adjustment_id)
    if not adj:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu điều chỉnh")

    if adj.status != "PENDING_ADMIN_APPROVAL":
        raise HTTPException(status_code=400, detail="Phiếu này không ở trạng thái chờ Admin duyệt")

    for item in adj.items:
        batch_stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == adj.warehouse_id,
                WarehouseBatchStock.batch_id == item.batch_id,
            )
        )
        if batch_stock:
            batch_stock.quantity_on_hand = item.actual_quantity
            batch_stock.quantity_available = max(0, item.actual_quantity - batch_stock.quantity_reserved)

            mov_type = "ADJUST_INC" if item.delta_quantity >= 0 else "ADJUST_DEC"
            mov_code = f"MOV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            mov = StockMovement(
                movement_code=mov_code,
                movement_type=mov_type,
                warehouse_id=adj.warehouse_id,
                batch_id=item.batch_id,
                quantity=item.delta_quantity,
                balance_after=item.actual_quantity,
                reference_type="ADJUSTMENT",
                reference_id=adj.adjustment_code,
                created_by=admin_user.id,
                note=f"Admin duyệt kiểm kê: {adj.reason}",
            )
            db.add(mov)

    adj.status = "CONFIRMED"
    adj.admin_approved_by = admin_user.id
    adj.admin_approved_at = utcnow()

    write_audit(
        db,
        "ADMIN_APPROVE_ADJUSTMENT",
        "StockAdjustment",
        adj.id,
        user=admin_user,
        request=request,
        after={"adjustment_code": adj.adjustment_code, "status": "CONFIRMED"},
    )
    db.commit()

    return {
        "success": True,
        "status": "CONFIRMED",
        "adjustment_code": adj.adjustment_code,
        "message": f"Admin đã duyệt thành công phiếu {adj.adjustment_code}",
    }


@router.post("/adjustments/{adjustment_id}/admin-reject")
def admin_reject_stock_adjustment(
    adjustment_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin từ chối phiếu điều chỉnh tồn kho lớn.
    """
    admin_user = current_user
    adj = db.get(StockAdjustment, adjustment_id)
    if not adj:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu điều chỉnh")

    if adj.status != "PENDING_ADMIN_APPROVAL":
        raise HTTPException(status_code=400, detail="Phiếu này không ở trạng thái chờ Admin duyệt")

    adj.status = "REJECTED"
    write_audit(
        db,
        "ADMIN_REJECT_ADJUSTMENT",
        "StockAdjustment",
        adj.id,
        user=admin_user,
        request=request,
        after={"adjustment_code": adj.adjustment_code, "status": "REJECTED"},
    )
    db.commit()

    return {"success": True, "message": f"Admin đã từ chối phiếu {adj.adjustment_code}"}


# ==============================================================================
# HỆ THỐNG THÔNG BÁO KHO (WAREHOUSE NOTIFICATIONS - RBAC & ANTI-IDOR)
# ==============================================================================

@router.get("/notifications")
def get_warehouse_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    is_read: Optional[bool] = None,
    severity: Optional[str] = None,
    notification_type: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách thông báo dành cho người dùng:
    - ADMIN: Xem toàn bộ thông báo hệ thống (hoặc lọc theo warehouse_id nếu có chỉ định).
    - Quản lý kho: Xem toàn bộ thông báo thuộc kho mình phụ trách.
    - Nhân viên kho: Xem đơn mới (ORDER_NEW, ORDER_CANCELLED) và công việc được giao trực tiếp cho mình trong kho.
    """
    user, _ = current_user
    wh = None
    if user.role == UserRole.ADMIN:
        if warehouse_id:
            wh = db.get(Warehouse, warehouse_id)
    else:
        wh = _resolve_caller_warehouse(user, db, warehouse_id)

    # Kích hoạt quét tự động hạn sử dụng (FEFO), tồn kho và đơn quá hạn
    if user.role in [UserRole.WAREHOUSE_MANAGER, UserRole.ADMIN]:
        try:
            if wh:
                WarehouseNotificationService.run_all_scans(db, warehouse_id=wh.id)
            elif user.role == UserRole.ADMIN:
                active_whs = db.scalars(select(Warehouse).where(Warehouse.is_active == True)).all()
                for aw in active_whs:
                    WarehouseNotificationService.run_all_scans(db, warehouse_id=aw.id)
        except Exception as e:
            logger.warning(f"Error running notification scans: {e}")

    query = select(WarehouseNotification).options(selectinload(WarehouseNotification.warehouse))
    if wh is not None:
        query = query.where(WarehouseNotification.warehouse_id == wh.id)

    # Lọc phân quyền theo vai trò nhân viên kho
    if user.role == UserRole.WAREHOUSE_STAFF:
        query = query.where(
            or_(
                WarehouseNotification.recipient_user_id == user.id,
                and_(
                    WarehouseNotification.recipient_user_id.is_(None),
                    WarehouseNotification.notification_type.in_(["ORDER_NEW", "ORDER_CANCELLED"]),
                ),
            )
        )

    if is_read is not None:
        query = query.where(WarehouseNotification.is_read == is_read)
    if severity and severity.upper() != "ALL":
        query = query.where(WarehouseNotification.severity == severity.upper())
    if notification_type and notification_type.upper() != "ALL":
        query = query.where(WarehouseNotification.notification_type == notification_type.upper())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    unread_q = select(func.count()).select_from(WarehouseNotification).where(
        WarehouseNotification.is_read.is_(False),
    )
    if wh is not None:
        unread_q = unread_q.where(WarehouseNotification.warehouse_id == wh.id)
    if user.role == UserRole.WAREHOUSE_STAFF:
        unread_q = unread_q.where(
            or_(
                WarehouseNotification.recipient_user_id == user.id,
                and_(
                    WarehouseNotification.recipient_user_id.is_(None),
                    WarehouseNotification.notification_type.in_(["ORDER_NEW", "ORDER_CANCELLED"]),
                ),
            )
        )
    unread_total = db.scalar(unread_q) or 0

    notifications = db.scalars(
        query.order_by(WarehouseNotification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for n in notifications:
        items.append({
            "id": n.id,
            "warehouse_id": n.warehouse_id,
            "warehouse_code": n.warehouse.code if n.warehouse else None,
            "warehouse_name": n.warehouse.name if n.warehouse else None,
            "recipient_user_id": n.recipient_user_id,
            "notification_type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "severity": n.severity,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "action_url": n.action_url,
            "is_read": n.is_read,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "unread_total": unread_total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/notifications/unread-count")
def get_warehouse_notifications_unread_count(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Endpoint phản hồi nhanh số lượng thông báo chưa đọc (phục vụ Polling chuông thông báo).
    """
    user, _ = current_user
    wh = None
    if user.role == UserRole.ADMIN:
        if warehouse_id:
            wh = db.get(Warehouse, warehouse_id)
    else:
        wh = _resolve_caller_warehouse(user, db, warehouse_id)

    unread_q = select(func.count()).select_from(WarehouseNotification).where(
        WarehouseNotification.is_read.is_(False),
    )
    if wh is not None:
        unread_q = unread_q.where(WarehouseNotification.warehouse_id == wh.id)

    if user.role == UserRole.WAREHOUSE_STAFF:
        unread_q = unread_q.where(
            or_(
                WarehouseNotification.recipient_user_id == user.id,
                and_(
                    WarehouseNotification.recipient_user_id.is_(None),
                    WarehouseNotification.notification_type.in_(["ORDER_NEW", "ORDER_CANCELLED"]),
                ),
            )
        )
    unread_count = db.scalar(unread_q) or 0
    return {"unread_count": unread_count}


@router.patch("/notifications/{notification_id}/read")
def mark_warehouse_notification_as_read(
    notification_id: int,
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Đánh dấu thông báo là đã đọc.
    Bảo vệ chống IDOR: Nếu thông báo thuộc kho khác hoặc của nhân viên khác, trả HTTP 404 hoặc 403.
    """
    user, _ = current_user
    notif = db.get(WarehouseNotification, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")

    if user.role != UserRole.ADMIN:
        wh = _resolve_caller_warehouse(user, db, warehouse_id)
        if notif.warehouse_id != wh.id:
            raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên thông báo của kho khác")

        if user.role == UserRole.WAREHOUSE_STAFF:
            is_my_task = notif.recipient_user_id == user.id
            is_order_broadcast = notif.recipient_user_id is None and notif.notification_type in ["ORDER_NEW", "ORDER_CANCELLED"]
            if not (is_my_task or is_order_broadcast):
                raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên thông báo này")

    notif.is_read = True
    notif.read_at = utcnow()
    db.commit()

    return {"success": True, "id": notif.id, "is_read": True}


@router.post("/notifications/mark-all-read")
def mark_all_warehouse_notifications_as_read(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_staff_or_manager),
    db: Session = Depends(get_db),
):
    """
    Đánh dấu tất cả thông báo hợp lệ của người dùng là đã đọc.
    """
    user, _ = current_user
    wh = None
    if user.role == UserRole.ADMIN:
        if warehouse_id:
            wh = db.get(Warehouse, warehouse_id)
    else:
        wh = _resolve_caller_warehouse(user, db, warehouse_id)

    query = select(WarehouseNotification).where(
        WarehouseNotification.is_read.is_(False),
    )
    if wh is not None:
        query = query.where(WarehouseNotification.warehouse_id == wh.id)

    if user.role == UserRole.WAREHOUSE_STAFF:
        query = query.where(
            or_(
                WarehouseNotification.recipient_user_id == user.id,
                and_(
                    WarehouseNotification.recipient_user_id.is_(None),
                    WarehouseNotification.notification_type.in_(["ORDER_NEW", "ORDER_CANCELLED"]),
                ),
            )
        )

    notifications = db.scalars(query).all()
    now_dt = utcnow()
    for n in notifications:
        n.is_read = True
        n.read_at = now_dt

    db.commit()
    return {"success": True, "marked_count": len(notifications)}


@router.post("/notifications/scan")
def trigger_warehouse_notification_scans(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(require_warehouse_manager),
    db: Session = Depends(get_db),
):
    """
    Kích hoạt quét chủ động các điều kiện cảnh báo:
    - Thuốc cận hạn 60 ngày theo FEFO (WARNING, HIGH, CRITICAL, EXPIRED)
    - Tồn kho thấp (<= 10) và Hết hàng (== 0)
    - Đơn hàng quá hạn (> 24h)
    """
    user, _ = current_user
    wh = _resolve_caller_warehouse(user, db, warehouse_id)
    results = WarehouseNotificationService.run_all_scans(db, warehouse_id=wh.id)
    return {"success": True, "warehouse_code": wh.code, **results}
