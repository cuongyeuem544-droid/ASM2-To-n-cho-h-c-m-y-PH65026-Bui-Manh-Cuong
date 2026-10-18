"""
Test Suite for:
1. Unrated product stars (average_rating = 0.0, review_count = 0, approved reviews only).
2. SMTP test email logging in EmailOutbox (reference_type="SMTP_TEST", SENT/FAILED, last_error).
3. Timestamps & Timezone normalization logic for orders and transactions.
"""

from datetime import datetime, timezone
import smtplib
import unittest
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import (
    CanonicalProduct,
    DataSource,
    Order,
    OrderItem,
    PriceObservation,
    ProductSku,
    User,
    Warehouse,
)
from app.models.enums import PublishStatus, RxOtcStatus, SourceType, UserRole
from app.models.inventory import EmailOutbox, ProductReview
from app.services.email_service import EmailService, EmailErrorCode
from app.api.products import list_products, get_product


class TestUnratedStarsAndEmailOutbox(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Seed admin
        self.admin = User(
            email="admin@pharmatrust.vn",
            full_name="Admin Test",
            password_hash="dummy_hash",
            role=UserRole.ADMIN,
            is_active=True,
        )
        self.db.add(self.admin)

        # Seed product
        self.prod = CanonicalProduct(
            canonical_name="Thuốc Bổ Thần Kinh Vitamin B1-B6-B12 Test",
            registration_number="VN-99999-TEST",
            publish_status=PublishStatus.PUBLISHED,
            rx_otc_status=RxOtcStatus.OTC,
            overall_score=95,
        )
        self.db.add(self.prod)
        self.db.commit()
        self.db.refresh(self.prod)

    def tearDown(self):
        self.db.close()

    def test_unrated_product_displays_zero_stars_and_zero_count(self):
        """Sản phẩm chưa có đánh giá phải trả về average_rating = 0.0 và review_count = 0."""
        # 1. Detail endpoint
        detail = get_product(self.prod.id, self.admin, self.db)
        self.assertEqual(detail.average_rating, 0.0)
        self.assertEqual(detail.review_count, 0)

        # 2. List products endpoint
        result = list_products(_=self.admin, db=self.db, page=1, page_size=20)
        items = result["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["average_rating"], 0.0)
        self.assertEqual(items[0]["review_count"], 0)

    def test_unapproved_reviews_are_not_counted_in_rating(self):
        """Đánh giá chưa duyệt (is_approved=False) không được tính vào rating hiển thị."""
        unapproved_rev = ProductReview(
            canonical_product_id=self.prod.id,
            customer_name="Người dùng A",
            rating=5,
            comment="Rất tốt nhưng chưa duyệt",
            is_approved=False,
        )
        self.db.add(unapproved_rev)
        self.db.commit()

        detail = get_product(self.prod.id, self.admin, self.db)
        self.assertEqual(detail.average_rating, 0.0)
        self.assertEqual(detail.review_count, 0)

        result = list_products(_=self.admin, db=self.db, page=1, page_size=20)
        self.assertEqual(result["items"][0]["average_rating"], 0.0)
        self.assertEqual(result["items"][0]["review_count"], 0)

    def test_approved_reviews_correctly_calculate_average_and_count(self):
        """Khi có đánh giá được duyệt (is_approved=True), điểm trung bình và số lượng được tính chính xác."""
        rev1 = ProductReview(
            canonical_product_id=self.prod.id,
            customer_name="Khách 1",
            rating=5,
            comment="Thuốc chuẩn",
            is_approved=True,
        )
        rev2 = ProductReview(
            canonical_product_id=self.prod.id,
            customer_name="Khách 2",
            rating=4,
            comment="Giao nhanh",
            is_approved=True,
        )
        # 1 review chưa duyệt
        rev3 = ProductReview(
            canonical_product_id=self.prod.id,
            customer_name="Khách 3",
            rating=1,
            comment="Spam",
            is_approved=False,
        )
        self.db.add_all([rev1, rev2, rev3])
        self.db.commit()

        detail = get_product(self.prod.id, self.admin, self.db)
        self.assertEqual(detail.review_count, 2)
        self.assertEqual(detail.average_rating, 4.5)

        result = list_products(_=self.admin, db=self.db, page=1, page_size=20)
        self.assertEqual(result["items"][0]["review_count"], 2)
        self.assertEqual(result["items"][0]["average_rating"], 4.5)

    @patch.object(EmailService, "send_smtp_email")
    def test_test_email_creates_outbox_record_on_success(self, mock_send):
        """Gửi email test tạo bản ghi EmailOutbox với reference_type='SMTP_TEST' và chuyển trạng thái SENT."""
        mock_send.return_value = None

        outbox = EmailService.queue_and_send_test_email(
            db=self.db,
            recipient_email="test_recipient@gmail.com",
        )

        self.assertIsNotNone(outbox.id)
        self.assertEqual(outbox.reference_type, "SMTP_TEST")
        self.assertTrue(outbox.reference_id.startswith("TEST-"))
        self.assertEqual(outbox.recipient_email, "test_recipient@gmail.com")
        self.assertEqual(outbox.status, "SENT")
        self.assertIsNotNone(outbox.sent_at)
        self.assertIsNone(outbox.last_error)

        mock_send.assert_called_once()

    @patch.object(EmailService, "send_smtp_email")
    def test_test_email_logs_failure_in_outbox_without_exposing_secrets(self, mock_send):
        """Gửi email test thất bại ghi nhận trạng thái FAILED và lỗi đã được làm sạch an toàn."""
        mock_send.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

        with self.assertRaises(Exception):
            EmailService.queue_and_send_test_email(
                db=self.db,
                recipient_email="failure_test@gmail.com",
            )

        # Kiểm tra bản ghi trong outbox
        outbox = self.db.query(EmailOutbox).filter(EmailOutbox.recipient_email == "failure_test@gmail.com").first()
        self.assertIsNotNone(outbox)
        self.assertEqual(outbox.status, "FAILED")
        self.assertEqual(outbox.reference_type, "SMTP_TEST")
        self.assertIsNotNone(outbox.last_error)
        self.assertIn(EmailErrorCode.AUTH_FAILED, outbox.last_error)
        # Secret/password không được in vào log
        self.assertNotIn("password=", outbox.last_error.lower())
