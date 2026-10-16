from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.addresses import (
    CustomerAddressCreate,
    CustomerAddressUpdate,
    _serialize_customer_address,
    _update_address_logic,
    validate_and_normalize_phone,
    validate_recipient_name,
)
from app.api.deps import get_current_user
from app.api.orders import _serialize_fulfillments
from app.db.session import get_db
from app.models import CustomerAddress, Order, User
from app.services.administrative_service import AdministrativeDataService
from app.services.audit import write_audit
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.geo_service import GeoService

me_router = APIRouter(prefix="/me", tags=["Hồ sơ & Đơn hàng Cá nhân"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class UserProfileResponse(BaseModel):
    id: int
    email: str
    phone: Optional[str] = None
    full_name: str
    role: str
    loyalty_points: int
    is_active: bool
    created_at: Optional[str] = None


class BuyerOrderCancelRequest(BaseModel):
    reason: Optional[str] = "Khách hàng yêu cầu hủy đơn"


# ==============================================================================
# 1. HỒ SƠ NGƯỜI DÙNG (PROFILE)
# ==============================================================================

@me_router.get("", response_model=UserProfileResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    [BUYER / USER] Xem thông tin hồ sơ của chính mình từ backend database.
    """
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        phone=current_user.phone,
        full_name=current_user.full_name,
        role=current_user.role.value,
        loyalty_points=current_user.loyalty_points,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@me_router.patch("", response_model=UserProfileResponse)
def update_my_profile(
    payload: UpdateProfileRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER / USER] Cập nhật thông tin cá nhân (Họ tên, SĐT, Email) có xác thực và chống trùng lặp.
    """
    before_json = {
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "email": current_user.email,
    }

    if payload.full_name and payload.full_name.strip():
        current_user.full_name = payload.full_name.strip()

    if payload.phone is not None:
        clean_phone = payload.phone.strip().replace(" ", "").replace("-", "")
        if clean_phone:
            if len(clean_phone) < 9 or len(clean_phone) > 15:
                raise HTTPException(status_code=400, detail="Số điện thoại phải từ 9 đến 15 chữ số.")
            existing_phone = db.scalar(select(User.id).where(User.phone == clean_phone, User.id != current_user.id))
            if existing_phone:
                raise HTTPException(status_code=409, detail="Số điện thoại này đã được sử dụng bởi tài khoản khác.")
            current_user.phone = clean_phone

    if payload.email is not None:
        clean_email = str(payload.email).strip().lower()
        if clean_email:
            existing_email = db.scalar(select(User.id).where(User.email == clean_email, User.id != current_user.id))
            if existing_email:
                raise HTTPException(status_code=409, detail="Email này đã được sử dụng bởi tài khoản khác.")
            current_user.email = clean_email

    write_audit(
        db,
        action="UPDATE_PROFILE",
        entity_type="User",
        entity_id=current_user.id,
        user=current_user,
        request=request,
        before=before_json,
        after={
            "full_name": current_user.full_name,
            "phone": current_user.phone,
            "email": current_user.email,
        },
    )

    db.commit()
    db.refresh(current_user)

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        phone=current_user.phone,
        full_name=current_user.full_name,
        role=current_user.role.value,
        loyalty_points=current_user.loyalty_points,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


# ==============================================================================
# 2. SỔ ĐỊA CHỈ KHÁCH HÀNG (ADDRESSES CRUD)
# ==============================================================================

@me_router.get("/addresses")
def list_my_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Lấy danh sách địa chỉ nhận hàng của chính mình.
    """
    addresses = db.scalars(
        select(CustomerAddress)
        .where(CustomerAddress.user_id == current_user.id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.desc())
    ).all()
    return [_serialize_customer_address(addr) for addr in addresses]


@me_router.post("/addresses", status_code=status.HTTP_201_CREATED)
def create_my_address(
    payload: CustomerAddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Thêm mới địa chỉ nhận hàng cá nhân.
    """
    recipient_name = validate_recipient_name(payload.recipient_name)
    phone = validate_and_normalize_phone(payload.phone)

    prov_code = payload.province_code.strip()
    prov_info = AdministrativeDataService.get_province_by_code(prov_code)
    if not prov_info:
        raise HTTPException(status_code=400, detail=f"Mã Tỉnh/Thành phố '{prov_code}' không hợp lệ.")

    comm_code = (payload.commune_code or payload.ward_code or "").strip()
    comm_name = payload.commune_name
    district_code = payload.district_code

    if comm_code:
        is_valid_sel, sel_err = AdministrativeDataService.validate_selection(prov_code, comm_code)
        if not is_valid_sel:
            raise HTTPException(status_code=400, detail=sel_err)
        comm_info = AdministrativeDataService.get_commune_by_code(comm_code)
        if comm_info:
            comm_name = comm_info["fullName"]
            if comm_info.get("legacyDistrictName"):
                district_code = comm_info.get("legacyDistrictName")

    address_line = payload.address_line.strip()
    province_name = prov_info["fullName"]
    formatted_address = f"{address_line}, {comm_name or ''}, {province_name}".strip(", ")

    is_verified = False
    verified_at = None
    if payload.lat is not None and payload.lng is not None:
        is_v, v_msg = GeoService.verify_customer_address(
            province_code=prov_code,
            commune_code=comm_code,
            lat=payload.lat,
            lng=payload.lng,
        )
        if not is_v:
            raise HTTPException(status_code=400, detail=v_msg)
        is_verified = True
        verified_at = datetime.now(timezone.utc)

    existing_count = db.scalar(select(CustomerAddress.id).where(CustomerAddress.user_id == current_user.id))
    is_first = (existing_count is None)
    should_be_default = payload.is_default or is_first

    if should_be_default:
        existing_defaults = db.scalars(
            select(CustomerAddress).where(
                CustomerAddress.user_id == current_user.id,
                CustomerAddress.is_default == True,
            )
        ).all()
        for ea in existing_defaults:
            ea.is_default = False

    addr = CustomerAddress(
        user_id=current_user.id,
        recipient_name=recipient_name,
        phone=phone,
        address_line=address_line,
        province_code=prov_code,
        province_name=province_name,
        commune_code=comm_code or None,
        commune_name=comm_name,
        formatted_address=formatted_address,
        district_code=district_code,
        ward_code=comm_code or payload.ward_code,
        lat=payload.lat,
        lng=payload.lng,
        place_id=payload.place_id,
        delivery_note=payload.delivery_note.strip() if payload.delivery_note else None,
        is_verified=is_verified,
        verified_at=verified_at,
        is_default=should_be_default,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return _serialize_customer_address(addr)


@me_router.get("/addresses/{address_id}")
def get_my_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Xem chi tiết 1 địa chỉ nhận hàng cá nhân.
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == current_user.id,
        )
    )
    if not addr:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa chỉ nhận hàng.")
    return _serialize_customer_address(addr)


@me_router.put("/addresses/{address_id}")
def update_my_address(
    address_id: int,
    payload: CustomerAddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Cập nhật địa chỉ nhận hàng cá nhân.
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == current_user.id,
        )
    )
    if not addr:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa chỉ nhận hàng.")

    return _update_address_logic(addr=addr, payload=payload, db=db, user=current_user)


@me_router.delete("/addresses/{address_id}")
def delete_my_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Xóa 1 địa chỉ nhận hàng cá nhân.
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == current_user.id,
        )
    )
    if not addr:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa chỉ nhận hàng.")

    was_default = addr.is_default
    db.delete(addr)
    db.commit()

    if was_default:
        next_addr = db.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == current_user.id)
            .order_by(CustomerAddress.id.desc())
        )
        if next_addr:
            next_addr.is_default = True
            db.commit()

    return {"status": "SUCCESS", "message": "Đã xóa địa chỉ thành công."}


