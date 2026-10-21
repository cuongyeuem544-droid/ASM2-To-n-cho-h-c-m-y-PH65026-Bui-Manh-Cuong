"""Migration: Return Request Beneficiary Bank Information.

Revision ID: 0018_return_refund_beneficiary
Revises: 0017_payos_order_codes
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_return_refund_beneficiary"
down_revision = "0017_payos_order_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("return_requests")}

    with op.batch_alter_table("return_requests") as batch_op:
        if "refund_bank_code" not in existing_cols:
            batch_op.add_column(sa.Column("refund_bank_code", sa.String(50), nullable=True))
        if "refund_bank_name" not in existing_cols:
            batch_op.add_column(sa.Column("refund_bank_name", sa.String(100), nullable=True))
        if "refund_account_number" not in existing_cols:
            batch_op.add_column(sa.Column("refund_account_number", sa.String(100), nullable=True))
        if "refund_account_name" not in existing_cols:
            batch_op.add_column(sa.Column("refund_account_name", sa.String(255), nullable=True))
        if "refund_beneficiary_submitted_at" not in existing_cols:
            batch_op.add_column(sa.Column("refund_beneficiary_submitted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {col["name"] for col in inspector.get_columns("return_requests")}

    with op.batch_alter_table("return_requests") as batch_op:
        if "refund_beneficiary_submitted_at" in existing_cols:
            batch_op.drop_column("refund_beneficiary_submitted_at")
        if "refund_account_name" in existing_cols:
            batch_op.drop_column("refund_account_name")
        if "refund_account_number" in existing_cols:
            batch_op.drop_column("refund_account_number")
        if "refund_bank_name" in existing_cols:
            batch_op.drop_column("refund_bank_name")
        if "refund_bank_code" in existing_cols:
            batch_op.drop_column("refund_bank_code")
