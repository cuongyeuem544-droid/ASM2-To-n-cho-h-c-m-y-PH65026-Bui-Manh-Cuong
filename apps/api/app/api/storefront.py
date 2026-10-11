from datetime import date
import re
import unicodedata
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import CanonicalProduct, PriceObservation, ProductIngredient
from app.models.enums import PublishStatus, RxOtcStatus

router = APIRouter(prefix="/store", tags=["Storefront Khách Hàng"])


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def determine_category_and_subcategory(product: CanonicalProduct) -> tuple[str, str, str]:
    name = (product.canonical_name or "").lower()
    indications = (product.indications or "").lower()
    dosage = (product.dosage_form or "").lower()
    combined = f"{name} {indications} {dosage}"

    is_rx = product.rx_otc_status == RxOtcStatus.PRESCRIPTION

    # 1. Subcategory detection
    if any(k in combined for k in ["paracetamol", "efferalgan", "panadol", "hapacol", "giảm đau", "hạ sốt"]):
        sub_cat = "giam-dau-ha-sot"
    elif any(k in combined for k in ["strepsils", "viên ngậm", "rát họng", "viêm họng", "đau họng"]):
        sub_cat = "tai-mui-hong"
    elif any(k in combined for k in ["bổ phế", "nam hà", "otrivin", "avamys", "hadocort", "xịt mũi", "nghẹt mũi", "ho", "đờm", "viêm phế quản"]):
        sub_cat = "ho-hap-xoang"
    elif any(k in combined for k in ["phosphalugel", "duphalac", "nexium", "smecta", "gaviscon", "dạ dày", "tiêu hóa", "táo bón", "berberin", "tiêu chảy"]):
        sub_cat = "tieu-hoa-da-day"
    elif any(k in combined for k in ["amlor", "lipitor", "crestor", "huyết áp", "mỡ máu", "tim mạch", "daflon"]):
        sub_cat = "tim-mach-huyet-ap"
    elif any(k in combined for k in ["augmentin", "amoxicillin", "zinnat", "cravit", "klacid", "medrol", "kháng sinh", "nhiễm khuẩn"]):
        sub_cat = "khang-sinh-khang-viem"
    elif any(k in combined for k in ["berocca", "vitamin", "khoáng chất", "kẽm", "canxi", "d3"]):
        sub_cat = "vitamin-khoang-chat"
    elif any(k in combined for k in ["orlistat", "béo phì", "giảm cân"]):
        sub_cat = "ho-tro-dieu-tri"
    else:
        sub_cat = "cham-soc-suc-khoe"

    # 2. Main category detection
    if sub_cat == "vitamin-khoang-chat" or "bổ sung" in combined:
        cat_slug = "thuc-pham-chuc-nang"
        cat_name = "Thực Phẩm Chức Năng"
    elif is_rx:
        cat_slug = "thuoc-ke-don"
        cat_name = "Thuốc Kê Đơn"
    else:
        cat_slug = "thuoc-khong-ke-don"
        cat_name = "Thuốc Không Kê Đơn"

    return cat_slug, cat_name, sub_cat


