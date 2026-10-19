from __future__ import annotations

import base64
import json
import os
import re
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.models.chat_models import AIChatAttachment, AIChatConversation, AIChatMessage
from app.models.enums import UserRole

router = APIRouter(prefix="/chat", tags=["AI Chatbot History & Attachments"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[\x00-\x1f\x80-\x9f/\\]", "", name).strip()
    return clean or "image.jpg"


def verify_image_signature(content: bytes, ext: str) -> bool:
    if len(content) < 12:
        return False
    if ext in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


class ChatAttachmentResponse(BaseModel):
    attachment_code: str
    original_filename: str
    file_size: int
    mime_type: str
    url: str
    base64_data: Optional[str] = None
    uploaded_at: str
    success: bool = True
    attachment: Optional[dict[str, Any]] = None


class SaveMessageSchema(BaseModel):
    id: Optional[str] = None
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., max_length=10000)
    attachments: List[dict[str, Any]] = Field(default_factory=list)
    safety_alert: Optional[dict[str, Any]] = None
    quick_replies: List[str] = Field(default_factory=list)
    recommended_products: List[dict[str, Any]] = Field(default_factory=list)
    api_status: Optional[str] = None
    model_used: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: Optional[str] = None


class SaveConversationSchema(BaseModel):
    conversation_code: Optional[str] = None
    id: Optional[str] = None
    session_id: str = Field(..., min_length=1, max_length=128)
    title: Optional[str] = Field(default="Cuộc trò chuyện mới", max_length=255)
    extracted_memory: Optional[dict[str, Any]] = None
    messages: List[SaveMessageSchema] = Field(default_factory=list)


class ConversationSummarySchema(BaseModel):
    conversation_code: str
    id: Optional[str] = None
    title: str
    session_id: str
    message_count: int
    last_message: Optional[str] = None
    created_at: str
    updated_at: str
    is_pinned: bool = False


class ConversationDetailSchema(BaseModel):
    conversation_code: str
    id: Optional[str] = None
    title: str
    session_id: str
    extracted_memory: Optional[dict[str, Any]] = None
    messages: List[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class RenameConversationSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


@router.post("/upload", response_model=ChatAttachmentResponse)
async def upload_chat_image(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Tải lên tệp ảnh đính kèm cho Chatbot AI với kiểm định an toàn nghiêm ngặt:
    - Định dạng: JPG, JPEG, PNG, WEBP
    - Giới hạn: tối đa 10 MB
    - Kiểm tra File Signature (Magic bytes)
    - Lưu vào Private Storage, chống Path Traversal
    """
    clean_name = sanitize_filename(file.filename or "image.jpg")
    ext = Path(clean_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng tệp '{ext}' không được hỗ trợ. Hệ thống chỉ hỗ trợ JPG, JPEG, PNG, WEBP.",
        )

    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp ảnh tải lên có dung lượng rỗng (0 bytes). Vui lòng kiểm tra lại tệp.",
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dung lượng tệp vượt quá giới hạn 10 MB (tệp hiện tại: {file_size / (1024 * 1024):.2f} MB).",
        )

    if not verify_image_signature(content, ext):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chữ ký nhị phân của tệp (Magic Bytes) không hợp lệ hoặc tệp bị giả mạo định dạng.",
        )

    # Sinh thư mục lưu trữ an toàn theo năm/tháng
    now = datetime.now(UTC)
    year_str = str(now.year)
    month_str = f"{now.month:02d}"
    storage_base = Path(settings.storage_root) / "chat-attachments" / year_str / month_str
    storage_base.mkdir(parents=True, exist_ok=True)

    file_uuid = uuid.uuid4().hex
    stored_filename = f"{file_uuid}{ext}"
    physical_path = storage_base / stored_filename

    with open(physical_path, "wb") as f:
        f.write(content)

    attachment_code = f"att-{file_uuid[:12]}"
    mime_type = "image/jpeg" if ext in {".jpg", ".jpeg"} else f"image/{ext.removeprefix('.')}"

    attachment = AIChatAttachment(
        attachment_code=attachment_code,
        user_id=current_user.id if current_user else None,
        session_id=session_id or f"sess-{file_uuid[:8]}",
        original_filename=clean_name,
        stored_filename=stored_filename,
        file_path=str(physical_path),
        mime_type=mime_type,
        file_size=file_size,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    base64_str = base64.b64encode(content).decode("utf-8")
    attachment_dict = {
        "id": attachment.attachment_code,
        "name": attachment.original_filename,
        "fileName": attachment.original_filename,
        "size": attachment.file_size,
        "fileSize": attachment.file_size,
        "type": "image",
        "mime_type": attachment.mime_type,
        "mimeType": attachment.mime_type,
        "url": f"/api/v1/chat/attachments/{attachment.attachment_code}",
        "uploaded_at": attachment.created_at.isoformat(),
        "uploadedAt": attachment.created_at.isoformat(),
    }

    return ChatAttachmentResponse(
        attachment_code=attachment.attachment_code,
        original_filename=attachment.original_filename,
        file_size=attachment.file_size,
        mime_type=attachment.mime_type,
        url=f"/api/v1/chat/attachments/{attachment.attachment_code}",
        base64_data=base64_str,
        uploaded_at=attachment.created_at.isoformat(),
        success=True,
        attachment=attachment_dict,
    )


@router.get("/attachments/{attachment_code}")
def get_chat_attachment(
    attachment_code: str,
    session_id: Optional[str] = Query(None),
    x_session_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Trả về tệp ảnh an toàn với security headers
    """
    stmt = select(AIChatAttachment).where(AIChatAttachment.attachment_code == attachment_code)
    att = db.scalars(stmt).first()
    if not att or not os.path.exists(att.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tệp đính kèm")

    caller_session_id = session_id or x_session_id
    # Anti-IDOR: Nếu tệp thuộc về user có tài khoản, chỉ cho phép chính user đó xem
    if att.user_id is not None:
        if not current_user or (current_user.id != att.user_id and current_user.role != UserRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền truy cập vào tệp đính kèm này",
            )
    else:
        # Tệp của khách vãng lai: bắt buộc có session_id khớp
        if not caller_session_id or not secrets.compare_digest(caller_session_id.strip(), (att.session_id or "").strip()):
            if not current_user or current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập vào tệp đính kèm này (yêu cầu session_id hợp lệ)",
                )

    return FileResponse(
        path=att.file_path,
        media_type=att.mime_type,
        filename=att.original_filename,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/conversations", response_model=List[ConversationSummarySchema])
def list_conversations(
    session_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách các cuộc trò chuyện của người dùng:
    - Nếu đã đăng nhập: lấy theo user_id
    - Nếu là khách vãng lai: lấy theo session_id
    """
    query = select(AIChatConversation).where(AIChatConversation.is_archived.is_(False))
    if current_user:
        query = query.where(AIChatConversation.user_id == current_user.id)
    elif session_id:
        query = query.where(AIChatConversation.session_id == session_id)
    else:
        return []

    query = query.order_by(desc(AIChatConversation.updated_at)).limit(50)
    convs = db.scalars(query).all()

    results = []
    for c in convs:
        last_msg = ""
        if c.messages:
            last_msg = c.messages[-1].content[:80]
        results.append(
            ConversationSummarySchema(
                id=c.conversation_code,
                conversation_code=c.conversation_code,
                title=c.title,
                session_id=c.session_id,
                message_count=len(c.messages),
                last_message=last_msg,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat(),
                is_pinned=c.is_pinned,
            )
        )
    return results


@router.post("/conversations", response_model=ConversationDetailSchema)
def save_or_update_conversation(
    payload: SaveConversationSchema,
    x_session_id: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Lưu hoặc đồng bộ cuộc trò chuyện từ client lên server
    """
    conv_code = payload.conversation_code or payload.id
    conv = None
    if conv_code:
        conv = db.scalars(
            select(AIChatConversation).where(AIChatConversation.conversation_code == conv_code)
        ).first()

    caller_session_id = payload.session_id or x_session_id
    if conv:
        # Anti-IDOR check
        if conv.user_id is not None:
            if not current_user or (current_user.id != conv.user_id and current_user.role != UserRole.ADMIN):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền chỉnh sửa cuộc trò chuyện này",
                )
        else:
            # Cuộc trò chuyện khách vãng lai: bắt buộc session_id phải khớp
            if not caller_session_id or not secrets.compare_digest(caller_session_id.strip(), (conv.session_id or "").strip()):
                if not current_user or current_user.role != UserRole.ADMIN:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Bạn không có quyền chỉnh sửa cuộc trò chuyện này (sai session_id)",
                    )
        if conv.user_id is None and current_user is not None:
            conv.user_id = current_user.id
    else:
        conv_code = conv_code or f"conv-{uuid.uuid4().hex[:12]}"
        conv = AIChatConversation(
            conversation_code=conv_code,
            user_id=current_user.id if current_user else None,
            session_id=payload.session_id,
            title=payload.title or "Cuộc trò chuyện mới",
        )
        db.add(conv)
        db.flush()

    if payload.title:
        conv.title = payload.title
    if payload.extracted_memory:
        conv.extracted_memory = json.dumps(payload.extracted_memory, ensure_ascii=False)

    conv.updated_at = datetime.now(UTC)

    # Cập nhật danh sách tin nhắn
    if payload.messages:
        # Xóa tin nhắn cũ để đồng bộ lại
        db.execute(delete(AIChatMessage).where(AIChatMessage.conversation_id == conv.id))
        for m in payload.messages:
            msg = AIChatMessage(
                conversation_id=conv.id,
                role=m.role,
                content=m.content,
                attachments_json=json.dumps(m.attachments, ensure_ascii=False) if m.attachments else None,
                safety_alert_json=json.dumps(m.safety_alert, ensure_ascii=False) if m.safety_alert else None,
                quick_replies_json=json.dumps(m.quick_replies, ensure_ascii=False) if m.quick_replies else None,
                recommended_products_json=json.dumps(m.recommended_products, ensure_ascii=False) if m.recommended_products else None,
                api_status=m.api_status,
                model_used=m.model_used,
                latency_ms=m.latency_ms,
            )
            db.add(msg)

    db.commit()
    db.refresh(conv)

    # Format trả về
    formatted_messages = []
    for m in conv.messages:
        formatted_messages.append({
            "id": f"msg-{m.id}",
            "role": m.role,
            "content": m.content,
            "timestamp": m.created_at.strftime("%H:%M"),
            "attachments": json.loads(m.attachments_json) if m.attachments_json else [],
            "safetyAlert": json.loads(m.safety_alert_json) if m.safety_alert_json else None,
            "quickReplies": json.loads(m.quick_replies_json) if m.quick_replies_json else [],
            "recommendedProducts": json.loads(m.recommended_products_json) if m.recommended_products_json else [],
            "apiStatus": m.api_status,
            "modelUsed": m.model_used,
            "latencyMs": m.latency_ms,
        })

    return ConversationDetailSchema(
        id=conv.conversation_code,
        conversation_code=conv.conversation_code,
        title=conv.title,
        session_id=conv.session_id,
        extracted_memory=json.loads(conv.extracted_memory) if conv.extracted_memory else None,
        messages=formatted_messages,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@router.get("/conversations/{conversation_code}", response_model=ConversationDetailSchema)
def get_conversation_detail(
    conversation_code: str,
    session_id: Optional[str] = Query(None),
    x_session_id: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Lấy chi tiết một cuộc trò chuyện cùng lịch sử tin nhắn và memory đã lưu
    """
    conv = db.scalars(
        select(AIChatConversation).where(AIChatConversation.conversation_code == conversation_code)
    ).first()

    if not conv or conv.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện")

    # Anti-IDOR check
    caller_session_id = session_id or x_session_id
    if conv.user_id is not None:
        if not current_user or (current_user.id != conv.user_id and current_user.role != UserRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem cuộc trò chuyện này",
            )
    else:
        # Cuộc trò chuyện khách vãng lai: bắt buộc session_id phải khớp
        if not caller_session_id or not secrets.compare_digest(caller_session_id.strip(), (conv.session_id or "").strip()):
            if not current_user or current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xem cuộc trò chuyện này (yêu cầu session_id hợp lệ)",
                )

    formatted_messages = []
    for m in conv.messages:
        formatted_messages.append({
            "id": f"msg-{m.id}",
            "role": m.role,
            "content": m.content,
            "timestamp": m.created_at.strftime("%H:%M"),
            "attachments": json.loads(m.attachments_json) if m.attachments_json else [],
            "safetyAlert": json.loads(m.safety_alert_json) if m.safety_alert_json else None,
            "quickReplies": json.loads(m.quick_replies_json) if m.quick_replies_json else [],
            "recommendedProducts": json.loads(m.recommended_products_json) if m.recommended_products_json else [],
            "apiStatus": m.api_status,
            "modelUsed": m.model_used,
            "latencyMs": m.latency_ms,
        })

    return ConversationDetailSchema(
        id=conv.conversation_code,
        conversation_code=conv.conversation_code,
        title=conv.title,
        session_id=conv.session_id,
        extracted_memory=json.loads(conv.extracted_memory) if conv.extracted_memory else None,
        messages=formatted_messages,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@router.patch("/conversations/{conversation_code}")
def rename_conversation(
    conversation_code: str,
    payload: RenameConversationSchema,
    session_id: Optional[str] = Query(None),
    x_session_id: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Đổi tên cuộc trò chuyện
    """
    conv = db.scalars(
        select(AIChatConversation).where(AIChatConversation.conversation_code == conversation_code)
    ).first()

    if not conv or conv.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện")

    caller_session_id = session_id or x_session_id
    if conv.user_id is not None:
        if not current_user or (current_user.id != conv.user_id and current_user.role != UserRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền chỉnh sửa cuộc trò chuyện này",
            )
    else:
        if not caller_session_id or not secrets.compare_digest(caller_session_id.strip(), (conv.session_id or "").strip()):
            if not current_user or current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền chỉnh sửa cuộc trò chuyện này (sai session_id)",
                )

    conv.title = payload.title.strip()
    conv.updated_at = datetime.now(UTC)
    db.commit()
    return {"success": True, "title": conv.title}


@router.delete("/conversations/{conversation_code}")
def delete_conversation(
    conversation_code: str,
    session_id: Optional[str] = Query(None),
    x_session_id: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Xóa một cuộc trò chuyện và dọn dẹp các tệp ảnh liên quan trên đĩa
    """
    conv = db.scalars(
        select(AIChatConversation).where(AIChatConversation.conversation_code == conversation_code)
    ).first()

    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện")

    caller_session_id = session_id or x_session_id
    if conv.user_id is not None:
        if not current_user or (current_user.id != conv.user_id and current_user.role != UserRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xóa cuộc trò chuyện này",
            )
    else:
        if not caller_session_id or not secrets.compare_digest(caller_session_id.strip(), (conv.session_id or "").strip()):
            if not current_user or current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xóa cuộc trò chuyện này (sai session_id)",
                )

    # Dọn dẹp tệp vật lý của các attachments liên quan
    for att in conv.attachments:
        if att.file_path and os.path.exists(att.file_path):
            try:
                os.remove(att.file_path)
            except Exception:
                pass

    db.delete(conv)
    db.commit()
    return {"success": True, "message": "Đã xóa cuộc trò chuyện thành công"}


@router.delete("/conversations")
def clear_all_conversations(
    session_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Xóa toàn bộ lịch sử trò chuyện của người dùng hoặc phiên hiện tại
    """
    query = select(AIChatConversation)
    if current_user:
        query = query.where(AIChatConversation.user_id == current_user.id)
    elif session_id:
        query = query.where(AIChatConversation.session_id == session_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần cung cấp session_id hoặc đăng nhập để xóa lịch sử.",
        )

    convs = db.scalars(query).all()
    count = len(convs)

    for conv in convs:
        for att in conv.attachments:
            if att.file_path and os.path.exists(att.file_path):
                try:
                    os.remove(att.file_path)
                except Exception:
                    pass
        db.delete(conv)

    db.commit()
    return {"success": True, "deleted_count": count, "message": f"Đã xóa toàn bộ {count} cuộc trò chuyện."}
