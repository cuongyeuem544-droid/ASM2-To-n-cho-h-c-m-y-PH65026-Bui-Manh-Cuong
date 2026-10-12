from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.classification import (
    Category,
    ProductCategory,
    ProductClassificationEvidence,
    ProductClassificationHistory,
    ProductClassificationReview,
    ProductType,
)
from app.models.entities import CanonicalProduct, User, utcnow
from app.models.enums import ClassificationReviewStatus, LegalProductType, PrescriptionStatus, UserRole
from app.services.audit import write_audit
from app.services.category_service import (
    get_category_tree,
    invalidate_category_cache,
    validate_category_compatibility,
)
from app.services.classification_pipeline import ProductClassificationPipeline

router = APIRouter(prefix="/admin", tags=["Admin Quản Trị Danh Mục & Phân Loại Y Tế"])


# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================

class CategoryCreateRequest(BaseModel):
    parent_id: int | None = None
    code: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=150)
    name: str = Field(min_length=2, max_length=255)
    category_kind: str = Field(default="STOREFRONT")
    allowed_product_type: str | None = None
    description: str | None = None
    icon_name: str | None = None
    badge: str | None = None
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    icon_name: str | None = None
    badge: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    allowed_product_type: str | None = None


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


class ClassificationApproveRequest(BaseModel):
    product_type: str | None = None
    prescription_status: str | None = None
    category_ids: list[int] | None = None
    primary_category_id: int | None = None
    note: str | None = None


class ClassificationRejectRequest(BaseModel):
    reason: str = Field(min_length=3)


class BulkApproveRequest(BaseModel):
    product_ids: list[int]
    product_type: str
    prescription_status: str
    category_ids: list[int]
    primary_category_id: int | None = None
    note: str | None = "Bulk approve by Admin/Data Reviewer"


# =====================================================================
# CATEGORY TREE MANAGEMENT ENDPOINTS
# =====================================================================

@router.get("/categories/tree")
def admin_get_category_tree(
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
):
    """Lấy cây danh mục cấp 1 và cấp 2 kèm số lượng sản phẩm."""
    return get_category_tree(db, force_refresh=True)


