"""
apps/api/app/api/admin_refunds.py

API Quản trị Hoàn Tiền & Đối Soát Tài Chính (Refunds & Financial Reconciliation) H4CARE:
1. Danh sách phiếu hoàn tiền với bộ lọc đa chiều (GET /api/v1/admin/refunds).
2. Chi tiết phiếu hoàn tiền & lịch sử cổng thanh toán (GET /api/v1/admin/refunds/{refund_code}).
3. Tạo phiếu hoàn tiền thủ công (POST /api/v1/admin/refunds).
4. Xác nhận ủy nhiệm chi chuyển khoản ngân hàng (POST /api/v1/admin/refunds/{refund_code}/manual-bank).
5. Kích hoạt hoàn tiền tự động qua MoMo API Sandbox (POST /api/v1/admin/refunds/{refund_code}/momo).
6. Cập nhật trạng thái đối soát kế toán (POST /api/v1/admin/refunds/{refund_code}/reconcile).
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
from app.models.entities import Order, User
from app.models.enums import UserRole
from app.models.returns import (
    ReconciliationStatus,
    Refund,
    RefundMethod,
    RefundStatus,
    ReturnRequest,
)
from app.services.refund_service import RefundService

router = APIRouter(prefix="/admin/refunds", tags=["Admin Refunds & Reconciliation"])


# --- Schemas ---

class CreateRefundPayload(BaseModel):
    order_code: str
    refund_amount: Decimal = Field(..., gt=0)
    refund_method: str = Field(default=RefundMethod.BANK_TRANSFER.value)
    return_code: Optional[str] = None
    reason: Optional[str] = None
    beneficiary_bank: Optional[str] = None
    beneficiary_account_number: Optional[str] = None
    beneficiary_account_name: Optional[str] = None
    idempotency_key: Optional[str] = None


class ManualBankPayload(BaseModel):
    bank_transfer_ref: str = Field(..., min_length=2, description="Mã giao dịch / UNC ngân hàng")
    proof_document_url: Optional[str] = None
    notes: Optional[str] = None


class ReconcilePayload(BaseModel):
    reconciliation_status: str = Field(..., description="MATCHED, MISMATCH, NEEDS_REVIEW, PENDING")
    note: Optional[str] = None


# --- Endpoints ---

@router.get("")
def list_admin_refunds(
    status_filter: Optional[str] = Query(None, alias="status"),
    method_filter: Optional[str] = Query(None, alias="refund_method"),
    reconciliation_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Danh sách phiếu hoàn tiền phục vụ đối soát kế toán.
    """
    query = select(Refund).join(Order, Refund.order_id == Order.id)

    if status_filter:
        query = query.where(Refund.status == status_filter)

    if method_filter:
        query = query.where(Refund.refund_method == method_filter)

    if reconciliation_status:
        query = query.where(Refund.reconciliation_status == reconciliation_status)

    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Refund.refund_code.ilike(term),
                Order.order_code.ilike(term),
                Refund.bank_transfer_ref.ilike(term),
                Refund.beneficiary_account_name.ilike(term),
                Refund.beneficiary_account_number.ilike(term),
            )
        )

    total_count = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    offset = (page - 1) * page_size
    records = db.scalars(query.order_by(Refund.id.desc()).offset(offset).limit(page_size)).all()

    items_out = []
    for r in records:
        items_out.append({
            "id": r.id,
            "refund_code": r.refund_code,
            "order_code": r.order.order_code if r.order else "",
            "return_code": r.return_request.return_code if r.return_request else None,
            "refund_amount": float(r.refund_amount),
            "refund_method": r.refund_method,
            "status": r.status,
            "reconciliation_status": r.reconciliation_status,
            "beneficiary_bank": r.beneficiary_bank,
            "beneficiary_account_number": r.beneficiary_account_number,
            "beneficiary_account_name": r.beneficiary_account_name,
            "bank_transfer_ref": r.bank_transfer_ref,
            "gateway_trans_id": r.gateway_trans_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
            "reconciled_at": r.reconciled_at.isoformat() if r.reconciled_at else None,
        })

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "items": items_out,
        "refunds": items_out,
    }


