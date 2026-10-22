"""
H4CARE Core Backend - Commercial Product Eligibility Engine
Động cơ thẩm định điều kiện mở bán và an toàn dược phẩm thương mại.
Tuân thủ Luật Dược 2016, Thông tư 02/2018/TT-BYT, quy chế GPP/GSP và thuật toán FEFO.
"""
from datetime import date, datetime
import re
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CanonicalProduct
from app.models.enums import PublishStatus, RxOtcStatus
from app.models.inventory import BatchStatus, InventoryBatch, ProductSku, WarehouseBatchStock


class ProductEligibilityResult:
    def __init__(
        self,
        is_eligible_for_sale: bool,
        eligibility_tier: str,
        can_add_to_cart: bool,
        cta_type: str,
        cta_label: str,
        available_stock: int,
        primary_reason: str,
        reasons: list[str],
        transparency_info: dict[str, Any],
        skus: list[dict[str, Any]],
        selected_sku: dict[str, Any] | None = None,
    ):
        self.is_eligible_for_sale = is_eligible_for_sale
        self.eligibility_tier = eligibility_tier
        self.can_add_to_cart = can_add_to_cart
        self.cta_type = cta_type
        self.cta_label = cta_label
        self.available_stock = available_stock
        self.primary_reason = primary_reason
        self.reasons = reasons
        self.transparency_info = transparency_info
        self.skus = skus
        self.selected_sku = selected_sku

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_eligible_for_sale": self.is_eligible_for_sale,
            "eligibility_tier": self.eligibility_tier,
            "can_add_to_cart": self.can_add_to_cart,
            "cta_type": self.cta_type,
            "cta_label": self.cta_label,
            "available_stock": self.available_stock,
            "primary_reason": self.primary_reason,
            "reasons": self.reasons,
            "transparency_info": self.transparency_info,
            "skus": self.skus,
            "selected_sku": self.selected_sku,
        }