@router.post("/categories", status_code=201)
def admin_create_category(
    payload: CategoryCreateRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """Tạo mới danh mục trong cây phân cấp."""
    # Kiểm tra trùng mã hoặc slug
    existing_code = db.scalar(select(Category).where(Category.code == payload.code.strip()))
    if existing_code:
        raise HTTPException(status_code=400, detail=f"Mã danh mục '{payload.code}' đã tồn tại.")

    existing_slug = db.scalar(select(Category).where(Category.slug == payload.slug.strip()))
    if existing_slug:
        raise HTTPException(status_code=400, detail=f"Slug '{payload.slug}' đã tồn tại.")

    if payload.parent_id:
        parent = db.get(Category, payload.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Không tìm thấy danh mục cha.")
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="Hệ thống chỉ hỗ trợ tối đa 2 cấp danh mục (cha và con).")

    new_cat = Category(
        parent_id=payload.parent_id,
        code=payload.code.strip(),
        slug=payload.slug.strip(),
        name=payload.name.strip(),
        category_kind=payload.category_kind,
        allowed_product_type=payload.allowed_product_type,
        description=payload.description,
        icon_name=payload.icon_name,
        badge=payload.badge,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)

    invalidate_category_cache()
    write_audit(db, "CREATE_CATEGORY", "Category", new_cat.id, user, request, after=payload.model_dump())
    return {"message": "Tạo danh mục thành công", "category": {"id": new_cat.id, "name": new_cat.name, "slug": new_cat.slug}}


@router.patch("/categories/{cat_id}")
def admin_update_category(
    cat_id: int,
    payload: CategoryUpdateRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """Cập nhật thông tin danh mục."""
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Không tìm thấy danh mục.")

    before = {"name": cat.name, "is_active": cat.is_active, "sort_order": cat.sort_order}
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(cat, field, val)

    cat.updated_at = utcnow()
    db.commit()
    invalidate_category_cache()
    write_audit(db, "UPDATE_CATEGORY", "Category", cat.id, user, request, before=before, after=update_data)
    return {"message": "Cập nhật danh mục thành công", "category_id": cat.id}


@router.post("/categories/reorder")
def admin_reorder_categories(
    payload: ReorderRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """Thay đổi thứ tự hiển thị của các danh mục."""
    for item in payload.items:
        cat = db.get(Category, item.id)
        if cat:
            cat.sort_order = item.sort_order
    db.commit()
    invalidate_category_cache()
    write_audit(db, "REORDER_CATEGORIES", "Category", 0, user, request, after={"count": len(payload.items)})
    return {"message": "Đã cập nhật thứ tự hiển thị danh mục thành công"}


@router.delete("/categories/{cat_id}")
def admin_delete_category(
    cat_id: int,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Xóa danh mục (chặn tuyệt đối nếu đang có sản phẩm liên kết)."""
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Không tìm thấy danh mục.")

    # Kiểm tra sản phẩm đang gán vào danh mục này
    linked_count = db.scalar(select(func.count()).select_from(ProductCategory).where(ProductCategory.category_id == cat_id)) or 0
    if linked_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể xóa danh mục '{cat.name}' vì đang có {linked_count} sản phẩm liên kết. Vui lòng chuyển sản phẩm sang danh mục khác trước.",
        )

    # Kiểm tra danh mục con
    children_count = db.scalar(select(func.count()).select_from(Category).where(Category.parent_id == cat_id)) or 0
    if children_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể xóa danh mục '{cat.name}' vì đang có {children_count} danh mục con. Hãy xóa hoặc chuyển các danh mục con trước.",
        )

    db.delete(cat)
    db.commit()
    invalidate_category_cache()
    write_audit(db, "DELETE_CATEGORY", "Category", cat_id, user, request, before={"name": cat.name, "slug": cat.slug})
    return {"message": f"Đã xóa danh mục '{cat.name}' thành công"}


# =====================================================================
# CLASSIFICATION REVIEW QUEUE ENDPOINTS
# =====================================================================

@router.get("/classification/review-queue")
def admin_get_review_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("PENDING"),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
):
    """Xem danh sách hàng chờ phân loại sản phẩm y tế cần duyệt."""
    query = (
        select(ProductClassificationReview)
        .where(ProductClassificationReview.status == status)
        .order_by(ProductClassificationReview.created_at.desc())
    )

    total = db.scalar(select(func.count()).select_from(ProductClassificationReview).where(ProductClassificationReview.status == status)) or 0
    reviews = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for r in reviews:
        prod = db.get(CanonicalProduct, r.product_id)
        cat = db.get(Category, r.suggested_category_id) if r.suggested_category_id else None
        items.append({
            "review_id": r.id,
            "product_id": r.product_id,
            "product_name": prod.canonical_name if prod else "",
            "registration_number": prod.registration_number if prod else None,
            "manufacturer": prod.manufacturer if prod else None,
            "image_url": prod.image_url if prod else None,
            "suggested_product_type": r.suggested_product_type,
            "suggested_prescription_status": r.suggested_prescription_status,
            "suggested_category_id": r.suggested_category_id,
            "suggested_category_name": cat.name if cat else None,
            "suggested_category_slug": cat.slug if cat else None,
            "confidence": r.confidence,
            "reasoning": r.reasoning,
            "missing_fields": r.missing_fields_json or [],
            "conflicts": r.conflicts_json or [],
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/classification/{product_id}/approve")
def admin_approve_classification(
    product_id: int,
    payload: ClassificationApproveRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """Phê duyệt kết quả phân loại sản phẩm y tế."""
    prod = db.get(CanonicalProduct, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    # Tìm bản ghi review nếu có
    review = db.scalar(
        select(ProductClassificationReview)
        .where(ProductClassificationReview.product_id == product_id, ProductClassificationReview.status == "PENDING")
        .order_by(ProductClassificationReview.id.desc())
    )

    p_type = payload.product_type or (review.suggested_product_type if review else prod.product_type)
    rx_status = payload.prescription_status or (review.suggested_prescription_status if review else prod.prescription_status)

    if not p_type or p_type == "OTHER":
        raise HTTPException(status_code=400, detail="Vui lòng xác định Loại sản phẩm pháp lý (Product Type) hợp lệ trước khi duyệt.")

    # Quy tắc kiểm tra xung đột
    if p_type in ["COSMETIC", "MEDICAL_DEVICE", "SUPPLEMENT", "MOTHER_BABY", "PERSONAL_CARE"]:
        rx_status = "NOT_APPLICABLE"
    elif p_type == "MEDICINE" and rx_status == "UNKNOWN":
        raise HTTPException(status_code=400, detail="Thuốc (MEDICINE) bắt buộc phải xác định OTC hoặc RX trước khi phê duyệt.")

    prod.product_type = p_type
    prod.prescription_status = rx_status
    prod.category_review_status = "APPROVED"

    # Cập nhật danh mục được duyệt
    target_cat_ids = payload.category_ids or ([review.suggested_category_id] if review and review.suggested_category_id else [])
    if target_cat_ids:
        db.query(ProductCategory).filter(ProductCategory.product_id == product_id).delete()
        primary_id = payload.primary_category_id or target_cat_ids[0]

        for cid in target_cat_ids:
            cat_obj = db.get(Category, cid)
            if cat_obj:
                is_comp, err = validate_category_compatibility(p_type, cat_obj)
                if not is_comp:
                    raise HTTPException(status_code=400, detail=err)

                db.add(
                    ProductCategory(
                        product_id=product_id,
                        category_id=cid,
                        is_primary=bool(cid == primary_id),
                        assignment_method="MANUAL",
                        confidence=1.0,
                        assigned_by=user.id,
                        approved_by=user.id,
                        approved_at=utcnow(),
                    )
                )

        primary_cat = db.get(Category, primary_id)
        if primary_cat:
            prod.category_slug = primary_cat.slug

    if review:
        review.status = "APPROVED"
        review.reviewed_by = user.id
        review.reviewed_at = utcnow()

    # Ghi lại lịch sử
    db.add(
        ProductClassificationHistory(
            product_id=product_id,
            new_data_json={"product_type": p_type, "prescription_status": rx_status, "category_ids": target_cat_ids},
            changed_by=user.id,
            reason=payload.note or "Phê duyệt bởi Admin/Data Reviewer",
            evidence_source="ADMIN_APPROVAL",
        )
    )

    db.commit()
    write_audit(db, "APPROVE_CLASSIFICATION", "CanonicalProduct", product_id, user, request, after=payload.model_dump())
    return {"message": f"Đã phê duyệt phân loại thành công cho sản phẩm '{prod.canonical_name}'", "product_id": product_id}


@router.post("/classification/{product_id}/reject")
def admin_reject_classification(
    product_id: int,
    payload: ClassificationRejectRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """Từ chối đề xuất phân loại và yêu cầu bổ sung hồ sơ."""
    prod = db.get(CanonicalProduct, product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm.")

    review = db.scalar(
        select(ProductClassificationReview)
        .where(ProductClassificationReview.product_id == product_id, ProductClassificationReview.status == "PENDING")
        .order_by(ProductClassificationReview.id.desc())
    )

    if review:
        review.status = "REJECTED"
        review.rejection_reason = payload.reason
        review.reviewed_by = user.id
        review.reviewed_at = utcnow()

    prod.category_review_status = "REJECTED"
    prod.category_review_reason = payload.reason

    db.add(
        ProductClassificationHistory(
            product_id=product_id,
            changed_by=user.id,
            reason=f"Từ chối phân loại: {payload.reason}",
            evidence_source="ADMIN_REJECTION",
        )
    )

    db.commit()
    write_audit(db, "REJECT_CLASSIFICATION", "CanonicalProduct", product_id, user, request, after=payload.model_dump())
    return {"message": f"Đã từ chối phân loại cho sản phẩm '{prod.canonical_name}'", "product_id": product_id}


@router.post("/classification/bulk-approve")
def admin_bulk_approve_classification(
    payload: BulkApproveRequest,
    request: Request,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """Phân loại và phê duyệt hàng loạt cho các sản phẩm cùng nhóm pháp lý."""
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Danh sách sản phẩm trống.")

    approved_count = 0
    primary_id = payload.primary_category_id or (payload.category_ids[0] if payload.category_ids else None)

    for pid in payload.product_ids:
        prod = db.get(CanonicalProduct, pid)
        if not prod:
            continue

        prod.product_type = payload.product_type
        prod.prescription_status = payload.prescription_status
        prod.category_review_status = "APPROVED"

        db.query(ProductCategory).filter(ProductCategory.product_id == pid).delete()
        for cid in payload.category_ids:
            db.add(
                ProductCategory(
                    product_id=pid,
                    category_id=cid,
                    is_primary=bool(cid == primary_id),
                    assignment_method="MANUAL",
                    confidence=1.0,
                    assigned_by=user.id,
                    approved_by=user.id,
                    approved_at=utcnow(),
                )
            )

        if primary_id:
            p_cat = db.get(Category, primary_id)
            if p_cat:
                prod.category_slug = p_cat.slug

        # Đánh dấu các review chờ thành APPROVED
        pending_reviews = db.scalars(
            select(ProductClassificationReview).where(
                ProductClassificationReview.product_id == pid,
                ProductClassificationReview.status == "PENDING",
            )
        ).all()
        for pr in pending_reviews:
            pr.status = "APPROVED"
            pr.reviewed_by = user.id
            pr.reviewed_at = utcnow()

        approved_count += 1

    db.commit()
    write_audit(db, "BULK_APPROVE_CLASSIFICATION", "CanonicalProduct", 0, user, request, after={"count": approved_count, "product_type": payload.product_type})
    return {"message": f"Đã phê duyệt hàng loạt thành công {approved_count} sản phẩm", "approved_count": approved_count}


@router.get("/classification/history/{product_id}")
def admin_get_classification_history(
    product_id: int,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
):
    """Xem nhật ký kiểm tra và thay đổi phân loại của một sản phẩm."""
    records = db.scalars(
        select(ProductClassificationHistory)
        .where(ProductClassificationHistory.product_id == product_id)
        .order_by(ProductClassificationHistory.created_at.desc())
    ).all()

    return records
