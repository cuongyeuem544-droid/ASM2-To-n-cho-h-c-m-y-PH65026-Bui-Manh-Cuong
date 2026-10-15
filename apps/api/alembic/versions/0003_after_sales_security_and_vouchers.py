"""Migration: after-sales, security fields, OTP, password reset, and vouchers.

Revision ID: 0003_after_sales_security_and_vouchers
Revises: 0002_inventory_warehouse_batch
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "0003_after_sales_security_and_vouchers"
down_revision = "0002_inventory_warehouse_batch"
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

    # 1. return_requests
    if "return_requests" not in tables:
        op.create_table(
            "return_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("return_code", sa.String(50), nullable=False, unique=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("customer_name", sa.String(255), nullable=False),
            sa.Column("customer_phone", sa.String(50), nullable=False),
            sa.Column("customer_email", sa.String(255), nullable=True),
            sa.Column("request_type", sa.String(20), nullable=False, server_default="RETURN"),
            sa.Column("status", sa.String(50), nullable=False, server_default="REQUESTED"),
            sa.Column("reason_code", sa.String(50), nullable=False),
            sa.Column("reason_text", sa.String(255), nullable=False),
            sa.Column("customer_note", sa.Text(), nullable=True),
            sa.Column("return_method", sa.String(50), nullable=False, server_default="CUSTOMER_SHIP"),
            sa.Column("carrier_name", sa.String(100), nullable=True),
            sa.Column("tracking_code", sa.String(100), nullable=True),
            sa.Column("return_address_snapshot", sa.Text(), nullable=True),
            sa.Column("admin_note", sa.Text(), nullable=True),
            sa.Column("customer_visible_note", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("assigned_staff_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("received_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("inspected_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_return_requests_return_code", "return_requests", ["return_code"])
        op.create_index("ix_return_requests_order_id", "return_requests", ["order_id"])
        op.create_index("ix_return_requests_user_id", "return_requests", ["user_id"])
        op.create_index("ix_return_requests_customer_phone", "return_requests", ["customer_phone"])
        op.create_index("ix_return_requests_status", "return_requests", ["status"])

    # 2. return_items
    if "return_items" not in tables:
        op.create_table(
            "return_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("return_request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("order_item_id", sa.Integer(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("product_name", sa.String(255), nullable=False),
            sa.Column("original_quantity", sa.Integer(), nullable=False),
            sa.Column("requested_quantity", sa.Integer(), nullable=False),
            sa.Column("approved_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("received_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("original_unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("net_unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("refundable_unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("total_refund_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("condition_received", sa.String(50), nullable=True),
            sa.Column("restock_destination", sa.String(50), nullable=True),
            sa.Column("restocked_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("restocked_batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True),
            sa.Column("is_seal_intact", sa.Boolean(), nullable=True),
            sa.Column("temperature_compliant", sa.Boolean(), nullable=True),
            sa.Column("blister_pack_intact", sa.Boolean(), nullable=True),
            sa.Column("expiry_date_verified", sa.Boolean(), nullable=True),
            sa.Column("batch_matched", sa.Boolean(), nullable=True),
            sa.Column("inspection_note", sa.Text(), nullable=True),
            sa.Column("inspected_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_return_items_return_request_id", "return_items", ["return_request_id"])
        op.create_index("ix_return_items_order_item_id", "return_items", ["order_item_id"])

    # 3. return_evidences
    if "return_evidences" not in tables:
        op.create_table(
            "return_evidences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("return_request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("return_item_id", sa.Integer(), sa.ForeignKey("return_items.id", ondelete="CASCADE"), nullable=True),
            sa.Column("storage_key", sa.String(255), nullable=False),
            sa.Column("file_url", sa.String(500), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("file_category", sa.String(50), nullable=False, server_default="CUSTOMER_IMAGE"),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_return_evidences_return_request_id", "return_evidences", ["return_request_id"])
    else:
        # Check description column
        ev_cols = _get_existing_columns(conn, "return_evidences")
        if "description" not in ev_cols:
            with op.batch_alter_table("return_evidences") as batch_op:
                batch_op.add_column(sa.Column("description", sa.String(500), nullable=True))

    # 4. return_status_history
    if "return_status_history" not in tables:
        op.create_table(
            "return_status_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("return_request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_status", sa.String(50), nullable=True),
            sa.Column("to_status", sa.String(50), nullable=False),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("actor_name", sa.String(255), nullable=True),
            sa.Column("actor_role", sa.String(50), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_return_status_history_return_request_id", "return_status_history", ["return_request_id"])

    # 5. refunds
    if "refunds" not in tables:
        op.create_table(
            "refunds",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("refund_code", sa.String(50), nullable=False, unique=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("return_request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="SET NULL"), nullable=True),
            sa.Column("payment_transaction_id", sa.Integer(), sa.ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False, server_default="VND"),
            sa.Column("refund_method", sa.String(50), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("reason", sa.String(255), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(100), nullable=True, unique=True),
            sa.Column("beneficiary_bank_name", sa.String(100), nullable=True),
            sa.Column("beneficiary_account_number", sa.String(50), nullable=True),
            sa.Column("beneficiary_account_name", sa.String(255), nullable=True),
            sa.Column("manual_reference_number", sa.String(100), nullable=True),
            sa.Column("manual_proof_storage_key", sa.String(255), nullable=True),
            sa.Column("provider_refund_id", sa.String(100), nullable=True),
            sa.Column("provider_reference", sa.String(100), nullable=True),
            sa.Column("failure_code", sa.String(100), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("reconciliation_status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("processed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_refunds_refund_code", "refunds", ["refund_code"])
        op.create_index("ix_refunds_order_id", "refunds", ["order_id"])
        op.create_index("ix_refunds_return_request_id", "refunds", ["return_request_id"])
        op.create_index("ix_refunds_status", "refunds", ["status"])
        op.create_index("ix_refunds_idempotency_key", "refunds", ["idempotency_key"])
    else:
        # Check notes column
        ref_cols = _get_existing_columns(conn, "refunds")
        if "notes" not in ref_cols:
            with op.batch_alter_table("refunds") as batch_op:
                batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))

    # 6. refund_attempts
    if "refund_attempts" not in tables:
        op.create_table(
            "refund_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("refund_id", sa.Integer(), sa.ForeignKey("refunds.id", ondelete="CASCADE"), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
            sa.Column("request_reference", sa.String(100), nullable=False),
            sa.Column("provider_reference", sa.String(100), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("error_code", sa.String(100), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("raw_response_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_refund_attempts_refund_id", "refund_attempts", ["refund_id"])
        op.create_index("ix_refund_attempts_idempotency_key", "refund_attempts", ["idempotency_key"])

    # 7. exchange_orders
    if "exchange_orders" not in tables:
        op.create_table(
            "exchange_orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("exchange_code", sa.String(50), nullable=False, unique=True),
            sa.Column("return_request_id", sa.Integer(), sa.ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False),
            sa.Column("original_order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("replacement_order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="REQUESTED"),
            sa.Column("original_credit", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("replacement_subtotal", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("price_difference", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("difference_action", sa.String(50), nullable=False, server_default="EVEN"),
            sa.Column("difference_payment_status", sa.String(50), nullable=False, server_default="SETTLED"),
            sa.Column("difference_payment_transaction_id", sa.Integer(), sa.ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("difference_refund_id", sa.Integer(), sa.ForeignKey("refunds.id", ondelete="SET NULL"), nullable=True),
            sa.Column("customer_note", sa.Text(), nullable=True),
            sa.Column("admin_note", sa.Text(), nullable=True),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_exchange_orders_exchange_code", "exchange_orders", ["exchange_code"])
        op.create_index("ix_exchange_orders_return_request_id", "exchange_orders", ["return_request_id"])
        op.create_index("ix_exchange_orders_original_order_id", "exchange_orders", ["original_order_id"])

    # 8. exchange_items
    if "exchange_items" not in tables:
        op.create_table(
            "exchange_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("exchange_order_id", sa.Integer(), sa.ForeignKey("exchange_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("original_order_item_id", sa.Integer(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("replacement_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("replacement_sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("sku_code", sa.String(50), nullable=True),
            sa.Column("replacement_product_name", sa.String(255), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("replacement_unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("original_credit_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("difference_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_exchange_items_exchange_order_id", "exchange_items", ["exchange_order_id"])
    else:
        ex_cols = _get_existing_columns(conn, "exchange_items")
        if "sku_code" not in ex_cols:
            with op.batch_alter_table("exchange_items") as batch_op:
                batch_op.add_column(sa.Column("sku_code", sa.String(50), nullable=True))

    # 9. user_otps
    if "user_otps" not in tables:
        op.create_table(
            "user_otps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("identifier", sa.String(100), nullable=False),
            sa.Column("otp_hash", sa.String(255), nullable=False),
            sa.Column("purpose", sa.String(50), nullable=False, server_default="LOGIN"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_user_otps_identifier", "user_otps", ["identifier"])
        op.create_index("ix_user_otps_purpose", "user_otps", ["purpose"])
        op.create_index("ix_user_otps_expires_at", "user_otps", ["expires_at"])

    # 10. password_reset_tokens
    if "password_reset_tokens" not in tables:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
        op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])

    # 11. vouchers
    if "vouchers" not in tables:
        op.create_table(
            "vouchers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("discount_type", sa.String(20), nullable=False),
            sa.Column("discount_value", sa.Numeric(12, 2), nullable=False),
            sa.Column("min_order_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("max_discount_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("usage_limit", sa.Integer(), nullable=True),
            sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_vouchers_code", "vouchers", ["code"])
        op.create_index("ix_vouchers_is_active", "vouchers", ["is_active"])

    # 12. Add missing columns to orders
    order_cols = _get_existing_columns(conn, "orders")
    with op.batch_alter_table("orders") as batch_op:
        if "idempotency_key" not in order_cols:
            batch_op.add_column(sa.Column("idempotency_key", sa.String(100), nullable=True))
        if "voucher_code" not in order_cols:
            batch_op.add_column(sa.Column("voucher_code", sa.String(50), nullable=True))
        if "promotion_id" not in order_cols:
            batch_op.add_column(sa.Column("promotion_id", sa.Integer(), nullable=True))
        if "discount_amount" not in order_cols:
            batch_op.add_column(sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"))
        if "discount_breakdown" not in order_cols:
            batch_op.add_column(sa.Column("discount_breakdown", sa.JSON(), nullable=True))

    # 13. Add recipient_name to email_outboxes
    if "email_outboxes" in tables:
        email_cols = _get_existing_columns(conn, "email_outboxes")
        if "recipient_name" not in email_cols:
            with op.batch_alter_table("email_outboxes") as batch_op:
                batch_op.add_column(sa.Column("recipient_name", sa.String(255), nullable=True))

    # 14. Add token_version to users
    if "users" in tables:
        user_cols = _get_existing_columns(conn, "users")
        if "token_version" not in user_cols:
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    conn = op.get_bind()
    tables = _get_existing_tables(conn)

    # Revert columns
    if "users" in tables:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("token_version")

    if "email_outboxes" in tables:
        with op.batch_alter_table("email_outboxes") as batch_op:
            batch_op.drop_column("recipient_name")

    if "orders" in tables:
        order_indexes = {idx["name"] for idx in sa.inspect(conn).get_indexes("orders")}
        with op.batch_alter_table("orders") as batch_op:
            if "ix_orders_idempotency_key" in order_indexes:
                batch_op.drop_index("ix_orders_idempotency_key")
            if "ix_orders_voucher_code" in order_indexes:
                batch_op.drop_index("ix_orders_voucher_code")
            batch_op.drop_column("discount_breakdown")
            batch_op.drop_column("discount_amount")
            batch_op.drop_column("promotion_id")
            batch_op.drop_column("voucher_code")
            batch_op.drop_column("idempotency_key")

    # Drop tables
    for tbl in [
        "vouchers",
        "password_reset_tokens",
        "user_otps",
        "exchange_items",
        "exchange_orders",
        "refund_attempts",
        "refunds",
        "return_status_history",
        "return_evidences",
        "return_items",
        "return_requests",
    ]:
        if tbl in tables:
            op.drop_table(tbl)
