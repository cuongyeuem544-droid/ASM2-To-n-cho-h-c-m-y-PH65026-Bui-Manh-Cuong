from datetime import date, timedelta
import math
from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models import (
    CanonicalProduct,
    DataConflict,
    InventoryBatch,
    PriceObservation,
    ProductCandidate,
    ProductIngredient,
    ProductSku,
    ReviewDecision,
    ScoreHistory,
    User,
    WarehouseBatchStock,
)
from app.models.inventory import ProductReview
from app.models.classification import Category, ProductCategory
from app.models.enums import (
    ConfidenceLabel,
    ConflictStatus,
    ProcessingStatus,
    PublishStatus,
    RegulatoryStatus,
    ReviewDecisionType,
    RxOtcStatus,
    UserRole,
)
from app.schemas.products import (
    CandidateMatchRequest,
    CandidateOut,
    ConflictOut,
    ConflictResolveRequest,
    IngredientOut,
    ProductDetail,
    ProductSummary,
    ReviewCreate,
    ScoreOut,
    ScoreRecalculateResponse,
    SourceFieldOut,
)
from app.services.audit import write_audit
from app.services.scoring import calculate_product_score
from app.services.image_storage import save_and_optimize_uploaded_image, download_and_optimize_image, backfill_product_images


router = APIRouter(tags=["Sản phẩm và kiểm chứng"])
public_router = APIRouter(prefix="/public", tags=["Public API"])


def _product_query():
    return select(CanonicalProduct).options(
        selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient),
        selectinload(CanonicalProduct.source_fields),
        selectinload(CanonicalProduct.conflicts),
        selectinload(CanonicalProduct.scores),
    )


def _detail(product: CanonicalProduct, db: Session | None = None) -> ProductDetail:
    latest_score = max(product.scores, key=lambda item: item.calculated_at) if product.scores else None
    r_cnt = 0
    r_avg = 0.0
    if db is not None:
        rev_stat = db.query(
            func.count(ProductReview.id),
            func.avg(ProductReview.rating),
        ).filter(
            ProductReview.canonical_product_id == product.id,
            ProductReview.is_approved == True,
        ).first()
        if rev_stat and rev_stat[0]:
            r_cnt = int(rev_stat[0])
            r_avg = round(float(rev_stat[1] or 0.0), 1)

    return ProductDetail(
        id=product.id,
        canonical_name=product.canonical_name,
        registration_number=product.registration_number,
        manufacturer=product.manufacturer,
        image_url=product.local_image_url or product.image_url,
        local_image_url=product.local_image_url,
        local_thumbnail_url=product.local_thumbnail_url,
        description=product.description,
        usage_instructions=product.usage_instructions,
        indications=product.indications,
        contraindications=product.contraindications,
        side_effects=product.side_effects,
        storage_conditions=product.storage_conditions,
        rx_otc_status=product.rx_otc_status,
        regulatory_status=product.regulatory_status,
        overall_score=product.overall_score,
        confidence_label=product.confidence_label,
        publish_status=product.publish_status,
        is_demo=product.is_demo,
        updated_at=product.updated_at,
        average_rating=r_avg,
        review_count=r_cnt,
        dosage_form=product.dosage_form,
        route=product.route,
        manufacturing_country=product.manufacturing_country,
        package_description=product.package_description,
        registration_valid_from=product.registration_valid_from,
        registration_valid_to=product.registration_valid_to,
        ingredients=[
            IngredientOut(
                name=item.ingredient.normalized_name,
                strength_value=item.strength_value,
                strength_unit=item.strength_unit,
                original_strength_text=item.original_strength_text,
            )
            for item in product.ingredients
        ],
        source_fields=[SourceFieldOut.model_validate(item) for item in product.source_fields],
        conflicts=[ConflictOut.model_validate(item) for item in product.conflicts],
        latest_score=ScoreOut.model_validate(latest_score) if latest_score else None,
    )


