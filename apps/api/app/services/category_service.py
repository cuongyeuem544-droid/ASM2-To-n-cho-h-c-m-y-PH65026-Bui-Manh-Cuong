from __future__ import annotations

import logging
from typing import Any
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.classification import Category, ProductCategory, ProductType
from app.models.entities import CanonicalProduct
from app.models.enums import LegalProductType, PrescriptionStatus

logger = logging.getLogger(__name__)

# Cache in-memory cho cây danh mục
_CATEGORY_TREE_CACHE: list[dict[str, Any]] | None = None


STANDARD_PRODUCT_TYPES = [
    {"code": LegalProductType.MEDICINE.value, "name": "Thuốc", "description": "Dược phẩm điều trị hoặc phòng bệnh có số đăng ký thuốc"},
    {"code": LegalProductType.SUPPLEMENT.value, "name": "Thực phẩm bảo vệ sức khỏe", "description": "Thực phẩm bổ sung vi chất, vitamin, khoáng chất"},
    {"code": LegalProductType.MEDICAL_DEVICE.value, "name": "Trang thiết bị y tế", "description": "Máy móc, dụng cụ, vật tư y tế gia đình và phòng khám"},
    {"code": LegalProductType.COSMETIC.value, "name": "Dược mỹ phẩm & Mỹ phẩm", "description": "Sản phẩm chăm sóc da, tóc, phục hồi chuẩn da liễu"},
    {"code": LegalProductType.MOTHER_BABY.value, "name": "Mẹ & Bé", "description": "Sản phẩm chuyên biệt cho phụ nữ mang thai, sau sinh và trẻ sơ sinh/trẻ nhỏ"},
    {"code": LegalProductType.PERSONAL_CARE.value, "name": "Chăm sóc cá nhân", "description": "Khăn ướt, bông tẩy trang, vệ sinh thân thể"},
    {"code": LegalProductType.OTHER.value, "name": "Khác", "description": "Chưa xác định nhóm phân loại pháp lý"},
]


