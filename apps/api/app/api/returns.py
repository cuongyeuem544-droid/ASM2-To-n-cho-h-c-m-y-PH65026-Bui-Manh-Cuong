"""
apps/api/app/api/returns.py

API Khách hàng phục vụ Đổi trả (Customer Return & Exchange Endpoints) H4CARE:
1. Thẩm định điều kiện đổi trả đơn hàng (GET /api/v1/returns/eligibility/{order_code}).
2. Gửi yêu cầu đổi/trả hàng mới (POST /api/v1/returns).
3. Lấy danh sách yêu cầu của tôi (GET /api/v1/returns/my-requests).
4. Xem chi tiết tiến trình đổi trả & đối soát hoàn tiền (GET /api/v1/returns/{return_code}).
5. Cập nhật mã vận đơn chiều trả về (POST /api/v1/returns/{return_code}/shipping).
6. Khách hàng tự hủy yêu cầu khi chưa gửi hàng (POST /api/v1/returns/{return_code}/cancel).
7. Tải lên hình ảnh bằng chứng hàng lỗi/hỏng (POST /api/v1/returns/upload-evidence).
"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.security import verify_guest_order_token
from app.db.session import get_db
from app.models.entities import Order, OrderItem, User
from app.models.returns import (
    ExchangeItem,
    ExchangeOrder,
    Refund,
    ReturnEvidence,
    ReturnEvidenceRequest,
    ReturnEvidenceRequestStatus,
    ReturnItem,
    ReturnMethod,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
    ReturnStatusHistory,
)
from app.services.refund_calculation_service import RefundCalculationService
from app.services.return_policy_service import ReturnPolicyService
from app.services.return_service import ReturnService
from app.services.warehouse_return_service import WarehouseReturnService


def to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


router = APIRouter(prefix="/returns", tags=["Customer Returns & Exchanges"])


# --- Schemas ---

class ReturnItemCreate(BaseModel):
    order_item_id: int
    requested_quantity: int = Field(ge=1)
    customer_reason: Optional[str] = None
    condition_reported: Optional[str] = None


class ReturnRequestCreate(BaseModel):
    order_code: str
    request_type: str = "RETURN"  # RETURN hoặc EXCHANGE
    reason_code: str
    reason_text: str
    customer_note: Optional[str] = None
    return_method: str = "CUSTOMER_SHIP"
    items: List[ReturnItemCreate]
    evidence_urls: Optional[List[str]] = None
    customer_phone_verify: Optional[str] = None
    customer_email_verify: Optional[str] = None
    order_token: Optional[str] = None


class ShippingUpdate(BaseModel):
    carrier_name: str
    tracking_code: str
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


class CancelReturnRequest(BaseModel):
    reason: Optional[str] = None
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None



class EvidenceItemInput(BaseModel):
    file_url: str
    file_name: str
    mime_type: Optional[str] = "image/jpeg"
    file_size: Optional[int] = 0


class CustomerSubmitEvidencePayload(BaseModel):
    images: List[EvidenceItemInput] = Field(..., min_length=1, max_length=3)
    customer_note: Optional[str] = None
    phone_verify: Optional[str] = None


# --- Endpoints ---

@router.get("/eligibility/{order_code}")
def check_order_eligibility(
    order_code: str,
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Kiểm tra điều kiện đổi trả của đơn hàng theo chính sách dược phẩm H4CARE.
    """
    clean_code = order_code.strip()
    order = db.scalar(select(Order).where(Order.order_code == clean_code))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{clean_code}'.")

    # Xác thực quyền kiểm tra điều kiện đổi/trả
    is_staff = current_user and getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    effective_token = x_order_token
    if not effective_token and authorization and authorization.startswith("Bearer "):
        bearer_val = authorization[7:].strip()
        if verify_guest_order_token(bearer_val, clean_code):
            effective_token = bearer_val

    is_token_valid = verify_guest_order_token(effective_token, clean_code)

    if not is_staff:
        if current_user and getattr(current_user, "role", "") == "CUSTOMER":
            if order.user_id and order.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập đơn hàng này.")
            if not order.user_id and not is_token_valid:
                clean_user_phone = (current_user.phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")
                clean_order_phone = (order.customer_phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")
                if clean_user_phone != clean_order_phone:
                    raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập đơn hàng này.")
        else:
            if not is_token_valid:
                raise HTTPException(
                    status_code=403,
                    detail="Số điện thoại không phải là bằng chứng duy nhất để xác thực quyền sở hữu đơn. Vui lòng cung cấp token đơn hàng hợp lệ (order_token) hoặc đăng nhập để kiểm tra điều kiện đổi/trả.",
                )

    eligibility = ReturnPolicyService.evaluate_order_eligibility(db, order)

    # Đơn giá ròng và hạn mức hoàn tiền
    items_out = []
    for it in eligibility.items:
        order_item = next((oi for oi in order.items if oi.id == it.order_item_id), None)
        net_unit_price = (
            RefundCalculationService.calculate_net_unit_price(order, order_item)
            if order_item
            else Decimal("0.0")
        )
        items_out.append({
            "order_item_id": it.order_item_id,
            "product_id": it.product_id,
            "product_name": it.product_name,
            "purchased_quantity": it.purchased_quantity,
            "returned_quantity": it.returned_quantity,
            "returnable_quantity": it.returnable_quantity,
            "is_rx": it.is_rx,
            "is_eligible": it.is_eligible,
            "reason_code": it.reason_code,
            "message": it.message,
            "net_unit_price": float(net_unit_price),
        })

    already_refunded = RefundCalculationService.get_already_refunded_amount(db, order.id)
    max_refundable = max(Decimal("0.0"), Decimal(str(order.total_amount)) - already_refunded)

    return {
        "order_code": eligibility.order_code,
        "order_status": eligibility.order_status,
        "payment_status": eligibility.payment_status,
        "total_amount": float(order.total_amount),
        "shipping_fee": float(order.shipping_fee or 0),
        "already_refunded": float(already_refunded),
        "max_possible_refund": float(max_refundable),
        "delivery_date": eligibility.delivery_date.isoformat() if eligibility.delivery_date else None,
        "days_since_delivery": eligibility.days_since_delivery,
        "within_return_window": eligibility.within_return_window,
        "can_request_return": eligibility.can_request_return,
        "can_request_exchange": eligibility.can_request_exchange,
        "rejection_reason": eligibility.rejection_reason,
        "free_return_shipping_reasons": eligibility.free_return_shipping_reasons,
        "items": items_out,
    }


@router.post("")
def create_return_request(
    payload: ReturnRequestCreate,
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Gửi yêu cầu đổi hoặc trả hàng mới.
    """
    clean_code = payload.order_code.strip()
    order = db.scalar(select(Order).where(Order.order_code == clean_code))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{clean_code}'.")

    is_staff = current_user and getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    effective_token = payload.order_token or x_order_token
    if not effective_token and authorization and authorization.startswith("Bearer "):
        bearer_val = authorization[7:].strip()
        if verify_guest_order_token(bearer_val, clean_code):
            effective_token = bearer_val

    is_token_valid = verify_guest_order_token(effective_token, clean_code)

    if not is_staff:
        if current_user and getattr(current_user, "role", "") == "CUSTOMER":
            if order.user_id and order.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Bạn không có quyền tạo yêu cầu đổi/trả cho đơn hàng này.")
            if not order.user_id and not is_token_valid:
                clean_user_phone = (current_user.phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")
                clean_order_phone = (order.customer_phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")
                if clean_user_phone != clean_order_phone:
                    raise HTTPException(status_code=403, detail="Bạn không có quyền tạo yêu cầu đổi/trả cho đơn hàng này.")
        else:
            if not is_token_valid:
                raise HTTPException(
                    status_code=403,
                    detail="Số điện thoại không phải là bằng chứng duy nhất để xác thực quyền sở hữu đơn. Vui lòng cung cấp token đơn hàng hợp lệ (order_token) để gửi yêu cầu đổi/trả.",
                )

    evidences_data = []
    if payload.evidence_urls:
        for url in payload.evidence_urls:
            evidences_data.append({"file_url": url, "file_name": os.path.basename(url)})

    ret = ReturnService.create_return_request(
        db=db,
        order_code=payload.order_code,
        request_type=payload.request_type,
        reason_code=payload.reason_code,
        reason_text=payload.reason_text,
        items_payload=[it.model_dump() for it in payload.items],
        customer_note=payload.customer_note,
        return_method=payload.return_method,
        evidences_payload=evidences_data,
        current_user=current_user,
        customer_phone_verify=payload.customer_phone_verify or (order.customer_phone if is_token_valid else None),
        customer_email_verify=payload.customer_email_verify,
    )

    return {
        "success": True,
        "return_code": ret.return_code,
        "request_type": ret.request_type,
        "status": ret.status,
        "message": "Gửi yêu cầu đổi/trả hàng thành công. Bộ phận Dược sĩ H4CARE sẽ thẩm định trong vòng 24 giờ làm việc.",
    }


@router.get("/my-requests")
def get_my_return_requests(
    customer_phone: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Lấy danh sách các yêu cầu đổi/trả của khách hàng hiện tại (Bảo đảm cách ly tài khoản).
    - Khách hàng bắt buộc phải đăng nhập.
    - User chỉ được xem danh sách yêu cầu đổi/trả thuộc tài khoản hoặc số điện thoại của chính mình.
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Vui lòng đăng nhập để tra cứu danh sách yêu cầu đổi/trả.",
        )

    is_staff = getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    clean_user_phone = (current_user.phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")

    query = select(ReturnRequest).order_by(ReturnRequest.id.desc())

    if not is_staff:
        if customer_phone:
            clean_param_phone = customer_phone.strip().replace(" ", "").replace(".", "").replace("-", "")
            if clean_param_phone != clean_user_phone:
                raise HTTPException(
                    status_code=403,
                    detail="Bạn không có quyền xem danh sách đổi/trả của số điện thoại khác.",
                )
        query = query.where(
            or_(
                ReturnRequest.user_id == current_user.id,
                ReturnRequest.customer_phone == clean_user_phone,
            )
        )
    elif customer_phone:
        clean_phone = customer_phone.strip().replace(" ", "").replace(".", "").replace("-", "")
        query = query.where(ReturnRequest.customer_phone == clean_phone)

    records = db.scalars(query.limit(limit)).all()

    out = []
    for r in records:
        out.append({
            "id": r.id,
            "return_code": r.return_code,
            "order_code": r.order.order_code if r.order else "",
            "request_type": r.request_type,
            "status": r.status,
            "reason_text": r.reason_text,
            "items_count": len(r.items),
            "carrier_name": r.carrier_name,
            "tracking_code": r.tracking_code,
            "requested_at": r.requested_at.isoformat() if r.requested_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return {"returns": out}


@router.get("/{return_code}")
def get_return_detail(
    return_code: str,
    phone_verify: Optional[str] = None,
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Xem chi tiết tiến trình đổi/trả, dòng thời gian (timeline), thông tin bưu tá và đối soát hoàn tiền.
    Yêu cầu bảo mật:
    - Nhân viên (ADMIN, PHARMACIST, DATA_REVIEWER): Toàn quyền tra cứu để xử lý nghiệp vụ.
    - Khách hàng đã đăng nhập (CUSTOMER): Chỉ được xem yêu cầu thuộc tài khoản của chính mình.
    - Khách vãng lai: Bắt buộc cung cấp token đơn hàng hợp lệ (order_token/guest_access_token) qua Header X-Order-Token.
      Số điện thoại không phải là bằng chứng duy nhất để cấp quyền xem thông tin chi tiết.
    """
    ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
    if not ret:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

    order_code = ret.order.order_code if ret.order else (db.scalar(select(Order.order_code).where(Order.id == ret.order_id)) or "")

    # Kiểm tra quyền truy cập (Anti-IDOR - Từ chối người chưa đủ quyền)
    is_staff = current_user and getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    clean_order_phone = (ret.customer_phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")

    effective_token = x_order_token
    if not effective_token and authorization and authorization.startswith("Bearer "):
        bearer_val = authorization[7:].strip()
        if verify_guest_order_token(bearer_val, order_code):
            effective_token = bearer_val

    is_token_valid = verify_guest_order_token(effective_token, order_code)

    if not is_staff:
        if current_user and getattr(current_user, "role", "") == "CUSTOMER":
            # Đơn gắn với tài khoản khác -> Chặn User A truy cập User B
            if ret.user_id and ret.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập yêu cầu đổi/trả này.")
            # Đơn chưa gắn user_id (đặt dạng guest trước đó) -> Kiểm tra số điện thoại hoặc token
            if not ret.user_id:
                clean_user_phone = (current_user.phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")
                if clean_user_phone != clean_order_phone and not is_token_valid:
                    raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập yêu cầu đổi/trả này.")
        else:
            # Khách vãng lai chưa đăng nhập: Bắt buộc có token ký điện tử hợp lệ
            if not is_token_valid:
                raise HTTPException(
                    status_code=403,
                    detail="Số điện thoại không phải là bằng chứng duy nhất để xác thực quyền sở hữu đơn. Vui lòng cung cấp token đơn hàng hợp lệ (order_token) hoặc đăng nhập để xem thông tin đổi/trả.",
                )

    # Format danh sách sản phẩm
    items_data = []
    for it in ret.items:
        items_data.append({
            "id": it.id,
            "order_item_id": it.order_item_id,
            "product_id": it.product_id,
            "product_name": it.product_name,
            "requested_quantity": it.requested_quantity,
            "accepted_quantity": it.accepted_quantity,
            "rejected_quantity": it.rejected_quantity,
            "inspected_condition": it.inspected_condition,
            "restock_destination": it.restock_destination,
            "inspection_notes": it.inspection_notes,
            "customer_reason": it.customer_reason,
            "condition_reported": it.condition_reported,
        })

    # Format timeline lịch sử trạng thái
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

    # Format bằng chứng
    evidences = [
        {
            "id": e.id,
            "file_url": e.file_url,
            "file_name": e.file_name,
            "file_type": e.file_type,
            "description": e.description,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in ret.evidences
    ]

    # Format thông tin hoàn tiền (Refunds)
    refunds_data = []
    for ref in ret.refunds:
        refunds_data.append({
            "id": ref.id,
            "refund_code": ref.refund_code,
            "refund_amount": float(ref.refund_amount),
            "refund_method": ref.refund_method,
            "status": ref.status,
            "reconciliation_status": ref.reconciliation_status,
            "bank_transfer_ref": ref.bank_transfer_ref,
            "gateway_trans_id": ref.gateway_trans_id,
            "beneficiary_bank": ref.beneficiary_bank,
            "beneficiary_account_number": ref.beneficiary_account_number,
            "beneficiary_account_name": ref.beneficiary_account_name,
            "proof_document_url": ref.proof_document_url,
            "processed_at": ref.processed_at.isoformat() if ref.processed_at else None,
        })

    # Format thông tin đơn đổi hàng (Exchanges)
    exchanges_data = []
    for ex in ret.exchange_orders:
        ex_items = [
            {
                "id": ei.id,
                "product_name": ei.product_name,
                "sku_code": ei.sku_code,
                "quantity": ei.quantity,
                "unit_price": float(ei.unit_price),
                "subtotal": float(ei.subtotal),
            }
            for ei in ex.items
        ]
        exchanges_data.append({
            "id": ex.id,
            "exchange_code": ex.exchange_code,
            "returned_items_value": float(ex.returned_items_value),
            "replacement_items_value": float(ex.replacement_items_value),
            "price_difference": float(ex.price_difference),
            "status": ex.status,
            "carrier_name": ex.carrier_name,
            "tracking_code": ex.tracking_code,
            "shipping_address": ex.shipping_address,
            "items": ex_items,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
        })

    # Tính toán dự kiến hoàn tiền
    refund_estimate = RefundCalculationService.calculate_return_refund(
        db=db,
        order=ret.order,
        return_items=ret.items,
        reason_code=ret.reason_code,
    )

    return {
        "id": ret.id,
        "return_code": ret.return_code,
        "order_code": ret.order.order_code if ret.order else "",
        "request_type": ret.request_type,
        "status": ret.status,
        "reason_code": ret.reason_code,
        "reason_text": ret.reason_text,
        "customer_note": ret.customer_note,
        "customer_name": ret.customer_name,
        "customer_phone": ret.customer_phone,
        "customer_email": ret.customer_email,
        "return_method": ret.return_method,
        "carrier_name": ret.carrier_name,
        "tracking_code": ret.tracking_code,
        "return_address_snapshot": ret.return_address_snapshot,
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
        "estimated_refund": {
            "items_refund": float(refund_estimate["items_refund_amount"]),
            "shipping_fee_refund": float(refund_estimate["shipping_fee_refund"]),
            "final_refund": float(refund_estimate["final_refund_amount"]),
        },
        "active_evidence_request": (
            lambda req: {
                "id": req.id,
                "request_code": req.request_code,
                "return_item_id": req.return_item_id,
                "product_name": req.return_item.product_name if req.return_item else None,
                "reason": req.reason,
                "instructions": req.instructions,
                "required_image_count": req.required_image_count,
                "status": req.status,
                "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                "expires_at": req.expires_at.isoformat() if req.expires_at else None,
                "remaining_seconds": max(0, int((to_utc(req.expires_at) - datetime.now(UTC)).total_seconds())) if req.expires_at else 0,
                "is_expired": (to_utc(req.expires_at) <= datetime.now(UTC)) or (req.status == "EXPIRED") if req.expires_at else (req.status == "EXPIRED"),
                "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
                "customer_note": req.customer_note,
                "evidences": [
                    {
                        "id": ev.id,
                        "file_url": ev.file_url,
                        "file_name": ev.file_name,
                        "created_at": ev.created_at.isoformat() if ev.created_at else None,
                    }
                    for ev in req.evidences
                ],
            } if req else None
        )(
            WarehouseReturnService.get_customer_evidence_request(
                db=db,
                return_code=return_code,
                user=current_user,
                phone_verify=phone_verify,
                is_token_verified=is_token_valid,
            )
        ),
    }


@router.get("/{return_code}/evidence-request")
def get_customer_evidence_request_endpoint(
    return_code: str,
    phone_verify: Optional[str] = Query(None),
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    order_token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Khách hàng xem yêu cầu bổ sung ảnh, hạn chót còn lại và danh sách ảnh đã nộp.
    """
    ret_req = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
    is_token_verified = False
    if ret_req and ret_req.order:
        effective_token = x_order_token or order_token
        if not effective_token and authorization and authorization.startswith("Bearer "):
            effective_token = authorization[7:].strip()
        if effective_token:
            is_token_verified = verify_guest_order_token(effective_token, ret_req.order.order_code)

    req = WarehouseReturnService.get_customer_evidence_request(
        db=db,
        return_code=return_code,
        user=current_user,
        phone_verify=phone_verify,
        is_token_verified=is_token_verified,
    )
    if not req:
        return {"has_active_request": False, "request": None}

    now = datetime.now(UTC)
    remaining_seconds = max(0, int((to_utc(req.expires_at) - now).total_seconds())) if req.expires_at else 0

    return {
        "has_active_request": True,
        "request": {
            "id": req.id,
            "request_code": req.request_code,
            "return_code": return_code,
            "return_item_id": req.return_item_id,
            "product_name": req.return_item.product_name if req.return_item else None,
            "reason": req.reason,
            "instructions": req.instructions,
            "required_image_count": req.required_image_count,
            "status": req.status,
            "requested_at": req.requested_at.isoformat() if req.requested_at else None,
            "expires_at": req.expires_at.isoformat() if req.expires_at else None,
            "remaining_seconds": remaining_seconds,
            "is_expired": remaining_seconds == 0 or req.status == "EXPIRED",
            "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
            "customer_note": req.customer_note,
            "evidences": [
                {
                    "id": ev.id,
                    "file_url": ev.file_url,
                    "file_name": ev.file_name,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                }
                for ev in req.evidences
            ],
        },
    }


@router.post("/{return_code}/evidence/submit")
@router.post("/{return_code}/evidence")
def submit_customer_evidence_endpoint(
    return_code: str,
    payload: CustomerSubmitEvidencePayload,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Khách hàng nộp đúng số lượng ảnh bổ sung theo yêu cầu.
    """
    images_dicts = [img.model_dump() for img in payload.images]
    req = WarehouseReturnService.submit_customer_evidence(
        db=db,
        return_code=return_code,
        user=current_user,
        images=images_dicts,
        customer_note=payload.customer_note,
        phone_verify=payload.phone_verify,
    )

    try:
        from app.services.warehouse_notification_service import WarehouseNotificationService
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        if ret and req.warehouse_id:
            WarehouseNotificationService.notify_return_evidence_added(db, ret, req.warehouse_id)
            db.commit()
    except Exception:
        pass
    return {
        "success": True,
        "message": "Đã gửi hình ảnh bổ sung thành công. Hồ sơ đang chờ Quản lý kho xem xét.",
        "request_code": req.request_code,
        "status": req.status,
        "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
    }


@router.post("/{return_code}/shipping")
def update_return_shipping(
    return_code: str,
    payload: ShippingUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Khách hàng gửi hàng và cập nhật đơn vị vận chuyển + mã vận đơn theo dõi.
    """
    ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
    if not ret:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

    order_code = ret.order.order_code if ret.order else (db.scalar(select(Order.order_code).where(Order.id == ret.order_id)) or "")
    is_staff = current_user and getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    is_token_valid = verify_guest_order_token(payload.order_token, order_code)
    if not is_staff:
        if current_user and getattr(current_user, "role", "") == "CUSTOMER":
            if ret.user_id and ret.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Bạn không có quyền cập nhật yêu cầu này.")
        else:
            if not is_token_valid:
                raise HTTPException(
                    status_code=403,
                    detail="Số điện thoại không phải là bằng chứng duy nhất để xác thực quyền sở hữu đơn. Vui lòng cung cấp token đơn hàng hợp lệ (order_token) để cập nhật thông tin gửi hàng.",
                )

    ret = ReturnService.update_customer_shipping(
        db=db,
        return_code=return_code,
        carrier_name=payload.carrier_name,
        tracking_code=payload.tracking_code,
        current_user=current_user,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": f"Đã ghi nhận thông tin gửi hàng qua {payload.carrier_name} (Mã: {payload.tracking_code}).",
    }


@router.post("/{return_code}/cancel")
def cancel_return_request(
    return_code: str,
    payload: CancelReturnRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Khách hàng chủ động hủy yêu cầu đổi/trả khi chưa gửi hàng đi.
    """
    ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
    if not ret:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu '{return_code}'.")

    order_code = ret.order.order_code if ret.order else (db.scalar(select(Order.order_code).where(Order.id == ret.order_id)) or "")
    is_staff = current_user and getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    is_token_valid = verify_guest_order_token(payload.order_token, order_code)
    if not is_staff:
        if current_user and getattr(current_user, "role", "") == "CUSTOMER":
            if ret.user_id and ret.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Bạn không có quyền hủy yêu cầu này.")
        else:
            if not is_token_valid:
                raise HTTPException(
                    status_code=403,
                    detail="Số điện thoại không phải là bằng chứng duy nhất để xác thực quyền sở hữu đơn. Vui lòng cung cấp token đơn hàng hợp lệ (order_token) để hủy yêu cầu đổi/trả.",
                )

    ret = ReturnService.cancel_return_request(
        db=db,
        return_code=return_code,
        actor_user=current_user,
        reason=payload.reason,
    )
    return {
        "success": True,
        "return_code": ret.return_code,
        "status": ret.status,
        "message": "Đã hủy yêu cầu đổi/trả hàng thành công.",
    }


DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".sh", ".py", ".php", ".phtml", ".html", ".htm",
    ".js", ".svg", ".dll", ".cmd", ".vbs", ".msi", ".jar", ".jsp", ".asp", ".aspx"
}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_EVIDENCE_SIZE = 5 * 1024 * 1024  # 5 MB


def verify_magic_bytes(data: bytes, ext: str) -> bool:
    """Xác minh loại file bằng nội dung nhị phân (magic bytes / file signature)."""
    if len(data) < 4:
        return False
    if ext in [".jpg", ".jpeg"]:
        return data.startswith(b"\xff\xd8\xff")
    elif ext == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext == ".webp":
        return data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP"
    elif ext == ".pdf":
        return data.startswith(b"%PDF-")
    return False


@router.post("/upload-evidence")
async def upload_return_evidence(
    file: UploadFile = File(...),
    return_code: str = Form(..., description="Mã yêu cầu đổi/trả bắt buộc"),
    description: Optional[str] = Form(None),
    order_token: Optional[str] = Form(None),
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Tải lên ảnh hoặc tài liệu bằng chứng hàng lỗi/hỏng (Lưu trữ cục bộ an toàn trong thư mục storage/returns).
    Bắt buộc phải gắn với một return_code hợp lệ và có quyền sở hữu (ngăn chặn file mồ côi).
    Kiểm tra dung lượng tối đa 5MB, chặn file nguy hiểm và xác minh magic bytes.
    """
    # 0. Bắt buộc có mã return_code hợp lệ trước khi tạo file
    clean_return_code = (return_code or "").strip()
    if not clean_return_code:
        raise HTTPException(
            status_code=400,
            detail="Mã yêu cầu đổi/trả (return_code) là bắt buộc. Không được phép tải lên tài liệu bằng chứng mồ côi.",
        )

    ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == clean_return_code))
    if not ret:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu đổi/trả '{clean_return_code}'.")

    # Kiểm tra quyền sở hữu (Anti-IDOR)
    is_staff = current_user and getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    is_owner = False
    if is_staff:
        is_owner = True
    elif current_user and ret.user_id and current_user.id == ret.user_id:
        is_owner = True

    effective_token = x_order_token or order_token
    if not effective_token and authorization and authorization.startswith("Bearer "):
        bearer_val = authorization[7:].strip()
        if ret.order and verify_guest_order_token(bearer_val, ret.order.order_code):
            effective_token = bearer_val

    if not is_owner and effective_token and ret.order:
        if verify_guest_order_token(effective_token, ret.order.order_code):
            is_owner = True

    if not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền tải lên bằng chứng cho yêu cầu đổi/trả này. Vui lòng cung cấp token đơn hàng hợp lệ hoặc đăng nhập tài khoản sở hữu.",
        )

    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    # 1. Chặn file nguy hiểm
    if ext in DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tệp chứa định dạng nguy hiểm bị từ chối ({ext}).",
        )

    # 2. Kiểm tra phần mở rộng cho phép
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng tệp không được hỗ trợ ({ext}). Chỉ chấp nhận: JPG, PNG, WEBP, PDF.",
        )

    # 3. Đọc dữ liệu và giới hạn dung lượng 5MB
    content = await file.read(MAX_EVIDENCE_SIZE + 1)
    if len(content) > MAX_EVIDENCE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Dung lượng tệp vượt quá giới hạn tối đa cho phép (5MB).",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Tệp tải lên rỗng không có nội dung.",
        )

    # 4. Xác minh loại file bằng nội dung (Magic Bytes)
    if not verify_magic_bytes(content, ext):
        raise HTTPException(
            status_code=400,
            detail=f"Nội dung tệp không khớp với định dạng khai báo ({ext}). Chữ ký tệp không hợp lệ hoặc bị giả mạo.",
        )

    # 5. Lưu file an toàn
    upload_dir = Path(settings.storage_root) / "returns"
    upload_dir.mkdir(parents=True, exist_ok=True)

    unique_filename = f"evid_{uuid.uuid4().hex[:12]}{ext}"
    target_path = upload_dir / unique_filename

    try:
        with open(target_path, "wb") as buffer:
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu file: {str(e)}")

    file_size = len(content)
    file_url = f"/api/v1/returns/evidence/{unique_filename}"

    evidence = ReturnEvidence(
        return_request_id=ret.id,
        storage_key=f"returns/{unique_filename}",
        file_url=file_url,
        file_name=filename or unique_filename,
        mime_type=file.content_type or ("image/jpeg" if ext in [".jpg", ".jpeg"] else "application/pdf"),
        file_size=file_size,
        file_category="DAMAGE_PHOTO",
        description=description,
        uploaded_by=current_user.id if current_user else None,
    )
    db.add(evidence)
    db.commit()

    return {
        "success": True,
        "file_url": file_url,
        "file_name": filename or unique_filename,
        "file_size": file_size,
    }


@router.get("/evidence/{filename}")
def get_evidence_file(
    filename: str,
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Truy xuất tệp bằng chứng hình ảnh hàng lỗi có kiểm soát quyền truy cập (Access Control).
    Chỉ cho phép Admin, Dược sĩ hoặc Khách hàng sở hữu yêu cầu đổi/trả.
    Yêu cầu truyền token qua Header X-Order-Token hoặc Authorization: Bearer, không dùng query string.
    """
    # Ngăn chặn Directory Traversal
    safe_filename = os.path.basename(filename)
    file_path = Path(settings.storage_root) / "returns" / safe_filename

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp bằng chứng.")

    # Kiểm tra quyền nhân viên quản trị / Dược sĩ
    is_staff = current_user and getattr(current_user, "role", "") in ["ADMIN", "PHARMACIST", "DATA_REVIEWER"]
    if is_staff:
        return FileResponse(file_path)

    # Tra cứu bản ghi ReturnEvidence
    evidence = db.scalar(select(ReturnEvidence).where(ReturnEvidence.file_url.like(f"%{safe_filename}")))
    if not evidence:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập tệp bằng chứng này.")

    ret = db.get(ReturnRequest, evidence.return_request_id) if evidence.return_request_id else None
    if not ret:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập tệp bằng chứng này.")

    # Xác thực quyền khách hàng
    is_authorized = False
    if current_user and ret.user_id and current_user.id == ret.user_id:
        is_authorized = True

    effective_token = x_order_token
    if not effective_token and authorization and authorization.startswith("Bearer "):
        bearer_val = authorization[7:].strip()
        if ret.order and verify_guest_order_token(bearer_val, ret.order.order_code):
            effective_token = bearer_val

    if not is_authorized and effective_token and ret.order:
        if verify_guest_order_token(effective_token, ret.order.order_code):
            is_authorized = True

    if not is_authorized:
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền truy cập tệp bằng chứng này. Vui lòng cung cấp mã token đơn hàng hợp lệ qua Header X-Order-Token hoặc đăng nhập tài khoản sở hữu.",
        )

    return FileResponse(file_path)
