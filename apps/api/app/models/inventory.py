from datetime import UTC, datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500))
    ward: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_central: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    province_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ward_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_radius_km: Mapped[float] = mapped_column(Float, default=30.0)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Ho_Chi_Minh")
    max_orders_per_day: Mapped[int] = mapped_column(Integer, default=500)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    locations: Mapped[list["WarehouseLocation"]] = relationship(back_populates="warehouse", cascade="all, delete-orphan")
    batch_stocks: Mapped[list["WarehouseBatchStock"]] = relationship(back_populates="warehouse", cascade="all, delete-orphan")
    memberships: Mapped[list["UserWarehouseMembership"]] = relationship(back_populates="warehouse", cascade="all, delete-orphan")


class WarehouseLocation(Base):
    __tablename__ = "warehouse_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aisle: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shelf: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    warehouse: Mapped[Warehouse] = relationship(back_populates="locations")


class AdministrativeUnit(Base):
    __tablename__ = "administrative_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(50))  # PROVINCE, DISTRICT, WARD
    full_name: Mapped[str] = mapped_column(String(255))


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    recipient_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(50))
    address_line: Mapped[str] = mapped_column(String(500))
    province_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    province_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commune_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commune_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    formatted_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    district_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ward_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=utcnow)


class ProductSku(Base):
    __tablename__ = "product_skus"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    sku_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    uom: Mapped[str] = mapped_column(String(50), default="Hộp")  # Hộp, Vỉ, Viên, Chai, Tuýp, Gói
    conversion_rate: Mapped[int] = mapped_column(Integer, default=1)
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    canonical_product: Mapped["CanonicalProduct"] = relationship()
    batches: Mapped[list["InventoryBatch"]] = relationship(back_populates="sku", cascade="all, delete-orphan")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gsp_license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BatchStatus:
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    RECALLED = "RECALLED"
    EXPIRED = "EXPIRED"


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id", ondelete="CASCADE"), index=True)
    batch_number: Mapped[str] = mapped_column(String(100), index=True)
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, index=True)  # Key for FEFO
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    initial_quantity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default=BatchStatus.ACTIVE)  # ACTIVE, QUARANTINED, RECALLED, EXPIRED
    certificate_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sku: Mapped[ProductSku] = relationship(back_populates="batches")
    supplier: Mapped[Supplier | None] = relationship()
    stocks: Mapped[list["WarehouseBatchStock"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class WarehouseBatchStock(Base):
    __tablename__ = "warehouse_batch_stock"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "batch_id", "location_id", name="uq_wh_batch_loc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("inventory_batches.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_locations.id", ondelete="SET NULL"), nullable=True)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0)
    quantity_available: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    warehouse: Mapped[Warehouse] = relationship(back_populates="batch_stocks")
    batch: Mapped[InventoryBatch] = relationship(back_populates="stocks")
    location: Mapped[WarehouseLocation | None] = relationship()


class StockReceipt(Base):
    __tablename__ = "stock_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)  # DRAFT, CONFIRMED, CANCELLED
    received_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.0"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["StockReceiptItem"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")
    warehouse: Mapped[Warehouse] = relationship()
    supplier: Mapped[Supplier] = relationship()


class StockReceiptItem(Base):
    __tablename__ = "stock_receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("stock_receipts.id", ondelete="CASCADE"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id", ondelete="RESTRICT"), index=True)
    batch_number: Mapped[str] = mapped_column(String(100))
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[int] = mapped_column(Integer)
    purchase_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    storage_location_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_locations.id", ondelete="SET NULL"), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True)

    receipt: Mapped[StockReceipt] = relationship(back_populates="items")
    sku: Mapped[ProductSku] = relationship()
    batch: Mapped[InventoryBatch | None] = relationship()


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    movement_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(50), index=True)  # RECEIPT, DISPATCH, TRANSFER_OUT, TRANSFER_IN, ADJUST_INC, ADJUST_DEC, DISPOSAL
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("inventory_batches.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer, default=0)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # STOCK_RECEIPT, ORDER_FULFILLMENT, TRANSFER, ADJUSTMENT
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    warehouse: Mapped[Warehouse] = relationship()
    batch: Mapped[InventoryBatch] = relationship()


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    adjustment_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)  # DRAFT, CONFIRMED, CANCELLED
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["StockAdjustmentItem"]] = relationship(back_populates="adjustment", cascade="all, delete-orphan")
    warehouse: Mapped[Warehouse] = relationship()


