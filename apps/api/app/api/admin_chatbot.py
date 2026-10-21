from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.chatbot import (
    ChatbotAuditLog,
    ChatbotSettings,
    ChatFeedback,
    ChatKnowledgeItem,
    ChatKnowledgeSource,
    ChatMessage,
    ChatPromptVersion,
    ChatProviderAttempt,
    ChatSession,
)
from app.models.entities import User
from app.services.chatbot.expert_provider import remove_vietnamese_accents
from app.services.chatbot.orchestrator import orchestrator

router = APIRouter(prefix="/admin/chatbot", tags=["Admin Chatbot Management"], dependencies=[Depends(require_admin)])


def log_admin_action(
    db: Session,
    admin: User,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    old_values: Optional[Any] = None,
    new_values: Optional[Any] = None,
    result: str = "SUCCESS",
):
    """Ghi nhật ký kiểm toán quản trị Chatbot."""
    entry = ChatbotAuditLog(
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        old_values=json.dumps(old_values, ensure_ascii=False) if old_values else None,
        new_values=json.dumps(new_values, ensure_ascii=False) if new_values else None,
        result=result,
        correlation_id=str(uuid.uuid4()),
    )
    db.add(entry)
    db.commit()


# =========================================================================
# 1. DASHBOARD & TỔNG QUAN KPI
# =========================================================================
@router.get("/dashboard", summary="Báo cáo tổng quan KPI Chatbot Dược sĩ AI")
def get_chatbot_dashboard(db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_sessions = db.scalar(select(func.count(ChatSession.id))) or 0
    today_sessions = db.scalar(select(func.count(ChatSession.id)).where(ChatSession.started_at >= start_of_today)) or 0

    total_messages = db.scalar(select(func.count(ChatMessage.id))) or 0
    today_messages = db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.created_at >= start_of_today)) or 0

    avg_latency = db.scalar(select(func.avg(ChatMessage.latency_ms)).where(ChatMessage.role == "assistant")) or 0

    # Phản hồi hài lòng
    total_feedbacks = db.scalar(select(func.count(ChatFeedback.id))) or 0
    positive_feedbacks = db.scalar(select(func.count(ChatFeedback.id)).where(ChatFeedback.rating >= 4)) or 0
    positive_feedback_pct = round((positive_feedbacks / total_feedbacks * 100), 1) if total_feedbacks > 0 else 100.0

    # Failover & Error rate
    total_attempts = db.scalar(select(func.count(ChatProviderAttempt.id))) or 0
    failed_attempts = db.scalar(select(func.count(ChatProviderAttempt.id)).where(ChatProviderAttempt.result != "success")) or 0
    error_rate = round((failed_attempts / total_attempts * 100), 2) if total_attempts > 0 else 0.0

    # Phân bổ Provider đã sử dụng trong 30 ngày qua
    since_30d = now - timedelta(days=30)
    provider_counts_query = (
        db.query(ChatMessage.provider, func.count(ChatMessage.id))
        .filter(ChatMessage.role == "assistant", ChatMessage.created_at >= since_30d)
        .group_by(ChatMessage.provider)
        .all()
    )
    provider_breakdown = {p: count for p, count in provider_counts_query if p}

    # Danh sách 5 phiên gần nhất
    recent_sessions = db.scalars(
        select(ChatSession).order_by(desc(ChatSession.last_message_at)).limit(5)
    ).all()

    return {
        "kpi": {
            "total_sessions": total_sessions,
            "today_sessions": today_sessions,
            "total_messages": total_messages,
            "today_messages": today_messages,
            "avg_latency_ms": round(float(avg_latency), 0),
            "positive_feedback_pct": positive_feedback_pct,
            "total_feedbacks": total_feedbacks,
            "error_rate": error_rate,
            "failover_attempts": failed_attempts,
        },
        "provider_breakdown": provider_breakdown,
        "recent_sessions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "user_name": s.user.full_name if s.user else "Khách vãng lai",
                "message_count": s.message_count,
                "started_at": s.started_at,
                "last_message_at": s.last_message_at,
                "status": s.status,
            }
            for s in recent_sessions
        ],
    }


