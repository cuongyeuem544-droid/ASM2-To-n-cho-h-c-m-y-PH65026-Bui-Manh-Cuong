"""Migration: Payment Expiry Management and Multi-Gateway Reconciliation.

Revision ID: 0021_payment_expiry_and_reconciliation
Revises: 0020_sepay_payment_integration
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_payment_expiry_and_reconciliation"
down_revision = "0020_sepay_payment_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Bảng payment_transactions: Thêm expires_at cho Payment Intent
    if "payment_transactions" in tables:
        cols = [c["name"] for c in inspector.get_columns("payment_transactions")]
        if "expires_at" not in cols:
            op.add_column(
                "payment_transactions",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )

    # 2. Bảng sepay_payment_codes: Thêm expires_at và status
    if "sepay_payment_codes" in tables:
        cols = [c["name"] for c in inspector.get_columns("sepay_payment_codes")]
        if "expires_at" not in cols:
            op.add_column(
                "sepay_payment_codes",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "status" not in cols:
            op.add_column(
                "sepay_payment_codes",
                sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
            )

    # 3. Bảng payos_order_codes: Thêm expires_at và status
    if "payos_order_codes" in tables:
        cols = [c["name"] for c in inspector.get_columns("payos_order_codes")]
        if "expires_at" not in cols:
            op.add_column(
                "payos_order_codes",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "status" not in cols:
            op.add_column(
                "payos_order_codes",
                sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "payos_order_codes" in tables:
        cols = [c["name"] for c in inspector.get_columns("payos_order_codes")]
        if "status" in cols:
            op.drop_column("payos_order_codes", "status")
        if "expires_at" in cols:
            op.drop_column("payos_order_codes", "expires_at")

    if "sepay_payment_codes" in tables:
        cols = [c["name"] for c in inspector.get_columns("sepay_payment_codes")]
        if "status" in cols:
            op.drop_column("sepay_payment_codes", "status")
        if "expires_at" in cols:
            op.drop_column("sepay_payment_codes", "expires_at")

    if "payment_transactions" in tables:
        cols = [c["name"] for c in inspector.get_columns("payment_transactions")]
        if "expires_at" in cols:
            op.drop_column("payment_transactions", "expires_at")
