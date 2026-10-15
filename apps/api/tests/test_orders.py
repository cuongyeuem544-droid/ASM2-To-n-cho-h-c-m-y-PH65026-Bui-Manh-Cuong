import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.main import app
from app.models.entities import CanonicalProduct, Order, OrderItem, User
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus, UserRole
from app.core.security import create_access_token


class TestOrdersSystem(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.db = SessionLocal()

        # Tạo sản phẩm mẫu
        self.prod = CanonicalProduct(
            id=501,
            canonical_name="Thuốc hạ sốt Hapacol 250mg",
            registration_number="VD-11223-19",
            regulatory_status=RegulatoryStatus.ACTIVE,
            rx_otc_status=RxOtcStatus.OTC,
            publish_status=PublishStatus.PUBLISHED,
            publish_mode="SALE_ELIGIBLE",
        )
        self.db.merge(self.prod)

        # Tạo giá bán niêm yết mẫu từ hệ thống (PriceObservation)
        from app.models.entities import PriceObservation
        price_obs = self.db.query(PriceObservation).filter_by(product_id=501).first()
        if not price_obs:
            price_obs = PriceObservation(
                product_id=501,
                source_id=1,
                source_url="https://example.com/products/hapacol-250",
                observed_price=Decimal("45000.0"),
            )
            self.db.add(price_obs)
        else:
            price_obs.observed_price = Decimal("45000.0")
        self.db.commit()

        # Tạo kho, SKU và lô tồn kho kiểm thử cho sản phẩm 501
        from datetime import date, timedelta
        from app.models import InventoryBatch, ProductSku, Warehouse, WarehouseBatchStock

        wh = self.db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not wh:
            wh = Warehouse(
                code="KHO-HCM-01",
                name="Kho HCM Test",
                address="123 Lê Lợi, Q1, HCM",
                is_active=True,
                is_central=True,
            )
            self.db.add(wh)
            self.db.commit()
            self.db.refresh(wh)

        sku = self.db.query(ProductSku).filter_by(canonical_product_id=501).first()
        if not sku:
            sku = ProductSku(
                canonical_product_id=501,
                sku_code="SKU-501-TEST",
                base_price=Decimal("45000.0"),
                is_default=True,
                is_active=True,
            )
            self.db.add(sku)
            self.db.commit()
            self.db.refresh(sku)

        batch = self.db.query(InventoryBatch).filter_by(sku_id=sku.id).first()
        if not batch:
            batch = InventoryBatch(
                sku_id=sku.id,
                batch_number="LOT-501-TEST",
                expiry_date=date.today() + timedelta(days=365),
                initial_quantity=1000,
                status="ACTIVE",
            )
            self.db.add(batch)
            self.db.commit()
            self.db.refresh(batch)

        stock = self.db.query(WarehouseBatchStock).filter_by(warehouse_id=wh.id, batch_id=batch.id).first()
        if not stock:
            stock = WarehouseBatchStock(
                warehouse_id=wh.id,
                batch_id=batch.id,
                quantity_on_hand=1000,
                quantity_reserved=0,
                quantity_available=1000,
            )
            self.db.add(stock)
        else:
            stock.quantity_available = 1000
            stock.quantity_on_hand = 1000
        self.db.commit()

        # Tạo admin user
        self.admin = self.db.query(User).filter_by(email="admin_orders@pharmatrust.vn").first()
        if not self.admin:
            self.admin = User(
                email="admin_orders@pharmatrust.vn",
                full_name="Admin Orders",
                role=UserRole.ADMIN,
                password_hash="test_hash",
                is_active=True,
            )
            self.db.add(self.admin)
            self.db.commit()
            self.db.refresh(self.admin)

        token = create_access_token(str(self.admin.id), self.admin.role.value)
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        # Cleanup test orders
        test_orders = self.db.query(Order).filter(Order.order_code.like("PT-%")).all()
        for o in test_orders:
            self.db.delete(o)
        self.db.commit()
        self.db.close()

    def test_01_storefront_checkout_order(self):
        """Khách hàng đặt hàng từ Storefront tạo đơn thành công và lưu CSDL."""
        payload = {
            "customer_name": "Nguyễn Văn An",
            "customer_phone": "0987654321",
            "customer_email": "an.nguyen@example.com",
            "shipping_address": "Số 123 Đường Cầu Giấy, Hà Nội",
            "shipping_city": "Hà Nội",
            "province_code": "01",
            "district_code": "009",
            "ward_code": "00142",
            "lat": 21.0362,
            "lng": 105.7906,
            "is_verified": True,
            "payment_method": "COD",
            "note": "Giao giờ hành chính",
            "items": [
                {
                    "product_id": 501,
                    "quantity": 2,
                }
            ],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertEqual(data["status"], "SUCCESS")
        self.assertTrue(data["order_code"].startswith("PT-"))
        self.assertIn(data["total_amount"], [95000.0, 105000.0, 115000.0, 135000.0])
        self.assertIn(data["shipping_fee"], [15000.0, 25000.0, 45000.0])
        self.assertEqual(data["order_status"], "PENDING")

        # Kiểm tra CSDL
        order_in_db = self.db.query(Order).filter_by(order_code=data["order_code"]).first()
        self.assertIsNotNone(order_in_db)
        self.assertEqual(order_in_db.customer_name, "Nguyễn Văn An")
        self.assertEqual(len(order_in_db.items), 1)
        self.assertEqual(order_in_db.items[0].quantity, 2)
        self.assertIn(order_in_db.items[0].subtotal, [Decimal("80000.0"), Decimal("90000.0")])

    def test_02_get_order_by_code(self):
        """Khách tra cứu thông tin đơn hàng qua mã đơn."""
        # Dọn dẹp đơn cũ nếu còn tồn tại
        old = self.db.query(Order).filter_by(order_code="PT-260927-9999").first()
        if old:
            self.db.delete(old)
            self.db.commit()

        # Tạo trước 1 đơn hàng
        order = Order(
            order_code="PT-260927-9999",
            customer_name="Trần Thị Bình",
            customer_phone="0912345678",
            shipping_address="456 Hai Bà Trưng, TP.HCM",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("150000.0"),
            items=[
                OrderItem(
                    product_id=501,
                    product_name="Thuốc hạ sốt Hapacol 250mg",
                    price=Decimal("50000.0"),
                    quantity=3,
                    subtotal=Decimal("150000.0"),
                )
            ],
        )
        self.db.add(order)
        self.db.commit()

        # 1. Truy cập không cung cấp SĐT / Token -> 401 Unauthorized hoặc 403 Forbidden
        resp_unauth = self.client.get(f"/api/v1/store/orders/{order.order_code}")
        self.assertIn(resp_unauth.status_code, [401, 403])

        # 2. Truy cập với sai SĐT -> 403 Forbidden
        resp_wrong = self.client.get(f"/api/v1/store/orders/{order.order_code}?phone=0999999999")
        self.assertEqual(resp_wrong.status_code, 403)

        # 3. Truy cập chỉ với SĐT (không có token) -> 403 Forbidden (chặn IDOR số điện thoại)
        resp_phone_only = self.client.get(f"/api/v1/store/orders/{order.order_code}?phone={order.customer_phone}")
        self.assertEqual(resp_phone_only.status_code, 403)
        self.assertIn("Số điện thoại không phải là bằng chứng duy nhất", resp_phone_only.json()["detail"])

        # 4. Truy cập với token bảo mật hợp lệ (guest order token) -> 200 OK
        from app.core.security import create_guest_order_token
        valid_token = create_guest_order_token(order.order_code, order.customer_phone)
        resp = self.client.get(f"/api/v1/store/orders/{order.order_code}", headers={"X-Order-Token": valid_token})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["order_code"], "PT-260927-9999")
        self.assertEqual(data["customer_name"], "Trần Thị Bình")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["quantity"], 3)

    def test_03_admin_list_and_update_status(self):
        """Admin xem danh sách đơn hàng và chuyển trạng thái."""
        # Tạo trước 1 đơn hàng độc lập cho test_03
        order = Order(
            order_code="PT-260927-8888",
            customer_name="Lê Văn Cường",
            customer_phone="0933333333",
            shipping_address="789 Điện Biên Phủ, TP.HCM",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("100000.0"),
            items=[
                OrderItem(
                    product_id=501,
                    product_name="Thuốc hạ sốt Hapacol 250mg",
                    price=Decimal("50000.0"),
                    quantity=2,
                    subtotal=Decimal("100000.0"),
                )
            ],
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        # Lấy danh sách
        resp = self.client.get("/api/v1/admin/orders", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)
        self.assertGreaterEqual(len(data["items"]), 1)

        # 1. Cố tình cập nhật trực tiếp payment_status sang PAID qua API thông thường -> Phải bị từ chối với HTTP 400
        forbidden_resp = self.client.patch(
            f"/api/v1/admin/orders/{order.id}/status",
            headers=self.headers,
            json={"order_status": "CONFIRMED", "payment_status": "PAID"},
        )
        self.assertEqual(forbidden_resp.status_code, 400)
        self.assertIn("Không được phép thay đổi trực tiếp payment_status sang PAID", forbidden_resp.json()["detail"])

        # 2. Cập nhật order_status hợp lệ -> 200 OK
        update_resp = self.client.patch(
            f"/api/v1/admin/orders/{order.id}/status",
            headers=self.headers,
            json={"order_status": "CONFIRMED"},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["order_status"], "CONFIRMED")

        self.db.refresh(order)
        self.assertEqual(order.order_status, "CONFIRMED")
        self.assertEqual(order.payment_status, "PENDING")


if __name__ == "__main__":
    unittest.main()
