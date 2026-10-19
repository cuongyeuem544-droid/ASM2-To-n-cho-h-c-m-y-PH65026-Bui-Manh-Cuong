"""Migration: Live Chat Attachments with Strict Session Binding.

Revision ID: 0014_live_chat_attachments
Revises: 0013_chatbot_admin_and_knowledge
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_live_chat_attachments"
down_revision = "0013_chatbot_admin_and_knowledge"
branch_labels = None
depends_on = None


def _get_existing_tables(conn) -> set[str]:
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    if "live_chat_attachments" not in tables:
        op.create_table(
            "live_chat_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attachment_code", sa.String(64), unique=True, nullable=False, index=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("live_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("live_chat_messages.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_filename", sa.String(255), nullable=False),
            sa.Column("file_path", sa.String(1000), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)
    if "live_chat_attachments" in tables:
        op.drop_table("live_chat_attachments")
