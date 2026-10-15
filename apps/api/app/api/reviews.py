from datetime import datetime, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import CanonicalProduct, Order, OrderItem, User
from app.models.enums import UserRole
from app.models.inventory import ProductReview

store_review_router = APIRouter(prefix="/store/products", tags=["Storefront Khách Hàng - Đánh Giá"])
admin_review_router = APIRouter(prefix="/admin/reviews", tags=["Quản Trị Đánh Giá & Nhận Xét"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class CreateReviewRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Điểm đánh giá từ 1 đến 5 sao")
    customer_name: str = Field(..., min_length=2, max_length=100, description="Tên người đánh giá")
    comment: str = Field(..., min_length=5, max_length=1000, description="Nội dung nhận xét")
    order_code: Optional[str] = Field(None, description="Mã đơn hàng đã mua để xác thực (Verified Purchase)")


class ReviewItemResponse(BaseModel):
    id: int
    canonical_product_id: int
    customer_name: str
    rating: int
    comment: str
    is_verified_purchase: bool
    is_approved: bool
    created_at: str
    order_code: Optional[str] = None


class ProductReviewSummaryResponse(BaseModel):
    average_rating: float
    total_reviews: int
    verified_reviews_count: int
    rating_distribution: dict[int, int]  # { 5: count, 4: count, ... }
    reviews: List[ReviewItemResponse]


class UpdateReviewStatusRequest(BaseModel):
    is_approved: bool


# ==============================================================================
# STOREFRONT ENDPOINTS
# ==============================================================================

@store_review_router.get("/{product_id}/reviews", response_model=ProductReviewSummaryResponse)
def get_product_reviews(
    product_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách đánh giá đã được kiểm duyệt (is_approved=True) của một sản phẩm.
    Tính toán trung bình sao và thống kê số lượng đánh giá thực tế từ CSDL.
    """
    prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.id == product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

    # Truy vấn các đánh giá đã duyệt
    reviews_stmt = (
        select(ProductReview)
        .where(
            ProductReview.canonical_product_id == product_id,
            ProductReview.is_approved == True,
        )
        .order_by(desc(ProductReview.id))
    )
    all_approved = db.scalars(reviews_stmt).all()
    paged_reviews = all_approved[offset : offset + limit]

    total_count = len(all_approved)
    avg_rating = round(sum(r.rating for r in all_approved) / total_count, 1) if total_count > 0 else 0.0
    verified_count = sum(1 for r in all_approved if r.is_verified_purchase)

    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in all_approved:
        if r.rating in distribution:
            distribution[r.rating] += 1

    # Prefetch order codes
    order_ids = [r.order_id for r in paged_reviews if r.order_id]
    order_map = {}
    if order_ids:
        orders = db.scalars(select(Order).where(Order.id.in_(order_ids))).all()
        order_map = {o.id: o.order_code for o in orders}

    return ProductReviewSummaryResponse(
        average_rating=avg_rating,
        total_reviews=total_count,
        verified_reviews_count=verified_count,
        rating_distribution=distribution,
        reviews=[
            ReviewItemResponse(
                id=r.id,
                canonical_product_id=r.canonical_product_id,
                customer_name=r.customer_name,
                rating=r.rating,
                comment=r.comment,
                is_verified_purchase=r.is_verified_purchase,
                is_approved=r.is_approved,
                created_at=r.created_at.strftime("%d/%m/%Y") if r.created_at else "",
                order_code=order_map.get(r.order_id) if r.order_id else None,
            )
            for r in paged_reviews
        ],
    )


@store_review_router.post("/{product_id}/reviews", response_model=ReviewItemResponse)
def submit_product_review(
    product_id: int,
    payload: CreateReviewRequest,
    db: Session = Depends(get_db),
):
    """
    Khách hàng gửi đánh giá cho sản phẩm.
    Nếu cung cấp mã đơn hàng hợp lệ có chứa sản phẩm này, tự động gắn nhãn "Đã mua hàng chính hãng" (Verified Purchase).
    """
    prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.id == product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

    is_verified = False
    matched_order_id = None

    if payload.order_code and payload.order_code.strip():
        # Kiểm tra đơn hàng có tồn tại và đã từng mua sản phẩm này chưa
        clean_code = payload.order_code.strip()
        order = db.scalar(select(Order).where(Order.order_code == clean_code))
        if order:
            has_item = any(item.product_id == product_id for item in order.items)
            if has_item:
                is_verified = True
                matched_order_id = order.id

    review = ProductReview(
        canonical_product_id=product_id,
        order_id=matched_order_id,
        rating=payload.rating,
        customer_name=payload.customer_name.strip(),
        comment=payload.comment.strip(),
        is_verified_purchase=is_verified,
        is_approved=True,  # Mặc định duyệt tự động, kiểm duyệt sau
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return ReviewItemResponse(
        id=review.id,
        canonical_product_id=review.canonical_product_id,
        customer_name=review.customer_name,
        rating=review.rating,
        comment=review.comment,
        is_verified_purchase=review.is_verified_purchase,
        is_approved=review.is_approved,
        created_at=review.created_at.strftime("%d/%m/%Y") if review.created_at else "",
        order_code=payload.order_code if is_verified else None,
    )


# ==============================================================================
# ADMIN ENDPOINTS
# ==============================================================================

@admin_review_router.get("", response_model=List[dict[str, Any]])
def admin_list_reviews(
    product_id: Optional[int] = None,
    is_approved: Optional[bool] = None,
    verified_only: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN] Xem toàn bộ danh sách đánh giá của khách hàng trên toàn sàn.
    """
    stmt = select(ProductReview)
    if product_id is not None:
        stmt = stmt.where(ProductReview.canonical_product_id == product_id)
    if is_approved is not None:
        stmt = stmt.where(ProductReview.is_approved == is_approved)
    if verified_only is not None:
        stmt = stmt.where(ProductReview.is_verified_purchase == verified_only)

    stmt = stmt.order_by(desc(ProductReview.id)).limit(limit).offset(offset)
    reviews = db.scalars(stmt).all()

    # Prefetch product names and order codes
    prod_ids = [r.canonical_product_id for r in reviews]
    prods = db.scalars(select(CanonicalProduct).where(CanonicalProduct.id.in_(prod_ids))).all()
    prod_map = {p.id: p.canonical_name for p in prods}

    order_ids = [r.order_id for r in reviews if r.order_id]
    order_map = {}
    if order_ids:
        orders = db.scalars(select(Order).where(Order.id.in_(order_ids))).all()
        order_map = {o.id: o.order_code for o in orders}

    results = []
    for r in reviews:
        results.append({
            "id": r.id,
            "canonical_product_id": r.canonical_product_id,
            "product_name": prod_map.get(r.canonical_product_id, "Sản phẩm"),
            "customer_name": r.customer_name,
            "rating": r.rating,
            "comment": r.comment,
            "is_verified_purchase": r.is_verified_purchase,
            "is_approved": r.is_approved,
            "order_code": order_map.get(r.order_id) if r.order_id else None,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M") if r.created_at else "",
        })
    return results


@admin_review_router.patch("/{review_id}/status")
def admin_toggle_review_status(
    review_id: int,
    payload: UpdateReviewStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN] Bật hoặc ẩn đánh giá khỏi giao diện người dùng (kiểm duyệt nội dung).
    """
    review = db.scalar(select(ProductReview).where(ProductReview.id == review_id))
    if not review:
        raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá")

    review.is_approved = payload.is_approved
    db.commit()
    db.refresh(review)

    return {
        "id": review.id,
        "is_approved": review.is_approved,
        "message": "Đã duyệt hiển thị đánh giá" if review.is_approved else "Đã ẩn đánh giá khỏi storefront",
    }


@admin_review_router.delete("/{review_id}")
def admin_delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN ONLY] Xóa hoàn toàn đánh giá vi phạm quy chuẩn khỏi hệ thống.
    """
    review = db.scalar(select(ProductReview).where(ProductReview.id == review_id))
    if not review:
        raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá")

    db.delete(review)
    db.commit()
    return {"success": True, "message": f"Đã xóa vĩnh viễn đánh giá #{review_id}"}
