"""
apps/api/app/models/returns.py

SQLAlchemy Models for Phase 2:
Returns, Exchanges, Refunds, Reverse Logistics, and Item Inspection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_type):
    return Enum(enum_type, native_enum=False, values_callable=lambda items: [item.value for item in items])


class ReturnRequestType(StrEnum):
    RETURN = "RETURN"
    EXCHANGE = "EXCHANGE"


class ReturnStatus(StrEnum):
    REQUESTED = "REQUESTED"
    ASSIGNED_TO_WAREHOUSE = "ASSIGNED_TO_WAREHOUSE"
    WAITING_CUSTOMER_SHIPMENT = "WAITING_CUSTOMER_SHIPMENT"
    IN_TRANSIT = "IN_TRANSIT"
    REVIEWING = "REVIEWING"
    NEEDS_CUSTOMER_INFO = "NEEDS_CUSTOMER_INFO"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    WAITING_CUSTOMER_RETURN = "WAITING_CUSTOMER_RETURN"
    RETURN_IN_TRANSIT = "RETURN_IN_TRANSIT"
    RECEIVED = "RECEIVED"
    INSPECTING = "INSPECTING"
    INSPECTION_COMPLETED = "INSPECTION_COMPLETED"
    WAITING_MANAGER_APPROVAL = "WAITING_MANAGER_APPROVAL"
    WAITING_CUSTOMER_EVIDENCE = "WAITING_CUSTOMER_EVIDENCE"
    WAITING_MANAGER_REVIEW = "WAITING_MANAGER_REVIEW"
    CANCELLED_EVIDENCE_TIMEOUT = "CANCELLED_EVIDENCE_TIMEOUT"
    REFUND_PENDING = "REFUND_PENDING"
    REFUND_PROCESSING = "REFUND_PROCESSING"
    EXCHANGE_PENDING = "EXCHANGE_PENDING"
    REFUNDED = "REFUNDED"
    REFUND_FAILED = "REFUND_FAILED"
    RESTOCKED = "RESTOCKED"
    QUARANTINED = "QUARANTINED"
    DISPOSED = "DISPOSED"
    EXCHANGED = "EXCHANGED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ReturnEvidenceRequestStatus(StrEnum):
    OPEN = "OPEN"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"


class ReturnMethod(StrEnum):
    CUSTOMER_SHIP = "CUSTOMER_SHIP"
    STORE_RETURN = "STORE_RETURN"
    PICKUP = "PICKUP"


class ItemCondition(StrEnum):
    SEALED = "SEALED"
    OPENED = "OPENED"
    DAMAGED = "DAMAGED"
    DEFECTIVE = "DEFECTIVE"
    WRONG_ITEM = "WRONG_ITEM"
    GOOD_CONDITION = "GOOD_CONDITION"
    UNSELLABLE = "UNSELLABLE"
    UNKNOWN = "UNKNOWN"


class RestockDestination(StrEnum):
    SELLABLE_STOCK = "SELLABLE_STOCK"
    QUARANTINE = "QUARANTINE"
    NON_SELLABLE_DISPOSE = "NON_SELLABLE_DISPOSE"


class RefundMethod(StrEnum):
    COD_MANUAL_BANK = "COD_MANUAL_BANK"
    CASH_AT_STORE = "CASH_AT_STORE"
    MOMO_ONLINE = "MOMO_ONLINE"
    BANK_TRANSFER = "BANK_TRANSFER"


class RefundStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CANCELLED = "CANCELLED"


class ReconciliationStatus(StrEnum):
    MATCHED = "MATCHED"
    PENDING = "PENDING"
    MISMATCH = "MISMATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ExchangeStatus(StrEnum):
    PENDING = "PENDING"
    WAITING_RETURN = "WAITING_RETURN"
    INSPECTION = "INSPECTION"
    WAITING_PAYMENT = "WAITING_PAYMENT"
    ALLOCATING_STOCK = "ALLOCATING_STOCK"
    READY_TO_SHIP = "READY_TO_SHIP"
    SHIPPING = "SHIPPING"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReturnRequest(Base):
    __tablename__ = "return_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    customer_name: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(50), index=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    request_type: Mapped[str] = mapped_column(String(20), default=ReturnRequestType.RETURN.value)
    status: Mapped[str] = mapped_column(String(50), default=ReturnStatus.REQUESTED.value, index=True)

    reason_code: Mapped[str] = mapped_column(String(50))
    reason_text: Mapped[str] = mapped_column(String(255))
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    return_method: Mapped[str] = mapped_column(String(50), default=ReturnMethod.CUSTOMER_SHIP.value)
    carrier_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    return_address_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_visible_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_staff_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    inspected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    order: Mapped["Order"] = relationship("Order")
    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id])
    items: Mapped[list["ReturnItem"]] = relationship("ReturnItem", back_populates="return_request", cascade="all, delete-orphan")
    evidences: Mapped[list["ReturnEvidence"]] = relationship("ReturnEvidence", back_populates="return_request", cascade="all, delete-orphan")
    history: Mapped[list["ReturnStatusHistory"]] = relationship("ReturnStatusHistory", back_populates="return_request", cascade="all, delete-orphan")
    refunds: Mapped[list["Refund"]] = relationship("Refund", back_populates="return_request")
    exchange_orders: Mapped[list["ExchangeOrder"]] = relationship("ExchangeOrder", back_populates="return_request")
    warehouse_cases: Mapped[list["WarehouseReturnCase"]] = relationship("WarehouseReturnCase", back_populates="return_request", cascade="all, delete-orphan")
    evidence_requests: Mapped[list["ReturnEvidenceRequest"]] = relationship("ReturnEvidenceRequest", back_populates="return_request", cascade="all, delete-orphan")


class ReturnItem(Base):
    __tablename__ = "return_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_request_id: Mapped[int] = mapped_column(ForeignKey("return_requests.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id", ondelete="RESTRICT"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="RESTRICT"), index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_skus.id", ondelete="SET NULL"), nullable=True)

    product_name: Mapped[str] = mapped_column(String(500))
    original_quantity: Mapped[int] = mapped_column(Integer)
    requested_quantity: Mapped[int] = mapped_column(Integer)
    approved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)

    unit_price_at_purchase: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    allocated_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"))
    net_paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    requested_refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    approved_refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"))

    rejected_quantity: Mapped[int] = mapped_column(Integer, default=0)
    restock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    customer_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition_reported: Mapped[str | None] = mapped_column(String(50), nullable=True)

    condition: Mapped[str] = mapped_column(String(50), default=ItemCondition.UNKNOWN.value)
    restock_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    restock_destination: Mapped[str | None] = mapped_column(String(50), nullable=True)

    original_batch_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    restocked_batch_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True)
    restocked_warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    inspection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    warehouse_return_case_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_return_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def accepted_quantity(self) -> int:
        return self.approved_quantity

    @accepted_quantity.setter
    def accepted_quantity(self, val: int) -> None:
        self.approved_quantity = val

    @property
    def inspected_condition(self) -> str:
        return self.condition

    @inspected_condition.setter
    def inspected_condition(self, val: str) -> None:
        self.condition = val

    @property
    def inspection_notes(self) -> str | None:
        return self.inspection_note

    @inspection_notes.setter
    def inspection_notes(self, val: str | None) -> None:
        self.inspection_note = val

    return_request: Mapped[ReturnRequest] = relationship("ReturnRequest", back_populates="items")
    order_item: Mapped["OrderItem"] = relationship("OrderItem")
    product: Mapped["CanonicalProduct"] = relationship("CanonicalProduct")
    warehouse_case: Mapped["WarehouseReturnCase | None"] = relationship("WarehouseReturnCase", back_populates="items")


class ReturnEvidence(Base):
    __tablename__ = "return_evidences"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_request_id: Mapped[int] = mapped_column(ForeignKey("return_requests.id", ondelete="CASCADE"), index=True)
    return_item_id: Mapped[int | None] = mapped_column(ForeignKey("return_items.id", ondelete="SET NULL"), nullable=True)

    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_url: Mapped[str] = mapped_column(String(1000))
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100), default="image/jpeg", nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    file_category: Mapped[str | None] = mapped_column(String(50), default="DAMAGE_PHOTO", nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    warehouse_return_case_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_return_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    evidence_request_id: Mapped[int | None] = mapped_column(ForeignKey("return_evidence_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def file_type(self) -> str | None:
        return self.mime_type or self.file_category

    @file_type.setter
    def file_type(self, val: str | None) -> None:
        self.mime_type = val

    @property
    def uploaded_by_user_id(self) -> int | None:
        return self.uploaded_by

    @uploaded_by_user_id.setter
    def uploaded_by_user_id(self, val: int | None) -> None:
        self.uploaded_by = val

    return_request: Mapped[ReturnRequest] = relationship("ReturnRequest", back_populates="evidences")
    warehouse_case: Mapped["WarehouseReturnCase | None"] = relationship("WarehouseReturnCase", back_populates="evidences")
    evidence_request: Mapped["ReturnEvidenceRequest | None"] = relationship("ReturnEvidenceRequest", back_populates="evidences")


class ReturnEvidenceRequest(Base):
    __tablename__ = "return_evidence_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    return_request_id: Mapped[int] = mapped_column(ForeignKey("return_requests.id", ondelete="CASCADE"), index=True)
    warehouse_return_case_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_return_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    return_item_id: Mapped[int | None] = mapped_column(ForeignKey("return_items.id", ondelete="SET NULL"), nullable=True, index=True)

    reason: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    required_image_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default=ReturnEvidenceRequestStatus.OPEN.value, index=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    return_request: Mapped["ReturnRequest"] = relationship("ReturnRequest", back_populates="evidence_requests")
    warehouse_case: Mapped["WarehouseReturnCase | None"] = relationship("WarehouseReturnCase", back_populates="evidence_requests")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    requested_by: Mapped["User"] = relationship("User", foreign_keys=[requested_by_user_id])
    customer: Mapped["User | None"] = relationship("User", foreign_keys=[customer_id])
    return_item: Mapped["ReturnItem | None"] = relationship("ReturnItem", foreign_keys=[return_item_id])
    evidences: Mapped[list["ReturnEvidence"]] = relationship("ReturnEvidence", back_populates="evidence_request")


class ReturnStatusHistory(Base):
    __tablename__ = "return_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_request_id: Mapped[int] = mapped_column(ForeignKey("return_requests.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_return_case_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_return_cases.id", ondelete="SET NULL"), nullable=True, index=True)

    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50))

    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), default="System", nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), default="SYSTEM", nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_safe: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def changed_by_user_id(self) -> int | None:
        return self.actor_id

    @changed_by_user_id.setter
    def changed_by_user_id(self, val: int | None) -> None:
        self.actor_id = val

    return_request: Mapped[ReturnRequest] = relationship("ReturnRequest", back_populates="history")
    warehouse_case: Mapped["WarehouseReturnCase | None"] = relationship("WarehouseReturnCase", back_populates="history")


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    return_request_id: Mapped[int | None] = mapped_column(ForeignKey("return_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_return_case_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_return_cases.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True, index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="VND")
    refund_method: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default=RefundStatus.PENDING.value, index=True)

    reason: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)

    beneficiary_bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    beneficiary_account_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    beneficiary_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    manual_reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manual_proof_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    provider_refund_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    failure_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    reconciliation_status: Mapped[str] = mapped_column(String(50), default=ReconciliationStatus.PENDING.value, index=True)

    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def refund_amount(self) -> Decimal:
        return self.amount

    @refund_amount.setter
    def refund_amount(self, val: Decimal) -> None:
        self.amount = val

    @property
    def beneficiary_bank(self) -> str | None:
        return self.beneficiary_bank_name

    @beneficiary_bank.setter
    def beneficiary_bank(self, val: str | None) -> None:
        self.beneficiary_bank_name = val

    @property
    def bank_transfer_ref(self) -> str | None:
        return self.manual_reference_number

    @bank_transfer_ref.setter
    def bank_transfer_ref(self, val: str | None) -> None:
        self.manual_reference_number = val

    @property
    def gateway_trans_id(self) -> str | None:
        return self.provider_refund_id

    @gateway_trans_id.setter
    def gateway_trans_id(self, val: str | None) -> None:
        self.provider_refund_id = val

    @property
    def proof_document_url(self) -> str | None:
        return self.manual_proof_storage_key

    @proof_document_url.setter
    def proof_document_url(self, val: str | None) -> None:
        self.manual_proof_storage_key = val

    @property
    def processed_at(self) -> datetime | None:
        return self.succeeded_at or self.processing_at

    @processed_at.setter
    def processed_at(self, val: datetime | None) -> None:
        self.succeeded_at = val

    @property
    def reconciled_at(self) -> datetime | None:
        return self.succeeded_at

    @reconciled_at.setter
    def reconciled_at(self, val: datetime | None) -> None:
        pass

    # Relationships
    order: Mapped["Order"] = relationship("Order")
    return_request: Mapped[ReturnRequest | None] = relationship("ReturnRequest", back_populates="refunds")
    attempts: Mapped[list["RefundAttempt"]] = relationship("RefundAttempt", back_populates="refund", cascade="all, delete-orphan")
    warehouse_case: Mapped["WarehouseReturnCase | None"] = relationship("WarehouseReturnCase", back_populates="refunds")


class RefundAttempt(Base):
    __tablename__ = "refund_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_id: Mapped[int] = mapped_column(ForeignKey("refunds.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)

    provider: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(100), index=True)
    request_reference: Mapped[str] = mapped_column(String(100))
    provider_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(50))

    safe_request_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    safe_response_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def gateway_provider(self) -> str:
        return self.provider

    @gateway_provider.setter
    def gateway_provider(self, val: str) -> None:
        self.provider = val

    @property
    def request_payload_json(self) -> dict[str, Any] | None:
        return self.safe_request_metadata

    @request_payload_json.setter
    def request_payload_json(self, val: dict[str, Any] | None) -> None:
        self.safe_request_metadata = val

    @property
    def response_payload_json(self) -> dict[str, Any] | None:
        return self.safe_response_metadata

    @response_payload_json.setter
    def response_payload_json(self, val: dict[str, Any] | None) -> None:
        self.safe_response_metadata = val

    refund: Mapped[Refund] = relationship("Refund", back_populates="attempts")


class WarehouseReturnCase(Base):
    __tablename__ = "warehouse_return_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    return_request_id: Mapped[int] = mapped_column(ForeignKey("return_requests.id", ondelete="CASCADE"), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True)
    fulfillment_id: Mapped[int | None] = mapped_column(ForeignKey("order_fulfillments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_staff_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    inspected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    refund_processed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="REQUESTED", index=True)
    carrier_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    package_condition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manager_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(50), nullable=True)  # RESTOCK, QUARANTINE, DISPOSE
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    return_request: Mapped["ReturnRequest"] = relationship("ReturnRequest", back_populates="warehouse_cases")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    fulfillment: Mapped["OrderFulfillment | None"] = relationship("OrderFulfillment")
    assigned_staff: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_staff_id])
    inspected_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[inspected_by_user_id])
    approved_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by_user_id])
    refund_processed_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[refund_processed_by_user_id])
    items: Mapped[list["ReturnItem"]] = relationship("ReturnItem", back_populates="warehouse_case")
    inspections: Mapped[list["ReturnInspection"]] = relationship("ReturnInspection", back_populates="warehouse_case", cascade="all, delete-orphan")
    evidences: Mapped[list["ReturnEvidence"]] = relationship("ReturnEvidence", back_populates="warehouse_case")
    refunds: Mapped[list["Refund"]] = relationship("Refund", back_populates="warehouse_case")
    history: Mapped[list["ReturnStatusHistory"]] = relationship("ReturnStatusHistory", back_populates="warehouse_case")
    evidence_requests: Mapped[list["ReturnEvidenceRequest"]] = relationship("ReturnEvidenceRequest", back_populates="warehouse_case")


class ReturnInspection(Base):
    __tablename__ = "return_inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("warehouse_return_cases.id", ondelete="CASCADE"), index=True)
    return_item_id: Mapped[int] = mapped_column(ForeignKey("return_items.id", ondelete="CASCADE"), index=True)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)
    accepted_quantity: Mapped[int] = mapped_column(Integer, default=0)
    rejected_quantity: Mapped[int] = mapped_column(Integer, default=0)
    package_condition: Mapped[str] = mapped_column(String(50), default="SEALED")
    seal_intact: Mapped[bool] = mapped_column(Boolean, default=True)
    batch_matched: Mapped[bool] = mapped_column(Boolean, default=True)
    expiry_matched: Mapped[bool] = mapped_column(Boolean, default=True)
    storage_condition_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    damage_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str] = mapped_column(String(50), default="RESTOCK")
    inspected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    warehouse_case: Mapped["WarehouseReturnCase"] = relationship("WarehouseReturnCase", back_populates="inspections")
    return_item: Mapped["ReturnItem"] = relationship("ReturnItem")
    inspector: Mapped["User | None"] = relationship("User", foreign_keys=[inspected_by])


class ExchangeOrder(Base):
    __tablename__ = "exchange_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    return_request_id: Mapped[int] = mapped_column(ForeignKey("return_requests.id", ondelete="CASCADE"), index=True)
    original_order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)

    status: Mapped[str] = mapped_column(String(50), default=ExchangeStatus.PENDING.value)
    original_credit: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    replacement_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_difference: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    additional_payment_required: Mapped[bool] = mapped_column(Boolean, default=False)
    refund_required: Mapped[bool] = mapped_column(Boolean, default=False)

    additional_payment_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True)
    difference_refund_id: Mapped[int | None] = mapped_column(ForeignKey("refunds.id", ondelete="SET NULL"), nullable=True)
    replacement_fulfillment_id: Mapped[int | None] = mapped_column(ForeignKey("order_fulfillments.id", ondelete="SET NULL"), nullable=True)

    shipping_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    carrier_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def returned_items_value(self) -> Decimal:
        return self.original_credit

    @returned_items_value.setter
    def returned_items_value(self, val: Decimal) -> None:
        self.original_credit = val

    @property
    def replacement_items_value(self) -> Decimal:
        return self.replacement_subtotal

    @replacement_items_value.setter
    def replacement_items_value(self, val: Decimal) -> None:
        self.replacement_subtotal = val

    return_request: Mapped[ReturnRequest] = relationship("ReturnRequest", back_populates="exchange_orders")
    items: Mapped[list["ExchangeItem"]] = relationship("ExchangeItem", back_populates="exchange_order", cascade="all, delete-orphan")


class ExchangeItem(Base):
    __tablename__ = "exchange_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange_order_id: Mapped[int] = mapped_column(ForeignKey("exchange_orders.id", ondelete="CASCADE"), index=True)
    original_order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True)

    replacement_product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="RESTRICT"), index=True)
    replacement_sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_skus.id", ondelete="SET NULL"), nullable=True)
    sku_code: Mapped[str | None] = mapped_column(String(150), nullable=True)
    replacement_product_name: Mapped[str] = mapped_column(String(500))

    quantity: Mapped[int] = mapped_column(Integer)
    replacement_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    original_credit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"))
    difference_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def product_id(self) -> int:
        return self.replacement_product_id

    @product_id.setter
    def product_id(self, val: int) -> None:
        self.replacement_product_id = val

    @property
    def sku_id(self) -> int | None:
        return self.replacement_sku_id

    @sku_id.setter
    def sku_id(self, val: int | None) -> None:
        self.replacement_sku_id = val

    @property
    def product_name(self) -> str:
        return self.replacement_product_name

    @product_name.setter
    def product_name(self, val: str) -> None:
        self.replacement_product_name = val

    @property
    def unit_price(self) -> Decimal:
        return self.replacement_unit_price

    @unit_price.setter
    def unit_price(self, val: Decimal) -> None:
        self.replacement_unit_price = val

    @property
    def subtotal(self) -> Decimal:
        return self.replacement_unit_price * Decimal(str(self.quantity))

    exchange_order: Mapped[ExchangeOrder] = relationship("ExchangeOrder", back_populates="items")
    replacement_product: Mapped["CanonicalProduct"] = relationship("CanonicalProduct")
