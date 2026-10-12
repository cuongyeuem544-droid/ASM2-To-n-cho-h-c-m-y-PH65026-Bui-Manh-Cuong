import datetime
import random
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_optional_current_user, require_roles
from app.db.session import get_db
from app.services.audit import write_audit
from app.services.pricing_service import PricingService
from app.models import (
    AdministrativeUnit,
    CanonicalProduct,
    FulfillmentItem,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderItemBatchAllocation,
    PaymentTransaction,
    PriceObservation,
    ProductSku,
    User,
)
from app.models.enums import PublishStatus, RxOtcStatus, UserRole
from app.services.administrative_service import AdministrativeDataService
from app.services.alert_notifier import dispatch_alert
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.geo_service import GeoService

router = APIRouter(tags=["Đơn Hàng & Mua Sắm"])
store_order_router = APIRouter(prefix="/store/orders", tags=["Storefront Khách Hàng - Đơn Hàng"])
admin_order_router = APIRouter(prefix="/admin/orders", tags=["Quản Trị Đơn Hàng"])


def _serialize_fulfillments(db: Session, order_id: int) -> list[dict[str, Any]]:
    ffs = db.scalars(
        select(OrderFulfillment)
        .options(
            selectinload(OrderFulfillment.warehouse),
            selectinload(OrderFulfillment.items).selectinload(FulfillmentItem.order_item),
        )
        .where(OrderFulfillment.order_id == order_id)
        .order_by(OrderFulfillment.id.asc())
    ).all()

    result = []
    for f in ffs:
        ff_item_ids = [it.id for it in f.items]
        alloc_map: dict[int, list[dict[str, Any]]] = {}

        if ff_item_ids:
            allocations = db.scalars(
                select(OrderItemBatchAllocation)
                .options(selectinload(OrderItemBatchAllocation.batch))
                .where(OrderItemBatchAllocation.fulfillment_item_id.in_(ff_item_ids))
            ).all()

            for a in allocations:
                if a.fulfillment_item_id not in alloc_map:
                    alloc_map[a.fulfillment_item_id] = []
                alloc_map[a.fulfillment_item_id].append({
                    "batch_id": a.batch_id,
                    "batch_number": a.batch.batch_number if a.batch else "",
                    "expiry_date": a.batch.expiry_date.isoformat() if (a.batch and a.batch.expiry_date) else "",
                    "allocated_quantity": a.allocated_quantity,
                })

        items_list = []
        for it in f.items:
            items_list.append({
                "fulfillment_item_id": it.id,
                "order_item_id": it.order_item_id,
                "product_name": it.order_item.product_name if it.order_item else "",
                "quantity": it.quantity,
                "batches": alloc_map.get(it.id, []),
            })

        result.append({
            "id": f.id,
            "fulfillment_code": f.fulfillment_code,
            "warehouse_id": f.warehouse_id,
            "warehouse_code": f.warehouse.code if f.warehouse else "",
            "warehouse_name": f.warehouse.name if f.warehouse else "",
            "status": f.status,
            "carrier_name": f.carrier_name,
            "tracking_code": f.tracking_code,
            "shipping_fee": float(f.shipping_fee),
            "shipped_at": f.shipped_at.isoformat() if f.shipped_at else None,
            "delivered_at": f.delivered_at.isoformat() if f.delivered_at else None,
            "items": items_list,
        })
    return result


# --- Schemas ---
class CheckoutItem(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=100)
    sku_id: Optional[int] = None
    client_unit_price: Optional[float] = None


class CheckoutRequest(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=255)
    customer_phone: str = Field(..., min_length=5, max_length=25)
    customer_email: Optional[str] = None
    shipping_address: str = Field(..., min_length=2, max_length=500)
    shipping_city: Optional[str] = "Toàn quốc"
    payment_method: str = "COD"  # COD | BANK_TRANSFER | MOMO
    note: Optional[str] = None
    items: List[CheckoutItem] = Field(..., min_length=1)
    idempotency_key: Optional[str] = None
    voucher_code: Optional[str] = None

    # Cấu trúc địa chỉ giao hàng xác minh (Mô hình 2 cấp 2025 & Legacy)
    fulfillment_type: Optional[str] = "DELIVERY"  # DELIVERY | STORE_PICKUP
    province_code: Optional[str] = None
    commune_code: Optional[str] = None
    commune_type: Optional[str] = None  # ward | commune | special_zone
    address_line: Optional[str] = None
    formatted_address: Optional[str] = None
    place_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_verified: Optional[bool] = False

    # Legacy fields
    district_code: Optional[str] = None
    ward_code: Optional[str] = None
    store_id: Optional[int] = None


