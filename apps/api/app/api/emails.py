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
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN ONLY] Gửi email kiểm tra cấu hình SMTP tới địa chỉ được chỉ định.
    """
    subject = "[PharmaTrust] Kiểm tra kết nối dịch vụ gửi Email Gmail SMTP"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
      <h2 style="color: #0284c7; margin-top: 0;">Kiểm tra kết nối SMTP PharmaTrust / H4CARE</h2>
      <p>Xin chào,</p>
      <p>Đây là email kiểm tra được gửi trực tiếp từ máy chủ PharmaTrust qua giao thức <b>SMTP ({settings.smtp_host}:{settings.smtp_port})</b>.</p>
      <p style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; font-family: monospace; font-size: 13px;">
        Sender: {settings.smtp_from_name} &lt;{settings.smtp_user or settings.smtp_from_email}&gt;<br>
        Recipient: {payload.recipient_email}<br>
        Host: {settings.smtp_host}:{settings.smtp_port}<br>
        TLS: {settings.smtp_tls} | SSL: {settings.smtp_ssl}
      </p>
      <p style="color: #16a34a; font-weight: bold;">✓ Kết nối SMTP Gmail hoạt động hoàn hảo!</p>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
      <p style="font-size: 11px; color: #64748b;">Hệ thống Thương mại Dược phẩm PharmaTrust & H4CARE.</p>
    </div>
    """
    body_text = f"Email kiểm tra kết nối SMTP PharmaTrust gửi tới {payload.recipient_email}. Kết nối thành công!"

    try:
        EmailService.send_smtp_email(
            recipient_email=str(payload.recipient_email),
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )
        return {
            "success": True,
            "message": f"Đã gửi thành công email kiểm tra tới '{payload.recipient_email}'",
            "host": settings.smtp_host,
            "port": settings.smtp_port,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể gửi email kiểm tra: {str(e)}")
