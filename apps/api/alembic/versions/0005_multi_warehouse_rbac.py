"""Migration: Multi-Warehouse Routing, Fulfillment State Machine, and RBAC Memberships.

Revision ID: 0005_multi_warehouse_rbac
Revises: 0004_category_classification_system
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0005_multi_warehouse_rbac"
down_revision = "0004_category_classification_system"
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

    # 1. Bảng user_warehouse_memberships
    if "user_warehouse_memberships" not in tables:
        op.create_table(
            "user_warehouse_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(50), server_default="WAREHOUSE_MANAGER", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("idx_uwm_user_id", "user_warehouse_memberships", ["user_id"])
        op.create_index("idx_uwm_warehouse_id", "user_warehouse_memberships", ["warehouse_id"])

    # 2. Bổ sung các cột mới vào warehouses nếu chưa có
    wh_cols = _get_existing_columns(conn, "warehouses")
    wh_new_cols = [
        ("email", sa.String(255), None),
        ("province_code", sa.String(50), None),
        ("ward_code", sa.String(50), None),
        ("place_id", sa.String(255), None),
        ("service_radius_km", sa.Float(), sa.text("30.0")),
        ("timezone", sa.String(50), sa.text("'Asia/Ho_Chi_Minh'")),
        ("max_orders_per_day", sa.Integer(), sa.text("500")),
    ]
    for col_name, col_type, default_val in wh_new_cols:
        if col_name not in wh_cols:
            op.add_column("warehouses", sa.Column(col_name, col_type, server_default=default_val, nullable=True))

    # 3. Bổ sung các cột routing & fulfillment vào orders nếu chưa có
    order_cols = _get_existing_columns(conn, "orders")
    order_new_cols = [
        ("assigned_warehouse_id", sa.Integer(), None),
        ("assignment_method", sa.String(50), None),
        ("assignment_distance_km", sa.Float(), None),
        ("fulfillment_status", sa.String(50), sa.text("'PENDING_ALLOCATION'")),
        ("estimated_ready_at", sa.DateTime(timezone=True), None),
        ("assigned_at", sa.DateTime(timezone=True), None),
        ("accepted_at", sa.DateTime(timezone=True), None),
    ]
    for col_name, col_type, default_val in order_new_cols:
        if col_name not in order_cols:
            op.add_column("orders", sa.Column(col_name, col_type, server_default=default_val, nullable=True))

    try:
        op.create_index("idx_orders_assigned_warehouse_id", "orders", ["assigned_warehouse_id"])
    except Exception:
        pass
    try:
        op.create_index("idx_orders_fulfillment_status", "orders", ["fulfillment_status"])
    except Exception:
        pass

    # 4. Bổ sung order_id vào stock_transfers nếu chưa có
    transfer_cols = _get_existing_columns(conn, "stock_transfers")
    if "order_id" not in transfer_cols:
        op.add_column("stock_transfers", sa.Column("order_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_stock_transfers_order_id", "stock_transfers", ["order_id"])
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    if "user_warehouse_memberships" in tables:
        op.drop_table("user_warehouse_memberships")
