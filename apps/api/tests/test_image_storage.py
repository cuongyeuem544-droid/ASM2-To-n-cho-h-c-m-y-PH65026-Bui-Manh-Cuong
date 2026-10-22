import io
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.entities import CanonicalProduct
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus
from app.services.image_storage import download_and_optimize_image, backfill_product_images, get_product_storage_dir, validate_image_magic_bytes, save_and_optimize_uploaded_image


class TestImageStorageAndOptimization(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()

    def _create_dummy_image_bytes(self, width=1200, height=800, color="blue") -> bytes:
        img = Image.new("RGB", (width, height), color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    @patch("httpx.Client.get")
    def test_01_download_and_optimize_image_success(self, mock_get):
        """Kiểm tra tải ảnh, nén sang WebP (max 800x800) và tạo thumbnail (max 250x250)."""
        raw_bytes = self._create_dummy_image_bytes(width=1200, height=900)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = raw_bytes
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_get.return_value = mock_resp

        main_url, thumb_url = download_and_optimize_image(
            remote_url="https://cdn.example.com/products/panadol.jpg",
            product_id=999,
        )

        self.assertIsNotNone(main_url)
        self.assertIsNotNone(thumb_url)
        self.assertTrue(main_url.startswith("/storage/products/prod_999_"))
        self.assertTrue(main_url.endswith(".webp"))
        self.assertTrue(thumb_url.endswith("_thumb.webp"))

        # Kiểm tra file thực tế trên đĩa
        storage_dir = get_product_storage_dir()
        main_filename = main_url.split("/")[-1]
        thumb_filename = thumb_url.split("/")[-1]

        main_path = storage_dir / main_filename
        thumb_path = storage_dir / thumb_filename

        self.assertTrue(main_path.exists())
        self.assertTrue(thumb_path.exists())

        # Mở lại ảnh đã nén để kiểm tra kích thước
        with Image.open(main_path) as saved_img:
            self.assertEqual(saved_img.format, "WEBP")
            self.assertLessEqual(saved_img.width, 800)
            self.assertLessEqual(saved_img.height, 800)

        with Image.open(thumb_path) as saved_thumb:
            self.assertEqual(saved_thumb.format, "WEBP")
            self.assertLessEqual(saved_thumb.width, 250)
            self.assertLessEqual(saved_thumb.height, 250)

    @patch("httpx.Client.get")
    def test_02_download_failure_handles_gracefully(self, mock_get):
        """Khi server ảnh trả về 404 hoặc timeout, hàm trả về (None, None) an toàn không gây crash."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.content = b""
        mock_get.return_value = mock_resp

        main_url, thumb_url = download_and_optimize_image(
            remote_url="https://cdn.example.com/broken_image.jpg",
            product_id=1001,
        )
        self.assertIsNone(main_url)
        self.assertIsNone(thumb_url)

    def test_03_invalid_or_local_url_skipped(self):
        """Bỏ qua URL cục bộ hoặc URL không hợp lệ."""
        main_url, thumb_url = download_and_optimize_image("/storage/products/test.webp", 1002)
        self.assertEqual(main_url, "/storage/products/test.webp")
        self.assertIsNone(thumb_url)

        m2, t2 = download_and_optimize_image("", 1003)
        self.assertIsNone(m2)
        self.assertIsNone(t2)

    @patch("app.services.image_storage.download_and_optimize_image")
    def test_04_backfill_product_images(self, mock_download):
        """Kiểm tra chức năng quét và tải ảnh hàng loạt cho sản phẩm trong CSDL."""
        mock_download.return_value = ("/storage/products/prod_1_abc.webp", "/storage/products/prod_1_abc_thumb.webp")

        prod1 = CanonicalProduct(
            id=1,
            canonical_name="Panadol Extra",
            image_url="https://cdn.example.com/panadol.jpg",
            local_image_url=None,
            regulatory_status=RegulatoryStatus.ACTIVE,
            rx_otc_status=RxOtcStatus.OTC,
            publish_status=PublishStatus.PUBLISHED,
        )
        prod2 = CanonicalProduct(
            id=2,
            canonical_name="Hapacol 650",
            image_url="/storage/products/already_local.webp",
            local_image_url="/storage/products/already_local.webp",
            regulatory_status=RegulatoryStatus.ACTIVE,
            rx_otc_status=RxOtcStatus.OTC,
            publish_status=PublishStatus.PUBLISHED,
        )
        self.db.add_all([prod1, prod2])
        self.db.commit()

        res = backfill_product_images(self.db, max_items=10)
        self.assertEqual(res["total_scanned"], 1)
        self.assertEqual(res["succeeded"], 1)

        # Kiểm tra prod1 đã được cập nhật local_image_url
        self.db.refresh(prod1)
        self.assertEqual(prod1.local_image_url, "/storage/products/prod_1_abc.webp")
        self.assertEqual(prod1.local_thumbnail_url, "/storage/products/prod_1_abc_thumb.webp")

    def test_05_validate_image_magic_bytes(self):
        """Kiểm tra xác thực định dạng nhị phân (magic bytes) chính xác."""
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01"
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 "
        bad_script = b"<?php echo 'malicious'; ?>"

        self.assertEqual(validate_image_magic_bytes(jpeg_bytes), "JPEG")
        self.assertEqual(validate_image_magic_bytes(png_bytes), "PNG")
        self.assertEqual(validate_image_magic_bytes(webp_bytes), "WEBP")

        with self.assertRaises(ValueError):
            validate_image_magic_bytes(bad_script)

        with self.assertRaises(ValueError):
            validate_image_magic_bytes(b"short")

    def test_06_save_and_optimize_uploaded_image(self):
        """Kiểm tra lưu và nén ảnh tải lên trực tiếp từ admin."""
        raw_bytes = self._create_dummy_image_bytes(width=1000, height=750, color="green")
        main_url, thumb_url = save_and_optimize_uploaded_image(
            content=raw_bytes,
            product_id=888,
            original_filename="packaging_photo.jpg",
        )

        self.assertIsNotNone(main_url)
        self.assertIsNotNone(thumb_url)
        self.assertTrue(main_url.startswith("/storage/products/prod_888_"))
        self.assertTrue(main_url.endswith(".webp"))
        self.assertTrue(thumb_url.endswith("_thumb.webp"))

        # Kiểm tra file đã ghi lên đĩa
        storage_dir = get_product_storage_dir()
        main_path = storage_dir / main_url.split("/")[-1]
        thumb_path = storage_dir / thumb_url.split("/")[-1]

        self.assertTrue(main_path.exists())
        self.assertTrue(thumb_path.exists())

        with Image.open(main_path) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertLessEqual(img.width, 800)
            self.assertLessEqual(img.height, 800)



if __name__ == "__main__":
    unittest.main()