class StockAdjustmentItem(Base):
    __tablename__ = "stock_adjustment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    adjustment_id: Mapped[int] = mapped_column(ForeignKey("stock_adjustments.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("inventory_batches.id", ondelete="RESTRICT"), index=True)
    system_quantity: Mapped[int] = mapped_column(Integer)
    actual_quantity: Mapped[int] = mapped_column(Integer)
    delta_quantity: Mapped[int] = mapped_column(Integer)  # actual - system
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    adjustment: Mapped[StockAdjustment] = relationship(back_populates="items")
    batch: Mapped[InventoryBatch] = relationship()


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    from_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    to_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)  # DRAFT, IN_TRANSIT, COMPLETED, CANCELLED
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["StockTransferItem"]] = relationship(back_populates="transfer", cascade="all, delete-orphan")
    from_warehouse: Mapped[Warehouse] = relationship(foreign_keys=[from_warehouse_id])
    to_warehouse: Mapped[Warehouse] = relationship(foreign_keys=[to_warehouse_id])


class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("stock_transfers.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("inventory_batches.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)

    transfer: Mapped[StockTransfer] = relationship(back_populates="items")
    batch: Mapped[InventoryBatch] = relationship()


class StockReservation(Base):
    __tablename__ = "stock_reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("inventory_batches.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="RESERVED", index=True)  # RESERVED, FULFILLED, RELEASED
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[InventoryBatch] = relationship()
    warehouse: Mapped[Warehouse] = relationship()


class OrderFulfillment(Base):
    __tablename__ = "order_fulfillments"

    id: Mapped[int] = mapped_column(primary_key=True)
    fulfillment_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, PICKED, PACKED, SHIPPED, DELIVERED, CANCELLED
    carrier_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["FulfillmentItem"]] = relationship(back_populates="fulfillment", cascade="all, delete-orphan")
    warehouse: Mapped[Warehouse] = relationship()


class FulfillmentItem(Base):
    __tablename__ = "fulfillment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    fulfillment_id: Mapped[int] = mapped_column(ForeignKey("order_fulfillments.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)

    fulfillment: Mapped[OrderFulfillment] = relationship(back_populates="items")
    order_item: Mapped["OrderItem"] = relationship("OrderItem")


class OrderItemBatchAllocation(Base):
    __tablename__ = "order_item_batch_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    fulfillment_item_id: Mapped[int | None] = mapped_column(ForeignKey("fulfillment_items.id", ondelete="CASCADE"), nullable=True, index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("inventory_batches.id", ondelete="RESTRICT"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    allocated_quantity: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    batch: Mapped[InventoryBatch] = relationship()
    warehouse: Mapped[Warehouse] = relationship()


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    transaction_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(50))  # MOMO, VNPAY, COD
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="VND")
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, SUCCESS, FAILED, REFUNDED
    provider_trans_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_pay_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    provider_response_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))
    event_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_raw: Mapped[str] = mapped_column(Text)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    process_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailOutbox(Base):
    __tablename__ = "email_outboxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_email: Mapped[str] = mapped_column(String(255), index=True)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(500))
    body_html: Mapped[str] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ORDER_CONFIRMATION, OTP, RESTOCK_ALERT
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, SENDING, SENT, FAILED
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductReview(Base):
    __tablename__ = "product_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1 to 5
    customer_name: Mapped[str] = mapped_column(String(255))
    comment: Mapped[str] = mapped_column(Text)
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeasonalCampaign(Base):
    __tablename__ = "seasonal_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    disease_name: Mapped[str] = mapped_column(String(255))
    season: Mapped[str] = mapped_column(String(50))  # XUAN, HA, THU, DONG, QUANH_NAM
    symptoms: Mapped[str] = mapped_column(Text)
    prevention: Mapped[str] = mapped_column(Text)
    recommended_product_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", index=True)  # ACTIVE, PAUSED, ENDED
    banner_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserWarehouseMembership(Base):
    __tablename__ = "user_warehouse_memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(50), default="WAREHOUSE_MANAGER")  # WAREHOUSE_MANAGER, WAREHOUSE_STAFF
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="memberships", foreign_keys=[warehouse_id])
