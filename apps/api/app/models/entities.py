from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ConfidenceLabel,
    ConflictSeverity,
    ConflictStatus,
    ProcessingStatus,
    PublishStatus,
    RegulatoryStatus,
    ReviewDecisionType,
    RunStatus,
    RxOtcStatus,
    SourceType,
    UserRole,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_type):
    return Enum(enum_type, native_enum=False, values_callable=lambda items: [item.value for item in items])


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole), default=UserRole.CUSTOMER)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    warehouse_memberships: Mapped[list["UserWarehouseMembership"]] = relationship("UserWarehouseMembership", back_populates="user", cascade="all, delete-orphan", foreign_keys="UserWarehouseMembership.user_id")

    @property
    def warehouse_id(self) -> int | None:
        for m in getattr(self, "warehouse_memberships", []):
            if m.is_active:
                return m.warehouse_id
        return None

    @property
    def warehouse_name(self) -> str | None:
        for m in getattr(self, "warehouse_memberships", []):
            if m.is_active and getattr(m, "warehouse", None):
                return m.warehouse.name
        return None


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[SourceType] = mapped_column(enum_column(SourceType))
    base_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    authority_level: Mapped[int] = mapped_column(Integer, default=1)
    authority_weight: Mapped[float] = mapped_column(Float, default=0.5)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    robots_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    terms_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit: Mapped[float] = mapped_column(Float, default=1.0)
    crawl_frequency: Mapped[str] = mapped_column(String(80), default="MANUAL")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    crawl_runs: Mapped[list[CrawlRun]] = relationship(back_populates="source")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), index=True)
    status: Mapped[RunStatus] = mapped_column(enum_column(RunStatus), default=RunStatus.QUEUED)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pages_requested: Mapped[int] = mapped_column(Integer, default=0)
    pages_success: Mapped[int] = mapped_column(Integer, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, default=0)
    products_discovered: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    source: Mapped[DataSource] = relationship(back_populates="crawl_runs")
    documents: Mapped[list[RawDocument]] = relationship(back_populates="crawl_run")


