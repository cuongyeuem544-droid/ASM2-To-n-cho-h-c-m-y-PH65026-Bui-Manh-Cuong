import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models import (
    CanonicalProduct,
    FulfillmentItem,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderItemBatchAllocation,
    ProductSku,
    Warehouse,
)
from app.models.enums import PublishStatus, RxOtcStatus
from app.models.inventory import EmailOutbox
from app.services.email_service import EmailService


class TestEmailServiceSuite(unittest.TestCase):
    def setUp(self):
        # Database in-memory SQLite riêng biệt cho từng test case
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Seed kho
        self.wh = Warehouse(
            code="KHO-TEST-01",
            name="Kho Dược Hà Nội 01",
            address="123 Tràng Tiền",
            province="01",
            district="001",
            lat=21.0285,
            lng=105.8542,
            is_active=True,
        )
        self.db.add(self.wh)
        self.db.flush()

        # Seed sản phẩm & SKU
        self.prod = CanonicalProduct(
            canonical_name="Panadol Extra 500mg/65mg",
            registration_number="VN-12345-TEST",
            publish_status=PublishStatus.PUBLISHED,
            rx_otc_status=RxOtcStatus.OTC,
        )
        self.db.add(self.prod)
        self.db.flush()

        self.sku = ProductSku(
            canonical_product_id=self.prod.id,
            sku_code="SKU-PANADOL-TEST",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("60000"),
            is_default=True,
        )
        self.db.add(self.sku)
        self.db.flush()

        # Seed Lô FEFO
        self.batch = InventoryBatch(
            sku_id=self.sku.id,
            batch_number="BATCH-FEFO-99",
            manufacture_date=date(2025, 1, 1),
            expiry_date=date(2026, 12, 31),
            initial_quantity=100,
            status="ACTIVE",
        )
        self.db.add(self.batch)
        self.db.flush()

        # Seed Đơn hàng
        self.order = Order(
            order_code="PT-TEST-EMAIL-01",
            customer_name="Nguyễn Văn A",
            customer_phone="0912345678",
            customer_email="nguyenvana@gmail.com",
            shipping_address="Số 10 Phố Huế, Hoàn Kiếm, Hà Nội",
            shipping_city="Hà Nội",
            payment_method="MOMO",
            payment_status="PAID",
            order_status="CONFIRMED",
            total_amount=Decimal("120000"),
            shipping_fee=Decimal("0.0"),
        )
        self.db.add(self.order)
        self.db.flush()

        self.order_item = OrderItem(
            order_id=self.order.id,
            product_id=self.prod.id,
            product_name=self.prod.canonical_name,
            product_sku=self.prod.registration_number,
            price=Decimal("60000"),
            quantity=2,
            subtotal=Decimal("120000"),
        )
        self.db.add(self.order_item)
        self.db.flush()

        # Seed Kiện hàng & Phân bổ lô FEFO
        self.ff = OrderFulfillment(
            fulfillment_code="FF-TEST-EMAIL-01",
            order_id=self.order.id,
            warehouse_id=self.wh.id,
            status="PACKED",
            carrier_name="GSP Express",
        )
        self.db.add(self.ff)
        self.db.flush()

        self.ff_item = FulfillmentItem(
            fulfillment_id=self.ff.id,
            order_item_id=self.order_item.id,
            quantity=2,
        )
        self.db.add(self.ff_item)
        self.db.flush()

        self.alloc = OrderItemBatchAllocation(
            fulfillment_item_id=self.ff_item.id,
            order_item_id=self.order_item.id,
            batch_id=self.batch.id,
            warehouse_id=self.wh.id,
            allocated_quantity=2,
        )
        self.db.add(self.alloc)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_01_build_order_confirmation_html(self):
        """Kiểm tra tạo mẫu email xác nhận đơn hàng chuẩn HTML với đầy đủ thông tin thuốc, kiện hàng và lô FEFO."""
        subject, body_html, body_text = EmailService.build_order_confirmation_html(
            db=self.db, order=self.order
        )

        self.assertIn("PT-TEST-EMAIL-01", subject)
        self.assertIn("Nguyễn Văn A", body_html)
        self.assertIn("Panadol Extra 500mg/65mg", body_html)
        self.assertIn("BATCH-FEFO-99", body_html)
        self.assertIn("31/12/2026", body_html)
        self.assertIn("KHO-TEST-01", body_html)
        self.assertIn("FF-TEST-EMAIL-01", body_html)
        self.assertIn("120.000", body_html)
        self.assertIn("MoMo", body_html)

        # Fallback text format
        self.assertIn("PT-TEST-EMAIL-01", body_text)
        self.assertIn("Nguyễn Văn A", body_text)
        self.assertIn("BATCH-FEFO-99", body_text)

    def test_02_strict_smtp_rejection_when_unconfigured(self):
        """Báo lỗi nghiêm ngặt (Strict rejection) khi chưa cấu hình SMTP_USER hoặc SMTP_PASSWORD trong .env."""
        with patch.object(settings, "smtp_user", ""), patch.object(settings, "smtp_password", ""):
            with self.assertRaises(ValueError) as ctx:
                EmailService.send_smtp_email(
                    recipient_email="test@gmail.com",
                    subject="Test Subject",
                    body_html="<p>Test</p>",
                )
            self.assertIn("Chưa cấu hình tài khoản SMTP", str(ctx.exception))

    def test_03_queue_and_send_order_confirmation_missing_credentials_marks_failed(self):
        """Hàng đợi EmailOutbox ghi nhận bản ghi với trạng thái FAILED và lưu last_error khi thiếu cấu hình SMTP."""
        with patch.object(settings, "smtp_user", ""), patch.object(settings, "smtp_password", ""):
            outbox = EmailService.queue_and_send_order_confirmation(
                db=self.db,
                order=self.order,
                send_immediately=True,
            )

            self.assertIsNotNone(outbox)
            self.assertEqual(outbox.recipient_email, "nguyenvana@gmail.com")
            self.assertEqual(outbox.reference_id, "PT-TEST-EMAIL-01")
            self.assertEqual(outbox.status, "FAILED")
            self.assertIn("Chưa cấu hình tài khoản SMTP", outbox.last_error or "")
            self.assertEqual(outbox.retry_count, 1)

    def test_04_send_smtp_email_mocked_success(self):
        """Kiểm tra gửi email thật qua SMTP với Mock server smtplib (STARTTLS, login, sendmail)."""
        with patch.object(settings, "smtp_user", "test.pharmatrust@gmail.com"), \
             patch.object(settings, "smtp_password", "app-password-secret-1234"), \
             patch("smtplib.SMTP") as mock_smtp_cls:

            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            success = EmailService.send_smtp_email(
                recipient_email="customer@example.com",
                subject="Test Pharmacy Order",
                body_html="<p>Order Placed</p>",
                body_text="Order Placed Text",
            )

            self.assertTrue(success)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("test.pharmatrust@gmail.com", "app-password-secret-1234")
            mock_server.sendmail.assert_called_once()
            self.assertEqual(mock_server.sendmail.call_args[0][0], "test.pharmatrust@gmail.com")
            self.assertEqual(mock_server.sendmail.call_args[0][1], ["customer@example.com"])
            mock_server.quit.assert_called_once()

    def test_05_resend_outbox_email(self):
        """Kiểm tra tính năng gửi lại (Retry/Resend) một email đã thất bại trong outbox."""
        # Tạo bản ghi failed
        outbox = EmailOutbox(
            recipient_email="retry.customer@gmail.com",
            subject="Thư cần gửi lại",
            body_html="<p>Retry HTML</p>",
            reference_type="ORDER_CONFIRMATION",
            reference_id="PT-RETRY-01",
            status="FAILED",
            retry_count=1,
            max_retries=3,
            last_error="Mất kết nối SMTP lần 1",
        )
        self.db.add(outbox)
        self.db.commit()

        # Mock gửi thành công lần 2
        with patch.object(settings, "smtp_user", "test@gmail.com"), \
             patch.object(settings, "smtp_password", "secret"), \
             patch("smtplib.SMTP") as mock_smtp_cls:

            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            updated = EmailService.resend_email(db=self.db, outbox_id=outbox.id)

            self.assertEqual(updated.status, "SENT")
            self.assertIsNotNone(updated.sent_at)
            self.assertIsNone(updated.last_error)
            self.assertEqual(updated.retry_count, 2)

    def test_06_retry_limit_exceeded(self):
        """Khi retry_count >= max_retries, từ chối retry và lưu vết RETRY_EXCEEDED."""
        outbox = EmailOutbox(
            recipient_email="retry.exceeded@gmail.com",
            subject="Thư vượt quá retry",
            body_html="<p>Exceeded</p>",
            reference_type="ORDER_CONFIRMATION",
            reference_id="PT-EXCEEDED-01",
            status="FAILED",
            retry_count=3,
            max_retries=3,
            last_error="Lỗi trước đó",
        )
        self.db.add(outbox)
        self.db.commit()

        with self.assertRaises(ValueError) as ctx:
            EmailService.resend_email(db=self.db, outbox_id=outbox.id)
        self.assertIn("vượt quá số lần thử", str(ctx.exception))
        self.assertIn("RETRY_EXCEEDED", outbox.last_error or "")

    def test_07_duplicate_send_prevention(self):
        """Nếu đơn hàng đã có bản ghi EmailOutbox trạng thái SENT, không tạo bản ghi mới và không gửi lại."""
        # 1. Giả lập đơn đã gửi thành công
        existing = EmailOutbox(
            recipient_email="nguyenvana@gmail.com",
            subject="Đã gửi thành công",
            body_html="<p>Sent</p>",
            reference_type="ORDER_CONFIRMATION",
            reference_id="PT-TEST-EMAIL-01",
            status="SENT",
            retry_count=0,
            max_retries=3,
        )
        self.db.add(existing)
        self.db.commit()

        # 2. Gọi lại queue_and_send_order_confirmation
        result = EmailService.queue_and_send_order_confirmation(
            db=self.db,
            order=self.order,
            send_immediately=True,
        )
        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.status, "SENT")

        # Đảm bảo chỉ có duy nhất 1 bản ghi trong DB
        count = len(self.db.scalars(select(EmailOutbox).where(EmailOutbox.reference_id == "PT-TEST-EMAIL-01")).all())
        self.assertEqual(count, 1)

    def test_08_dns_resolution_failed_classification(self):
        """Lỗi [Errno 11001] getaddrinfo failed được phân loại chuẩn thành DNS_RESOLUTION_FAILED."""
        import socket
        gaierr = socket.gaierror(11001, "getaddrinfo failed")
        code, retryable, msg = EmailService.classify_smtp_error(gaierr)
        self.assertEqual(code, "DNS_RESOLUTION_FAILED")
        self.assertTrue(retryable)
        self.assertIn("getaddrinfo failed", msg)

    def test_09_timeout_classification(self):
        """Lỗi Timeout kết nối SMTP được phân loại thành SMTP_CONNECTION_TIMEOUT."""
        timeout_err = TimeoutError("Connection timed out")
        code, retryable, msg = EmailService.classify_smtp_error(timeout_err)
        self.assertEqual(code, "SMTP_CONNECTION_TIMEOUT")
        self.assertTrue(retryable)

    def test_10_auth_failed_classification(self):
        """Lỗi sai username/password SMTP được phân loại thành SMTP_AUTHENTICATION_FAILED và không retry vô ích."""
        import smtplib
        auth_err = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        code, retryable, msg = EmailService.classify_smtp_error(auth_err)
        self.assertEqual(code, "SMTP_AUTHENTICATION_FAILED")
        self.assertFalse(retryable)

    def test_11_ssl_tls_conflict_validation(self):
        """Báo lỗi khi cả SMTP_SSL và SMTP_TLS đều được bật đồng thời."""
        with patch.object(settings, "smtp_user", "test@gmail.com"), \
             patch.object(settings, "smtp_password", "pass"), \
             patch.object(settings, "smtp_ssl", True), \
             patch.object(settings, "smtp_tls", True):
            with self.assertRaises(ValueError) as ctx:
                EmailService.send_smtp_email(
                    recipient_email="test@gmail.com",
                    subject="Conflict",
                    body_html="<p>Test</p>",
                )
            self.assertIn("xung đột", str(ctx.exception))

    def test_12_html_escaping_customer_input(self):
        """Dữ liệu khách hàng nhập chứa mã độc hại được escape an toàn bởi html.escape."""
        self.order.customer_name = "<script>alert('xss')</script> Nguyễn Văn B"
        self.order.shipping_address = "<b>Tòa nhà H4</b> <img src=x onerror=alert(1)>"
        subject, body_html, body_text = EmailService.build_order_confirmation_html(
            db=self.db, order=self.order
        )
        self.assertNotIn("<script>", body_html)
        self.assertIn("&lt;script&gt;", body_html)
        self.assertNotIn("<img src=x", body_html)
        self.assertIn("&lt;img src=x", body_html)


if __name__ == "__main__":
    unittest.main()