def serialize_product(
    product: CanonicalProduct,
    price: int | None = None,
    rating: float = 0.0,
    review_count: int = 0,
    stock: int = 0,
    eligibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cat_slug, cat_name, sub_cat = determine_category_and_subcategory(product)
    
    # Resolve price from actual DB data or selected SKU
    final_price = price if price is not None else 0
    if eligibility and eligibility.get("selected_sku") and eligibility["selected_sku"].get("base_price"):
        final_price = eligibility["selected_sku"]["base_price"]
    
    sale_price = int(final_price * 0.95) if (final_price and final_price > 80000) else None

    # Ingredients string
    ing_names = []
    if product.ingredients:
        for pi in product.ingredients:
            if pi.ingredient and pi.ingredient.normalized_name:
                name = pi.ingredient.normalized_name
                if pi.original_strength_text:
                    name += f" ({pi.original_strength_text})"
                elif pi.strength_value and pi.strength_unit:
                    name += f" ({pi.strength_value}{pi.strength_unit})"
                ing_names.append(name)
    ingredients_str = ", ".join(ing_names) if ing_names else (product.dosage_form or "Xem tờ hướng dẫn sử dụng")

    base_slug = slugify(product.canonical_name)
    slug = f"{base_slug}-{product.id}"

    # Priority for product image: local optimized WebP -> original remote image -> fallback
    fallback_img = "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800&auto=format&fit=crop&q=80"
    if product.local_image_url:
        image_url = product.local_image_url
    elif product.image_url and product.image_url.startswith("http"):
        image_url = product.image_url
    else:
        image_url = fallback_img

    thumbnail_url = product.local_thumbnail_url or image_url

    is_rx = product.rx_otc_status == RxOtcStatus.PRESCRIPTION
    featured_ids = {16, 56, 57, 58, 59, 60, 61, 62, 63, 65, 66, 67, 68, 70, 71}
    bestseller_ids = {16, 57, 59, 63, 66, 68, 70, 71}

    # Extract eligibility parameters if provided
    is_sale_eligible = False
    can_add_to_cart = False
    cta_type = "CONSULT_PHARMACIST"
    cta_label = "Tư Vấn Dược Sĩ"
    eligibility_tier = product.publish_mode or "REFERENCE_ONLY"
    skus_data: list[dict[str, Any]] = []
    selected_sku_data: dict[str, Any] | None = None
    transparency_data: dict[str, Any] | None = None
    primary_reason = ""
    reasons_list: list[str] = []

    if eligibility:
        is_sale_eligible = eligibility.get("is_eligible_for_sale", False)
        can_add_to_cart = eligibility.get("can_add_to_cart", False)
        cta_type = eligibility.get("cta_type", "CONSULT_PHARMACIST")
        cta_label = eligibility.get("cta_label", "Tư Vấn Dược Sĩ")
        eligibility_tier = eligibility.get("eligibility_tier", product.publish_mode or "REFERENCE_ONLY")
        skus_data = eligibility.get("skus", [])
        selected_sku_data = eligibility.get("selected_sku")
        transparency_data = eligibility.get("transparency_info")
        primary_reason = eligibility.get("primary_reason", "")
        reasons_list = eligibility.get("reasons", [])
        if "available_stock" in eligibility:
            stock = eligibility["available_stock"]
    else:
        # Default intelligent evaluation for product listing when eligibility is not explicitly passed
        if product.publish_status == PublishStatus.PUBLISHED and not product.is_demo and product.publish_mode != "INTERNAL_TEST":
            if is_rx:
                cta_type = "RX_PRESCRIPTION"
                cta_label = "Tư Vấn Dược Sĩ"
                eligibility_tier = "PRESCRIPTION_RESTRICTED"
                is_sale_eligible = False
                can_add_to_cart = False
            elif product.publish_mode == "REFERENCE_ONLY":
                cta_type = "CONSULT_PHARMACIST"
                cta_label = "Tra Cứu Y Tế"
                eligibility_tier = "REFERENCE_ONLY"
                is_sale_eligible = False
                can_add_to_cart = False
            else:
                # Active Published OTC Medicine
                if stock > 0 or final_price > 0:
                    is_sale_eligible = True
                    can_add_to_cart = True
                    cta_type = "BUY_NOW"
                    cta_label = "Chọn Mua"
                    eligibility_tier = "SALE_ELIGIBLE"
                else:
                    is_sale_eligible = False
                    can_add_to_cart = False
                    cta_type = "OUT_OF_STOCK"
                    cta_label = "Tạm Hết Hàng"
                    eligibility_tier = "OUT_OF_STOCK"

    return {
        "id": f"pt-{product.id}",
        "dbId": product.id,
        "name": product.canonical_name,
        "slug": slug,
        "sku": product.registration_number or f"PT-MED-{product.id:04d}",
        "brand": product.manufacturer or "PharmaTrust",
        "category": cat_slug,
        "categoryName": cat_name,
        "subCategory": sub_cat,
        "price": final_price,
        "salePrice": sale_price,
        "images": [image_url],
        "thumbnail": thumbnail_url,
        "shortDescription": (product.description[:180] + "...") if product.description and len(product.description) > 180 else (product.indications or product.canonical_name),
        "description": product.description or product.indications or product.canonical_name,
        "activeIngredient": ingredients_str,
        "dosageForm": product.dosage_form or "Viên nén",
        "packaging": product.package_description or "Hộp tiêu chuẩn",
        "origin": product.manufacturing_country or "Việt Nam",
        "manufacturer": product.manufacturer or "PharmaTrust Hợp Tác",
        "usage": product.usage_instructions or "Dùng theo chỉ định của bác sĩ/dược sĩ hoặc đọc kỹ hướng dẫn sử dụng trong hộp thuốc.",
        "indications": product.indications or "Chỉ định điều trị theo công bố của nhà sản xuất và Cục Quản lý Dược.",
        "contraindications": product.contraindications or "Mẫn cảm với bất kỳ thành phần nào của thuốc. Phụ nữ có thai và cho con bú cần hỏi ý kiến bác sĩ.",
        "sideEffects": product.side_effects or "Thông báo ngay cho bác sĩ hoặc dược sĩ nếu gặp phải bất kỳ tác dụng phụ không mong muốn nào.",
        "precautions": "Đọc kỹ hướng dẫn sử dụng trước khi dùng. Không tự ý tăng liều. Để xa tầm tay trẻ em.",
        "storage": product.storage_conditions or "Bảo quản nơi khô ráo, thoáng mát, nhiệt độ dưới 30°C, tránh ánh sáng trực tiếp.",
        "stock": stock,
        "rating": rating,
        "reviewCount": review_count,
        "isPrescription": is_rx,
        "isFeatured": product.id in featured_ids,
        "isBestSeller": product.id in bestseller_ids,
        "catalogTier": eligibility_tier,
        "isSaleEligible": is_sale_eligible,
        "canAddToCart": can_add_to_cart,
        "ctaType": cta_type,
        "ctaLabel": cta_label,
        "primaryReason": primary_reason,
        "reasons": reasons_list,
        "transparency": transparency_data,
        "skus": skus_data,
        "selectedSku": selected_sku_data,
        "createdAt": product.created_at.strftime("%Y-%m-%d") if product.created_at else "2026-01-01",
    }


@router.get("/products")
def get_store_products(
    category: str | None = None,
    subCategory: str | None = None,
    prescriptionType: str = Query("all", regex="^(all|otc|rx)$"),
    search: str | None = Query(None, max_length=100),
    sort: str = "popular",
    limit: int = Query(150, ge=1, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = (
        select(CanonicalProduct)
        .options(
            selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient),
        )
        .where(
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
            ~CanonicalProduct.canonical_name.like("Hồ sơ%"),
        )
    )

    if prescriptionType == "rx":
        query = query.where(CanonicalProduct.rx_otc_status == RxOtcStatus.PRESCRIPTION)
    elif prescriptionType == "otc":
        query = query.where(CanonicalProduct.rx_otc_status == RxOtcStatus.OTC)

    fts_ids = None
    if search and search.strip():
        from app.services.search_service import search_product_ids_fts
        fts_ids = search_product_ids_fts(db, search.strip(), limit=limit * 2)
        if fts_ids:
            query = query.where(CanonicalProduct.id.in_(fts_ids))
        else:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    CanonicalProduct.canonical_name.ilike(term),
                    CanonicalProduct.manufacturer.ilike(term),
                    CanonicalProduct.indications.ilike(term),
                    CanonicalProduct.registration_number.ilike(term),
                )
            )

    products = db.scalars(query).all()

    # Pre-fetch prices
    prod_ids = [p.id for p in products]
    prices_map: dict[int, int] = {}
    reviews_map: dict[int, tuple[float, int]] = {}
    stocks_map: dict[int, int] = {}
    if prod_ids:
        price_rows = db.query(PriceObservation.product_id, PriceObservation.observed_price).filter(
            PriceObservation.product_id.in_(prod_ids)
        ).all()
        for pid, pval in price_rows:
            if pid not in prices_map and pval is not None:
                prices_map[pid] = int(pval)

        from app.models.inventory import BatchStatus, InventoryBatch, ProductReview, ProductSku, WarehouseBatchStock
        rev_rows = db.query(
            ProductReview.canonical_product_id,
            func.avg(ProductReview.rating),
            func.count(ProductReview.id),
        ).filter(
            ProductReview.canonical_product_id.in_(prod_ids),
            ProductReview.is_approved == True,
        ).group_by(ProductReview.canonical_product_id).all()
        for pid, avg_r, cnt in rev_rows:
            reviews_map[pid] = (round(float(avg_r), 1) if avg_r else 0.0, int(cnt) if cnt else 0)

        stock_rows = db.query(
            ProductSku.canonical_product_id,
            func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0),
        ).select_from(ProductSku).join(
            InventoryBatch, InventoryBatch.sku_id == ProductSku.id
        ).join(
            WarehouseBatchStock, WarehouseBatchStock.batch_id == InventoryBatch.id
        ).filter(
            ProductSku.canonical_product_id.in_(prod_ids),
            InventoryBatch.status == BatchStatus.ACTIVE,
            InventoryBatch.expiry_date > date.today(),
            WarehouseBatchStock.quantity_available > 0,
        ).group_by(ProductSku.canonical_product_id).all()
        for pid, s_qty in stock_rows:
            stocks_map[pid] = int(s_qty)

    serialized = []
    for p in products:
        r_val, r_cnt = reviews_map.get(p.id, (0.0, 0))
        item = serialize_product(
            p,
            price=prices_map.get(p.id),
            rating=r_val,
            review_count=r_cnt,
            stock=stocks_map.get(p.id, 0),
        )
        
        # Category filters in memory
        if category and item["category"] != category:
            continue
        if subCategory and item["subCategory"] != subCategory:
            continue

        serialized.append(item)

    # Sort
    if search and search.strip() and fts_ids and sort == "popular":
        rank_dict = {pid: idx for idx, pid in enumerate(fts_ids)}
        serialized.sort(key=lambda x: rank_dict.get(x["dbId"], 9999))
    elif sort == "newest":
        serialized.sort(key=lambda x: x["dbId"], reverse=True)
    elif sort == "price-asc":
        serialized.sort(key=lambda x: x["price"])
    elif sort == "price-desc":
        serialized.sort(key=lambda x: x["price"], reverse=True)
    elif sort == "rating":
        serialized.sort(key=lambda x: x["rating"], reverse=True)
    else:  # popular / default
        serialized.sort(key=lambda x: (not x["isBestSeller"], not x["isFeatured"], x["dbId"]))

    total = len(serialized)
    paged_items = serialized[offset : offset + limit]

    return {
        "items": paged_items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def resolve_canonical_product(slug_or_id: str, db: Session) -> CanonicalProduct | None:
    match_id = None
    if slug_or_id.isdigit():
        match_id = int(slug_or_id)
    elif slug_or_id.startswith("pt-") and slug_or_id[3:].isdigit():
        match_id = int(slug_or_id[3:])
    else:
        parts = slug_or_id.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            match_id = int(parts[1])

    if match_id:
        product = db.scalar(
            select(CanonicalProduct)
            .options(
                selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient),
            )
            .where(
                CanonicalProduct.id == match_id,
                CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
                CanonicalProduct.publish_mode != "INTERNAL_TEST",
                CanonicalProduct.is_demo == False,
            )
        )
        if product:
            return product

    # Search all published products and find matching slug
    all_prods = db.scalars(
        select(CanonicalProduct)
        .options(
            selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient),
        )
        .where(
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
            CanonicalProduct.publish_mode != "INTERNAL_TEST",
            CanonicalProduct.is_demo == False,
            ~CanonicalProduct.canonical_name.like("Hồ sơ%"),
        )
    ).all()
    for p in all_prods:
        p_slug = slugify(p.canonical_name)
        if p_slug == slug_or_id or f"{p_slug}-{p.id}" == slug_or_id:
            return p

    return None