STANDARD_STOREFRONT_CATEGORIES = [
    # 1. Thuốc Không Kê Đơn
    {
        "code": "CAT_OTC",
        "slug": "thuoc-khong-ke-don",
        "name": "Thuốc Không Kê Đơn",
        "category_kind": "STOREFRONT",
        "allowed_product_type": "MEDICINE",
        "icon_name": "Pill",
        "badge": "Phổ biến",
        "description": "Giảm đau, hạ sốt, cảm cúm, tiêu hóa, dị ứng thông thường",
        "featured_title": "Tủ thuốc gia đình chuẩn GPP",
        "featured_subtitle": "Đầy đủ các loại thuốc cơ bản, hạn sử dụng mới nhất",
        "featured_image": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600&auto=format&fit=crop&q=80",
        "sort_order": 1,
        "children": [
            {"code": "SUB_OTC_PAIN", "slug": "giam-dau-ha-sot", "name": "Giảm đau & Hạ sốt", "sort_order": 1, "badge": "Hot"},
            {"code": "SUB_OTC_FLU", "slug": "tri-ho-cam-cum", "name": "Trị ho, Cảm cúm & Viêm họng", "sort_order": 2, "badge": "Hot"},
            {"code": "SUB_OTC_GI", "slug": "da-day-tieu-hoa", "name": "Dạ dày & Tiêu hóa", "sort_order": 3, "badge": "Hot"},
            {"code": "SUB_OTC_EYE_EAR", "slug": "nho-mat-mui-tai", "name": "Thuốc nhỏ mắt & Mũi tai", "sort_order": 4},
            {"code": "SUB_OTC_ALLERGY", "slug": "say-xe-di-ung", "name": "Chống say xe & Dị ứng", "sort_order": 5},
            {"code": "SUB_OTC_ANTI_INFLAM", "slug": "khang-viem", "name": "Kháng viêm & Phù nề", "sort_order": 6},
            {"code": "SUB_OTC_SKIN", "slug": "da-lieu-ngoai", "name": "Da liễu dùng ngoài", "sort_order": 7},
            {"code": "SUB_OTC_ANTISEPTIC", "slug": "sat-khuan-vet-thuong", "name": "Sát khuẩn & Vết thương", "sort_order": 8},
            {"code": "SUB_OTC_ORAL", "slug": "cham-soc-rang-mieng", "name": "Chăm sóc răng miệng", "sort_order": 9},
            {"code": "SUB_OTC_OTHER", "slug": "otc-khac", "name": "Nhóm OTC khác", "sort_order": 10},
        ],
    },
    # 2. Thuốc Kê Đơn (Rx)
    {
        "code": "CAT_RX",
        "slug": "thuoc-ke-don",
        "name": "Thuốc Kê Đơn (Rx)",
        "category_kind": "STOREFRONT",
        "allowed_product_type": "MEDICINE",
        "icon_name": "FileCheck",
        "badge": "Cần đơn BS",
        "description": "Tư vấn và cấp phát thuốc theo toa chỉ định của Bác sĩ",
        "featured_title": "Hỗ trợ gửi đơn thuốc online",
        "featured_subtitle": "Dược sĩ chuyên môn kiểm tra toa và tư vấn liều dùng an toàn",
        "featured_image": "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=600&auto=format&fit=crop&q=80",
        "sort_order": 2,
        "children": [
            {"code": "SUB_RX_ANTIBIOTIC", "slug": "khang-sinh", "name": "Kháng sinh & Kháng nấm", "sort_order": 1, "badge": "Hot"},
            {"code": "SUB_RX_CARDIO", "slug": "tim-mach-huyet-ap", "name": "Thuốc Tim mạch & Huyết áp", "sort_order": 2, "badge": "Hot"},
            {"code": "SUB_RX_DIABETES", "slug": "tieu-duong", "name": "Thuốc Trị Tiểu đường", "sort_order": 3, "badge": "Hot"},
            {"code": "SUB_RX_JOINT", "slug": "co-xuong-khop", "name": "Cơ - Xương - Khớp", "sort_order": 4},
            {"code": "SUB_RX_NEURO", "slug": "than-kinh-giac-ngu", "name": "Thần kinh & Giấc ngủ", "sort_order": 5},
            {"code": "SUB_RX_RESPIRATORY", "slug": "ho-hap-chuyen-sau", "name": "Hô hấp chuyên sâu", "sort_order": 6},
            {"code": "SUB_RX_GI", "slug": "tieu-hoa-ke-don", "name": "Tiêu hóa chuyên khoa", "sort_order": 7},
            {"code": "SUB_RX_DERMA", "slug": "da-lieu-ke-don", "name": "Da liễu chuyên sâu", "sort_order": 8},
            {"code": "SUB_RX_OTHER", "slug": "ke-don-khac", "name": "Nhóm kê đơn khác", "sort_order": 9},
        ],
    },
    # 3. Vitamin & Thực Phẩm Chức Năng
    {
        "code": "CAT_SUPPLEMENT",
        "slug": "thuc-pham-chuc-nang",
        "name": "Vitamin & Thực Phẩm Chức Năng",
        "category_kind": "STOREFRONT",
        "allowed_product_type": "SUPPLEMENT",
        "icon_name": "Sparkles",
        "badge": "Hot Deal",
        "description": "Tăng đề kháng, bổ não, tim mạch, làm đẹp, xương khớp",
        "featured_title": "Dưỡng chất nhập khẩu 100%",
        "featured_subtitle": "Từ các thương hiệu uy tín: Blackmores, DHC, Kirkland",
        "featured_image": "https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=600&auto=format&fit=crop&q=80",
        "sort_order": 3,
        "children": [
            {"code": "SUB_SUPP_VITAMIN", "slug": "vitamin-khoang-chat", "name": "Vitamin & Khoáng chất tổng hợp", "sort_order": 1, "badge": "Hot"},
            {"code": "SUB_SUPP_IMMUNE", "slug": "tang-mien-dich", "name": "Tăng cường Miễn dịch", "sort_order": 2, "badge": "Hot"},
            {"code": "SUB_SUPP_BRAIN", "slug": "bo-nao", "name": "Bổ Não & Tăng trí nhớ", "sort_order": 3, "badge": "Hot"},
            {"code": "SUB_SUPP_JOINT", "slug": "bo-khop", "name": "Glucosamine & Khớp xương", "sort_order": 4},
            {"code": "SUB_SUPP_OMEGA", "slug": "omega-3", "name": "Omega 3 & Sức khỏe Tim", "sort_order": 5},
            {"code": "SUB_SUPP_LIVER", "slug": "giai-doc-gan", "name": "Thanh nhiệt & Giải độc gan", "sort_order": 6},
            {"code": "SUB_SUPP_GI", "slug": "ho-tro-tieu-hoa", "name": "Hỗ trợ Tiêu hóa & Men vi sinh", "sort_order": 7},
            {"code": "SUB_SUPP_CARDIO", "slug": "ho-tro-tim-mach", "name": "Hỗ trợ Tim mạch", "sort_order": 8},
            {"code": "SUB_SUPP_SLEEP", "slug": "ho-tro-giac-ngu", "name": "Hỗ trợ Giấc ngủ ngon", "sort_order": 9},
            {"code": "SUB_SUPP_ELDERLY", "slug": "nguoi-cao-tuoi", "name": "Dinh dưỡng Người cao tuổi", "sort_order": 10},
            {"code": "SUB_SUPP_CHILD", "slug": "tre-em", "name": "Vi chất cho Trẻ em", "sort_order": 11},
            {"code": "SUB_SUPP_OTHER", "slug": "ho-tro-khac", "name": "Hỗ trợ sức khỏe khác", "sort_order": 12},
        ],
    },
    # 4. Dược Mỹ Phẩm & Chăm Sóc Da
    {
        "code": "CAT_COSMETIC",
        "slug": "duoc-my-pham",
        "name": "Dược Mỹ Phẩm & Chăm Sóc Da",
        "category_kind": "STOREFRONT",
        "allowed_product_type": "COSMETIC",
        "icon_name": "ShieldAlert",
        "description": "Sản phẩm da liễu lành tính, phục hồi và bảo vệ da",
        "featured_title": "Chăm sóc làn da chuẩn Y khoa",
        "featured_subtitle": "An toàn cho cả làn da nhạy cảm nhất",
        "featured_image": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=600&auto=format&fit=crop&q=80",
        "sort_order": 4,
        "children": [
            {"code": "SUB_COSM_SUNSCREEN", "slug": "kem-chong-nang", "name": "Kem chống nắng Y khoa", "sort_order": 1, "badge": "Hot"},
            {"code": "SUB_COSM_CLEANSER", "slug": "sua-rua-mat", "name": "Sữa rửa mặt dịu nhẹ", "sort_order": 2, "badge": "Hot"},
            {"code": "SUB_COSM_ACNE", "slug": "tri-mun-phuc-hoi", "name": "Trị mụn & Phục hồi da", "sort_order": 3, "badge": "Hot"},
            {"code": "SUB_COSM_MOISTURE", "slug": "duong-am", "name": "Kem dưỡng ẩm chuyên sâu", "sort_order": 4},
            {"code": "SUB_COSM_SERUM", "slug": "serum-dac-tri", "name": "Serum đặc trị thâm nám", "sort_order": 5},
            {"code": "SUB_COSM_SENSITIVE", "slug": "da-nhay-cam", "name": "Chăm sóc da nhạy cảm", "sort_order": 6},
            {"code": "SUB_COSM_HAIR", "slug": "cham-soc-toc", "name": "Chăm sóc tóc & Da đầu", "sort_order": 7},
            {"code": "SUB_COSM_BODY", "slug": "cham-soc-co-the", "name": "Chăm sóc cơ thể", "sort_order": 8},
            {"code": "SUB_COSM_OTHER", "slug": "my-pham-khac", "name": "Mỹ phẩm khác", "sort_order": 9},
        ],
    },
    # 5. Thiết Bị & Dụng Cụ Y Tế
    {
        "code": "CAT_DEVICE",
        "slug": "thiet-bi-y-te",
        "name": "Thiết Bị & Dụng Cụ Y Tế",
        "category_kind": "STOREFRONT",
        "allowed_product_type": "MEDICAL_DEVICE",
        "icon_name": "Activity",
        "description": "Máy đo huyết áp, máy đo đường huyết, nhiệt kế điện tử",
        "featured_title": "Thiết bị y tế chính hãng Omron, Microlife",
        "featured_subtitle": "Bảo hành chính hãng 2 - 5 năm tận nhà",
        "featured_image": "https://images.unsplash.com/photo-1584017911766-d451b3d0e843?w=600&auto=format&fit=crop&q=80",
        "sort_order": 5,
        "children": [
            {"code": "SUB_DEV_BP", "slug": "may-do-huyet-ap", "name": "Máy đo Huyết áp điện tử", "sort_order": 1, "badge": "Hot"},
            {"code": "SUB_DEV_GLUCOSE", "slug": "may-do-duong-huyet", "name": "Máy & Que đo Đường huyết", "sort_order": 2, "badge": "Hot"},
            {"code": "SUB_DEV_THERMOMETER", "slug": "nhiet-ke-spo2", "name": "Nhiệt kế hồng ngoại & SpO2", "sort_order": 3},
            {"code": "SUB_DEV_NEBULIZER", "slug": "may-xong-khi-dung", "name": "Máy xông khí dung mũi họng", "sort_order": 4},
            {"code": "SUB_DEV_BANDAGE", "slug": "bang-gac-sat-trung", "name": "Băng gạc & Sơ cứu vết thương", "sort_order": 5},
            {"code": "SUB_DEV_MASK", "slug": "khau-trang", "name": "Khẩu trang y tế & Kháng khuẩn", "sort_order": 6},
            {"code": "SUB_DEV_HOMECARE", "slug": "dung-cu-cham-soc", "name": "Dụng cụ chăm sóc tại nhà", "sort_order": 7},
            {"code": "SUB_DEV_OTHER", "slug": "thiet-bi-khac", "name": "Thiết bị y tế khác", "sort_order": 8},
        ],
    },
    # 6. Mẹ & Bé
    {
        "code": "CAT_MOTHER_BABY",
        "slug": "me-va-be",
        "name": "Mẹ & Bé",
        "category_kind": "STOREFRONT",
        "allowed_product_type": None,  # Đa loại: có thể gán cho SUPPLEMENT, COSMETIC, MOTHER_BABY
        "icon_name": "HeartPulse",
        "description": "Sữa dinh dưỡng, vitamin bầu, đồ dùng y tế an toàn cho bé",
        "featured_title": "Dinh dưỡng & Chăm sóc bé yêu",
        "featured_subtitle": "Chuẩn an toàn dược khoa cho sơ sinh",
        "featured_image": "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=600&auto=format&fit=crop&q=80",
        "sort_order": 6,
        "children": [
            {"code": "SUB_MB_MOM_VITAMIN", "slug": "vitamin-me-bau", "name": "Vitamin & Sắt cho Mẹ bầu", "sort_order": 1, "badge": "Hot"},
            {"code": "SUB_MB_BABY_PROBIOTIC", "slug": "men-vi-sinh-be", "name": "Men vi sinh & Tiêu hóa trẻ em", "sort_order": 2, "badge": "Hot"},
            {"code": "SUB_MB_BABY_IMMUNE", "slug": "de-khang-be", "name": "Tăng đề kháng & Trị ho cho bé", "sort_order": 3},
            {"code": "SUB_MB_BABY_BATH", "slug": "tam-goi-be", "name": "Tắm gội & Dưỡng ẩm dịu nhẹ", "sort_order": 4},
            {"code": "SUB_MB_PREGNANCY", "slug": "cham-soc-thai-ky", "name": "Chăm sóc thai kỳ & Rạn da", "sort_order": 5},
            {"code": "SUB_MB_POSTPARTUM", "slug": "cham-soc-sau-sinh", "name": "Chăm sóc Mẹ sau sinh", "sort_order": 6},
            {"code": "SUB_MB_NUTRITION", "slug": "dinh-duong-be", "name": "Dinh dưỡng & Sữa cho bé", "sort_order": 7},
            {"code": "SUB_MB_HYGIENE", "slug": "ve-sinh-be", "name": "Vệ sinh & Tã bỉm cho bé", "sort_order": 8},
            {"code": "SUB_MB_GEAR", "slug": "dung-cu-me-be", "name": "Dụng cụ chăm sóc Mẹ & Bé", "sort_order": 9},
            {"code": "SUB_MB_OTHER", "slug": "me-be-khac", "name": "Sản phẩm mẹ và bé khác", "sort_order": 10},
        ],
    },
]


