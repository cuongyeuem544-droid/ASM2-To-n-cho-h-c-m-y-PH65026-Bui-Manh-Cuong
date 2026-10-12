"""Migration: Category classification system, legal product types, and evidence queues.

Revision ID: 0004_category_classification_system
Revises: 0003_after_sales_security_and_vouchers
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0004_category_classification_system"
down_revision = "0003_after_sales_security_and_vouchers"
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

    # 1. Bảng product_types
    if "product_types" not in tables:
        op.create_table(
            "product_types",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        )
        op.create_index("idx_product_types_code", "product_types", ["code"])

    # 2. Bảng categories
    if "categories" not in tables:
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("code", sa.String(100), nullable=False, unique=True),
            sa.Column("slug", sa.String(150), nullable=False, unique=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("category_kind", sa.String(50), server_default="STOREFRONT", nullable=False),
            sa.Column("allowed_product_type", sa.String(50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("icon_name", sa.String(100), nullable=True),
            sa.Column("badge", sa.String(100), nullable=True),
            sa.Column("featured_image", sa.String(1000), nullable=True),
            sa.Column("featured_title", sa.String(255), nullable=True),
            sa.Column("featured_subtitle", sa.String(255), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("idx_categories_slug", "categories", ["slug"])
        op.create_index("idx_categories_parent", "categories", ["parent_id"])
        op.create_index("idx_categories_kind", "categories", ["category_kind"])

    # 3. Bảng product_classification_evidences
    if "product_classification_evidences" not in tables:
        op.create_table(
            "product_classification_evidences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("field_name", sa.String(100), nullable=False),
            sa.Column("proposed_value", sa.String(500), nullable=False),
            sa.Column("source_type", sa.String(100), nullable=False),
            sa.Column("source_url", sa.String(1500), nullable=True),
            sa.Column("source_record_id", sa.String(150), nullable=True),
            sa.Column("registration_number", sa.String(150), nullable=True),
            sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_hash", sa.String(64), nullable=True),
            sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("review_status", sa.String(50), server_default="PENDING", nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
        )
        op.create_index("idx_pce_product_id", "product_classification_evidences", ["product_id"])
        op.create_index("idx_pce_reg_num", "product_classification_evidences", ["registration_number"])

    # 4. Bảng product_categories
    if "product_categories" not in tables:
        op.create_table(
            "product_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_primary", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("assignment_method", sa.String(50), server_default="RULE_SUGGESTION", nullable=False),
            sa.Column("confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False),
            sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("product_classification_evidences.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("product_id", "category_id", name="uq_product_category"),
        )
        op.create_index("idx_pc_product_id", "product_categories", ["product_id"])
        op.create_index("idx_pc_category_id", "product_categories", ["category_id"])

    # 5. Bảng product_classification_reviews
    if "product_classification_reviews" not in tables:
        op.create_table(
            "product_classification_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("suggested_product_type", sa.String(50), nullable=True),
            sa.Column("suggested_prescription_status", sa.String(50), nullable=True),
            sa.Column("suggested_category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("confidence", sa.Float(), server_default=sa.text("0.0"), nullable=False),
            sa.Column("reasoning", sa.Text(), nullable=True),
            sa.Column("missing_fields_json", sa.JSON(), nullable=True),
            sa.Column("conflicts_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(50), server_default="PENDING", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
        )
        op.create_index("idx_pcr_product_id", "product_classification_reviews", ["product_id"])
        op.create_index("idx_pcr_status", "product_classification_reviews", ["status"])

    # 6. Bảng product_classification_history
    if "product_classification_history" not in tables:
        op.create_table(
            "product_classification_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("previous_data_json", sa.JSON(), nullable=True),
            sa.Column("new_data_json", sa.JSON(), nullable=True),
            sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("evidence_source", sa.String(255), nullable=True),
            sa.Column("ip_address", sa.String(100), nullable=True),
            sa.Column("request_id", sa.String(100), nullable=True),
        )
        op.create_index("idx_pch_product_id", "product_classification_history", ["product_id"])

    # 7. Bổ sung các cột mới vào canonical_products nếu chưa có
    cols = _get_existing_columns(conn, "canonical_products")
    new_cols = [
        ("product_type", sa.String(50), "OTHER"),
        ("prescription_status", sa.String(50), "UNKNOWN"),
        ("target_audience", sa.String(100), None),
        ("atc_code", sa.String(50), None),
        ("atc_name", sa.String(255), None),
        ("atc_level", sa.Integer(), None),
        ("atc_source", sa.String(100), None),
        ("atc_verified_at", sa.DateTime(timezone=True), None),
    ]
    for col_name, col_type, default_val in new_cols:
        if col_name not in cols:
            server_def = sa.text(f"'{default_val}'") if default_val is not None else None
            op.add_column("canonical_products", sa.Column(col_name, col_type, server_default=server_def, nullable=True))

    # Đảm bảo index cho canonical_products
    try:
        op.create_index("idx_canonical_product_type", "canonical_products", ["product_type"])
    except Exception:
        pass
    try:
        op.create_index("idx_canonical_prescription_status", "canonical_products", ["prescription_status"])
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    for tbl in [
        "product_classification_history",
        "product_classification_reviews",
        "product_categories",
        "product_classification_evidences",
        "categories",
        "product_types",
    ]:
        if tbl in tables:
            op.drop_table(tbl)
