from pydantic import BaseModel
from datetime import date
import math
import re
import unicodedata
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import CanonicalProduct, Category, PriceObservation, ProductCategory, ProductIngredient
from app.models.enums import PublishStatus, RxOtcStatus
from app.services.category_service import get_category_tree

router = APIRouter(prefix="/store", tags=["Storefront Khách Hàng"])


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


CATEGORY_NAME_MAP = {
    "thuoc-khong-ke-don": "Thuốc Không Kê Đơn",
    "thuoc-ke-don": "Thuốc Kê Đơn (Rx)",
    "thuc-pham-chuc-nang": "Vitamin & Thực Phẩm Chức Năng",
    "duoc-my-pham": "Dược Mỹ Phẩm & Chăm Sóc Da",
    "thiet-bi-y-te": "Thiết Bị & Dụng Cụ Y Tế",
    "me-va-be": "Mẹ & Bé",
}


def determine_category_and_subcategory(product: CanonicalProduct) -> tuple[str, str, str]:
    # 1. Ưu tiên liên kết ProductCategory đã được gán hoặc category_slug trên sản phẩm
    if product.category_slug and product.category_slug in CATEGORY_NAME_MAP:
        cat_slug = product.category_slug
        cat_name = CATEGORY_NAME_MAP[cat_slug]
        sub_cat = product.subcategory_slug or "pho-bien"
        return cat_slug, cat_name, sub_cat

    # 2. Kiểm tra theo product_type
    p_type = getattr(product, "product_type", None)
    if p_type == "COSMETIC":
        return "duoc-my-pham", CATEGORY_NAME_MAP["duoc-my-pham"], product.subcategory_slug or "cham-soc-da"
    elif p_type == "MEDICAL_DEVICE":
        return "thiet-bi-y-te", CATEGORY_NAME_MAP["thiet-bi-y-te"], product.subcategory_slug or "thiet-bi-khac"
    elif p_type == "SUPPLEMENT":
        return "thuc-pham-chuc-nang", CATEGORY_NAME_MAP["thuc-pham-chuc-nang"], product.subcategory_slug or "vitamin-khoang-chat"
    elif p_type == "MOTHER_BABY":
        return "me-va-be", CATEGORY_NAME_MAP["me-va-be"], product.subcategory_slug or "me-be-khac"

    name = (product.canonical_name or "").lower()
    indications = (product.indications or "").lower()
    dosage = (product.dosage_form or "").lower()
    combined = f"{name} {indications} {dosage}"

    is_rx = product.rx_otc_status == RxOtcStatus.PRESCRIPTION

    # 3. Phân loại theo từ khóa y tế
    if any(k in combined for k in ["bầu", "mẹ và bé", "sơ sinh", "trẻ em", "tã", "bỉm"]):
        return "me-va-be", CATEGORY_NAME_MAP["me-va-be"], product.subcategory_slug or "me-be-khac"
    elif any(k in combined for k in ["sữa rửa mặt", "chống nắng", "dưỡng da", "mỹ phẩm", "serum"]):
        return "duoc-my-pham", CATEGORY_NAME_MAP["duoc-my-pham"], product.subcategory_slug or "cham-soc-da"
    elif any(k in combined for k in ["máy đo", "nhiệt kế", "huyết áp", "băng gạc", "khí dung"]):
        return "thiet-bi-y-te", CATEGORY_NAME_MAP["thiet-bi-y-te"], product.subcategory_slug or "thiet-bi-khac"

    # Subcategory detection cho Thuốc & TPCN
    if any(k in combined for k in ["paracetamol", "efferalgan", "panadol", "hapacol", "giảm đau", "hạ sốt"]):
        sub_cat = "giam-dau-ha-sot"
    elif any(k in combined for k in ["strepsils", "viên ngậm", "rát họng", "viêm họng", "đau họng"]):
        sub_cat = "tri-ho-cam-cum"
    elif any(k in combined for k in ["bổ phế", "nam hà", "otrivin", "avamys", "hadocort", "xịt mũi", "nghẹt mũi", "ho", "đờm", "viêm phế quản"]):
        sub_cat = "tri-ho-cam-cum"
    elif any(k in combined for k in ["phosphalugel", "duphalac", "nexium", "smecta", "gaviscon", "dạ dày", "tiêu hóa", "táo bón", "berberin", "tiêu chảy"]):
        sub_cat = "da-day-tieu-hoa"
    elif any(k in combined for k in ["amlor", "lipitor", "crestor", "huyết áp", "mỡ máu", "tim mạch", "daflon"]):
        sub_cat = "tim-mach-huyet-ap"
    elif any(k in combined for k in ["augmentin", "amoxicillin", "zinnat", "cravit", "klacid", "medrol", "kháng sinh", "nhiễm khuẩn"]):
        sub_cat = "khang-sinh"
    elif any(k in combined for k in ["berocca", "vitamin", "khoáng chất", "kẽm", "canxi", "d3"]):
        sub_cat = "vitamin-khoang-chat"
    elif any(k in combined for k in ["orlistat", "béo phì", "giảm cân"]):
        sub_cat = "otc-khac"
    else:
        sub_cat = "otc-khac"

    if sub_cat == "vitamin-khoang-chat" or "bổ sung" in combined:
        cat_slug = "thuc-pham-chuc-nang"
        cat_name = CATEGORY_NAME_MAP["thuc-pham-chuc-nang"]
    elif is_rx:
        cat_slug = "thuoc-ke-don"
        cat_name = CATEGORY_NAME_MAP["thuoc-ke-don"]
    else:
        cat_slug = "thuoc-khong-ke-don"
        cat_name = CATEGORY_NAME_MAP["thuoc-khong-ke-don"]

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
    
    # Giá khuyến mãi thực tế (chỉ thiết lập khi có chương trình phê duyệt; không tự sinh giả mạo)
    sale_price = None

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

    # Priority for product image: local optimized WebP -> original remote image -> neutral placeholder
    fallback_img = "/images/placeholder-medicine.svg"
    if product.local_image_url:
        image_url = product.local_image_url
    elif product.image_url and product.image_url.startswith("http"):
        image_url = product.image_url
    else:
        image_url = fallback_img

    thumbnail_url = product.local_thumbnail_url or image_url

    is_rx = product.rx_otc_status == RxOtcStatus.PRESCRIPTION
    is_featured = bool(getattr(product, "is_featured", False))
    is_bestseller = False

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
            if stock <= 0:
                is_sale_eligible = False
                can_add_to_cart = False
                cta_type = "OUT_OF_STOCK"
                cta_label = "Tạm Hết Hàng"
                eligibility_tier = "OUT_OF_STOCK"
                primary_reason = "Tạm hết hàng hoặc các lô thuốc đã hết hạn sử dụng."
            elif is_rx:
                cta_type = "RX_PRESCRIPTION"
                cta_label = "Gửi Đơn Thuốc Để Dược Sĩ Tư Vấn"
                eligibility_tier = "PRESCRIPTION_RESTRICTED"
                is_sale_eligible = False
                can_add_to_cart = False
                primary_reason = "Thuốc kê đơn (Rx) không được phép bán trực tuyến theo quy định của Bộ Y Tế. Cần có đơn thuốc để Dược sĩ kiểm tra và tư vấn."
            elif product.publish_mode == "REFERENCE_ONLY":
                cta_type = "CONSULT_PHARMACIST"
                cta_label = "Tra Cứu Y Tế"
                eligibility_tier = "REFERENCE_ONLY"
                is_sale_eligible = False
                can_add_to_cart = False
            else:
                # Active Published OTC Medicine with stock > 0
                if stock > 0 and final_price > 0:
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
        "brand": product.manufacturer or "Đang cập nhật",
        "productType": getattr(product, "product_type", "MEDICINE") or "MEDICINE",
        "prescriptionStatus": getattr(product, "prescription_status", "RX" if is_rx else "OTC") or ("RX" if is_rx else "OTC"),
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
        "dosageForm": product.dosage_form or "Đang cập nhật theo hồ sơ đăng ký",
        "packaging": product.package_description or "Đang cập nhật theo hồ sơ đăng ký",
        "origin": product.manufacturing_country or "Chưa có thông tin xuất xứ",
        "manufacturer": product.manufacturer or "Đang cập nhật theo hồ sơ đăng ký",
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
        "isFeatured": is_featured,
        "isBestSeller": is_bestseller,
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