@router.get("/products")
def list_products(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    search: str | None = None,
    label: ConfidenceLabel | None = None,
    rx_otc: RxOtcStatus | None = None,
    product_type: str | None = None,
    category_slug: str | None = None,
    is_demo: bool | None = None,
    publish_status: PublishStatus | None = None,
    has_conflict: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(CanonicalProduct.canonical_name.ilike(pattern), CanonicalProduct.registration_number.ilike(pattern)))
    if label:
        conditions.append(CanonicalProduct.confidence_label == label)
    if rx_otc:
        conditions.append(CanonicalProduct.rx_otc_status == rx_otc)
    if product_type:
        conditions.append(CanonicalProduct.product_type == product_type)
    if category_slug:
        cat_id_subq = select(ProductCategory.product_id).join(Category, Category.id == ProductCategory.category_id).where(
            or_(Category.slug == category_slug, Category.parent_id.in_(select(Category.id).where(Category.slug == category_slug)))
        )
        conditions.append(
            or_(
                CanonicalProduct.category_slug == category_slug,
                CanonicalProduct.id.in_(cat_id_subq)
            )
        )
    if is_demo is not None:
        conditions.append(CanonicalProduct.is_demo == is_demo)
    if publish_status:
        conditions.append(CanonicalProduct.publish_status == publish_status)
    if has_conflict is not None:
        conflict_exists = select(DataConflict.id).where(
            DataConflict.product_id == CanonicalProduct.id,
            DataConflict.status == ConflictStatus.OPEN,
        ).exists()
        conditions.append(conflict_exists if has_conflict else ~conflict_exists)
    total = db.scalar(select(func.count()).select_from(CanonicalProduct).where(*conditions)) or 0
    products = db.scalars(
        select(CanonicalProduct)
        .options(selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient))
        .where(*conditions)
        .order_by(CanonicalProduct.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    p_ids = [p.id for p in products]
    prices_map: dict[int, float] = {}
    stocks_map: dict[int, int] = {}
    near_expiry_map: dict[int, int] = {}
    reviews_map: dict[int, tuple[int, float]] = {}

    if p_ids:
        # 1. Prices
        price_rows = db.query(PriceObservation.product_id, PriceObservation.observed_price).filter(
            PriceObservation.product_id.in_(p_ids)
        ).all()
        for pid, pval in price_rows:
            if pid not in prices_map and pval is not None:
                prices_map[pid] = float(pval)

        # 2. Stocks
        stock_rows = db.query(
            ProductSku.canonical_product_id,
            func.sum(WarehouseBatchStock.quantity_available),
        ).join(
            InventoryBatch, InventoryBatch.sku_id == ProductSku.id
        ).join(
            WarehouseBatchStock, WarehouseBatchStock.batch_id == InventoryBatch.id
        ).filter(
            ProductSku.canonical_product_id.in_(p_ids)
        ).group_by(ProductSku.canonical_product_id).all()
        for pid, total_stk in stock_rows:
            stocks_map[pid] = int(total_stk or 0)

        # 3. Near expiry count (< 90 days)
        today = date.today()
        near_rows = db.query(
            ProductSku.canonical_product_id,
            func.count(InventoryBatch.id),
        ).join(
            InventoryBatch, InventoryBatch.sku_id == ProductSku.id
        ).filter(
            ProductSku.canonical_product_id.in_(p_ids),
            InventoryBatch.expiry_date >= today,
            InventoryBatch.expiry_date <= today + timedelta(days=90),
            InventoryBatch.status == "ACTIVE",
        ).group_by(ProductSku.canonical_product_id).all()
        for pid, n_cnt in near_rows:
            near_expiry_map[pid] = int(n_cnt or 0)

        # 4. Approved reviews summary (Batch query without N+1)
        review_rows = db.query(
            ProductReview.canonical_product_id,
            func.count(ProductReview.id),
            func.avg(ProductReview.rating),
        ).filter(
            ProductReview.canonical_product_id.in_(p_ids),
            ProductReview.is_approved == True,
        ).group_by(ProductReview.canonical_product_id).all()
        for pid, r_cnt, r_avg in review_rows:
            reviews_map[pid] = (int(r_cnt or 0), round(float(r_avg or 0.0), 1))

    items = []
    for p in products:
        item_dict = ProductSummary.model_validate(p).model_dump()
        item_dict["image_url"] = p.local_image_url or p.image_url
        item_dict["local_image_url"] = p.local_image_url
        item_dict["local_thumbnail_url"] = p.local_thumbnail_url
        item_dict["dosage_form"] = p.dosage_form or "Viên nén"
        item_dict["package_description"] = p.package_description or "Hộp tiêu chuẩn"
        item_dict["price"] = prices_map.get(p.id)
        item_dict["total_stock"] = stocks_map.get(p.id, 0)
        item_dict["near_expiry_count"] = near_expiry_map.get(p.id, 0)
        r_cnt, r_avg = reviews_map.get(p.id, (0, 0.0))
        item_dict["review_count"] = r_cnt
        item_dict["average_rating"] = r_avg
        
        # Active ingredient
        ing_names = [pi.ingredient.normalized_name for pi in p.ingredients if pi.ingredient]
        item_dict["active_ingredient"] = ", ".join(ing_names) if ing_names else (p.indications or "—")
        items.append(item_dict)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/products/images/review-queue")
@router.get("/admin/products/images/review-queue")
def get_product_images_review_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str = Query(default="ALL", description="ALL, HAS_LOCAL, HAS_REMOTE, NEEDS_IMAGE"),
    search: str | None = Query(default=None),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    query = select(CanonicalProduct)
    if search and search.strip():
        kw = f"%{search.strip()}%"
        query = query.where(
            or_(
                CanonicalProduct.canonical_name.ilike(kw),
                CanonicalProduct.registration_number.ilike(kw),
                CanonicalProduct.manufacturer.ilike(kw),
            )
        )

    if status == "HAS_LOCAL":
        query = query.where(CanonicalProduct.local_image_url.is_not(None))
    elif status == "HAS_REMOTE":
        query = query.where(CanonicalProduct.image_url.is_not(None), CanonicalProduct.local_image_url.is_(None))
    elif status == "NEEDS_IMAGE":
        query = query.where(CanonicalProduct.local_image_url.is_(None), CanonicalProduct.image_url.is_(None))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    # Aggregate statistics
    total_all = db.scalar(select(func.count(CanonicalProduct.id))) or 0
    total_local = db.scalar(select(func.count(CanonicalProduct.id)).where(CanonicalProduct.local_image_url.is_not(None))) or 0
    total_remote = db.scalar(select(func.count(CanonicalProduct.id)).where(CanonicalProduct.image_url.is_not(None), CanonicalProduct.local_image_url.is_(None))) or 0
    total_needs = db.scalar(select(func.count(CanonicalProduct.id)).where(CanonicalProduct.local_image_url.is_(None), CanonicalProduct.image_url.is_(None))) or 0

    offset = (page - 1) * page_size
    products = db.scalars(query.order_by(CanonicalProduct.id.asc()).offset(offset).limit(page_size)).all()

    items = []
    for p in products:
        eff_img = p.local_image_url or p.image_url or "/images/placeholder-medicine.svg"
        if p.local_image_url:
            img_status = "LOCAL_VERIFIED"
        elif p.image_url:
            img_status = "REMOTE_CDN"
        else:
            img_status = "PLACEHOLDER"

        items.append({
            "id": p.id,
            "canonical_name": p.canonical_name,
            "dosage_form": p.dosage_form or "—",
            "package_description": p.package_description or "—",
            "manufacturer": p.manufacturer or "—",
            "manufacturing_country": p.manufacturing_country or "—",
            "image_url": p.image_url,
            "local_image_url": p.local_image_url,
            "effective_image_url": eff_img,
            "image_status": img_status,
            "publish_mode": p.publish_mode or "REFERENCE_ONLY",
            "publish_status": p.publish_status.value if hasattr(p.publish_status, "value") else str(p.publish_status),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
        "stats": {
            "total": total_all,
            "has_local": total_local,
            "has_remote": total_remote,
            "needs_image": total_needs,
        },
    }


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.scalar(_product_query().where(CanonicalProduct.id == product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return _detail(product, db=db)


@router.post("/products/{product_id}/recalculate", response_model=ScoreRecalculateResponse)
def recalculate(
    product_id: int,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    product = db.scalar(_product_query().where(CanonicalProduct.id == product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    result = calculate_product_score(db, product, "Người dùng yêu cầu tính lại")
    write_audit(db, "RECALCULATE_SCORE", "CanonicalProduct", product.id, user, request, before={"score": result.old_score}, after={"score": result.new_score})
    db.commit()
    return ScoreRecalculateResponse(
        product_id=product.id,
        old_score=result.old_score,
        new_score=result.new_score,
        confidence_label=result.label,
        reasons=result.reasons,
    )


@router.get("/candidates", response_model=list[CandidateOut])
def list_candidates(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: ProcessingStatus | None = None,
    limit: int = Query(100, ge=1, le=200),
):
    query = select(ProductCandidate).order_by(ProductCandidate.id.desc()).limit(limit)
    if status:
        query = query.where(ProductCandidate.processing_status == status)
    return db.scalars(query).all()


@router.post("/candidates/{candidate_id}/match", response_model=CandidateOut)
def decide_candidate_match(
    candidate_id: int,
    payload: CandidateMatchRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    candidate = db.get(ProductCandidate, candidate_id)
    product = db.get(CanonicalProduct, payload.product_id)
    if not candidate or not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy candidate hoặc sản phẩm")
    before = {"canonical_product_id": candidate.canonical_product_id, "status": candidate.processing_status.value}
    if payload.accept:
        candidate.canonical_product_id = product.id
        candidate.processing_status = ProcessingStatus.MATCHED
        decision = ReviewDecisionType.MERGE_ACCEPTED
    else:
        candidate.processing_status = ProcessingStatus.REJECTED
        decision = ReviewDecisionType.MERGE_REJECTED
    db.add(ReviewDecision(product_id=product.id, reviewer_id=user.id, decision=decision, note=payload.note))
    write_audit(db, "DECIDE_MATCH", "ProductCandidate", candidate.id, user, request, before=before, after={"accepted": payload.accept, "product_id": product.id})
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/candidates/{candidate_id}/approve")
def approve_candidate(
    candidate_id: int,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    from app.models import Ingredient, Warehouse
    from app.services.fulfillment_service import FulfillmentRoutingService
    from app.services.importer import parse_rx_otc
    from app.services.normalization import normalize_for_match

    candidate = db.get(ProductCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Không tìm thấy candidate")

    prod = None
    if candidate.canonical_product_id:
        prod = db.get(CanonicalProduct, candidate.canonical_product_id)
        if prod:
            prod.publish_status = PublishStatus.PUBLISHED

    if not prod:
        if candidate.registration_number_text:
            prod = db.scalar(
                select(CanonicalProduct).where(
                    func.lower(CanonicalProduct.registration_number) == candidate.registration_number_text.lower()
                )
            )
        if not prod:
            prod = db.scalar(
                select(CanonicalProduct).where(
                    func.lower(CanonicalProduct.canonical_name) == candidate.observed_name.lower()
                )
            )
        if not prod:
            prod = CanonicalProduct(
                canonical_name=candidate.observed_name,
                registration_number=candidate.registration_number_text,
                dosage_form=candidate.dosage_form_text,
                package_description=candidate.package_text,
                manufacturer=candidate.manufacturer_text,
                image_url=candidate.image_url,
                description=candidate.description,
                usage_instructions=candidate.usage_instructions,
                indications=candidate.indications,
                contraindications=candidate.contraindications,
                side_effects=candidate.side_effects,
                storage_conditions=candidate.storage_conditions,
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=parse_rx_otc(candidate.rx_otc_text),
                publish_status=PublishStatus.PUBLISHED,
                overall_score=85,
                confidence_label=ConfidenceLabel.HIGH_OFFICIAL_MATCH,
                is_demo=False,
            )
            db.add(prod)
            db.flush()

            for ing in (candidate.ingredients_json or []):
                ing_name = ing.get("name") if isinstance(ing, dict) else str(ing)
                if ing_name:
                    norm_ing = normalize_for_match(ing_name)
                    ing_entity = db.scalar(select(Ingredient).where(Ingredient.normalized_name == norm_ing))
                    if not ing_entity:
                        ing_entity = Ingredient(normalized_name=norm_ing, alternative_names=[ing_name])
                        db.add(ing_entity)
                        db.flush()
                    db.add(
                        ProductIngredient(
                            product_id=prod.id,
                            ingredient_id=ing_entity.id,
                            strength_value=ing.get("strength_value") if isinstance(ing, dict) else None,
                            strength_unit=ing.get("strength_unit") if isinstance(ing, dict) else None,
                            original_strength_text=ing.get("original_strength_text") if isinstance(ing, dict) else None,
                        )
                    )

            sku = FulfillmentRoutingService.get_or_create_default_sku(db, prod.id)
            default_wh = db.query(Warehouse).first()
            if default_wh and sku:
                batch = InventoryBatch(
                    sku_id=sku.id,
                    batch_number=f"LOT-APP-{prod.id}-{date.today().strftime('%Y%m')}",
                    expiry_date=date.today() + timedelta(days=730),
                    initial_quantity=100,
                    status="ACTIVE",
                )
                db.add(batch)
                db.flush()
                wh_stock = WarehouseBatchStock(
                    warehouse_id=default_wh.id,
                    batch_id=batch.id,
                    quantity_on_hand=100,
                    quantity_available=100,
                    quantity_reserved=0,
                )
                db.add(wh_stock)

        candidate.canonical_product_id = prod.id

    if prod:
        prod.publish_status = PublishStatus.PUBLISHED
        prod.confidence_label = ConfidenceLabel.HIGH_OFFICIAL_MATCH
        prod.overall_score = max(prod.overall_score or 0, 88)
        try:
            from app.services.search_service import index_single_product
            index_single_product(db, prod)
        except Exception:
            pass

    candidate.processing_status = ProcessingStatus.MATCHED
    db.add(ReviewDecision(product_id=prod.id, reviewer_id=user.id, decision=ReviewDecisionType.MERGE_ACCEPTED, note="Duyệt vào kho chính thức"))
    write_audit(db, "APPROVE_CANDIDATE", "ProductCandidate", candidate.id, user, request, after={"canonical_product_id": prod.id})
    db.commit()
    return {"message": f"Đã duyệt thuốc '{candidate.observed_name}' vào kho thành công", "product_id": prod.id, "candidate_id": candidate.id}


@router.post("/candidates/approve-all")
def approve_all_candidates(
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    from app.models import Ingredient, Warehouse
    from app.services.fulfillment_service import FulfillmentRoutingService
    from app.services.importer import parse_rx_otc
    from app.services.normalization import normalize_for_match

    candidates = db.scalars(
        select(ProductCandidate).where(
            ProductCandidate.processing_status.in_([ProcessingStatus.EXTRACTED, ProcessingStatus.REVIEW_REQUIRED, ProcessingStatus.NEW])
        )
    ).all()

    default_wh = db.query(Warehouse).first()
    approved_count = 0
    for candidate in candidates:
        prod = None
        if candidate.canonical_product_id:
            prod = db.get(CanonicalProduct, candidate.canonical_product_id)
            if prod:
                prod.publish_status = PublishStatus.PUBLISHED
        if not prod and candidate.registration_number_text:
            prod = db.scalar(
                select(CanonicalProduct).where(
                    func.lower(CanonicalProduct.registration_number) == candidate.registration_number_text.lower()
                )
            )
        if not prod:
            prod = db.scalar(
                select(CanonicalProduct).where(
                    func.lower(CanonicalProduct.canonical_name) == candidate.observed_name.lower()
                )
            )
        if not prod:
            prod = CanonicalProduct(
                canonical_name=candidate.observed_name,
                registration_number=candidate.registration_number_text,
                dosage_form=candidate.dosage_form_text,
                package_description=candidate.package_text,
                manufacturer=candidate.manufacturer_text,
                image_url=candidate.image_url,
                description=candidate.description,
                usage_instructions=candidate.usage_instructions,
                indications=candidate.indications,
                contraindications=candidate.contraindications,
                side_effects=candidate.side_effects,
                storage_conditions=candidate.storage_conditions,
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=parse_rx_otc(candidate.rx_otc_text),
                publish_status=PublishStatus.PUBLISHED,
                overall_score=85,
                confidence_label=ConfidenceLabel.HIGH_OFFICIAL_MATCH,
                is_demo=False,
            )
            db.add(prod)
            db.flush()

            for ing in (candidate.ingredients_json or []):
                ing_name = ing.get("name") if isinstance(ing, dict) else str(ing)
                if ing_name:
                    norm_ing = normalize_for_match(ing_name)
                    ing_entity = db.scalar(select(Ingredient).where(Ingredient.normalized_name == norm_ing))
                    if not ing_entity:
                        ing_entity = Ingredient(normalized_name=norm_ing, alternative_names=[ing_name])
                        db.add(ing_entity)
                        db.flush()
                    db.add(
                        ProductIngredient(
                            product_id=prod.id,
                            ingredient_id=ing_entity.id,
                            strength_value=ing.get("strength_value") if isinstance(ing, dict) else None,
                            strength_unit=ing.get("strength_unit") if isinstance(ing, dict) else None,
                            original_strength_text=ing.get("original_strength_text") if isinstance(ing, dict) else None,
                        )
                    )

            sku = FulfillmentRoutingService.get_or_create_default_sku(db, prod.id)
            if default_wh and sku:
                batch = InventoryBatch(
                    sku_id=sku.id,
                    batch_number=f"LOT-ALL-{prod.id}-{date.today().strftime('%Y%m')}",
                    expiry_date=date.today() + timedelta(days=730),
                    initial_quantity=100,
                    status="ACTIVE",
                )
                db.add(batch)
                db.flush()
                wh_stock = WarehouseBatchStock(
                    warehouse_id=default_wh.id,
                    batch_id=batch.id,
                    quantity_on_hand=100,
                    quantity_available=100,
                    quantity_reserved=0,
                )
                db.add(wh_stock)

        candidate.canonical_product_id = prod.id
        if prod:
            prod.publish_status = PublishStatus.PUBLISHED
            prod.confidence_label = ConfidenceLabel.HIGH_OFFICIAL_MATCH
            prod.overall_score = max(prod.overall_score or 0, 88)
            try:
                from app.services.search_service import index_single_product
                index_single_product(db, prod)
            except Exception:
                pass
        candidate.processing_status = ProcessingStatus.MATCHED
        approved_count += 1

    write_audit(db, "APPROVE_ALL_CANDIDATES", "ProductCandidate", 0, user, request, after={"count": approved_count})
    db.commit()
    return {"message": f"Đã duyệt thành công {approved_count} thuốc vào kho chính thức", "approved_count": approved_count}


@router.post("/candidates/{candidate_id}/reject")
def reject_candidate(
    candidate_id: int,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    candidate = db.get(ProductCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Không tìm thấy candidate")
    candidate.processing_status = ProcessingStatus.REJECTED
    write_audit(db, "REJECT_CANDIDATE", "ProductCandidate", candidate.id, user, request)
    db.commit()
    return {"message": f"Đã từ chối bản ghi '{candidate.observed_name}'", "candidate_id": candidate.id}


@router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: ConflictStatus | None = ConflictStatus.OPEN,
    limit: int = Query(100, ge=1, le=200),
):
    query = select(DataConflict).order_by(DataConflict.created_at.desc()).limit(limit)
    if status:
        query = query.where(DataConflict.status == status)
    return db.scalars(query).all()


@router.patch("/conflicts/{conflict_id}", response_model=ConflictOut)
def resolve_conflict(
    conflict_id: int,
    payload: ConflictResolveRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    from datetime import UTC, datetime

    conflict = db.get(DataConflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="Không tìm thấy mâu thuẫn")
    before = {"status": conflict.status.value, "resolution_note": conflict.resolution_note}
    conflict.status = payload.status
    conflict.resolution_note = payload.resolution_note
    conflict.resolved_by = user.id
    conflict.resolved_at = datetime.now(UTC) if payload.status != ConflictStatus.OPEN else None
    write_audit(db, "RESOLVE_CONFLICT", "DataConflict", conflict.id, user, request, before=before, after=payload.model_dump(mode="json"))
    db.commit()
    db.refresh(conflict)
    return conflict


@router.post("/products/{product_id}/reviews", status_code=201)
def create_review(
    product_id: int,
    payload: ReviewCreate,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    review = ReviewDecision(product_id=product_id, reviewer_id=user.id, decision=payload.decision, note=payload.note)
    db.add(review)
    db.flush()
    write_audit(db, "CREATE_REVIEW", "CanonicalProduct", product_id, user, request, after=payload.model_dump(mode="json"))
    db.commit()
    return {"id": review.id, "message": "Đã lưu kết quả kiểm tra dữ liệu"}


@router.get("/products/{product_id}/score-history")
def score_history(product_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(ScoreHistory).where(ScoreHistory.product_id == product_id).order_by(ScoreHistory.calculated_at.desc())).all()


class UpdatePricingRequest(BaseModel):
    price: float
    availability_text: str | None = "Có sẵn"


@router.post("/products/{product_id}/publish")
def publish_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    product.publish_status = PublishStatus.PUBLISHED
    db.commit()
    db.refresh(product)
    return {"message": "Đã duyệt và đăng bán sản phẩm thành công", "product_id": product.id, "publish_status": product.publish_status.value}


@router.post("/products/{product_id}/unpublish")
def unpublish_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    product.publish_status = PublishStatus.DRAFT
    db.commit()
    db.refresh(product)
    return {"message": "Đã chuyển sản phẩm về bản nháp / ngừng bán", "product_id": product.id, "publish_status": product.publish_status.value}


@router.patch("/products/{product_id}/pricing")
def update_product_pricing(
    product_id: int,
    payload: UpdatePricingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    from app.models import PriceObservation, DataSource
    from decimal import Decimal
    po = db.query(PriceObservation).filter(PriceObservation.product_id == product_id).first()
    if po:
        po.observed_price = Decimal(str(payload.price))
        if payload.availability_text:
            po.availability_text = payload.availability_text
    else:
        source = db.query(DataSource).first()
        po = PriceObservation(
            product_id=product_id,
            source_id=source.id if source else 1,
            observed_price=Decimal(str(payload.price)),
            currency="VND",
            availability_text=payload.availability_text or "Có sẵn",
            source_url="https://pharmatrust.vn"
        )
        db.add(po)
    db.commit()
    return {"message": "Đã cập nhật giá bán thành công", "product_id": product_id, "price": payload.price}



@public_router.get("/products")
def public_products(
    db: Session = Depends(get_db),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conditions = [
        CanonicalProduct.is_demo.is_(False),
        CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
        CanonicalProduct.confidence_label == ConfidenceLabel.HIGH_OFFICIAL_MATCH,
        CanonicalProduct.overall_score >= settings.public_api_min_score,
    ]
    if search and search.strip():
        from app.services.search_service import search_product_ids_fts
        fts_ids = search_product_ids_fts(db, search.strip(), limit=page_size * 2)
        if fts_ids:
            conditions.append(CanonicalProduct.id.in_(fts_ids))
        else:
            pattern = f"%{search.strip()}%"
            conditions.append(or_(CanonicalProduct.canonical_name.ilike(pattern), CanonicalProduct.registration_number.ilike(pattern)))
    products = db.scalars(
        select(CanonicalProduct).where(*conditions).order_by(CanonicalProduct.canonical_name).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [ProductSummary.model_validate(item) for item in products], "page": page, "page_size": page_size}


@public_router.get("/search")
def public_search(
    q: str = Query(min_length=2, max_length=100),
    db: Session = Depends(get_db),
):
    return public_products(db=db, search=q, page=1, page_size=20)


@public_router.get("/products/{product_id}", response_model=ProductDetail)
def public_product(product_id: int, db: Session = Depends(get_db)):
    product = db.scalar(
        _product_query().where(
            CanonicalProduct.id == product_id,
            CanonicalProduct.is_demo.is_(False),
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
            CanonicalProduct.overall_score >= settings.public_api_min_score,
        )
    )
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm đủ điều kiện công bố")
    return _detail(product, db=db)

class UpdateProductImageUrlRequest(BaseModel):
    image_url: str


@router.post("/products/{product_id}/image")
@router.post("/admin/products/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """
    Tải lên và đồng bộ ảnh thuốc chính thức:
    1. Kiểm tra quyền Admin/Warehouse Manager.
    2. Xác thực kích thước (max 10MB) và magic bytes nhị phân.
    3. Tối ưu ảnh chính thành WebP 800x800 và thumbnail WebP 250x250.
    4. Cập nhật CanonicalProduct.local_image_url, local_thumbnail_url và image_url.
    5. Ghi nhật ký WarehouseAuditLog bảo đảm truy vết.
    """
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Kích thước tệp vượt quá 10MB.")

    try:
        main_url, thumb_url = save_and_optimize_uploaded_image(
            content=content,
            product_id=product.id,
            original_filename=file.filename or "",
        )
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        logger.error(f"Lỗi khi xử lý ảnh tải lên cho thuốc {product_id}: {exc}")
        raise HTTPException(status_code=500, detail="Lỗi xử lý ảnh nén WebP trên máy chủ.")

    product.local_image_url = main_url
    product.local_thumbnail_url = thumb_url
    product.image_url = main_url
    product.updated_at = utcnow()

    write_audit(
        db=db,
        action="UPLOAD_PRODUCT_IMAGE",
        entity_type="CanonicalProduct",
        entity_id=product.id,
        user=current_user,
        after={
            "filename": file.filename,
            "local_image_url": main_url,
            "local_thumbnail_url": thumb_url,
        },
    )
    db.commit()
    db.refresh(product)

    return {
        "success": True,
        "message": f"Tải lên và tối ưu ảnh WebP cho thuốc '{product.canonical_name}' thành công.",
        "product_id": product.id,
        "local_image_url": main_url,
        "local_thumbnail_url": thumb_url,
        "image_url": main_url,
    }


@router.post("/products/{product_id}/image-url")
@router.post("/admin/products/{product_id}/image-url")
def update_product_image_url(
    product_id: int,
    payload: UpdateProductImageUrlRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """
    Cập nhật URL ảnh thuốc từ bên ngoài và tự động tải về tối ưu WebP nội bộ.
    """
    product = db.get(CanonicalProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    clean_url = payload.image_url.strip()
    if not clean_url:
        raise HTTPException(status_code=400, detail="URL ảnh không được để trống.")

    main_url, thumb_url = download_and_optimize_image(clean_url, product.id)
    product.image_url = clean_url
    if main_url:
        product.local_image_url = main_url
        product.local_thumbnail_url = thumb_url
    product.updated_at = utcnow()

    write_audit(
        db=db,
        action="UPDATE_PRODUCT_IMAGE_URL",
        entity_type="CanonicalProduct",
        entity_id=product.id,
        user=current_user,
        after={"image_url": clean_url, "local_image_url": main_url},
    )
    db.commit()
    db.refresh(product)

    return {
        "success": True,
        "message": "Cập nhật URL ảnh và đồng bộ tối ưu hóa WebP thành công.",
        "product_id": product.id,
        "image_url": product.image_url,
        "local_image_url": product.local_image_url,
        "local_thumbnail_url": product.local_thumbnail_url,
    }


@router.post("/products/images/backfill")
@router.post("/admin/products/images/backfill")
def trigger_backfill_product_images(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
    db: Session = Depends(get_db),
):
    """
    Kích hoạt tiến trình quét và tối ưu hàng loạt ảnh thuốc sang WebP cục bộ.
    """
    stats = backfill_product_images(db=db, max_items=limit)
    return {
        "success": True,
        "message": f"Hoàn tất quét {stats['total_scanned']} ảnh: {stats['succeeded']} thành công, {stats['failed']} thất bại.",
        "stats": stats,
    }

