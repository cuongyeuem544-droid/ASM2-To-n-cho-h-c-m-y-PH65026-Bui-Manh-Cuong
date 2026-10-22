import unittest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import (
    CanonicalProduct,
    CustomerAddress,
    InventoryBatch,
    Order,
    PriceObservation,
    ProductSku,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RxOtcStatus, UserRole
from datetime import date, timedelta


class TestAddressV2Comprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Tạo User A
        cls.user_a = cls.db.query(User).filter_by(email="customer_a_phase1@pharmatrust.vn").first()
        if not cls.user_a:
            cls.user_a = User(
                email="customer_a_phase1@pharmatrust.vn",
                full_name="Khách Hàng A",
                phone="0901234567",
                role=UserRole.CUSTOMER,
                password_hash="hashed_pw_a",
                is_active=True,
            )
            cls.db.add(cls.user_a)
            cls.db.commit()
            cls.db.refresh(cls.user_a)

        token_a = create_access_token(str(cls.user_a.id), cls.user_a.role.value)
        cls.headers_a = {"Authorization": f"Bearer {token_a}"}

        # Tạo User B (để test Ownership Security)
        cls.user_b = cls.db.query(User).filter_by(email="customer_b_phase1@pharmatrust.vn").first()
        if not cls.user_b:
            cls.user_b = User(
                email="customer_b_phase1@pharmatrust.vn",
                full_name="Khách Hàng B",
                phone="0987654321",
                role=UserRole.CUSTOMER,
                password_hash="hashed_pw_b",
                is_active=True,
            )
            cls.db.add(cls.user_b)
            cls.db.commit()
            cls.db.refresh(cls.user_b)

        token_b = create_access_token(str(cls.user_b.id), cls.user_b.role.value)
        cls.headers_b = {"Authorization": f"Bearer {token_b}"}

        # Tạo sản phẩm và kho phục vụ order snapshot test
        prod = cls.db.query(CanonicalProduct).filter_by(canonical_name="Berberin H4Care Phase1").first()
        if not prod:
            prod = CanonicalProduct(
                canonical_name="Berberin H4Care Phase1",
                manufacturer="Dược H4Care",
                manufacturing_country="Việt Nam",
                package_description="Lọ 100 viên",
                publish_status=PublishStatus.PUBLISHED,
                publish_mode="SALE_ELIGIBLE",
                rx_otc_status=RxOtcStatus.OTC,
            )
            cls.db.add(prod)
            cls.db.commit()
            cls.db.refresh(prod)
        else:
            prod.publish_mode = "SALE_ELIGIBLE"
            prod.publish_status = PublishStatus.PUBLISHED
            cls.db.commit()
        cls.test_prod_id = prod.id

        price_obs = cls.db.query(PriceObservation).filter_by(product_id=prod.id).first()
        if not price_obs:
            price_obs = PriceObservation(
                product_id=prod.id,
                source_id=1,
                source_url="https://example.com/berberin",
                observed_price=Decimal("25000.0"),
                currency="VND",
            )
            cls.db.add(price_obs)
            cls.db.commit()

        wh_hcm = cls.db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not wh_hcm:
            wh_hcm = Warehouse(
                code="KHO-HCM-01",
                name="Kho Dược HCM",
                address="123 Lê Lợi, Quận 1, TP. Hồ Chí Minh",
                lat=10.7769,
                lng=106.7009,
                is_active=True,
                is_central=True,
            )
            cls.db.add(wh_hcm)
            cls.db.commit()
            cls.db.refresh(wh_hcm)

        sku = cls.db.query(ProductSku).filter_by(canonical_product_id=prod.id).first()
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod.id,
                sku_code=f"SKU-BERBERIN-{prod.id}",
                base_price=Decimal("25000.0"),
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
                batch_number="BATCH-BERB-01",
                expiry_date=date.today() + timedelta(days=500),
                initial_quantity=1000,
                status="ACTIVE",
            )
            cls.db.add(batch)
            cls.db.commit()
            cls.db.refresh(batch)

        stock = cls.db.query(WarehouseBatchStock).filter_by(warehouse_id=wh_hcm.id, batch_id=batch.id).first()
        if not stock:
            stock = WarehouseBatchStock(
                warehouse_id=wh_hcm.id,
                batch_id=batch.id,
                quantity_on_hand=1000,
                quantity_reserved=0,
                quantity_available=1000,
            )
            cls.db.add(stock)
            cls.db.commit()
        else:
            stock.quantity_available = 1000
            stock.quantity_on_hand = 1000
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        # Dọn sạch các địa chỉ test của User A và B
        cls.db.query(CustomerAddress).filter(
            CustomerAddress.user_id.in_([cls.user_a.id, cls.user_b.id])
        ).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def setUp(self):
        # Dọn sạch địa chỉ trước mỗi test của User A và User B
        self.db = SessionLocal()
        self.db.query(CustomerAddress).filter(
            CustomerAddress.user_id.in_([self.user_a.id, self.user_b.id])
        ).delete(synchronize_session=False)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # 1. Test tạo địa chỉ hợp lệ
    def test_01_create_valid_address(self):
        payload = {
            "recipient_name": "Nguyễn Văn Hùng",
            "phone": "0912345678",
            "address_line": "123 Đường Hai Bà Trưng",
            "province_code": "79",
            "commune_code": "791161",
            "lat": 10.7769,
            "lng": 106.7009,
            "delivery_note": "Giao giờ hành chính, gọi trước 15 phút",
            "is_default": True,
        }
        res = self.client.post("/api/v1/customer/addresses", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["recipient_name"], "Nguyễn Văn Hùng")
        self.assertEqual(data["phone"], "0912345678")
        self.assertTrue(data["is_default"])
        self.assertTrue(data["is_verified"])
        self.assertIsNotNone(data["verified_at"])
        self.assertIn("Hồ Chí Minh", data["province_name"])
        self.assertEqual(data["delivery_note"], "Giao giờ hành chính, gọi trước 15 phút")

    # 2. Test số điện thoại không hợp lệ
    def test_02_invalid_phone_formats(self):
        invalid_phones = ["123", "01234567", "090123456789", "abcdefghij", "0012345678", "0212345678"]
        for bad_phone in invalid_phones:
            payload = {
                "recipient_name": "Test Phone",
                "phone": bad_phone,
                "address_line": "123 Lê Duẩn",
                "province_code": "79",
                "lat": 10.7769,
                "lng": 106.7009,
            }
            res = self.client.post("/api/v1/customer/addresses", json=payload, headers=self.headers_a)
            self.assertIn(res.status_code, [400, 422], f"Phone '{bad_phone}' should have been rejected")

    # 3. Test mã tỉnh không hợp lệ
    def test_03_invalid_province(self):
        payload = {
            "recipient_name": "Nguyễn Văn Hùng",
            "phone": "0912345678",
            "address_line": "123 Đường Hai Bà Trưng",
            "province_code": "999_NON_EXISTENT",
            "lat": 10.7769,
            "lng": 106.7009,
        }
        res = self.client.post("/api/v1/customer/addresses", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 400)
        self.assertIn("không hợp lệ", res.json()["detail"])

    # 4. Test xã/phường không thuộc tỉnh
    def test_04_commune_province_mismatch(self):
        # 011001 thuộc Hà Nội (01), nhưng chọn Province 79 (TP.HCM)
        payload = {
            "recipient_name": "Nguyễn Văn Hùng",
            "phone": "0912345678",
            "address_line": "123 Đường Hai Bà Trưng",
            "province_code": "79",
            "commune_code": "011001",
            "lat": 10.7769,
            "lng": 106.7009,
        }
        res = self.client.post("/api/v1/customer/addresses", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 400)
        self.assertIn("không thuộc phạm vi", res.json()["detail"])

    # 5. Test tọa độ không hợp lệ (ngoài khoảng, (0,0), lệch tỉnh)
    def test_05_invalid_coordinates(self):
        # Tọa độ (0, 0)
        res_zero = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Test Zero",
            "phone": "0912345678",
            "address_line": "123 Test",
            "province_code": "79",
            "lat": 0.0,
            "lng": 0.0,
        }, headers=self.headers_a)
        self.assertEqual(res_zero.status_code, 400)
        self.assertIn("(0, 0)", res_zero.json()["detail"])

        # Tọa độ Hà Nội gán vào TP.HCM
        res_cross = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Test Cross",
            "phone": "0912345678",
            "address_line": "123 Test",
            "province_code": "79",
            "lat": 21.0285,
            "lng": 105.8542,
        }, headers=self.headers_a)
        self.assertEqual(res_cross.status_code, 400)
        self.assertIn("không khớp với phạm vi", res_cross.json()["detail"])

    # 6. Test tự động đặt default cho địa chỉ đầu tiên
    def test_06_first_address_auto_default(self):
        payload = {
            "recipient_name": "Địa chỉ đầu tiên",
            "phone": "0912345678",
            "address_line": "123 Lê Lợi",
            "province_code": "79",
            "is_default": False,  # Client gửi false nhưng là địa chỉ đầu tiên
        }
        res = self.client.post("/api/v1/customer/addresses", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.json()["is_default"])

    # 7. Test quy tắc duy nhất 1 địa chỉ mặc định
    def test_07_single_default_address_guarantee(self):
        # Địa chỉ 1 (mặc định)
        res1 = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Địa chỉ 1",
            "phone": "0912345678",
            "address_line": "123 Lê Lợi",
            "province_code": "79",
            "is_default": True,
        }, headers=self.headers_a)
        id1 = res1.json()["id"]

        # Địa chỉ 2 đặt làm mặc định
        res2 = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Địa chỉ 2",
            "phone": "0912345678",
            "address_line": "456 Nguyễn Huệ",
            "province_code": "79",
            "is_default": True,
        }, headers=self.headers_a)
        id2 = res2.json()["id"]

        # Kiểm tra danh sách: id2 là default, id1 đã mất default
        res_list = self.client.get("/api/v1/customer/addresses", headers=self.headers_a).json()
        a1 = next(a for a in res_list if a["id"] == id1)
        a2 = next(a for a in res_list if a["id"] == id2)
        self.assertFalse(a1["is_default"])
        self.assertTrue(a2["is_default"])

        # Chuyển lại id1 làm default qua PATCH /default
        res_patch = self.client.patch(f"/api/v1/customer/addresses/{id1}/default", headers=self.headers_a)
        self.assertEqual(res_patch.status_code, 200)

        res_list2 = self.client.get("/api/v1/customer/addresses", headers=self.headers_a).json()
        a1_after = next(a for a in res_list2 if a["id"] == id1)
        a2_after = next(a for a in res_list2 if a["id"] == id2)
        self.assertTrue(a1_after["is_default"])
        self.assertFalse(a2_after["is_default"])

    # 8. Test cập nhật và xóa địa chỉ với fallback default
    def test_08_update_and_delete_with_fallback_default(self):
        res1 = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Địa chỉ 1",
            "phone": "0912345678",
            "address_line": "123 Lê Lợi",
            "province_code": "79",
            "is_default": False,
        }, headers=self.headers_a)
        id1 = res1.json()["id"]

        res2 = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Địa chỉ 2",
            "phone": "0912345678",
            "address_line": "456 Nguyễn Huệ",
            "province_code": "79",
            "is_default": True,
        }, headers=self.headers_a)
        id2 = res2.json()["id"]

        # Cập nhật địa chỉ 1
        res_update = self.client.patch(f"/api/v1/customer/addresses/{id1}", json={
            "recipient_name": "Địa chỉ 1 Đã Đổi Tên",
            "delivery_note": "Ghi chú mới",
        }, headers=self.headers_a)
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["recipient_name"], "Địa chỉ 1 Đã Đổi Tên")

        # Xóa địa chỉ 2 (đang là default). Địa chỉ 1 phải tự động trở thành default fallback
        res_del = self.client.delete(f"/api/v1/customer/addresses/{id2}", headers=self.headers_a)
        self.assertEqual(res_del.status_code, 200)

        res_list = self.client.get("/api/v1/customer/addresses", headers=self.headers_a).json()
        self.assertEqual(len(res_list), 1)
        self.assertEqual(res_list[0]["id"], id1)
        self.assertTrue(res_list[0]["is_default"])

    # 9. Test BẢO MẬT QUYỀN SỞ HỮU (OWNERSHIP SECURITY)
    def test_09_ownership_security_strict_isolation(self):
        # User A tạo địa chỉ
        res_a = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Địa chỉ bí mật của User A",
            "phone": "0901234567",
            "address_line": "123 Khu Biệt Thự",
            "province_code": "79",
        }, headers=self.headers_a)
        addr_a_id = res_a.json()["id"]

        # User B KHÔNG ĐƯỢC GET địa chỉ của User A
        res_b_get = self.client.get(f"/api/v1/customer/addresses/{addr_a_id}", headers=self.headers_b)
        self.assertEqual(res_b_get.status_code, 404)

        # User B KHÔNG ĐƯỢC UPDATE địa chỉ của User A
        res_b_put = self.client.put(f"/api/v1/customer/addresses/{addr_a_id}", json={
            "recipient_name": "Hacker B Sửa",
        }, headers=self.headers_b)
        self.assertEqual(res_b_put.status_code, 404)

        # User B KHÔNG ĐƯỢC SET DEFAULT địa chỉ của User A
        res_b_def = self.client.patch(f"/api/v1/customer/addresses/{addr_a_id}/default", headers=self.headers_b)
        self.assertEqual(res_b_def.status_code, 404)

        # User B KHÔNG ĐƯỢC DELETE địa chỉ của User A
        res_b_del = self.client.delete(f"/api/v1/customer/addresses/{addr_a_id}", headers=self.headers_b)
        self.assertEqual(res_b_del.status_code, 404)

        # Địa chỉ của User A vẫn còn nguyên vẹn
        res_a_check = self.client.get(f"/api/v1/customer/addresses/{addr_a_id}", headers=self.headers_a)
        self.assertEqual(res_a_check.status_code, 200)
        self.assertEqual(res_a_check.json()["recipient_name"], "Địa chỉ bí mật của User A")

    # 10. Test SNAPSHOT ĐỊA CHỈ ĐƠN HÀNG (Order Snapshot Immutability)
    def test_10_order_address_snapshot_immutability(self):
        # Tạo địa chỉ cho User A
        res_addr = self.client.post("/api/v1/customer/addresses", json={
            "recipient_name": "Người Nhận Ban Đầu",
            "phone": "0901234567",
            "address_line": "100 Phố Cũ",
            "province_code": "79",
            "commune_code": "791161",
            "lat": 10.7769,
            "lng": 106.7009,
        }, headers=self.headers_a)
        self.assertEqual(res_addr.status_code, 201, res_addr.text)
        addr_id = res_addr.json()["id"]

        # Đặt đơn hàng với địa chỉ này
        checkout_payload = {
            "customer_name": "Người Nhận Ban Đầu",
            "customer_phone": "0901234567",
            "shipping_address": "100 Phố Cũ, P. Bến Nghé, TP. Hồ Chí Minh",
            "fulfillment_type": "DELIVERY",
            "province_code": "79",
            "commune_code": "791161",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "items": [{"product_id": self.test_prod_id, "quantity": 2}],
            "payment_method": "COD",
        }
        res_order = self.client.post("/api/v1/store/orders/checkout", json=checkout_payload)
        self.assertEqual(res_order.status_code, 200, res_order.text)
        order_code = res_order.json()["order_code"]

        # Sau khi đặt đơn, khách hàng sửa địa chỉ lưu thành địa chỉ hoàn toàn khác
        self.client.put(f"/api/v1/customer/addresses/{addr_id}", json={
            "recipient_name": "Tên Mới Hoàn Toàn",
            "address_line": "999 Phố Mới",
        }, headers=self.headers_a)

        # Hoặc thậm chí xóa luôn địa chỉ đã lưu
        self.client.delete(f"/api/v1/customer/addresses/{addr_id}", headers=self.headers_a)

        # Đơn hàng cũ trong DB VẪN PHẢI GIỮ NGUYÊN SNAPSHOT BAN ĐẦU
        order_db = self.db.scalar(select(Order).where(Order.order_code == order_code))
        self.assertIsNotNone(order_db)
        self.assertEqual(order_db.customer_name, "Người Nhận Ban Đầu")
        self.assertEqual(order_db.shipping_address, "100 Phố Cũ, P. Bến Nghé, TP. Hồ Chí Minh")
        self.assertEqual(order_db.province_code, "79")
        self.assertEqual(order_db.lat, 10.7769)
        self.assertEqual(order_db.lng, 106.7009)
        self.assertTrue(order_db.is_verified)

    # 11. Test tính cước vận chuyển (ShippingService)
    def test_11_shipping_service_calculation(self):
        # Tọa độ ngay cạnh kho HCM (<= 5km) -> Cước siêu tốc 15.000đ
        res_near = self.client.post("/api/v1/addresses/calculate-shipping", json={
            "lat": 10.7780,
            "lng": 106.7015,
            "order_total": 100000.0,
        })
        self.assertEqual(res_near.status_code, 200)
        data_near = res_near.json()
        self.assertLessEqual(data_near["distance_km"], 5.0)
        self.assertEqual(data_near["shipping_fee"], 15000.0)
        self.assertFalse(data_near["is_free_shipping"])

        # Đơn hàng >= 300.000đ -> Miễn phí cước vận chuyển (0đ)
        res_free = self.client.post("/api/v1/addresses/calculate-shipping", json={
            "lat": 10.7780,
            "lng": 106.7015,
            "order_total": 350000.0,
        })
        self.assertEqual(res_free.status_code, 200)
        data_free = res_free.json()
        self.assertEqual(data_free["shipping_fee"], 0.0)
        self.assertTrue(data_free["is_free_shipping"])

    # 12. Test toàn diện luồng UX Mục tiêu (Mục 4: Account -> Address -> Verify -> Default -> Checkout -> Snapshot)
    def test_12_full_ux_flow_account_to_checkout(self):
        # Bước 1: Tài khoản vào xem sổ địa chỉ
        res_list_init = self.client.get("/api/v1/customer/addresses", headers=self.headers_a)
        self.assertEqual(res_list_init.status_code, 200)

        # Bước 2: Thêm địa chỉ mới với đầy đủ thông tin & tọa độ bản đồ
        payload_new = {
            "recipient_name": "Trần Thị Bích Ngọc",
            "phone": "0987 654 321",  # Kiểm tra chuẩn hóa khoảng trắng
            "province_code": "79",
            "commune_code": "791161",
            "address_line": "Số 25 Lê Duẩn, Tòa nhà Deutsches Haus",
            "lat": 10.7818,
            "lng": 106.7002,
            "delivery_note": "Giao giờ hành chính, gọi trước khi đến",
            "is_default": True,
        }
        res_create = self.client.post("/api/v1/customer/addresses", json=payload_new, headers=self.headers_a)
        self.assertIn(res_create.status_code, [200, 201])
        addr_created = res_create.json()
        addr_id = addr_created["id"]

        # Bước 3: Backend xác minh vị trí và thông tin
        self.assertEqual(addr_created["phone"], "0987654321")
        self.assertTrue(addr_created["is_verified"])
        self.assertIsNotNone(addr_created["verified_at"])
        self.assertTrue(addr_created["is_default"])

        # Bước 4: Tính cước vận chuyển và thời gian giao hàng từ kho gần nhất
        res_shipping = self.client.post("/api/v1/addresses/calculate-shipping", json={
            "lat": 10.7818,
            "lng": 106.7002,
            "province_code": "79",
            "order_total": 120000.0,
        })
        self.assertEqual(res_shipping.status_code, 200)
        ship_data = res_shipping.json()
        self.assertIn("distance_km", ship_data)
        self.assertIn("estimated_delivery", ship_data)

        # Bước 5: Khách hàng tiến hành Checkout sử dụng địa chỉ đã lưu
        checkout_payload = {
            "customer_name": addr_created["recipient_name"],
            "customer_phone": addr_created["phone"],
            "shipping_address": addr_created["formatted_address"],
            "shipping_city": addr_created["province_name"],
            "payment_method": "COD",
            "note": addr_created["delivery_note"],
            "fulfillment_type": "DELIVERY",
            "province_code": addr_created["province_code"],
            "commune_code": addr_created["commune_code"],
            "address_line": addr_created["address_line"],
            "formatted_address": addr_created["formatted_address"],
            "lat": addr_created["lat"],
            "lng": addr_created["lng"],
            "is_verified": True,
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        res_checkout = self.client.post("/api/v1/store/orders/checkout", json=checkout_payload)
        self.assertEqual(res_checkout.status_code, 200)
        order_res = res_checkout.json()
        order_code = order_res["order_code"]

        # Bước 6: Kiểm tra Snapshot đơn hàng trong DB
        order_db = self.db.scalar(select(Order).where(Order.order_code == order_code))
        self.assertIsNotNone(order_db)
        self.assertEqual(order_db.customer_name, "Trần Thị Bích Ngọc")
        self.assertEqual(order_db.customer_phone, "0987654321")
        self.assertEqual(order_db.province_code, "79")
        self.assertEqual(order_db.commune_code_current, "791161")
        self.assertEqual(order_db.lat, 10.7818)
        self.assertEqual(order_db.lng, 106.7002)
        self.assertTrue(order_db.is_verified)
        self.assertEqual(order_db.note, "Giao giờ hành chính, gọi trước khi đến")

    # 16. Test Luồng Google Maps-like hoàn chỉnh theo Mục 20: FPT Polytechnic Trịnh Văn Bô
    def test_16_fpt_polytechnic_google_like_flow(self):
        # Bước 1: Kiểm tra báo cáo Provider Geocoding (Mục 16)
        res_provider = self.client.get("/api/v1/addresses/provider-status")
        self.assertEqual(res_provider.status_code, 200)
        prov_info = res_provider.json()
        self.assertIn("report", prov_info)
        self.assertIn("FALLBACK", prov_info["report"])

        # Bước 2: User gõ 'FPT Polytechnic Trịnh Văn Bô' (Mục 1 & 2)
        res_suggest = self.client.get("/api/v1/addresses/places/autocomplete", params={"q": "FPT Polytechnic Trịnh Văn Bô"})
        self.assertEqual(res_suggest.status_code, 200)
        items = res_suggest.json()
        self.assertGreater(len(items), 0, "Phải trả về ít nhất 1 gợi ý cho FPT Polytechnic Trịnh Văn Bô")
        fpt_item = items[0]
        self.assertIn("FPT Polytechnic", fpt_item["name"])
        self.assertIn("Trịnh Văn Bô", fpt_item["formatted_address"])
        self.assertEqual(fpt_item["province_code"], "01")  # Hà Nội
        self.assertEqual(fpt_item["commune_code"], "011051")  # Phường Xuân Phương

        # Bước 3: User chọn địa điểm, sau đó kéo ghim hoặc click map tới cổng giao hàng (Mục 5, 6, 7)
        gate_lat = 21.0382
        gate_lng = 105.7471
        res_rev = self.client.get("/api/v1/addresses/reverse-geocode", params={"lat": gate_lat, "lng": gate_lng})
        self.assertEqual(res_rev.status_code, 200)
        rev_data = res_rev.json()
        self.assertTrue(rev_data["is_verified"])
        self.assertEqual(rev_data["province_code"], "01")
        self.assertIsNotNone(rev_data["formatted_address"])

        # Bước 4: User nhập thông tin người nhận + số điện thoại và Lưu địa chỉ (Mục 10 & 11)
        save_payload = {
            "recipient_name": "Nguyễn Văn Sinh Viên",
            "phone": "0912 345 678",  # Kiểm tra chuẩn hóa số điện thoại
            "province_code": rev_data["province_code"],
            "commune_code": rev_data.get("commune_code") or "011051",
            "address_line": "Cổng số 1, Cao đẳng FPT Polytechnic, Phố Trịnh Văn Bô",
            "lat": gate_lat,
            "lng": gate_lng,
            "delivery_note": "Giao tại cổng trường, gọi trước 5 phút",
            "is_default": True,
        }
        res_save = self.client.post("/api/v1/customer/addresses", json=save_payload, headers=self.headers_a)
        self.assertIn(res_save.status_code, [200, 201])
        addr_saved = res_save.json()

        # Bước 5: Backend tự động xác minh địa chỉ (Mục 15 của V2)
        self.assertEqual(addr_saved["phone"], "0912345678")
        self.assertTrue(addr_saved["is_verified"])
        self.assertIsNotNone(addr_saved["verified_at"])
        self.assertTrue(addr_saved["is_default"])

        # Bước 6: Checkout sử dụng địa chỉ này và kiểm tra Snapshot đơn hàng
        checkout_payload = {
            "customer_name": addr_saved["recipient_name"],
            "customer_phone": addr_saved["phone"],
            "shipping_address": addr_saved["formatted_address"],
            "shipping_city": addr_saved["province_name"],
            "payment_method": "COD",
            "note": addr_saved["delivery_note"],
            "fulfillment_type": "DELIVERY",
            "province_code": addr_saved["province_code"],
            "commune_code": addr_saved["commune_code"],
            "address_line": addr_saved["address_line"],
            "formatted_address": addr_saved["formatted_address"],
            "lat": addr_saved["lat"],
            "lng": addr_saved["lng"],
            "is_verified": True,
            "items": [{"product_id": self.test_prod_id, "quantity": 1}],
        }
        res_checkout = self.client.post("/api/v1/store/orders/checkout", json=checkout_payload)
        self.assertEqual(res_checkout.status_code, 200)
        order_data = res_checkout.json()
        order_code = order_data["order_code"]

        # Bước 7: Xác thực snapshot lưu trữ trong cơ sở dữ liệu
        order_db = self.db.scalar(select(Order).where(Order.order_code == order_code))
        self.assertIsNotNone(order_db)
        self.assertEqual(order_db.customer_name, "Nguyễn Văn Sinh Viên")
        self.assertEqual(order_db.customer_phone, "0912345678")
        self.assertEqual(order_db.province_code, "01")
        self.assertEqual(order_db.commune_code_current, "011051")
        self.assertEqual(order_db.lat, gate_lat)
        self.assertEqual(order_db.lng, gate_lng)
        self.assertTrue(order_db.is_verified)
        self.assertEqual(order_db.note, "Giao tại cổng trường, gọi trước 5 phút")


if __name__ == "__main__":
    unittest.main()

