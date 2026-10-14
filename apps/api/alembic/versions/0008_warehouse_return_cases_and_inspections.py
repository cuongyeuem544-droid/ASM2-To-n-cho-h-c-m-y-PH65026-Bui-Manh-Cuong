"""Migration: Warehouse Return Cases, Inspections, and Multi-Warehouse Order Return Lifecycle.

Revision ID: 0008_warehouse_return_cases_and_inspections
Revises: 0007_branch_warehouse_management_module
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_warehouse_return_cases_and_inspections"
down_revision = "0007_branch_warehouse_management_module"
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

    # 1. Bảng warehouse_return_cases (Ca hoàn chi nhánh - Con của ReturnRequest)
    if "warehouse_return_cases" not in tables:
        op.create_table(
            "warehouse_return_cases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_code", sa.String(50), nullable=False, unique=True, index=True),
            sa.Column("return_request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("fulfillment_id", sa.Integer(), sa.ForeignKey("order_fulfillments.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("assigned_staff_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("inspected_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("refund_processed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("status", sa.String(50), server_default="REQUESTED", nullable=False, index=True),
            sa.Column("carrier_name", sa.String(100), nullable=True),
            sa.Column("tracking_code", sa.String(100), nullable=True),
            sa.Column("package_condition", sa.String(50), nullable=True),
            sa.Column("manager_note", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("disposition", sa.String(50), nullable=True),
            sa.Column("disposition_note", sa.Text(), nullable=True),
            sa.Column("disposition_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("refund_processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    # 2. Bảng return_inspections (Biên bản kiểm hàng của nhân viên kho)
    if "return_inspections" not in tables:
        op.create_table(
            "return_inspections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("warehouse_return_cases.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("return_item_id", sa.Integer(), sa.ForeignKey("return_items.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("received_quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("accepted_quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("rejected_quantity", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("package_condition", sa.String(50), server_default="SEALED", nullable=False),
            sa.Column("seal_intact", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("batch_matched", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("expiry_matched", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("storage_condition_ok", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("damage_description", sa.Text(), nullable=True),
            sa.Column("suggested_action", sa.String(50), server_default="RESTOCK", nullable=False),
            sa.Column("inspected_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("inspection_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    # 3. Cập nhật return_items
    ret_item_cols = _get_existing_columns(conn, "return_items")
    if "warehouse_return_case_id" not in ret_item_cols:
        op.add_column("return_items", sa.Column("warehouse_return_case_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_return_items_wrc_id", "return_items", ["warehouse_return_case_id"])
        except Exception:
            pass
    if "warehouse_id" not in ret_item_cols:
        op.add_column("return_items", sa.Column("warehouse_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_return_items_warehouse_id", "return_items", ["warehouse_id"])
        except Exception:
            pass

    # 4. Cập nhật refunds
    refund_cols = _get_existing_columns(conn, "refunds")
    if "warehouse_return_case_id" not in refund_cols:
        op.add_column("refunds", sa.Column("warehouse_return_case_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_refunds_wrc_id", "refunds", ["warehouse_return_case_id"])
        except Exception:
            pass
    if "warehouse_id" not in refund_cols:
        op.add_column("refunds", sa.Column("warehouse_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_refunds_warehouse_id", "refunds", ["warehouse_id"])
        except Exception:
            pass

    # 5. Cập nhật return_evidences
    evid_cols = _get_existing_columns(conn, "return_evidences")
    if "warehouse_return_case_id" not in evid_cols:
        op.add_column("return_evidences", sa.Column("warehouse_return_case_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_return_evidences_wrc_id", "return_evidences", ["warehouse_return_case_id"])
        except Exception:
            pass
    if "video_url" not in evid_cols:
        op.add_column("return_evidences", sa.Column("video_url", sa.String(1000), nullable=True))

    # 6. Cập nhật return_status_history
    hist_cols = _get_existing_columns(conn, "return_status_history")
    if "warehouse_id" not in hist_cols:
        op.add_column("return_status_history", sa.Column("warehouse_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_return_status_history_warehouse_id", "return_status_history", ["warehouse_id"])
        except Exception:
            pass
    if "warehouse_return_case_id" not in hist_cols:
        op.add_column("return_status_history", sa.Column("warehouse_return_case_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_return_status_history_wrc_id", "return_status_history", ["warehouse_return_case_id"])
        except Exception:
            pass
    if "ip_address" not in hist_cols:
        op.add_column("return_status_history", sa.Column("ip_address", sa.String(50), nullable=True))
    if "user_agent" not in hist_cols:
        op.add_column("return_status_history", sa.Column("user_agent", sa.String(255), nullable=True))

    # 7. Cập nhật order_fulfillments
    ful_cols = _get_existing_columns(conn, "order_fulfillments")
    if "assigned_staff_id" not in ful_cols:
        op.add_column("order_fulfillments", sa.Column("assigned_staff_id", sa.Integer(), nullable=True))
        try:
            op.create_index("idx_order_fulfillments_staff_id", "order_fulfillments", ["assigned_staff_id"])
        except Exception:
            pass
    if "picked_at" not in ful_cols:
        op.add_column("order_fulfillments", sa.Column("picked_at", sa.DateTime(timezone=True), nullable=True))
    if "packed_at" not in ful_cols:
        op.add_column("order_fulfillments", sa.Column("packed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    pass