class CartItemValidate(BaseModel):
    product_id: int
    sku_id: Optional[int] = None
    quantity: int = Field(default=1, ge=1, le=100)
    client_price: Optional[float] = None


class CartValidateRequest(BaseModel):
    items: List[CartItemValidate]


class CartCalculateRequest(BaseModel):
    items: List[CartItemValidate]
    voucher_code: Optional[str] = None
    fulfillment_type: Optional[str] = "DELIVERY"
    province_code: Optional[str] = None
    district_code: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class UpdateOrderStatusRequest(BaseModel):
    order_status: str  # PENDING | CONFIRMED | PROCESSING | SHIPPING | COMPLETED | CANCELLED
    payment_status: Optional[str] = None


def generate_order_code() -> str:
    now_str = datetime.datetime.now().strftime("%y%m%d")
    rand_suffix = random.randint(1000, 9999)
    return f"PT-{now_str}-{rand_suffix}"


# ==========================================
# 1. STOREFRONT CHECKOUT & TRA CỨU ĐƠN HÀNG
# ==========================================
@store_order_router.post("/cart/validate")
def validate_cart(payload: CartValidateRequest, db: Session = Depends(get_db)):
    """
    Kiểm tra và xác thực tính hợp lệ của toàn bộ giỏ hàng trước khi đặt hàng:
    - Giá niêm yết chính thức từ máy chủ.
    - Cảnh báo biến động giá nếu client giữ giá cũ.
    - Tồn kho khả dụng thực tế theo FEFO.
    - Tính hợp lệ mở bán theo Product Eligibility Engine.
    """
    from app.services.product_eligibility_service import ProductEligibilityService

    product_ids = [it.product_id for it in payload.items]
    products = db.scalars(
        select(CanonicalProduct).where(CanonicalProduct.id.in_(product_ids))
    ).all()
    products_map = {p.id: p for p in products}

    results = []
    total_valid_amount = Decimal("0.0")
    all_valid = True

    for it in payload.items:
        prod = products_map.get(it.product_id)
        if not prod or prod.publish_status != PublishStatus.PUBLISHED:
            results.append({
                "product_id": it.product_id,
                "sku_id": it.sku_id,
                "product_name": prod.canonical_name if prod else f"Sản phẩm #{it.product_id}",
                "uom": "Hộp",
                "server_price": 0.0,
                "client_price": it.client_price,
                "price_changed": False,
                "available_stock": 0,
                "is_eligible": False,
                "rejection_reason": "Sản phẩm không tồn tại hoặc đã ngừng kinh doanh",
                "can_checkout": False,
            })
            all_valid = False
            continue

        eligibility = ProductEligibilityService.evaluate_product_eligibility(prod, db)
        sku_obj = None
        if it.sku_id:
            sku_obj = db.get(ProductSku, it.sku_id)
        if not sku_obj:
            sku_obj = db.query(ProductSku).filter(
                ProductSku.canonical_product_id == prod.id,
                ProductSku.is_active == True,
            ).order_by(ProductSku.is_default.desc()).first()

        server_price = Decimal("0.0")
        if sku_obj and sku_obj.base_price and sku_obj.base_price > 0:
            server_price = Decimal(str(sku_obj.base_price))
        else:
            po = db.query(PriceObservation.observed_price).filter(
                PriceObservation.product_id == prod.id
            ).first()
            if po and po[0]:
                server_price = Decimal(str(po[0]))

        uom = sku_obj.uom if sku_obj else (prod.package_description or "Hộp")
        available_stock = eligibility.available_stock

        price_changed = False
        if it.client_price is not None and server_price > 0:
            price_changed = abs(float(server_price) - it.client_price) > 0.01

        can_checkout = (
            eligibility.can_add_to_cart
            and server_price > 0
            and available_stock >= it.quantity
        )

        rejection = None
        if not eligibility.can_add_to_cart:
            rejection = eligibility.primary_reason
        elif server_price <= 0:
            rejection = "Sản phẩm chưa có giá niêm yết thương mại"
        elif available_stock < it.quantity:
            rejection = f"Chỉ còn {available_stock} {uom} trong kho (bạn chọn {it.quantity})"

        if can_checkout:
            total_valid_amount += server_price * it.quantity
        else:
            all_valid = False

        results.append({
            "product_id": it.product_id,
            "sku_id": sku_obj.id if sku_obj else it.sku_id,
            "product_name": prod.canonical_name,
            "uom": uom,
            "server_price": float(server_price),
            "client_price": it.client_price,
            "price_changed": price_changed,
            "available_stock": available_stock,
            "is_eligible": eligibility.can_add_to_cart,
            "rejection_reason": rejection,
            "can_checkout": can_checkout,
        })

    return {
        "all_valid": all_valid,
        "total_valid_amount": float(total_valid_amount),
        "items": results,
    }


