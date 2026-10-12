"""
apps/api/app/api/admin_exchanges.py

API Quản trị Đơn Hàng Đổi Hàng Dược Phẩm (Admin Exchange Order Management) H4CARE:
1. Danh sách đơn đổi hàng (GET /api/v1/admin/exchanges).
2. Chi tiết đơn đổi hàng & sản phẩm thay thế (GET /api/v1/admin/exchanges/{exchange_code}).
3. Tạo đơn đổi hàng mới từ yêu cầu đổi/trả đã duyệt (POST /api/v1/admin/exchanges).
4. Xác nhận thanh toán chênh lệch giá (POST /api/v1/admin/exchanges/{exchange_code}/confirm-payment).
5. Xuất kho & phát hành vận đơn thay thế (POST /api/v1/admin/exchanges/{exchange_code}/dispatch).
6. Hoàn tất đơn đổi hàng (POST /api/v1/admin/exchanges/{exchange_code}/complete).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.entities import User
from app.models.enums import UserRole
from app.models.returns import ExchangeItem, ExchangeOrder, ExchangeStatus, ReturnRequest
from app.services.exchange_service import ExchangeService

router = APIRouter(prefix="/admin/exchanges", tags=["Admin Exchange Orders"])


# --- Schemas ---

class ReplacementItemPayload(BaseModel):
    product_id: int
    sku_id: Optional[int] = None
    quantity: int = Field(ge=1)
    unit_price: Optional[Decimal] = None


class CreateExchangePayload(BaseModel):
    return_code: str
    shipping_address: Optional[str] = None
    items: List[ReplacementItemPayload]


class ConfirmPaymentPayload(BaseModel):
    payment_method: str = Field(default="COD")
    transaction_ref: str = Field(..., min_length=2)


class DispatchExchangePayload(BaseModel):
    carrier_name: str = Field(..., min_length=2)
    tracking_code: str = Field(..., min_length=2)


# --- Endpoints ---

@router.get("")
def list_admin_exchanges(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Danh sách các đơn đổi hàng trong hệ thống.
    """
    query = select(ExchangeOrder)

    if status_filter:
        query = query.where(ExchangeOrder.status == status_filter)

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ExchangeOrder.exchange_code.ilike(term),
                ExchangeOrder.tracking_code.ilike(term),
            )
        )

    total_count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    offset = (page - 1) * page_size
    records = db.scalars(query.order_by(ExchangeOrder.id.desc()).offset(offset).limit(page_size)).all()

    items_out = []
    for ex in records:
        items_out.append({
            "id": ex.id,
            "exchange_code": ex.exchange_code,
            "return_code": ex.return_request.return_code if ex.return_request else "",
            "returned_items_value": float(ex.returned_items_value),
            "replacement_items_value": float(ex.replacement_items_value),
            "price_difference": float(ex.price_difference),
            "status": ex.status,
            "carrier_name": ex.carrier_name,
            "tracking_code": ex.tracking_code,
            "items_count": len(ex.items),
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
            "shipped_at": ex.shipped_at.isoformat() if ex.shipped_at else None,
            "delivered_at": ex.delivered_at.isoformat() if ex.delivered_at else None,
        })

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "items": items_out,
        "exchanges": items_out,
    }


@router.get("/{exchange_code}")
def get_admin_exchange_detail(
    exchange_code: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Chi tiết đơn đổi hàng và danh sách sản phẩm thay thế.
    """
    ex = db.scalar(select(ExchangeOrder).where(ExchangeOrder.exchange_code == exchange_code))
    if not ex:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn đổi hàng '{exchange_code}'.")

    items_data = [
        {
            "id": it.id,
            "product_id": it.product_id,
            "sku_id": it.sku_id,
            "product_name": it.product_name,
            "sku_code": it.sku_code,
            "quantity": it.quantity,
            "unit_price": float(it.unit_price),
            "subtotal": float(it.subtotal),
        }
        for it in ex.items
    ]

    return {
        "id": ex.id,
        "exchange_code": ex.exchange_code,
        "return_code": ex.return_request.return_code if ex.return_request else "",
        "original_order_code": ex.original_order.order_code if ex.original_order else "",
        "returned_items_value": float(ex.returned_items_value),
        "replacement_items_value": float(ex.replacement_items_value),
        "price_difference": float(ex.price_difference),
        "shipping_address": ex.shipping_address,
        "status": ex.status,
        "carrier_name": ex.carrier_name,
        "tracking_code": ex.tracking_code,
        "created_at": ex.created_at.isoformat() if ex.created_at else None,
        "shipped_at": ex.shipped_at.isoformat() if ex.shipped_at else None,
        "delivered_at": ex.delivered_at.isoformat() if ex.delivered_at else None,
        "items": items_data,
    }


@router.post("")
def create_exchange_order(
    payload: CreateExchangePayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Khởi tạo đơn đổi hàng mới từ yêu cầu đổi/trả.
    """
    ex = ExchangeService.create_exchange_order(
        db=db,
        return_code=payload.return_code,
        replacement_items_payload=[it.model_dump() for it in payload.items],
        shipping_address=payload.shipping_address,
        operator_user=admin_user,
    )
    return {
        "success": True,
        "exchange_code": ex.exchange_code,
        "price_difference": float(ex.price_difference),
        "status": ex.status,
        "message": "Đã khởi tạo đơn hàng đổi mới thành công.",
    }


@router.post("/{exchange_code}/confirm-payment")
def confirm_exchange_payment(
    exchange_code: str,
    payload: ConfirmPaymentPayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Xác nhận khách hàng đã thanh toán xong khoản chênh lệch đổi hàng.
    """
    ex = ExchangeService.confirm_difference_payment(
        db=db,
        exchange_code=exchange_code,
        payment_method=payload.payment_method,
        transaction_ref=payload.transaction_ref,
        operator_user=admin_user,
    )
    return {
        "success": True,
        "exchange_code": ex.exchange_code,
        "status": ex.status,
        "message": "Đã xác nhận thanh toán chênh lệch thành công.",
    }


@router.post("/{exchange_code}/dispatch")
def dispatch_exchange(
    exchange_code: str,
    payload: DispatchExchangePayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Xuất kho và gửi kiện hàng đổi mới tới khách hàng.
    """
    ex = ExchangeService.dispatch_exchange_order(
        db=db,
        exchange_code=exchange_code,
        carrier_name=payload.carrier_name,
        tracking_code=payload.tracking_code,
        operator_user=admin_user,
    )
    return {
        "success": True,
        "exchange_code": ex.exchange_code,
        "status": ex.status,
        "message": f"Đã xuất kho gửi hàng đổi qua {payload.carrier_name} (Mã vận đơn: {payload.tracking_code}).",
    }


@router.post("/{exchange_code}/complete")
def complete_exchange(
    exchange_code: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Hoàn tất đơn đổi hàng (Khách đã nhận kiện hàng mới thành công).
    """
    ex = ExchangeService.complete_exchange_order(
        db=db,
        exchange_code=exchange_code,
        operator_user=admin_user,
    )
    return {
        "success": True,
        "exchange_code": ex.exchange_code,
        "status": ex.status,
        "message": "Đã hoàn tất đơn đổi hàng và đóng hồ sơ liên quan.",
    }
