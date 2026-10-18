"""Migration: Live Chat System between Customers and Staff.

Revision ID: 0011_live_chat_system
Revises: 0010_warehouse_notifications
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_live_chat_system"
down_revision = "0010_warehouse_notifications"
branch_labels = None
depends_on = None


def _get_existing_tables(conn) -> set[str]:
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    if "live_chat_sessions" not in tables:
        op.create_table(
            "live_chat_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_code", sa.String(64), unique=True, nullable=False, index=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("customer_name", sa.String(255), server_default="Khách hàng", nullable=False),
            sa.Column("customer_email", sa.String(255), nullable=True),
            sa.Column("customer_phone", sa.String(50), nullable=True),
            sa.Column("guest_session_token", sa.String(128), nullable=True, index=True),
            sa.Column("assigned_staff_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("status", sa.String(30), server_default="WAITING", nullable=False, index=True),
            sa.Column("subject", sa.String(255), nullable=True),
            sa.Column("initial_context", sa.Text(), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
        )

    if "live_chat_messages" not in tables:
        op.create_table(
            "live_chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("live_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("sender_type", sa.String(20), nullable=False, index=True),
            sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("sender_name", sa.String(255), nullable=False),
            sa.Column("sender_role_title", sa.String(100), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("attachment_url", sa.String(1000), nullable=True),
            sa.Column("attachment_type", sa.String(50), nullable=True),
            sa.Column("is_read", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("client_msg_id", sa.String(64), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)
    if "live_chat_messages" in tables:
        op.drop_table("live_chat_messages")
    if "live_chat_sessions" in tables:
        op.drop_table("live_chat_sessions")