# =========================================================================
# 2. QUẢN LÝ PHIÊN HỘI THOẠI (SESSIONS)
# =========================================================================
@router.get("/sessions", summary="Danh sách phiên hội thoại phân trang")
def list_chat_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = select(ChatSession)

    if status:
        query = query.where(ChatSession.status == status)
    if user_id:
        query = query.where(ChatSession.user_id == user_id)
    if search:
        query = query.where(
            or_(
                ChatSession.id.ilike(f"%{search}%"),
                ChatSession.client_session_id.ilike(f"%{search}%"),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    sessions = db.scalars(
        query.order_by(desc(ChatSession.last_message_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "user_name": s.user.full_name if s.user else "Khách vãng lai",
                "user_email": s.user.email if s.user else None,
                "channel": s.channel,
                "status": s.status,
                "message_count": s.message_count,
                "started_at": s.started_at,
                "last_message_at": s.last_message_at,
            }
            for s in sessions
        ],
    }


@router.get("/sessions/{session_id}", summary="Chi tiết phiên hội thoại và tin nhắn")
def get_chat_session_detail(session_id: str, db: Session = Depends(get_db)):
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên trò chuyện")

    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    ).all()

    feedbacks = db.scalars(
        select(ChatFeedback).where(ChatFeedback.session_id == session_id)
    ).all()

    message_ids = [m.id for m in messages]
    attempts = db.scalars(
        select(ChatProviderAttempt)
        .where(
            or_(
                ChatProviderAttempt.session_id == session_id,
                ChatProviderAttempt.message_id.in_(message_ids) if message_ids else False,
            )
        )
        .order_by(ChatProviderAttempt.started_at)
    ).all()

    return {
        "session": {
            "id": session.id,
            "user_id": session.user_id,
            "user_name": session.user.full_name if session.user else "Khách vãng lai",
            "user_email": session.user.email if session.user else None,
            "channel": session.channel,
            "status": session.status,
            "message_count": session.message_count,
            "started_at": session.started_at,
            "last_message_at": session.last_message_at,
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "provider": m.provider,
                "model": m.model,
                "latency_ms": m.latency_ms,
                "finish_reason": m.finish_reason,
                "safety_flags": json.loads(m.safety_flags) if m.safety_flags else [],
                "citations": json.loads(m.citations) if m.citations else [],
                "created_at": m.created_at,
            }
            for m in messages
        ],
        "feedbacks": [
            {
                "id": f.id,
                "rating": f.rating,
                "reason": f.reason,
                "comment": f.comment,
                "created_at": f.created_at,
            }
            for f in feedbacks
        ],
        "provider_attempts": [
            {
                "id": a.id,
                "message_id": a.message_id,
                "provider": a.provider,
                "model": a.model,
                "attempt_number": a.attempt_number,
                "latency_ms": a.latency_ms,
                "http_status": a.http_status,
                "result": a.result,
                "safe_error_message": a.safe_error_message,
                "started_at": a.started_at,
            }
            for a in attempts
        ],
    }


@router.delete("/sessions/{session_id}", summary="Lưu trữ / Xóa mềm phiên hội thoại")
def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên hội thoại")

    old_status = session.status
    session.status = "deleted"
    db.commit()

    log_admin_action(
        db, admin, "DELETE_SESSION", "ChatSession", session_id, {"status": old_status}, {"status": "deleted"}
    )

    return {"message": "Đã lưu trữ và ẩn phiên hội thoại thành công"}


# =========================================================================
# 3. CẤU HÌNH HỆ THỐNG & FAILOVER (SETTINGS)
# =========================================================================
class SettingsUpdateSchema(BaseModel):
    enabled: Optional[bool] = None
    active_provider: Optional[str] = None
    active_model: Optional[str] = None
    failover_order: Optional[List[str]] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_output_tokens: Optional[int] = Field(None, ge=100, le=4000)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=60)
    max_retries: Optional[int] = Field(None, ge=0, le=5)
    retention_days: Optional[int] = Field(None, ge=7, le=365)


