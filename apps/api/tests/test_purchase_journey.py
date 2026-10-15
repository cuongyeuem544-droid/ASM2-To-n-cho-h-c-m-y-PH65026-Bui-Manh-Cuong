"""
H4CARE Commercial E2E Purchase Journey & Commercial Safety Test Suite.
Tests both positive commercial fulfillment and negative safety gates.
Runs strictly against isolated test database (pharmatrust_test.db).
"""
import os
import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    BatchStatus,
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderItemBatchAllocation,
    ProductSku,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus
from app.services.product_eligibility_service import ProductEligibilityService


class TestPurchaseJourney(unittest.TestCase):
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

        # Đảm bảo có kho kiểm thử mặc định
        self.wh = self.db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not self.wh:
            self.wh = Warehouse(
                code="KHO-HCM-01",
                name="Tổng kho Miền Nam (Tân Bình)",
                address="45 Hoàng Hoa Thám, P.13, Q. Tân Bình, TP. Hồ Chí Minh",
                is_active=True,
                is_central=True,
                lat=10.7981,
                lng=106.6534,
            )
            self.db.add(self.wh)
            self.db.commit()
            self.db.refresh(self.wh)

    def tearDown(self):
        self.db.close()

    def _create_isolated_product(
        self,
        pid: int,
        name: str,
        publish_mode: str,
        rx_status: RxOtcStatus = RxOtcStatus.OTC,
        regulatory_status: str = "ACTIVE",
        reg_number: str | None = None,
    ) -> CanonicalProduct:
        # Xóa nếu đã tồn tại để tránh conflict
        existing = self.db.query(CanonicalProduct).filter_by(id=pid).first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        if not reg_number:
            reg_number = f"VD-TEST-{pid}"

        prod = CanonicalProduct(
            id=pid,
            canonical_name=name,
            registration_number=reg_number,
            dosage_form="Viên nén",
            manufacturer="DHG Pharma Test",
            manufacturing_country="Việt Nam",
            package_description="Hộp 10 vỉ x 10 viên",
            rx_otc_status=rx_status,
            publish_status=PublishStatus.PUBLISHED,
            publish_mode=publish_mode,
            regulatory_status=regulatory_status,
            is_demo=False,
            category_slug="giam-dau-ha-sot",
            subcategory_slug="paracetamol",
        )
        self.db.add(prod)
        self.db.commit()
        self.db.refresh(prod)
        return prod

    # =========================================================================
    # POSITIVE PATH: COMMERCIAL PURCHASE JOURNEY & FEFO ALLOCATION
    # =========================================================================

    def test_01_full_positive_purchase_journey_with_fefo_allocation(self):
        """
        Luồng mua hàng thành công hoàn chỉnh:
        1. Sản phẩm SALE_ELIGIBLE có nhiều SKU.
        2. Chọn SKU hộp (45,000đ).
        3. Có 2 lô ACTIVE: Lô A (hạn 30 ngày, 20 hộp) và Lô B (hạn 180 ngày, 50 hộp).
        4. Kiểm tra tồn khả dụng = 70 hộp, cta_type='BUY_NOW'.
        5. Đặt mua 15 hộp qua /store/orders/checkout.
        6. FEFO cấp phát 100% từ Lô A (hạn gần nhất).
        7. Tồn kho Lô A giảm còn 5 hộp, Lô B còn nguyên 50 hộp.
        8. Đơn hàng được tạo thành công với mã định danh rõ ràng.
        """
        pid = 99901
        today = date.today()
        prod = self._create_isolated_product(pid, "Paracetamol 500mg Chuẩn Thương Mại", "SALE_ELIGIBLE")

        # Tạo SKU 1: Hộp
        sku_box = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-PARA-COMM-BOX",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("45000.0"),
            is_default=True,
            is_active=True,
        )
        # Tạo SKU 2: Vỉ
        sku_blister = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-PARA-COMM-BLISTER",
            uom="Vỉ",
            conversion_rate=10,
            base_price=Decimal("5000.0"),
            is_default=False,
            is_active=True,
        )
        self.db.add_all([sku_box, sku_blister])
        self.db.commit()
        self.db.refresh(sku_box)
        self.db.refresh(sku_blister)

        # Tạo Lô A: Hạn 200 ngày (Gần hạn hơn -> FEFO ưu tiên)
        batch_a = InventoryBatch(
            sku_id=sku_box.id,
            batch_number="LOT-COMM-EXP-EARLY",
            expiry_date=today + timedelta(days=200),
            initial_quantity=20,
            status=BatchStatus.ACTIVE,
        )
        # Tạo Lô B: Hạn 400 ngày (Xa hạn hơn)
        batch_b = InventoryBatch(
            sku_id=sku_box.id,
            batch_number="LOT-COMM-EXP-LATER",
            expiry_date=today + timedelta(days=400),
            initial_quantity=50,
            status=BatchStatus.ACTIVE,
        )
        self.db.add_all([batch_a, batch_b])
        self.db.commit()
        self.db.refresh(batch_a)
        self.db.refresh(batch_b)

        # Nhập tồn kho vật lý
        stock_a = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch_a.id,
            quantity_on_hand=20,
            quantity_reserved=0,
            quantity_available=20,
        )
        stock_b = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch_b.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        )
        self.db.add_all([stock_a, stock_b])
        self.db.commit()

        # BƯỚC 1: Thẩm định điều kiện bán hàng
        eligibility = ProductEligibilityService.evaluate_product_eligibility(prod, self.db, sku_id=sku_box.id)
        self.assertTrue(eligibility.is_eligible_for_sale)
        self.assertTrue(eligibility.can_add_to_cart)
        self.assertEqual(eligibility.eligibility_tier, "SALE_ELIGIBLE")
        self.assertEqual(eligibility.cta_type, "BUY_NOW")
        self.assertEqual(eligibility.available_stock, 70)
        self.assertEqual(eligibility.selected_sku["uom"], "Hộp")
        self.assertEqual(eligibility.selected_sku["base_price"], 45000)

        # BƯỚC 2: Đặt mua 15 hộp
        payload = {
            "customer_name": "Nguyễn Văn Thương Mại",
            "customer_phone": "0987654321",
            "customer_email": "thuongmai@example.com",
            "shipping_address": "123 Đường Cộng Hòa, Phường 13, Quận Tân Bình, TP. Hồ Chí Minh",
            "shipping_city": "Hồ Chí Minh",
            "province_code": "79",
            "ward_code": "26965",
            "lat": 10.7985,
            "lng": 106.6540,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": pid, "quantity": 15}],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertIn("order_code", data)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(len(data["fulfillments"]), 1)

        # BƯỚC 3: Đối soát FEFO Allocation trong Database
        allocations = (
            self.db.query(OrderItemBatchAllocation)
            .join(InventoryBatch, InventoryBatch.id == OrderItemBatchAllocation.batch_id)
            .filter(InventoryBatch.sku_id == sku_box.id)
            .all()
        )
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0].batch_id, batch_a.id)
        self.assertEqual(allocations[0].allocated_quantity, 15)

        # BƯỚC 4: Kiểm tra tồn kho sau khi xuất
        self.db.refresh(stock_a)
        self.db.refresh(stock_b)
        self.assertEqual(stock_a.quantity_available, 5) # 20 - 15 = 5
        self.assertEqual(stock_a.quantity_reserved, 15)
        self.assertEqual(stock_b.quantity_available, 50) # Nguyên vẹn
        self.assertEqual(stock_b.quantity_reserved, 0)

        # BƯỚC 5: Thẩm định lại tồn kho khả dụng mới
        elig_after = ProductEligibilityService.evaluate_product_eligibility(prod, self.db, sku_id=sku_box.id)
        self.assertEqual(elig_after.available_stock, 55)

    # =========================================================================
    # NEGATIVE PATHS: COMMERCIAL SAFETY GATES & REJECTIONS
    # =========================================================================

    def test_02_reject_prescription_rx_medicine_online(self):
        """Thuốc kê đơn (Rx) phải bị chặn tuyệt đối cả ở eligibility lẫn checkout API."""
        pid = 99902
        prod = self._create_isolated_product(
            pid, "Amoxicillin 500mg Kê Đơn", "SALE_ELIGIBLE", rx_status=RxOtcStatus.PRESCRIPTION
        )
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-AMOX-RX",
            uom="Hộp",
            base_price=Decimal("80000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()

        # 1. Eligibility check
        elig = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertFalse(elig.is_eligible_for_sale)
        self.assertFalse(elig.can_add_to_cart)
        self.assertEqual(elig.eligibility_tier, "PRESCRIPTION_RESTRICTED")
        self.assertEqual(elig.cta_type, "RX_PRESCRIPTION")

        # 2. Checkout API attempt must return HTTP 400
        payload = {
            "customer_name": "Khách Thử Mua Rx",
            "customer_phone": "0987654321",
            "shipping_address": "123 Đường Cộng Hòa, Phường 13, Quận Tân Bình, TP. Hồ Chí Minh",
            "province_code": "79",
            "ward_code": "26965",
            "lat": 10.7985,
            "lng": 106.6540,
            "is_verified": True,
            "items": [{"product_id": pid, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("thuốc kê đơn", resp.json()["detail"].lower())

    def test_03_reject_reference_only_product_from_cart(self):
        """Sản phẩm REFERENCE_ONLY chỉ cho tra cứu dược lý, không cho thêm vào giỏ và bị từ chối khi đặt hàng."""
        pid = 99903
        prod = self._create_isolated_product(pid, "Dược Phẩm Tra Cứu Tham Khảo", "REFERENCE_ONLY")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-REF-ONLY",
            uom="Chai",
            base_price=Decimal("50000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()

        elig = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertFalse(elig.is_eligible_for_sale)
        self.assertFalse(elig.can_add_to_cart)
        self.assertEqual(elig.eligibility_tier, "REFERENCE_ONLY")
        self.assertEqual(elig.cta_type, "CONSULT_PHARMACIST")

        payload = {
            "customer_name": "Khách Mua Hàng Tham Khảo",
            "customer_phone": "0987654321",
            "shipping_address": "123 Đường Cộng Hòa, Phường 13, Quận Tân Bình, TP. Hồ Chí Minh",
            "province_code": "79",
            "ward_code": "26965",
            "lat": 10.7985,
            "lng": 106.6540,
            "is_verified": True,
            "items": [{"product_id": pid, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("tham khảo", resp.json()["detail"].lower())

    def test_04_reject_internal_test_product(self):
        """Sản phẩm thử nghiệm INTERNAL_TEST bị khóa hoàn toàn khỏi giỏ hàng và checkout."""
        pid = 99904
        prod = self._create_isolated_product(pid, "Thuốc Thử Nghiệm Mock Sandbox", "INTERNAL_TEST")

        elig = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertFalse(elig.is_eligible_for_sale)
        self.assertFalse(elig.can_add_to_cart)
        self.assertEqual(elig.eligibility_tier, "INTERNAL_TEST")
        self.assertEqual(elig.cta_type, "LOCKED")

    def test_05_reject_out_of_stock_product(self):
        """Sản phẩm SALE_ELIGIBLE nhưng không có tồn kho khả dụng thì cta_type='OUT_OF_STOCK'."""
        pid = 99905
        prod = self._create_isolated_product(pid, "Sản Phẩm Tạm Hết Hàng", "SALE_ELIGIBLE")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-OOS-TEST",
            uom="Hộp",
            base_price=Decimal("30000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()

        elig = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertFalse(elig.is_eligible_for_sale)
        self.assertFalse(elig.can_add_to_cart)
        self.assertEqual(elig.eligibility_tier, "OUT_OF_STOCK")
        self.assertEqual(elig.cta_type, "OUT_OF_STOCK")
        self.assertEqual(elig.available_stock, 0)

    def test_06_expired_batch_excluded_from_stock_and_fefo(self):
        """Lô hàng hết hạn (expiry_date <= today) tuyệt đối không được tính vào tồn khả dụng."""
        pid = 99906
        today = date.today()
        prod = self._create_isolated_product(pid, "Thuốc Có Lô Hết Hạn", "SALE_ELIGIBLE")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-EXP-BATCH",
            uom="Hộp",
            base_price=Decimal("30000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        self.db.refresh(sku)

        # Lô hết hạn 5 ngày trước với tồn 100
        batch_exp = InventoryBatch(
            sku_id=sku.id,
            batch_number="LOT-ALREADY-EXPIRED",
            expiry_date=today - timedelta(days=5),
            initial_quantity=100,
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch_exp)
        self.db.commit()
        self.db.refresh(batch_exp)

        stock = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch_exp.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            quantity_available=100,
        )
        self.db.add(stock)
        self.db.commit()

        elig = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertEqual(elig.available_stock, 0) # Lô hết hạn bị loại hoàn toàn!
        self.assertEqual(elig.eligibility_tier, "OUT_OF_STOCK")

    def test_07_quarantined_batch_excluded_from_stock_and_fefo(self):
        """Lô hàng đang bị cách ly (status=QUARANTINED) tuyệt đối không được bán."""
        pid = 99907
        today = date.today()
        prod = self._create_isolated_product(pid, "Thuốc Có Lô Đang Cách Ly", "SALE_ELIGIBLE")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-QUARANTINE-BATCH",
            uom="Hộp",
            base_price=Decimal("40000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        self.db.refresh(sku)

        # Lô còn hạn 1 năm nhưng bị QUARANTINED
        batch_quar = InventoryBatch(
            sku_id=sku.id,
            batch_number="LOT-UNDER-QUARANTINE",
            expiry_date=today + timedelta(days=365),
            initial_quantity=80,
            status=BatchStatus.QUARANTINED,
        )
        self.db.add(batch_quar)
        self.db.commit()
        self.db.refresh(batch_quar)

        stock = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch_quar.id,
            quantity_on_hand=80,
            quantity_reserved=0,
            quantity_available=80,
        )
        self.db.add(stock)
        self.db.commit()

        elig = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertEqual(elig.available_stock, 0) # Lô cách ly bị loại hoàn toàn!
        self.assertEqual(elig.eligibility_tier, "OUT_OF_STOCK")

    def test_08_invalid_price_or_missing_sku_rejected(self):
        """Sản phẩm thiếu SKU hoặc có giá bán <= 0 bị gắn nhãn UNVERIFIED_DATA và khóa mua."""
        pid = 99908
        prod = self._create_isolated_product(pid, "Thuốc Thiếu Giá Bán", "SALE_ELIGIBLE")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-ZERO-PRICE",
            uom="Hộp",
            base_price=Decimal("0.0"), # Giá 0đ không hợp lệ
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()

        elig = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertFalse(elig.is_eligible_for_sale)
        self.assertFalse(elig.can_add_to_cart)
        self.assertEqual(elig.eligibility_tier, "UNVERIFIED_DATA")
        self.assertEqual(elig.cta_type, "LOCKED")


if __name__ == "__main__":
    unittest.main()
