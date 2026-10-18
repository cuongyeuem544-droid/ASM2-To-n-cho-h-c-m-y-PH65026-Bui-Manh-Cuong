from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    ConfidenceLabel,
    ConflictSeverity,
    ConflictStatus,
    ProcessingStatus,
    PublishStatus,
    RegulatoryStatus,
    ReviewDecisionType,
    RxOtcStatus,
)
from app.schemas.common import ORMModel


class IngredientOut(BaseModel):
    name: str
    strength_value: float | None
    strength_unit: str | None
    original_strength_text: str | None


class ProductSummary(ORMModel):
    id: int
    canonical_name: str
    registration_number: str | None
    manufacturer: str | None
    image_url: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    side_effects: str | None = None
    storage_conditions: str | None = None
    dosage_form: str | None = None
    package_description: str | None = None
    price: float | None = None
    total_stock: int | None = None
    near_expiry_count: int | None = None
    active_ingredient: str | None = None
    rx_otc_status: RxOtcStatus
    product_type: str | None = None
    prescription_status: str | None = None
    category_slug: str | None = None
    regulatory_status: RegulatoryStatus
    overall_score: int
    confidence_label: ConfidenceLabel
    publish_status: PublishStatus
    is_demo: bool
    average_rating: float = 0.0
    review_count: int = 0
    updated_at: datetime


class SourceFieldOut(ORMModel):
    id: int
    source_id: int
    raw_document_id: int | None
    field_name: str
    original_value: str | None
    normalized_value: str | None
    field_confidence: float
    observed_at: datetime
    is_selected_value: bool


class ConflictOut(ORMModel):
    id: int
    product_id: int
    conflict_type: str
    severity: ConflictSeverity
    field_name: str
    source_a_id: int | None
    value_a: str | None
    source_b_id: int | None
    value_b: str | None
    description: str
    status: ConflictStatus
    detected_by: str
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None


class ScoreOut(ORMModel):
    id: int
    product_id: int
    registration_match_score: int
    otc_status_score: int
    ingredient_strength_score: int
    manufacturer_score: int
    package_score: int
    source_consensus_score: int
    recency_score: int
    completeness_score: int
    penalty: int
    total_score: int
    confidence_label: ConfidenceLabel
    scoring_rule_version: str
    calculated_at: datetime


class ProductDetail(ProductSummary):
    dosage_form: str | None
    route: str | None
    manufacturing_country: str | None
    package_description: str | None
    registration_valid_from: date | None
    registration_valid_to: date | None
    ingredients: list[IngredientOut] = []
    source_fields: list[SourceFieldOut] = []
    conflicts: list[ConflictOut] = []
    latest_score: ScoreOut | None = None


class CandidateOut(ORMModel):
    id: int
    raw_document_id: int
    canonical_product_id: int | None
    observed_name: str
    normalized_name: str
    registration_number_text: str | None
    manufacturer_text: str | None
    dosage_form_text: str | None
    package_text: str | None
    rx_otc_text: str | None
    ingredients_json: list[dict]
    image_url: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    side_effects: str | None = None
    storage_conditions: str | None = None
    extraction_confidence: float
    extraction_method: str
    processing_status: ProcessingStatus
    created_at: datetime


class CandidateMatchRequest(BaseModel):
    product_id: int
    accept: bool
    note: str | None = None


class ConflictResolveRequest(BaseModel):
    status: ConflictStatus
    resolution_note: str = Field(min_length=3, max_length=2000)


class ReviewCreate(BaseModel):
    decision: ReviewDecisionType
    note: str | None = Field(default=None, max_length=2000)


class ScoreRecalculateResponse(BaseModel):
    product_id: int
    old_score: int
    new_score: int
    confidence_label: ConfidenceLabel
    reasons: list[str]