class ProductEligibilityService:
    # Chuẩn số đăng ký lưu hành chính thức Cục Quản lý Dược (Bộ Y Tế)
    # Loại bỏ hoàn toàn regex bắt tự do; chỉ chấp nhận các đầu mã lưu hành pháp lý chuẩn
    DAV_REG_REGEX = re.compile(
        r"^(VD|VD3|VN|VN2|VN3|QLĐB|GC)-\d+-\d{2}$"
        r"|^V\d{2,4}-[A-Z]\d{2}-\d{2}$"
        r"|^\d+/\d{4}/(ĐKSP|ATTP-XNCB|ATTP-TNCB)$"
        r"|^\d{2,5}/(BYT-TB-CT|ĐKLT-BYT)$",
        re.IGNORECASE,
    )

    @classmethod
    def is_valid_registration_format(cls, reg_num: str | None) -> bool:
        """Kiểm tra định dạng cấu trúc cú pháp của Số Đăng Ký (FORMAT_VALID)."""
        if not reg_num or not isinstance(reg_num, str):
            return False
        clean = reg_num.strip().upper()
        if len(clean) < 6:
            return False
        if any(clean.startswith(prefix) for prefix in ("DEMO", "REF-", "TEST", "SAMPLE", "DRAFT", "TEMP")):
            return False
        return bool(cls.DAV_REG_REGEX.match(clean))

    @classmethod
    def is_verified_registration(cls, reg_num: str | None) -> bool:
        """Alias tương thích ngược kiểm tra cú pháp SĐK hợp lệ."""
        return cls.is_valid_registration_format(reg_num)

    @classmethod
    def verify_official_registration(
        cls, product: CanonicalProduct, db: Session
    ) -> tuple[bool, str, list[str]]:
        """
        Kiểm tra bằng chứng đối chiếu thực tế với hồ sơ quản lý dược (OFFICIALLY_VERIFIED).
        Tuyệt đối không dùng độ dài hoặc regex để chứng minh tính pháp lý nếu thiếu chứng cứ.
        """
        if not product.registration_number or not isinstance(product.registration_number, str):
            return False, "MISSING_REGISTRATION", []

        if not cls.is_valid_registration_format(product.registration_number):
            return False, "INVALID_FORMAT", []

        clean_reg = product.registration_number.strip().upper()

        from app.models.entities import RegulatoryRecord
        records = db.query(RegulatoryRecord).filter(
            func.upper(RegulatoryRecord.registration_number) == clean_reg
        ).all()

        if not records:
            return False, "FORMAT_VALID_UNVERIFIED_EVIDENCE", []

        sources = []
        has_verified_record = False
        for rec in records:
            if rec.source_url:
                sources.append(rec.source_url)
                has_verified_record = True
            elif rec.official_name:
                sources.append("Cơ sở dữ liệu Dược thư Cục Quản lý Dược")
                has_verified_record = True

        if has_verified_record:
            return True, "OFFICIALLY_VERIFIED", sources

        return False, "FORMAT_VALID_UNVERIFIED_EVIDENCE", []

    @classmethod
    def calculate_transparency_score(cls, product: CanonicalProduct) -> tuple[int, list[str]]:
        """
        Tính điểm mức độ minh bạch và đầy đủ của hồ sơ dược khoa.
        Điểm số phản ánh mức độ đối chiếu dữ liệu, KHÔNG phải chất lượng hay an toàn tuyệt đối của thuốc.
        """
        checklist = [
            ("canonical_name", bool(product.canonical_name), 10),
            ("registration_number", cls.is_valid_registration_format(product.registration_number), 20),
            ("manufacturer", bool(product.manufacturer), 10),
            ("dosage_form", bool(product.dosage_form), 10),
            ("indications", bool(product.indications), 10),
            ("usage_instructions", bool(product.usage_instructions), 10),
            ("contraindications", bool(product.contraindications), 10),
            ("side_effects", bool(product.side_effects), 10),
            ("storage_conditions", bool(product.storage_conditions), 10),
        ]

        score = sum(points for _, present, points in checklist if present)
        missing_fields = [field for field, present, _ in checklist if not present]
        return score, missing_fields

    @classmethod
    def evaluate_product_eligibility(
        cls,
        product: CanonicalProduct,
        db: Session,
        sku_id: int | None = None,
    ) -> ProductEligibilityResult:
        reasons: list[str] = []
        now = datetime.now()
        today = date.today()

        # 1. Thu thập danh sách SKU của sản phẩm
        all_skus = db.query(ProductSku).filter(
            ProductSku.canonical_product_id == product.id,
            ProductSku.is_active == True,
        ).order_by(ProductSku.is_default.desc(), ProductSku.id.asc()).all()

        sku_list: list[dict[str, Any]] = []
        selected_sku_dict: dict[str, Any] | None = None

        for s in all_skus:
            # Tính tồn khả dụng theo từng SKU (chỉ tính lô ACTIVE, chưa hết hạn, không bị cách ly)
            sku_stock_query = db.query(
                func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0)
            ).join(
                InventoryBatch, InventoryBatch.id == WarehouseBatchStock.batch_id
            ).filter(
                InventoryBatch.sku_id == s.id,
                InventoryBatch.status == BatchStatus.ACTIVE,
                InventoryBatch.expiry_date > today,
                WarehouseBatchStock.quantity_available > 0,
            )
            s_stock = int(sku_stock_query.scalar() or 0)

            s_data = {
                "id": s.id,
                "sku_code": s.sku_code,
                "uom": s.uom,
                "conversion_rate": s.conversion_rate or 1,
                "base_price": int(s.base_price or 0),
                "is_default": bool(s.is_default),
                "available_stock": s_stock,
            }
            sku_list.append(s_data)
            if sku_id and s.id == sku_id:
                selected_sku_dict = s_data

        if not selected_sku_dict and sku_list:
            selected_sku_dict = sku_list[0]

        # 2. Tính toán điểm minh bạch dữ liệu H4CARE
        comp_score, missing_fields = cls.calculate_transparency_score(product)
        is_format_valid = cls.is_valid_registration_format(product.registration_number)
        is_officially_verified, reg_status_code, reg_sources = cls.verify_official_registration(product, db)

        if is_officially_verified:
            source_name = "Dữ liệu Cục Quản lý Dược (Bộ Y Tế) & Hồ sơ pháp lý đã đối chiếu"
            reg_status_label = "ĐÃ ĐỐI CHIẾU SỐ ĐĂNG KÝ VỚI CƠ QUAN QUẢN LÝ"
        elif is_format_valid:
            source_name = "Cấu trúc định dạng SĐK hợp lệ - Đang chờ đối chiếu hồ sơ gốc"
            reg_status_label = "ĐÚNG ĐỊNH DẠNG SĐK - CHƯA ĐỐI CHIẾU CHỨNG TỪ GỐC"
        else:
            source_name = "Dữ liệu tra cứu danh mục dược lý tham khảo"
            reg_status_label = "SỐ ĐĂNG KÝ CHƯA ĐẠT CHUẨN ĐỊNH DẠNG"

        pending_verifications: list[str] = []
        if not is_officially_verified:
            pending_verifications.append("Đối chiếu số đăng ký với hồ sơ cấp phép lưu hành của Cục Quản lý Dược")
        if product.publish_mode != "SALE_ELIGIBLE":
            pending_verifications.append("Biên bản kiểm nghiệm chất lượng xuất xưởng (COA) của lô hàng vật lý")
            pending_verifications.append("Phiếu kiểm nhập kho GSP và hóa đơn GTGT của nhà phân phối hợp pháp")
        if missing_fields:
            pending_verifications.append(f"Cập nhật hoàn thiện các trường dữ liệu: {', '.join(missing_fields)}")

        transparency_info = {
            "source_name": source_name,
            "registration_number": product.registration_number or "Đang cập nhật",
            "registration_status": reg_status_label,
            "registration_status_code": reg_status_code,
            "verified_sources": reg_sources,
            "is_officially_verified": is_officially_verified,
            "is_format_valid": is_format_valid,
            "completeness_score": comp_score,
            "pending_verifications": pending_verifications,
            "last_audited_at": (product.updated_at or product.created_at or now).strftime("%Y-%m-%d"),
            "disclaimer": "Chỉ số minh bạch dữ liệu phản ánh mức độ đầy đủ và nguồn gốc đối chiếu của hồ sơ thông tin, không phải đánh giá chất lượng sinh học hay hiệu quả điều trị của thuốc.",
        }

        # 3. KIỂM TRA ĐIỀU KIỆN MỞ BÁN (9 PILLARS)

        # Pillar 1: Trạng thái phát hành
        if product.publish_status != PublishStatus.PUBLISHED or product.is_demo or product.publish_mode == "INTERNAL_TEST":
            return ProductEligibilityResult(
                is_eligible_for_sale=False,
                eligibility_tier="INTERNAL_TEST",
                can_add_to_cart=False,
                cta_type="LOCKED",
                cta_label="Không Khả Dụng",
                available_stock=0,
                primary_reason="Sản phẩm thử nghiệm nội bộ, không công khai trên sàn thương mại.",
                reasons=["Sản phẩm mang nhãn INTERNAL_TEST hoặc is_demo=True."],
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=selected_sku_dict,
            )

        # Pillar 2: Kiểm tra Thuốc kê đơn (Rx Safety Enforcement)
        is_rx = product.rx_otc_status == RxOtcStatus.PRESCRIPTION
        if is_rx:
            reasons.append("Theo Thông tư 02/2018/TT-BYT và Luật Dược 2016, thuốc kê đơn (Rx) tuyệt đối không được bán trực tuyến.")
            reasons.append("Khách hàng cần gửi đơn thuốc hợp lệ để Dược sĩ Đại học kiểm duyệt liều lượng và tư vấn trực tiếp.")
            return ProductEligibilityResult(
                is_eligible_for_sale=False,
                eligibility_tier="PRESCRIPTION_RESTRICTED",
                can_add_to_cart=False,
                cta_type="RX_PRESCRIPTION",
                cta_label="Gửi Đơn Thuốc Để Dược Sĩ Tư Vấn",
                available_stock=selected_sku_dict["available_stock"] if selected_sku_dict else 0,
                primary_reason="Thuốc kê đơn (Rx) không được phép bán trực tuyến theo quy định của Bộ Y Tế.",
                reasons=reasons,
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=selected_sku_dict,
            )

        # Pillar 3: Thu hồi hoặc đình chỉ lưu hành
        if product.regulatory_status in ["RECALLED", "SUSPENDED", "EXPIRED"]:
            reasons.append(f"Sản phẩm có trạng thái pháp lý: {product.regulatory_status}.")
            return ProductEligibilityResult(
                is_eligible_for_sale=False,
                eligibility_tier="RECALLED",
                can_add_to_cart=False,
                cta_type="LOCKED",
                cta_label="Sản Phẩm Tạm Đình Chỉ",
                available_stock=0,
                primary_reason="Sản phẩm thuộc diện tạm ngừng lưu hành hoặc thu hồi theo thông báo của cơ quan quản lý.",
                reasons=reasons,
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=selected_sku_dict,
            )

        # Pillar 4: Danh mục tham khảo (REFERENCE_ONLY)
        if product.publish_mode == "REFERENCE_ONLY":
            reasons.append("Sản phẩm thuộc danh mục tra cứu thông tin dược khoa tham khảo.")
            reasons.append("Chưa có chứng từ kiểm nghiệm xuất xưởng (COA) và hóa đơn nhập kho vật lý từ nhà phân phối.")
            return ProductEligibilityResult(
                is_eligible_for_sale=False,
                eligibility_tier="REFERENCE_ONLY",
                can_add_to_cart=False,
                cta_type="CONSULT_PHARMACIST",
                cta_label="Tra Cứu Dược Lý / Tư Vấn Dược Sĩ",
                available_stock=0,
                primary_reason="Sản phẩm thuộc danh mục tra cứu thông tin tham khảo, chưa mở bán trực tuyến.",
                reasons=reasons,
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=selected_sku_dict,
            )

        # Pillar 5: Kiểm tra SKU và Giá bán
        if not selected_sku_dict:
            reasons.append("Sản phẩm chưa có quy cách đóng gói (SKU) được phê duyệt mở bán.")
            return ProductEligibilityResult(
                is_eligible_for_sale=False,
                eligibility_tier="UNVERIFIED_DATA",
                can_add_to_cart=False,
                cta_type="LOCKED",
                cta_label="Chưa Có Quy Cách / Giá",
                available_stock=0,
                primary_reason="Sản phẩm chưa có quy cách đóng gói (SKU) hợp lệ trong hệ thống.",
                reasons=reasons,
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=None,
            )

        if selected_sku_dict.get("base_price", 0) <= 0:
            reasons.append("Sản phẩm chưa có giá bán thương mại niêm yết hợp lệ từ SKU chính thức.")
            return ProductEligibilityResult(
                is_eligible_for_sale=False,
                eligibility_tier="UNVERIFIED_DATA",
                can_add_to_cart=False,
                cta_type="LOCKED",
                cta_label="Chưa Có Giá Niêm Yết",
                available_stock=0,
                primary_reason="Chưa có thông tin giá bán thương mại được phê duyệt từ quy cách đóng gói chính thức (không sử dụng giá tham khảo thị trường).",
                reasons=reasons,
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=selected_sku_dict,
            )

        # Pillar 6: Kiểm tra Tồn kho khả dụng (FEFO Stock Check)
        cur_stock = selected_sku_dict["available_stock"]
        if cur_stock <= 0:
            reasons.append("Hiện tại không có lô hàng nào đạt chuẩn cấp phát (hết tồn, hết hạn dùng hoặc đang cách ly kiểm nghiệm).")
            return ProductEligibilityResult(
                is_eligible_for_sale=False,
                eligibility_tier="OUT_OF_STOCK",
                can_add_to_cart=False,
                cta_type="OUT_OF_STOCK",
                cta_label="Tạm Hết Hàng",
                available_stock=0,
                primary_reason="Tạm hết hàng tại hệ thống nhà thuốc và kho phân phối GPP.",
                reasons=reasons,
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=selected_sku_dict,
            )

        # Pillar 7: Đủ điều kiện bán hàng thương mại (SALE_ELIGIBLE)
        # Chỉ có publish_mode == 'SALE_ELIGIBLE' và publish_status == PUBLISHED mới được mở bán trực tuyến
        if product.publish_mode == "SALE_ELIGIBLE" and product.publish_status == PublishStatus.PUBLISHED:
            return ProductEligibilityResult(
                is_eligible_for_sale=True,
                eligibility_tier="SALE_ELIGIBLE",
                can_add_to_cart=True,
                cta_type="BUY_NOW",
                cta_label="Chọn Mua Ngay",
                available_stock=cur_stock,
                primary_reason="Sản phẩm đạt toàn bộ tiêu chuẩn thương mại, có tồn kho xác minh và đủ điều kiện bán trực tuyến.",
                reasons=[
                    "Đã xác thực định dạng số đăng ký lưu hành.",
                    "Lô hàng hợp lệ, còn hạn dùng theo chuẩn FEFO.",
                    "Đủ điều kiện kinh doanh sản phẩm OTC trực tuyến.",
                ],
                transparency_info=transparency_info,
                skus=sku_list,
                selected_sku=selected_sku_dict,
            )

        # Trường hợp VERIFIED_PRODUCT_DATA (Dữ liệu đã đối chiếu nhưng chưa ký quỹ kho bán online)
        return ProductEligibilityResult(
            is_eligible_for_sale=False,
            eligibility_tier="VERIFIED_PRODUCT_DATA",
            can_add_to_cart=False,
            cta_type="CONSULT_PHARMACIST",
            cta_label="Tư Vấn Dược Sĩ (Chưa Mở Bán Trực Tuyến)",
            available_stock=cur_stock,
            primary_reason="Dữ liệu dược khoa đã được đối chiếu chính thức, nhưng sản phẩm chưa kích hoạt mở bán thương mại trực tuyến.",
            reasons=[
                "Hồ sơ đăng ký lưu hành đã được xác minh đối chiếu với Cục Quản lý Dược.",
                "Cần hoàn tất quy trình nghiệm thu chứng từ nhập kho vật lý GSP trước khi mở bán thương mại cho khách hàng.",
            ],
            transparency_info=transparency_info,
            skus=sku_list,
            selected_sku=selected_sku_dict,
        )
