"""Migration: create inventory, warehouse, batch, movements, fulfillments, payments, reviews, and seasonal campaigns tables.

Revision ID: 0002_inventory_warehouse_batch
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_inventory_warehouse_batch"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())

    # 1. warehouses
    if "warehouses" not in tables:
        op.create_table(
            "warehouses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("address", sa.String(500), nullable=False),
            sa.Column("ward", sa.String(100), nullable=True),
            sa.Column("district", sa.String(100), nullable=True),
            sa.Column("province", sa.String(100), nullable=True),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lng", sa.Float(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_central", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_warehouses_code", "warehouses", ["code"])

    # 2. warehouse_locations
    if "warehouse_locations" not in tables:
        op.create_table(
            "warehouse_locations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("name", sa.String(255), nullable=True),
            sa.Column("aisle", sa.String(50), nullable=True),
            sa.Column("shelf", sa.String(50), nullable=True),
            sa.Column("bin", sa.String(50), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index("ix_warehouse_locations_warehouse_id", "warehouse_locations", ["warehouse_id"])
        op.create_index("ix_warehouse_locations_code", "warehouse_locations", ["code"])

    # 3. administrative_units
    if "administrative_units" not in tables:
        op.create_table(
            "administrative_units",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("parent_code", sa.String(50), nullable=True),
            sa.Column("level", sa.String(50), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
        )
        op.create_index("ix_administrative_units_code", "administrative_units", ["code"])
        op.create_index("ix_administrative_units_parent_code", "administrative_units", ["parent_code"])

    # 4. customer_addresses
    if "customer_addresses" not in tables:
        op.create_table(
            "customer_addresses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("recipient_name", sa.String(255), nullable=False),
            sa.Column("phone", sa.String(50), nullable=False),
            sa.Column("address_line", sa.String(500), nullable=False),
            sa.Column("province_code", sa.String(50), nullable=True),
            sa.Column("district_code", sa.String(50), nullable=True),
            sa.Column("ward_code", sa.String(50), nullable=True),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lng", sa.Float(), nullable=True),
            sa.Column("place_id", sa.String(255), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_customer_addresses_user_id", "customer_addresses", ["user_id"])

    # 5. product_skus
    if "product_skus" not in tables:
        op.create_table(
            "product_skus",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sku_code", sa.String(100), nullable=False, unique=True),
            sa.Column("barcode", sa.String(100), nullable=True),
            sa.Column("uom", sa.String(50), nullable=False, server_default="Hộp"),
            sa.Column("conversion_rate", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index("ix_product_skus_canonical_product_id", "product_skus", ["canonical_product_id"])
        op.create_index("ix_product_skus_sku_code", "product_skus", ["sku_code"])
        op.create_index("ix_product_skus_barcode", "product_skus", ["barcode"])

    # 6. suppliers
    if "suppliers" not in tables:
        op.create_table(
            "suppliers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("tax_code", sa.String(50), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("address", sa.String(500), nullable=True),
            sa.Column("gsp_license_number", sa.String(100), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_suppliers_code", "suppliers", ["code"])

    # 7. inventory_batches
    if "inventory_batches" not in tables:
        op.create_table(
            "inventory_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_number", sa.String(100), nullable=False),
            sa.Column("manufacture_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("initial_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
            sa.Column("certificate_url", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_inventory_batches_sku_id", "inventory_batches", ["sku_id"])
        op.create_index("ix_inventory_batches_batch_number", "inventory_batches", ["batch_number"])
        op.create_index("ix_inventory_batches_expiry_date", "inventory_batches", ["expiry_date"])
        op.create_index("ix_inventory_batches_supplier_id", "inventory_batches", ["supplier_id"])

    # 8. warehouse_batch_stock
    if "warehouse_batch_stock" not in tables:
        op.create_table(
            "warehouse_batch_stock",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("warehouse_locations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("quantity_on_hand", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("quantity_reserved", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("quantity_available", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("warehouse_id", "batch_id", "location_id", name="uq_wh_batch_loc"),
        )
        op.create_index("ix_warehouse_batch_stock_warehouse_id", "warehouse_batch_stock", ["warehouse_id"])
        op.create_index("ix_warehouse_batch_stock_batch_id", "warehouse_batch_stock", ["batch_id"])

    # 9. stock_receipts
    if "stock_receipts" not in tables:
        op.create_table(
            "stock_receipts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("receipt_code", sa.String(50), nullable=False, unique=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
            sa.Column("received_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0.0"),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_stock_receipts_receipt_code", "stock_receipts", ["receipt_code"])
        op.create_index("ix_stock_receipts_warehouse_id", "stock_receipts", ["warehouse_id"])
        op.create_index("ix_stock_receipts_supplier_id", "stock_receipts", ["supplier_id"])
        op.create_index("ix_stock_receipts_status", "stock_receipts", ["status"])

    # 10. stock_receipt_items
    if "stock_receipt_items" not in tables:
        op.create_table(
            "stock_receipt_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("stock_receipts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sku_id", sa.Integer(), sa.ForeignKey("product_skus.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("batch_number", sa.String(100), nullable=False),
            sa.Column("manufacture_date", sa.Date(), nullable=True),
            sa.Column("expiry_date", sa.Date(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("purchase_unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
            sa.Column("storage_location_id", sa.Integer(), sa.ForeignKey("warehouse_locations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_stock_receipt_items_receipt_id", "stock_receipt_items", ["receipt_id"])
        op.create_index("ix_stock_receipt_items_sku_id", "stock_receipt_items", ["sku_id"])

    # 11. stock_movements
    if "stock_movements" not in tables:
        op.create_table(
            "stock_movements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("movement_code", sa.String(50), nullable=False, unique=True),
            sa.Column("movement_type", sa.String(50), nullable=False),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reference_type", sa.String(50), nullable=True),
            sa.Column("reference_id", sa.String(100), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_stock_movements_movement_code", "stock_movements", ["movement_code"])
        op.create_index("ix_stock_movements_movement_type", "stock_movements", ["movement_type"])
        op.create_index("ix_stock_movements_warehouse_id", "stock_movements", ["warehouse_id"])
        op.create_index("ix_stock_movements_batch_id", "stock_movements", ["batch_id"])

    # 12. stock_adjustments
    if "stock_adjustments" not in tables:
        op.create_table(
            "stock_adjustments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("adjustment_code", sa.String(50), nullable=False, unique=True),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("reason", sa.String(255), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_stock_adjustments_adjustment_code", "stock_adjustments", ["adjustment_code"])
        op.create_index("ix_stock_adjustments_warehouse_id", "stock_adjustments", ["warehouse_id"])

    # 13. stock_adjustment_items
    if "stock_adjustment_items" not in tables:
        op.create_table(
            "stock_adjustment_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("adjustment_id", sa.Integer(), sa.ForeignKey("stock_adjustments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("system_quantity", sa.Integer(), nullable=False),
            sa.Column("actual_quantity", sa.Integer(), nullable=False),
            sa.Column("delta_quantity", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(255), nullable=True),
        )
        op.create_index("ix_stock_adjustment_items_adjustment_id", "stock_adjustment_items", ["adjustment_id"])

    # 14. stock_transfers
    if "stock_transfers" not in tables:
        op.create_table(
            "stock_transfers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transfer_code", sa.String(50), nullable=False, unique=True),
            sa.Column("from_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("to_warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_stock_transfers_transfer_code", "stock_transfers", ["transfer_code"])
        op.create_index("ix_stock_transfers_from_warehouse_id", "stock_transfers", ["from_warehouse_id"])
        op.create_index("ix_stock_transfers_to_warehouse_id", "stock_transfers", ["to_warehouse_id"])

    # 15. stock_transfer_items
    if "stock_transfer_items" not in tables:
        op.create_table(
            "stock_transfer_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transfer_id", sa.Integer(), sa.ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("received_quantity", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_stock_transfer_items_transfer_id", "stock_transfer_items", ["transfer_id"])

    # 16. stock_reservations
    if "stock_reservations" not in tables:
        op.create_table(
            "stock_reservations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="RESERVED"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_stock_reservations_order_id", "stock_reservations", ["order_id"])
        op.create_index("ix_stock_reservations_batch_id", "stock_reservations", ["batch_id"])
        op.create_index("ix_stock_reservations_warehouse_id", "stock_reservations", ["warehouse_id"])

    # 17. order_fulfillments
    if "order_fulfillments" not in tables:
        op.create_table(
            "order_fulfillments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("fulfillment_code", sa.String(50), nullable=False, unique=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("carrier_name", sa.String(100), nullable=True),
            sa.Column("tracking_code", sa.String(100), nullable=True),
            sa.Column("shipping_fee", sa.Numeric(12, 2), nullable=False, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_order_fulfillments_fulfillment_code", "order_fulfillments", ["fulfillment_code"])
        op.create_index("ix_order_fulfillments_order_id", "order_fulfillments", ["order_id"])
        op.create_index("ix_order_fulfillments_warehouse_id", "order_fulfillments", ["warehouse_id"])

    # 18. fulfillment_items
    if "fulfillment_items" not in tables:
        op.create_table(
            "fulfillment_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("fulfillment_id", sa.Integer(), sa.ForeignKey("order_fulfillments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("order_item_id", sa.Integer(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
        )
        op.create_index("ix_fulfillment_items_fulfillment_id", "fulfillment_items", ["fulfillment_id"])
        op.create_index("ix_fulfillment_items_order_item_id", "fulfillment_items", ["order_item_id"])

    # 19. order_item_batch_allocations
    if "order_item_batch_allocations" not in tables:
        op.create_table(
            "order_item_batch_allocations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("fulfillment_item_id", sa.Integer(), sa.ForeignKey("fulfillment_items.id", ondelete="CASCADE"), nullable=True),
            sa.Column("order_item_id", sa.Integer(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("allocated_quantity", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_order_item_batch_allocations_order_item_id", "order_item_batch_allocations", ["order_item_id"])
        op.create_index("ix_order_item_batch_allocations_batch_id", "order_item_batch_allocations", ["batch_id"])

    # 20. payment_transactions
    if "payment_transactions" not in tables:
        op.create_table(
            "payment_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("transaction_code", sa.String(100), nullable=False, unique=True),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False, server_default="VND"),
            sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("provider_trans_id", sa.String(100), nullable=True),
            sa.Column("provider_pay_url", sa.String(1000), nullable=True),
            sa.Column("provider_response_raw", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_payment_transactions_order_id", "payment_transactions", ["order_id"])
        op.create_index("ix_payment_transactions_transaction_code", "payment_transactions", ["transaction_code"])

    # 21. payment_webhook_events
    if "payment_webhook_events" not in tables:
        op.create_table(
            "payment_webhook_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("event_id", sa.String(100), nullable=True),
            sa.Column("signature", sa.String(255), nullable=True),
            sa.Column("payload_raw", sa.Text(), nullable=False),
            sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("process_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_payment_webhook_events_event_id", "payment_webhook_events", ["event_id"])

    # 22. email_outboxes
    if "email_outboxes" not in tables:
        op.create_table(
            "email_outboxes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("recipient_email", sa.String(255), nullable=False),
            sa.Column("subject", sa.String(500), nullable=False),
            sa.Column("body_html", sa.Text(), nullable=False),
            sa.Column("body_text", sa.Text(), nullable=True),
            sa.Column("reference_type", sa.String(50), nullable=True),
            sa.Column("reference_id", sa.String(100), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_email_outboxes_recipient_email", "email_outboxes", ["recipient_email"])
        op.create_index("ix_email_outboxes_status", "email_outboxes", ["status"])

    # 23. product_reviews
    if "product_reviews" not in tables:
        op.create_table(
            "product_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("customer_name", sa.String(255), nullable=False),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("is_verified_purchase", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_product_reviews_canonical_product_id", "product_reviews", ["canonical_product_id"])

    # 24. seasonal_campaigns
    if "seasonal_campaigns" not in tables:
        op.create_table(
            "seasonal_campaigns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(100), nullable=False, unique=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("disease_name", sa.String(255), nullable=False),
            sa.Column("season", sa.String(50), nullable=False),
            sa.Column("symptoms", sa.Text(), nullable=False),
            sa.Column("prevention", sa.Text(), nullable=False),
            sa.Column("recommended_product_ids", sa.Text(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
            sa.Column("banner_image_url", sa.String(1000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_seasonal_campaigns_slug", "seasonal_campaigns", ["slug"])


def downgrade() -> None:
    op.drop_table("seasonal_campaigns")
    op.drop_table("product_reviews")
    op.drop_table("email_outboxes")
    op.drop_table("payment_webhook_events")
    op.drop_table("payment_transactions")
    op.drop_table("order_item_batch_allocations")
    op.drop_table("fulfillment_items")
    op.drop_table("order_fulfillments")
    op.drop_table("stock_reservations")
    op.drop_table("stock_transfer_items")
    op.drop_table("stock_transfers")
    op.drop_table("stock_adjustment_items")
    op.drop_table("stock_adjustments")
    op.drop_table("stock_movements")
    op.drop_table("stock_receipt_items")
    op.drop_table("stock_receipts")
    op.drop_table("warehouse_batch_stock")
    op.drop_table("inventory_batches")
    op.drop_table("suppliers")
    op.drop_table("product_skus")
    op.drop_table("customer_addresses")
    op.drop_table("administrative_units")
    op.drop_table("warehouse_locations")
    op.drop_table("warehouses")