@router.get("/products/{slug_or_id}")
def get_store_product_detail(
    slug_or_id: str,
    skuId: int | None = Query(None),
    db: Session = Depends(get_db),
):
    product = resolve_canonical_product(slug_or_id, db)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại hoặc chưa được mở bán")

    # Evaluate product eligibility via engine
    from app.services.product_eligibility_service import ProductEligibilityService
    eligibility_res = ProductEligibilityService.evaluate_product_eligibility(product, db, sku_id=skuId)

    # Fetch price fallback if not from SKU
    price_row = db.query(PriceObservation.observed_price).filter(
        PriceObservation.product_id == product.id
    ).first()
    price_val = int(price_row[0]) if (price_row and price_row[0] is not None) else None

    # Fetch real review stats
    from app.models.inventory import ProductReview
    rev_row = db.query(
        func.avg(ProductReview.rating),
        func.count(ProductReview.id),
    ).filter(
        ProductReview.canonical_product_id == product.id,
        ProductReview.is_approved == True,
    ).first()
    p_rating = round(float(rev_row[0]), 1) if (rev_row and rev_row[0] is not None) else 0.0
    p_count = int(rev_row[1]) if (rev_row and rev_row[1] is not None) else 0

    return serialize_product(
        product,
        price=price_val,
        rating=p_rating,
        review_count=p_count,
        eligibility=eligibility_res.to_dict(),
    )