class RawDocument(Base):
    __tablename__ = "raw_documents"
    __table_args__ = (UniqueConstraint("source_id", "source_url", "content_hash", name="uq_raw_document_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    crawl_run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), nullable=True, index=True)
    source_url: Mapped[str] = mapped_column(String(1500))
    content_type: Mapped[str] = mapped_column(String(150))
    local_storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    crawl_run: Mapped[CrawlRun | None] = relationship(back_populates="documents")
    candidates: Mapped[list[ProductCandidate]] = relationship(back_populates="raw_document")


class ProductCandidate(Base):
    __tablename__ = "product_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_document_id: Mapped[int] = mapped_column(ForeignKey("raw_documents.id", ondelete="CASCADE"), index=True)
    canonical_product_id: Mapped[int | None] = mapped_column(ForeignKey("canonical_products.id"), nullable=True, index=True)
    observed_name: Mapped[str] = mapped_column(String(500))
    normalized_name: Mapped[str] = mapped_column(String(500), index=True)
    registration_number_text: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    manufacturer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dosage_form_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    package_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rx_otc_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ingredients_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    indications: Mapped[str | None] = mapped_column(Text, nullable=True)
    contraindications: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_conditions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0)
    extraction_method: Mapped[str] = mapped_column(String(80), default="PARSER")
    extraction_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(enum_column(ProcessingStatus), default=ProcessingStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    raw_document: Mapped[RawDocument] = relationship(back_populates="candidates")
    canonical_product: Mapped[CanonicalProduct | None] = relationship(back_populates="candidates")


class CanonicalProduct(TimestampMixin, Base):
    __tablename__ = "canonical_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(500), index=True)
    registration_number: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True, index=True)
    dosage_form: Mapped[str | None] = mapped_column(String(300), nullable=True)
    route: Mapped[str | None] = mapped_column(String(200), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manufacturing_country: Mapped[str | None] = mapped_column(String(200), nullable=True)
    package_description: Mapped[str | None] = mapped_column(String(700), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    local_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    local_thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    indications: Mapped[str | None] = mapped_column(Text, nullable=True)
    contraindications: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_conditions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    regulatory_status: Mapped[RegulatoryStatus] = mapped_column(enum_column(RegulatoryStatus), default=RegulatoryStatus.UNKNOWN)
    rx_otc_status: Mapped[RxOtcStatus] = mapped_column(enum_column(RxOtcStatus), default=RxOtcStatus.UNKNOWN)
    registration_valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    overall_score: Mapped[int] = mapped_column(Integer, default=0)
    confidence_label: Mapped[ConfidenceLabel] = mapped_column(enum_column(ConfidenceLabel), default=ConfidenceLabel.INSUFFICIENT_EVIDENCE)
    publish_status: Mapped[PublishStatus] = mapped_column(enum_column(PublishStatus), default=PublishStatus.DRAFT)
    publish_mode: Mapped[str] = mapped_column(String(50), default="MANUAL_REVIEW")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Phân loại danh mục bởi AI & Hàng chờ Admin phân loại
    product_type: Mapped[str] = mapped_column(String(50), default="OTHER", index=True)  # MEDICINE, SUPPLEMENT, MEDICAL_DEVICE, COSMETIC, MOTHER_BABY, PERSONAL_CARE, OTHER
    prescription_status: Mapped[str] = mapped_column(String(50), default="UNKNOWN", index=True)  # OTC, RX, CONTROLLED, UNKNOWN, NOT_APPLICABLE
    target_audience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    atc_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    atc_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atc_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    atc_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    atc_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category_slug: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    subcategory_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    category_review_status: Mapped[str] = mapped_column(String(50), default="AUTO_RESOLVED", index=True)  # AUTO_RESOLVED | CATEGORY_REVIEW_REQUIRED | MANUALLY_RESOLVED
    category_review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    ingredients: Mapped[list[ProductIngredient]] = relationship(back_populates="product", cascade="all, delete-orphan")
    candidates: Mapped[list[ProductCandidate]] = relationship(back_populates="canonical_product")
    source_fields: Mapped[list[ProductSourceField]] = relationship(back_populates="product", cascade="all, delete-orphan")
    conflicts: Mapped[list[DataConflict]] = relationship(back_populates="product", cascade="all, delete-orphan")
    scores: Mapped[list[ConfidenceScore]] = relationship(back_populates="product", cascade="all, delete-orphan")
    price_observations: Mapped[list["PriceObservation"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    category_links: Mapped[list["ProductCategory"]] = relationship("ProductCategory", back_populates="product", cascade="all, delete-orphan")



class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized_name: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    alternative_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    external_codes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class ProductIngredient(Base):
    __tablename__ = "product_ingredients"
    __table_args__ = (UniqueConstraint("product_id", "ingredient_id", "strength_value", "strength_unit", name="uq_product_ingredient"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    strength_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    strength_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    original_strength_text: Mapped[str | None] = mapped_column(String(200), nullable=True)

    product: Mapped[CanonicalProduct] = relationship(back_populates="ingredients")
    ingredient: Mapped[Ingredient] = relationship()


class ProductSourceField(Base):
    __tablename__ = "product_source_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    raw_document_id: Mapped[int | None] = mapped_column(ForeignKey("raw_documents.id"), nullable=True)
    field_name: Mapped[str] = mapped_column(String(100), index=True)
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_confidence: Mapped[float] = mapped_column(Float, default=0)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_selected_value: Mapped[bool] = mapped_column(Boolean, default=False)

    product: Mapped[CanonicalProduct] = relationship(back_populates="source_fields")
    source: Mapped[DataSource] = relationship()


class RegulatoryRecord(Base):
    __tablename__ = "regulatory_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_number: Mapped[str] = mapped_column(String(150), index=True)
    official_name: Mapped[str] = mapped_column(String(500))
    manufacturer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ingredients_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    dosage_form: Mapped[str | None] = mapped_column(String(300), nullable=True)
    package_description: Mapped[str | None] = mapped_column(String(700), nullable=True)
    rx_otc_status: Mapped[RxOtcStatus] = mapped_column(enum_column(RxOtcStatus), default=RxOtcStatus.UNKNOWN)
    regulatory_status: Mapped[RegulatoryStatus] = mapped_column(enum_column(RegulatoryStatus), default=RegulatoryStatus.UNKNOWN)
    source_url: Mapped[str] = mapped_column(String(1500))
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_document_id: Mapped[int | None] = mapped_column(ForeignKey("raw_documents.id"), nullable=True)


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    observed_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(10), default="VND")
    availability_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_url: Mapped[str] = mapped_column(String(1500))

    product: Mapped[CanonicalProduct] = relationship(back_populates="price_observations")


class DataConflict(Base):
    __tablename__ = "data_conflicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    conflict_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[ConflictSeverity] = mapped_column(enum_column(ConflictSeverity))
    field_name: Mapped[str] = mapped_column(String(100))
    source_a_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    value_a: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_b_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    value_b: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[ConflictStatus] = mapped_column(enum_column(ConflictStatus), default=ConflictStatus.OPEN)
    detected_by: Mapped[str] = mapped_column(String(100), default="RULE_ENGINE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped[CanonicalProduct] = relationship(back_populates="conflicts")


class ConfidenceScore(Base):
    __tablename__ = "confidence_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    registration_match_score: Mapped[int] = mapped_column(Integer, default=0)
    otc_status_score: Mapped[int] = mapped_column(Integer, default=0)
    ingredient_strength_score: Mapped[int] = mapped_column(Integer, default=0)
    manufacturer_score: Mapped[int] = mapped_column(Integer, default=0)
    package_score: Mapped[int] = mapped_column(Integer, default=0)
    source_consensus_score: Mapped[int] = mapped_column(Integer, default=0)
    recency_score: Mapped[int] = mapped_column(Integer, default=0)
    completeness_score: Mapped[int] = mapped_column(Integer, default=0)
    penalty: Mapped[int] = mapped_column(Integer, default=0)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    confidence_label: Mapped[ConfidenceLabel] = mapped_column(enum_column(ConfidenceLabel))
    scoring_rule_version: Mapped[str] = mapped_column(String(30), default="1.0")
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[CanonicalProduct] = relationship(back_populates="scores")


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    old_score: Mapped[int] = mapped_column(Integer, default=0)
    new_score: Mapped[int] = mapped_column(Integer)
    old_label: Mapped[str] = mapped_column(String(80))
    new_label: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[ReviewDecisionType] = mapped_column(enum_column(ReviewDecisionType))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CrawlLock(Base):
    __tablename__ = "crawl_locks"

    source_code: Mapped[str] = mapped_column(String(80), primary_key=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    current_run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_timeout_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    overlap_count: Mapped[int] = mapped_column(Integer, default=0)
    last_skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FailedCrawlItem(Base):
    __tablename__ = "failed_crawl_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    crawl_run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(1500))
    error_type: Mapped[str] = mapped_column(String(100), index=True)
    error_message: Mapped[str] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminAlert(Base):
    __tablename__ = "admin_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_code: Mapped[str] = mapped_column(String(80), index=True)
    alert_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(50), default="WARNING")
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(50), index=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_address: Mapped[str] = mapped_column(String(500))
    shipping_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    district_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ward_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="COD")
    payment_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    order_status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 2-Tier 2025 Administrative Model & Legacy Snapshot
    province_code_current: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commune_code_current: Mapped[str | None] = mapped_column(String(50), nullable=True)
    commune_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    formatted_address_current: Mapped[str | None] = mapped_column(String(500), nullable=True)
    legacy_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legacy_district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legacy_ward: Mapped[str | None] = mapped_column(String(100), nullable=True)
    migration_status: Mapped[str | None] = mapped_column(String(50), default="MIGRATED_2025")
    geocode_provider: Mapped[str | None] = mapped_column(String(50), default="nominatim")
    place_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    voucher_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    promotion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.0"))
    discount_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Multi-Warehouse Routing & Fulfillment State Machine
    assigned_warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    assignment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assignment_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    fulfillment_status: Mapped[str] = mapped_column(String(50), default="PENDING_ALLOCATION", index=True)
    estimated_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    assigned_warehouse: Mapped[Optional["Warehouse"]] = relationship("Warehouse", foreign_keys=[assigned_warehouse_id])


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("canonical_products.id", ondelete="SET NULL"), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(500))
    product_sku: Mapped[str | None] = mapped_column(String(150), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[CanonicalProduct | None] = relationship()