@me_router.patch("/addresses/{address_id}/default")
def set_my_default_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Đặt địa chỉ làm mặc định.
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == current_user.id,
        )
    )
    if not addr:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa chỉ nhận hàng.")

    all_addrs = db.scalars(
        select(CustomerAddress).where(CustomerAddress.user_id == current_user.id)
    ).all()
    for a in all_addrs:
        a.is_default = (a.id == address_id)

    db.commit()
    return {"status": "SUCCESS", "message": "Đã đặt địa chỉ mặc định thành công.", "id": address_id}


# ==============================================================================
# 3. LỊCH SỬ ĐƠN HÀNG CÁ NHÂN (BUYER ORDERS - NO IDOR)
# ==============================================================================

@me_router.get("/orders")
def list_my_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Tra cứu lịch sử đơn hàng của chính mình (chống IDOR 100%).
    Tuyệt đối không lộ đơn của khách hàng khác.
    """
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == current_user.id)
    )
    if status_filter and status_filter.strip():
        stmt = stmt.where(Order.order_status == status_filter.strip().upper())

    stmt = stmt.order_by(desc(Order.id)).limit(limit).offset(offset)
    orders = db.scalars(stmt).all()

    total_count = db.scalar(
        select(func.count(Order.id)).where(Order.user_id == current_user.id)
    ) or 0

    results = []
    for o in orders:
        results.append({
            "order_code": o.order_code,
            "order_status": o.order_status,
            "payment_status": o.payment_status,
            "payment_method": o.payment_method,
            "total_amount": float(o.total_amount),
            "shipping_fee": float(o.shipping_fee or 0),
            "discount_amount": float(o.discount_amount or 0),
            "voucher_code": o.voucher_code,
            "shipping_address": o.shipping_address,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items_count": len(o.items),
            "items": [
                {
                    "product_id": it.product_id,
                    "product_name": it.product_name,
                    "product_sku": it.product_sku,
                    "price": float(it.price),
                    "quantity": it.quantity,
                    "subtotal": float(it.subtotal),
                }
                for it in o.items
            ],
        })

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "orders": results,
    }


@me_router.get("/orders/{order_code}")
def get_my_order_detail(
    order_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Xem chi tiết 1 đơn hàng của chính mình (chống IDOR 100%).
    Chỉ trả thông tin cần thiết cho người mua, ẩn mã nội bộ kho và thông tin nhạy cảm.
    """
    clean_code = order_code.strip()
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.order_code == clean_code,
            Order.user_id == current_user.id,
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng của bạn.")

    return {
        "order_code": order.order_code,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "shipping_address": order.shipping_address,
        "shipping_city": order.shipping_city,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "order_status": order.order_status,
        "total_amount": float(order.total_amount),
        "shipping_fee": float(order.shipping_fee or 0),
        "discount_amount": float(order.discount_amount or 0),
        "voucher_code": order.voucher_code,
        "note": order.note,
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
        "fulfillments": _serialize_fulfillments(db, order.id),
    }


