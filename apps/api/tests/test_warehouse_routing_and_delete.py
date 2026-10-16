import time
import unittest
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import (
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderFulfillment,
    PriceObservation,
    ProductSku,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus, UserRole
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.geo_service import GeoService


class TestWarehouseRoutingAndDeleteSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()

        # Đảm bảo có 2 kho hàng cơ bản: KHO-HCM-01 (Central) và KHO-HN-01
        self.wh_hcm = self.db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not self.wh_hcm:
            self.wh_hcm = Warehouse(
                code="KHO-HCM-01",
                name="Tổng kho Miền Nam (Tân Bình)",
                address="45 Hoàng Hoa Thám, P.13, Q. Tân Bình, TP. Hồ Chí Minh",
                lat=10.7872,
                lng=106.7001,
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
                lat=21.0253,
                lng=105.8552,
                is_active=True,
                is_central=False,
            )
            self.db.add(self.wh_hn)
            self.db.commit()
            self.db.refresh(self.wh_hn)

        # Admin user
        self.admin = self.db.query(User).filter_by(email="admin_wh_test@pharmatrust.vn").first()
        if not self.admin:
            self.admin = User(
                email="admin_wh_test@pharmatrust.vn",
                full_name="Admin Warehouse Test",
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
                registration_number=f"VD-{prod_id:05d}-26",
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=RxOtcStatus.OTC,
                publish_status=PublishStatus.PUBLISHED,
            )
            self.db.add(prod)
            self.db.commit()
            self.db.refresh(prod)

        price_obs = self.db.query(PriceObservation).filter_by(product_id=prod_id).first()
        if not price_obs:
            price_obs = PriceObservation(
                product_id=prod_id,
                source_id=1,
                source_url=f"https://example.com/p/{prod_id}",
                observed_price=price,
            )
            self.db.add(price_obs)
            self.db.commit()

        sku = self.db.query(ProductSku).filter_by(canonical_product_id=prod_id).first()
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod_id,
                sku_code=f"SKU-{prod_id}-BOX",
                barcode=f"893{prod_id:09d}",
                uom="Hộp",
                conversion_rate=1,
                base_price=price,
                is_default=True,
                is_active=True,
            )
            self.db.add(sku)
            self.db.commit()
            self.db.refresh(sku)

        return prod, sku

    def test_01_delete_empty_new_warehouse_hard_deletes(self):
        """Kho mới tạo chưa phát sinh dữ liệu được xóa vật lý (Hard Delete) khỏi database."""
        ts = int(time.time() * 1000) % 100000
        code = f"KHO-EMPTY-{ts}"
        create_res = self.client.post(
            "/api/v1/warehouses",
            headers=self.headers,
            json={
                "code": code,
                "name": f"Kho Tạm Thời {ts}",
                "address": "Số 99 Phố Trống, Cần Thơ",
                "province": "Thành phố Cần Thơ",
                "lat": 10.0452,
                "lng": 105.7469,
            },
        )
        self.assertEqual(create_res.status_code, 201, create_res.text)
        new_wh_id = create_res.json()["id"]

        # Thực hiện xóa kho
        del_res = self.client.delete(f"/api/v1/warehouses/{new_wh_id}", headers=self.headers)
        self.assertEqual(del_res.status_code, 200, del_res.text)
        del_data = del_res.json()
        self.assertEqual(del_data["action"], "HARD_DELETE")
        self.assertEqual(del_data["status"], "deleted")

        # Kiểm tra database không còn kho này
        wh_in_db = self.db.get(Warehouse, new_wh_id)
        self.assertIsNone(wh_in_db)

    def test_02_delete_warehouse_with_stock_or_orders_soft_deletes(self):
        """Kho đã có tồn kho/giao dịch được chuyển sang 'Ngừng hoạt động' (Soft Delete, is_active=False)."""
        ts = int(time.time() * 1000) % 100000
        code = f"KHO-USED-{ts}"
        wh = Warehouse(
            code=code,
            name=f"Kho Có Tồn Kho {ts}",
            address="Số 88 Đường Giao Dịch, Đà Nẵng",
            province="Thành phố Đà Nẵng",
            lat=16.0544,
            lng=108.2022,
            is_active=True,
            is_central=False,
        )
        self.db.add(wh)
        self.db.commit()
        self.db.refresh(wh)

        # Thêm 1 lô tồn kho vào kho này
        _, sku = self._setup_product(71000 + ts % 1000, "Thuốc Giảm Đau Test", Decimal("45000.0"))
        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-USED-{ts}",
            expiry_date=date.today() + timedelta(days=200),
            initial_quantity=20,
            status="ACTIVE",
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=20,
            quantity_reserved=0,
            quantity_available=20,
        )
        self.db.add(stock)
        self.db.commit()

        # Thực hiện xóa kho
        del_res = self.client.delete(f"/api/v1/warehouses/{wh.id}", headers=self.headers)
        self.assertEqual(del_res.status_code, 200, del_res.text)
        del_data = del_res.json()
        self.assertEqual(del_data["action"], "SOFT_DELETE")
        self.assertEqual(del_data["status"], "deactivated")

        # Kiểm tra database: kho vẫn tồn tại nhưng is_active = False
        self.db.expire_all()
        wh_after = self.db.get(Warehouse, wh.id)
        self.assertIsNotNone(wh_after)
        self.assertFalse(wh_after.is_active)

    def test_03_delete_sole_central_warehouse_is_blocked(self):
        """Không cho phép xóa Kho Tổng Trung Tâm duy nhất đang hoạt động."""
        del_res = self.client.delete(f"/api/v1/warehouses/{self.wh_hcm.id}", headers=self.headers)
        self.assertEqual(del_res.status_code, 400)
        self.assertIn("Kho Tổng Trung Tâm duy nhất", del_res.json()["detail"])

    def test_04_order_routing_routes_to_nearest_created_active_warehouse(self):
        """Đơn hàng ở địa phương gần kho chưa tạo tự động điều phối về kho đã tạo gần nhất."""
        ts = int(time.time() * 1000) % 100000
        pid = 75000 + ts % 1000
        _, sku = self._setup_product(pid, "Paracetamol 500mg Kháng Viêm", Decimal("50000.0"))
        today = date.today()

        # Đảm bảo kho KHO-HN-01 có hàng
        b_hn = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-HN-ROUTING-{ts}",
            expiry_date=today + timedelta(days=365),
            initial_quantity=100,
            status="ACTIVE",
        )
        self.db.add(b_hn)
        self.db.commit()
        self.db.refresh(b_hn)

        s_hn = WarehouseBatchStock(
            warehouse_id=self.wh_hn.id,
            batch_id=b_hn.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            quantity_available=100,
        )
        self.db.add(s_hn)

        # Đảm bảo kho KHO-HCM-01 cũng có hàng
        b_hcm = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"LOT-HCM-ROUTING-{ts}",
            expiry_date=today + timedelta(days=365),
            initial_quantity=100,
            status="ACTIVE",
        )
        self.db.add(b_hcm)
        self.db.commit()
        self.db.refresh(b_hcm)

        s_hcm = WarehouseBatchStock(
            warehouse_id=self.wh_hcm.id,
            batch_id=b_hcm.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            quantity_available=100,
        )
        self.db.add(s_hcm)
        self.db.commit()

        # Khách hàng đặt đơn tại Đà Nẵng (nơi chưa có kho được tạo)
        order_payload = {
            "customer_name": "Lê Hoàng Đà Nẵng",
            "customer_phone": "0987654321",
            "customer_email": "danang.customer@example.com",
            "shipping_address": "Số 150 Nguyễn Văn Linh, Phường Hải Châu 1, Đà Nẵng",
            "shipping_city": "Đà Nẵng",
            "province_code": "48",
            "commune_code": "481385",
            "is_verified": True,
            "lat": 16.0544,
            "lng": 108.2022,
            "payment_method": "COD",
            "items": [{"product_id": pid, "quantity": 2}],
        }

        resp = self.client.post("/api/v1/store/orders/checkout", json=order_payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        # Đơn hàng phải được gán vào 1 kho đã tạo thực tế (KHO-HN-01 hoặc KHO-HCM-01)
        # Tuyệt đối không gán vào bất kỳ kho ảo hay kho chưa tạo nào
        self.assertIn("fulfillments", data)
        self.assertEqual(len(data["fulfillments"]), 1)
        assigned_wh_code = data["fulfillments"][0]["warehouse_code"]
        self.assertIn(assigned_wh_code, ["KHO-HN-01", "KHO-HCM-01"])

        # Do Đà Nẵng gần Hà Nội hơn (605 km vs 612 km), hệ thống ưu tiên KHO-HN-01
        self.assertEqual(assigned_wh_code, "KHO-HN-01")

    def test_05_calculate_shipping_endpoint_returns_nearest_active_warehouse(self):
        """API /api/v1/addresses/calculate-shipping trả về kho đã tạo gần nhất chính xác."""
        resp = self.client.post(
            "/api/v1/addresses/calculate-shipping",
            json={
                "address": "Số 10 Đường 30 Tháng 4, Phường An Phú, Ninh Kiều, Cần Thơ",
                "province_code": "92",
                "order_total": 350000,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        res_data = resp.json()

        # Cần Thơ đã có KHO-CT-01 hoặc nếu chưa tạo thì về KHO-HCM-01 gần nhất
        self.assertIn(res_data["warehouse_code"], ["KHO-CT-01", "KHO-HCM-01"])
        self.assertTrue(res_data["is_free_shipping"])
        self.assertEqual(res_data["shipping_fee"], 0)
        self.assertGreater(res_data["distance_km"], 0)


if __name__ == "__main__":
    unittest.main()
