"""Migration: Branch Warehouse Management, Import Jobs, Alerts and Large Adjustment Governance.

Revision ID: 0007_branch_warehouse_management_module
Revises: 0006_user_account_security_and_management
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_branch_warehouse_management_module"
down_revision = "0006_user_account_security_and_management"
branch_labels = None
depends_on = None


def _get_existing_tables(conn) -> set[str]:
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def _get_existing_columns(conn, table_name: str) -> set[str]:
    inspector = sa.inspect(conn)
    try:
        return {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return set()


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    # 1. Bảng warehouse_import_jobs
    if "warehouse_import_jobs" not in tables:
        op.create_table(
            "warehouse_import_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("import_code", sa.String(50), nullable=False, unique=True, index=True),
            sa.Column("file_hash", sa.String(64), nullable=False, index=True),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("file_size", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("imported_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("total_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("valid_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("warning_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("invalid_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("candidate_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("status", sa.String(50), server_default="PREVIEW", nullable=False, index=True),
            sa.Column("error_details", sa.Text(), nullable=True),
            sa.Column("preview_data", sa.Text(), nullable=True),
            sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("stock_receipts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        )

    # 2. Bảng warehouse_alerts
    if "warehouse_alerts" not in tables:
        op.create_table(
            "warehouse_alerts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("alert_type", sa.String(50), nullable=False, index=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(20), server_default="WARNING", nullable=False),
            sa.Column("reference_type", sa.String(50), nullable=True),
            sa.Column("reference_id", sa.String(100), nullable=True),
            sa.Column("is_read", sa.Boolean(), server_default=sa.text("0"), nullable=False, index=True),
            sa.Column("read_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, index=True),
        )

    # 3. Cột mới cho stock_adjustments sử dụng batch_alter_table cho SQLite
    adj_cols = _get_existing_columns(conn, "stock_adjustments")
    with op.batch_alter_table("stock_adjustments") as batch_op:
        if "is_large_adjustment" not in adj_cols:
            batch_op.add_column(sa.Column("is_large_adjustment", sa.Boolean(), server_default=sa.text("0"), nullable=True))
        if "total_quantity_variance" not in adj_cols:
            batch_op.add_column(sa.Column("total_quantity_variance", sa.Integer(), server_default=sa.text("0"), nullable=True))
        if "total_amount_variance" not in adj_cols:
            batch_op.add_column(sa.Column("total_amount_variance", sa.Numeric(14, 2), server_default=sa.text("0.0"), nullable=True))
        if "admin_approved_by" not in adj_cols:
            batch_op.add_column(sa.Column("admin_approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
        if "admin_approved_at" not in adj_cols:
            batch_op.add_column(sa.Column("admin_approved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    pass
