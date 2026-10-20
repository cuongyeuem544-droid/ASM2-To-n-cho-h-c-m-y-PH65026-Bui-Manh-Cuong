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
            from app.models.inventory import StockReservation, PayosOrderCode
            if hasattr(self, "order") and self.order:
                self.db.query(StockReservation).filter_by(order_id=self.order.id).delete()
                self.db.query(PayosOrderCode).filter_by(order_id=self.order.id).delete()
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
        mock_payment_link.amount = int(self.order.total_amount)
        mock_payment_link.amountPaid = int(self.order.total_amount)
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



    @patch("app.services.payos_service.PayOS")
    def test_11_webhook_amount_underpaid_rejected(self, MockPayOS):
        """Webhook payOS thanh toán thiếu tiền (200k < 240k) bị từ chối 400 và không đổi PAID (BUG-01)."""
        mock_instance = MockPayOS.return_value
        payos_order_code = 111222333
        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-UNDER-{self.order.order_code}",
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
            amount=200000,  # Thiếu 40,000 VND so với 240,000 VND
            description=f"DH {self.order.order_code}",
            account_number="123456789",
            reference="FT_UNDERPAID",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_underpaid",
            code="00",
            desc="Thanh toan thieu tien",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "data": {"orderCode": payos_order_code, "amount": 200000},
                },
            )

        self.assertEqual(res.status_code, 400)
        self.assertIn("thiếu", res.json()["detail"])

        # Kiểm tra Database: Đơn hàng không được chuyển sang PAID
        self.db.expire_all()
        refreshed = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed.payment_status, "PENDING")
        self.assertEqual(refreshed.fulfillment_status, "WAITING_PAYMENT")

    @patch("app.services.payos_service.PayOS")
    def test_12_webhook_amount_overpaid_handled_safely(self, MockPayOS):
        """Webhook payOS thanh toán thừa tiền (300k > 240k) bị từ chối 400 và không kích hoạt xuất kho (BUG-01)."""
        mock_instance = MockPayOS.return_value
        payos_order_code = 444555666
        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-OVER-{self.order.order_code}",
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
            amount=300000,  # Thừa 60,000 VND
            description=f"DH {self.order.order_code}",
            account_number="123456789",
            reference="FT_OVERPAID",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_overpaid",
            code="00",
            desc="Thanh toan thua tien",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "data": {"orderCode": payos_order_code, "amount": 300000},
                },
            )

        self.assertEqual(res.status_code, 400)
        self.assertIn("thừa", res.json()["detail"])

        self.db.expire_all()
        refreshed = self.db.get(Order, self.order.id)
        self.assertNotEqual(refreshed.payment_status, "PAID")
        self.assertNotEqual(refreshed.fulfillment_status, "ALLOCATED")

    @patch("app.services.payos_service.PayOS")
    def test_13_webhook_unlinked_transaction_rejected(self, MockPayOS):
        """Webhook với orderCode không tồn tại trong hệ thống bị từ chối 400 (BUG-03)."""
        mock_instance = MockPayOS.return_value
        unlinked_code = 999888777

        fake_verified_data = WebhookData(
            order_code=unlinked_code,
            amount=240000,
            description="DH KHONG_TON_TAI",
            account_number="123456789",
            reference="FT_UNLINKED",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_unlinked",
            code="00",
            desc="Giao dich khong co lien ket",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "data": {"orderCode": unlinked_code, "amount": 240000},
                },
            )

        self.assertEqual(res.status_code, 400)
        self.assertIn("Không tìm thấy PaymentTransaction", res.json()["detail"])

    @patch("app.services.payos_service.PayOS")
    def test_14_webhook_cancelled_order_payment_received(self, MockPayOS):
        """Webhook cho đơn đã bị hủy ghi nhận REFUND_PENDING, không phục hồi CONFIRMED/ALLOCATED (BUG-02)."""
        mock_instance = MockPayOS.return_value
        payos_order_code = 777888999

        # Hủy đơn hàng trước
        self.order.order_status = "CANCELLED"
        self.order.fulfillment_status = "CANCELLED"
        self.db.commit()

        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-CANCEL-{self.order.order_code}",
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
            reference="FT_LATE_WEBHOOK",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_late",
            code="00",
            desc="Thanh toan thanh cong sau khi huy",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "data": {"orderCode": payos_order_code, "amount": 240000},
                },
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("payment_status"), "REFUND_PENDING")

        self.db.expire_all()
        refreshed = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed.order_status, "CANCELLED")
        self.assertEqual(refreshed.fulfillment_status, "CANCELLED")
        self.assertEqual(refreshed.payment_status, "REFUND_PENDING")

    def test_15_order_code_uniqueness_concurrent_generation(self):
        """Sinh mã orderCode payOS đồng thời: 30 luồng không có mã trùng và <= 9007199254740991 (BUG-04)."""
        import concurrent.futures

        codes = []
        def generate_code():
            session = self.SessionClass()
            try:
                code = PayOSPaymentService.generate_unique_order_code(session, self.order.id)
                return code
            finally:
                session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(generate_code) for _ in range(30)]
            for fut in concurrent.futures.as_completed(futures):
                codes.append(fut.result())

        self.assertEqual(len(codes), 30)
        self.assertEqual(len(set(codes)), 30, "Mã orderCode bị trùng lặp!")
        for code in codes:
            self.assertTrue(0 < code <= 9007199254740991, f"Mã vượt giới hạn JS safe int: {code}")

    def test_16_cancel_order_before_payment_releases_stock(self):
        """Hủy đơn khi chưa thanh toán thành công: Giải phóng reservation và cập nhật CANCELLED (Req V)."""
        from app.models.inventory import StockReservation
        resv = StockReservation(
            order_id=self.order.id,
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity=2,
            status="RESERVED",
        )
        self.db.add(resv)
        self.db.commit()

        res = self.client.post(
            f"/api/v1/payments/orders/{self.order.order_code}/cancel",
            json={
                "phone_verify": self.order.customer_phone,
                "order_token": self.order_token,
                "reason": "Khách đổi ý muốn đặt lại",
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data.get("order_status"), "CANCELLED")

        self.db.expire_all()
        refreshed = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed.order_status, "CANCELLED")
        self.assertEqual(refreshed.fulfillment_status, "CANCELLED")

        refreshed_resv = self.db.get(StockReservation, resv.id)
        self.assertEqual(refreshed_resv.status, "RELEASED")

    def test_17_cancel_order_after_paid_blocked(self):
        """Hủy đơn sau khi đã thanh toán thành công (PAID) bị chặn và yêu cầu liên hệ CSKH (Req V.3)."""
        self.order.payment_status = "PAID"
        self.order.fulfillment_status = "ALLOCATED"
        self.order.order_status = "CONFIRMED"
        self.db.commit()

        res = self.client.post(
            f"/api/v1/payments/orders/{self.order.order_code}/cancel",
            json={
                "phone_verify": self.order.customer_phone,
                "order_token": self.order_token,
                "reason": "Muốn hủy sau khi đã trả tiền",
            },
        )
        self.assertEqual(res.status_code, 400, res.text)
        self.assertIn("đã được thanh toán thành công (PAID)", res.json()["detail"])


    @patch("app.services.payos_service.PayOS")
    def test_18_payos_multiple_links_preserves_old_link_mapping(self, MockPayOS):
        """Tạo nhiều link thanh toán cho một đơn: Không ghi đè mapping cũ, thanh toán link cũ vẫn thành công."""
        mock_instance = MockPayOS.return_value

        from app.models.inventory import StockReservation
        resv = StockReservation(
            order_id=self.order.id,
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity=2,
            status="RESERVED",
        )
        self.db.add(resv)

        link_1_code = 111111111
        link_2_code = 222222222

        # Link 1
        txn_1 = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-{self.order.order_code}-{link_1_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="PENDING",
            provider_trans_id=str(link_1_code),
        )
        self.db.add(txn_1)

        # Link 2
        txn_2 = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-{self.order.order_code}-{link_2_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="PENDING",
            provider_trans_id=str(link_2_code),
        )
        self.db.add(txn_2)
        self.db.commit()

        # Kiểm tra cả 2 giao dịch đều tồn tại với provider_trans_id riêng
        self.db.expire_all()
        txs = self.db.query(PaymentTransaction).filter_by(order_id=self.order.id, provider="PAYOS").all()
        trans_ids = [t.provider_trans_id for t in txs]
        self.assertIn(str(link_1_code), trans_ids)
        self.assertIn(str(link_2_code), trans_ids)

        # Khách quét và thanh toán link cũ (link_1_code)
        fake_verified_data = WebhookData(
            order_code=link_1_code,
            amount=240000,
            description=f"DH {self.order.order_code}",
            account_number="123456789",
            reference="FT_LINK_1_PAID",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_1",
            code="00",
            desc="Thanh toan link 1 thanh cong",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "data": {"orderCode": link_1_code, "amount": 240000},
                },
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("payment_status"), "PAID")
        self.assertEqual(data.get("fulfillment_status"), "ALLOCATED")

        self.db.expire_all()
        refreshed_order = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed_order.payment_status, "PAID")
        self.assertEqual(refreshed_order.fulfillment_status, "ALLOCATED")

    @patch("app.services.payos_service.PayOS")
    def test_19_payos_double_payment_on_multiple_links_prevented(self, MockPayOS):
        """Khách thanh toán cả 2 link: Link 1 kích hoạt đơn, Link 2 bị chặn xuất kho thêm và chuyển đối soát hoàn tiền."""
        mock_instance = MockPayOS.return_value

        link_1_code = 333333333
        link_2_code = 444444444

        # Link 1 đã thanh toán thành công
        txn_1 = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-{self.order.order_code}-{link_1_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="SUCCESS",
            provider_trans_id=str(link_1_code),
        )
        self.db.add(txn_1)

        # Link 2 vẫn đang PENDING
        txn_2 = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-{self.order.order_code}-{link_2_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="PENDING",
            provider_trans_id=str(link_2_code),
        )
        self.db.add(txn_2)

        self.order.payment_status = "PAID"
        self.order.fulfillment_status = "ALLOCATED"
        self.db.commit()

        # Webhook của link 2 đến (khách chuyển tiền lần thứ hai)
        fake_verified_data = WebhookData(
            order_code=link_2_code,
            amount=240000,
            description=f"DH {self.order.order_code}",
            account_number="123456789",
            reference="FT_LINK_2_DOUBLE_PAY",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_2",
            code="00",
            desc="Thanh toan link 2 bi trung",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "data": {"orderCode": link_2_code, "amount": 240000},
                },
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("duplicate_payment"))
        self.assertTrue(data.get("refund_required"))

        # Giao dịch 2 bị chuyển sang OVERPAID để kế toán hoàn tiền
        self.db.expire_all()
        refreshed_txn_2 = self.db.get(PaymentTransaction, txn_2.id)
        self.assertEqual(refreshed_txn_2.status, "OVERPAID")

    def test_20_payos_reservation_expiration_cancels_pending_orders(self):
        """Bổ sung PAYOS vào quy trình hết hạn: Quá hạn thanh toán tự động giải phóng tồn kho và hủy đơn."""
        from datetime import datetime, UTC, timedelta
        from app.services.fulfillment_service import FulfillmentRoutingService
        from app.models.inventory import StockReservation

        self.order.payment_method = "PAYOS"
        self.order.payment_status = "PENDING"
        self.order.order_status = "PENDING"
        self.order.created_at = datetime.now(UTC) - timedelta(minutes=45)
        self.db.commit()

        resv = StockReservation(
            order_id=self.order.id,
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity=2,
            status="RESERVED",
        )
        self.db.add(resv)

        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-EXPIRE-{self.order.order_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="PENDING",
            provider_trans_id="999000111",
        )
        self.db.add(txn)
        self.db.commit()

        # Quét hết hạn các đơn quá 30 phút
        cancelled_codes = FulfillmentRoutingService.expire_stale_reservations(self.db, max_age_minutes=30)
        self.assertIn(self.order.order_code, cancelled_codes)

        self.db.expire_all()
        refreshed_order = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed_order.payment_status, "EXPIRED")
        self.assertEqual(refreshed_order.order_status, "CANCELLED")
        self.assertEqual(refreshed_order.fulfillment_status, "CANCELLED")

        refreshed_resv = self.db.get(StockReservation, resv.id)
        self.assertEqual(refreshed_resv.status, "RELEASED")

        refreshed_txn = self.db.get(PaymentTransaction, txn.id)
        self.assertEqual(refreshed_txn.status, "CANCELLED")

    @patch("app.services.payos_service.PayOS")
    def test_21_payos_late_payment_after_reservation_released_routes_to_refund(self, MockPayOS):
        """Thanh toán payOS đến sau khi thuốc giữ chỗ đã bị giải phóng: Chuyển REFUND_PENDING, không xuất kho âm."""
        mock_instance = MockPayOS.return_value
        from app.models.inventory import StockReservation

        payos_order_code = 888777666
        self.order.payment_status = "EXPIRED"
        self.order.order_status = "CANCELLED"
        self.order.fulfillment_status = "CANCELLED"
        self.db.commit()

        resv = StockReservation(
            order_id=self.order.id,
            warehouse_id=self.wh.id,
            batch_id=self.batch.id,
            quantity=2,
            status="RELEASED",
        )
        self.db.add(resv)

        txn = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-PAYOS-LATE-{self.order.order_code}",
            provider="PAYOS",
            amount=Decimal("240000.0"),
            currency="VND",
            status="CANCELLED",
            provider_trans_id=str(payos_order_code),
        )
        self.db.add(txn)
        self.db.commit()

        fake_verified_data = WebhookData(
            order_code=payos_order_code,
            amount=240000,
            description=f"DH {self.order.order_code}",
            account_number="123456789",
            reference="FT_LATE_AFTER_EXPIRE",
            transaction_date_time="2026-10-20 02:40:00",
            currency="VND",
            payment_link_id="link_late_expire",
            code="00",
            desc="Khach tra tien muon",
        )
        mock_instance.webhooks.verify.return_value = fake_verified_data

        with patch.object(settings, "payos_client_id", "dummy_client_id"), \
             patch.object(settings, "payos_api_key", "dummy_api_key"), \
             patch.object(settings, "payos_checksum_key", "dummy_checksum_key"):
            res = self.client.post(
                "/api/v1/payments/payos/webhook",
                json={
                    "code": "00",
                    "data": {"orderCode": payos_order_code, "amount": 240000},
                },
            )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("payment_status"), "REFUND_PENDING")
        self.assertTrue(data.get("refund_pending"))

        self.db.expire_all()
        refreshed_order = self.db.get(Order, self.order.id)
        self.assertEqual(refreshed_order.payment_status, "REFUND_PENDING")
        self.assertEqual(refreshed_order.fulfillment_status, "CANCELLED")
        self.assertEqual(refreshed_order.order_status, "CANCELLED")


if __name__ == "__main__":
    unittest.main()
