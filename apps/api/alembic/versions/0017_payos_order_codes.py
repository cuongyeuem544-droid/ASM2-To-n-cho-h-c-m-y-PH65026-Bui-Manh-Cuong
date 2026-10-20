"""Migration: payOS Unique Order Codes Sequence Table.

Revision ID: 0017_payos_order_codes
Revises: 0016_stock_movement_idempotency_key
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_payos_order_codes"
down_revision = "0016_stock_movement_idempotency_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "payos_order_codes" not in tables:
        op.create_table(
            "payos_order_codes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("order_code_num", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index(
            "ix_payos_order_codes_order_code_num",
            "payos_order_codes",
            ["order_code_num"],
            unique=True,
        )

    # Backfill các giao dịch payOS lịch sử từ payment_transactions
    existing_payos_txs = conn.execute(
        sa.text(
            "SELECT order_id, provider_trans_id, created_at "
            "FROM payment_transactions "
            "WHERE provider = 'PAYOS' AND provider_trans_id IS NOT NULL AND provider_trans_id != ''"
        )
    ).fetchall()

    for row in existing_payos_txs:
        ord_id, trans_id_str, c_at = row
        try:
            code_num = int(trans_id_str)
            exists = conn.execute(
                sa.text("SELECT id FROM payos_order_codes WHERE order_code_num = :c"),
                {"c": code_num},
            ).fetchone()
            if not exists:
                conn.execute(
                    sa.text(
                        "INSERT INTO payos_order_codes (order_id, order_code_num, created_at) "
                        "VALUES (:oid, :c, :cat)"
                    ),
                    {"oid": ord_id, "c": code_num, "cat": c_at},
                )
        except (ValueError, TypeError):
            continue


def downgrade() -> None:
    op.drop_table("payos_order_codes")
