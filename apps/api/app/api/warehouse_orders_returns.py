"""
apps/api/app/api/warehouse_orders_returns.py

API Đơn hàng, Đổi trả & Hoàn tiền cho Quản lý kho và Nhân viên kho H4CARE:
1. WAREHOUSE_MANAGER (/api/v1/warehouse/me):
   - GET /orders: Danh sách đơn hàng thuộc kho mình kèm thống kê
   - GET /orders/{fulfillment_code}: Chi tiết đơn & danh sách lô thuốc FEFO
   - POST /orders/{fulfillment_code}/assign: Phân công nhân viên lấy hàng/đóng gói
   - GET /returns: Danh sách ca hoàn thuộc kho mình
   - GET /returns/{return_code}: Chi tiết ca hoàn, biên bản kiểm hàng, ảnh bằng chứng
   - POST /returns/{return_code}/assign: Phân công nhân viên kiểm hàng
   - POST /returns/{return_code}/request-reinspection: Yêu cầu nhân viên kiểm tra lại
   - POST /returns/{return_code}/approve: Duyệt hoàn hàng
   - POST /returns/{return_code}/reject: Từ chối hoàn hàng kèm lý do bắt buộc
   - POST /returns/{return_code}/refund: Hoàn tiền (Backend tính toán, xác thực MK)
   - POST /returns/{return_code}/stock-disposition: Phân luồng kho (Restock/Quarantine/Dispose)

2. WAREHOUSE_STAFF (/api/v1/warehouse/staff/me):
   - GET /orders: Các đơn được phân công cho mình
   - GET /returns: Các ca hoàn được phân công cho mình
   - GET /returns/{return_code}: Chi tiết ca hoàn cần kiểm hàng
   - POST /returns/{return_code}/receive: Tiếp nhận hàng từ bưu tá
   - POST /returns/{return_code}/evidence: Tải ảnh/video bằng chứng
   - POST /returns/{return_code}/inspect: Lưu biên bản kiểm đếm chi tiết
   - POST /returns/{return_code}/submit: Nộp kết quả lên Quản lý kho
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import (
    get_current_user,
    require_roles,
    require_warehouse_manager,
    require_warehouse_staff_or_manager,
)
from app.db.session import get_db
from app.models.entities import Order, OrderItem, User
from app.models.enums import UserRole
from app.models.inventory import (
    FulfillmentItem,
    InventoryBatch,
    OrderFulfillment,
    OrderItemBatchAllocation,
    UserWarehouseMembership,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import (
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
    WarehouseReturnCase,
)
from app.services.audit import write_audit
from app.services.refund_calculation_service import RefundCalculationService
from app.services.warehouse_return_service import WarehouseReturnService

manager_router = APIRouter(prefix="/warehouse/me", tags=["Warehouse Manager Operations"])
staff_router = APIRouter(prefix="/warehouse/staff/me", tags=["Warehouse Staff Operations"])
compat_portal_router = APIRouter(prefix="/warehouse-portal", tags=["Warehouse Portal Aliases"])


def utcnow() -> datetime:
    return datetime.now(UTC)


# ==========================================
# SCHEMAS
# ==========================================

class AssignOrderStaffPayload(BaseModel):
    staff_id: int


class AssignReturnStaffPayload(BaseModel):
    staff_id: int


class ReceiveReturnPayload(BaseModel):
    carrier_name: Optional[str] = None
    tracking_code: Optional[str] = None
    package_condition: Optional[str] = None
    note: Optional[str] = None


class EvidencePayload(BaseModel):
    file_url: str
    file_name: str
    mime_type: Optional[str] = "image/jpeg"
    file_category: Optional[str] = "DAMAGE_PHOTO"
    file_size: Optional[int] = 0
    description: Optional[str] = None
    video_url: Optional[str] = None
    return_item_id: Optional[int] = None


class ItemInspectionItem(BaseModel):
    return_item_id: int = Field(..., description="ID sản phẩm đổi/trả bắt buộc")
    condition: Optional[str] = Field(default=None, description="Tình trạng thực tế bắt buộc")
    package_condition: str = Field(..., min_length=1, description="Trạng thái bao bì bắt buộc")
    seal_intact: bool = Field(..., description="Tem niêm phong nguyên vẹn bắt buộc (True/False)")
    batch_matched: bool = Field(..., description="Khớp số lô đã xuất bắt buộc (True/False)")
    expiry_matched: bool = Field(..., description="Khớp hạn sử dụng bắt buộc (True/False)")
    storage_condition_ok: bool = Field(..., description="Điều kiện bảo quản đạt bắt buộc (True/False)")
    received_quantity: int = Field(..., ge=0, description="Số lượng nhận bắt buộc")
    accepted_quantity: int = Field(..., ge=0, description="Số lượng chấp nhận bắt buộc")
    rejected_quantity: int = Field(..., ge=0, description="Số lượng từ chối bắt buộc (không mặc định)")
    restock_destination: Optional[str] = Field(default=None, description="Phân luồng kho bắt buộc")
    suggested_action: Optional[str] = Field(default=None, description="Đề xuất xử lý bắt buộc (RESTOCK/QUARANTINE/DISPOSE)")
    restock_quantity: Optional[int] = Field(default=None, ge=0, description="Số lượng nhập lại kho bán nếu có")
    rejection_reason: Optional[str] = Field(default=None, description="Lý do từ chối nếu có rejected_quantity > 0")
    damage_description: Optional[str] = None
    inspection_note: Optional[str] = None

    @model_validator(mode="before")
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("condition") and data.get("package_condition"):
                data["condition"] = data["package_condition"]
            if not data.get("package_condition") and data.get("condition"):
                data["package_condition"] = data["condition"]
            if not data.get("suggested_action") and data.get("restock_destination"):
                data["suggested_action"] = data["restock_destination"]
            if not data.get("restock_destination") and data.get("suggested_action"):
                data["restock_destination"] = data["suggested_action"]
            if not data.get("rejection_reason") and data.get("damage_description"):
                data["rejection_reason"] = data["damage_description"]
        return data

    @model_validator(mode="after")
    def validate_inspection_safety(self):
        # 1. Bắt buộc có condition và package_condition
        if not self.condition or not str(self.condition).strip():
            raise ValueError("Thiếu trường kiểm định bắt buộc: condition")
        if not self.package_condition or not str(self.package_condition).strip():
            raise ValueError("Thiếu trường kiểm định bắt buộc: package_condition")

        # 2. Bắt buộc có restock_destination hoặc suggested_action
        action = (self.restock_destination or self.suggested_action or "").strip().upper()
        if not action:
            raise ValueError("Thiếu trường kiểm định bắt buộc: restock_destination / suggested_action")

        # 3. Tổng nhận phải bằng tổng chấp nhận + từ chối
        if self.accepted_quantity + self.rejected_quantity != self.received_quantity:
            raise ValueError(
                f"Tổng số lượng chấp nhận ({self.accepted_quantity}) và từ chối ({self.rejected_quantity}) "
                f"phải bằng số lượng nhận ({self.received_quantity})."
            )

        # 4. Bắt buộc có rejection_reason khi có rejected_quantity > 0
        if self.rejected_quantity > 0 and (not self.rejection_reason or not str(self.rejection_reason).strip()):
            raise ValueError(f"Sản phẩm #{self.return_item_id} có {self.rejected_quantity} đơn vị bị từ chối, bắt buộc phải nêu rõ lý do từ chối (rejection_reason).")

        # 5. Kiểm định an toàn khi đề xuất nhập lại kho bán (RESTOCK / SELLABLE_STOCK)
        if action in ["RESTOCK", "SELLABLE_STOCK"]:
            if self.restock_quantity is not None and self.restock_quantity > self.accepted_quantity:
                raise ValueError(f"Số lượng nhập kho bán ({self.restock_quantity}) không được lớn hơn số lượng chấp nhận ({self.accepted_quantity}).")

            failed = []
            if not self.seal_intact:
                failed.append("tem niêm phong không nguyên vẹn (seal_intact=False)")
            if not self.batch_matched:
                failed.append("số lô không khớp đã xuất (batch_matched=False)")
            if not self.expiry_matched:
                failed.append("hạn sử dụng không khớp hoặc hết hạn (expiry_matched=False)")
            if not self.storage_condition_ok:
                failed.append("điều kiện bảo quản không đạt chuẩn GSP (storage_condition_ok=False)")

            if failed:
                raise ValueError(
                    f"Sản phẩm không đạt chuẩn an toàn dược phẩm ({', '.join(failed)}). "
                    "Tuyệt đối không được đề xuất hoặc nhập lại kho bán (RESTOCK/SELLABLE_STOCK). Bắt buộc chuyển sang QUARANTINE hoặc DISPOSE."
                )

            pkg_lower = self.package_condition.lower()
            if any(bad in pkg_lower for bad in ["rách", "móp", "vỡ", "hỏng", "damaged", "broken", "torn"]):
                raise ValueError(f"Bao bì '{self.package_condition}' bị hư hại, không đạt chuẩn nhập lại kho bán.")
        return self


class SaveInspectionPayload(BaseModel):
    inspections: List[ItemInspectionItem]
    general_note: Optional[str] = None


class SubmitInspectionPayload(BaseModel):
    note: Optional[str] = None


class ReinspectionPayload(BaseModel):
    reason: str = Field(..., min_length=5, description="Lý do yêu cầu kiểm tra lại bắt buộc")


class ItemApprovalItem(BaseModel):
    return_item_id: int = Field(..., description="ID sản phẩm đổi/trả")
    approved_quantity: int = Field(..., ge=0, description="Số lượng được quản lý duyệt hoàn tiền")
    rejected_quantity: int = Field(..., ge=0, description="Số lượng từ chối hoàn tiền")
    rejection_reason: Optional[str] = Field(default=None, description="Lý do từ chối (bắt buộc nếu rejected_quantity > 0)")

    @model_validator(mode="after")
    def validate_rejection_reason(self):
        if self.rejected_quantity > 0 and (not self.rejection_reason or not str(self.rejection_reason).strip()):
            raise ValueError(f"Sản phẩm #{self.return_item_id} có {self.rejected_quantity} đơn vị bị từ chối, bắt buộc phải nêu rõ lý do từ chối (rejection_reason).")
        return self


class ApproveReturnPayload(BaseModel):
    items: List[ItemApprovalItem] = Field(..., min_length=1, description="Danh sách phê duyệt chi tiết từng sản phẩm bắt buộc do Quản lý kho duyệt")
    manager_note: Optional[str] = None


class RejectReturnPayload(BaseModel):
    rejection_reason: str = Field(..., min_length=5, description="Lý do từ chối bắt buộc")


class ProcessRefundPayload(BaseModel):
    password: str = Field(..., description="Mật khẩu tài khoản để xác thực bảo mật")
    refund_method: Optional[str] = RefundMethod.BANK_TRANSFER.value
    beneficiary_bank: Optional[str] = None
    beneficiary_account_number: Optional[str] = None
    beneficiary_account_name: Optional[str] = None
    manual_reference_number: Optional[str] = None
    manual_proof_storage_key: Optional[str] = None
    idempotency_key: Optional[str] = None


class StockDispositionPayload(BaseModel):
    disposition: str = Field(..., description="RESTOCK, QUARANTINE, DISPOSE")
    note: Optional[str] = None


class RequestEvidencePayload(BaseModel):
    reason: str = Field(..., min_length=3, description="Lý do yêu cầu bổ sung ảnh")
    instructions: str = Field(..., min_length=3, description="Hướng dẫn chụp ảnh cho khách")
    required_image_count: int = Field(..., ge=1, le=3, description="Số lượng ảnh bắt buộc: 1, 2 hoặc 3")
    return_item_id: Optional[int] = Field(default=None, description="ID sản phẩm cần bổ sung (nếu có)")


class AcceptEvidencePayload(BaseModel):
    manager_note: Optional[str] = Field(default=None, description="Ghi chú của quản lý khi chấp nhận")


# ==========================================
# 1. WAREHOUSE MANAGER ENDPOINTS (/warehouse/me)
# ==========================================

@manager_router.get("/orders")
@compat_portal_router.get("/me/orders")
def get_manager_warehouse_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho xem toàn bộ đơn được phân công cho kho mình kèm thẻ thống kê.
    Chặn truy cập chéo kho (anti-IDOR).
    """
    manager, warehouse_id = auth
    if warehouse_id is None:
        first_wh = db.scalars(select(Warehouse.id).where(Warehouse.is_active.is_(True))).first()
        warehouse_id = first_wh or 1

    # Thống kê nhanh các thẻ
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    ful_base = select(OrderFulfillment).where(OrderFulfillment.warehouse_id == warehouse_id)
    all_fuls = db.scalars(ful_base).all()

    kpi = {
        "total_today": sum(1 for f in all_fuls if f.created_at and f.created_at >= today_start),
        "orders_new": sum(1 for f in all_fuls if f.status == "PENDING"),
        "orders_picking": sum(1 for f in all_fuls if f.status in ["ALLOCATED", "PICKING"]),
        "orders_packing": sum(1 for f in all_fuls if f.status == "PACKED"),
        "orders_shipping": sum(1 for f in all_fuls if f.status == "SHIPPED"),
        "orders_delivered": sum(1 for f in all_fuls if f.status == "DELIVERED"),
        "orders_cancelled": sum(1 for f in all_fuls if f.status == "CANCELLED"),
        "returns_count": db.scalar(
            select(func.count(WarehouseReturnCase.id)).where(
                WarehouseReturnCase.warehouse_id == warehouse_id,
                WarehouseReturnCase.status.not_in(["CLOSED", "REJECTED"]),
            )
        ) or 0,
    }

    # Query phân trang
    query = (
        select(OrderFulfillment)
        .options(
            selectinload(OrderFulfillment.order),
            selectinload(OrderFulfillment.assigned_staff),
            selectinload(OrderFulfillment.items).selectinload(FulfillmentItem.order_item),
        )
        .where(OrderFulfillment.warehouse_id == warehouse_id)
    )

    if status_filter and status_filter.upper() != "ALL":
        query = query.where(OrderFulfillment.status == status_filter.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Order, OrderFulfillment.order_id == Order.id).where(
            or_(
                OrderFulfillment.fulfillment_code.ilike(term),
                Order.order_code.ilike(term),
                Order.customer_name.ilike(term),
                Order.customer_phone.ilike(term),
            )
        )

    total_count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    records = db.scalars(
        query.order_by(desc(OrderFulfillment.id)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items_out = []
    for f in records:
        order = f.order
        items_out.append({
            "id": f.id,
            "fulfillment_code": f.fulfillment_code,
            "order_id": f.order_id,
            "order_code": order.order_code if order else "",
            "customer_name": order.customer_name if order else "",
            "customer_phone": order.customer_phone if order else "",
            "shipping_address": order.shipping_address if order else "",
            "payment_method": order.payment_method if order else "COD",
            "payment_status": order.payment_status if order else "PENDING",
            "status": f.status,
            "carrier_name": f.carrier_name,
            "tracking_code": f.tracking_code,
            "assigned_staff_id": f.assigned_staff_id,
            "assigned_staff_name": f.assigned_staff.full_name if f.assigned_staff else None,
            "total_items": len(f.items),
            "total_quantity": sum(it.quantity for it in f.items),
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "picked_at": f.picked_at.isoformat() if f.picked_at else None,
            "packed_at": f.packed_at.isoformat() if f.packed_at else None,
        })

    return {
        "kpi": kpi,
        "items": items_out,
        "total": total_count,
        "page": page,
        "page_size": page_size,
    }


@manager_router.get("/orders/{fulfillment_code}")
@compat_portal_router.get("/me/orders/{fulfillment_code}")
def get_manager_order_fulfillment_detail(
    fulfillment_code: str,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Chi tiết fulfillment gồm từng loại thuốc, số lượng, lô FEFO và vị trí kệ.
    """
    manager, warehouse_id = auth
    query = (
        select(OrderFulfillment)
        .options(
            selectinload(OrderFulfillment.order).selectinload(Order.items),
            selectinload(OrderFulfillment.assigned_staff),
            selectinload(OrderFulfillment.items).selectinload(FulfillmentItem.order_item),
            selectinload(OrderFulfillment.warehouse),
        )
        .where(
            or_(
                OrderFulfillment.fulfillment_code == fulfillment_code,
                OrderFulfillment.id == int(fulfillment_code) if fulfillment_code.isdigit() else False,
            )
        )
    )
    if warehouse_id is not None:
        query = query.where(OrderFulfillment.warehouse_id == warehouse_id)

    ful = db.scalars(query).first()
    if not ful:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy đơn hàng / fulfillment '{fulfillment_code}' thuộc kho của bạn.",
        )

    # Chi tiết từng sản phẩm kèm lô FEFO
    items_out = []
    for fit in ful.items:
        oit = fit.order_item
        # Tìm các lô được phân bổ
        allocations = db.scalars(
            select(OrderItemBatchAllocation)
            .options(selectinload(OrderItemBatchAllocation.batch))
            .where(OrderItemBatchAllocation.order_item_id == fit.order_item_id)
        ).all()

        batches_out = [
            {
                "batch_id": a.batch_id,
                "batch_number": a.batch.batch_number if a.batch else "N/A",
                "expiry_date": a.batch.expiry_date.isoformat() if a.batch and a.batch.expiry_date else None,
                "allocated_quantity": a.allocated_quantity,
            }
            for a in allocations
        ]

        items_out.append({
            "id": fit.id,
            "order_item_id": fit.order_item_id,
            "product_name": oit.product_name if oit else "",
            "product_sku": oit.product_sku if oit else "",
            "quantity": fit.quantity,
            "price": float(oit.price) if oit else 0.0,
            "subtotal": float(oit.subtotal) if oit else 0.0,
            "batches": batches_out,
        })

    return {
        "id": ful.id,
        "fulfillment_code": ful.fulfillment_code,
        "order_id": ful.order_id,
        "order_code": ful.order.order_code if ful.order else "",
        "warehouse_id": ful.warehouse_id,
        "warehouse_name": ful.warehouse.name if ful.warehouse else "",
        "status": ful.status,
        "carrier_name": ful.carrier_name,
        "tracking_code": ful.tracking_code,
        "assigned_staff_id": ful.assigned_staff_id,
        "assigned_staff_name": ful.assigned_staff.full_name if ful.assigned_staff else None,
        "created_at": ful.created_at.isoformat() if ful.created_at else None,
        "items": items_out,
    }


@manager_router.post("/orders/{fulfillment_code}/assign")
@compat_portal_router.post("/me/orders/{fulfillment_code}/assign")
def assign_order_fulfillment_staff(
    fulfillment_code: str,
    payload: AssignOrderStaffPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Phân công nhân viên lấy hàng/đóng gói cho đơn.
    """
    manager, warehouse_id = auth
    query = select(OrderFulfillment).where(
        or_(
            OrderFulfillment.fulfillment_code == fulfillment_code,
            OrderFulfillment.id == int(fulfillment_code) if fulfillment_code.isdigit() else False,
        )
    )
    if warehouse_id is not None:
        query = query.where(OrderFulfillment.warehouse_id == warehouse_id)

    ful = db.scalars(query).first()
    if not ful:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng thuộc kho của bạn.")

    # Xác thực nhân viên thuộc kho
    membership = db.scalar(
        select(UserWarehouseMembership).where(
            UserWarehouseMembership.user_id == payload.staff_id,
            UserWarehouseMembership.warehouse_id == ful.warehouse_id,
            UserWarehouseMembership.is_active.is_(True),
        )
    )
    if not membership and manager.role != "ADMIN":
        raise HTTPException(status_code=400, detail="Nhân viên không thuộc kho này.")

    staff_user = db.get(User, payload.staff_id)
    ful.assigned_staff_id = payload.staff_id
    if ful.status == "PENDING":
        ful.status = "ALLOCATED"

    if ful.order and ful.warehouse_id:
        try:
            from app.services.warehouse_notification_service import WarehouseNotificationService
            WarehouseNotificationService.notify_order_assigned(
                db=db,
                order=ful.order,
                warehouse_id=ful.warehouse_id,
                staff_user_id=payload.staff_id,
            )
        except Exception:
            pass

    write_audit(
        db=db,
        action="ASSIGN_ORDER_STAFF",
        entity_type="ORDER_FULFILLMENT",
        entity_id=ful.fulfillment_code,
        user=manager,
        details=f"Phân công nhân viên {staff_user.full_name if staff_user else payload.staff_id} xử lý đơn {ful.fulfillment_code}",
    )

    db.commit()
    db.refresh(ful)
    return {"success": True, "fulfillment_code": ful.fulfillment_code, "assigned_staff_id": payload.staff_id}


# --- CA HOÀN QUẢN LÝ KHO ---

@manager_router.get("/returns")
@compat_portal_router.get("/me/returns")
def get_manager_warehouse_returns(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Danh sách toàn bộ ca hoàn thuộc warehouse_id của Quản lý kho.
    """
    manager, warehouse_id = auth
    if warehouse_id is None:
        first_wh = db.scalars(select(Warehouse.id).where(Warehouse.is_active.is_(True))).first()
        warehouse_id = first_wh or 1

    query = (
        select(WarehouseReturnCase)
        .options(
            selectinload(WarehouseReturnCase.return_request),
            selectinload(WarehouseReturnCase.assigned_staff),
            selectinload(WarehouseReturnCase.items),
        )
        .where(WarehouseReturnCase.warehouse_id == warehouse_id)
    )

    if status_filter and status_filter.upper() != "ALL":
        query = query.where(WarehouseReturnCase.status == status_filter.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(ReturnRequest, WarehouseReturnCase.return_request_id == ReturnRequest.id).where(
            or_(
                WarehouseReturnCase.case_code.ilike(term),
                ReturnRequest.return_code.ilike(term),
                ReturnRequest.customer_name.ilike(term),
                ReturnRequest.customer_phone.ilike(term),
            )
        )

    total_count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    cases = db.scalars(
        query.order_by(desc(WarehouseReturnCase.id)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items_out = []
    for c in cases:
        req = c.return_request
        items_out.append({
            "id": c.id,
            "case_code": c.case_code,
            "return_code": req.return_code if req else "",
            "customer_name": req.customer_name if req else "",
            "customer_phone": req.customer_phone if req else "",
            "status": c.status,
            "carrier_name": c.carrier_name,
            "tracking_code": c.tracking_code,
            "assigned_staff_id": c.assigned_staff_id,
            "assigned_staff_name": c.assigned_staff.full_name if c.assigned_staff else None,
            "items_count": len(c.items),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "inspected_at": c.inspected_at.isoformat() if c.inspected_at else None,
            "approved_at": c.approved_at.isoformat() if c.approved_at else None,
            "refund_processed_at": c.refund_processed_at.isoformat() if c.refund_processed_at else None,
            "disposition": c.disposition,
        })

    return {
        "items": items_out,
        "total": total_count,
        "page": page,
        "page_size": page_size,
    }


@manager_router.get("/returns/{return_code}")
@compat_portal_router.get("/me/returns/{return_code}")
def get_manager_return_case_detail(
    return_code: str,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Chi tiết ca hoàn: Đơn gốc, danh sách sản phẩm, biên bản kiểm hàng, ảnh bằng chứng.
    """
    manager, warehouse_id = auth
    case = WarehouseReturnService.get_case_by_identifier(db, return_code, warehouse_id)

    order = case.return_request.order if case.return_request else None

    # Tính toán số tiền hoàn dự kiến dựa trên các sản phẩm trong ca này
    order_items_map = {it.id: it for it in order.items} if order else {}
    items_refund_proposed = Decimal("0.0")
    items_data = []

    for it in case.items:
        oit = order_items_map.get(it.order_item_id)
        net_unit = RefundCalculationService.calculate_net_unit_price(order, oit) if (order and oit) else (it.unit_price_at_purchase or Decimal("0.0"))
        line_proposed = net_unit * Decimal(str(it.accepted_quantity or 0))
        items_refund_proposed += line_proposed

        items_data.append({
            "id": it.id,
            "order_item_id": it.order_item_id,
            "product_id": it.product_id,
            "product_name": it.product_name,
            "requested_quantity": it.requested_quantity,
            "received_quantity": it.received_quantity,
            "accepted_quantity": it.accepted_quantity,
            "rejected_quantity": it.rejected_quantity,
            "unit_price": float(it.unit_price_at_purchase or 0),
            "net_unit_price": float(net_unit or 0),
            "subtotal": float(line_proposed),
            "approved_refund_amount": float(it.approved_refund_amount or 0),
            "condition": it.condition,
            "inspection_note": it.inspection_note,
        })

    # Giới hạn trần hoàn tiền còn lại
    already_refunded = RefundCalculationService.get_already_refunded_amount(db, order.id) if order else Decimal("0.0")
    order_total = Decimal(str(order.total_amount)) if order else Decimal("0.0")
    max_possible = max(Decimal("0.0"), order_total - already_refunded)
    final_proposed = min(items_refund_proposed, max_possible)

    # Lấy thông tin tài khoản thụ hưởng hoàn tiền an toàn (từ bản ghi Refund nếu đã có)
    last_refund = (
        case.refunds[-1]
        if case.refunds
        else (
            case.return_request.refunds[-1]
            if (case.return_request and case.return_request.refunds)
            else None
        )
    )
    bank_name = (
        getattr(last_refund, "beneficiary_bank", None)
        or getattr(last_refund, "beneficiary_bank_name", None)
        or "Mặc định"
    )
    account_name = (
        getattr(last_refund, "beneficiary_account_name", None)
        or (case.return_request.customer_name if case.return_request else "Khách hàng")
    )
    acc_no = getattr(last_refund, "beneficiary_account_number", None)
    account_number_masked = (
        f"***{acc_no[-4:]}" if (acc_no and len(acc_no) >= 4) else (acc_no or "—")
    )

    return {
        "id": case.id,
        "case_code": case.case_code,
        "return_code": case.return_request.return_code if case.return_request else "",
        "warehouse_id": case.warehouse_id,
        "warehouse_name": case.warehouse.name if case.warehouse else "",
        "order_code": order.order_code if order else "",
        "order_total": float(order_total),
        "customer_name": case.return_request.customer_name if case.return_request else "",
        "customer_phone": case.return_request.customer_phone if case.return_request else "",
        "status": case.status,
        "carrier_name": case.carrier_name,
        "tracking_code": case.tracking_code,
        "package_condition": case.package_condition,
        "manager_note": case.manager_note,
        "rejection_reason": case.rejection_reason,
        "disposition": case.disposition,
        "disposition_note": case.disposition_note,
        "assigned_staff": {
            "id": case.assigned_staff.id,
            "full_name": case.assigned_staff.full_name,
            "phone": case.assigned_staff.phone,
        } if case.assigned_staff else None,
        "inspected_by": case.inspected_by_user.full_name if case.inspected_by_user else None,
        "approved_by": case.approved_by_user.full_name if case.approved_by_user else None,
        "refund_processed_by": case.refund_processed_by_user.full_name if case.refund_processed_by_user else None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "inspected_at": case.inspected_at.isoformat() if case.inspected_at else None,
        "approved_at": case.approved_at.isoformat() if case.approved_at else None,
        "refund_processed_at": case.refund_processed_at.isoformat() if case.refund_processed_at else None,
        "items": items_data,
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
                "storage_condition_ok": insp.storage_condition_ok,
                "suggested_action": insp.suggested_action,
                "inspector_name": insp.inspector.full_name if insp.inspector else None,
                "inspection_note": insp.inspection_note,
                "inspected_at": insp.inspected_at.isoformat() if insp.inspected_at else None,
            }
            for insp in case.inspections
        ],
        "evidences": [
            {
                "id": e.id,
                "file_url": e.file_url,
                "file_name": e.file_name,
                "file_category": e.file_category,
                "description": e.description,
                "video_url": e.video_url,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in case.evidences
        ],
        "history": [
            {
                "id": h.id,
                "from_status": h.from_status,
                "to_status": h.to_status,
                "actor_name": h.actor_name,
                "actor_role": h.actor_role,
                "note": h.note,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in sorted(case.history, key=lambda x: x.created_at or datetime.min)
        ],
        "proposed_refund": {
            "items_refund_amount": float(items_refund_proposed),
            "max_possible_refund": float(max_possible),
            "already_refunded": float(already_refunded),
            "final_proposed_refund": float(final_proposed),
        },
        "refund_info": {
            "estimated_refund_amount": float(final_proposed),
            "already_refunded": already_refunded > Decimal("0.0"),
            "refund_status": "COMPLETED" if (already_refunded > Decimal("0.0") and final_proposed == Decimal("0.0")) else "PENDING",
            "beneficiary_bank": bank_name,
            "beneficiary_account_name": account_name,
            "beneficiary_account_number_masked": account_number_masked,
        },
        "active_evidence_request": (
            lambda req: {
                "id": req.id,
                "request_code": req.request_code,
                "return_item_id": req.return_item_id,
                "reason": req.reason,
                "instructions": req.instructions,
                "required_image_count": req.required_image_count,
                "status": req.status,
                "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                "expires_at": req.expires_at.isoformat() if req.expires_at else None,
                "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
                "customer_note": req.customer_note,
                "evidences": [
                    {
                        "id": ev.id,
                        "file_url": ev.file_url,
                        "file_name": ev.file_name,
                        "created_at": ev.created_at.isoformat() if ev.created_at else None,
                    }
                    for ev in (req.evidences or [])
                ],
            } if req else None
        )(
            db.scalar(
                select(ReturnEvidenceRequest)
                .options(selectinload(ReturnEvidenceRequest.evidences))
                .where(
                    ReturnEvidenceRequest.warehouse_return_case_id == case.id,
                    ReturnEvidenceRequest.status.in_([
                        ReturnEvidenceRequestStatus.OPEN.value,
                        ReturnEvidenceRequestStatus.SUBMITTED.value,
                    ]),
                )
                .order_by(ReturnEvidenceRequest.id.desc())
            )
        ),
    }


@manager_router.post("/returns/{return_code}/request-evidence")
@compat_portal_router.post("/me/returns/{return_code}/request-evidence")
def request_customer_evidence_endpoint(
    return_code: str,
    payload: RequestEvidencePayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho yêu cầu khách hàng bổ sung từ 1 đến 3 ảnh.
    """
    manager, warehouse_id = auth
    evidence_req = WarehouseReturnService.request_customer_evidence(
        db=db,
        case_code=return_code,
        user=manager,
        warehouse_id=warehouse_id,
        reason=payload.reason,
        instructions=payload.instructions,
        required_image_count=payload.required_image_count,
        return_item_id=payload.return_item_id,
    )
    return {
        "status": "SUCCESS",
        "message": f"Đã gửi yêu cầu khách bổ sung {evidence_req.required_image_count} hình ảnh thành công.",
        "request_code": evidence_req.request_code,
        "expires_at": evidence_req.expires_at.isoformat() if evidence_req.expires_at else None,
        "case_status": ReturnStatus.WAITING_CUSTOMER_EVIDENCE.value,
    }


@manager_router.post("/returns/{return_code}/accept-evidence")
@compat_portal_router.post("/me/returns/{return_code}/accept-evidence")
def accept_customer_evidence_endpoint(
    return_code: str,
    payload: Optional[AcceptEvidencePayload] = None,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho duyệt chấp nhận bằng chứng và chuyển ca hoàn sang WAITING_MANAGER_APPROVAL.
    """
    manager, warehouse_id = auth
    note = payload.manager_note if payload else None
    case = WarehouseReturnService.accept_customer_evidence(
        db=db,
        case_code=return_code,
        user=manager,
        warehouse_id=warehouse_id,
        manager_note=note,
    )
    return {
        "status": "SUCCESS",
        "message": "Đã chấp nhận bằng chứng của khách hàng. Ca hoàn chuyển sang trạng thái Chờ Quản lý duyệt hoàn.",
        "case_code": case.case_code,
        "case_status": case.status,
    }


@manager_router.post("/returns/{return_code}/assign")
@compat_portal_router.post("/me/returns/{return_code}/assign")
def assign_return_case_staff(
    return_code: str,
    payload: AssignReturnStaffPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho phân công nhân viên kiểm hàng.
    """
    manager, warehouse_id = auth
    wcase = WarehouseReturnService.assign_staff(
        db=db,
        case_code=return_code,
        staff_id=payload.staff_id,
        manager_user=manager,
        warehouse_id=warehouse_id,
    )
    return {"status": "SUCCESS", "success": True, "case_code": wcase.case_code, "assigned_staff_id": payload.staff_id}


@manager_router.post("/returns/{return_code}/request-reinspection")
@compat_portal_router.post("/me/returns/{return_code}/request-reinspection")
def request_case_reinspection(
    return_code: str,
    payload: ReinspectionPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho yêu cầu nhân viên kiểm tra lại khi phát hiện nghi vấn.
    """
    manager, warehouse_id = auth
    wcase = WarehouseReturnService.request_reinspection(
        db=db,
        case_code=return_code,
        manager_user=manager,
        warehouse_id=warehouse_id,
        reason=payload.reason,
    )
    return {"success": True, "case_code": wcase.case_code, "status": wcase.status}


@manager_router.post("/returns/{return_code}/approve")
@compat_portal_router.post("/me/returns/{return_code}/approve")
def approve_return_case(
    return_code: str,
    payload: ApproveReturnPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho phê duyệt đơn hoàn. Chuyển sang REFUND_PENDING.
    """
    manager, warehouse_id = auth
    raw_items = payload.items or payload.accepted_items
    items_approval = [item.model_dump() for item in raw_items] if raw_items else None
    wcase = WarehouseReturnService.manager_approve_case(
        db=db,
        case_code=return_code,
        manager_user=manager,
        warehouse_id=warehouse_id,
        items_approval=items_approval,
        manager_note=payload.manager_note,
    )
    return {"success": True, "case_code": wcase.case_code, "status": wcase.status}


@manager_router.post("/returns/{return_code}/reject")
@compat_portal_router.post("/me/returns/{return_code}/reject")
def reject_return_case(
    return_code: str,
    payload: RejectReturnPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho từ chối yêu cầu hoàn (BẮT BUỘC nhập lý do).
    """
    manager, warehouse_id = auth
    wcase = WarehouseReturnService.manager_reject_case(
        db=db,
        case_code=return_code,
        manager_user=manager,
        warehouse_id=warehouse_id,
        rejection_reason=payload.rejection_reason,
    )
    return {"success": True, "case_code": wcase.case_code, "status": wcase.status}


@manager_router.post("/returns/{return_code}/refund")
@compat_portal_router.post("/me/returns/{return_code}/refund")
def process_return_case_refund(
    return_code: str,
    payload: ProcessRefundPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho thực hiện hoàn tiền:
    - Bắt buộc xác thực mật khẩu.
    - Backend tính toán số tiền hoàn; không cho phép frontend override.
    """
    manager, warehouse_id = auth
    res = WarehouseReturnService.manager_process_refund(
        db=db,
        case_code=return_code,
        manager_user=manager,
        warehouse_id=warehouse_id,
        password=payload.password,
        refund_method=payload.refund_method or RefundMethod.BANK_TRANSFER.value,
        beneficiary_bank=payload.beneficiary_bank,
        beneficiary_account_number=payload.beneficiary_account_number,
        beneficiary_account_name=payload.beneficiary_account_name,
        manual_reference_number=payload.manual_reference_number,
        manual_proof_storage_key=payload.manual_proof_storage_key,
        idempotency_key=payload.idempotency_key,
    )
    return res


@manager_router.post("/returns/{return_code}/stock-disposition")
@compat_portal_router.post("/me/returns/{return_code}/stock-disposition")
def stock_disposition_case(
    return_code: str,
    payload: StockDispositionPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_manager),
):
    """
    Quản lý kho phân luồng xử lý hàng: RESTOCK, QUARANTINE, DISPOSE.
    """
    manager, warehouse_id = auth
    wcase = WarehouseReturnService.manager_stock_disposition(
        db=db,
        case_code=return_code,
        manager_user=manager,
        warehouse_id=warehouse_id,
        disposition=payload.disposition,
        note=payload.note,
    )
    return {"success": True, "case_code": wcase.case_code, "disposition": wcase.disposition, "status": wcase.status}


# ==========================================
# 2. WAREHOUSE STAFF ENDPOINTS (/warehouse/staff/me)
# ==========================================

@staff_router.get("/orders")
def get_staff_assigned_orders(
    db: Session = Depends(get_db),
    staff_user: User = Depends(require_roles(UserRole.WAREHOUSE_STAFF, UserRole.WAREHOUSE_MANAGER, UserRole.ADMIN)),
):
    """
    Nhân viên xem danh sách các đơn hàng / kiện hàng được phân công cho mình.
    """
    fulfillments = db.scalars(
        select(OrderFulfillment)
        .options(
            selectinload(OrderFulfillment.order),
            selectinload(OrderFulfillment.items).selectinload(FulfillmentItem.order_item),
        )
        .where(OrderFulfillment.assigned_staff_id == staff_user.id)
        .order_by(desc(OrderFulfillment.id))
    ).all()

    return [
        {
            "id": f.id,
            "fulfillment_code": f.fulfillment_code,
            "order_code": f.order.order_code if f.order else "",
            "customer_name": f.order.customer_name if f.order else "",
            "customer_phone": f.order.customer_phone if f.order else "",
            "status": f.status,
            "items_count": len(f.items),
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in fulfillments
    ]


@staff_router.get("/returns")
def get_staff_assigned_returns(
    db: Session = Depends(get_db),
    staff_user: User = Depends(require_roles(UserRole.WAREHOUSE_STAFF, UserRole.WAREHOUSE_MANAGER, UserRole.ADMIN)),
):
    """
    Nhân viên xem các ca hoàn hàng được phân công cho mình.
    """
    cases = db.scalars(
        select(WarehouseReturnCase)
        .options(
            selectinload(WarehouseReturnCase.return_request),
            selectinload(WarehouseReturnCase.items),
        )
        .where(
            WarehouseReturnCase.assigned_staff_id == staff_user.id,
        )
        .order_by(desc(WarehouseReturnCase.id))
    ).all()

    items_out = [
        {
            "id": c.id,
            "case_code": c.case_code,
            "return_code": c.return_request.return_code if c.return_request else "",
            "customer_name": c.return_request.customer_name if c.return_request else "",
            "customer_phone": c.return_request.customer_phone if c.return_request else "",
            "status": c.status,
            "carrier_name": c.carrier_name,
            "tracking_code": c.tracking_code,
            "package_condition": c.package_condition,
            "items_count": len(c.items),
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "inspected_at": c.inspected_at.isoformat() if c.inspected_at else None,
        }
        for c in cases
    ]
    return {"items": items_out, "total": len(items_out)}


@staff_router.get("/returns/{return_code}")
def get_staff_return_detail(
    return_code: str,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_staff_or_manager),
):
    """
    Nhân viên xem chi tiết ca hoàn để thực hiện tiếp nhận và kiểm tra.
    """
    user, warehouse_id = auth
    case = WarehouseReturnService.get_case_by_identifier(db, return_code, warehouse_id)

    return {
        "id": case.id,
        "case_code": case.case_code,
        "return_code": case.return_request.return_code if case.return_request else "",
        "status": case.status,
        "carrier_name": case.carrier_name,
        "tracking_code": case.tracking_code,
        "package_condition": case.package_condition,
        "manager_note": case.manager_note,
        "items": [
            {
                "id": it.id,
                "order_item_id": it.order_item_id,
                "product_name": it.product_name,
                "requested_quantity": it.requested_quantity,
                "received_quantity": it.received_quantity,
                "condition": it.condition,
                "inspection_note": it.inspection_note,
            }
            for it in case.items
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
                "inspection_note": insp.inspection_note,
            }
            for insp in case.inspections
        ],
        "evidences": [
            {
                "id": e.id,
                "file_url": e.file_url,
                "file_name": e.file_name,
                "file_category": e.file_category,
                "description": e.description,
            }
            for e in case.evidences
        ],
    }


@staff_router.post("/returns/{return_code}/receive")
def staff_receive_return(
    return_code: str,
    payload: ReceiveReturnPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_staff_or_manager),
):
    """
    Nhân viên kho xác nhận tiếp nhận gói hàng từ bưu tá.
    """
    user, warehouse_id = auth
    wcase = WarehouseReturnService.staff_receive_package(
        db=db,
        case_code=return_code,
        staff_user=user,
        warehouse_id=warehouse_id,
        carrier_name=payload.carrier_name,
        tracking_code=payload.tracking_code,
        package_condition=payload.package_condition,
        note=payload.note,
    )
    return {"success": True, "case_code": wcase.case_code, "status": wcase.status}


@staff_router.post("/returns/{return_code}/evidence")
def staff_upload_return_evidence(
    return_code: str,
    payload: EvidencePayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_staff_or_manager),
):
    """
    Nhân viên tải ảnh/video bằng chứng kiểm hàng.
    """
    user, warehouse_id = auth
    evidence = WarehouseReturnService.record_evidence(
        db=db,
        case_code=return_code,
        user=user,
        warehouse_id=warehouse_id,
        file_url=payload.file_url,
        file_name=payload.file_name,
        mime_type=payload.mime_type or "image/jpeg",
        file_category=payload.file_category or "DAMAGE_PHOTO",
        file_size=payload.file_size or 0,
        description=payload.description,
        video_url=payload.video_url,
        return_item_id=payload.return_item_id,
    )
    return {"success": True, "evidence_id": evidence.id, "file_url": evidence.file_url}


@staff_router.post("/returns/{return_code}/inspect")
def staff_inspect_return(
    return_code: str,
    payload: SaveInspectionPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_staff_or_manager),
):
    """
    Nhân viên lưu biên bản kiểm đếm chi tiết từng sản phẩm.
    """
    user, warehouse_id = auth
    inspections_data = [i.model_dump() for i in payload.inspections]
    wcase = WarehouseReturnService.staff_inspect_items(
        db=db,
        case_code=return_code,
        staff_user=user,
        warehouse_id=warehouse_id,
        inspections_data=inspections_data,
        general_note=payload.general_note,
    )
    return {"success": True, "case_code": wcase.case_code, "status": wcase.status}


@staff_router.post("/returns/{return_code}/submit")
def staff_submit_return_inspection(
    return_code: str,
    payload: SubmitInspectionPayload,
    db: Session = Depends(get_db),
    auth: tuple[User, int | None] = Depends(require_warehouse_staff_or_manager),
):
    """
    Nhân viên kho nộp kết quả kiểm hàng lên Quản lý kho.
    Trạng thái chuyển sang: WAITING_MANAGER_APPROVAL.
    (Nhân viên không có quyền duyệt cuối cùng hay hoàn tiền!)
    """
    user, warehouse_id = auth
    wcase = WarehouseReturnService.staff_submit_inspection(
        db=db,
        case_code=return_code,
        staff_user=user,
        warehouse_id=warehouse_id,
        note=payload.note,
    )
    return {"success": True, "case_code": wcase.case_code, "status": wcase.status}