@router.get("/settings", summary="Lấy cấu hình hiện tại của Chatbot (Không lộ Secret)")
def get_chatbot_settings(db: Session = Depends(get_db)):
    st = orchestrator.get_or_create_settings(db)

    # Kiểm tra trạng thái cấu hình của các nhà cung cấp bên ngoài mà KHÔNG trả về API key thật
    gemini_key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "gemini_api_key", None)
    openai_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "openai_api_key", None)
    ollama_url = os.environ.get("OLLAMA_BASE_URL") or getattr(settings, "ollama_base_url", "http://localhost:11434")

    def mask_key(k: Optional[str]) -> str:
        if not k:
            return "Chưa cấu hình"
        clean = k.strip()
        if len(clean) <= 8:
            return "****"
        return f"{clean[:3]}...{clean[-4:]}"

    return {
        "id": st.id,
        "enabled": st.enabled,
        "active_provider": st.active_provider,
        "active_model": st.active_model,
        "failover_order": json.loads(st.failover_order) if st.failover_order else [],
        "temperature": st.temperature,
        "max_output_tokens": st.max_output_tokens,
        "timeout_seconds": st.timeout_seconds,
        "max_retries": st.max_retries,
        "retention_days": st.retention_days,
        "system_prompt_version_id": st.system_prompt_version_id,
        "updated_at": st.updated_at,
        "providers_config_status": {
            "gemini": {
                "configured": bool(gemini_key),
                "masked_key": mask_key(gemini_key),
            },
            "openai": {
                "configured": bool(openai_key),
                "masked_key": mask_key(openai_key),
            },
            "ollama": {
                "configured": bool(ollama_url),
                "base_url": ollama_url,
            },
            "h4care_expert": {
                "configured": True,
                "masked_key": "Hệ thống nội bộ",
            },
        },
    }


