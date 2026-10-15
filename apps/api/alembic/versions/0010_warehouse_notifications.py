"""Migration: Warehouse Notifications for Warehouse Managers and Staff.

Revision ID: 0010_warehouse_notifications
Revises: 0009_return_evidence_requests
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_warehouse_notifications"
down_revision = "0009_return_evidence_requests"
branch_labels = None
depends_on = None


def _get_existing_tables(conn) -> set[str]:
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def _get_existing_indexes(conn, table_name: str) -> set[str]:
    inspector = sa.inspect(conn)
    try:
        return {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    if "warehouse_notifications" not in tables:
        op.create_table(
            "warehouse_notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("notification_type", sa.String(50), nullable=False, index=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(20), server_default="INFO", nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=True),
            sa.Column("entity_id", sa.String(100), nullable=True),
            sa.Column("action_url", sa.String(255), nullable=True),
            sa.Column("is_read", sa.Boolean(), server_default=sa.text("0"), nullable=False, index=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
            sa.Column("deduplication_key", sa.String(150), unique=True, index=True, nullable=True),
        )

        op.create_index(
            "ix_wh_notif_wh_recip_read",
            "warehouse_notifications",
            ["warehouse_id", "recipient_user_id", "is_read"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)
    if "warehouse_notifications" in tables:
        op.drop_table("warehouse_notifications")
