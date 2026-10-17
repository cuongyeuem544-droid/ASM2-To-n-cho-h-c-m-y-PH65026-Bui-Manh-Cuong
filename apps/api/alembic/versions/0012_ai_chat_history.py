"""Migration: AI Chat Conversations, Messages, and Attachments History.

Revision ID: 0012_ai_chat_history
Revises: 0011_live_chat_system
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_ai_chat_history"
down_revision = "0011_live_chat_system"
branch_labels = None
depends_on = None


def _get_existing_tables(conn) -> set[str]:
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    if "ai_chat_conversations" not in tables:
        op.create_table(
            "ai_chat_conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_code", sa.String(64), unique=True, nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("session_id", sa.String(128), nullable=False, index=True),
            sa.Column("title", sa.String(255), server_default="Cuộc trò chuyện mới", nullable=False),
            sa.Column("extracted_memory", sa.Text(), nullable=True),
            sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("is_archived", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    if "ai_chat_messages" not in tables:
        op.create_table(
            "ai_chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("role", sa.String(20), nullable=False, index=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("attachments_json", sa.Text(), nullable=True),
            sa.Column("safety_alert_json", sa.Text(), nullable=True),
            sa.Column("quick_replies_json", sa.Text(), nullable=True),
            sa.Column("recommended_products_json", sa.Text(), nullable=True),
            sa.Column("api_status", sa.String(50), nullable=True),
            sa.Column("model_used", sa.String(50), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
        )

    if "ai_chat_attachments" not in tables:
        op.create_table(
            "ai_chat_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attachment_code", sa.String(64), unique=True, nullable=False, index=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_chat_conversations.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("ai_chat_messages.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("session_id", sa.String(128), nullable=True, index=True),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_filename", sa.String(255), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)
    if "ai_chat_attachments" in tables:
        op.drop_table("ai_chat_attachments")
    if "ai_chat_messages" in tables:
        op.drop_table("ai_chat_messages")
    if "ai_chat_conversations" in tables:
        op.drop_table("ai_chat_conversations")
