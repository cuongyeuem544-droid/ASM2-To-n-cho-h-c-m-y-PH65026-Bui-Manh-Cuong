from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class LiveChatSession(Base):
    __tablename__ = "live_chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), default="Khách hàng")
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    guest_session_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    assigned_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="WAITING", index=True)  # WAITING, ACTIVE, CLOSED
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    initial_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Relationships
    customer = relationship("User", foreign_keys=[customer_id])
    assigned_staff = relationship("User", foreign_keys=[assigned_staff_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    messages = relationship(
        "LiveChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LiveChatMessage.created_at.asc()",
    )
    attachments = relationship(
        "LiveChatAttachment",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class LiveChatMessage(Base):
    __tablename__ = "live_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("live_chat_sessions.id", ondelete="CASCADE"), index=True)
    sender_type: Mapped[str] = mapped_column(String(20), index=True)  # CUSTOMER, STAFF, SYSTEM
    sender_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    sender_name: Mapped[str] = mapped_column(String(255))
    sender_role_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    content: Mapped[str] = mapped_column(Text)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    attachment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    client_msg_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Relationships
    session = relationship("LiveChatSession", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])


class AIChatConversation(Base):
    __tablename__ = "ai_chat_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255), default="Cuộc trò chuyện mới")
    extracted_memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON serialized
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    messages = relationship(
        "AIChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIChatMessage.created_at.asc()",
    )
    attachments = relationship(
        "AIChatAttachment",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_chat_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), index=True)  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text)
    attachments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    safety_alert_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quick_replies_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_products_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Relationships
    conversation = relationship("AIChatConversation", back_populates="messages")


class AIChatAttachment(Base):
    __tablename__ = "ai_chat_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    attachment_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ai_chat_conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ai_chat_messages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Relationships
    conversation = relationship("AIChatConversation", back_populates="attachments")
    user = relationship("User", foreign_keys=[user_id])


class LiveChatAttachment(Base):
    __tablename__ = "live_chat_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    attachment_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("live_chat_sessions.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("live_chat_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Relationships
    session = relationship("LiveChatSession", back_populates="attachments")
    message = relationship("LiveChatMessage")
    uploader = relationship("User", foreign_keys=[user_id])