@router.get("/{refund_code}")
def get_admin_refund_detail(
    refund_code: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Chi tiết phiếu hoàn tiền và các lần thử giao dịch qua cổng (Refund Attempts).
    """
    refund = db.scalar(select(Refund).where(Refund.refund_code == refund_code))
    if not refund:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phiếu hoàn tiền '{refund_code}'.")

    attempts_data = []
    for at in refund.attempts:
        attempts_data.append({
            "id": at.id,
            "attempt_number": at.attempt_number,
            "gateway_provider": at.gateway_provider,
            "status": at.status,
            "error_message": at.error_message,
            "created_at": at.created_at.isoformat() if at.created_at else None,
            "request_payload": at.request_payload_json,
            "response_payload": at.response_payload_json,
        })

    return {
        "id": refund.id,
        "refund_code": refund.refund_code,
        "order_code": refund.order.order_code if refund.order else "",
        "order_total": float(refund.order.total_amount) if refund.order else 0,
        "return_code": refund.return_request.return_code if refund.return_request else None,
        "refund_amount": float(refund.refund_amount),
        "currency": refund.currency,
        "refund_method": refund.refund_method,
        "status": refund.status,
        "reconciliation_status": refund.reconciliation_status,
        "bank_transfer_ref": refund.bank_transfer_ref,
        "gateway_trans_id": refund.gateway_trans_id,
        "beneficiary_bank": refund.beneficiary_bank,
        "beneficiary_account_number": refund.beneficiary_account_number,
        "beneficiary_account_name": refund.beneficiary_account_name,
        "reason": refund.reason,
        "notes": refund.notes,
        "proof_document_url": refund.proof_document_url,
        "idempotency_key": refund.idempotency_key,
        "created_at": refund.created_at.isoformat() if refund.created_at else None,
        "processed_at": refund.processed_at.isoformat() if refund.processed_at else None,
        "reconciled_at": refund.reconciled_at.isoformat() if refund.reconciled_at else None,
        "attempts": attempts_data,
    }


@router.post("")
def create_manual_refund(
    payload: CreateRefundPayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Tạo mới phiếu hoàn tiền theo yêu cầu.
    """
    order = db.scalar(select(Order).where(Order.order_code == payload.order_code))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{payload.order_code}'.")

    return_request_id = None
    if payload.return_code:
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == payload.return_code))
        if not ret:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy yêu cầu đổi/trả '{payload.return_code}'.")
        return_request_id = ret.id

    refund = RefundService.create_refund_request(
        db=db,
        order_id=order.id,
        refund_amount=payload.refund_amount,
        refund_method=payload.refund_method,
        return_request_id=return_request_id,
        reason=payload.reason,
        beneficiary_bank=payload.beneficiary_bank,
        beneficiary_account_number=payload.beneficiary_account_number,
        beneficiary_account_name=payload.beneficiary_account_name,
        idempotency_key=payload.idempotency_key,
        created_by_user=admin_user,
    )

    return {
        "success": True,
        "refund_code": refund.refund_code,
        "status": refund.status,
        "refund_amount": float(refund.refund_amount),
        "message": "Đã tạo phiếu hoàn tiền thành công.",
    }


@router.post("/{refund_code}/manual-bank")
def process_manual_bank(
    refund_code: str,
    payload: ManualBankPayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Kế toán xác nhận đã chuyển khoản ngân hàng hoàn tất (cung cấp mã UNC và link chứng từ).
    """
    refund = RefundService.process_manual_bank_refund(
        db=db,
        refund_code=refund_code,
        accountant_user=admin_user,
        bank_transfer_ref=payload.bank_transfer_ref,
        proof_document_url=payload.proof_document_url,
        notes=payload.notes,
    )
    return {
        "success": True,
        "refund_code": refund.refund_code,
        "status": refund.status,
        "message": f"Đã ghi nhận chuyển khoản thành công. Mã UNC: {payload.bank_transfer_ref}",
    }


@router.post("/{refund_code}/momo")
def trigger_momo_refund(
    refund_code: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Kích hoạt hoàn tiền trực tuyến qua API MoMo V2.
    """
    result = RefundService.process_momo_refund(
        db=db,
        refund_code=refund_code,
        operator_user=admin_user,
    )
    return result


@router.post("/{refund_code}/reconcile")
def update_reconciliation(
    refund_code: str,
    payload: ReconcilePayload,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Cập nhật trạng thái đối soát kế toán (MATCHED / MISMATCH / NEEDS_REVIEW).
    """
    refund = RefundService.reconcile_refund(
        db=db,
        refund_code=refund_code,
        reconciliation_status=payload.reconciliation_status,
        accountant_user=admin_user,
        note=payload.note,
    )
    return {
        "success": True,
        "refund_code": refund.refund_code,
        "reconciliation_status": refund.reconciliation_status,
        "message": f"Đã cập nhật trạng thái đối soát: {payload.reconciliation_status}",
    }
