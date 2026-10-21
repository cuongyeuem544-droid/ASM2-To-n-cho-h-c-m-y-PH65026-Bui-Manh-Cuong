"""Migration: SePay Payment Integration and Inbound Transaction Deduplication.

Revision ID: 0020_sepay_payment_integration
Revises: 0019_remove_unsafe_inspection_defaults
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_sepay_payment_integration"
down_revision = "0019_remove_unsafe_inspection_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Bảng sepay_payment_codes: Lưu mã định danh thanh toán duy nhất HC + 8 số cho mỗi đơn hàng
    if "sepay_payment_codes" not in tables:
        op.create_table(
            "sepay_payment_codes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payment_code", sa.String(20), nullable=False),
            sa.Column("code_number", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index(
            "ix_sepay_payment_codes_payment_code",
            "sepay_payment_codes",
            ["payment_code"],
            unique=True,
        )
        op.create_index(
            "ix_sepay_payment_codes_code_number",
            "sepay_payment_codes",
            ["code_number"],
            unique=True,
        )
        op.create_index(
            "ix_sepay_payment_codes_order_id",
            "sepay_payment_codes",
            ["order_id"],
            unique=True,
        )

    # 2. Bảng sepay_inbound_transactions: Lưu vết giao dịch SePay webhook và chống trùng lặp tuyệt đối
    if "sepay_inbound_transactions" not in tables:
        op.create_table(
            "sepay_inbound_transactions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("sepay_id", sa.BigInteger(), nullable=False),
            sa.Column("gateway", sa.String(50), nullable=True),
            sa.Column("account_number", sa.String(50), nullable=False),
            sa.Column("transfer_type", sa.String(20), nullable=False),
            sa.Column("transfer_amount", sa.BigInteger(), nullable=False),
            sa.Column("accumulated", sa.BigInteger(), nullable=True),
            sa.Column("code", sa.String(50), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("reference_code", sa.String(100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="PROCESSED"),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("raw_payload", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index(
            "ix_sepay_inbound_transactions_sepay_id",
            "sepay_inbound_transactions",
            ["sepay_id"],
            unique=True,
        )
        op.create_index(
            "ix_sepay_inbound_transactions_account_number",
            "sepay_inbound_transactions",
            ["account_number"],
        )
        op.create_index(
            "ix_sepay_inbound_transactions_code",
            "sepay_inbound_transactions",
            ["code"],
        )
        op.create_index(
            "ix_sepay_inbound_transactions_order_id",
            "sepay_inbound_transactions",
            ["order_id"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "sepay_inbound_transactions" in tables:
        op.drop_table("sepay_inbound_transactions")

    if "sepay_payment_codes" in tables:
        op.drop_table("sepay_payment_codes")
