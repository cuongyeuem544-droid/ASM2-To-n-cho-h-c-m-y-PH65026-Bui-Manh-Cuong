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

    # Backfill idempotency_key cho dữ liệu DISPATCH lịch sử
    dispatch_rows = conn.execute(
        sa.text(
            "SELECT sm.id, sm.reference_id, sm.batch_id, f.id "
            "FROM stock_movements sm "
            "LEFT JOIN order_fulfillments f ON f.fulfillment_code = sm.reference_id "
            "WHERE sm.movement_type = 'DISPATCH' AND (sm.idempotency_key IS NULL OR sm.idempotency_key = '')"
        )
    ).fetchall()

    for row in dispatch_rows:
        sm_id, ref_id, batch_id, ff_id = row
        key_target_id = ff_id if ff_id else ref_id
        if key_target_id and batch_id:
            key = f"DISPATCH:{key_target_id}:{batch_id}"
            # Tránh lỗi trùng nếu có trùng dữ liệu lịch sử
            exists = conn.execute(
                sa.text("SELECT id FROM stock_movements WHERE idempotency_key = :k AND id != :id"),
                {"k": key, "id": sm_id},
            ).fetchone()
            if not exists:
                conn.execute(
                    sa.text("UPDATE stock_movements SET idempotency_key = :k WHERE id = :id"),
                    {"k": key, "id": sm_id},
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("stock_movements")}

    if "idempotency_key" in existing_cols:
        op.drop_index("ix_stock_movements_idempotency_key", table_name="stock_movements")
        op.drop_column("stock_movements", "idempotency_key")