@me_router.post("/orders/{order_code}/cancel")
def cancel_my_order(
    order_code: str,
    payload: BuyerOrderCancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [BUYER] Khách hàng tự hủy đơn hàng của chính mình.
    Điều kiện:
    - Quyền sở hữu: đơn hàng phải thuộc user_id của chính người yêu cầu.
    - Trạng thái: đơn còn ở trạng thái PENDING hoặc trong vòng 30 phút sau khi đặt.
    - Idempotent: nếu đơn đã hủy thì trả về trạng thái hủy an toàn.
    - Giải phóng giữ chỗ tồn kho (StockReservation) và ghi audit log bất biến.
    """
    clean_code = order_code.strip()
    order = db.scalar(
        select(Order).where(
            Order.order_code == clean_code,
            Order.user_id == current_user.id,
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng của bạn.")

    if order.order_status == "CANCELLED":
        return {
            "status": "SUCCESS",
            "message": "Đơn hàng đã ở trạng thái hủy trước đó.",
            "order_code": clean_code,
            "order_status": "CANCELLED",
        }

    if order.order_status in ["SHIPPING", "COMPLETED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Đơn hàng đang ở trạng thái '{order.order_status}', không thể tự hủy trực tuyến. Vui lòng liên hệ Dược sĩ trực tuyến.",
        )

    # Kiểm tra thời hạn 30 phút nếu trạng thái đã vượt qua PENDING (nhưng chưa giao)
    now = datetime.now(timezone.utc)
    order_time = order.created_at
    if order_time:
        if order_time.tzinfo is None:
            order_time = order_time.replace(tzinfo=timezone.utc)
        time_elapsed = (now - order_time).total_seconds()
        if order.order_status != "PENDING" and time_elapsed > 1800:
            raise HTTPException(
                status_code=400,
                detail="Đơn hàng đã được xác nhận quá 30 phút. Không thể tự hủy trực tuyến.",
            )

    before_status = order.order_status

    # Giải phóng tồn kho giữ chỗ (FEFO)
    released_qty = FulfillmentRoutingService.release_order_reservations(
        db=db,
        order_id=order.id,
        reason=payload.reason or "Khách hàng tự hủy đơn trên tài khoản",
    )

    order.order_status = "CANCELLED"
    order.fulfillment_status = "CANCELLED"

    write_audit(
        db,
        action="BUYER_CANCEL_ORDER",
        entity_type="Order",
        entity_id=order.id,
        user=current_user,
        request=request,
        before={"order_status": before_status},
        after={"order_status": "CANCELLED", "released_quantity": released_qty, "reason": payload.reason},
    )

    db.commit()
    db.refresh(order)

    return {
        "status": "SUCCESS",
        "message": f"Đã hủy đơn hàng {clean_code} thành công và giải phóng {released_qty} đơn vị thuốc.",
        "order_code": clean_code,
        "released_quantity": released_qty,
        "order_status": "CANCELLED",
    }
