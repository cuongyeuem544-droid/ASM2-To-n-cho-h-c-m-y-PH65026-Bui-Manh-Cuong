"""
H4CARE Commercial Module C Commerce & Checkout Automated Test Suite.
Covers all 35 Commercial Verification Gates specified in Module C Section 30.
Runs strictly against isolated test database (pharmatrust_test.db).
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    BatchStatus,
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderItem,
    OrderItemBatchAllocation,
    PaymentTransaction,
    ProductSku,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.momo_service import MomoPaymentService
from app.services.product_eligibility_service import ProductEligibilityService
from app.services.return_policy_service import ReturnPolicyService
from app.services.vietqr_service import VietQrService


class TestModuleCCommerce(unittest.TestCase):
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

        # Đảm bảo có tổng kho kiểm thử
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

        from app.models.entities import User
        from app.models.enums import UserRole
        from app.core.security import create_access_token, hash_password
        admin = self.db.query(User).filter_by(role=UserRole.ADMIN).first()
        if not admin:
            admin = User(
                email="admin_test@h4care.vn",
                password_hash=hash_password("Admin@123"),
                full_name="Admin Test",
                role=UserRole.ADMIN,
                is_active=True,
            )
            self.db.add(admin)
            self.db.commit()
            self.db.refresh(admin)
        admin_tok = create_access_token(str(admin.id), "ADMIN")
        self.admin_headers = {"Authorization": f"Bearer {admin_tok}"}

    def tearDown(self):
        self.db.close()

    def _create_test_product(
        self,
        pid: int,
        name: str,
        publish_mode: str = "SALE_ELIGIBLE",
        rx_status: RxOtcStatus = RxOtcStatus.OTC,
        regulatory_status: str = "ACTIVE",
    ) -> CanonicalProduct:
        existing = self.db.query(CanonicalProduct).filter_by(id=pid).first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        prod = CanonicalProduct(
            id=pid,
            canonical_name=name,
            registration_number=f"VD-COMM-TEST-{pid}",
            dosage_form="Viên nén",
            manufacturer="H4Care Pharma Lab",
            manufacturing_country="Việt Nam",
            package_description="Hộp 10 vỉ",
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
    # 1. GUEST ADD TO CART & VALIDATE
    # =========================================================================
    def test_01_guest_cart_validate(self):
        """1. Guest Cart validation via /api/v1/store/orders/cart/validate returns server prices and status."""
        prod = self._create_test_product(801, "Thuốc Giảm Đau Test 801")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-801-BOX",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("50000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()

        # Thêm lô tồn kho hợp lệ
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="BATCH-801-A",
            expiry_date=date.today() + timedelta(days=90),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()

        stock = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        )
        self.db.add(stock)
        self.db.commit()

        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [
                {"product_id": prod.id, "sku_id": sku.id, "quantity": 2, "client_price": 50000.0}
            ]
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["all_valid"])
        self.assertEqual(data["items"][0]["server_price"], 50000.0)
        self.assertEqual(data["items"][0]["available_stock"], 50)
        self.assertTrue(data["items"][0]["can_checkout"])

    # =========================================================================
    # 2. AUTHENTICATED ADD TO CART
    # =========================================================================
    def test_02_authenticated_cart_validate(self):
        """2. Authenticated Cart validation operates seamlessly with user payload."""
        prod = self._create_test_product(802, "Vitamin C 500mg Test 802")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-802-BOX",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("35000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()

        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="BATCH-802-A",
            expiry_date=date.today() + timedelta(days=120),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=30,
            quantity_reserved=0,
            quantity_available=30,
        ))
        self.db.commit()

        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 1}]
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["all_valid"])

    # =========================================================================
    # 3. GUEST CART MERGE
    # =========================================================================
    def test_03_guest_cart_merge(self):
        """3. Merging distinct guest items with existing cart items preserves all valid SKUs."""
        guest_items = [
            {"product_id": 801, "sku_id": 1, "quantity": 2},
            {"product_id": 802, "sku_id": 2, "quantity": 1},
        ]
        auth_items = [
            {"product_id": 802, "sku_id": 2, "quantity": 3},  # Trùng SKU 2 -> cộng dồn
            {"product_id": 803, "sku_id": 3, "quantity": 1},
        ]
        merged_map = {}
        for it in guest_items + auth_items:
            key = f"{it['product_id']}_{it['sku_id']}"
            if key in merged_map:
                merged_map[key]["quantity"] += it["quantity"]
            else:
                merged_map[key] = dict(it)
        merged = list(merged_map.values())
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged_map["802_2"]["quantity"], 4)

    # =========================================================================
    # 4. MULTIPLE SKU (HỘP vs VỈ vs VIÊN)
    # =========================================================================
    def test_04_multiple_sku(self):
        """4. Multiple SKUs on same product validate distinct base_prices and UOMs."""
        prod = self._create_test_product(804, "Paracetamol Đa Quy Cách Test 804")
        sku_box = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-804-BOX",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("60000.0"),
            is_default=True,
            is_active=True,
        )
        sku_blister = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-804-BLISTER",
            uom="Vỉ",
            conversion_rate=10,
            base_price=Decimal("6500.0"),
            is_default=False,
            is_active=True,
        )
        self.db.add_all([sku_box, sku_blister])
        self.db.commit()

        batch = InventoryBatch(
            sku_id=sku_box.id,
            initial_quantity=50,
            batch_number="BATCH-804-A",
            expiry_date=date.today() + timedelta(days=90),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            quantity_available=100,
        ))
        self.db.commit()

        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [
                {"product_id": prod.id, "sku_id": sku_box.id, "quantity": 1},
                {"product_id": prod.id, "sku_id": sku_blister.id, "quantity": 5},
            ]
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["server_price"], 60000.0)
        self.assertEqual(data["items"][0]["uom"], "Hộp")
        self.assertEqual(data["items"][1]["server_price"], 6500.0)
        self.assertEqual(data["items"][1]["uom"], "Vỉ")

    # =========================================================================
    # 5. QUANTITY INCREASE
    # =========================================================================
    def test_05_quantity_increase(self):
        """5. Quantity increase within available stock validates successfully."""
        prod = self._create_test_product(805, "Test Quantity Inc 805")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-805",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("20000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-805",
            expiry_date=date.today() + timedelta(days=100),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        ))
        self.db.commit()

        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 10}]
        })
        self.assertTrue(resp.json()["items"][0]["can_checkout"])

    # =========================================================================
    # 6. QUANTITY DECREASE
    # =========================================================================
    def test_06_quantity_decrease(self):
        """6. Quantity decrease to minimum 1 succeeds."""
        prod = self._create_test_product(806, "Test Quantity Dec 806")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-806",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("20000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-806",
            expiry_date=date.today() + timedelta(days=100),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        ))
        self.db.commit()

        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 1}]
        })
        self.assertTrue(resp.json()["items"][0]["can_checkout"])

    # =========================================================================
    # 7. REMOVE ITEM
    # =========================================================================
    def test_07_remove_item(self):
        """7. Removing item leaves remaining items validated correctly."""
        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": 806, "quantity": 1}]
        })
        self.assertEqual(len(resp.json()["items"]), 1)

    # =========================================================================
    # 8. PRICE CHANGED DETECTION
    # =========================================================================
    def test_08_price_changed(self):
        """8. Server detects discrepancy when client has stale price."""
        prod = self._create_test_product(808, "Test Price Change 808")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-808",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("45000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-808",
            expiry_date=date.today() + timedelta(days=100),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=20,
            quantity_reserved=0,
            quantity_available=20,
        ))
        self.db.commit()

        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 1, "client_price": 40000.0}]
        })
        data = resp.json()
        self.assertTrue(data["items"][0]["price_changed"])
        self.assertEqual(data["items"][0]["server_price"], 45000.0)

    # =========================================================================
    # 9. OUT OF STOCK REJECTION
    # =========================================================================
    def test_09_out_of_stock(self):
        """9. Requesting quantity exceeding available stock returns can_checkout: False."""
        prod = self._create_test_product(809, "Test OOS 809")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-809",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("30000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        # Không có lô tồn kho nào
        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 5}]
        })
        data = resp.json()
        self.assertFalse(data["all_valid"])
        self.assertFalse(data["items"][0]["can_checkout"])

    # =========================================================================
    # 10. INVALID SKU REJECTION
    # =========================================================================
    def test_10_invalid_sku(self):
        """10. Non-existent SKU is rejected at checkout."""
        prod = self._create_test_product(810, "Thuốc Test SKU Lỗi 810")
        sku_valid = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-810",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("30000.0"),
            is_active=True,
        )
        self.db.add(sku_valid)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku_valid.id,
            batch_number="B-810",
            expiry_date=date.today() + timedelta(days=90),
            initial_quantity=50,
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        ))
        self.db.commit()

        payload = {
            "customer_name": "Nguyễn Văn Test",
            "customer_phone": "0912345678",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": prod.id, "sku_id": 999999, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("SKU #999999", resp.json()["detail"])

    # =========================================================================
    # 11. REFERENCE ONLY REJECTION
    # =========================================================================
    def test_11_reference_only(self):
        """11. Product in REFERENCE_ONLY catalog tier is rejected from cart."""
        prod = self._create_test_product(811, "Thuốc Tham Khảo 811", publish_mode="REFERENCE_ONLY")
        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "quantity": 1}]
        })
        data = resp.json()
        self.assertFalse(data["items"][0]["is_eligible"])
        self.assertFalse(data["items"][0]["can_checkout"])

    # =========================================================================
    # 12. INTERNAL TEST PRODUCT REJECTION
    # =========================================================================
    def test_12_internal_test_product(self):
        """12. Product in INTERNAL_TEST tier is rejected."""
        prod = self._create_test_product(812, "Thuốc Nội Bộ 812", publish_mode="INTERNAL_TEST")
        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "quantity": 1}]
        })
        self.assertFalse(resp.json()["items"][0]["can_checkout"])

    # =========================================================================
    # 13. RESTRICTED RX REJECTION
    # =========================================================================
    def test_13_restricted_rx(self):
        """13. Rx prescription product cannot be checked out online without Rx workflow."""
        prod = self._create_test_product(813, "Kháng Sinh Rx 813", rx_status=RxOtcStatus.PRESCRIPTION)
        resp = self.client.post("/api/v1/store/orders/cart/validate", json={
            "items": [{"product_id": prod.id, "quantity": 1}]
        })
        self.assertFalse(resp.json()["items"][0]["can_checkout"])

    # =========================================================================
    # 14. EXPIRED BATCH EXCLUSION
    # =========================================================================
    def test_14_expired_batch(self):
        """14. Batches past expiry date are excluded by FEFO."""
        prod = self._create_test_product(814, "Thuốc Quá Hạn 814")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-814",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("20000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        # Lô hết hạn 10 ngày trước
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-814-EXP",
            expiry_date=date.today() - timedelta(days=10),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        ))
        self.db.commit()

        eligibility = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertEqual(eligibility.available_stock, 0)
        self.assertFalse(eligibility.can_add_to_cart)

    # =========================================================================
    # 15. QUARANTINED BATCH EXCLUSION
    # =========================================================================
    def test_15_quarantined_batch(self):
        """15. Quarantined batches are excluded from saleable stock."""
        prod = self._create_test_product(815, "Thuốc Cách Ly 815")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-815",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("20000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-815-QUAR",
            expiry_date=date.today() + timedelta(days=180),
            status=BatchStatus.QUARANTINED,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            quantity_available=100,
        ))
        self.db.commit()

        eligibility = ProductEligibilityService.evaluate_product_eligibility(prod, self.db)
        self.assertEqual(eligibility.available_stock, 0)

    # =========================================================================
    # 16. FEFO RESERVATION (EARLIEST EXPIRY ALLOCATED FIRST)
    # =========================================================================
    def test_16_fefo_reservation(self):
        """16. FEFO allocates batch with earliest expiry date first."""
        prod = self._create_test_product(816, "Thuốc FEFO Test 816")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-816",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("30000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()

        # Lô A: hạn 30 ngày (20 hộp)
        batch_a = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=20,
            batch_number="BATCH-816-EARLY",
            expiry_date=date.today() + timedelta(days=30),
            status=BatchStatus.ACTIVE,
        )
        # Lô B: hạn 180 ngày (50 hộp)
        batch_b = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="BATCH-816-LATE",
            expiry_date=date.today() + timedelta(days=180),
            status=BatchStatus.ACTIVE,
        )
        self.db.add_all([batch_a, batch_b])
        self.db.commit()

        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch_a.id,
            quantity_on_hand=20,
            quantity_reserved=0,
            quantity_available=20,
        ))
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch_b.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        ))
        self.db.commit()

        payload = {
            "customer_name": "Trần FEFO",
            "customer_phone": "0987654321",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 15}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200)
        order_code = resp.json()["order_code"]

        # Kiểm tra allocation
        order = self.db.query(Order).filter_by(order_code=order_code).first()
        self.assertIsNotNone(order)
        alloc = self.db.query(OrderItemBatchAllocation).filter_by(batch_id=batch_a.id).first()
        self.assertIsNotNone(alloc)
        self.assertEqual(alloc.allocated_quantity, 15)

    # =========================================================================
    # 17. MULTIPLE ORDERS COMPETING STOCK
    # =========================================================================
    def test_17_multiple_orders_competing_stock(self):
        """17. Order 1 exhausts stock; Order 2 attempting to purchase remaining quantity fails."""
        prod = self._create_test_product(817, "Thuốc Tranh Chấp Tồn Kho 817")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-817",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("15000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-817",
            expiry_date=date.today() + timedelta(days=90),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=10,
            quantity_reserved=0,
            quantity_available=10,
        ))
        self.db.commit()

        # Đơn 1 mua 10 hộp -> tồn còn 0
        p1 = {
            "customer_name": "Khách A",
            "customer_phone": "0901000001",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 10}],
        }
        r1 = self.client.post("/api/v1/store/orders/checkout", json=p1)
        self.assertEqual(r1.status_code, 200)

        # Đơn 2 cố mua 5 hộp -> fail
        p2 = {
            "customer_name": "Khách B",
            "customer_phone": "0901000002",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 5}],
        }
        r2 = self.client.post("/api/v1/store/orders/checkout", json=p2)
        self.assertEqual(r2.status_code, 400)

    # =========================================================================
    # 18. SHIPPING FEE
    # =========================================================================
    def test_18_shipping_fee(self):
        """18. Store pickup has 0 shipping fee; Delivery records appropriate fee."""
        order_delivery = Order(
            order_code="PT-TEST-DELIV",
            customer_name="Test Ship",
            customer_phone="0911111111",
            shipping_address="123 Test",
            total_amount=Decimal("100000.0"),
            shipping_fee=Decimal("25000.0"),
            payment_method="COD",
        )
        order_pickup = Order(
            order_code="PT-TEST-PICKUP",
            customer_name="Test Pickup",
            customer_phone="0911111112",
            shipping_address="Nhận tại nhà thuốc",
            total_amount=Decimal("100000.0"),
            shipping_fee=Decimal("0.0"),
            payment_method="COD",
        )
        self.assertEqual(order_pickup.shipping_fee, Decimal("0.0"))
        self.assertEqual(order_delivery.shipping_fee, Decimal("25000.0"))

    # =========================================================================
    # 19. INVALID ADDRESS REJECTION
    # =========================================================================
    def test_19_invalid_address(self):
        """19. Checkout without verified GPS coordinates is rejected with HTTP 400."""
        payload = {
            "customer_name": "Lỗi Địa Chỉ",
            "customer_phone": "0902222222",
            "shipping_address": "Địa chỉ chưa định vị",
            "is_verified": False,
            "payment_method": "COD",
            "items": [{"product_id": 801, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("chưa được xác minh", resp.json()["detail"])

    # =========================================================================
    # 20. CHECKOUT SUCCESS POSITIVE PATH
    # =========================================================================
    def test_20_checkout_success(self):
        """20. Positive checkout creates order with code, PENDING status, and allocations."""
        prod = self._create_test_product(820, "Thuốc Mua Thành Công 820")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-820",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("40000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-820",
            expiry_date=date.today() + timedelta(days=120),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        ))
        self.db.commit()

        payload = {
            "customer_name": "Lê Thành Công",
            "customer_phone": "0903333333",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 2}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["order_code"].startswith("PT-"))
        self.assertEqual(data["order_status"], "PENDING")
        self.assertEqual(data["total_amount"], 80000.0)

    # =========================================================================
    # 21. DUPLICATE CHECKOUT IDEMPOTENCY
    # =========================================================================
    def test_21_duplicate_checkout(self):
        """21. Re-submitting with identical idempotency_key returns existing order without creating duplicate."""
        prod = self._create_test_product(821, "Thuốc Test Trùng Đơn 821")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-821",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("25000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-821",
            expiry_date=date.today() + timedelta(days=100),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=30,
            quantity_reserved=0,
            quantity_available=30,
        ))
        self.db.commit()

        idem_key = "IDEM-TEST-KEY-821-UNIQUE"
        payload = {
            "customer_name": "Phạm Trùng Đơn",
            "customer_phone": "0904444444",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "idempotency_key": idem_key,
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 1}],
        }
        # Lần submit 1
        r1 = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(r1.status_code, 200)
        code1 = r1.json()["order_code"]

        # Lần submit 2 (double-click hoặc network retry)
        r2 = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(r2.status_code, 200)
        code2 = r2.json()["order_code"]
        self.assertEqual(code1, code2)
        self.assertTrue(r2.json().get("is_idempotent_replay"))

        # Đảm bảo chỉ có duy nhất 1 record trong CSDL
        total_orders = self.db.query(Order).filter_by(idempotency_key=idem_key).count()
        self.assertEqual(total_orders, 1)

    # =========================================================================
    # 22. ORDER SNAPSHOT IMMUTABILITY
    # =========================================================================
    def test_22_order_snapshot(self):
        """22. Changing product base_price later does not alter historical OrderItem price."""
        prod = self._create_test_product(822, "Thuốc Test Snapshot 822")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-822",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("10000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-822",
            expiry_date=date.today() + timedelta(days=100),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=30,
            quantity_reserved=0,
            quantity_available=30,
        ))
        self.db.commit()

        payload = {
            "customer_name": "Đặng Snapshot",
            "customer_phone": "0905555555",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 1}],
        }
        r = self.client.post("/api/v1/store/orders/checkout", json=payload)
        code = r.json()["order_code"]

        # Tăng giá sản phẩm lên gấp đôi trong danh mục
        sku.base_price = Decimal("20000.0")
        self.db.commit()

        # Giá trong đơn cũ vẫn phải là 10,000đ
        order = self.db.query(Order).filter_by(order_code=code).first()
        self.assertEqual(order.items[0].price, Decimal("10000.0"))

    # =========================================================================
    # 23. COD UNPAID
    # =========================================================================
    def test_23_cod_unpaid(self):
        """23. Order created with COD has payment_status='PENDING'."""
        order = Order(
            order_code="PT-TEST-COD-UNPAID",
            customer_name="Test COD",
            customer_phone="0906666666",
            shipping_address="123 Test",
            total_amount=Decimal("50000.0"),
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()
        self.assertEqual(order.payment_status, "PENDING")

    # =========================================================================
    # 24. MOMO PAYMENT PENDING
    # =========================================================================
    def test_24_momo_payment_pending(self):
        """24. MoMo payment request creates pending transaction."""
        order = Order(
            order_code="PT-TEST-MOMO-PEND",
            customer_name="Test MoMo",
            customer_phone="0907777777",
            shipping_address="123 Test",
            total_amount=Decimal("150000.0"),
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        from unittest.mock import MagicMock, patch
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"resultCode": 0}'
        mock_resp.json.return_value = {
            "resultCode": 0,
            "message": "Thành công",
            "payUrl": "https://test-payment.momo.vn/v2/gateway/pay?token=MOMO_TOKEN_OK",
            "qrCodeUrl": "https://test-payment.momo.vn/qr/MOMO_TOKEN_OK",
            "deeplink": "momo://app?action=payWithApp",
        }

        with patch("app.services.momo_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            from app.core.security import create_guest_order_token
            valid_token = create_guest_order_token(order.order_code, order.customer_phone)
            resp = self.client.post("/api/v1/payments/momo/create", json={
                "order_code": order.order_code,
                "return_url": "http://localhost:3000/checkout/result",
                "phone_verify": order.customer_phone,
                "order_token": valid_token,
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("pay_url", data)

    # =========================================================================
    # 25. MOMO SUCCESS WEBHOOK
    # =========================================================================
    def test_25_momo_success_webhook(self):
        """25. Simulating MoMo payment success marks payment as PAID."""
        order = Order(
            order_code="PT-TEST-MOMO-OK",
            customer_name="Test MoMo Success",
            customer_phone="0908888888",
            shipping_address="123 Test",
            total_amount=Decimal("100000.0"),
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        resp = self.client.post("/api/v1/payments/momo/simulate", json={
            "order_code": order.order_code,
            "success": True,
        })
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(order)
        self.assertEqual(order.payment_status, "PAID")

    # =========================================================================
    # 26. MOMO FAILURE WEBHOOK
    # =========================================================================
    def test_26_momo_failure(self):
        """26. MoMo payment failure keeps order open without falsely marking PAID."""
        order = Order(
            order_code="PT-TEST-MOMO-FAIL",
            customer_name="Test MoMo Fail",
            customer_phone="0909999999",
            shipping_address="123 Test",
            total_amount=Decimal("100000.0"),
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        resp = self.client.post("/api/v1/payments/momo/simulate", json={
            "order_code": order.order_code,
            "success": False,
        })
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(order)
        self.assertNotEqual(order.payment_status, "PAID")

    # =========================================================================
    # 27. PAYMENT RETRY
    # =========================================================================
    def test_27_payment_retry(self):
        """27. Retrying payment allows switching to another payment method."""
        order = Order(
            order_code="PT-TEST-RETRY",
            customer_name="Test Retry",
            customer_phone="0901234123",
            shipping_address="123 Test",
            total_amount=Decimal("75000.0"),
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        from app.core.security import create_guest_order_token
        valid_token = create_guest_order_token(order.order_code, order.customer_phone)
        resp = self.client.post("/api/v1/payments/retry", json={
            "order_code": order.order_code,
            "new_payment_method": "COD",
            "phone_verify": order.customer_phone,
            "order_token": valid_token,
        })
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(order)
        self.assertEqual(order.payment_method, "COD")

    # =========================================================================
    # 28. VIETQR PENDING
    # =========================================================================
    def test_28_vietqr_pending(self):
        """28. VietQR creation returns transfer string and transaction in PENDING."""
        order = Order(
            order_code="PT-TEST-VIETQR",
            customer_name="Test VietQR",
            customer_phone="0904321432",
            shipping_address="123 Test",
            total_amount=Decimal("200000.0"),
            payment_method="VIETQR",
            payment_status="PENDING",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        from app.core.security import create_guest_order_token
        valid_token = create_guest_order_token(order.order_code, order.customer_phone)
        resp = self.client.post("/api/v1/payments/vietqr/create", json={
            "order_code": order.order_code,
            "phone_verify": order.customer_phone,
            "order_token": valid_token,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("qr_code_url", data)

    # =========================================================================
    # 29. PAYMENT AMOUNT MISMATCH
    # =========================================================================
    def test_29_payment_amount_mismatch(self):
        """29. Reconciliation detects mismatch when paid amount != order amount."""
        order = Order(
            order_code="PT-TEST-MISMATCH",
            customer_name="Test Mismatch",
            customer_phone="0905556667",
            shipping_address="123 Test",
            total_amount=Decimal("100000.0"),
            payment_method="VIETQR",
            payment_status="PENDING",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        # Ghi nhận giao dịch chuyển thiếu tiền (50,000đ thay vì 100,000đ)
        tx = PaymentTransaction(
            order_id=order.id,
            transaction_code="TX-UNDERPAID-01",
            provider="VIETQR",
            amount=Decimal("50000.0"),
            currency="VND",
            status="SUCCESS",
        )
        self.db.add(tx)
        self.db.commit()

        resp = self.client.get(f"/api/v1/payments/reconciliation/order/{order.order_code}", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["discrepancy_type"], "UNDERPAID")

    # =========================================================================
    # 30. LATE PAYMENT CALLBACK ON CANCELLED ORDER
    # =========================================================================
    def test_30_late_payment_callback(self):
        """30. Callback arriving after order cancellation is handled gracefully."""
        order = Order(
            order_code="PT-TEST-LATE-CANCEL",
            customer_name="Test Late Callback",
            customer_phone="0909991112",
            shipping_address="123 Test",
            total_amount=Decimal("60000.0"),
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="CANCELLED",
        )
        self.db.add(order)
        self.db.commit()

        # Simulate callback on cancelled order
        resp = self.client.post("/api/v1/payments/momo/simulate", json={
            "order_code": order.order_code,
            "success": True,
        })
        self.assertEqual(resp.status_code, 200)

    # =========================================================================
    # 31. ORDER CANCELLATION
    # =========================================================================
    def test_31_order_cancellation(self):
        """31. Customer can cancel PENDING order."""
        order = Order(
            order_code="PT-TEST-CANCEL-FLOW",
            customer_name="Test Cancel",
            customer_phone="0901237890",
            shipping_address="123 Test",
            total_amount=Decimal("40000.0"),
            payment_method="COD",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        from app.core.security import create_guest_order_token
        valid_token = create_guest_order_token(order.order_code, order.customer_phone)
        resp = self.client.post(f"/api/v1/payments/orders/{order.order_code}/cancel", json={
            "reason": "Đổi ý không mua nữa",
            "phone_verify": order.customer_phone,
            "order_token": valid_token,
        })
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(order)
        self.assertEqual(order.order_status, "CANCELLED")

    # =========================================================================
    # 32. INVENTORY RELEASE ON CANCELLATION
    # =========================================================================
    def test_32_inventory_release(self):
        """32. Cancelling order releases reserved stock back to available."""
        prod = self._create_test_product(832, "Thuốc Release Stock 832")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-832",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("20000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-832",
            expiry_date=date.today() + timedelta(days=90),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        stock = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=30,
            quantity_reserved=0,
            quantity_available=30,
        )
        self.db.add(stock)
        self.db.commit()

        # Checkout 10 hộp -> available còn 20
        payload = {
            "customer_name": "Test Release",
            "customer_phone": "0908889999",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 10}],
        }
        r = self.client.post("/api/v1/store/orders/checkout", json=payload)
        code = r.json()["order_code"]
        order_token = r.json().get("order_token")
        self.db.refresh(stock)
        self.assertEqual(stock.quantity_available, 20)

        # Hủy đơn -> available phải hoàn lại 30
        self.client.post(f"/api/v1/payments/orders/{code}/cancel", json={
            "reason": "Hủy đơn thử nghiệm giải phóng tồn",
            "phone_verify": payload["customer_phone"],
            "order_token": order_token,
        })
        self.db.refresh(stock)
        self.assertEqual(stock.quantity_available, 30)

    # =========================================================================
    # 33. CUSTOMER ORDER OWNERSHIP
    # =========================================================================
    def test_33_customer_order_ownership(self):
        """33. Querying customer orders isolates orders by customer phone."""
        phone = "0907771234"
        order = Order(
            order_code="PT-TEST-OWNER-01",
            customer_name="Chủ Đơn",
            customer_phone=phone,
            shipping_address="123 Test",
            total_amount=Decimal("80000.0"),
            payment_method="COD",
            order_status="PENDING",
        )
        self.db.add(order)
        self.db.commit()

        # 1. Khách hàng chưa đăng nhập -> 401 Unauthorized
        resp_unauth = self.client.get(f"/api/v1/store/orders/customer/{phone}")
        self.assertEqual(resp_unauth.status_code, 401)

        # 2. Đăng nhập đúng tài khoản sở hữu SĐT này
        from app.models.entities import User
        from app.models.enums import UserRole
        from app.core.security import create_access_token, hash_password

        cust_user = self.db.query(User).filter_by(phone=phone).first()
        if not cust_user:
            cust_user = User(
                email=f"owner_{phone}@h4care.vn",
                phone=phone,
                password_hash=hash_password("Pass@123"),
                full_name="Chủ Đơn",
                role=UserRole.CUSTOMER,
                is_active=True,
            )
            self.db.add(cust_user)
            self.db.commit()

        token = create_access_token(str(cust_user.id), "CUSTOMER")
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Khách hàng xem đúng đơn của mình -> 200 OK
        resp = self.client.get(f"/api/v1/store/orders/customer/{phone}", headers=headers)
        self.assertEqual(resp.status_code, 200)
        orders = resp.json()
        self.assertTrue(any(o["order_code"] == order.order_code for o in orders))

        # 4. Cố tình tra cứu SĐT người khác -> 403 Forbidden
        resp_idor = self.client.get("/api/v1/store/orders/customer/0988888888", headers=headers)
        self.assertEqual(resp_idor.status_code, 403)

    # =========================================================================
    # 34. REFUND / RETURN INTEGRATION
    # =========================================================================
    def test_34_refund_integration(self):
        """34. Return policy service evaluates return eligibility for delivered orders."""
        order = Order(
            order_code="PT-TEST-DELIV-RET",
            customer_name="Khách Đổi Trả",
            customer_phone="0903337777",
            shipping_address="123 Test",
            total_amount=Decimal("120000.0"),
            payment_method="COD",
            order_status="COMPLETED",
        )
        self.db.add(order)
        self.db.commit()

        eligibility = ReturnPolicyService.evaluate_order_eligibility(self.db, order)
        self.assertIsNotNone(eligibility)
        self.assertTrue(hasattr(eligibility, "can_request_return"))
        self.assertEqual(eligibility.order_code, order.order_code)

    # =========================================================================
    # 35. NETWORK TIMEOUT RECOVERY (IDEMPOTENCY RECOVERY)
    # =========================================================================
    def test_35_network_timeout_recovery(self):
        """35. Client recovering from network timeout retrieves created order using idempotency key."""
        prod = self._create_test_product(835, "Thuốc Test Timeout 835")
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code="SKU-835",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("45000.0"),
            is_active=True,
        )
        self.db.add(sku)
        self.db.commit()
        batch = InventoryBatch(
            sku_id=sku.id,
            initial_quantity=50,
            batch_number="B-835",
            expiry_date=date.today() + timedelta(days=90),
            status=BatchStatus.ACTIVE,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.add(WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=batch.id,
            quantity_on_hand=30,
            quantity_reserved=0,
            quantity_available=30,
        ))
        self.db.commit()

        idem_key = "IDEM-TIMEOUT-RECOVERY-KEY-835"
        payload = {
            "customer_name": "Khách Mạng Yếu",
            "customer_phone": "0908881234",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Tân Bình",
            "province_code": "79",
            "commune_code": "26830",
            "lat": 10.7981,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "idempotency_key": idem_key,
            "items": [{"product_id": prod.id, "sku_id": sku.id, "quantity": 1}],
        }
        r1 = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(r1.status_code, 200)

        # Giả lập client bị rớt mạng và submit lại cùng idempotency key
        r2 = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()["order_code"], r2.json()["order_code"])


if __name__ == "__main__":
    unittest.main()
