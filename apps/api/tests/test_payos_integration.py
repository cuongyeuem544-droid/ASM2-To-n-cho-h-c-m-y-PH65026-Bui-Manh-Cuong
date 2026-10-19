import json
import os
import random
import sys
import time
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models import (
    AuditLog,
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    PaymentTransaction,
    PriceObservation,
    ProductSku,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus, UserRole
from app.services.payos_service import PayOSPaymentService
from payos.types.v2.payment_requests import CreatePaymentLinkResponse
from payos.types.webhooks.webhook import WebhookData


class TestPayOSIntegrationSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_db_config import setup_isolated_test_db, TestSessionLocal
        setup_isolated_test_db()
        cls.SessionClass = TestSessionLocal

    @classmethod
    def tearDownClass(cls):
        from tests.test_db_config import teardown_isolated_test_db
        teardown_isolated_test_db()

    def setUp(self):
        self.client = TestClient(app)
        self.db = self.SessionClass()

        # Đảm bảo có kho hàng
        self.wh = self.db.query(Warehouse).filter_by(code="KHO-PAYOS-01").first()
        if not self.wh:
            self.wh = Warehouse(
                code="KHO-PAYOS-01",
                name="Kho Dược PayOS Trung Tâm",
                address="123 Điện Biên Phủ, Bình Thạnh, TP.HCM",
                lat=10.7990,
                lng=106.7110,
                is_active=True,
                is_central=True,
            )
            self.db.add(self.wh)
            self.db.commit()
            self.db.refresh(self.wh)

        # Tạo sản phẩm và SKU mẫu
        ts = int(time.time() * 1000) % 1000000
        pid = random.randint(300000, 399999)
        self.prod = CanonicalProduct(
            id=pid,
            canonical_name=f"Thuốc Thử Nghiệm PayOS {ts}",
            registration_number=f"VD-{pid}-26",
            regulatory_status=RegulatoryStatus.ACTIVE,
            rx_otc_status=RxOtcStatus.OTC,
            publish_status=PublishStatus.PUBLISHED,
        )
        self.db.add(self.prod)
        self.db.commit()

        self.price_obs = PriceObservation(
            product_id=pid,
            source_id=1,
            source_url=f"https://example.com/p/{pid}",
            observed_price=Decimal("120000.0"),
        )
        self.db.add(self.price_obs)

        self.sku = ProductSku(
            canonical_product_id=pid,
            sku_code=f"SKU-PAYOS-{pid}",
            base_price=Decimal("120000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(self.sku)
        self.db.commit()
        self.db.refresh(self.sku)

        self.batch = InventoryBatch(
            sku_id=self.sku.id,
            batch_number=f"LOT-PAYOS-{ts}",
            expiry_date=date.today() + timedelta(days=365),
            initial_quantity=100,
            status="ACTIVE",
        )
        self.db.add(self.batch)
        self.db.commit()
        self.db.refresh(self.batch)

        self.stock = WarehouseBatchStock(
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity_on_hand=100,
            quantity_available=100,
            quantity_reserved=0,
        )
        self.db.add(self.stock)
        self.db.commit()

        # Tạo đơn hàng mẫu
        self.order_code = f"PT-PAYOS-{ts}"
        self.order = Order(
            order_code=self.order_code,
            customer_name="Lê Khách Hàng PayOS",
            customer_phone="0988776655",
            customer_email="payos.customer@example.com",
            shipping_address="456 Xô Viết Nghệ Tĩnh, Bình Thạnh, TP.HCM",
            shipping_city="Hồ Chí Minh",
            payment_method="PAYOS",
            payment_status="PENDING",
            order_status="PENDING",
            fulfillment_status="WAITING_PAYMENT",
            assigned_warehouse_id=self.wh.id,
            total_amount=Decimal("240000.0"),
            shipping_fee=Decimal("0.0"),
            items=[
                OrderItem(
                    product_id=pid,
                    product_name=self.prod.canonical_name,
                    product_sku=self.sku.sku_code,
                    price=Decimal("120000.0"),
                    quantity=2,
                    subtotal=Decimal("240000.0"),
                )
            ],
        )
        self.db.add(self.order)
        self.db.commit()
        self.db.refresh(self.order)

        # Tạo fulfillment
        self.ff = OrderFulfillment(
            fulfillment_code=f"FF-{self.order.order_code}-01",
            order_id=self.order.id,
            warehouse_id=self.wh.id,
            status="WAITING_PAYMENT",
        )
        self.db.add(self.ff)
        self.db.commit()

        from app.core.security import create_guest_order_token
        self.order_token = create_guest_order_token(self.order_code, self.order.customer_phone)

    def tearDown(self):
        try:
            if hasattr(self, "order") and self.order:
                self.db.query(OrderFulfillment).filter_by(order_id=self.order.id).delete()
                self.db.query(OrderItem).filter_by(order_id=self.order.id).delete()
                self.db.query(PaymentTransaction).filter_by(order_id=self.order.id).delete()
                self.db.delete(self.order)
            if hasattr(self, "stock") and self.stock:
                self.db.delete(self.stock)
            if hasattr(self, "batch") and self.batch:
                self.db.delete(self.batch)
            if hasattr(self, "sku") and self.sku:
                self.db.delete(self.sku)
            if hasattr(self, "prod") and self.prod:
                self.db.delete(self.prod)
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def test_01_payos_configuration_check(self):
        """Kiểm tra thuộc tính is_payos_configured phản ánh chính xác trạng thái cài đặt keys."""
        with patch.object(settings, "payos_client_id", "test_id"), \
             patch.object(settings, "payos_api_key", "test_key"), \
             patch.object(settings, "payos_checksum_key", "test_checksum"):
            self.assertTrue(settings.is_payos_configured)

        with patch.object(settings, "payos_client_id", ""):
            self.assertFalse(settings.is_payos_configured)

    @patch("app.services.payos_service.PayOS")
    def test_02_create_payment_request_success(self, MockPayOS):
        """Kiểm tra khởi tạo yêu cầu thanh toán payOS trả về link và cô lập đơn ở WAITING_PAYMENT."""
        mock_instance = MockPayOS.return_value
        fake_response = CreatePaymentLinkResponse(
            bin="970422",
            account_number="123456789",
            account_name="NHA THUOC H4CARE",
            amount=240000,
            description="DH " + self.order_code,
            order_code=99887766,
            currency="VND",
            payment_link_id="link_abc123",
            status="PENDING",
            checkout_url="https://pay.payos.vn/web/test-checkout-123",
            qr_code="vietqr://data",
        )
        mock_instance.payment_requests.create.return_value = fake_response

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/create",
                json={
                    "order_code": self.order_code,
                    "phone_verify": self.order.customer_phone,
                    "order_token": self.order_token,
                    "return_url": "http://localhost:3000/checkout/result",
                },
            )

        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["provider"], "PAYOS")
        self.assertEqual(data["checkout_url"], "https://pay.payos.vn/web/test-checkout-123")
        self.assertTrue(data["payos_order_code"] > 0)

        # Kiểm tra database: Đơn hàng ở trạng thái WAITING_PAYMENT
        refreshed_order = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed_order.fulfillment_status, "WAITING_PAYMENT")
        self.assertEqual(refreshed_order.payment_status, "PENDING")
        self.assertEqual(refreshed_order.payment_method, "PAYOS")

        # Kiểm tra có bản ghi PaymentTransaction PENDING
        txn = self.db.query(PaymentTransaction).filter_by(order_id=self.order.id, provider="PAYOS").first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.status, "PENDING")
        self.assertEqual(int(txn.amount), 240000)

    def test_03_warehouse_fulfillment_safety_gate(self):
        """Đơn hàng trực tuyến chưa thanh toán (WAITING_PAYMENT) bị chặn xuất kho / soạn hàng."""
        # Giả lập token quản lý/nhân viên kho
        from app.core.security import create_access_token, hash_password
        from app.models.inventory import UserWarehouseMembership
        staff_user = self.db.query(User).filter_by(email="staff.payos@example.com").first()
        if not staff_user:
            staff_user = User(
                email="staff.payos@example.com",
                phone="0912345678",
                full_name="Nhân viên Kho PayOS",
                password_hash=hash_password("StaffPass123!"),
                role=UserRole.WAREHOUSE_STAFF,
                warehouse_id=self.wh.id,
                is_active=True,
            )
            self.db.add(staff_user)
            self.db.commit()
            self.db.refresh(staff_user)

        membership = self.db.query(UserWarehouseMembership).filter_by(user_id=staff_user.id).first()
        if not membership:
            membership = UserWarehouseMembership(
                user_id=staff_user.id,
                warehouse_id=self.wh.id,
                role="WAREHOUSE_STAFF",
                is_active=True,
            )
            self.db.add(membership)
            self.db.commit()

        staff_token = create_access_token(str(staff_user.id), UserRole.WAREHOUSE_STAFF.value)
        headers = {"Authorization": f"Bearer {staff_token}"}

        # Cố gắng chuyển sang PICKING khi chưa thanh toán
        res = self.client.patch(
            f"/api/v1/warehouse-portal/orders/{self.order.id}/fulfillment",
            json={"status": "PICKING"},
            headers=headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("chưa thanh toán thành công", res.json()["detail"])

    @patch("app.services.payos_service.PayOS")
    def test_04_payos_webhook_success_updates_order_and_notifies_warehouse(self, MockPayOS):
        """Webhook payOS với chữ ký hợp lệ cập nhật PAID, chuyển sang ALLOCATED và phát thông báo kho."""
        mock_instance = MockPayOS.return_value

        # Tạo PaymentTransaction tương ứng trước
        payos_order_code = 123456789
        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-{self.order.order_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="PENDING",
            provider_trans_id=str(payos_order_code),
        )
        self.db.add(txn)
        self.db.commit()

        fake_verified_data = WebhookData(
            order_code=payos_order_code,
            amount=240000,
            description=f"DH {self.order.order_code}",
            account_number="123456789",
            reference="FT2401019999",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_abc123",
            code="00",
            desc="Thanh toan thanh cong",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "desc": "success",
                    "data": {
                        "orderCode": payos_order_code,
                        "amount": 240000,
                        "description": f"DH {self.order.order_code}",
                    },
                    "signature": "valid_signature_hash",
                },
            )

        self.assertEqual(res.status_code, 200, res.text)
        res_data = res.json()
        self.assertTrue(res_data["success"])
        self.assertEqual(res_data["payment_status"], "PAID")
        self.assertEqual(res_data["fulfillment_status"], "ALLOCATED")

        # Kiểm tra Database
        self.db.expire_all()
        order_in_db = self.db.get(Order, self.order.id)
        self.assertEqual(order_in_db.payment_status, "PAID")
        self.assertEqual(order_in_db.fulfillment_status, "ALLOCATED")
        self.assertEqual(order_in_db.order_status, "CONFIRMED")

        txn_in_db = self.db.get(PaymentTransaction, txn.id)
        self.assertEqual(txn_in_db.status, "SUCCESS")

        # Kiểm tra Audit Log
        audit = self.db.query(AuditLog).filter_by(
            action="PAYOS_WEBHOOK_PAYMENT_SUCCESS",
            entity_id=self.order.id,
        ).first()
        self.assertIsNotNone(audit)

    @patch("app.services.payos_service.PayOS")
    def test_05_payos_webhook_idempotency(self, MockPayOS):
        """Gửi lặp Webhook cho đơn đã PAID không gây lỗi và trả về already_paid=True."""
        mock_instance = MockPayOS.return_value
        payos_order_code = 987654321

        # Đặt đơn thành PAID trước
        self.order.payment_status = "PAID"
        self.order.fulfillment_status = "ALLOCATED"
        self.db.commit()

        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-{self.order.order_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="SUCCESS",
            provider_trans_id=str(payos_order_code),
        )
        self.db.add(txn)
        self.db.commit()

        fake_verified_data = WebhookData(
            order_code=payos_order_code,
            amount=240000,
            description=f"DH {self.order.order_code}",
            account_number="123456789",
            reference="FT2401019999",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_abc123",
            code="00",
            desc="Thanh toan thanh cong",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={"code": "00", "data": {"orderCode": payos_order_code}},
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("already_paid"))

    @patch("app.services.payos_service.PayOS")
    def test_06_payos_webhook_invalid_signature_rejected(self, MockPayOS):
        """Webhook với chữ ký giả mạo bị từ chối với HTTP 400 và không cập nhật đơn hàng."""
        mock_instance = MockPayOS.return_value
        mock_instance.webhooks.verify.side_effect = Exception("Invalid signature")

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={"code": "00", "signature": "fake_bad_sig"},
            )

        self.assertEqual(res.status_code, 400)
        self.assertIn("Xác thực chữ ký webhook payOS thất bại", res.json()["detail"])

        # Trạng thái đơn vẫn PENDING, WAITING_PAYMENT
        refreshed = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed.payment_status, "PENDING")
        self.assertEqual(refreshed.fulfillment_status, "WAITING_PAYMENT")

    @patch("app.services.payos_service.PayOS")
    def test_07_payos_webhook_test_event_handling(self, MockPayOS):
        """Webhook test event từ payOS dashboard phản hồi 200 thành công không đổi dữ liệu thật."""
        mock_instance = MockPayOS.return_value
        fake_test_data = WebhookData(
            order_code=123,
            amount=1000,
            description="test webhook",
            account_number="123",
            reference="test",
            transaction_date_time="2026-10-20",
            currency="VND",
            payment_link_id="test",
            code="00",
            desc="test",
        )
        mock_instance.webhooks.verify.return_value = fake_test_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post("/api/v1/payments/payos/webhook", json={"test": True})

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])

    @patch("app.services.payos_service.PayOS")
    def test_08_reconciliation_check_payment_status(self, MockPayOS):
        """Đối soát trực tiếp qua endpoint check status khi payOS đã nhận tiền."""
        mock_instance = MockPayOS.return_value
        payos_order_code = 554433221

        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-{self.order.order_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="PENDING",
            provider_trans_id=str(payos_order_code),
        )
        self.db.add(txn)
        self.db.commit()

        # Mock payOS API trả về status PAID
        mock_payment_link = MagicMock()
        mock_payment_link.status = "PAID"
        mock_instance.payment_requests.get.return_value = mock_payment_link

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                f"/api/v1/payments/payos/check/{self.order.order_code}?phone_verify={self.order.customer_phone}",
                headers={"X-Order-Token": self.order_token},
            )

        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertTrue(data["is_paid"])
        self.assertEqual(data["fulfillment_status"], "ALLOCATED")

        # Database đã đồng bộ
        self.db.expire_all()
        refreshed = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed.payment_status, "PAID")
        self.assertEqual(refreshed.fulfillment_status, "ALLOCATED")

    def test_09_anti_idor_order_access(self):
        """Truy cập tạo thanh toán hoặc check status của đơn người khác bị chặn 403 Forbidden."""
        # Gọi với số điện thoại sai
        res = self.client.post(
            "/api/v1/payments/payos/create",
            json={
                "order_code": self.order_code,
                "phone_verify": "0999999999",  # Sai số điện thoại
            },
        )
        self.assertEqual(res.status_code, 403)

    def test_10_retry_with_cod_switches_fulfillment_to_allocated(self):
        """Khách hàng đổi từ PAYOS sang COD qua endpoint retry -> Chuyển fulfillment_status sang ALLOCATED."""
        res = self.client.post(
            "/api/v1/payments/retry",
            json={
                "order_code": self.order_code,
                "new_payment_method": "COD",
                "phone_verify": self.order.customer_phone,
                "order_token": self.order_token,
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["payment_method"], "COD")

        # Sau khi chuyển COD, đơn tự động có thể xuất kho (ALLOCATED)
        self.db.expire_all()
        refreshed = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed.payment_method, "COD")
        self.assertEqual(refreshed.fulfillment_status, "ALLOCATED")


if __name__ == "__main__":
    unittest.main()