@router.get("/products/{slug_or_id}/eligibility")
def get_store_product_eligibility(
    slug_or_id: str,
    skuId: int | None = Query(None),
    db: Session = Depends(get_db),
):
    product = resolve_canonical_product(slug_or_id, db)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại hoặc chưa được mở bán")

    from app.services.product_eligibility_service import ProductEligibilityService
    eligibility_res = ProductEligibilityService.evaluate_product_eligibility(product, db, sku_id=skuId)
    return eligibility_res.to_dict()


@router.get("/categories")
def get_store_categories(db: Session = Depends(get_db)):
    prods = db.scalars(
        select(CanonicalProduct).where(
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
            ~CanonicalProduct.canonical_name.like("Hồ sơ%"),
        )
    ).all()

    cat_counts: dict[str, int] = {}
    for p in prods:
        c_slug, _, _ = determine_category_and_subcategory(p)
        cat_counts[c_slug] = cat_counts.get(c_slug, 0) + 1

    return [
        {
            "id": "cat-01",
            "name": "Thuốc Không Kê Đơn",
            "slug": "thuoc-khong-ke-don",
            "iconName": "Pill",
            "description": "Các loại thuốc giảm đau, hạ sốt, cảm cúm, tiêu hóa sử dụng an toàn không cần toa bác sĩ.",
            "badge": "Phổ biến nhất",
            "productCount": cat_counts.get("thuoc-khong-ke-don", 0),
            "subCategories": [
                {"id": "sub-01", "name": "Giảm đau - Hạ sốt", "slug": "giam-dau-ha-sot", "isPopular": True},
                {"id": "sub-02", "name": "Tai - Mũi - Họng", "slug": "tai-mui-hong", "isPopular": True},
                {"id": "sub-03", "name": "Hô hấp - Xoang", "slug": "ho-hap-xoang", "isPopular": True},
                {"id": "sub-04", "name": "Tiêu hóa - Dạ dày", "slug": "tieu-hoa-da-day", "isPopular": True},
            ],
        },
        {
            "id": "cat-02",
            "name": "Thuốc Kê Đơn",
            "slug": "thuoc-ke-don",
            "iconName": "Stethoscope",
            "description": "Thuốc đặc trị theo đơn bác sĩ: Kháng sinh, tim mạch, huyết áp, tiểu đường.",
            "badge": "Cần đơn thuốc",
            "productCount": cat_counts.get("thuoc-ke-don", 0),
            "subCategories": [
                {"id": "sub-05", "name": "Kháng sinh - Kháng viêm", "slug": "khang-sinh-khang-viem", "isPopular": True},
                {"id": "sub-06", "name": "Tim mạch - Huyết áp", "slug": "tim-mach-huyet-ap", "isPopular": True},
            ],
        },
        {
            "id": "cat-03",
            "name": "Thực Phẩm Chức Năng",
            "slug": "thuc-pham-chuc-nang",
            "iconName": "HeartPulse",
            "description": "Bổ sung vitamin, khoáng chất, tăng cường đề kháng và bồi bổ sức khỏe toàn diện.",
            "badge": "Chính hãng",
            "productCount": cat_counts.get("thuc-pham-chuc-nang", 0),
            "subCategories": [
                {"id": "sub-07", "name": "Vitamin & Khoáng chất", "slug": "vitamin-khoang-chat", "isPopular": True},
            ],
        },
    ]
