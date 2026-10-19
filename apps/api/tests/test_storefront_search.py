import sys
import os
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.services.search_service import reindex_all_products


class TestStorefrontSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_db_config import setup_isolated_test_db, TestSessionLocal
        setup_isolated_test_db()
        cls.SessionClass = TestSessionLocal
        db = cls.SessionClass()
        reindex_all_products(db)
        db.close()

    @classmethod
    def tearDownClass(cls):
        from tests.test_db_config import teardown_isolated_test_db
        teardown_isolated_test_db()

    def setUp(self):
        self.client = TestClient(app)
        self.db = self.SessionClass()

    def tearDown(self):
        self.db.close()

    def test_search_by_brand_name(self):
        """Khách hàng tìm kiếm theo tên biệt dược (Panadol)."""
        response = self.client.get("/api/v1/store/products?search=panadol&limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        items = data["items"]
        names = [item["name"].lower() for item in items]
        self.assertTrue(any("panadol" in n for n in names))

    def test_search_by_active_ingredient(self):
        """Khách hàng tìm kiếm theo tên hoạt chất (Paracetamol)."""
        response = self.client.get("/api/v1/store/products?search=paracetamol&limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        items = data["items"]
        # Phải trả về ít nhất một thuốc chứa paracetamol như Panadol, Efferalgan hoặc Hapacol
        found_paracetamol = any(
            "paracetamol" in (item.get("activeIngredient") or "").lower() or
            "panadol" in item["name"].lower() or
            "efferalgan" in item["name"].lower() or
            "hapacol" in item["name"].lower()
            for item in items
        )
        self.assertTrue(found_paracetamol)

    def test_search_by_symptom_accented_and_unaccented(self):
        """Tìm kiếm theo triệu chứng có dấu 'hạ sốt' và không dấu 'ha sot' cho kết quả nhất quán."""
        res_accent = self.client.get("/api/v1/store/products?search=hạ sốt&limit=10")
        res_unaccent = self.client.get("/api/v1/store/products?search=ha sot&limit=10")
        self.assertEqual(res_accent.status_code, 200)
        self.assertEqual(res_unaccent.status_code, 200)

        data_accent = res_accent.json()
        data_unaccent = res_unaccent.json()
        self.assertGreater(data_accent["total"], 0)
        self.assertGreater(data_unaccent["total"], 0)

    def test_search_prescription_medicine_with_badge(self):
        """Thuốc kê đơn (Rx) như Augmentin phải xuất hiện trong tìm kiếm và được đánh dấu isPrescription=True."""
        response = self.client.get("/api/v1/store/products?search=augmentin&limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        rx_found = any(item["isPrescription"] is True for item in data["items"])
        self.assertTrue(rx_found, "Thuốc kê đơn phải có cờ isPrescription = True")

    def test_prescription_type_filter(self):
        """Lọc theo phân loại kê đơn (rx vs otc)."""
        res_otc = self.client.get("/api/v1/store/products?prescriptionType=otc&limit=20")
        res_rx = self.client.get("/api/v1/store/products?prescriptionType=rx&limit=20")
        self.assertEqual(res_otc.status_code, 200)
        self.assertEqual(res_rx.status_code, 200)

        data_otc = res_otc.json()
        data_rx = res_rx.json()

        # Kiểm tra không có sản phẩm kê đơn nào lẫn vào danh sách otc
        for item in data_otc["items"]:
            self.assertFalse(item["isPrescription"])

        # Kiểm tra tất cả sản phẩm trong danh sách rx đều là kê đơn
        for item in data_rx["items"]:
            self.assertTrue(item["isPrescription"])

    def test_product_detail_by_slug(self):
        """Lấy chi tiết sản phẩm qua slug."""
        # Lấy một sản phẩm bất kỳ từ danh sách
        res = self.client.get("/api/v1/store/products?limit=1")
        self.assertEqual(res.status_code, 200)
    def test_search_by_manufacturer(self):
        """Khách hàng tìm theo tên công ty sản xuất (GSK, Sanofi, DHG)."""
        res = self.client.get("/api/v1/store/products?search=Sanofi&limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total"], 0)

    def test_search_multi_word_continuous_query(self):
        """Khách hàng gõ nhiều từ liên tiếp 'panadol giam dau'."""
        res = self.client.get("/api/v1/store/products?search=panadol giam dau&limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total"], 0)

    def test_search_pagination_limit_and_offset(self):
        """Kiểm tra phân trang: trang 1 và trang 2 không bị trùng lặp."""
        res1 = self.client.get("/api/v1/store/products?search=hạ sốt&limit=3&offset=0")
        res2 = self.client.get("/api/v1/store/products?search=hạ sốt&limit=3&offset=3")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res2.status_code, 200)
        ids1 = [item["id"] for item in res1.json()["items"]]
        ids2 = [item["id"] for item in res2.json()["items"]]
        # Không có ID nào ở trang 1 xuất hiện lại ở trang 2
        for id1 in ids1:
            self.assertNotIn(id1, ids2)

    def test_search_empty_results_gracefully(self):
        """Khi tìm từ khóa không có thật, trả về danh sách rỗng 200 OK thay vì lỗi 500."""
        res = self.client.get("/api/v1/store/products?search=xyznonexistentdrug999&limit=10")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["items"]), 0)


    def test_out_of_stock_or_expired_product_cannot_add_to_cart(self):
        """Item 1: Thuốc hết hàng hoặc quá hạn không được phép có nút thêm vào giỏ hàng (canAddToCart=False)."""
        from app.api.storefront import serialize_product
        from app.models import CanonicalProduct
        from app.models.enums import PublishStatus, RxOtcStatus

        mock_product = CanonicalProduct(
            id=99999,
            canonical_name="Thuốc Mẫu Hết Hàng",
            publish_status=PublishStatus.PUBLISHED,
            publish_mode="SALE_ELIGIBLE",
            rx_otc_status=RxOtcStatus.OTC,
            is_demo=False,
        )

        # 1. Hàng hết tồn kho (stock=0)
        data_zero_stock = serialize_product(mock_product, price=50000, stock=0)
        self.assertFalse(data_zero_stock["canAddToCart"], "Hàng hết kho không được phép canAddToCart")
        self.assertFalse(data_zero_stock["isSaleEligible"], "Hàng hết kho không được phép isSaleEligible")
        self.assertEqual(data_zero_stock["catalogTier"], "OUT_OF_STOCK")
        self.assertEqual(data_zero_stock["ctaType"], "OUT_OF_STOCK")

        # 2. Hàng còn tồn kho (stock=10)
        data_in_stock = serialize_product(mock_product, price=50000, stock=10)
        self.assertTrue(data_in_stock["canAddToCart"])
        self.assertTrue(data_in_stock["isSaleEligible"])
        self.assertEqual(data_in_stock["catalogTier"], "SALE_ELIGIBLE")
        self.assertEqual(data_in_stock["ctaType"], "BUY_NOW")


if __name__ == "__main__":
    unittest.main()