@store_order_router.post("/cart/calculate")
def calculate_cart_quote(payload: CartCalculateRequest, db: Session = Depends(get_db)):
    """
    Bảng tính tiền chính thức từ máy chủ (Server-side Pricing & Voucher Engine):
    - Tải giá niêm yết từ DB.
    - Kiểm tra tồn kho khả dụng FEFO.
    - Tính cước vận chuyển chuẩn xác (miễn cước >= 300.000đ).
    - Thẩm định điều kiện voucher (thời hạn, lượt dùng, giá trị tối thiểu, chiết khấu).
    - Trả về subtotal, shipping_fee, discount_amount, grand_total trước khi xác nhận đặt hàng.
    """
    items_data = [
        {
            "product_id": it.product_id,
            "sku_id": it.sku_id,
            "quantity": it.quantity,
        }
        for it in payload.items
    ]
    res = PricingService.calculate_cart_pricing(
        db=db,
        items=items_data,
        voucher_code=payload.voucher_code,
        fulfillment_type=payload.fulfillment_type or "DELIVERY",
        province_code=payload.province_code,
        district_code=payload.district_code,
        lat=payload.lat,
        lng=payload.lng,
    )
    # Remove internal _voucher_obj before returning JSON
    res.pop("_voucher_obj", None)
    return res


