from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.classification import (
    Category,
    ProductCategory,
    ProductClassificationEvidence,
    ProductClassificationReview,
    ProductClassificationHistory,
    ProductType,
)
from app.models.entities import CanonicalProduct, RegulatoryRecord, utcnow
from app.models.enums import LegalProductType, PrescriptionStatus, AssignmentMethod, ClassificationReviewStatus


@dataclass
class ClassificationProposal:
    suggested_product_type: str | None = None
    suggested_prescription_status: str | None = None
    suggested_categories: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    requires_review: bool = True
    evidence_source: str = "OFFICIAL_REGULATORY_PIPELINE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggested_product_type": self.suggested_product_type,
            "suggested_prescription_status": self.suggested_prescription_status,
            "suggested_categories": self.suggested_categories,
            "confidence": round(self.confidence, 2),
            "reasoning": self.reasoning,
            "missing_fields": self.missing_fields,
            "conflicts": self.conflicts,
            "requires_review": self.requires_review,
        }


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def normalize_reg_number(reg: str | None) -> str | None:
    if not reg:
        return None
    cleaned = reg.strip().upper().replace(" ", "").replace("_", "-")
    return cleaned if len(cleaned) >= 4 else None


# Nhận diện tiền tố số đăng ký thuốc Việt Nam theo Cục Quản lý Dược
MEDICINE_REG_PATTERNS = [
    r"^VD-\d+",        # Thuốc tân dược trong nước
    r"^VN-\d+",        # Thuốc tân dược nhập khẩu
    r"^VN2-\d+",       # Thuốc tân dược nhập khẩu đợt 2
    r"^GC-\d+",        # Thuốc gia công
    r"^QLĐB-\d+",      # Thuốc quản lý đặc biệt
    r"^VS-\d+",        # Vắc xin, sinh phẩm
    r"^V\d+-[A-Z]\d+", # Thuốc đông dược, thảo dược (V161-H12-13, v.v.)
]

SUPPLEMENT_REG_PATTERNS = [
    r"\b\d+/\d+/ĐKSP\b",
    r"\b\d+/\d+/ATTP-XNCB\b",
    r"\bĐKSP\b",
    r"\bXNCB\b",
]

COSMETIC_REG_PATTERNS = [
    r"\b\d+/\d+/CBMP\b",
    r"\bCBMP\b",
]

DEVICE_REG_PATTERNS = [
    r"\b\d+/BYT-TB-CT\b",
    r"\bĐKLH-TTBYT\b",
    r"\bPCBB-BYT\b",
    r"\bTTBYT\b",
]