def invalidate_category_cache() -> None:
    global _CATEGORY_TREE_CACHE
    _CATEGORY_TREE_CACHE = None


def seed_standard_categories(db: Session) -> dict[str, int]:
    """Khởi tạo đầy đủ nhóm loại sản phẩm pháp lý và cây danh mục chuẩn."""
    # 1. Seed ProductTypes
    types_count = 0
    for pt in STANDARD_PRODUCT_TYPES:
        existing = db.scalar(select(ProductType).where(ProductType.code == pt["code"]))
        if not existing:
            new_pt = ProductType(
                code=pt["code"],
                name=pt["name"],
                description=pt["description"],
                is_active=True,
            )
            db.add(new_pt)
            types_count += 1
    db.flush()

    # 2. Seed Storefront Categories
    cats_count = 0
    subcats_count = 0
    for root in STANDARD_STOREFRONT_CATEGORIES:
        parent = db.scalar(select(Category).where(Category.code == root["code"]))
        if not parent:
            parent = Category(
                parent_id=None,
                code=root["code"],
                slug=root["slug"],
                name=root["name"],
                category_kind=root.get("category_kind", "STOREFRONT"),
                allowed_product_type=root.get("allowed_product_type"),
                description=root.get("description"),
                icon_name=root.get("icon_name"),
                badge=root.get("badge"),
                featured_image=root.get("featured_image"),
                featured_title=root.get("featured_title"),
                featured_subtitle=root.get("featured_subtitle"),
                sort_order=root.get("sort_order", 0),
                is_active=True,
            )
            db.add(parent)
            db.flush()
            cats_count += 1
        else:
            # Đồng bộ thông tin nếu cần
            parent.slug = root["slug"]
            parent.name = root["name"]
            parent.icon_name = root.get("icon_name", parent.icon_name)
            parent.badge = root.get("badge", parent.badge)
            parent.description = root.get("description", parent.description)

        for sub in root.get("children", []):
            existing_sub = db.scalar(select(Category).where(Category.code == sub["code"]))
            if not existing_sub:
                existing_sub = Category(
                    parent_id=parent.id,
                    code=sub["code"],
                    slug=sub["slug"],
                    name=sub["name"],
                    category_kind=root.get("category_kind", "STOREFRONT"),
                    allowed_product_type=root.get("allowed_product_type"),
                    badge=sub.get("badge"),
                    sort_order=sub.get("sort_order", 0),
                    is_active=True,
                )
                db.add(existing_sub)
                subcats_count += 1
            else:
                existing_sub.parent_id = parent.id
                existing_sub.slug = sub["slug"]
                existing_sub.name = sub["name"]

    db.commit()
    invalidate_category_cache()
    return {"product_types": types_count, "categories": cats_count, "subcategories": subcats_count}


