"""Migration: Return Evidence Requests and Customer Evidence Submission Workflow.

Revision ID: 0009_return_evidence_requests
Revises: 0008_warehouse_return_cases_and_inspections
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_return_evidence_requests"
down_revision = "0008_warehouse_return_cases_and_inspections"
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

    # 1. Bảng return_evidence_requests (Yêu cầu bổ sung hình ảnh từ Quản lý kho)
    if "return_evidence_requests" not in tables:
        op.create_table(
            "return_evidence_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_code", sa.String(50), nullable=False, unique=True, index=True),
            sa.Column("return_request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("warehouse_return_case_id", sa.Integer(), sa.ForeignKey("warehouse_return_cases.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("return_item_id", sa.Integer(), sa.ForeignKey("return_items.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=False),
            sa.Column("required_image_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.Column("status", sa.String(50), server_default="OPEN", nullable=False, index=True),
            sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("customer_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    # 2. Cột evidence_request_id và customer_note trong return_evidences
    if "return_evidences" in tables:
        evidence_cols = _get_existing_columns(conn, "return_evidences")
        if "evidence_request_id" not in evidence_cols:
            op.add_column("return_evidences", sa.Column("evidence_request_id", sa.Integer(), nullable=True))
            try:
                op.create_index("idx_return_evidences_evidence_request_id", "return_evidences", ["evidence_request_id"])
            except Exception:
                pass
        if "customer_note" not in evidence_cols:
            op.add_column("return_evidences", sa.Column("customer_note", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)
    if "return_evidences" in tables:
        evidence_cols = _get_existing_columns(conn, "return_evidences")
        inspector = sa.inspect(conn)
        existing_indices = {idx["name"] for idx in inspector.get_indexes("return_evidences")}
        with op.batch_alter_table("return_evidences") as batch_op:
            for idx_name in ["ix_return_evidences_evidence_request_id", "idx_return_evidences_evidence_request_id"]:
                if idx_name in existing_indices:
                    batch_op.drop_index(idx_name)
            if "customer_note" in evidence_cols:
                batch_op.drop_column("customer_note")
            if "evidence_request_id" in evidence_cols:
                batch_op.drop_column("evidence_request_id")
    if "return_evidence_requests" in tables:
        op.drop_table("return_evidence_requests")