@store_order_router.post("/checkout")
def checkout_order(
    payload: CheckoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Tạo đơn hàng mới từ Storefront Web Khách Hàng.
    Tính giá 100% tại máy chủ (Server-side Pricing), loại bỏ hoàn toàn thuốc kê đơn Rx và chặn can thiệp giá.
    Xác minh nghiêm ngặt địa chỉ giao hàng và tọa độ bản đồ.
    Hỗ trợ Idempotency Key để chống tạo đơn trùng lặp khi người mua bấm 2 lần hoặc mạng retry.
    """
    # 0. Chống tạo đơn trùng (Idempotency Replay)
    if payload.idempotency_key and payload.idempotency_key.strip():
        clean_idem = payload.idempotency_key.strip()
        existing_order = db.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.idempotency_key == clean_idem)
        )
        if existing_order:
            return {
                "status": "SUCCESS",
                "message": f"Đơn hàng của bạn đã được ghi nhận thành công trước đó (Mã đơn: {existing_order.order_code}).",
                "order_code": existing_order.order_code,
                "total_amount": float(existing_order.total_amount),
                "order_status": existing_order.order_status,
                "created_at": existing_order.created_at.isoformat() if existing_order.created_at else None,
                "fulfillments": _serialize_fulfillments(db, existing_order.id),
                "is_idempotent_replay": True,
            }

    name = payload.customer_name.strip()
    phone = payload.customer_phone.strip()
    address = payload.shipping_address.strip()

    if not name or not phone or not address:
        raise HTTPException(status_code=400, detail="Vui lòng điền đầy đủ họ tên, số điện thoại và địa chỉ giao hàng.")

    # Xác thực địa chỉ giao hàng đối với hình thức Giao Tận Nơi
    if (payload.fulfillment_type or "DELIVERY").upper() == "DELIVERY":
        if not payload.is_verified:
            raise HTTPException(
                status_code=400,
                detail="Địa chỉ giao hàng chưa được xác minh vị trí. Vui lòng bấm 'Xác nhận địa chỉ này' trước khi đặt hàng.",
            )

        if payload.lat is None or payload.lng is None:
            raise HTTPException(
                status_code=400,
                detail="Thiếu tọa độ định vị GPS giao hàng. Vui lòng chọn và xác nhận vị trí trên bản đồ.",
            )

        p_code = payload.province_code
        c_code = payload.commune_code or payload.ward_code

        if not p_code or not c_code:
            raise HTTPException(
                status_code=400,
                detail="Vui lòng chọn đầy đủ 2 cấp hành chính hiện hành: Tỉnh/Thành phố và Xã/Phường/Đặc khu.",
            )

        # 1. Kiểm tra tính khớp giữa Tỉnh/Thành và tọa độ GPS
        is_coord_valid, coord_err = GeoService.validate_province_coordinates(
            province_code=p_code,
            lat=payload.lat,
            lng=payload.lng,
        )
        if not is_coord_valid:
            raise HTTPException(status_code=400, detail=coord_err)

        # 2. Kiểm tra tính hợp lệ của cấp hành chính 2 cấp theo dataset 2025
        is_valid_sel, sel_err = AdministrativeDataService.validate_selection(p_code, c_code)
        if not is_valid_sel:
            prov_db = db.scalar(
                select(AdministrativeUnit).where(
                    AdministrativeUnit.code == p_code,
                    AdministrativeUnit.level == "PROVINCE",
                )
            )
            comm_db = db.scalar(
                select(AdministrativeUnit).where(
                    AdministrativeUnit.code == c_code,
                    AdministrativeUnit.parent_code == p_code,
                )
            )
            if not prov_db or not comm_db:
                raise HTTPException(
                    status_code=400,
                    detail=sel_err or "Cấp hành chính không hợp lệ hoặc không thuộc Tỉnh/Thành phố đã chọn.",
                )

    # Tính giá toàn diện và kiểm tra voucher tại máy chủ (Server-side Pricing & Voucher Engine)
    pricing_payload = [
        {
            "product_id": it.product_id,
            "sku_id": it.sku_id,
            "quantity": it.quantity,
        }
        for it in payload.items
    ]
    pricing = PricingService.calculate_cart_pricing(
        db=db,
        items=pricing_payload,
        voucher_code=payload.voucher_code,
        fulfillment_type=payload.fulfillment_type or "DELIVERY",
        province_code=payload.province_code,
        district_code=payload.district_code,
        lat=payload.lat,
        lng=payload.lng,
    )

    if not pricing["all_eligible"]:
        for cit in pricing["items"]:
            if not cit["can_checkout"]:
                raise HTTPException(status_code=400, detail=f"Sản phẩm '{cit['product_name']}': {cit['rejection_reason']}")
        raise HTTPException(status_code=400, detail="Một số sản phẩm không đủ điều kiện mở bán hoặc không đủ tồn kho.")

    if payload.voucher_code and payload.voucher_code.strip():
        if not pricing.get("voucher") or not pricing["voucher"]["is_valid"]:
            v_msg = pricing["voucher"]["message"] if pricing.get("voucher") else "Mã giảm giá không hợp lệ."
            raise HTTPException(status_code=400, detail=v_msg)

    order_items_to_add = []
    for cit in pricing["items"]:
        order_items_to_add.append(
            OrderItem(
                product_id=cit["product_id"],
                product_name=cit["product_name"],
                product_sku=cit["sku_code"] or cit["uom"],
                price=Decimal(str(cit["unit_price"])),
                quantity=cit["quantity"],
                subtotal=Decimal(str(cit["subtotal"])),
            )
        )

    comm_code_val = payload.commune_code or payload.ward_code
    comm_info = AdministrativeDataService.get_commune_by_code(comm_code_val) if payload.province_code and comm_code_val else None
    prov_info = AdministrativeDataService.get_province_by_code(payload.province_code) if payload.province_code else None

    initial_order_status = "PENDING"
    order_code = generate_order_code()

    voucher_obj = pricing.get("_voucher_obj")
    if voucher_obj:
        voucher_obj.used_count += 1

    order = Order(
        order_code=order_code,
        user_id=current_user.id if current_user else None,
        idempotency_key=payload.idempotency_key.strip() if payload.idempotency_key else None,
        customer_name=name,
        customer_phone=phone,
        customer_email=payload.customer_email.strip() if payload.customer_email else None,
        shipping_address=address,
        shipping_city=prov_info["fullName"] if prov_info else (payload.shipping_city or "Toàn quốc"),
        province_code=payload.province_code,
        district_code=payload.district_code or (comm_info.get("legacyDistrictName") if comm_info else None),
        ward_code=comm_code_val,
        lat=payload.lat,
        lng=payload.lng,
        is_verified=bool(payload.is_verified),
        province_code_current=payload.province_code,
        commune_code_current=comm_code_val,
        commune_type=payload.commune_type or (comm_info.get("type") if comm_info else None),
        formatted_address_current=payload.formatted_address or address,
        legacy_province=prov_info["fullName"] if prov_info else None,
        legacy_district=payload.district_code or (comm_info.get("legacyDistrictName") if comm_info else None),
        legacy_ward=comm_info["fullName"] if comm_info else None,
        migration_status="MIGRATED_2025",
        geocode_provider="nominatim",
        place_id=payload.place_id or f"geo_{payload.province_code}_{comm_code_val}",
        verified_at=datetime.datetime.utcnow() if payload.is_verified else None,
        payment_method=payload.payment_method.upper(),
        payment_status="PENDING",
        order_status=initial_order_status,
        total_amount=Decimal(str(pricing["grand_total"])),
        shipping_fee=Decimal(str(pricing["shipping_fee"])),
        discount_amount=Decimal(str(pricing["discount_amount"])),
        voucher_code=pricing["voucher"]["code"] if pricing.get("voucher") and pricing["voucher"]["is_valid"] else None,
        promotion_id=voucher_obj.id if voucher_obj else None,
        discount_breakdown=pricing["voucher"].get("discount_breakdown") if pricing.get("voucher") else None,
        note=payload.note.strip() if payload.note else None,
        items=order_items_to_add,
    )
    db.add(order)
    db.flush()

    # Điều phối kho và phân bổ lô theo FEFO
    FulfillmentRoutingService.route_and_allocate_order(
        db=db,
        order=order,
        items=order_items_to_add,
        shipping_city=payload.shipping_city,
        shipping_address=payload.shipping_address,
    )

    # Ghi nhận giao dịch thanh toán khởi tạo trong PaymentTransaction
    init_provider = "COD" if order.payment_method == "COD" else ("VIETQR" if order.payment_method in ["BANK_TRANSFER", "VIETQR"] else "MOMO")
    initial_tx = PaymentTransaction(
        order_id=order.id,
        transaction_code=f"TXN-{init_provider}-{order.order_code}-{int(datetime.datetime.now().timestamp()) % 100000}",
        provider=init_provider,
        amount=order.total_amount,
        currency="VND",
        status="PENDING",
    )
    db.add(initial_tx)

    # Ghi audit log
    write_audit(
        db,
        action="CREATE_ORDER",
        entity_type="Order",
        entity_id=order.id,
        user=current_user,
        request=request,
        before=None,
        after={
            "order_code": order.order_code,
            "total_amount": float(order.total_amount),
            "shipping_fee": float(order.shipping_fee),
            "discount_amount": float(order.discount_amount),
            "voucher_code": order.voucher_code,
            "items_count": len(order_items_to_add),
        },
    )

    db.commit()
    db.refresh(order)

    # Gửi email xác nhận đơn hàng thật (Gmail SMTP & lưu vết EmailOutbox)
    if order.customer_email:
        try:
            from app.services.email_service import EmailService
            EmailService.queue_and_send_order_confirmation(db=db, order=order, send_immediately=True)
        except Exception as e:
            # Ghi nhận log cảnh báo, không làm crash luồng tạo đơn
            import logging
            logging.getLogger(__name__).warning(f"[ORDER] Không thể gửi email xác nhận cho đơn '{order.order_code}': {e}")

    # Gửi cảnh báo tức thì tới Telegram Quản trị viên
    items_summary = ", ".join([f"{it.product_name} (x{it.quantity})" for it in order_items_to_add[:3]])
    if len(order_items_to_add) > 3:
        items_summary += f" và {len(order_items_to_add) - 3} sản phẩm khác"

    dispatch_alert(
        title="ĐƠN HÀNG MỚI TỪ STOREFRONT",
        message=(
            f"Mã đơn: <b>{order.order_code}</b>\n"
            f"Khách hàng: <b>{order.customer_name}</b> - SĐT: <code>{order.customer_phone}</code>\n"
            f"Địa chỉ: {order.shipping_address}\n"
            f"Tổng tiền: <b>{int(order.total_amount):,} đ</b>\n"
            f"Sản phẩm: {items_summary}"
        ),
        severity="INFO",
        alert_type="NEW_ORDER",
        details={
            "Mã đơn hàng": order.order_code,
            "Thanh toán": order.payment_method,
            "Tổng thanh toán": f"{int(order.total_amount):,} VND",
        },
    )

    return {
        "status": "SUCCESS",
        "message": f"Đặt hàng thành công! Mã đơn của bạn là {order.order_code}.",
        "order_code": order.order_code,
        "total_amount": float(order.total_amount),
        "order_status": order.order_status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "fulfillments": _serialize_fulfillments(db, order.id),
    }


@store_order_router.get("/{order_code}")
def get_order_by_code(
    order_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tra cứu thông tin tiến độ đơn hàng.
    Bắt buộc JWT. Khách hàng chỉ xem được đơn hàng của chính mình (chống IDOR).
    ADMIN được xem.
    """
    clean_code = order_code.strip()
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.order_code == clean_code)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng với mã này.")

    if current_user.role == UserRole.CUSTOMER:
        if order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thông tin đơn hàng này.")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thông tin đơn hàng này.")

    is_admin = current_user.role == UserRole.ADMIN
    masked_phone = (
        order.customer_phone
        if is_admin
        else (order.customer_phone[:3] + "****" + order.customer_phone[-3:] if len(order.customer_phone) >= 7 else order.customer_phone)
    )

    return {
        "order_code": order.order_code,
        "customer_name": order.customer_name,
        "customer_phone": masked_phone,
        "shipping_address": order.shipping_address,
        "shipping_city": order.shipping_city,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "order_status": order.order_status,
        "total_amount": float(order.total_amount),
        "shipping_fee": float(order.shipping_fee or 0),
        "discount_amount": float(order.discount_amount or 0),
        "voucher_code": order.voucher_code,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "product_id": it.product_id,
                "product_name": it.product_name,
                "product_sku": it.product_sku,
                "price": float(it.price),
                "quantity": it.quantity,
                "subtotal": float(it.subtotal),
            }
            for it in order.items
        ],
        "fulfillments": _serialize_fulfillments(db, order.id) if is_admin else [],
    }


