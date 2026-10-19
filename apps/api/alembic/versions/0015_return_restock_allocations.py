"""Migration: Return Restock Allocations with Multi-Batch Idempotency.

Revision ID: 0015_return_restock_allocations
Revises: 0014_live_chat_attachments
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_return_restock_allocations"
down_revision = "0014_live_chat_attachments"
branch_labels = None
depends_on = None


def _get_existing_tables(conn) -> set[str]:
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    if "return_restock_allocations" not in tables:
        op.create_table(
            "return_restock_allocations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("canonical_return_code", sa.String(50), nullable=False, index=True),
            sa.Column("source_type", sa.String(50), nullable=False),
            sa.Column("source_code", sa.String(50), nullable=False, index=True),
            sa.Column("order_item_id", sa.Integer(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("stock_movement_id", sa.Integer(), sa.ForeignKey("stock_movements.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("canonical_return_code", "order_item_id", "batch_id", name="uq_restock_canonical_item_batch"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)
    if "return_restock_allocations" in tables:
        op.drop_table("return_restock_allocations")
