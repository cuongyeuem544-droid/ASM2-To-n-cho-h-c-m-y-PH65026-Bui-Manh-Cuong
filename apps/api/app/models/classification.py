from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.entities import utcnow

if TYPE_CHECKING:
    from app.models.entities import CanonicalProduct, User


class ProductType(Base):
    __tablename__ = "product_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category_kind: Mapped[str] = mapped_column(String(50), default="STOREFRONT", index=True)  # STOREFRONT, THERAPEUTIC, AUDIENCE, SEASONAL
    allowed_product_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # MEDICINE, SUPPLEMENT, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(100), nullable=True)
    featured_image: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    featured_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    featured_subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    parent: Mapped[Category | None] = relationship("Category", remote_side=[id], back_populates="children")
    children: Mapped[list[Category]] = relationship("Category", back_populates="parent", order_by="Category.sort_order")
    product_links: Mapped[list[ProductCategory]] = relationship("ProductCategory", back_populates="category", cascade="all, delete-orphan")


class ProductCategory(Base):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("product_id", "category_id", name="uq_product_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    assignment_method: Mapped[str] = mapped_column(String(50), default="RULE_SUGGESTION")  # OFFICIAL_IMPORT, RULE_SUGGESTION, AI_SUGGESTION, MANUAL
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("product_classification_evidences.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Category] = relationship("Category", back_populates="product_links")
    product: Mapped[CanonicalProduct] = relationship("CanonicalProduct", back_populates="category_links")


class ProductClassificationEvidence(Base):
    __tablename__ = "product_classification_evidences"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(100))
    proposed_value: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(100))  # REGULATORY_REGISTRATION, OFFICIAL_CIRCULAR, PHARMACY_CRAWL, MANUAL
    source_url: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, APPROVED, REJECTED
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductClassificationReview(Base):
    __tablename__ = "product_classification_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    suggested_product_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    suggested_prescription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    suggested_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_fields_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    conflicts_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED, AUTO_RESOLVED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductClassificationHistory(Base):
    __tablename__ = "product_classification_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True)
    previous_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    new_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