@store_order_router.get("/customer/{phone}")
def get_customer_orders(phone: str):
    """
    [ĐÃ VÔ HIỆU HÓA - BẢO MẬT PII]
    Không sử dụng số điện thoại như bằng chứng quyền sở hữu đơn hàng.
    Vui lòng đăng nhập và sử dụng GET /api/v1/me/orders.
    """
    raise HTTPException(
        status_code=403,
        detail="Tra cứu đơn hàng bằng số điện thoại đã bị vô hiệu hóa vì lý do bảo mật. Vui lòng đăng nhập và truy cập GET /api/v1/me/orders.",
    )


# ==========================================
# 2. ADMIN QUẢN LÝ ĐƠN HÀNG
# ==========================================
@admin_order_router.get("")
def list_orders(
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Danh sách đơn hàng dành cho Admin & Viewer quản lý/theo dõi.
    """
    query = select(Order).options(selectinload(Order.items))

    if status and status.upper() != "ALL":
        query = query.where(Order.order_status == status.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Order.order_code.ilike(term),
                Order.customer_name.ilike(term),
                Order.customer_phone.ilike(term),
            )
        )

    total = db.scalar(select(Order).with_only_columns(Order.id).order_by(None))
    orders = db.scalars(
        query.order_by(desc(Order.id)).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return {
        "items": [
            {
                "id": o.id,
                "order_code": o.order_code,
                "customer_name": o.customer_name,
                "customer_phone": o.customer_phone,
                "shipping_address": o.shipping_address,
                "payment_method": o.payment_method,
                "payment_status": o.payment_status,
                "order_status": o.order_status,
                "total_amount": float(o.total_amount),
                "items_count": len(o.items),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
        "page": page,
        "page_size": page_size,
    }


@admin_order_router.get("/{order_id}")
def get_admin_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Chi tiết đơn hàng cho Admin & Viewer.
    """
    order = db.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")

    return {
        "id": order.id,
        "order_code": order.order_code,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "customer_email": order.customer_email,
        "shipping_address": order.shipping_address,
        "shipping_city": order.shipping_city,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "order_status": order.order_status,
        "total_amount": float(order.total_amount),
        "note": order.note,
        "is_verified": bool(order.is_verified) if order.is_verified is not None else False,
        "lat": order.lat,
        "lng": order.lng,
        "province_code": order.province_code,
        "district_code": order.district_code,
        "ward_code": order.ward_code,
        "province_code_current": order.province_code_current,
        "commune_code_current": order.commune_code_current,
        "commune_type": order.commune_type,
        "formatted_address_current": order.formatted_address_current,
        "legacy_province": order.legacy_province,
        "legacy_district": order.legacy_district,
        "legacy_ward": order.legacy_ward,
        "verified_at": order.verified_at.isoformat() if order.verified_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "product_name": it.product_name,
                "product_sku": it.product_sku,
                "price": float(it.price),
                "quantity": it.quantity,
                "subtotal": float(it.subtotal),
            }
            for it in order.items
        ],
        "fulfillments": _serialize_fulfillments(db, order.id),
    }


