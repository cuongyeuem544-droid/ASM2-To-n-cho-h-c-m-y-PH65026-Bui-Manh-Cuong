import json
from datetime import datetime, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import CanonicalProduct, PriceObservation, User
from app.models.enums import PublishStatus, RxOtcStatus, UserRole
from app.models.inventory import SeasonalCampaign

store_campaign_router = APIRouter(prefix="/store/campaigns", tags=["Storefront Khách Hàng - Chiến Dịch Mùa Bệnh"])
admin_campaign_router = APIRouter(prefix="/admin/campaigns", tags=["Quản Trị Chiến Dịch Mùa Bệnh"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class SeasonalCampaignCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    disease_name: str = Field(..., min_length=2, max_length=255)
    season: str = Field(..., description="XUAN | HA | THU | DONG | MUA_MUA | QUANH_NAM")
    symptoms: str = Field(..., min_length=5, description="Triệu chứng nhận biết")
    prevention: str = Field(..., min_length=5, description="Biện pháp phòng ngừa và lời khuyên y tế")
    recommended_product_ids: Optional[List[int]] = Field(default=[], description="Danh sách ID sản phẩm chỉ định")
    status: str = Field(default="ACTIVE", description="ACTIVE | PAUSED | ENDED")
    banner_image_url: Optional[str] = None


class SeasonalCampaignUpdateRequest(BaseModel):
    title: Optional[str] = None
    disease_name: Optional[str] = None
    season: Optional[str] = None
    symptoms: Optional[str] = None
    prevention: Optional[str] = None
    recommended_product_ids: Optional[List[int]] = None
    status: Optional[str] = None
    banner_image_url: Optional[str] = None


class RecommendedProductItem(BaseModel):
    id: int
    dbId: int
    name: str
    registration_number: Optional[str] = None
    price: int
    image_url: Optional[str] = None
    dosage_form: Optional[str] = None
    indications: Optional[str] = None
    is_rx: bool


class SeasonalCampaignDetailResponse(BaseModel):
    id: int
    slug: str
    title: str
    disease_name: str
    season: str
    symptoms: str
    prevention: str
    status: str
    banner_image_url: Optional[str] = None
    recommended_products: List[RecommendedProductItem]
    created_at: str


# ==============================================================================
# HELPERS
# ==============================================================================

def _resolve_recommended_products(db: Session, raw_ids: Optional[str]) -> List[RecommendedProductItem]:
    if not raw_ids:
        return []
    try:
        p_ids = json.loads(raw_ids)
        if not isinstance(p_ids, list):
            return []
    except Exception:
        return []

    if not p_ids:
        return []

    # Truy vấn sản phẩm và giá niêm yết
    products = db.scalars(
        select(CanonicalProduct)
        .where(
            CanonicalProduct.id.in_(p_ids),
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
        )
    ).all()

    # Query prices
    price_rows = db.query(PriceObservation.product_id, PriceObservation.observed_price).filter(
        PriceObservation.product_id.in_(p_ids)
    ).all()
    prices_map = {pid: int(val) for pid, val in price_rows if val is not None}

    results = []
    for p in products:
        img = p.local_thumbnail_url or p.local_image_url or p.image_url or "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800"
        results.append(
            RecommendedProductItem(
                id=p.id,
                dbId=p.id,
                name=p.canonical_name,
                registration_number=p.registration_number,
                price=prices_map.get(p.id, 0),
                image_url=img,
                dosage_form=p.dosage_form or "Viên nén",
                indications=p.indications or p.description,
                is_rx=p.rx_otc_status == RxOtcStatus.PRESCRIPTION,
            )
        )
    return results


def _slugify(text: str) -> str:
    import re
    import unicodedata
    slug = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "chien-dich"


# ==============================================================================
# STOREFRONT ENDPOINTS
# ==============================================================================

@store_campaign_router.get("", response_model=List[SeasonalCampaignDetailResponse])
def get_active_campaigns(
    season: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Storefront: Lấy danh sách các chuyên mục dịch bệnh và sức khỏe theo mùa đang kích hoạt (status=ACTIVE).
    Kèm danh sách các loại thuốc điều trị / phòng ngừa chỉ định.
    """
    stmt = select(SeasonalCampaign).where(SeasonalCampaign.status == "ACTIVE")
    if season:
        stmt = stmt.where(SeasonalCampaign.season == season.upper())
    stmt = stmt.order_by(desc(SeasonalCampaign.id))

    campaigns = db.scalars(stmt).all()

    return [
        SeasonalCampaignDetailResponse(
            id=c.id,
            slug=c.slug,
            title=c.title,
            disease_name=c.disease_name,
            season=c.season,
            symptoms=c.symptoms,
            prevention=c.prevention,
            status=c.status,
            banner_image_url=c.banner_image_url,
            recommended_products=_resolve_recommended_products(db, c.recommended_product_ids),
            created_at=c.created_at.strftime("%d/%m/%Y") if c.created_at else "",
        )
        for c in campaigns
    ]


@store_campaign_router.get("/{slug}", response_model=SeasonalCampaignDetailResponse)
def get_campaign_by_slug(
    slug: str,
    db: Session = Depends(get_db),
):
    """
    Storefront: Xem chi tiết cẩm nang phòng ngừa và toa thuốc điều trị theo mùa theo đường dẫn (slug).
    """
    c = db.scalar(select(SeasonalCampaign).where(SeasonalCampaign.slug == slug.strip()))
    if not c or c.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Không tìm thấy chiến dịch theo mùa")

    return SeasonalCampaignDetailResponse(
        id=c.id,
        slug=c.slug,
        title=c.title,
        disease_name=c.disease_name,
        season=c.season,
        symptoms=c.symptoms,
        prevention=c.prevention,
        status=c.status,
        banner_image_url=c.banner_image_url,
        recommended_products=_resolve_recommended_products(db, c.recommended_product_ids),
        created_at=c.created_at.strftime("%d/%m/%Y") if c.created_at else "",
    )


# ==============================================================================
# ADMIN ENDPOINTS
# ==============================================================================

@admin_campaign_router.get("", response_model=List[SeasonalCampaignDetailResponse])
def admin_list_campaigns(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN] Xem toàn bộ chiến dịch bệnh theo mùa (kể cả PAUSED, ENDED).
    """
    stmt = select(SeasonalCampaign)
    if status_filter:
        stmt = stmt.where(SeasonalCampaign.status == status_filter.upper())
    stmt = stmt.order_by(desc(SeasonalCampaign.id))
    campaigns = db.scalars(stmt).all()

    return [
        SeasonalCampaignDetailResponse(
            id=c.id,
            slug=c.slug,
            title=c.title,
            disease_name=c.disease_name,
            season=c.season,
            symptoms=c.symptoms,
            prevention=c.prevention,
            status=c.status,
            banner_image_url=c.banner_image_url,
            recommended_products=_resolve_recommended_products(db, c.recommended_product_ids),
            created_at=c.created_at.strftime("%d/%m/%Y %H:%M") if c.created_at else "",
        )
        for c in campaigns
    ]


@admin_campaign_router.post("", response_model=SeasonalCampaignDetailResponse)
def admin_create_campaign(
    payload: SeasonalCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN ONLY] Tạo mới chiến dịch cẩm nang mùa bệnh và gắn sản phẩm khuyến nghị.
    """
    base_slug = _slugify(payload.title)
    unique_slug = base_slug

    # Kiểm tra trùng slug
    existing = db.scalar(select(SeasonalCampaign).where(SeasonalCampaign.slug == unique_slug))
    if existing:
        import time
        unique_slug = f"{base_slug}-{int(time.time())}"

    json_product_ids = json.dumps(payload.recommended_product_ids or [])

    campaign = SeasonalCampaign(
        slug=unique_slug,
        title=payload.title.strip(),
        disease_name=payload.disease_name.strip(),
        season=payload.season.upper(),
        symptoms=payload.symptoms.strip(),
        prevention=payload.prevention.strip(),
        recommended_product_ids=json_product_ids,
        status=payload.status.upper(),
        banner_image_url=payload.banner_image_url,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return SeasonalCampaignDetailResponse(
        id=campaign.id,
        slug=campaign.slug,
        title=campaign.title,
        disease_name=campaign.disease_name,
        season=campaign.season,
        symptoms=campaign.symptoms,
        prevention=campaign.prevention,
        status=campaign.status,
        banner_image_url=campaign.banner_image_url,
        recommended_products=_resolve_recommended_products(db, campaign.recommended_product_ids),
        created_at=campaign.created_at.strftime("%d/%m/%Y %H:%M") if campaign.created_at else "",
    )


@admin_campaign_router.put("/{campaign_id}", response_model=SeasonalCampaignDetailResponse)
def admin_update_campaign(
    campaign_id: int,
    payload: SeasonalCampaignUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN ONLY] Cập nhật thông tin chiến dịch mùa bệnh.
    """
    c = db.scalar(select(SeasonalCampaign).where(SeasonalCampaign.id == campaign_id))
    if not c:
        raise HTTPException(status_code=404, detail="Không tìm thấy chiến dịch")

    if payload.title is not None:
        c.title = payload.title.strip()
    if payload.disease_name is not None:
        c.disease_name = payload.disease_name.strip()
    if payload.season is not None:
        c.season = payload.season.upper()
    if payload.symptoms is not None:
        c.symptoms = payload.symptoms.strip()
    if payload.prevention is not None:
        c.prevention = payload.prevention.strip()
    if payload.recommended_product_ids is not None:
        c.recommended_product_ids = json.dumps(payload.recommended_product_ids)
    if payload.status is not None:
        c.status = payload.status.upper()
    if payload.banner_image_url is not None:
        c.banner_image_url = payload.banner_image_url

    db.commit()
    db.refresh(c)

    return SeasonalCampaignDetailResponse(
        id=c.id,
        slug=c.slug,
        title=c.title,
        disease_name=c.disease_name,
        season=c.season,
        symptoms=c.symptoms,
        prevention=c.prevention,
        status=c.status,
        banner_image_url=c.banner_image_url,
        recommended_products=_resolve_recommended_products(db, c.recommended_product_ids),
        created_at=c.created_at.strftime("%d/%m/%Y %H:%M") if c.created_at else "",
    )


@admin_campaign_router.patch("/{campaign_id}/status")
def admin_toggle_campaign_status(
    campaign_id: int,
    status: str = "ACTIVE",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN ONLY] Chuyển đổi trạng thái chiến dịch: ACTIVE (kích hoạt), PAUSED (tạm dừng), ENDED (kết thúc).
    """
    c = db.scalar(select(SeasonalCampaign).where(SeasonalCampaign.id == campaign_id))
    if not c:
        raise HTTPException(status_code=404, detail="Không tìm thấy chiến dịch")

    c.status = status.upper()
    db.commit()
    return {"id": c.id, "status": c.status, "message": f"Đã chuyển trạng thái chiến dịch sang {c.status}"}


@admin_campaign_router.delete("/{campaign_id}")
def admin_delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [ADMIN ONLY] Xóa chiến dịch mùa bệnh.
    """
    c = db.scalar(select(SeasonalCampaign).where(SeasonalCampaign.id == campaign_id))
    if not c:
        raise HTTPException(status_code=404, detail="Không tìm thấy chiến dịch")

    db.delete(c)
    db.commit()
    return {"success": True, "message": f"Đã xóa chiến dịch #{campaign_id}"}
