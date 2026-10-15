from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import (
    AdministrativeUnit,
    CanonicalProduct,
    FulfillmentItem,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItemBatchAllocation,
    ProductIngredient,
    ProductSku,
    ReturnItem,
    ReturnRequest,
    StockAdjustment,
    StockAdjustmentItem,
    StockMovement,
    StockReceipt,
    StockReceiptItem,
    StockTransfer,
    StockTransferItem,
    Supplier,
    User,
    Warehouse,
    WarehouseBatchStock,
    WarehouseLocation,
)
from app.models.enums import UserRole
from app.services.audit import write_audit


def utcnow() -> datetime:
    return datetime.now(UTC)


router = APIRouter(prefix="/inventory", tags=["Quản lý Kho & Lô thuốc"])
warehouses_router = APIRouter(prefix="/warehouses", tags=["Kho & Chi nhánh"])
admin_warehouses_router = APIRouter(prefix="/admin/warehouses", tags=["Admin Quản lý Kho"])
admin_units_router = APIRouter(prefix="/administrative-units", tags=["Địa giới hành chính"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class WarehouseCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    address: str = Field(..., min_length=5, max_length=500)
    ward: str | None = None
    district: str | None = None
    province: str | None = None
    lat: float | None = None
    lng: float | None = None
    is_active: bool = True
    is_central: bool = False
    phone: str | None = None


class WarehouseUpdateRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    ward: str | None = None
    district: str | None = None
    province: str | None = None
    lat: float | None = None
    lng: float | None = None
    is_active: bool | None = None
    is_central: bool | None = None
    phone: str | None = None


class BatchStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|QUARANTINED|RECALLED|EXPIRED)$")
    reason: str | None = None


class ReceiptItemIn(BaseModel):
    sku_id: int
    batch_number: str = Field(..., min_length=1, max_length=100)
    manufacture_date: date | None = None
    expiry_date: date
    quantity: int = Field(..., gt=0)
    purchase_unit_price: Decimal = Field(..., ge=0)
    storage_location_id: int | None = None


class ReceiptCreateRequest(BaseModel):
    warehouse_id: int
    supplier_id: int
    note: str | None = None
    items: list[ReceiptItemIn] = Field(..., min_items=1)


class TransferItemIn(BaseModel):
    batch_id: int
    quantity: int = Field(..., gt=0)


class TransferCreateRequest(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    note: str | None = None
    items: list[TransferItemIn] = Field(..., min_items=1)


# ==============================================================================
# WAREHOUSES ENDPOINTS
# ==============================================================================

@warehouses_router.get("")
def list_warehouses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    warehouses = db.scalars(
        select(Warehouse)
        .options(selectinload(Warehouse.locations))
        .order_by(Warehouse.id.asc())
    ).all()

    result = []
    for wh in warehouses:
        # Aggregate stocks for this warehouse
        stock_stats = db.query(
            func.count(WarehouseBatchStock.id).label("total_batch_entries"),
            func.sum(WarehouseBatchStock.quantity_on_hand).label("total_on_hand"),
            func.sum(WarehouseBatchStock.quantity_available).label("total_available"),
        ).filter(WarehouseBatchStock.warehouse_id == wh.id).first()

        result.append({
            "id": wh.id,
            "code": wh.code,
            "name": wh.name,
            "address": wh.address,
            "ward": wh.ward,
            "district": wh.district,
            "province": wh.province,
            "lat": wh.lat,
            "lng": wh.lng,
            "is_active": wh.is_active,
            "is_central": wh.is_central,
            "phone": wh.phone,
            "locations_count": len(wh.locations),
            "locations": [
                {
                    "id": loc.id,
                    "code": loc.code,
                    "name": loc.name,
                    "aisle": loc.aisle,
                    "shelf": loc.shelf,
                    "bin": loc.bin,
                }
                for loc in wh.locations
            ],
            "total_on_hand": int(stock_stats.total_on_hand or 0) if stock_stats else 0,
            "total_available": int(stock_stats.total_available or 0) if stock_stats else 0,
            "created_at": wh.created_at.isoformat() if wh.created_at else None,
        })

    return result


@warehouses_router.post("", status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    existing = db.scalar(select(Warehouse).where(Warehouse.code == payload.code.strip()))
    if existing:
        raise HTTPException(status_code=400, detail=f"Mã kho '{payload.code}' đã tồn tại trong hệ thống")

    wh = Warehouse(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        address=payload.address.strip(),
        ward=payload.ward.strip() if payload.ward else None,
        district=payload.district.strip() if payload.district else None,
        province=payload.province.strip() if payload.province else None,
        lat=payload.lat,
        lng=payload.lng,
        is_active=payload.is_active,
        is_central=payload.is_central,
        phone=payload.phone.strip() if payload.phone else None,
    )
    db.add(wh)
    db.commit()
    db.refresh(wh)

    # Automatically create default storage locations
    locs = [
        WarehouseLocation(warehouse_id=wh.id, code=f"{wh.code}-A1", name="Khu vực Dược phẩm Tiêu chuẩn"),
        WarehouseLocation(warehouse_id=wh.id, code=f"{wh.code}-B1", name="Khu vực Thực phẩm Chức năng"),
        WarehouseLocation(warehouse_id=wh.id, code=f"{wh.code}-C1", name="Khu vực Cách ly & Cận hạn"),
    ]
    db.add_all(locs)
    db.commit()

    write_audit(db, "CREATE_WAREHOUSE", "Warehouse", wh.id, user, request, after={"code": wh.code, "name": wh.name})
    db.commit()

    return {"message": "Tạo kho mới thành công", "id": wh.id, "code": wh.code}


@warehouses_router.put("/{wh_id}")
def update_warehouse(
    wh_id: int,
    payload: WarehouseUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    wh = db.get(Warehouse, wh_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin kho")

    before = {"name": wh.name, "is_active": wh.is_active, "phone": wh.phone}
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(wh, field, val)

    db.commit()
    write_audit(db, "UPDATE_WAREHOUSE", "Warehouse", wh.id, user, request, before=before, after=update_data)
    db.commit()

    return {"message": "Cập nhật thông tin kho thành công", "id": wh.id}


@warehouses_router.get("/{wh_id}/stocks")
def get_warehouse_stocks(
    wh_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Xem chi tiết tất cả mặt hàng thuốc, số lượng, phân loại đơn thuốc (Rx/OTC)
    và hạn sử dụng của từng lô trong kho / chi nhánh chỉ định.
    """
    wh = db.get(Warehouse, wh_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin kho chi nhánh")

    stocks = db.scalars(
        select(WarehouseBatchStock)
        .where(WarehouseBatchStock.warehouse_id == wh_id)
        .options(
            selectinload(WarehouseBatchStock.batch).selectinload(InventoryBatch.sku).selectinload(ProductSku.canonical_product),
            selectinload(WarehouseBatchStock.batch).selectinload(InventoryBatch.supplier),
            selectinload(WarehouseBatchStock.location),
        )
    ).all()

    today = date.today()
    items = []
    unique_product_ids = set()
    total_on_hand = 0
    total_available = 0
    total_reserved = 0
    rx_count = 0
    otc_count = 0
    near_expiry_count = 0
    expired_count = 0

    for s in stocks:
        b = s.batch
        if not b:
            continue

        prod = b.sku.canonical_product if b.sku else None
        prod_name = prod.canonical_name if prod else "N/A"
        prod_id = prod.id if prod else None
        if prod_id:
            unique_product_ids.add(prod_id)

        rx_val = prod.rx_otc_status.value if prod and prod.rx_otc_status else "UNKNOWN"
        is_rx = rx_val == "RX"
        if is_rx:
            rx_count += 1
        elif rx_val == "OTC":
            otc_count += 1

        days_remaining = (b.expiry_date - today).days
        if days_remaining <= 0 or b.status == "EXPIRED":
            risk = "CRITICAL"
            risk_label = "Đã hết hạn"
            expired_count += 1
        elif days_remaining <= 60:
            risk = "CRITICAL"
            risk_label = "Cận hạn khẩn cấp (<60 ngày)"
            near_expiry_count += 1
        elif days_remaining <= 180:
            risk = "WARNING"
            risk_label = "Cận hạn (2-6 tháng)"
            near_expiry_count += 1
        else:
            risk = "SAFE"
            risk_label = "An toàn (>6 tháng)"

        total_on_hand += s.quantity_on_hand
        total_available += s.quantity_available
        total_reserved += s.quantity_reserved

        items.append({
            "stock_id": s.id,
            "product_id": prod_id,
            "product_name": prod_name,
            "registration_number": prod.registration_number if prod else None,
            "dosage_form": prod.dosage_form if prod else None,
            "package_description": prod.package_description if prod else None,
            "manufacturer": prod.manufacturer if prod else None,
            "rx_otc": rx_val,
            "is_prescription": is_rx,
            "rx_label": "Kê đơn (Rx)" if is_rx else ("Không kê đơn (OTC)" if rx_val == "OTC" else "Chưa phân loại"),
            "sku_id": b.sku_id,
            "sku_code": b.sku.sku_code if b.sku else "",
            "uom": b.sku.uom if b.sku else "Hộp",
            "price": float(b.sku.base_price) if b.sku and b.sku.base_price else None,
            "batch_id": b.id,
            "batch_number": b.batch_number,
            "manufacture_date": b.manufacture_date.isoformat() if b.manufacture_date else None,
            "expiry_date": b.expiry_date.isoformat(),
            "days_remaining": days_remaining,
            "risk_level": risk,
            "risk_label": risk_label,
            "quantity_on_hand": s.quantity_on_hand,
            "quantity_available": s.quantity_available,
            "quantity_reserved": s.quantity_reserved,
            "location_code": s.location.code if s.location else "Khu tiêu chuẩn",
            "location_name": s.location.name if s.location else None,
            "batch_status": b.status,
            "supplier_name": b.supplier.name if b.supplier else "N/A",
        })

    # Sort items by FEFO (expiry date ascending)
    items.sort(key=lambda x: x["expiry_date"])

    return {
        "warehouse": {
            "id": wh.id,
            "code": wh.code,
            "name": wh.name,
            "address": wh.address,
            "district": wh.district,
            "province": wh.province,
            "phone": wh.phone,
            "is_central": wh.is_central,
            "is_active": wh.is_active,
        },
        "stats": {
            "total_products": len(unique_product_ids),
            "total_batches": len(items),
            "total_on_hand": total_on_hand,
            "total_available": total_available,
            "total_reserved": total_reserved,
            "rx_count": rx_count,
            "otc_count": otc_count,
            "near_expiry_count": near_expiry_count,
            "expired_count": expired_count,
        },
        "stocks": items,
    }


@admin_warehouses_router.get("/{wh_id}/fulfillments")
@warehouses_router.get("/{wh_id}/fulfillments")
def list_warehouse_fulfillments(
    wh_id: int,
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Danh sách các kiện hàng (OrderFulfillment) được phân bổ hoặc xử lý tại kho chỉ định.
    Bao gồm thông tin đơn hàng, khách hàng, sản phẩm và chi tiết phân bổ lô thuốc theo FEFO.
    """
    wh = db.get(Warehouse, wh_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin kho hàng.")

    query = (
        select(OrderFulfillment)
        .join(Order, OrderFulfillment.order_id == Order.id)
        .options(
            selectinload(OrderFulfillment.warehouse),
            selectinload(OrderFulfillment.order),
            selectinload(OrderFulfillment.items).selectinload(FulfillmentItem.order_item),
        )
        .where(OrderFulfillment.warehouse_id == wh_id)
    )

    if status and status.upper() != "ALL":
        query = query.where(OrderFulfillment.status == status.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                OrderFulfillment.fulfillment_code.ilike(term),
                OrderFulfillment.tracking_code.ilike(term),
                Order.order_code.ilike(term),
                Order.customer_name.ilike(term),
                Order.customer_phone.ilike(term),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    fulfillments = db.scalars(
        query.order_by(desc(OrderFulfillment.id)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    all_ff_item_ids = [it.id for ff in fulfillments for it in ff.items]
    alloc_map: dict[int, list[dict[str, Any]]] = {}
    if all_ff_item_ids:
        allocations = db.scalars(
            select(OrderItemBatchAllocation)
            .options(selectinload(OrderItemBatchAllocation.batch))
            .where(OrderItemBatchAllocation.fulfillment_item_id.in_(all_ff_item_ids))
        ).all()
        for a in allocations:
            if a.fulfillment_item_id not in alloc_map:
                alloc_map[a.fulfillment_item_id] = []
            alloc_map[a.fulfillment_item_id].append({
                "id": a.id,
                "batch_id": a.batch_id,
                "batch_number": a.batch.batch_number if a.batch else "",
                "expiry_date": a.batch.expiry_date.isoformat() if (a.batch and a.batch.expiry_date) else "",
                "allocated_quantity": a.allocated_quantity,
                "warehouse_id": a.warehouse_id,
            })

    items = []
    for ff in fulfillments:
        o = ff.order
        ff_items = []
        for it in ff.items:
            ff_items.append({
                "id": it.id,
                "fulfillment_id": it.fulfillment_id,
                "order_item_id": it.order_item_id,
                "product_id": it.order_item.product_id if it.order_item else None,
                "product_name": it.order_item.product_name if it.order_item else "",
                "product_sku": it.order_item.product_sku if it.order_item else "",
                "quantity": it.quantity,
                "allocations": alloc_map.get(it.id, []),
            })

        items.append({
            "id": ff.id,
            "fulfillment_code": ff.fulfillment_code,
            "order_id": ff.order_id,
            "order_code": o.order_code if o else "",
            "customer_name": o.customer_name if o else "",
            "customer_phone": o.customer_phone if o else "",
            "shipping_address": o.shipping_address if o else "",
            "shipping_city": o.shipping_city if o else "",
            "order_status": o.order_status if o else "",
            "payment_method": o.payment_method if o else "",
            "payment_status": o.payment_status if o else "",
            "warehouse_id": ff.warehouse_id,
            "warehouse_code": ff.warehouse.code if ff.warehouse else "",
            "warehouse_name": ff.warehouse.name if ff.warehouse else "",
            "status": ff.status,
            "carrier_name": ff.carrier_name,
            "tracking_code": ff.tracking_code,
            "shipping_fee": float(ff.shipping_fee or 0),
            "created_at": ff.created_at.isoformat() if ff.created_at else None,
            "shipped_at": ff.shipped_at.isoformat() if ff.shipped_at else None,
            "delivered_at": ff.delivered_at.isoformat() if ff.delivered_at else None,
            "items": ff_items,
        })

    return {
        "items": items,
        "total": total,
        "total_count": total,
        "page": page,
        "page_size": page_size,
    }


@admin_warehouses_router.get("/{wh_id}/returns")
@warehouses_router.get("/{wh_id}/returns")
def list_warehouse_returns(
    wh_id: int,
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Danh sách các yêu cầu đổi/trả hàng liên quan đến kho chỉ định
    (sản phẩm xuất từ kho này hoặc hàng hoàn về kho này).
    """
    wh = db.get(Warehouse, wh_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin kho hàng.")

    query = (
        select(ReturnRequest)
        .join(Order, ReturnRequest.order_id == Order.id)
        .outerjoin(ReturnItem, ReturnItem.return_request_id == ReturnRequest.id)
        .outerjoin(OrderItemBatchAllocation, OrderItemBatchAllocation.order_item_id == ReturnItem.order_item_id)
        .outerjoin(OrderFulfillment, OrderFulfillment.order_id == Order.id)
        .where(
            or_(
                OrderItemBatchAllocation.warehouse_id == wh_id,
                OrderFulfillment.warehouse_id == wh_id,
            )
        )
        .distinct()
        .options(
            selectinload(ReturnRequest.order),
            selectinload(ReturnRequest.items),
        )
    )

    if status and status.upper() != "ALL":
        query = query.where(ReturnRequest.status == status.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ReturnRequest.return_code.ilike(term),
                ReturnRequest.customer_name.ilike(term),
                ReturnRequest.customer_phone.ilike(term),
                ReturnRequest.tracking_code.ilike(term),
                Order.order_code.ilike(term),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    returns = db.scalars(
        query.order_by(desc(ReturnRequest.id)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = []
    for r in returns:
        items.append({
            "id": r.id,
            "return_code": r.return_code,
            "order_id": r.order_id,
            "order_code": r.order.order_code if r.order else "",
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
            "customer_email": r.customer_email,
            "request_type": r.request_type,
            "status": r.status,
            "reason_code": r.reason_code,
            "reason_text": r.reason_text,
            "return_method": r.return_method,
            "carrier_name": r.carrier_name,
            "tracking_code": r.tracking_code,
            "warehouse_id": wh_id,
            "warehouse_code": wh.code,
            "requested_at": r.requested_at.isoformat() if r.requested_at else None,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "inspected_at": r.inspected_at.isoformat() if r.inspected_at else None,
            "items": [
                {
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
                }
                for it in r.items
            ],
        })

    return {
        "items": items,
        "total": total,
        "total_count": total,
        "page": page,
        "page_size": page_size,
    }


# ==============================================================================
# BATCHES & FEFO INVENTORY
# ==============================================================================

@router.get("/batches")
def list_batches(
    warehouse_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    near_expiry: bool = False,
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(InventoryBatch)
        .options(
            selectinload(InventoryBatch.sku).selectinload(ProductSku.canonical_product),
            selectinload(InventoryBatch.stocks).selectinload(WarehouseBatchStock.warehouse),
            selectinload(InventoryBatch.stocks).selectinload(WarehouseBatchStock.location),
            selectinload(InventoryBatch.supplier),
        )
        .order_by(InventoryBatch.expiry_date.asc())  # FEFO by default!
    )

    if status_filter:
        query = query.where(InventoryBatch.status == status_filter)

    today = date.today()
    if near_expiry:
        # Near expiry: between today and today + 90 days
        query = query.where(InventoryBatch.expiry_date >= today, InventoryBatch.expiry_date <= today + timedelta(days=90))

    batches = db.scalars(query).all()

    result = []
    for b in batches:
        # Check warehouse filter
        if warehouse_id:
            matching_stock = [s for s in b.stocks if s.warehouse_id == warehouse_id]
            if not matching_stock:
                continue

        days_remaining = (b.expiry_date - today).days

        if days_remaining <= 0 or b.status == "EXPIRED":
            risk = "CRITICAL"
            risk_label = "Đã hết hạn"
        elif days_remaining <= 60:
            risk = "CRITICAL"
            risk_label = "Cận hạn khẩn cấp (<60 ngày)"
        elif days_remaining <= 180:
            risk = "WARNING"
            risk_label = "Cận hạn (2-6 tháng)"
        else:
            risk = "SAFE"
            risk_label = "An toàn (>6 tháng)"

        prod = b.sku.canonical_product if b.sku else None
        prod_name = prod.canonical_name if prod else "N/A"
        reg_num = prod.registration_number if prod else None

        if search and search.strip():
            term = search.strip().lower()
            if term not in b.batch_number.lower() and term not in prod_name.lower():
                continue

        total_on_hand = sum(s.quantity_on_hand for s in b.stocks)
        total_available = sum(s.quantity_available for s in b.stocks)

        stock_breakdown = [
            {
                "warehouse_id": s.warehouse_id,
                "warehouse_name": s.warehouse.name if s.warehouse else f"Kho #{s.warehouse_id}",
                "warehouse_code": s.warehouse.code if s.warehouse else "",
                "location_code": s.location.code if s.location else None,
                "quantity_on_hand": s.quantity_on_hand,
                "quantity_reserved": s.quantity_reserved,
                "quantity_available": s.quantity_available,
            }
            for s in b.stocks
        ]

        result.append({
            "id": b.id,
            "batch_number": b.batch_number,
            "sku_id": b.sku_id,
            "sku_code": b.sku.sku_code if b.sku else "",
            "uom": b.sku.uom if b.sku else "Hộp",
            "product_id": prod.id if prod else None,
            "product_name": prod_name,
            "registration_number": reg_num,
            "manufacture_date": b.manufacture_date.isoformat() if b.manufacture_date else None,
            "expiry_date": b.expiry_date.isoformat(),
            "days_remaining": days_remaining,
            "risk_level": risk,
            "risk_label": risk_label,
            "status": b.status,
            "certificate_url": b.certificate_url,
            "supplier_name": b.supplier.name if b.supplier else "N/A",
            "initial_quantity": b.initial_quantity,
            "total_on_hand": total_on_hand,
            "total_available": total_available,
            "stocks": stock_breakdown,
        })

    return result


@router.patch("/batches/{batch_id}/status")
def update_batch_status(
    batch_id: int,
    payload: BatchStatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    batch = db.get(InventoryBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin lô hàng")

    old_status = batch.status
    new_status = payload.status
    batch.status = new_status

    # If quarantined, recalled or expired -> zero out available stock immediately
    stocks = db.scalars(select(WarehouseBatchStock).where(WarehouseBatchStock.batch_id == batch.id)).all()
    for s in stocks:
        if new_status in ["QUARANTINED", "RECALLED", "EXPIRED"]:
            s.quantity_available = 0
        elif new_status == "ACTIVE":
            s.quantity_available = max(0, s.quantity_on_hand - s.quantity_reserved)

    # Record Movement if quarantined or recalled
    if new_status in ["QUARANTINED", "RECALLED"]:
        for s in stocks:
            db.add(StockMovement(
                movement_code=f"MOV-STATUS-{batch.id}-{int(datetime.now().timestamp())}",
                movement_type="DISPOSAL" if new_status == "RECALLED" else "ADJUST_DEC",
                warehouse_id=s.warehouse_id,
                batch_id=batch.id,
                quantity=s.quantity_on_hand,
                balance_after=s.quantity_on_hand,
                reference_type="BATCH_STATUS_CHANGE",
                reference_id=str(batch.id),
                created_by=user.id,
                note=f"Chuyển trạng thái lô sang {new_status}. Lý do: {payload.reason or 'Chỉ đạo quản lý kho'}",
            ))

    db.commit()
    write_audit(
        db,
        "UPDATE_BATCH_STATUS",
        "InventoryBatch",
        batch.id,
        user,
        request,
        before={"status": old_status},
        after={"status": new_status, "reason": payload.reason},
    )
    db.commit()

    return {"message": f"Cập nhật trạng thái lô {batch.batch_number} sang {new_status} thành công"}


# ==============================================================================
# STOCK RECEIPTS (NHẬP KHO GSP)
# ==============================================================================

@router.get("/receipts")
def list_stock_receipts(
    warehouse_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(StockReceipt)
        .options(
            selectinload(StockReceipt.warehouse),
            selectinload(StockReceipt.supplier),
            selectinload(StockReceipt.items).selectinload(StockReceiptItem.sku),
        )
        .order_by(StockReceipt.id.desc())
        .limit(limit)
    )

    if warehouse_id:
        query = query.where(StockReceipt.warehouse_id == warehouse_id)

    receipts = db.scalars(query).all()

    return [
        {
            "id": r.id,
            "receipt_code": r.receipt_code,
            "warehouse_id": r.warehouse_id,
            "warehouse_name": r.warehouse.name if r.warehouse else "",
            "supplier_id": r.supplier_id,
            "supplier_name": r.supplier.name if r.supplier else "",
            "status": r.status,
            "total_amount": float(r.total_amount),
            "received_date": r.received_date.isoformat() if r.received_date else None,
            "note": r.note,
            "items_count": len(r.items),
            "items": [
                {
                    "id": it.id,
                    "sku_id": it.sku_id,
                    "sku_code": it.sku.sku_code if it.sku else "",
                    "batch_number": it.batch_number,
                    "manufacture_date": it.manufacture_date.isoformat() if it.manufacture_date else None,
                    "expiry_date": it.expiry_date.isoformat(),
                    "quantity": it.quantity,
                    "purchase_unit_price": float(it.purchase_unit_price),
                    "line_total": float(it.line_total),
                }
                for it in r.items
            ],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in receipts
    ]


@router.post("/receipts", status_code=status.HTTP_201_CREATED)
def create_stock_receipt(
    payload: ReceiptCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    wh = db.get(Warehouse, payload.warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin kho nhập")

    supplier = db.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhà cung cấp")

    receipt_code = f"PNK-{wh.code}-{datetime.now().strftime('%y%m%d%H%M%S')}"
    total_amount = sum(it.quantity * it.purchase_unit_price for it in payload.items)

    receipt = StockReceipt(
        receipt_code=receipt_code,
        warehouse_id=wh.id,
        supplier_id=supplier.id,
        status="CONFIRMED",
        received_date=utcnow(),
        total_amount=total_amount,
        note=payload.note,
        created_by=user.id,
        confirmed_by=user.id,
    )
    db.add(receipt)
    db.flush()

    for item_data in payload.items:
        sku = db.get(ProductSku, item_data.sku_id)
        if not sku:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy SKU #{item_data.sku_id}")

        line_total = item_data.quantity * item_data.purchase_unit_price

        # Find or create batch
        batch = db.scalar(
            select(InventoryBatch).where(
                InventoryBatch.sku_id == sku.id,
                InventoryBatch.batch_number == item_data.batch_number.strip().upper(),
            )
        )
        if not batch:
            batch = InventoryBatch(
                sku_id=sku.id,
                batch_number=item_data.batch_number.strip().upper(),
                manufacture_date=item_data.manufacture_date,
                expiry_date=item_data.expiry_date,
                supplier_id=supplier.id,
                initial_quantity=item_data.quantity,
                status="ACTIVE",
                certificate_url=None,
            )
            db.add(batch)
            db.flush()
        else:
            batch.initial_quantity += item_data.quantity

        receipt_item = StockReceiptItem(
            receipt_id=receipt.id,
            sku_id=sku.id,
            batch_number=batch.batch_number,
            manufacture_date=item_data.manufacture_date,
            expiry_date=item_data.expiry_date,
            quantity=item_data.quantity,
            purchase_unit_price=item_data.purchase_unit_price,
            line_total=line_total,
            storage_location_id=item_data.storage_location_id,
            batch_id=batch.id,
        )
        db.add(receipt_item)

        # Update warehouse batch stock
        stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh.id,
                WarehouseBatchStock.batch_id == batch.id,
            )
        )
        if not stock:
            stock = WarehouseBatchStock(
                warehouse_id=wh.id,
                batch_id=batch.id,
                location_id=item_data.storage_location_id,
                quantity_on_hand=item_data.quantity,
                quantity_reserved=0,
                quantity_available=item_data.quantity,
            )
            db.add(stock)
        else:
            stock.quantity_on_hand += item_data.quantity
            stock.quantity_available += item_data.quantity

        db.flush()

        # Record Stock Movement
        db.add(StockMovement(
            movement_code=f"MOV-REC-{receipt.id}-{batch.id}-{int(datetime.now().timestamp())}",
            movement_type="RECEIPT",
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity=item_data.quantity,
            balance_after=stock.quantity_on_hand,
            reference_type="STOCK_RECEIPT",
            reference_id=receipt.receipt_code,
            created_by=user.id,
            note=f"Nhập kho theo phiếu {receipt.receipt_code} từ {supplier.name}",
        ))

    db.commit()
    write_audit(db, "CREATE_STOCK_RECEIPT", "StockReceipt", receipt.id, user, request, after={"receipt_code": receipt.receipt_code, "total_amount": float(total_amount)})
    db.commit()

    return {"message": "Nhập kho thành công", "receipt_code": receipt.receipt_code, "id": receipt.id}


# ==============================================================================
# STOCK TRANSFERS (ĐIỀU CHUYỂN KHO)
# ==============================================================================

@router.get("/transfers")
def list_stock_transfers(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    transfers = db.scalars(
        select(StockTransfer)
        .options(
            selectinload(StockTransfer.from_warehouse),
            selectinload(StockTransfer.to_warehouse),
            selectinload(StockTransfer.items).selectinload(StockTransferItem.batch).selectinload(InventoryBatch.sku),
        )
        .order_by(StockTransfer.id.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": t.id,
            "transfer_code": t.transfer_code,
            "from_warehouse_id": t.from_warehouse_id,
            "from_warehouse_name": t.from_warehouse.name if t.from_warehouse else "",
            "to_warehouse_id": t.to_warehouse_id,
            "to_warehouse_name": t.to_warehouse.name if t.to_warehouse else "",
            "status": t.status,
            "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "shipped_at": t.shipped_at.isoformat() if t.shipped_at else None,
            "received_at": t.received_at.isoformat() if t.received_at else None,
            "items_count": len(t.items),
            "items": [
                {
                    "id": it.id,
                    "batch_id": it.batch_id,
                    "batch_number": it.batch.batch_number if it.batch else "",
                    "sku_code": it.batch.sku.sku_code if (it.batch and it.batch.sku) else "",
                    "quantity": it.quantity,
                    "received_quantity": it.received_quantity,
                }
                for it in t.items
            ],
        }
        for t in transfers
    ]


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
def create_stock_transfer(
    payload: TransferCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise HTTPException(status_code=400, detail="Kho xuất và kho nhập không được trùng nhau")

    wh_from = db.get(Warehouse, payload.from_warehouse_id)
    wh_to = db.get(Warehouse, payload.to_warehouse_id)
    if not wh_from or not wh_to:
        raise HTTPException(status_code=404, detail="Không tìm thấy kho xuất hoặc kho nhập")

    # Verify inventory at source warehouse
    for it in payload.items:
        stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh_from.id,
                WarehouseBatchStock.batch_id == it.batch_id,
            )
        )
        if not stock or stock.quantity_available < it.quantity:
            batch = db.get(InventoryBatch, it.batch_id)
            batch_num = batch.batch_number if batch else f"#{it.batch_id}"
            avail = stock.quantity_available if stock else 0
            raise HTTPException(
                status_code=400,
                detail=f"Lô {batch_num} tại {wh_from.name} chỉ còn khả dụng {avail}, không đủ để điều chuyển {it.quantity}",
            )

    transfer_code = f"DCK-{wh_from.code}-{wh_to.code}-{datetime.now().strftime('%y%m%d%H%M%S')}"
    transfer = StockTransfer(
        transfer_code=transfer_code,
        from_warehouse_id=wh_from.id,
        to_warehouse_id=wh_to.id,
        status="COMPLETED",  # Direct transfer for internal multi-warehouse
        note=payload.note,
        created_by=user.id,
        shipped_at=utcnow(),
        received_at=utcnow(),
    )
    db.add(transfer)
    db.flush()

    for it in payload.items:
        db.add(StockTransferItem(
            transfer_id=transfer.id,
            batch_id=it.batch_id,
            quantity=it.quantity,
            received_quantity=it.quantity,
        ))

        # 1. Deduct from source warehouse
        src_stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh_from.id,
                WarehouseBatchStock.batch_id == it.batch_id,
            )
        )
        src_stock.quantity_on_hand -= it.quantity
        src_stock.quantity_available -= it.quantity

        db.add(StockMovement(
            movement_code=f"MOV-TF-OUT-{transfer.id}-{it.batch_id}",
            movement_type="TRANSFER_OUT",
            warehouse_id=wh_from.id,
            batch_id=it.batch_id,
            quantity=-it.quantity,
            balance_after=src_stock.quantity_on_hand,
            reference_type="STOCK_TRANSFER",
            reference_id=transfer.transfer_code,
            created_by=user.id,
            note=f"Xuất điều chuyển sang {wh_to.name} theo lệnh {transfer.transfer_code}",
        ))

        # 2. Add to destination warehouse
        dest_stock = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh_to.id,
                WarehouseBatchStock.batch_id == it.batch_id,
            )
        )
        if not dest_stock:
            dest_stock = WarehouseBatchStock(
                warehouse_id=wh_to.id,
                batch_id=it.batch_id,
                quantity_on_hand=it.quantity,
                quantity_reserved=0,
                quantity_available=it.quantity,
            )
            db.add(dest_stock)
        else:
            dest_stock.quantity_on_hand += it.quantity
            dest_stock.quantity_available += it.quantity

        db.flush()

        db.add(StockMovement(
            movement_code=f"MOV-TF-IN-{transfer.id}-{it.batch_id}",
            movement_type="TRANSFER_IN",
            warehouse_id=wh_to.id,
            batch_id=it.batch_id,
            quantity=it.quantity,
            balance_after=dest_stock.quantity_on_hand,
            reference_type="STOCK_TRANSFER",
            reference_id=transfer.transfer_code,
            created_by=user.id,
            note=f"Nhập điều chuyển từ {wh_from.name} theo lệnh {transfer.transfer_code}",
        ))

    db.commit()
    write_audit(db, "CREATE_STOCK_TRANSFER", "StockTransfer", transfer.id, user, request, after={"transfer_code": transfer.transfer_code})
    db.commit()

    return {"message": "Điều chuyển kho thành công", "transfer_code": transfer.transfer_code, "id": transfer.id}


# ==============================================================================
# STOCK MOVEMENTS (THẺ KHO) & SUPPLIERS
# ==============================================================================

@router.get("/movements")
def list_stock_movements(
    warehouse_id: int | None = None,
    batch_id: int | None = None,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(StockMovement)
        .options(
            selectinload(StockMovement.warehouse),
            selectinload(StockMovement.batch).selectinload(InventoryBatch.sku),
        )
        .order_by(StockMovement.id.desc())
        .limit(limit)
    )

    if warehouse_id:
        query = query.where(StockMovement.warehouse_id == warehouse_id)
    if batch_id:
        query = query.where(StockMovement.batch_id == batch_id)

    movements = db.scalars(query).all()

    return [
        {
            "id": m.id,
            "movement_code": m.movement_code,
            "movement_type": m.movement_type,
            "warehouse_id": m.warehouse_id,
            "warehouse_name": m.warehouse.name if m.warehouse else "",
            "batch_id": m.batch_id,
            "batch_number": m.batch.batch_number if m.batch else "",
            "sku_code": m.batch.sku.sku_code if (m.batch and m.batch.sku) else "",
            "quantity": m.quantity,
            "balance_after": m.balance_after,
            "reference_type": m.reference_type,
            "reference_id": m.reference_id,
            "note": m.note,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in movements
    ]


@router.get("/suppliers")
def list_suppliers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suppliers = db.scalars(select(Supplier).where(Supplier.is_active == True).order_by(Supplier.name.asc())).all()
    return [
        {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "tax_code": s.tax_code,
            "phone": s.phone,
            "email": s.email,
            "address": s.address,
            "gsp_license_number": s.gsp_license_number,
        }
        for s in suppliers
    ]


# ==============================================================================
# ADMINISTRATIVE UNITS (ĐỊA GIỚI HÀNH CHÍNH)
# ==============================================================================

@admin_units_router.get("")
def list_administrative_units(
    level: str | None = None,
    parent_code: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(AdministrativeUnit).order_by(AdministrativeUnit.name.asc())
    if level:
        query = query.where(AdministrativeUnit.level == level.upper())
    if parent_code:
        query = query.where(AdministrativeUnit.parent_code == parent_code)

    units = db.scalars(query).all()
    return [
        {
            "code": u.code,
            "name": u.name,
            "parent_code": u.parent_code,
            "level": u.level,
            "full_name": u.full_name,
        }
        for u in units
    ]