def _unwrap_param(val: Any, fallback: Any = None) -> Any:
    if hasattr(val, "default"):
        res = val.default
        return fallback if res is ... else res
    return val if val is not None else fallback


@router.get("/categories/tree")
def get_store_category_tree(db: Session = Depends(get_db)):
    """Lấy cây danh mục dược phẩm chuẩn hóa 6 nhóm cho MegaMenu Storefront."""
    return get_category_tree(db)


@router.get("/categories/{slug}/products")
def get_category_products(
    slug: str,
    prescriptionType: str = Query("all", pattern="^(all|otc|rx)$"),
    sort: str = "popular",
    brand: str | None = None,
    origin: str | None = None,
    dosageForm: str | None = None,
    priceRange: str | None = None,
    minPrice: int | None = None,
    maxPrice: int | None = None,
    page: int = Query(1, ge=1),
    pageSize: int | None = Query(None, ge=1, le=100),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    """Lấy danh sách sản phẩm theo slug danh mục (hỗ trợ cả nhóm cấp 1 và nhóm con)."""
    return get_store_products(
        category=slug,
        prescriptionType=prescriptionType,
        search=search,
        brand=brand,
        origin=origin,
        dosageForm=dosageForm,
        priceRange=priceRange,
        minPrice=minPrice,
        maxPrice=maxPrice,
        sort=sort,
        page=page,
        pageSize=pageSize,
        limit=limit,
        offset=offset,
        db=db,
    )


@router.get("/home/curated")
def get_curated_home_data(db: Session = Depends(get_db)):
    """Curated homepage sections with real database products, verified packshots,
    and verified pharmaceutical data. No 300-item client-side loading."""
    from app.models.inventory import BatchStatus, InventoryBatch, ProductSku, WarehouseBatchStock, ProductReview

    products = db.scalars(
        select(CanonicalProduct)
        .options(
            selectinload(CanonicalProduct.ingredients).selectinload(ProductIngredient.ingredient),
        )
        .where(
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
            ~CanonicalProduct.canonical_name.like("Hồ sơ%"),
        )
        .order_by(CanonicalProduct.id.asc())
    ).all()

    if not products:
        return {
            "bestsellers": [],
            "otc_medicines": [],
            "supplements": [],
            "medical_devices": [],
            "campaigns": [],
            "verified_brands": [],
            "health_articles": [],
            "total_active_products": 0,
        }

    prod_ids = [p.id for p in products]

    # Batch prices from ProductSku then PriceObservation
    sku_prices = db.query(
        ProductSku.canonical_product_id,
        ProductSku.base_price,
        ProductSku.is_default,
    ).filter(
        ProductSku.canonical_product_id.in_(prod_ids),
        ProductSku.is_active == True,
        ProductSku.base_price.isnot(None),
        ProductSku.base_price > 0,
    ).order_by(ProductSku.is_default.desc(), ProductSku.id.asc()).all()
    prices_map = {}
    for pid, b_price, _ in sku_prices:
        if pid not in prices_map and b_price:
            prices_map[pid] = int(b_price)

    obs_prices = db.query(
        PriceObservation.product_id,
        PriceObservation.observed_price,
    ).filter(
        PriceObservation.product_id.in_(prod_ids),
        PriceObservation.observed_price.isnot(None),
        PriceObservation.observed_price > 0,
    ).order_by(PriceObservation.observed_at.desc()).all()
    for pid, obs_p in obs_prices:
        if pid not in prices_map and obs_p:
            prices_map[pid] = int(obs_p)

    # Batch reviews
    rev_rows = db.query(
        ProductReview.canonical_product_id,
        func.avg(ProductReview.rating),
        func.count(ProductReview.id),
    ).filter(
        ProductReview.canonical_product_id.in_(prod_ids),
        ProductReview.is_approved == True,
    ).group_by(ProductReview.canonical_product_id).all()
    reviews_map = {pid: (round(float(avg_r), 1) if avg_r else 0.0, int(cnt) if cnt else 0) for pid, avg_r, cnt in rev_rows}

    # Batch stock
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
    stocks_map = {pid: int(s_qty) for pid, s_qty in stock_rows}

    all_serialized = [
        serialize_product(
            p,
            price=prices_map.get(p.id),
            rating=reviews_map.get(p.id, (0.0, 0))[0],
            review_count=reviews_map.get(p.id, (0.0, 0))[1],
            stock=stocks_map.get(p.id, 0),
        )
        for p in products
    ]

    # Bestsellers: products with verified local images or top active medicines
    bestseller_ids = {279185, 279284, 120085, 279255, 279189, 279336, 279338, 279341}
    bestsellers = [item for item in all_serialized if item["dbId"] in bestseller_ids or item.get("isBestseller")]
    if len(bestsellers) < 6:
        extras = [item for item in all_serialized if item["isSaleEligible"] and item not in bestsellers]
        bestsellers.extend(extras[: 8 - len(bestsellers)])

    # OTC Medicines
    otc_medicines = [
        item for item in all_serialized
        if item.get("category") == "thuoc-khong-ke-don" and not item.get("isPrescription")
    ][:8]

    # Supplements
    supplements = [
        item for item in all_serialized
        if item.get("category") == "thuc-pham-chuc-nang"
    ][:8]

    # Medical Devices
    medical_devices = [
        item for item in all_serialized
        if item.get("category") == "thiet-bi-y-te"
    ][:6]

    # Curated verified brands
    verified_brands = [
        {"name": "DHG Pharma", "country": "Việt Nam", "badge": "Dược Hậu Giang - Chuẩn GMP-WHO", "logoText": "DHG"},
        {"name": "Sanofi", "country": "Pháp", "badge": "Tập đoàn Dược phẩm Quốc tế", "logoText": "SANOFI"},
        {"name": "GSK", "country": "Anh Quốc", "badge": "GlaxoSmithKline Toàn cầu", "logoText": "GSK"},
        {"name": "Reckitt Benckiser", "country": "Anh Quốc", "badge": "Chăm sóc sức khỏe & Giảm đau", "logoText": "RECKITT"},
        {"name": "Traphaco", "country": "Việt Nam", "badge": "Đông dược & Tân dược Việt Nam", "logoText": "TRAPHACO"},
        {"name": "Rohto Mentholatum", "country": "Nhật Bản", "badge": "Chăm sóc mắt & Da liễu", "logoText": "ROHTO"},
        {"name": "Omron Healthcare", "country": "Nhật Bản", "badge": "Thiết bị y tế gia đình hàng đầu", "logoText": "OMRON"},
        {"name": "Ipsen", "country": "Pháp", "badge": "Dược phẩm tiêu hóa chuyên sâu", "logoText": "IPSEN"},
    ]

    # Curated Active Campaigns
    active_campaigns = [
        {
            "id": "camp-flu-season",
            "title": "Chiến Dịch Phòng Ngừa Cảm Cúm & Viêm Họng Mùa Mưa",
            "tag": "Chiến dịch y tế",
            "description": "Bảo vệ hệ hô hấp cho cả gia đình. Hỗ trợ tư vấn dược sĩ 24/7 và kiểm tra tương tác thuốc miễn phí.",
            "gradient": "from-blue-600 to-indigo-700",
            "cta": "Xem gói thuốc cảm cúm",
            "link": "/category/thuoc-khong-ke-don?subCategory=tri-ho-cam-cum",
        },
        {
            "id": "camp-gut-health",
            "title": "Bảo Vệ Hệ Tiêu Hóa & Men Vi Sinh Chuẩn Y Khoa",
            "tag": "Sức khỏe tiêu hóa",
            "description": "Men vi sinh dạng ống uống Enterogermina và gói Smecta chính hãng bảo quản điều kiện chuẩn GSP.",
            "gradient": "from-teal-600 to-emerald-700",
            "cta": "Khám phá danh mục tiêu hóa",
            "link": "/category/thuoc-khong-ke-don?subCategory=da-day-tieu-hoa",
        },
    ]

    # Curated Health Articles
    health_articles = [
        {
            "id": "art-paracetamol-safety",
            "title": "Sử dụng Paracetamol an toàn: Cảnh báo quá liều và cách tính liều chuẩn theo cân nặng",
            "category": "Dược lâm sàng",
            "readTime": "4 phút đọc",
            "author": "Dược sĩ CKI H4CARE",
            "date": "22/10/2026",
            "summary": "Paracetamol là thuốc giảm đau hạ sốt phổ biến nhất nhưng tiềm ẩn nguy cơ tổn thương gan cấp tính nếu dùng vượt quá 4g/ngày ở người lớn hoặc tính sai liều theo kg ở trẻ em.",
            "link": "/category/thuoc-khong-ke-don?subCategory=giam-dau-ha-sot",
        },
        {
            "id": "art-probiotics-vs-enzymes",
            "title": "Phân biệt Men vi sinh (Probiotics) và Men tiêu hóa (Enzymes): Tránh lạm dụng ở trẻ nhỏ",
            "category": "Tiêu hóa & Nhi khoa",
            "readTime": "5 phút đọc",
            "author": "Hội đồng Dược sĩ H4CARE",
            "date": "20/10/2026",
            "summary": "Nhiều phụ huynh nhầm lẫn giữa vi khuẩn có lợi đường ruột và enzym tiêu hóa thức ăn, dẫn đến việc dùng men tiêu hóa kéo dài làm teo tuyến tiết tự nhiên của cơ thể bé.",
            "link": "/category/thuoc-khong-ke-don?subCategory=da-day-tieu-hoa",
        },
        {
            "id": "art-rx-dispensing-standard",
            "title": "Quy trình tư vấn và cung ứng thuốc kê đơn (Rx) an toàn theo quy chuẩn Bộ Y Tế tại H4CARE",
            "category": "Quy chế & An toàn",
            "readTime": "3 phút đọc",
            "author": "Ban Giám sát Chất lượng GPP",
            "date": "18/10/2026",
            "summary": "H4CARE tuân thủ nghiêm ngặt Luật Dược 2016: Không bán thuốc kê đơn trực tuyến tùy tiện, mọi đơn thuốc phải được dược sĩ đại học xác thực trước khi điều phối từ kho chi nhánh.",
            "link": "/category/thuoc-ke-don",
        },
    ]

    return {
        "bestsellers": bestsellers[:8],
        "otc_medicines": otc_medicines,
        "supplements": supplements,
        "medical_devices": medical_devices,
        "campaigns": active_campaigns,
        "verified_brands": verified_brands,
        "health_articles": health_articles,
        "total_active_products": len(all_serialized),
    }


@router.get("/products")
def get_store_products(
    category: str | None = None,
    subCategory: str | None = None,
    product_type: str | None = None,
    prescription_status: str | None = None,
    tag: str | None = None,
    prescriptionType: str = Query("all", pattern="^(all|otc|rx)$"),
    search: str | None = Query(None, max_length=100),
    brand: str | None = None,
    origin: str | None = None,
    dosageForm: str | None = None,
    priceRange: str | None = None,
    minPrice: int | None = None,
    maxPrice: int | None = None,
    sort: str = "popular",
    page: int = Query(1, ge=1),
    pageSize: int | None = Query(None, ge=1, le=100),
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

    # Defensive unwrapping in case called internally without FastAPI dependency resolution
    rx_type = str(_unwrap_param(prescriptionType, "all"))
    raw_search = _unwrap_param(search, None)
    search_term = str(raw_search).strip() if (raw_search and str(raw_search).strip()) else None
    sort_mode = str(_unwrap_param(sort, "popular"))
    try:
        limit_num = int(_unwrap_param(limit, 150))
    except (TypeError, ValueError):
        limit_num = 150
    try:
        offset_num = int(_unwrap_param(offset, 0))
    except (TypeError, ValueError):
        offset_num = 0

    if rx_type == "rx":
        query = query.where(CanonicalProduct.rx_otc_status == RxOtcStatus.PRESCRIPTION)
    elif rx_type == "otc":
        query = query.where(CanonicalProduct.rx_otc_status == RxOtcStatus.OTC)

    fts_ids = None
    if search_term:
        from app.services.search_service import search_product_ids_fts
        fts_ids = search_product_ids_fts(db, search_term, limit=limit_num * 2)
        if fts_ids:
            query = query.where(CanonicalProduct.id.in_(fts_ids))
        else:
            term = f"%{search_term}%"
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
        from app.models.inventory import ProductSku
        sku_prices = db.query(
            ProductSku.canonical_product_id,
            ProductSku.base_price,
            ProductSku.is_default,
        ).filter(
            ProductSku.canonical_product_id.in_(prod_ids),
            ProductSku.is_active == True,
            ProductSku.base_price.isnot(None),
            ProductSku.base_price > 0,
        ).order_by(ProductSku.is_default.desc(), ProductSku.id.asc()).all()
        for pid, b_price, _ in sku_prices:
            if pid not in prices_map and b_price:
                prices_map[pid] = int(b_price)

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

    # Pre-resolve category matching slugs once before iteration (eliminates N+1 queries)
    matching_slugs: set[str] | None = None
    if category and isinstance(category, str):
        matching_slugs = {category}
        cat_obj = db.scalar(select(Category).where(Category.slug == category))
        if cat_obj and cat_obj.parent_id is None:
            ch_slugs = db.scalars(select(Category.slug).where(Category.parent_id == cat_obj.id)).all()
            matching_slugs.update(ch_slugs)

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
        
        # Category matching: support matching root category or subcategories
        if matching_slugs is not None:
            if item["category"] not in matching_slugs and item["subCategory"] not in matching_slugs:
                continue

        if subCategory and item["subCategory"] != subCategory:
            continue

        if product_type and item.get("productType") != product_type:
            continue

        if prescription_status and item.get("prescriptionStatus") != prescription_status:
            continue

        if tag:
            t = tag.lower().strip()
            if t in ["hot", "popular"]:
                if not (item.get("isBestSeller") or item.get("isFeatured")):
                    continue
            elif t == "bestseller" and not item.get("isBestSeller"):
                continue
            elif t == "featured" and not item.get("isFeatured"):
                continue

        serialized.append(item)

    # Collect available facets from the category/search matching products
    available_brands = set()
    available_origins = set()
    available_dosage_forms = set()
    for item in serialized:
        if item.get("brand"):
            available_brands.add(item["brand"])
        if item.get("origin"):
            available_origins.add(item["origin"])
        if item.get("dosageForm"):
            available_dosage_forms.add(item["dosageForm"])

    # Parse and apply facet filters (brand, origin, dosageForm, price)
    brand_tokens = [b.strip().lower() for b in str(_unwrap_param(brand, "")).split(",") if b.strip()]
    origin_tokens = [o.strip().lower() for o in str(_unwrap_param(origin, "")).split(",") if o.strip()]
    dosage_tokens = [d.strip().lower() for d in str(_unwrap_param(dosageForm, "")).split(",") if d.strip()]
    price_range_str = str(_unwrap_param(priceRange, "")).strip()
    min_p = _unwrap_param(minPrice, None)
    max_p = _unwrap_param(maxPrice, None)

    filtered_items = []
    for item in serialized:
        if brand_tokens:
            b_val = (item.get("brand") or "").lower()
            if not any(bt in b_val for bt in brand_tokens):
                continue
        if origin_tokens:
            o_val = (item.get("origin") or "").lower()
            if not any(ot in o_val for ot in origin_tokens):
                continue
        if dosage_tokens:
            d_val = (item.get("dosageForm") or "").lower()
            if not any(dt in d_val for dt in dosage_tokens):
                continue
        cur_p = item.get("price") or 0
        if min_p is not None and cur_p < min_p:
            continue
        if max_p is not None and cur_p > max_p:
            continue
        if price_range_str:
            if price_range_str == "under-100" and cur_p >= 100000:
                continue
            elif price_range_str == "100-300" and (cur_p < 100000 or cur_p > 300000):
                continue
            elif price_range_str == "300-500" and (cur_p < 300000 or cur_p > 500000):
                continue
            elif price_range_str == "above-500" and cur_p <= 500000:
                continue

        filtered_items.append(item)

    # Sort
    if search_term and fts_ids and sort_mode == "popular":
        rank_dict = {pid: idx for idx, pid in enumerate(fts_ids)}
        filtered_items.sort(key=lambda x: rank_dict.get(x["dbId"], 9999))
    elif sort_mode == "newest":
        filtered_items.sort(key=lambda x: x["dbId"], reverse=True)
    elif sort_mode == "price-asc":
        filtered_items.sort(key=lambda x: x["price"])
    elif sort_mode == "price-desc":
        filtered_items.sort(key=lambda x: x["price"], reverse=True)
    elif sort_mode == "rating":
        filtered_items.sort(key=lambda x: x["rating"], reverse=True)
    else:  # popular / default
        filtered_items.sort(key=lambda x: (not x["isBestSeller"], not x["isFeatured"], x["dbId"]))

    total = len(filtered_items)

    # Calculate pagination params (page & pageSize take precedence over offset & limit)
    raw_page_size = _unwrap_param(pageSize, None)
    raw_page = _unwrap_param(page, 1)
    if raw_page_size is not None:
        try:
            page_size_num = max(1, min(100, int(raw_page_size)))
        except (TypeError, ValueError):
            page_size_num = 12
        try:
            page_num = max(1, int(raw_page))
        except (TypeError, ValueError):
            page_num = 1
        limit_num = page_size_num
        offset_num = (page_num - 1) * page_size_num
        current_page = page_num
    else:
        current_page = (offset_num // limit_num) + 1 if limit_num else 1

    total_pages = math.ceil(total / limit_num) if limit_num else 1
    paged_items = filtered_items[offset_num : offset_num + limit_num]

    return {
        "items": paged_items,
        "total": total,
        "page": current_page,
        "pageSize": limit_num,
        "totalPages": total_pages,
        "limit": limit_num,
        "offset": offset_num,
        "availableBrands": sorted(list(available_brands)),
        "availableOrigins": sorted(list(available_origins)),
        "availableDosageForms": sorted(list(available_dosage_forms)),
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

    # Extract official retail price strictly from active SKU
    price_val = None
    if eligibility_res.selected_sku and eligibility_res.selected_sku.get("base_price", 0) > 0:
        price_val = int(eligibility_res.selected_sku["base_price"])

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


class PrescriptionConsultPayload(BaseModel):
    product_id: int
    patient_name: str
    phone_number: str
    prescription_file_name: str | None = None
    storage_key: str | None = None
    notes: str | None = None


@router.post("/prescriptions/consult")
def submit_prescription_consultation(
    payload: PrescriptionConsultPayload,
    db: Session = Depends(get_db),
):
    product = db.get(CanonicalProduct, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm yêu cầu tư vấn không tồn tại")

    # Validate Vietnamese phone number format
    phone = payload.phone_number.strip().replace(" ", "")
    if not re.match(r"^(0|\+84)(3|5|7|8|9)[0-9]{8}$", phone):
        raise HTTPException(status_code=400, detail="Số điện thoại không đúng định dạng Việt Nam")

    patient_name = payload.patient_name.strip()
    if len(patient_name) < 2:
        raise HTTPException(status_code=400, detail="Vui lòng nhập họ và tên người bệnh hợp lệ")

    # Save real consult alert for pharmacists
    from app.models.entities import AdminAlert
    alert_message = (
        f"Yêu cầu tư vấn thuốc kê đơn: '{product.canonical_name}' (ID: {product.id}). "
        f"Bệnh nhân: {patient_name}, SĐT: {phone}. "
        f"Tệp đơn thuốc: {payload.prescription_file_name or payload.storage_key or 'Không đính kèm'}. "
        f"Ghi chú: {payload.notes or 'Không có ghi chú thêm.'}"
    )
    alert = AdminAlert(
        source_code="RX_CONSULTATION",
        alert_type="PRESCRIPTION_CONSULT_REQUEST",
        severity="INFO",
        message=alert_message,
        is_read=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    return {
        "success": True,
        "message": "Yêu cầu tư vấn đơn thuốc đã được tiếp nhận thành công",
        "requestId": alert.id,
        "productName": product.canonical_name,
        "patientName": patient_name,
        "phoneNumber": phone,
        "consultSla": "Dược sĩ chuyên môn H4CARE sẽ liên hệ tư vấn trong giờ làm việc (8h00 - 21h30 hàng ngày)",
    }
