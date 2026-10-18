from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class ChatbotSettings(Base):
    """
    Cấu hình Chatbot Dược sĩ AI (Không chứa API key hoặc secret).
    """
    __tablename__ = "chatbot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active_provider: Mapped[str] = mapped_column(String(50), default="gemini", nullable=False)
    active_model: Mapped[str] = mapped_column(String(100), default="gemini-1.5-flash", nullable=False)
    failover_order: Mapped[str] = mapped_column(
        String(255),
        default='["gemini", "openai", "ollama", "h4care_expert"]',
        nullable=False,
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=800, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    system_prompt_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_prompt_versions.id"), nullable=True
    )
    retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    active_prompt_version: Mapped[Optional[ChatPromptVersion]] = relationship(
        "ChatPromptVersion", foreign_keys=[system_prompt_version_id]
    )
    updater: Mapped[Optional[Any]] = relationship("User", foreign_keys=[updated_by])


class ChatPromptVersion(Base):
    """
    Quản lý phiên bản System Prompt an toàn y tế cho Dược sĩ AI.
    Không chỉnh sửa trực tiếp phiên bản đã publish.
    """
    __tablename__ = "chat_prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)  # draft, published, archived
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    published_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator: Mapped[Optional[Any]] = relationship("User", foreign_keys=[created_by])
    publisher: Mapped[Optional[Any]] = relationship("User", foreign_keys=[published_by])


class ChatSession(Base):
    """
    Phiên hội thoại của khách hàng hoặc khách vãng lai.
    """
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)  # active, closed, flagged, deleted
    channel: Mapped[str] = mapped_column(String(50), default="storefront_widget", nullable=False)
    client_session_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent_summary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    user: Mapped[Optional[Any]] = relationship("User", foreign_keys=[user_id])
    messages: Mapped[List[ChatMessage]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )
    feedbacks: Mapped[List[ChatFeedback]] = relationship(
        "ChatFeedback", back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """
    Từng tin nhắn trong phiên hội thoại.
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="completed", nullable=False)  # pending, completed, blocked, failed
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_prompt_versions.id"), nullable=True
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    safety_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    citations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string of sources/recommended products
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")
    prompt_version: Mapped[Optional[ChatPromptVersion]] = relationship("ChatPromptVersion")
    attempts: Mapped[List[ChatProviderAttempt]] = relationship(
        "ChatProviderAttempt", back_populates="message", cascade="all, delete-orphan"
    )


class ChatProviderAttempt(Base):
    """
    Theo dõi từng lần gọi provider để phân tích độ trễ và vết chuyển mạch (Failover trace).
    """
    __tablename__ = "chat_provider_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_messages.id"), index=True, nullable=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("chat_sessions.id"), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # success, timeout, rate_limited, auth_error, server_error, blocked
    safe_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    # Relationships
    message: Mapped[Optional[ChatMessage]] = relationship("ChatMessage", back_populates="attempts")


class ChatKnowledgeSource(Base):
    """
    Nguồn dữ liệu y tế / chính sách cho Dược sĩ AI.
    """
    __tablename__ = "chat_knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # official_url, file, manual_faq, product_database, policy
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)  # draft, approved, active, archived
    medical_review_status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )  # pending, reviewed, rejected
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    items: Mapped[List[ChatKnowledgeItem]] = relationship(
        "ChatKnowledgeItem", back_populates="source", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional[Any]] = relationship("User", foreign_keys=[created_by])
    approver: Mapped[Optional[Any]] = relationship("User", foreign_keys=[approved_by])


class ChatKnowledgeItem(Base):
    """
    Từng mục tri thức (Hỏi đáp, Hướng dẫn triệu chứng, Thông tin thuốc).
    """
    __tablename__ = "chat_knowledge_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_knowledge_sources.id"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), default="duoc_ly", nullable=False
    )  # trieu_chung, duoc_ly, chinh_sach, huong_dan
    keywords: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("canonical_products.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    source: Mapped[Optional[ChatKnowledgeSource]] = relationship("ChatKnowledgeSource", back_populates="items")
    product: Mapped[Optional[Any]] = relationship("CanonicalProduct", foreign_keys=[product_id])


class ChatFeedback(Base):
    """
    Đánh giá phản hồi của khách hàng đối với câu trả lời.
    """
    __tablename__ = "chat_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), index=True, nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_messages.id"), index=True, nullable=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 hoặc 1: dislike, 5: like
    reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="feedbacks")


class ChatbotAuditLog(Base):
    """
    Nhật ký kiểm toán mọi thao tác quản trị Chatbot (Prompt, Model, Settings, Knowledge).
    """
    __tablename__ = "chatbot_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    old_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    new_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    result: Mapped[str] = mapped_column(String(20), default="SUCCESS", nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    admin: Mapped[Optional[Any]] = relationship("User", foreign_keys=[admin_id])
