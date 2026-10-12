from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import CanonicalProduct
from app.services.classification_pipeline import ProductClassificationPipeline, ClassificationProposal


@dataclass
class CategoryClassificationResult:
    category_slug: str | None
    category_name: str | None
    subcategory_slug: str | None
    subcategory_name: str | None
    confidence: float
    reasoning: str
    model_version: str = "pharmatrust-cat-v2.0"
    requires_review: bool = False
    product_type: str | None = None
    prescription_status: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


# Danh mục tiêu chuẩn 6 nhóm đầy đủ bao gồm Mẹ & Bé
VALID_CATEGORIES = {
    "thuoc-khong-ke-don": {
        "name": "Thuốc Không Kê Đơn",
        "subcategories": {
            "giam-dau-ha-sot": "Giảm đau & Hạ sốt",
            "tri-ho-cam-cum": "Trị ho, Cảm cúm & Viêm họng",
            "da-day-tieu-hoa": "Dạ dày & Tiêu hóa",
            "nho-mat-mui-tai": "Thuốc nhỏ mắt & Mũi tai",
            "say-xe-di-ung": "Chống say xe & Dị ứng",
            "khang-viem": "Kháng viêm & Phù nề",
            "da-lieu-ngoai": "Da liễu dùng ngoài",
            "sat-khuan-vet-thuong": "Sát khuẩn & Vết thương",
            "cham-soc-rang-mieng": "Chăm sóc răng miệng",
            "otc-khac": "Nhóm OTC khác",
        },
    },
    "thuoc-ke-don": {
        "name": "Thuốc Kê Đơn (Rx)",
        "subcategories": {
            "khang-sinh": "Kháng sinh & Kháng nấm",
            "tim-mach-huyet-ap": "Thuốc Tim mạch & Huyết áp",
            "tieu-duong": "Thuốc Trị Tiểu đường",
            "co-xuong-khop": "Cơ - Xương - Khớp",
            "than-kinh-giac-ngu": "Thần kinh & Giấc ngủ",
            "ho-hap-chuyen-sau": "Hô hấp chuyên sâu",
            "tieu-hoa-ke-don": "Tiêu hóa chuyên khoa",
            "da-lieu-ke-don": "Da liễu chuyên sâu",
            "ke-don-khac": "Nhóm kê đơn khác",
        },
    },
    "thuc-pham-chuc-nang": {
        "name": "Vitamin & Thực Phẩm Chức Năng",
        "subcategories": {
            "vitamin-khoang-chat": "Vitamin & Khoáng chất tổng hợp",
            "tang-mien-dich": "Tăng cường Miễn dịch",
            "bo-nao": "Bổ Não & Tăng trí nhớ",
            "bo-khop": "Glucosamine & Khớp xương",
            "omega-3": "Omega 3 & Sức khỏe Tim",
            "giai-doc-gan": "Thanh nhiệt & Giải độc gan",
            "ho-tro-tieu-hoa": "Hỗ trợ Tiêu hóa & Men vi sinh",
            "ho-tro-tim-mach": "Hỗ trợ Tim mạch",
            "ho-tro-giac-ngu": "Hỗ trợ Giấc ngủ ngon",
            "nguoi-cao-tuoi": "Dinh dưỡng Người cao tuổi",
            "tre-em": "Vi chất cho Trẻ em",
            "ho-tro-khac": "Hỗ trợ sức khỏe khác",
        },
    },
    "duoc-my-pham": {
        "name": "Dược Mỹ Phẩm & Chăm Sóc Da",
        "subcategories": {
            "kem-chong-nang": "Kem chống nắng Y khoa",
            "sua-rua-mat": "Sữa rửa mặt dịu nhẹ",
            "tri-mun-phuc-hoi": "Trị mụn & Phục hồi da",
            "duong-am": "Kem dưỡng ẩm chuyên sâu",
            "serum-dac-tri": "Serum đặc trị thâm nám",
            "da-nhay-cam": "Chăm sóc da nhạy cảm",
            "cham-soc-toc": "Chăm sóc tóc & Da đầu",
            "cham-soc-co-the": "Chăm sóc cơ thể",
            "my-pham-khac": "Mỹ phẩm khác",
        },
    },
    "thiet-bi-y-te": {
        "name": "Thiết Bị & Dụng Cụ Y Tế",
        "subcategories": {
            "may-do-huyet-ap": "Máy đo Huyết áp điện tử",
            "may-do-duong-huyet": "Máy & Que đo Đường huyết",
            "nhiet-ke-spo2": "Nhiệt kế hồng ngoại & SpO2",
            "may-xong-khi-dung": "Máy xông khí dung mũi họng",
            "bang-gac-sat-trung": "Băng gạc & Sơ cứu vết thương",
            "khau-trang": "Khẩu trang y tế & Kháng khuẩn",
            "dung-cu-cham-soc": "Dụng cụ chăm sóc tại nhà",
            "thiet-bi-khac": "Thiết bị y tế khác",
        },
    },
    "me-va-be": {
        "name": "Mẹ & Bé",
        "subcategories": {
            "vitamin-me-bau": "Vitamin & Sắt cho Mẹ bầu",
            "men-vi-sinh-be": "Men vi sinh & Tiêu hóa trẻ em",
            "de-khang-be": "Tăng đề kháng & Trị ho cho bé",
            "tam-goi-be": "Tắm gội & Dưỡng ẩm dịu nhẹ",
            "cham-soc-thai-ky": "Chăm sóc thai kỳ & Rạn da",
            "cham-soc-sau-sinh": "Chăm sóc Mẹ sau sinh",
            "dinh-duong-be": "Dinh dưỡng & Sữa cho bé",
            "ve-sinh-be": "Vệ sinh & Tã bỉm cho bé",
            "dung-cu-me-be": "Dụng cụ chăm sóc Mẹ & Bé",
            "me-be-khac": "Sản phẩm mẹ và bé khác",
        },
    },
}