seed_standard_categories_and_types = seed_standard_categories


def get_category_tree(db: Session, force_refresh: bool = False, include_empty: bool = True) -> list[dict[str, Any]]:
    """Lấy cây danh mục cấp 1 & cấp 2 có kèm số lượng sản phẩm."""
    global _CATEGORY_TREE_CACHE
    if _CATEGORY_TREE_CACHE is not None and not force_refresh:
        return _CATEGORY_TREE_CACHE

    roots = db.scalars(
        select(Category)
        .where(Category.parent_id.is_(None), Category.is_active.is_(True))
        .order_by(Category.sort_order.asc(), Category.id.asc())
    ).all()

    # Tính product count cho từng category
    prod_count_query = db.execute(
        select(ProductCategory.category_id, func.count(ProductCategory.product_id))
        .join(CanonicalProduct, CanonicalProduct.id == ProductCategory.product_id)
        .where(CanonicalProduct.publish_status == "PUBLISHED")
        .group_by(ProductCategory.category_id)
    ).fetchall()
    count_map = {cat_id: cnt for cat_id, cnt in prod_count_query}

    tree = []
    for root in roots:
        children = db.scalars(
            select(Category)
            .where(Category.parent_id == root.id, Category.is_active.is_(True))
            .order_by(Category.sort_order.asc(), Category.id.asc())
        ).all()

        child_list = []
        total_root_products = count_map.get(root.id, 0)
        for child in children:
            c_cnt = count_map.get(child.id, 0)
            total_root_products += c_cnt
            child_list.append({
                "id": f"sub-{child.id}",
                "dbId": child.id,
                "code": child.code,
                "name": child.name,
                "slug": child.slug,
                "isPopular": bool(child.badge == "Hot"),
                "badge": child.badge,
                "sortOrder": child.sort_order,
                "productCount": c_cnt,
            })

        tree.append({
            "id": f"cat-{root.id}",
            "dbId": root.id,
            "code": root.code,
            "name": root.name,
            "slug": root.slug,
            "categoryKind": root.category_kind,
            "allowedProductType": root.allowed_product_type,
            "iconName": root.icon_name or "Pill",
            "badge": root.badge,
            "description": root.description or "",
            "featuredTitle": root.featured_title or "Tủ thuốc gia đình chuẩn GPP",
            "featuredSubtitle": root.featured_subtitle or "Nguồn gốc xuất xứ rõ ràng",
            "featuredImage": root.featured_image or "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600&auto=format&fit=crop&q=80",
            "sortOrder": root.sort_order,
            "productCount": total_root_products,
            "subCategories": child_list,
        })

    _CATEGORY_TREE_CACHE = tree
    return tree


def validate_category_compatibility(product_type: str, category: Category) -> tuple[bool, str | None]:
    """Kiểm tra tính tương thích giữa loại sản phẩm pháp lý và danh mục."""
    if not category.allowed_product_type:
        return True, None

    if category.allowed_product_type != product_type:
        return False, f"Danh mục '{category.name}' chỉ cho phép loại sản phẩm '{category.allowed_product_type}', không thể gán cho '{product_type}'."

    return True, None
