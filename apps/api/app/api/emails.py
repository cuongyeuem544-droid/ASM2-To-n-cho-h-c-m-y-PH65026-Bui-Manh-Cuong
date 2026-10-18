from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.models.inventory import EmailOutbox
from app.services.email_service import EmailService

emails_router = APIRouter(prefix="/emails", tags=["Hộp thư & Gửi Email"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class SendTestEmailRequest(BaseModel):
    recipient_email: EmailStr = Field(..., description="Địa chỉ email nhận thư kiểm tra")


class EmailOutboxItemResponse(BaseModel):
    id: int
    recipient_email: str
    subject: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    status: str
    retry_count: int
    max_retries: int
    last_error: Optional[str] = None
    sent_at: Optional[str] = None
    created_at: Optional[str] = None


class EmailOutboxDetailResponse(EmailOutboxItemResponse):
    body_html: str
    body_text: Optional[str] = None


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@emails_router.get("/outbox", response_model=List[EmailOutboxItemResponse])
def list_email_outbox(
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo trạng thái: PENDING, SENT, FAILED"),
    reference_id: Optional[str] = Query(None, description="Lọc theo mã đơn hàng hoặc tham chiếu"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN / MANAGER] Xem danh sách lịch sử gửi email và trạng thái gửi (SENT, FAILED, PENDING).
    """
    stmt = select(EmailOutbox)
    if status_filter:
        stmt = stmt.where(EmailOutbox.status == status_filter.upper())
    if reference_id:
        stmt = stmt.where(EmailOutbox.reference_id.ilike(f"%{reference_id.strip()}%"))

    stmt = stmt.order_by(desc(EmailOutbox.id)).limit(limit).offset(offset)
    records = db.scalars(stmt).all()

    return [
        EmailOutboxItemResponse(
            id=r.id,
            recipient_email=r.recipient_email,
            subject=r.subject,
            reference_type=r.reference_type,
            reference_id=r.reference_id,
            status=r.status,
            retry_count=r.retry_count,
            max_retries=r.max_retries,
            last_error=r.last_error,
            sent_at=r.sent_at.isoformat() if r.sent_at else None,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in records
    ]


@emails_router.get("/outbox/{outbox_id}", response_model=EmailOutboxDetailResponse)
def get_email_outbox_detail(
    outbox_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN / MANAGER] Xem chi tiết nội dung email HTML và văn bản thô để đối soát.
    """
    outbox = db.scalar(select(EmailOutbox).where(EmailOutbox.id == outbox_id))
    if not outbox:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi email")

    return EmailOutboxDetailResponse(
        id=outbox.id,
        recipient_email=outbox.recipient_email,
        subject=outbox.subject,
        reference_type=outbox.reference_type,
        reference_id=outbox.reference_id,
        status=outbox.status,
        retry_count=outbox.retry_count,
        max_retries=outbox.max_retries,
        last_error=outbox.last_error,
        sent_at=outbox.sent_at.isoformat() if outbox.sent_at else None,
        created_at=outbox.created_at.isoformat() if outbox.created_at else None,
        body_html=outbox.body_html,
        body_text=outbox.body_text,
    )


@emails_router.post("/outbox/{outbox_id}/resend")
def resend_outbox_email(
    outbox_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN / MANAGER] Thử gửi lại bức thư trong hàng đợi (Retry Resend).
    """
    try:
        updated = EmailService.resend_email(db=db, outbox_id=outbox_id)
        return {
            "success": True,
            "message": f"Đã gửi lại thành công email #{outbox_id} tới '{updated.recipient_email}'",
            "status": updated.status,
            "sent_at": updated.sent_at.isoformat() if updated.sent_at else None,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gửi lại email thất bại: {str(e)}")


@emails_router.post("/test")
def send_test_email(
    payload: SendTestEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN ONLY] Gửi email kiểm tra cấu hình SMTP tới địa chỉ được chỉ định,
    ghi nhận đầy đủ vào EmailOutbox.
    """
    try:
        outbox = EmailService.queue_and_send_test_email(
            db=db,
            recipient_email=str(payload.recipient_email),
        )
        return {
            "success": True,
            "message": f"Đã gửi thành công email kiểm tra tới '{payload.recipient_email}'",
            "outbox_id": outbox.id,
            "status": outbox.status,
            "sent_at": outbox.sent_at.isoformat() if outbox.sent_at else None,
            "reference_id": outbox.reference_id,
            "host": settings.smtp_host,
            "port": settings.smtp_port,
        }
    except Exception as e:
        err_code, _, sanitized_msg = EmailService.classify_smtp_error(e)
        raise HTTPException(status_code=400, detail=f"Không thể gửi email kiểm tra [{err_code}]: {sanitized_msg}")