class UpdateFulfillmentStatusRequest(BaseModel):
    status: str  # PENDING | PICKED | PACKED | SHIPPED | DELIVERED | CANCELLED


@admin_order_router.patch("/fulfillments/{fulfillment_id}/status")
def update_fulfillment_status(
    fulfillment_id: int,
    payload: UpdateFulfillmentStatusRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Cập nhật trạng thái kiện hàng theo quy trình kho (chỉ ADMIN).
    """
    ff = FulfillmentRoutingService.transition_fulfillment_status(
        db=db,
        fulfillment_id=fulfillment_id,
        new_status=payload.status.upper(),
        user_id=admin.id,
    )
    return {
        "status": "SUCCESS",
        "message": f"Kiện hàng {ff.fulfillment_code} đã cập nhật trạng thái: {ff.status}.",
        "fulfillment": {
            "id": ff.id,
            "fulfillment_code": ff.fulfillment_code,
            "status": ff.status,
            "shipped_at": ff.shipped_at.isoformat() if ff.shipped_at else None,
            "delivered_at": ff.delivered_at.isoformat() if ff.delivered_at else None,
        },
    }


@admin_order_router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: UpdateOrderStatusRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Cập nhật trạng thái đơn hàng (Duyệt, Giao, Hoàn thành, Hủy).
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")

    valid_statuses = {"PENDING", "CONFIRMED", "PROCESSING", "SHIPPING", "COMPLETED", "CANCELLED"}
    if payload.order_status.upper() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Trạng thái không hợp lệ. Phải là một trong: {valid_statuses}")

    order.order_status = payload.order_status.upper()
    if payload.payment_status:
        order.payment_status = payload.payment_status.upper()

    db.commit()
    return {
        "status": "UPDATED",
        "message": f"Đã cập nhật trạng thái đơn {order.order_code} thành {order.order_status}.",
        "order_id": order.id,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
    }
