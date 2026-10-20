"""Migration: Remove unsafe server defaults on return_inspections.

Revision ID: 0019_remove_unsafe_inspection_defaults
Revises: 0018_return_refund_beneficiary
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_remove_unsafe_inspection_defaults"
down_revision = "0018_return_refund_beneficiary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("return_inspections") as batch_op:
        batch_op.alter_column("package_condition", server_default=None, nullable=True)
        batch_op.alter_column("suggested_action", server_default=None, nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("return_inspections") as batch_op:
        batch_op.alter_column("package_condition", server_default="SEALED", nullable=False)
        batch_op.alter_column("suggested_action", server_default="RESTOCK", nullable=False)
