import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from datetime import date, timedelta
from app.models import (
    AdministrativeUnit,
    CanonicalProduct,
    InventoryBatch,
    Order,
    PriceObservation,
    ProductSku,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RxOtcStatus


class TestDeliveryAddressVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        prod = cls.db.scalar(
            select(CanonicalProduct).where(
                CanonicalProduct.publish_status == PublishStatus.PUBLISHED,
                CanonicalProduct.rx_otc_status == RxOtcStatus.OTC,
            )
        )
        if not prod:
            prod = CanonicalProduct(
                canonical_name="Băng cá nhân Urgo Transparent (Test)",
                manufacturer="Urgo",
                manufacturing_country="Pháp",
                package_description="Hộp 100 miếng",
                publish_status=PublishStatus.PUBLISHED,
                rx_otc_status=RxOtcStatus.OTC,
            )
            cls.db.add(prod)
            cls.db.commit()
        prod.publish_mode = "SALE_ELIGIBLE"
        prod.publish_status = PublishStatus.PUBLISHED
        prod.is_demo = False
        cls.db.commit()

        cls.test_prod_id = prod.id

        price_obs = cls.db.query(PriceObservation).filter_by(product_id=prod.id).first()
        if not price_obs:
            price_obs = PriceObservation(
                product_id=prod.id,
                source_id=1,
                source_url="https://example.com/products/test-product",
                observed_price=Decimal("45000.0"),
                currency="VND",
            )
            cls.db.add(price_obs)
            cls.db.commit()

        # Đảm bảo kho hoạt động và tồn kho
        wh = cls.db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not wh:
            wh = Warehouse(
                code="KHO-HCM-01",
                name="Kho Dược HCM",
                address="123 Lê Lợi, Quận 1, TP. Hồ Chí Minh",
                is_active=True,
                is_central=True,
            )
            cls.db.add(wh)
            cls.db.commit()
            cls.db.refresh(wh)
        else:
            wh.is_active = True
            cls.db.commit()

        sku = cls.db.query(ProductSku).filter_by(canonical_product_id=prod.id).first()
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod.id,
                sku_code=f"SKU-TEST-{prod.id}",
                base_price=Decimal("45000.0"),
                is_default=True,
                is_active=True,
            )
            cls.db.add(sku)
            cls.db.commit()
            cls.db.refresh(sku)

        batch = cls.db.query(InventoryBatch).filter_by(sku_id=sku.id).first()
        if not batch:
            batch = InventoryBatch(
                sku_id=sku.id,
                batch_number="BATCH-TEST-VERIFY-01",
                expiry_date=date.today() + timedelta(days=365),
                initial_quantity=500,
                status="ACTIVE",
            )
            cls.db.add(batch)
            cls.db.commit()
            cls.db.refresh(batch)

        stock = cls.db.query(WarehouseBatchStock).filter_by(warehouse_id=wh.id, batch_id=batch.id).first()
        if not stock:
            stock = WarehouseBatchStock(
                warehouse_id=wh.id,
                batch_id=batch.id,
                quantity_on_hand=500,
                quantity_reserved=0,
                quantity_available=500,
            )
            cls.db.add(stock)
            cls.db.commit()
        else:
            stock.quantity_available = 500
            stock.quantity_on_hand = 500
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_suggest_rejects_junk_text(self):
        """Autocomplete từ chối các chuỗi rác như 'tt', 'abc', 'nhà tôi', '123 test'."""
        junk_queries = ["tt", "abc", "123 test", "nhà tôi", "dự án xyz", "gần trường"]
        for jq in junk_queries:
            resp = self.client.get(
                "/api/v1/addresses/suggest",
                params={
                    "q": jq,
                    "province_code": "79",
                    "district_code": "760",
                    "ward_code": "26734",
                },
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(len(data), 0, f"Query '{jq}' should return 0 suggestions")

    def test_02_suggest_returns_valid_suggestions_for_real_street(self):
        """Autocomplete trả về gợi ý hợp lệ với số nhà, tên đường cụ thể trong địa giới."""
        resp = self.client.get(
            "/api/v1/addresses/suggest",
            params={
                "q": "45 Hoàng Hoa Thám",
                "province_code": "79",
                "district_code": "766",
                "ward_code": "26965",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(len(data), 0)
        item = data[0]
        self.assertTrue(item["verified"])
        self.assertIn("45 Hoàng Hoa Thám", item["street_address"])
        self.assertTrue("Tân Bình" in item["district_name"] or item["district_name"] == "")
        self.assertIn("Hồ Chí Minh", item["province_name"])
        self.assertTrue(10.0 <= item["lat"] <= 11.5)
        self.assertTrue(106.0 <= item["lng"] <= 107.2)

    def test_03_delivery_rejected_if_not_verified(self):
        """Chặn đơn giao tận nơi nếu is_verified = False."""
        payload = {
            "customer_name": "Nguyễn Văn Test",
            "customer_phone": "0912345678",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Q. Tân Bình",
            "fulfillment_type": "DELIVERY",
            "province_code": "79",
            "district_code": "766",
            "ward_code": "26965",
            "lat": 10.7992,
            "lng": 106.6534,
            "is_verified": False,
            "payment_method": "COD",
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("chưa được xác minh", resp.json()["detail"])

    def test_04_delivery_rejected_if_missing_coordinates(self):
        """Chặn đơn nếu thiếu lat hoặc lng."""
        payload = {
            "customer_name": "Nguyễn Văn Test",
            "customer_phone": "0912345678",
            "shipping_address": "45 Hoàng Hoa Thám, P.13, Q. Tân Bình",
            "fulfillment_type": "DELIVERY",
            "province_code": "79",
            "district_code": "766",
            "ward_code": "26965",
            "lat": None,
            "lng": None,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Thiếu tọa độ", resp.json()["detail"])

    def test_05_cross_province_coordinate_mismatch_rejected(self):
        """Chặn gian lận: Chọn Hà Nội (01) nhưng truyền tọa độ TP.HCM (10.77, 106.70) -> HTTP 400."""
        payload = {
            "customer_name": "Trần Văn Gian Lận",
            "customer_phone": "0912345678",
            "shipping_address": "25 Phố Huế, Hàng Bài, Hoàn Kiếm, Hà Nội",
            "fulfillment_type": "DELIVERY",
            "province_code": "01",
            "district_code": "002",
            "ward_code": "00049",
            # Tọa độ TP.HCM (Quận 1)
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("không khớp với phạm vi địa lý", resp.json()["detail"])

    def test_06_cross_province_hcm_with_hanoi_coords_rejected(self):
        """Chặn gian lận: Chọn TP.HCM (79) nhưng truyền tọa độ Hà Nội (21.02, 105.85) -> HTTP 400."""
        payload = {
            "customer_name": "Lê Văn Sai Lệch",
            "customer_phone": "0912345678",
            "shipping_address": "88 Pasteur, Bến Nghé, Quận 1, TP. Hồ Chí Minh",
            "fulfillment_type": "DELIVERY",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            # Tọa độ Hà Nội
            "lat": 21.0285,
            "lng": 105.8542,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("không khớp với phạm vi địa lý", resp.json()["detail"])

    def test_07_valid_verified_delivery_order_succeeds(self):
        """Đơn hàng có địa chỉ xác minh hợp lệ tạo thành công và lưu đủ cấu trúc."""
        payload = {
            "customer_name": "Đặng Thị Mai",
            "customer_phone": "0918765432",
            "customer_email": "mai.dang@example.com",
            "shipping_address": "Số 45 Đường Hoàng Hoa Thám, Phường 13, Quận Tân Bình, TP. Hồ Chí Minh",
            "shipping_city": "TP. Hồ Chí Minh",
            "fulfillment_type": "DELIVERY",
            "province_code": "79",
            "district_code": "766",
            "ward_code": "26965",
            "lat": 10.7992,
            "lng": 106.6534,
            "is_verified": True,
            "payment_method": "COD",
            "note": "Gọi trước 15 phút, gửi bảo vệ tòa nhà",
            "items": [{"product_id": self.test_prod_id, "quantity": 2}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "SUCCESS")
        order_code = data["order_code"]

        # Kiểm tra CSDL
        order = self.db.query(Order).filter_by(order_code=order_code).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.province_code, "79")
        self.assertEqual(order.district_code, "766")
        self.assertEqual(order.ward_code, "26965")
        self.assertEqual(order.lat, 10.7992)
        self.assertEqual(order.lng, 106.6534)
        self.assertTrue(order.is_verified)
        self.assertEqual(order.note, "Gọi trước 15 phút, gửi bảo vệ tòa nhà")
        # Ghi chú KHÔNG bị dồn vào ô địa chỉ
        self.assertNotIn("Gọi trước 15 phút", order.shipping_address)

    def test_08_store_pickup_order_succeeds_without_home_address(self):
        """Hình thức nhận tại quầy (STORE_PICKUP) không đòi hỏi xác minh địa chỉ nhà riêng."""
        payload = {
            "customer_name": "Phan Hữu Thắng",
            "customer_phone": "0909112233",
            "shipping_address": "Nhận tại: H4CARE Hoàng Hoa Thám (45 Hoàng Hoa Thám, Tân Bình)",
            "shipping_city": "TP. Hồ Chí Minh",
            "fulfillment_type": "STORE_PICKUP",
            "is_verified": False,
            "payment_method": "COD",
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "SUCCESS")

    def test_09_official_34_provinces_after_2025(self):
        """Kiểm tra API /locations/provinces trả về đúng 34 đơn vị hành chính cấp tỉnh."""
        resp = self.client.get("/api/v1/locations/provinces")
        self.assertEqual(resp.status_code, 200)
        provinces = resp.json()
        self.assertEqual(len(provinces), 34)
        codes = [p["code"] for p in provinces]
        self.assertEqual(len(codes), len(set(codes)))
        # Phải có Hà Nội (01) và TP.HCM (79)
        self.assertIn("01", codes)
        self.assertIn("79", codes)

    def test_10_locations_metadata(self):
        """Kiểm tra Metadata chính thức năm 2025: 34 tỉnh, 3.321 xã, 2-tier."""
        resp = self.client.get("/api/v1/locations/metadata")
        self.assertEqual(resp.status_code, 200)
        meta = resp.json()
        self.assertEqual(meta["country"], "VN")
        self.assertEqual(meta["administrativeModel"], "2-tier")
        self.assertEqual(meta["effectiveDate"], "2025-07-01")
        self.assertEqual(meta["totalProvinces"], 34)
        self.assertEqual(meta["totalCommunes"], 3321)

    def test_11_communes_filter_by_province(self):
        """Kiểm tra danh sách xã/phường thuộc Hà Nội theo mô hình 2 cấp."""
        resp = self.client.get("/api/v1/locations/communes?provinceCode=01")
        self.assertEqual(resp.status_code, 200)
        communes = resp.json()
        self.assertGreater(len(communes), 50)
        for c in communes:
            self.assertEqual(c["provinceCode"], "01")
            self.assertIn(c["type"], ["ward", "commune", "special_zone"])

    def test_12_special_zone_support(self):
        """Hệ thống phải hỗ trợ Đặc khu (special_zone) như Phú Quốc, Vân Đồn, Côn Đảo."""
        resp = self.client.get("/api/v1/locations/communes?type=special_zone")
        self.assertEqual(resp.status_code, 200)
        sz_list = resp.json()
        self.assertGreaterEqual(len(sz_list), 7)
        names = [sz["name"] for sz in sz_list]
        self.assertIn("Phú Quốc", names)
        self.assertIn("Vân Đồn", names)
        self.assertIn("Côn Đảo", names)

    def test_13_unaccented_search_and_alias(self):
        """Tìm kiếm không dấu 'ha noi' và tra cứu alias quận cũ 'Ba Đình'."""
        # Tìm tỉnh không dấu
        resp = self.client.get("/api/v1/locations/provinces?search=ha%20noi")
        self.assertEqual(resp.status_code, 200)
        provinces = resp.json()
        self.assertTrue(any(p["code"] == "01" for p in provinces))

        # Tìm xã/phường qua alias quận cũ
        resp2 = self.client.get("/api/v1/locations/communes?provinceCode=01&search=Ba%20Đình")
        self.assertEqual(resp2.status_code, 200)
        results = resp2.json()
        self.assertGreater(len(results), 0)

    def test_14_checkout_2tier_succeeds_without_district(self):
        """Đặt hàng thành công với schema 2 cấp hiện hành (Tỉnh/Thành + Xã/Phường), KHÔNG cần District."""
        payload = {
            "customer_name": "Nguyễn Minh Châu",
            "customer_phone": "0987654321",
            "shipping_address": "Số 12 Đường Hàng Bài, Phường Tràng Tiền, Thành phố Hà Nội",
            "fulfillment_type": "DELIVERY",
            "province_code": "01",
            "commune_code": "011002",
            "commune_type": "ward",
            "lat": 21.0255,
            "lng": 105.8530,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "SUCCESS")
        order_code = data["order_code"]

        order = self.db.query(Order).filter_by(order_code=order_code).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.province_code_current, "01")
        self.assertEqual(order.commune_code_current, "011002")
        self.assertEqual(order.migration_status, "MIGRATED_2025")
        self.assertTrue(order.is_verified)

    def test_15_checkout_2tier_rejects_province_commune_mismatch(self):
        """Chặn gian lận: Tỉnh Hà Nội (01) nhưng mã xã thuộc TP.HCM (79001) -> HTTP 400."""
        payload = {
            "customer_name": "Kẻ Gian Lận",
            "customer_phone": "0912345678",
            "shipping_address": "123 Test, Hà Nội",
            "fulfillment_type": "DELIVERY",
            "province_code": "01",
            "commune_code": "79001",  # Côn Đảo thuộc TP.HCM
            "lat": 21.0255,
            "lng": 105.8530,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("không thuộc phạm vi hành chính", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
