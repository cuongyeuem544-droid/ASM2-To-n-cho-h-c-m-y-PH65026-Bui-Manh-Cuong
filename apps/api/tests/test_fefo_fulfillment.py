import os
import sys
import time
import unittest
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import (
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItemBatchAllocation,
    PriceObservation,
    ProductSku,
    StockMovement,
    StockReservation,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus, UserRole
from app.core.security import create_access_token


class TestFefoFulfillmentSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()

        # Đảm bảo có 2 kho hàng: KHO-HCM-01 và KHO-HN-01
        self.wh_hcm = self.db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not self.wh_hcm:
            self.wh_hcm = Warehouse(
                code="KHO-HCM-01",
                name="Tổng kho Miền Nam (Tân Bình)",
                address="45 Hoàng Hoa Thám, P.13, Q. Tân Bình, TP. Hồ Chí Minh",
                is_active=True,
                is_central=True,
            )
            self.db.add(self.wh_hcm)
            self.db.commit()
            self.db.refresh(self.wh_hcm)

        self.wh_hn = self.db.query(Warehouse).filter_by(code="KHO-HN-01").first()
        if not self.wh_hn:
            self.wh_hn = Warehouse(
                code="KHO-HN-01",
                name="Kho Miền Bắc (Cầu Giấy)",
                address="12 Cầu Giấy, Q. Cầu Giấy, Hà Nội",
                is_active=True,
                is_central=False,
            )
            self.db.add(self.wh_hn)
            self.db.commit()
            self.db.refresh(self.wh_hn)

        # Admin user
        self.admin = self.db.query(User).filter_by(email="admin_fefo@pharmatrust.vn").first()
        if not self.admin:
            self.admin = User(
                email="admin_fefo@pharmatrust.vn",
                full_name="Admin FEFO",
                role=UserRole.ADMIN,
                password_hash="test_pass",
                is_active=True,
            )
            self.db.add(self.admin)
            self.db.commit()
            self.db.refresh(self.admin)

        token = create_access_token(str(self.admin.id), self.admin.role.value)
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.close()

    def _setup_product(self, prod_id: int, name: str, price: Decimal) -> tuple[CanonicalProduct, ProductSku]:
        prod = self.db.get(CanonicalProduct, prod_id)
        if not prod:
            prod = CanonicalProduct(
                id=prod_id,
                canonical_name=name,
                registration_number=f"VD-{prod_id:05d}-22",
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=RxOtcStatus.OTC,
                publish_status=PublishStatus.PUBLISHED,
            )
            self.db.add(prod)
            self.db.commit()
            self.db.refresh(prod)

        prod.publish_mode = "SALE_ELIGIBLE"
        prod.publish_status = PublishStatus.PUBLISHED
        prod.is_demo = False
        self.db.commit()

        price_obs = self.db.query(PriceObservation).filter_by(product_id=prod_id).first()
        if not price_obs:
            price_obs = PriceObservation(
                product_id=prod_id,
                source_id=1,
                source_url=f"https://example.com/p/{prod_id}",
                observed_price=price,
            )
            self.db.add(price_obs)
        else:
            price_obs.observed_price = price
        self.db.commit()

        sku = self.db.query(ProductSku).filter_by(canonical_product_id=prod_id).first()
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod_id,
                sku_code=f"SKU-{prod_id:04d}-TEST",
                base_price=price,
                is_default=True,
                is_active=True,
            )
            self.db.add(sku)
            self.db.commit()
            self.db.refresh(sku)

        return prod, sku

    def test_01_north_province_routing_prefers_hanoi_warehouse(self):
        """Khách hàng ở khu vực phía Bắc tự động được định tuyến ưu tiên kho Hà Nội (KHO-HN-01)."""
        import random
        pid = random.randint(80000, 89999)
        prod, sku = self._setup_product(pid, "Vitamin C 500mg Dược Hậu Giang", Decimal("60000.0"))
        today = date.today()
        ts = int(time.time() * 1000) % 1000000

        b_hn = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-HN-8801-{ts}",
            expiry_date=today + timedelta(days=180),
            initial_quantity=50,
            status="ACTIVE",
        )
        self.db.add(b_hn)
        self.db.commit()
        self.db.refresh(b_hn)

        s_hn = WarehouseBatchStock(
            warehouse_id=self.wh_hn.id,
            batch_id=b_hn.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        )
        self.db.add(s_hn)
        self.db.commit()

        payload = {
            "customer_name": "Trần Văn Bắc",
            "customer_phone": "0912345678",
            "customer_email": "bac.tran@example.com",
            "shipping_address": "Số 25 Phố Huế, P. Hàng Bài, Q. Hoàn Kiếm, Hà Nội",
            "shipping_city": "Hà Nội",
            "province_code": "01",
            "district_code": "002",
            "ward_code": "00049",
            "lat": 21.0285,
            "lng": 105.8542,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": pid, "quantity": 3}],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertIn("fulfillments", data)
        self.assertEqual(len(data["fulfillments"]), 1)
        self.assertEqual(data["fulfillments"][0]["warehouse_code"], "KHO-HN-01")

    def test_02_fefo_allocation_earliest_expiry_first(self):
        """Thuật toán FEFO luôn chọn lô có hạn dùng gần nhất trước, bỏ qua lô hết hạn."""
        import random
        pid = random.randint(90000, 99999)
        prod, sku = self._setup_product(pid, "Siro Ho Prospan 100ml", Decimal("85000.0"))
        today = date.today()
        ts = int(time.time() * 1000) % 1000000

        # Tạo Lô 1: Hết hạn (đã quá đát) -> Phải bị bỏ qua
        b_expired = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-8802-EXP-{ts}",
            expiry_date=today - timedelta(days=10),
            initial_quantity=100,
            status="ACTIVE",
        )
        # Tạo Lô 2: Còn hạn 200 ngày (đạt chuẩn FEFO >= 180 ngày, cận hạn nhất) -> Phải xuất trước
        b_near = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-8802-NEAR-{ts}",
            expiry_date=today + timedelta(days=200),
            initial_quantity=5,
            status="ACTIVE",
        )
        # Tạo Lô 3: Còn hạn 365 ngày (xa hơn) -> Phải xuất sau
        b_fresh = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-8802-FRESH-{ts}",
            expiry_date=today + timedelta(days=365),
            initial_quantity=20,
            status="ACTIVE",
        )
        self.db.add_all([b_expired, b_near, b_fresh])
        self.db.commit()
        for b in [b_expired, b_near, b_fresh]:
            self.db.refresh(b)

        # Gán tồn kho tại KHO-HCM-01
        self.db.add(WarehouseBatchStock(warehouse_id=self.wh_hcm.id, batch_id=b_expired.id, quantity_on_hand=100, quantity_available=100, quantity_reserved=0))
        self.db.add(WarehouseBatchStock(warehouse_id=self.wh_hcm.id, batch_id=b_near.id, quantity_on_hand=5, quantity_available=5, quantity_reserved=0))
        self.db.add(WarehouseBatchStock(warehouse_id=self.wh_hcm.id, batch_id=b_fresh.id, quantity_on_hand=20, quantity_available=20, quantity_reserved=0))
        self.db.commit()

        # Đặt 8 hộp: Cần 5 hộp từ Lô cận hạn (b_near) + 3 hộp từ Lô mới (b_fresh)
        payload = {
            "customer_name": "Lê Thị Thảo",
            "customer_phone": "0901234567",
            "customer_email": "thao.le@example.com",
            "shipping_address": "12 Điện Biên Phủ, P. Đa Kao, Q.1, TP. Hồ Chí Minh",
            "shipping_city": "Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26746",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": pid, "quantity": 8}],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        ff = data["fulfillments"][0]
        self.assertEqual(ff["warehouse_code"], "KHO-HCM-01")
        batches_allocated = ff["items"][0]["batches"]
        self.assertEqual(len(batches_allocated), 2)

        # Lô cận hạn lấy hết 5
        self.assertEqual(batches_allocated[0]["batch_number"], b_near.batch_number)
        self.assertEqual(batches_allocated[0]["allocated_quantity"], 5)

        # Lô mới lấy 3
        self.assertEqual(batches_allocated[1]["batch_number"], b_fresh.batch_number)
        self.assertEqual(batches_allocated[1]["allocated_quantity"], 3)

        # Lô hết hạn không bao giờ được chọn
        allocated_batch_nums = [b["batch_number"] for b in batches_allocated]
        self.assertNotIn(b_expired.batch_number, allocated_batch_nums)

    def test_03_split_order_when_single_warehouse_insufficient(self):
        """Tách đơn đa kho (Split Order): Khi không kho nào đơn lẻ đủ hàng, chia kiện giữa các kho."""
        import random
        pid = random.randint(100000, 109999)
        prod, sku = self._setup_product(pid, "Thuốc dị ứng Telfast HD 180mg", Decimal("120000.0"))
        today = date.today()
        ts = int(time.time() * 1000) % 1000000

        # KHO-HCM-01 có 4 hộp
        b_hcm = InventoryBatch(sku_id=sku.id, batch_number=f"LOT-8803-HCM-{ts}", expiry_date=today + timedelta(days=200), initial_quantity=4, status="ACTIVE")
        self.db.add(b_hcm)
        self.db.commit()
        self.db.refresh(b_hcm)
        self.db.add(WarehouseBatchStock(warehouse_id=self.wh_hcm.id, batch_id=b_hcm.id, quantity_on_hand=4, quantity_available=4, quantity_reserved=0))

        # KHO-HN-01 có 6 hộp
        b_hn = InventoryBatch(sku_id=sku.id, batch_number=f"LOT-8803-HN-{ts}", expiry_date=today + timedelta(days=200), initial_quantity=6, status="ACTIVE")
        self.db.add(b_hn)
        self.db.commit()
        self.db.refresh(b_hn)
        self.db.add(WarehouseBatchStock(warehouse_id=self.wh_hn.id, batch_id=b_hn.id, quantity_on_hand=6, quantity_available=6, quantity_reserved=0))
        self.db.commit()

        # Đặt 7 hộp: Không kho nào có đủ 7, nhưng tổng hệ thống có 10
        payload = {
            "customer_name": "Vũ Hải Đăng",
            "customer_phone": "0933221100",
            "customer_email": "dang.vu@example.com",
            "shipping_address": "88 Pasteur, Bến Nghé, Quận 1, TP. Hồ Chí Minh",
            "shipping_city": "Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": pid, "quantity": 7}],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        # Đơn phải bị tách thành 2 kiện hàng từ 2 kho khác nhau
        fulfillments = data["fulfillments"]
        self.assertEqual(len(fulfillments), 2)

        wh_codes = {f["warehouse_code"] for f in fulfillments}
        self.assertIn("KHO-HCM-01", wh_codes)
        self.assertIn("KHO-HN-01", wh_codes)

        # Tổng số lượng hàng trong các kiện phải đúng bằng 7
        total_delivered = sum(f["items"][0]["quantity"] for f in fulfillments)
        self.assertEqual(total_delivered, 7)

    def test_04_insufficient_system_stock_rejects_order(self):
        """Từ chối đơn hàng khi toàn bộ hệ thống không đủ hàng khả dụng (HTTP 400)."""
        import random
        pid = random.randint(110000, 119999)
        prod, sku = self._setup_product(pid, "Thuốc nhỏ mắt Rohto 12ml", Decimal("55000.0"))

        # Đặt hàng với số lượng 100 trong khi tồn = 0
        payload = {
            "customer_name": "Phạm Minh Tâm",
            "customer_phone": "0988776655",
            "customer_email": "tam.pham@example.com",
            "shipping_address": "123 Cầu Giấy, Hà Nội",
            "shipping_city": "Hà Nội",
            "province_code": "01",
            "district_code": "009",
            "ward_code": "00142",
            "lat": 21.0362,
            "lng": 105.7906,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": pid, "quantity": 100}],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(
            any(k in resp.json()["detail"] for k in ["Số lượng tồn kho không đủ", "Tạm hết hàng"]),
            resp.json()["detail"],
        )

    def test_05_fulfillment_lifecycle_shipped_updates_stock_and_creates_movement(self):
        """Chuyển trạng thái kiện sang SHIPPED trừ on_hand và ghi Thẻ kho DISPATCH."""
        import random
        pid = random.randint(120000, 129999)
        prod, sku = self._setup_product(pid, "Men vi sinh Enterogermina 20 ống", Decimal("150000.0"))
        today = date.today()
        ts = int(time.time() * 1000) % 1000000

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-8805-DISP-{ts}",
            expiry_date=today + timedelta(days=300),
            initial_quantity=20,
            status="ACTIVE",
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        stock = WarehouseBatchStock(
            warehouse_id=self.wh_hcm.id,
            batch_id=batch.id,
            quantity_on_hand=20,
            quantity_reserved=0,
            quantity_available=20,
        )
        self.db.add(stock)
        self.db.commit()

        # Đặt 5 hộp
        payload = {
            "customer_name": "Hoàng Yến",
            "customer_phone": "0977889900",
            "shipping_address": "15 Lê Lợi, Q1, TP. Hồ Chí Minh",
            "shipping_city": "Hồ Chí Minh",
            "province_code": "79",
            "district_code": "760",
            "ward_code": "26734",
            "lat": 10.7769,
            "lng": 106.7009,
            "is_verified": True,
            "payment_method": "COD",
            "items": [{"product_id": pid, "quantity": 5}],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        fulfillment_id = data["fulfillments"][0]["id"]

        # Kiểm tra tồn sau khi checkout: available giảm còn 15, reserved tăng lên 5, on_hand vẫn là 20
        self.db.refresh(stock)
        self.assertEqual(stock.quantity_available, 15)
        self.assertEqual(stock.quantity_reserved, 5)
        self.assertEqual(stock.quantity_on_hand, 20)

        # Admin chuyển trạng thái kiện qua FSM: PENDING -> PICKED -> PACKED -> SHIPPED
        self.client.patch(
            f"/api/v1/admin/orders/fulfillments/{fulfillment_id}/status",
            json={"status": "PICKED"},
            headers=self.headers,
        )
        self.client.patch(
            f"/api/v1/admin/orders/fulfillments/{fulfillment_id}/status",
            json={"status": "PACKED"},
            headers=self.headers,
        )
        ship_resp = self.client.patch(
            f"/api/v1/admin/orders/fulfillments/{fulfillment_id}/status",
            json={"status": "SHIPPED"},
            headers=self.headers,
        )
        self.assertEqual(ship_resp.status_code, 200, ship_resp.text)

        # Kiểm tra tồn sau khi SHIPPED: on_hand giảm xuống 15, reserved giảm về 0
        self.db.refresh(stock)
        self.assertEqual(stock.quantity_on_hand, 15)
        self.assertEqual(stock.quantity_reserved, 0)
        self.assertEqual(stock.quantity_available, 15)

        # Kiểm tra Thẻ kho (StockMovement) được ghi nhận với loại DISPATCH và số lượng âm (-5)
        movement = (
            self.db.query(StockMovement)
            .filter_by(batch_id=batch.id, movement_type="DISPATCH")
            .order_by(StockMovement.id.desc())
            .first()
        )
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, -5)
        self.assertEqual(movement.balance_after, 15)

        # Kiểm tra Reservation được cập nhật thành FULFILLED
        reservation = self.db.query(StockReservation).filter_by(batch_id=batch.id).first()
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.status, "FULFILLED")


if __name__ == "__main__":
    unittest.main()
