import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import CanonicalProduct, InventoryBatch, PriceObservation, WarehouseBatchStock
from app.models.enums import PublishStatus, RxOtcStatus
from app.services.search_service import search_product_ids_fts


class TestRxSafetyAndSearchSecurity(unittest.TestCase):
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

    # =========================================================================
    # 1. BẢO VỆ PHÁP LÝ THUỐC KÊ ĐƠN (Rx SAFETY AT BACKEND)
    # =========================================================================
    def test_backend_strictly_blocks_checkout_for_rx_medications(self):
        """Chứng minh Backend chặn 100% việc đặt mua trực tuyến thuốc kê đơn Rx."""
        rx_prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.rx_otc_status == RxOtcStatus.PRESCRIPTION,
            CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
        ).first()
        self.assertIsNotNone(rx_prod, "Phải có ít nhất 1 thuốc kê đơn Rx trong DB để kiểm tra")

        payload = {
            "customer_name": "Nguyễn Văn Test",
            "customer_phone": "0912345678",
            "shipping_address": "Số 12 Nguyễn Thị Minh Khai, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
            "fulfillment_type": "DELIVERY",
            "is_verified": True,
            "lat": 10.7872,
            "lng": 106.7001,
            "province_code": "79",
            "ward_code": "26734",
            "items": [
                {
                    "product_id": rx_prod.id,
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
            "payment_method": "COD",
        }

        response = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("thuốc kê đơn", data["detail"].lower())
        self.assertIn("bộ y tế", data["detail"].lower())

    def test_backend_blocks_checkout_for_unverified_or_draft_products(self):
        """Chặn đặt mua sản phẩm chưa được Publish (DRAFT hoặc REVIEW_REQUIRED)."""
        draft_prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.publish_status != PublishStatus.PUBLISHED
        ).first()
        if not draft_prod:
            # Tạo bản ghi draft mẫu
            draft_prod = CanonicalProduct(
                canonical_name="Thuốc Đang Thẩm Định Chưa Bán",
                publish_status=PublishStatus.DRAFT,
                rx_otc_status=RxOtcStatus.OTC,
            )
            self.db.add(draft_prod)
            self.db.commit()
            self.db.refresh(draft_prod)

        payload = {
            "customer_name": "Trần Thị Test",
            "customer_phone": "0987654321",
            "shipping_address": "Số 12 Nguyễn Thị Minh Khai, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
            "fulfillment_type": "DELIVERY",
            "is_verified": True,
            "lat": 10.7872,
            "lng": 106.7001,
            "province_code": "79",
            "ward_code": "26734",
            "items": [
                {
                    "product_id": draft_prod.id,
                    "quantity": 1,
                    "unit_price": 10000,
                }
            ],
            "payment_method": "COD",
        }

        response = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("chưa sẵn sàng để đặt hàng", response.json()["detail"])

    def test_backend_blocks_checkout_for_reference_only_catalog_products(self):
        """Chặn đặt mua sản phẩm thuộc danh mục tra cứu thông tin tham khảo (REFERENCE_ONLY)."""
        ref_prod = self.db.query(CanonicalProduct).filter(
            CanonicalProduct.publish_mode == "REFERENCE_ONLY"
        ).first()
        self.assertIsNotNone(ref_prod, "Phải có ít nhất 1 sản phẩm REFERENCE_ONLY trong catalog")

        payload = {
            "customer_name": "Lê Văn Tham Khảo",
            "customer_phone": "0933445566",
            "shipping_address": "Số 12 Nguyễn Thị Minh Khai, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
            "fulfillment_type": "DELIVERY",
            "is_verified": True,
            "lat": 10.7872,
            "lng": 106.7001,
            "province_code": "79",
            "ward_code": "26734",
            "items": [
                {
                    "product_id": ref_prod.id,
                    "quantity": 1,
                    "unit_price": 50000,
                }
            ],
            "payment_method": "COD",
        }

        response = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("chưa mở bán trực tuyến", response.json()["detail"].lower())

    # =========================================================================
    # 2. BẢO MẬT VÀ AN TOÀN TÌM KIẾM (SEARCH SECURITY & ROBUSTNESS)
    # =========================================================================
    def test_search_special_characters_and_sql_injection(self):
        """Kiểm thử các chuỗi tấn công SQL Injection và ký tự đặc biệt FTS."""
        attack_strings = [
            "panadol' OR 1=1 --",
            "'; DROP TABLE products_fts; --",
            'panadol" OR "1"="1',
            'panadol"""*"*""',
            "<script>alert('xss')</script>",
            "AND OR NOT NEAR()",
            "(((((((((())))))))))",
            "***???:::^^^~~~",
            "\\\\\\/////\"\"\"",
        ]

        for s in attack_strings:
            res = self.client.get(f"/api/v1/store/products?search={s}&limit=5")
            self.assertIn(
                res.status_code,
                [200, 422],
                f"Truy vấn '{s}' gây lỗi không mong muốn (HTTP {res.status_code})",
            )
            if res.status_code == 200:
                data = res.json()
                self.assertIsInstance(data["items"], list)

    def test_search_query_length_boundary(self):
        """Kiểm thử giới hạn độ dài truy vấn tìm kiếm."""
        # Chuỗi bình thường < 100 ký tự -> 200 OK
        res_ok = self.client.get("/api/v1/store/products?search=panadol&limit=5")
        self.assertEqual(res_ok.status_code, 200)

        # Chuỗi dài vượt 100 ký tự -> FastAPI trả về 422 Unprocessable Entity
        long_query = "a" * 150
        res_long = self.client.get(f"/api/v1/store/products?search={long_query}&limit=5")
        self.assertEqual(res_long.status_code, 422)

    def test_quarantined_test_batches_have_zero_available_stock(self):
        """Chứng minh toàn bộ 170 lô test FEFO đã được cách ly hoàn toàn khỏi tồn bán thật."""
        quarantined = self.db.query(InventoryBatch).filter(
            InventoryBatch.status == "QUARANTINED"
        ).all()
        self.assertGreaterEqual(len(quarantined), 170)

        q_ids = [b.id for b in quarantined]
        q_stocks = self.db.query(WarehouseBatchStock).filter(
            WarehouseBatchStock.batch_id.in_(q_ids)
        ).all()

        for s in q_stocks:
            self.assertEqual(
                s.quantity_available,
                0,
                f"Lô cách ly #{s.batch_id} có tồn khả dụng khác 0: {s.quantity_available}",
            )


if __name__ == "__main__":
    unittest.main()
