import unittest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import AdministrativeUnit, CustomerAddress, User, Warehouse
from app.models.enums import UserRole
from app.services.geo_service import (
    calculate_haversine_distance,
    get_estimated_delivery_time,
    GeoService,
)


class TestGeoAddressSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()

        # Đảm bảo kho HCM và HN có tọa độ chính xác
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
        else:
            self.wh_hcm.lat = 10.7872
            self.wh_hcm.lng = 106.7001

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
        else:
            self.wh_hn.lat = 21.0253
            self.wh_hn.lng = 105.8552
        self.db.commit()

        # Tạo user khách hàng kiểm thử
        self.cust_user = self.db.query(User).filter_by(email="customer_geo@pharmatrust.vn").first()
        if not self.cust_user:
            self.cust_user = User(
                email="customer_geo@pharmatrust.vn",
                full_name="Khách Hàng Test Geo",
                role=UserRole.CUSTOMER,
                password_hash="pass_geo_123",
                is_active=True,
            )
            self.db.add(self.cust_user)
            self.db.commit()
            self.db.refresh(self.cust_user)

        token = create_access_token(str(self.cust_user.id), self.cust_user.role.value)
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        try:
            self.db.rollback()
        except Exception:
            pass
        self.db.close()

    def test_01_haversine_formula_accuracy(self):
        """Kiểm tra độ chính xác của hàm tính khoảng cách địa lý Haversine."""
        # Khoảng cách giữa 2 điểm trùng nhau = 0
        d_zero = calculate_haversine_distance(10.7872, 106.7001, 10.7872, 106.7001)
        self.assertEqual(d_zero, 0.0)

        # Khoảng cách giữa Kho HCM và Kho HN (~1138 km)
        d_hcm_hn = calculate_haversine_distance(10.7872, 106.7001, 21.0253, 105.8552)
        self.assertGreater(d_hcm_hn, 1100.0)
        self.assertLess(d_hcm_hn, 1200.0)

        # Kiểm tra nhãn ước tính thời gian giao hàng
        self.assertIn("siêu tốc", get_estimated_delivery_time(5.0))
        self.assertIn("trong ngày", get_estimated_delivery_time(25.0))
        self.assertIn("liên tỉnh", get_estimated_delivery_time(500.0))

    def test_02_nearest_warehouse_calculation_by_gps(self):
        """Khách cung cấp tọa độ GPS tại Hà Nội -> Hệ thống chọn kho KHO-HN-01 gần nhất."""
        payload = {
            "lat": 21.0333,
            "lng": 105.7939,
            "address": "Số 12 Cầu Giấy, Hà Nội",
        }
        resp = self.client.post("/api/v1/addresses/nearest-warehouse", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertEqual(data["customer_location"]["source"], "GPS_EXACT")
        self.assertIn(data["nearest_warehouse"]["warehouse_code"], ["KHO-HN-01", "KHO-HN-02"])
        self.assertLess(data["nearest_warehouse"]["distance_km"], 10.0)
        self.assertIn("google.com/maps", data["nearest_warehouse"]["navigation_url"])

    def test_03_nearest_warehouse_by_administrative_code_fallback(self):
        """Khi khách không bật GPS, hệ thống tự động suy diễn từ mã Tỉnh/Quận (79 - TP.HCM)."""
        payload = {
            "province_code": "79",
            "district_code": "760",
            "address": "Quận 1, TP. Hồ Chí Minh",
        }
        resp = self.client.post("/api/v1/addresses/nearest-warehouse", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertEqual(data["customer_location"]["source"], "DISTRICT_CENTROID")
        self.assertEqual(data["nearest_warehouse"]["warehouse_code"], "KHO-HCM-01")
        self.assertLess(data["nearest_warehouse"]["distance_km"], 15.0)

    def test_04_get_administrative_units_tree_and_filter(self):
        """Tra cứu danh mục hành chính 2 cấp (Tỉnh / Thành phố và Quận / Huyện)."""
        # 1. Tra cứu dạng cây (tree=true)
        resp_tree = self.client.get("/api/v1/addresses/administrative-units?tree=true")
        self.assertEqual(resp_tree.status_code, 200)
        tree_data = resp_tree.json()
        self.assertGreater(len(tree_data), 0)
        hcm_node = next((p for p in tree_data if p["code"] == "79"), None)
        self.assertIsNotNone(hcm_node)
        self.assertGreater(len(hcm_node["districts"]), 0)

        # 2. Lọc danh sách Quận thuộc Hà Nội (parent_code=01)
        resp_hn_districts = self.client.get("/api/v1/addresses/administrative-units?level=DISTRICT&parent_code=01")
        self.assertEqual(resp_hn_districts.status_code, 200)
        hn_districts = resp_hn_districts.json()
        self.assertGreater(len(hn_districts), 0)
        for d in hn_districts:
            self.assertEqual(d["parent_code"], "01")

    def test_05_customer_address_book_crud_and_set_default(self):
        """Khách hàng thêm, xem, sửa, xóa và chọn địa chỉ nhận hàng mặc định."""
        # 1. Thêm địa chỉ mới
        create_payload = {
            "recipient_name": "Nguyễn Thị Mai",
            "phone": "0981122334",
            "address_line": "Số 48 Đường Nguyễn Huệ, P. Bến Nghé",
            "province_code": "79",
            "district_code": "760",
            "lat": 10.7745,
            "lng": 106.7034,
            "is_default": True,
        }
        res_create = self.client.post("/api/v1/customer/addresses", json=create_payload, headers=self.headers)
        self.assertEqual(res_create.status_code, 201, res_create.text)
        addr_id = res_create.json()["id"]

        # 2. Lấy danh sách địa chỉ
        res_list = self.client.get("/api/v1/customer/addresses", headers=self.headers)
        self.assertEqual(res_list.status_code, 200)
        addrs = res_list.json()
        self.assertGreater(len(addrs), 0)
        created_addr = next((a for a in addrs if a["id"] == addr_id), None)
        self.assertIsNotNone(created_addr)
        self.assertEqual(created_addr["recipient_name"], "Nguyễn Thị Mai")
        self.assertTrue(created_addr["is_default"])

        # 3. Cập nhật địa chỉ
        update_payload = {"recipient_name": "Nguyễn Thị Mai (Công ty)"}
        res_update = self.client.put(f"/api/v1/customer/addresses/{addr_id}", json=update_payload, headers=self.headers)
        self.assertEqual(res_update.status_code, 200)

        # 4. Thêm địa chỉ thứ 2 và set-default
        create_payload2 = {
            "recipient_name": "Mai Nhà Riêng",
            "phone": "0981122334",
            "address_line": "Số 15 Lê Văn Sỹ",
            "province_code": "79",
            "is_default": False,
        }
        res_create2 = self.client.post("/api/v1/customer/addresses", json=create_payload2, headers=self.headers)
        addr2_id = res_create2.json()["id"]

        res_def = self.client.post(f"/api/v1/customer/addresses/{addr2_id}/set-default", headers=self.headers)
        self.assertEqual(res_def.status_code, 200)

        # Kiểm tra addr2_id là mặc định, addr_id không còn là mặc định
        res_list_after = self.client.get("/api/v1/customer/addresses", headers=self.headers).json()
        a1 = next(a for a in res_list_after if a["id"] == addr_id)
        a2 = next(a for a in res_list_after if a["id"] == addr2_id)
        self.assertFalse(a1["is_default"])
        self.assertTrue(a2["is_default"])

        # 5. Xóa địa chỉ
        res_del = self.client.delete(f"/api/v1/customer/addresses/{addr2_id}", headers=self.headers)
        self.assertEqual(res_del.status_code, 200)


if __name__ == "__main__":
    unittest.main()