@router.patch("/settings", summary="Cập nhật cấu hình Chatbot AI")
def update_chatbot_settings(
    body: SettingsUpdateSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    st = orchestrator.get_or_create_settings(db)
    old_data = {
        "enabled": st.enabled,
        "active_provider": st.active_provider,
        "active_model": st.active_model,
        "failover_order": st.failover_order,
        "temperature": st.temperature,
        "max_output_tokens": st.max_output_tokens,
        "timeout_seconds": st.timeout_seconds,
    }

    if body.enabled is not None:
        st.enabled = body.enabled
    if body.active_provider is not None:
        st.active_provider = body.active_provider
    if body.active_model is not None:
        st.active_model = body.active_model
    if body.failover_order is not None:
        st.failover_order = json.dumps(body.failover_order)
    if body.temperature is not None:
        st.temperature = body.temperature
    if body.max_output_tokens is not None:
        st.max_output_tokens = body.max_output_tokens
    if body.timeout_seconds is not None:
        st.timeout_seconds = body.timeout_seconds
    if body.max_retries is not None:
        st.max_retries = body.max_retries
    if body.retention_days is not None:
        st.retention_days = body.retention_days

    st.updated_by = admin.id
    st.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(st)

    new_data = {
        "enabled": st.enabled,
        "active_provider": st.active_provider,
        "active_model": st.active_model,
        "failover_order": st.failover_order,
        "temperature": st.temperature,
        "max_output_tokens": st.max_output_tokens,
        "timeout_seconds": st.timeout_seconds,
    }

    log_admin_action(db, admin, "UPDATE_SETTINGS", "ChatbotSettings", str(st.id), old_data, new_data)

    return {"message": "Cập nhật cấu hình Chatbot thành công", "settings": st}


class ApiKeyUpdateSchema(BaseModel):
    provider: str = Field(..., pattern="^(gemini|openai)$", description="Tên nhà cung cấp (gemini hoặc openai)")
    api_key: str = Field(..., min_length=10, max_length=200, description="Giá trị API Key mới")


@router.post("/api-keys", summary="Lưu và kích hoạt trực tiếp API Key cho Google Gemini hoặc OpenAI")
def update_provider_api_key(
    body: ApiKeyUpdateSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Cho phép Quản trị viên cập nhật API Key từ giao diện web Admin:
    - Lưu vào môi trường RAM (os.environ, settings) để có hiệu lực ngay lập tức.
    - Lưu vào file .env ở thư mục gốc để duy trì qua các lần khởi động lại.
    - Không trả lại toàn bộ API Key về client; chỉ trả masked preview an toàn.
    """
    key = body.api_key.strip()
    provider = body.provider.lower().strip()
    env_var_name = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"

    # 1. Cập nhật vào runtime
    os.environ[env_var_name] = key
    if provider == "gemini":
        setattr(settings, "gemini_api_key", key)
    else:
        setattr(settings, "openai_api_key", key)

    # 2. Ghi đè hoặc thêm vào file .env ở thư mục gốc
    try:
        from app.core.config import _REPO_ROOT
        repo_root = _REPO_ROOT
        env_file = repo_root / ".env"
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8")
            pattern = rf"^{env_var_name}=.*$"
            if re.search(pattern, content, flags=re.MULTILINE):
                new_content = re.sub(pattern, f"{env_var_name}={key}", content, flags=re.MULTILINE)
            else:
                new_content = content.rstrip() + f"\n{env_var_name}={key}\n"
            env_file.write_text(new_content, encoding="utf-8")
    except Exception:
        pass

    # 3. Tạo preview masked an toàn
    masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"

    log_admin_action(
        db, admin, "UPDATE_API_KEY", f"Provider_{provider}", None, None, {"provider": provider, "masked_key": masked}
    )

    return {
        "success": True,
        "provider": provider,
        "masked_key": masked,
        "message": f"Đã lưu và kích hoạt API Key cho {provider.upper()} thành công!",
    }


# =========================================================================
# 4. TRẠNG THÁI & KIỂM TRA PROVIDERS
# =========================================================================
@router.get("/providers", summary="Trạng thái sức khỏe thời gian thực của các AI Provider")
async def get_providers_status():
    statuses = await orchestrator.check_all_providers()
    return {"providers": statuses}


class ProviderTestSchema(BaseModel):
    provider: str
    model: Optional[str] = None
    prompt: Optional[str] = "Xin chào Dược sĩ, Paracetamol dùng liều thế nào?"


@router.post("/providers/test", summary="Kiểm thử kết nối đến một Provider cụ thể")
async def test_provider_connection(
    body: ProviderTestSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    provider = orchestrator.get_provider(body.provider)
    if not provider:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provider '{body.provider}' không tồn tại")

    start = time.perf_counter()
    res = await provider.generate_response(
        system_prompt="Bạn là Dược sĩ H4CARE. Trả lời ngắn gọn 1 câu để kiểm tra kết nối.",
        user_message=body.prompt,
        conversation_history=[],
        model=body.model,
        timeout_seconds=15,
    )
    latency = int((time.perf_counter() - start) * 1000)

    log_admin_action(
        db,
        admin,
        "TEST_PROVIDER",
        "AIProvider",
        body.provider,
        {"model": body.model},
        {"result": res.result, "latency_ms": latency, "http_status": res.http_status},
    )

    return {
        "provider": body.provider,
        "model": res.model,
        "latency_ms": latency,
        "http_status": res.http_status,
        "result": res.result,
        "text_preview": res.text[:200] if res.text else "",
        "safe_error_message": res.safe_error_message,
        "success": res.result == "success",
    }


# =========================================================================
# 5. QUẢN LÝ PHIÊN BẢN SYSTEM PROMPT (VERSIONING)
# =========================================================================
class PromptVersionCreateSchema(BaseModel):
    version: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    content: str
    change_note: Optional[str] = None


@router.get("/prompts", summary="Danh sách phiên bản System Prompt")
def list_prompt_versions(db: Session = Depends(get_db)):
    versions = db.scalars(select(ChatPromptVersion).order_by(desc(ChatPromptVersion.id))).all()
    st = orchestrator.get_or_create_settings(db)

    return {
        "active_version_id": st.system_prompt_version_id,
        "items": [
            {
                "id": v.id,
                "version": v.version,
                "name": v.name,
                "content": v.content,
                "status": v.status,
                "change_note": v.change_note,
                "created_at": v.created_at,
                "creator_name": v.creator.full_name if v.creator else "Hệ thống",
                "published_at": v.published_at,
                "publisher_name": v.publisher.full_name if v.publisher else None,
                "is_active": v.id == st.system_prompt_version_id,
            }
            for v in versions
        ],
    }


@router.post("/prompts", summary="Tạo phiên bản System Prompt mới dạng Draft")
def create_prompt_version(
    body: PromptVersionCreateSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = db.scalar(select(ChatPromptVersion).where(ChatPromptVersion.version == body.version.strip()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã phiên bản '{body.version}' đã tồn tại. Vui lòng tăng số phiên bản (ví dụ v1.2 -> v1.3).",
        )

    pv = ChatPromptVersion(
        version=body.version.strip(),
        name=body.name.strip(),
        content=body.content.strip(),
        status="draft",
        change_note=body.change_note,
        created_by=admin.id,
    )
    db.add(pv)
    db.commit()
    db.refresh(pv)

    log_admin_action(db, admin, "CREATE_PROMPT_VERSION", "ChatPromptVersion", str(pv.id), None, {"version": pv.version})

    return {"message": "Đã tạo bản nháp System Prompt thành công", "prompt_version": pv}


@router.post("/prompts/{version_id}/publish", summary="Xuất bản (Publish) một phiên bản System Prompt")
def publish_prompt_version(
    version_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.scalar(select(ChatPromptVersion).where(ChatPromptVersion.id == version_id))
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên bản prompt")

    st = orchestrator.get_or_create_settings(db)
    old_version_id = st.system_prompt_version_id

    # Đưa các phiên bản đã publish trước đó về archived
    db.query(ChatPromptVersion).filter(ChatPromptVersion.status == "published").update({"status": "archived"})

    target.status = "published"
    target.published_by = admin.id
    target.published_at = datetime.now(UTC)

    st.system_prompt_version_id = target.id
    st.updated_at = datetime.now(UTC)
    st.updated_by = admin.id

    db.commit()

    log_admin_action(
        db,
        admin,
        "PUBLISH_PROMPT_VERSION",
        "ChatPromptVersion",
        str(target.id),
        {"old_active_id": old_version_id},
        {"new_active_id": target.id, "version": target.version},
    )

    return {"message": f"Đã xuất bản thành công phiên bản prompt {target.version}", "prompt_version": target}


@router.post("/prompts/{version_id}/rollback", summary="Rollback về một phiên bản Prompt đã có")
def rollback_prompt_version(
    version_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.scalar(select(ChatPromptVersion).where(ChatPromptVersion.id == version_id))
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên bản prompt cần rollback")

    st = orchestrator.get_or_create_settings(db)
    old_version_id = st.system_prompt_version_id

    # Đánh dấu phiên bản này là published
    target.status = "published"
    st.system_prompt_version_id = target.id
    st.updated_at = datetime.now(UTC)
    st.updated_by = admin.id

    db.commit()

    log_admin_action(
        db,
        admin,
        "ROLLBACK_PROMPT_VERSION",
        "ChatPromptVersion",
        str(target.id),
        {"previous_version_id": old_version_id},
        {"restored_version_id": target.id, "version": target.version},
    )

    return {"message": f"Đã rollback về phiên bản {target.version} thành công", "prompt_version": target}


# =========================================================================
# 6. QUẢN LÝ KHO TRI THỨC Y TẾ (KNOWLEDGE BASE)
# =========================================================================
class KnowledgeSourceCreateSchema(BaseModel):
    title: str = Field(..., max_length=255)
    source_type: str = Field(default="manual_faq")  # official_url, manual_faq, policy, product_database
    source_url: Optional[str] = None
    publisher: Optional[str] = None
    version: Optional[str] = None


class KnowledgeItemCreateSchema(BaseModel):
    source_id: Optional[int] = None
    title: str = Field(..., max_length=255)
    question: Optional[str] = None
    answer: Optional[str] = None
    content: str
    category: str = Field(default="duoc_ly")  # trieu_chung, duoc_ly, chinh_sach, huong_dan
    keywords: Optional[str] = None
    is_active: bool = True
    product_id: Optional[int] = None


@router.get("/knowledge/sources", summary="Danh sách nguồn dữ liệu tri thức")
def list_knowledge_sources(db: Session = Depends(get_db)):
    sources = db.scalars(select(ChatKnowledgeSource).order_by(desc(ChatKnowledgeSource.id))).all()
    return {
        "items": [
            {
                "id": s.id,
                "title": s.title,
                "source_type": s.source_type,
                "source_url": s.source_url,
                "publisher": s.publisher,
                "version": s.version,
                "status": s.status,
                "medical_review_status": s.medical_review_status,
                "items_count": len(s.items),
                "created_at": s.created_at,
            }
            for s in sources
        ]
    }


@router.post("/knowledge/sources", summary="Tạo mới nguồn dữ liệu tri thức")
def create_knowledge_source(
    body: KnowledgeSourceCreateSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ks = ChatKnowledgeSource(
        title=body.title.strip(),
        source_type=body.source_type,
        source_url=body.source_url,
        publisher=body.publisher,
        version=body.version,
        status="approved",
        medical_review_status="reviewed",
        created_by=admin.id,
        approved_by=admin.id,
    )
    db.add(ks)
    db.commit()
    db.refresh(ks)

    log_admin_action(db, admin, "CREATE_KNOWLEDGE_SOURCE", "ChatKnowledgeSource", str(ks.id), None, {"title": ks.title})
    return {"message": "Tạo nguồn tri thức thành công", "source": ks}


@router.get("/knowledge/items", summary="Danh sách các mục tri thức y tế")
def list_knowledge_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    source_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = select(ChatKnowledgeItem)
    if category:
        query = query.where(ChatKnowledgeItem.category == category)
    if source_id:
        query = query.where(ChatKnowledgeItem.source_id == source_id)
    if search:
        query = query.where(
            or_(
                ChatKnowledgeItem.title.ilike(f"%{search}%"),
                ChatKnowledgeItem.question.ilike(f"%{search}%"),
                ChatKnowledgeItem.keywords.ilike(f"%{search}%"),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(desc(ChatKnowledgeItem.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": it.id,
                "source_id": it.source_id,
                "source_title": it.source.title if it.source else None,
                "title": it.title,
                "question": it.question,
                "answer": it.answer,
                "content": it.content,
                "category": it.category,
                "keywords": it.keywords,
                "is_active": it.is_active,
                "created_at": it.created_at,
            }
            for it in items
        ],
    }


@router.post("/knowledge/items", summary="Tạo mới mục tri thức y tế")
def create_knowledge_item(
    body: KnowledgeItemCreateSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    it = ChatKnowledgeItem(
        source_id=body.source_id,
        title=body.title.strip(),
        question=body.question.strip() if body.question else None,
        answer=body.answer.strip() if body.answer else None,
        content=body.content.strip(),
        category=body.category,
        keywords=body.keywords,
        is_active=body.is_active,
        product_id=body.product_id,
        created_by=admin.id,
    )
    db.add(it)
    db.commit()
    db.refresh(it)

    log_admin_action(db, admin, "CREATE_KNOWLEDGE_ITEM", "ChatKnowledgeItem", str(it.id), None, {"title": it.title})
    return {"message": "Đã thêm mục tri thức mới thành công", "item": it}


@router.put("/knowledge/items/{item_id}", summary="Cập nhật mục tri thức")
def update_knowledge_item(
    item_id: int,
    body: KnowledgeItemCreateSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    it = db.scalar(select(ChatKnowledgeItem).where(ChatKnowledgeItem.id == item_id))
    if not it:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục tri thức")

    it.title = body.title.strip()
    it.question = body.question.strip() if body.question else None
    it.answer = body.answer.strip() if body.answer else None
    it.content = body.content.strip()
    it.category = body.category
    it.keywords = body.keywords
    it.is_active = body.is_active
    it.product_id = body.product_id
    it.updated_by = admin.id
    it.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(it)

    log_admin_action(db, admin, "UPDATE_KNOWLEDGE_ITEM", "ChatKnowledgeItem", str(it.id), None, {"title": it.title})
    return {"message": "Đã cập nhật mục tri thức thành công", "item": it}


@router.delete("/knowledge/items/{item_id}", summary="Xóa mục tri thức")
def delete_knowledge_item(
    item_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    it = db.scalar(select(ChatKnowledgeItem).where(ChatKnowledgeItem.id == item_id))
    if not it:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục tri thức cần xóa")

    title = it.title
    db.delete(it)
    db.commit()

    log_admin_action(db, admin, "DELETE_KNOWLEDGE_ITEM", "ChatKnowledgeItem", str(item_id), {"title": title}, None)
    return {"message": "Đã xóa mục tri thức thành công"}


# =========================================================================
# 7. NHẬT KÝ LỖI, FAILOVER & AUDIT LOGS
# =========================================================================
@router.get("/logs/errors", summary="Danh sách vết chuyển mạch failover và lỗi Provider")
def list_provider_error_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = select(ChatProviderAttempt).where(ChatProviderAttempt.result != "success")
    if provider:
        query = query.where(ChatProviderAttempt.provider == provider)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    logs = db.scalars(
        query.order_by(desc(ChatProviderAttempt.started_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": l.id,
                "session_id": l.session_id,
                "message_id": l.message_id,
                "provider": l.provider,
                "model": l.model,
                "attempt_number": l.attempt_number,
                "latency_ms": l.latency_ms,
                "http_status": l.http_status,
                "result": l.result,
                "safe_error_message": l.safe_error_message,
                "correlation_id": l.correlation_id,
                "started_at": l.started_at,
            }
            for l in logs
        ],
    }


@router.get("/audit-logs", summary="Nhật ký thao tác quản trị Chatbot của Admin")
def list_chatbot_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    action: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = select(ChatbotAuditLog)
    if action:
        query = query.where(ChatbotAuditLog.action == action)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    logs = db.scalars(
        query.order_by(desc(ChatbotAuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": l.id,
                "admin_id": l.admin_id,
                "admin_name": l.admin.full_name if l.admin else "Quản trị viên",
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "old_values": json.loads(l.old_values) if l.old_values else None,
                "new_values": json.loads(l.new_values) if l.new_values else None,
                "result": l.result,
                "correlation_id": l.correlation_id,
                "created_at": l.created_at,
            }
            for l in logs
        ],
    }


# =========================================================================
# 8. BÀN KIỂM THỬ AN TOÀN Y TẾ (TEST CONSOLE)
# =========================================================================
class TestConsoleRequestSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None


@router.post("/test-console", summary="Kiểm thử câu hỏi và đánh giá Checklist an toàn Y tế")
async def run_test_console(
    body: TestConsoleRequestSchema,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    st = orchestrator.get_or_create_settings(db)
    target_provider = body.provider or st.active_provider or "gemini"
    target_model = body.model or (st.active_model if target_provider == st.active_provider else None)
    prompt_to_use = body.system_prompt or orchestrator.get_active_system_prompt(db, st)[0]

    provider = orchestrator.get_provider(target_provider) or orchestrator.get_provider("h4care_expert")

    start = time.perf_counter()
    res = await provider.generate_response(
        system_prompt=prompt_to_use,
        user_message=body.message,
        conversation_history=[],
        model=target_model,
        timeout_seconds=20,
    )
    latency = int((time.perf_counter() - start) * 1000)

    # Đánh giá Checklist Y tế an toàn
    norm_text = remove_vietnamese_accents(res.text)
    norm_query = remove_vietnamese_accents(body.message)

    checklist = {
        "emergency_advice_included": ("115" in res.text) or ("cap cuu" in norm_text) or ("benh vien" in norm_text),
        "pharmacist_hotline_included": ("1800" in res.text) or ("duoc si" in norm_text),
        "no_rx_prescription": not any(kw in norm_text for kw in ["ke don thuoc", "don thuoc cua toi la"]),
        "safe_dosage_warning": ("lieu" in norm_text) or ("huong dan" in norm_text),
        "paracetamol_overdose_safe": ("4g" in res.text) or ("4000mg" in res.text) or ("gan" in norm_text) if "paracetamol" in norm_query else True,
    }

    passed_count = sum(1 for v in checklist.values() if v)
    total_checks = len(checklist)

    log_admin_action(
        db,
        admin,
        "RUN_TEST_CONSOLE",
        "TestConsole",
        target_provider,
        {"query": body.message[:50]},
        {"result": res.result, "safety_score": f"{passed_count}/{total_checks}"},
    )

    return {
        "provider": res.provider,
        "model": res.model,
        "latency_ms": latency,
        "http_status": res.http_status,
        "result": res.result,
        "reply": res.text,
        "safety_flags": res.safety_flags,
        "safe_error_message": res.safe_error_message,
        "checklist": checklist,
        "safety_score_percentage": round(passed_count / total_checks * 100, 1),
    }