class AICategoryClassifier:
    """
    Bộ phân loại sản phẩm y tế tuân thủ quy trình chuẩn hóa:
    - Sử dụng ProductClassificationPipeline
    - Không suy diễn kê đơn chỉ từ tên hoạt chất
    - Đưa vào hàng chờ duyệt nếu thiếu căn cứ chính thức
    """

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold if threshold is not None else settings.category_ai_threshold

    def classify(
        self,
        name: str,
        ingredients: list[dict[str, Any]] | None = None,
        dosage_form: str | None = None,
        indications: str | None = None,
        source_category: str | None = None,
        is_rx: bool | None = None,
        registration_number: str | None = None,
        manufacturer: str | None = None,
    ) -> CategoryClassificationResult:
        db = SessionLocal()
        try:
            pipeline = ProductClassificationPipeline(db)
            # Tạo dummy CanonicalProduct để chạy qua pipeline
            dummy_prod = CanonicalProduct(
                id=0,
                canonical_name=name,
                registration_number=registration_number,
                dosage_form=dosage_form,
                manufacturer=manufacturer,
                indications=indications,
            )
            proposal = pipeline.classify_product(dummy_prod)

            primary_cat = None
            sub_cat = None
            for c in proposal.suggested_categories:
                if c.get("is_primary") and not primary_cat:
                    primary_cat = c
                elif not sub_cat:
                    sub_cat = c

            cat_slug = primary_cat["slug"] if primary_cat else None
            sub_slug = sub_cat["slug"] if sub_cat else None

            cat_info = VALID_CATEGORIES.get(cat_slug, {}) if cat_slug else {}
            cat_name = cat_info.get("name")
            sub_name = cat_info.get("subcategories", {}).get(sub_slug) if sub_slug else None

            return CategoryClassificationResult(
                category_slug=cat_slug,
                category_name=cat_name,
                subcategory_slug=sub_slug,
                subcategory_name=sub_name,
                confidence=round(proposal.confidence, 2),
                reasoning="; ".join(proposal.reasoning),
                requires_review=proposal.requires_review,
                product_type=proposal.suggested_product_type,
                prescription_status=proposal.suggested_prescription_status,
                missing_fields=proposal.missing_fields,
                conflicts=proposal.conflicts,
            )
        finally:
            db.close()


classifier = AICategoryClassifier()
