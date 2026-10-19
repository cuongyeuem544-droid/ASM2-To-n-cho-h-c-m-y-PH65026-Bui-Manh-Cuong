"""Migration: Stock Movement Idempotency Key.

Revision ID: 0016_stock_movement_idempotency_key
Revises: 0015_return_restock_allocations
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_stock_movement_idempotency_key"
down_revision = "0015_return_restock_allocations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("stock_movements")}

    if "idempotency_key" not in existing_cols:
        op.add_column(
            "stock_movements",
            sa.Column("idempotency_key", sa.String(150), nullable=True),
        )
        op.create_index(
            "ix_stock_movements_idempotency_key",
            "stock_movements",
            ["idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("stock_movements")}

    if "idempotency_key" in existing_cols:
        op.drop_index("ix_stock_movements_idempotency_key", table_name="stock_movements")
        op.drop_column("stock_movements", "idempotency_key")
