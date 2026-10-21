"""
Unit tests for H4CARE Product Eligibility Engine & Commercial Readiness (Module B).
Runs strictly on isolated test database (pharmatrust_test.db).
"""
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app
from app.models import CanonicalProduct
from app.models.enums import PublishStatus, RxOtcStatus
from app.models.inventory import InventoryBatch, ProductSku, WarehouseBatchStock
from app.services.product_eligibility_service import ProductEligibilityService


class TestProductEligibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_db_config import setup_isolated_test_db, TestSessionLocal
        setup_isolated_test_db()
        cls.SessionClass = TestSessionLocal

    @classmethod
    def tearDownClass(cls):
        from tests.test_db_config import teardown_isolated_test_db
        teardown_isolated_test_db()

    def setUp(self):
        self.client = TestClient(app)
        self.db = self.SessionClass()

    def tearDown(self):
        self.db.close()

    def test_evaluate_rx_product_restricted(self):
        """Thuốc kê đơn (Rx) phải bị chặn bán trực tuyến với tier PRESCRIPTION_RESTRICTED."""
        rx_prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.rx_otc_status == RxOtcStatus.PRESCRIPTION,
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
        ).first()
        self.assertIsNotNone(rx_prod)

        res = ProductEligibilityService.evaluate_product_eligibility(rx_prod, self.db)
        self.assertFalse(res.is_eligible_for_sale)
        self.assertFalse(res.can_add_to_cart)
        self.assertEqual(res.eligibility_tier, "PRESCRIPTION_RESTRICTED")
        self.assertEqual(res.cta_type, "RX_PRESCRIPTION")
        self.assertIn("thuốc kê đơn", res.primary_reason.lower())
        self.assertIn("bộ y tế", res.primary_reason.lower())

    def test_evaluate_reference_only_product(self):
        """Sản phẩm danh mục tham khảo (REFERENCE_ONLY) chỉ cho tra cứu, không cho thêm vào giỏ."""
        ref_prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.publish_mode == "REFERENCE_ONLY",
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
        ).first()
        self.assertIsNotNone(ref_prod)

        res = ProductEligibilityService.evaluate_product_eligibility(ref_prod, self.db)
        self.assertFalse(res.is_eligible_for_sale)
        self.assertFalse(res.can_add_to_cart)
        self.assertEqual(res.eligibility_tier, "REFERENCE_ONLY")
        self.assertEqual(res.cta_type, "CONSULT_PHARMACIST")
        self.assertIn("tham khảo", res.primary_reason.lower())

    def test_evaluate_internal_test_product(self):
        """Sản phẩm thử nghiệm nội bộ (INTERNAL_TEST / is_demo) bị khóa hoàn toàn khỏi bán hàng."""
        test_prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.publish_mode == "INTERNAL_TEST",
        ).first()
        if not test_prod:
            test_prod = self.db.query(CanonicalProduct).filter(
                CanonicalProduct.is_demo == True,
            ).first()
        self.assertIsNotNone(test_prod)

        res = ProductEligibilityService.evaluate_product_eligibility(test_prod, self.db)
        self.assertFalse(res.is_eligible_for_sale)
        self.assertFalse(res.can_add_to_cart)
        self.assertEqual(res.eligibility_tier, "INTERNAL_TEST")
        self.assertEqual(res.cta_type, "LOCKED")

    def test_evaluate_multi_sku_pricing_and_selection(self):
        """Sản phẩm có nhiều SKU (Hapacol: Hộp vs Gói) trả về danh sách SKU và giá chính xác theo SKU được chọn."""
        prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.id == 501,
        ).first()
        self.assertIsNotNone(prod)

        # Gọi không truyền sku_id -> mặc định chọn SKU default (Hộp)
        res_default = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertTrue(len(res_default.skus) >= 2)
        default_sku = res_default.selected_sku
        self.assertIsNotNone(default_sku)
        self.assertEqual(default_sku["uom"], "Hộp")
        self.assertEqual(default_sku["base_price"], 45000)

        # Gọi với SKU thứ 2 (Gói)
        secondary_sku = [s for s in res_default.skus if s["uom"] == "Gói"][0]
        res_sec = ProductEligibilityService.evaluate_product_eligibility(prod, self.db, sku_id=secondary_sku["id"])
        self.assertEqual(res_sec.selected_sku["id"], secondary_sku["id"])
        self.assertEqual(res_sec.selected_sku["uom"], "Gói")
        self.assertEqual(res_sec.selected_sku["base_price"], 2000)

    def test_expired_batches_excluded_from_available_stock(self):
        """Các lô hàng đã hết hạn sử dụng tuyệt đối không được tính vào tồn khả dụng."""
        prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.id == 99770, # Prospan có lô expired 2026-09-20 trong DB
        ).first()
        self.assertIsNotNone(prod)

        res = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        today = date.today()
        from sqlalchemy import func
        sku = self.db.query(ProductSku).filter(ProductSku.canonical_product_id == prod.id).first()
        total_all_batches = self.db.query(func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0)).join(
            InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id
        ).filter(InventoryBatch.sku_id == sku.id).scalar()

        expired_qty = self.db.query(func.coalesce(func.sum(WarehouseBatchStock.quantity_available), 0)).join(
            InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id
        ).filter(
            InventoryBatch.sku_id == sku.id,
            InventoryBatch.expiry_date <= today,
        ).scalar()

        # res.available_stock must equal total_all_batches - expired_qty
        self.assertEqual(res.available_stock, total_all_batches - expired_qty)
        self.assertGreater(expired_qty, 0)

    def test_product_without_sku_is_locked(self):
        """Sản phẩm không có SKU trong database phải bị khóa (LOCKED), stock = 0, can_add_to_cart = False."""
        no_sku_prod = CanonicalProduct(
            canonical_name="Thuốc Thử Nghiệm Không SKU",
            registration_number="VD-99999-25",
            publish_status=PublishStatus.PUBLISHED,
            publish_mode="SALE_ELIGIBLE",
            rx_otc_status=RxOtcStatus.OTC,
            is_demo=False,
        )
        self.db.add(no_sku_prod)
        self.db.commit()

        res = ProductEligibilityService.evaluate_product_eligibility(no_sku_prod, self.db)
        self.assertFalse(res.is_eligible_for_sale)
        self.assertFalse(res.can_add_to_cart)
        self.assertEqual(res.available_stock, 0)
        self.assertEqual(res.cta_type, "LOCKED")
        self.assertEqual(res.eligibility_tier, "UNVERIFIED_DATA")

    def test_transparency_score_and_data_provenance(self):
        """Hồ sơ minh bạch cung cấp điểm số, nguồn đối chiếu và tuyên bố trách nhiệm y khoa."""
        prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.id == 106139, # Telfast HD 180mg
        ).first()
        self.assertIsNotNone(prod)

        res = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        t_info = res.transparency_info
        self.assertIn("completeness_score", t_info)
        self.assertGreaterEqual(t_info["completeness_score"], 80)
        self.assertIn("registration_number", t_info)
        self.assertEqual(t_info["registration_number"], "VD-25032-16")
        self.assertIn("disclaimer", t_info)
        self.assertIn("không phải đánh giá chất lượng sinh học", t_info["disclaimer"])

    def test_api_product_detail_includes_eligibility_payload(self):
        """Endpoint GET /store/products/{id} trả về đầy đủ thông tin eligibility và multi-SKU."""
        response = self.client.get("/api/v1/store/products/501")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("catalogTier", data)
        self.assertIn("isSaleEligible", data)
        self.assertIn("canAddToCart", data)
        self.assertIn("ctaType", data)
        self.assertIn("ctaLabel", data)
        self.assertIn("transparency", data)
        self.assertIn("skus", data)
        self.assertTrue(len(data["skus"]) >= 2)

    def test_api_product_eligibility_dedicated_endpoint(self):
        """Endpoint GET /store/products/{id}/eligibility phản hồi thời gian thực khi chuyển SKU."""
        response = self.client.get("/api/v1/store/products/501/eligibility")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("is_eligible_for_sale", data)
        self.assertIn("eligibility_tier", data)
        self.assertIn("can_add_to_cart", data)
        self.assertIn("transparency_info", data)
        self.assertIn("skus", data)


if __name__ == "__main__":
    unittest.main()