class ProductClassificationPipeline:
    """
    Quy trình phân loại sản phẩm y tế đa tầng theo chuẩn pháp lý Dược phẩm Việt Nam:
    Tuyệt đối không đoán mò Rx/OTC từ tên thuốc hay AI.
    Tách biệt hoàn toàn Loại sản phẩm pháp lý (ProductType) và Danh mục bán hàng (Storefront Category).
    """

    def __init__(self, db: Session):
        self.db = db

    def classify_product(self, product: CanonicalProduct) -> ClassificationProposal:
        proposal = ClassificationProposal()
        name = product.canonical_name or ""
        reg = normalize_reg_number(product.registration_number)

        # -------------------------------------------------------------
        # BƯỚC 1: Chuẩn hóa & kiểm tra trường thiếu
        # -------------------------------------------------------------
        if not reg:
            proposal.missing_fields.append("registration_number")
        if not product.manufacturer:
            proposal.missing_fields.append("manufacturer")
        if not product.dosage_form:
            proposal.missing_fields.append("dosage_form")

        # -------------------------------------------------------------
        # BƯỚC 2: Xác định product_type từ hồ sơ chính thức
        # -------------------------------------------------------------
        reg_record = None
        if reg:
            reg_record = self.db.scalar(
                select(RegulatoryRecord).where(RegulatoryRecord.registration_number == reg)
            )

        if reg_record:
            # Có hồ sơ pháp lý Cục Quản lý Dược
            proposal.suggested_product_type = LegalProductType.MEDICINE.value
            proposal.reasoning.append(f"Khớp hồ sơ đăng ký thuốc chính thức của Cục QLD: {reg}")
            proposal.confidence = max(proposal.confidence, 0.95)
        elif reg and any(re.search(pat, reg, re.IGNORECASE) for pat in MEDICINE_REG_PATTERNS):
            proposal.suggested_product_type = LegalProductType.MEDICINE.value
            proposal.reasoning.append(f"Số đăng ký có định dạng giấy phép lưu hành thuốc chính thức: {reg}")
            proposal.confidence = max(proposal.confidence, 0.90)
        elif reg and any(re.search(pat, reg, re.IGNORECASE) for pat in SUPPLEMENT_REG_PATTERNS):
            proposal.suggested_product_type = LegalProductType.SUPPLEMENT.value
            proposal.reasoning.append(f"Số công bố Cục An toàn thực phẩm (ĐKSP/XNCB): {reg}")
            proposal.confidence = max(proposal.confidence, 0.90)
        elif reg and any(re.search(pat, reg, re.IGNORECASE) for pat in COSMETIC_REG_PATTERNS):
            proposal.suggested_product_type = LegalProductType.COSMETIC.value
            proposal.reasoning.append(f"Số phiếu công bố mỹ phẩm (CBMP): {reg}")
            proposal.confidence = max(proposal.confidence, 0.90)
        elif reg and any(re.search(pat, reg, re.IGNORECASE) for pat in DEVICE_REG_PATTERNS):
            proposal.suggested_product_type = LegalProductType.MEDICAL_DEVICE.value
            proposal.reasoning.append(f"Số lưu hành thiết bị y tế Vụ Trang thiết bị y tế: {reg}")
            proposal.confidence = max(proposal.confidence, 0.90)
        else:
            # Chưa có bằng chứng số đăng ký pháp lý
            # Kiểm tra xem có bằng chứng đã duyệt trước đó từ Admin không
            approved_evidence = self.db.scalar(
                select(ProductClassificationEvidence).where(
                    ProductClassificationEvidence.product_id == product.id,
                    ProductClassificationEvidence.field_name == "product_type",
                    ProductClassificationEvidence.review_status == "APPROVED",
                ).order_by(ProductClassificationEvidence.id.desc())
            )
            if approved_evidence:
                proposal.suggested_product_type = approved_evidence.proposed_value
                proposal.reasoning.append(f"Theo bằng chứng đã được Admin phê duyệt (Evidence #{approved_evidence.id})")
                proposal.confidence = max(proposal.confidence, 0.95)
            else:
                proposal.suggested_product_type = LegalProductType.OTHER.value
                proposal.reasoning.append("Không có số đăng ký hoặc hồ sơ pháp lý đối chứng. Tạm xếp vào nhóm Chưa xác định (OTHER)")
                proposal.confidence = 0.20
                proposal.requires_review = True

        # -------------------------------------------------------------
        # BƯỚC 3: Xác định prescription_status theo quy tắc nghiêm ngặt
        # -------------------------------------------------------------
        if proposal.suggested_product_type != LegalProductType.MEDICINE.value:
            # Mỹ phẩm, TPCN, thiết bị y tế, mẹ bé -> NOT_APPLICABLE
            proposal.suggested_prescription_status = PrescriptionStatus.NOT_APPLICABLE.value
            proposal.reasoning.append("Sản phẩm không phải là Thuốc, trạng thái kê đơn là NOT_APPLICABLE")
        else:
            # Sản phẩm là Thuốc -> Tra cứu bằng chứng chính thức
            # Ưu tiên 1: Hồ sơ Cục Quản lý Dược
            if reg_record and reg_record.rx_otc_status:
                from app.models.enums import RxOtcStatus
                if reg_record.rx_otc_status == RxOtcStatus.OTC:
                    proposal.suggested_prescription_status = PrescriptionStatus.OTC.value
                    proposal.reasoning.append("Xác nhận OTC từ hồ sơ đăng ký Cục Quản lý Dược")
                elif reg_record.rx_otc_status == RxOtcStatus.PRESCRIPTION:
                    proposal.suggested_prescription_status = PrescriptionStatus.RX.value
                    proposal.reasoning.append("Xác nhận Thuốc Kê Đơn (Rx) từ hồ sơ đăng ký Cục Quản lý Dược")

            # Ưu tiên 2: Bằng chứng đã được Admin phê duyệt
            if not proposal.suggested_prescription_status:
                approved_rx_ev = self.db.scalar(
                    select(ProductClassificationEvidence).where(
                        ProductClassificationEvidence.product_id == product.id,
                        ProductClassificationEvidence.field_name == "prescription_status",
                        ProductClassificationEvidence.review_status == "APPROVED",
                    ).order_by(ProductClassificationEvidence.id.desc())
                )
                if approved_rx_ev:
                    proposal.suggested_prescription_status = approved_rx_ev.proposed_value
                    proposal.reasoning.append(f"Theo xác nhận của Admin (Evidence #{approved_rx_ev.id})")

            # Ưu tiên 3: Nếu vẫn chưa có bằng chứng -> Bắt buộc là UNKNOWN, KHÔNG đoán mò
            if not proposal.suggested_prescription_status:
                proposal.suggested_prescription_status = PrescriptionStatus.UNKNOWN.value
                proposal.reasoning.append("Chưa có hồ sơ đối chứng Cục QLD xác nhận Rx/OTC. Yêu cầu trạng thái UNKNOWN và chuyển duyệt")
                proposal.requires_review = True

        # -------------------------------------------------------------
        # BƯỚC 4 & 5: Gợi ý Storefront & Therapeutic Categories
        # -------------------------------------------------------------
        suggested_cats = self._suggest_categories(product, proposal.suggested_product_type, proposal.suggested_prescription_status)
        proposal.suggested_categories = suggested_cats

        # -------------------------------------------------------------
        # BƯỚC 6: Kiểm tra xung đột logic y tế
        # -------------------------------------------------------------
        self._detect_conflicts(product, proposal)

        # -------------------------------------------------------------
        # BƯỚC 7: Kết luận độ tin cậy và quyết định cần duyệt
        # -------------------------------------------------------------
        if (
            proposal.suggested_product_type in [LegalProductType.OTHER.value, None]
            or proposal.suggested_prescription_status == PrescriptionStatus.UNKNOWN.value
            or len(proposal.conflicts) > 0
            or proposal.confidence < 0.85
        ):
            proposal.requires_review = True
        else:
            proposal.requires_review = False

        return proposal

    def _suggest_categories(
        self, product: CanonicalProduct, p_type: str | None, rx_status: str | None
    ) -> list[dict[str, Any]]:
        suggestions = []
        name_lower = normalize_text(product.canonical_name)
        desc_lower = normalize_text(product.description or "")
        ind_lower = normalize_text(product.indications or "")
        combined = f"{name_lower} {desc_lower} {ind_lower}"

        # 1. Thuốc kê đơn
        if p_type == LegalProductType.MEDICINE.value and rx_status in [PrescriptionStatus.RX.value, PrescriptionStatus.CONTROLLED.value]:
            root_rx = self._get_cat_by_slug("thuoc-ke-don")
            if root_rx:
                suggestions.append({"category_id": root_rx.id, "slug": root_rx.slug, "name": root_rx.name, "is_primary": True, "method": AssignmentMethod.RULE_SUGGESTION.value})
                # Subcategories
                if any(k in combined for k in ["kháng sinh", "kháng nấm", "nhiễm khuẩn"]):
                    sub = self._get_cat_by_slug("khang-sinh")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["huyết áp", "tim mạch", "suy tim", "mỡ máu"]):
                    sub = self._get_cat_by_slug("tim-mach-huyet-ap")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["tiểu đường", "đái tháo đường", "hạ đường huyết"]):
                    sub = self._get_cat_by_slug("tieu-duong")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["xương khớp", "viêm khớp", "gút"]):
                    sub = self._get_cat_by_slug("co-xuong-khop")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})

        # 2. Thuốc không kê đơn
        elif p_type == LegalProductType.MEDICINE.value and rx_status == PrescriptionStatus.OTC.value:
            root_otc = self._get_cat_by_slug("thuoc-khong-ke-don")
            if root_otc:
                suggestions.append({"category_id": root_otc.id, "slug": root_otc.slug, "name": root_otc.name, "is_primary": True, "method": AssignmentMethod.RULE_SUGGESTION.value})
                if any(k in combined for k in ["giảm đau", "hạ sốt", "paracetamol"]):
                    sub = self._get_cat_by_slug("giam-dau-ha-sot")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["ho", "cảm cúm", "viêm họng", "rát họng", "viên ngậm"]):
                    sub = self._get_cat_by_slug("tri-ho-cam-cum")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["dạ dày", "tiêu hóa", "ợ nóng", "trào ngược", "tiêu chảy", "táo bón"]):
                    sub = self._get_cat_by_slug("da-day-tieu-hoa")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["dị ứng", "say xe", "mề đay", "sổ mũi"]):
                    sub = self._get_cat_by_slug("say-xe-di-ung")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})

        # 3. Thực phẩm bảo vệ sức khỏe
        elif p_type == LegalProductType.SUPPLEMENT.value:
            root_supp = self._get_cat_by_slug("thuc-pham-chuc-nang")
            if root_supp:
                suggestions.append({"category_id": root_supp.id, "slug": root_supp.slug, "name": root_supp.name, "is_primary": True, "method": AssignmentMethod.RULE_SUGGESTION.value})
                if any(k in combined for k in ["vitamin", "khoáng chất", "vi chất", "kẽm", "canxi"]):
                    sub = self._get_cat_by_slug("vitamin-khoang-chat")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["đề kháng", "miễn dịch"]):
                    sub = self._get_cat_by_slug("tang-mien-dich")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["não", "trí nhớ", "ginkgo"]):
                    sub = self._get_cat_by_slug("bo-nao")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})

            # Cho phép gợi ý thêm danh mục Mẹ & Bé nếu phù hợp
            if any(k in combined for k in ["bầu", "mang thai", "thai kỳ", "sau sinh", "cho con bú", "trẻ em", "bé"]):
                mb_root = self._get_cat_by_slug("me-va-be")
                if mb_root:
                    suggestions.append({"category_id": mb_root.id, "slug": mb_root.slug, "name": mb_root.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})

        # 4. Dược mỹ phẩm & Chăm sóc da
        elif p_type == LegalProductType.COSMETIC.value:
            root_cosm = self._get_cat_by_slug("duoc-my-pham")
            if root_cosm:
                suggestions.append({"category_id": root_cosm.id, "slug": root_cosm.slug, "name": root_cosm.name, "is_primary": True, "method": AssignmentMethod.RULE_SUGGESTION.value})
                if any(k in combined for k in ["rửa mặt", "tẩy trang", "cleanser"]):
                    sub = self._get_cat_by_slug("sua-rua-mat")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["chống nắng", "sunscreen"]):
                    sub = self._get_cat_by_slug("kem-chong-nang")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["mụn", "acne", "b5", "phục hồi"]):
                    sub = self._get_cat_by_slug("tri-mun-phuc-hoi")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})

        # 5. Thiết bị y tế
        elif p_type == LegalProductType.MEDICAL_DEVICE.value:
            root_dev = self._get_cat_by_slug("thiet-bi-y-te")
            if root_dev:
                suggestions.append({"category_id": root_dev.id, "slug": root_dev.slug, "name": root_dev.name, "is_primary": True, "method": AssignmentMethod.RULE_SUGGESTION.value})
                if any(k in combined for k in ["huyết áp", "omron"]):
                    sub = self._get_cat_by_slug("may-do-huyet-ap")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["đường huyết", "que thử"]):
                    sub = self._get_cat_by_slug("may-do-duong-huyet")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})
                elif any(k in combined for k in ["nhiệt kế", "spo2"]):
                    sub = self._get_cat_by_slug("nhiet-ke-spo2")
                    if sub: suggestions.append({"category_id": sub.id, "slug": sub.slug, "name": sub.name, "is_primary": False, "method": AssignmentMethod.RULE_SUGGESTION.value})

        # 6. Mẹ & Bé thuần túy
        elif p_type == LegalProductType.MOTHER_BABY.value:
            root_mb = self._get_cat_by_slug("me-va-be")
            if root_mb:
                suggestions.append({"category_id": root_mb.id, "slug": root_mb.slug, "name": root_mb.name, "is_primary": True, "method": AssignmentMethod.RULE_SUGGESTION.value})

        return suggestions

    def _get_cat_by_slug(self, slug: str) -> Category | None:
        return self.db.scalar(select(Category).where(Category.slug == slug))

    def _detect_conflicts(self, product: CanonicalProduct, proposal: ClassificationProposal) -> None:
        p_type = proposal.suggested_product_type
        rx_status = proposal.suggested_prescription_status
        name_lower = normalize_text(product.canonical_name)
        desc_lower = normalize_text(product.description or "")
        combined = f"{name_lower} {desc_lower}"

        # Xung đột 1: COSMETIC nhưng prescription_status là OTC hoặc RX
        if p_type == LegalProductType.COSMETIC.value and rx_status in [PrescriptionStatus.OTC.value, PrescriptionStatus.RX.value, PrescriptionStatus.CONTROLLED.value]:
            proposal.conflicts.append("Mỹ phẩm (COSMETIC) không được phép có trạng thái kê đơn OTC/RX.")

        # Xung đột 2: MEDICAL_DEVICE nhưng có trạng thái kê đơn OTC hoặc RX
        if p_type == LegalProductType.MEDICAL_DEVICE.value and rx_status in [PrescriptionStatus.OTC.value, PrescriptionStatus.RX.value, PrescriptionStatus.CONTROLLED.value]:
            proposal.conflicts.append("Thiết bị y tế (MEDICAL_DEVICE) không được phép có trạng thái kê đơn OTC/RX.")

        # Xung đột 3: SUPPLEMENT nhưng tuyên bố điều trị/chữa bệnh
        if p_type == LegalProductType.SUPPLEMENT.value:
            if any(k in combined for k in ["điều trị bệnh", "chữa khỏi bệnh", "thay thế thuốc chữa bệnh"]):
                proposal.conflicts.append("Thực phẩm chức năng không được phép sử dụng từ ngữ mang ý nghĩa điều trị hay chữa bệnh.")

        # Xung đột 4: Danh mục gợi ý không tương thích với product_type
        for cat_info in proposal.suggested_categories:
            cat_obj = self.db.get(Category, cat_info["category_id"])
            if cat_obj and cat_obj.allowed_product_type and p_type:
                if cat_obj.allowed_product_type != p_type:
                    proposal.conflicts.append(
                        f"Danh mục '{cat_obj.name}' yêu cầu loại sản phẩm '{cat_obj.allowed_product_type}', mâu thuẫn với '{p_type}'."
                    )

    def apply_proposal(
        self,
        product: CanonicalProduct,
        proposal: ClassificationProposal,
        user_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        """Lưu kết quả phân loại vào database, cập nhật bảng ánh xạ và ghi audit log."""
        prev_data = {
            "product_type": product.product_type,
            "prescription_status": product.prescription_status,
            "category_slug": product.category_slug,
            "subcategory_slug": product.subcategory_slug,
        }

        # Cập nhật CanonicalProduct
        if proposal.suggested_product_type:
            product.product_type = proposal.suggested_product_type
        if proposal.suggested_prescription_status:
            product.prescription_status = proposal.suggested_prescription_status
            # Đồng bộ ngược với rx_otc_status cũ để không làm gãy code hiện tại
            from app.models.enums import RxOtcStatus
            if proposal.suggested_prescription_status == PrescriptionStatus.RX.value:
                product.rx_otc_status = RxOtcStatus.PRESCRIPTION
            elif proposal.suggested_prescription_status == PrescriptionStatus.OTC.value:
                product.rx_otc_status = RxOtcStatus.OTC
            else:
                product.rx_otc_status = RxOtcStatus.UNKNOWN

        # Gán category chính và phụ
        primary_slug = None
        sub_slug = None
        for cat_item in proposal.suggested_categories:
            if cat_item.get("is_primary"):
                primary_slug = cat_item["slug"]
            else:
                if not sub_slug:
                    sub_slug = cat_item["slug"]

        if primary_slug:
            product.category_slug = primary_slug
        if sub_slug:
            product.subcategory_slug = sub_slug

        product.category_confidence = proposal.confidence
        product.category_review_status = (
            ClassificationReviewStatus.PENDING.value
            if proposal.requires_review
            else ClassificationReviewStatus.AUTO_RESOLVED.value
        )
        product.category_review_reason = "; ".join(proposal.reasoning)

        # Xóa liên kết category cũ và ghi lại liên kết mới
        self.db.query(ProductCategory).filter(ProductCategory.product_id == product.id).delete()
        for c in proposal.suggested_categories:
            self.db.add(
                ProductCategory(
                    product_id=product.id,
                    category_id=c["category_id"],
                    is_primary=c.get("is_primary", False),
                    assignment_method=c.get("method", AssignmentMethod.RULE_SUGGESTION.value),
                    confidence=proposal.confidence,
                    assigned_by=user_id,
                    approved_by=user_id if not proposal.requires_review else None,
                    approved_at=utcnow() if not proposal.requires_review else None,
                )
            )

        # Lưu hàng chờ review nếu cần duyệt
        if proposal.requires_review:
            primary_cat_id = None
            for c in proposal.suggested_categories:
                if c.get("is_primary"):
                    primary_cat_id = c["category_id"]
                    break
            self.db.add(
                ProductClassificationReview(
                    product_id=product.id,
                    suggested_product_type=proposal.suggested_product_type,
                    suggested_prescription_status=proposal.suggested_prescription_status,
                    suggested_category_id=primary_cat_id,
                    confidence=proposal.confidence,
                    reasoning="; ".join(proposal.reasoning),
                    missing_fields_json=proposal.missing_fields,
                    conflicts_json=proposal.conflicts,
                    status=ClassificationReviewStatus.PENDING.value,
                )
            )

        # Lưu lịch sử phân loại
        new_data = {
            "product_type": product.product_type,
            "prescription_status": product.prescription_status,
            "category_slug": product.category_slug,
            "subcategory_slug": product.subcategory_slug,
            "suggested_categories": proposal.suggested_categories,
        }
        self.db.add(
            ProductClassificationHistory(
                product_id=product.id,
                previous_data_json=prev_data,
                new_data_json=new_data,
                changed_by=user_id,
                reason=reason or "; ".join(proposal.reasoning),
                evidence_source=proposal.evidence_source,
            )
        )
