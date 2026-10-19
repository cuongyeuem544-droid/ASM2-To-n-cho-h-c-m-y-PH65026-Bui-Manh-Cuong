import os
import random
import sys
import time
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decimal import Decimal
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import (
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderItem,
    PaymentTransaction,
    PaymentWebhookEvent,
    PriceObservation,
    ProductSku,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import PublishStatus, RegulatoryStatus, RxOtcStatus
from app.services.momo_service import MomoPaymentService


class TestMomoPaymentSuite(unittest.TestCase):
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

        # Tạo kho hàng nếu chưa có
        self.wh = self.db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not self.wh:
            self.wh = Warehouse(
                code="KHO-HCM-01",
                name="Tổng kho Miền Nam",
                address="45 Hoàng Hoa Thám, Tân Bình, TP.HCM",
                lat=10.7872,
                lng=106.7001,
                is_active=True,
                is_central=True,
            )
            self.db.add(self.wh)
            self.db.commit()
            self.db.refresh(self.wh)

        # Tạo sản phẩm mẫu
        ts = int(time.time() * 1000) % 1000000
        pid = random.randint(200000, 299999)
        self.prod = CanonicalProduct(
            id=pid,
            canonical_name=f"Thuốc Test MoMo {ts}",
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
            observed_price=Decimal("150000.0"),
        )
        self.db.add(self.price_obs)

        self.sku = ProductSku(
            canonical_product_id=pid,
            sku_code=f"SKU-{pid}",
            base_price=Decimal("150000.0"),
            is_default=True,
            is_active=True,
        )
        self.db.add(self.sku)
        self.db.commit()
        self.db.refresh(self.sku)

        from datetime import date, timedelta
        self.batch = InventoryBatch(
            sku_id=self.sku.id,
            batch_number=f"LOT-MOMO-{ts}",
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

        # Tạo đơn hàng mẫu chờ thanh toán
        self.order_code = f"PT-MOMO-{ts}"
        self.order = Order(
            order_code=self.order_code,
            customer_name="Nguyễn Thanh Toán",
            customer_phone="0911223344",
            customer_email="thanhtoan.nguyen@example.com",
            shipping_address="123 Nguyễn Thị Minh Khai, Q1, TP.HCM",
            shipping_city="Hồ Chí Minh",
            payment_method="MOMO",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("300000.0"),
            shipping_fee=Decimal("0.0"),
            items=[
                OrderItem(
                    product_id=pid,
                    product_name=self.prod.canonical_name,
                    product_sku=self.sku.sku_code,
                    price=Decimal("150000.0"),
                    quantity=2,
                    subtotal=Decimal("300000.0"),
                )
            ],
        )
        self.db.add(self.order)
        self.db.commit()
        self.db.refresh(self.order)

        # Khởi tạo giao dịch PaymentTransaction PENDING ban đầu tương tự luồng tạo đơn thực tế
        self.tx = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-MOMO-{self.order_code}",
            provider="MOMO",
            amount=self.order.total_amount,
            currency="VND",
            status="PENDING",
        )
        self.db.add(self.tx)
        self.db.commit()
        self.db.refresh(self.tx)

    def tearDown(self):
        try:
            if hasattr(self, "order") and self.order:
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

    def test_01_signature_generation(self):
        """Kiểm tra độ chính xác của thuật toán chữ ký số HMAC-SHA256."""
        secret = "test_secret_key_123"
        raw_data = "accessKey=KEY123&amount=50000&orderId=ORDER001"
        sig1 = MomoPaymentService.generate_signature(raw_data, secret)
        sig2 = MomoPaymentService.generate_signature(raw_data, secret)

        self.assertEqual(sig1, sig2)
        self.assertEqual(len(sig1), 64)  # SHA256 hex string độ dài 64 chars

        # Dữ liệu thay đổi thì chữ ký phải thay đổi
        sig_diff = MomoPaymentService.generate_signature(raw_data + "&extra=1", secret)
        self.assertNotEqual(sig1, sig_diff)

    def test_02_create_momo_payment_request(self):
        """Khách hàng tạo yêu cầu thanh toán MoMo Sandbox cho đơn hàng."""
        from unittest.mock import MagicMock, patch

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"resultCode": 0}'
        mock_resp.json.return_value = {
            "resultCode": 0,
            "message": "Success",
            "payUrl": "https://test-payment.momo.vn/v2/gateway/pay?token=MOMO_TEST_OK",
            "qrCodeUrl": "https://test-payment.momo.vn/qr/MOMO_TEST_OK",
            "deeplink": "momo://app?action=payWithApp",
        }

        from app.core.security import create_guest_order_token
        valid_token = create_guest_order_token(self.order_code, self.order.customer_phone)
        payload = {
            "order_code": self.order_code,
            "return_url": "http://localhost:3000/checkout/result",
            "phone_verify": self.order.customer_phone,
            "order_token": valid_token,
        }

        # 1. Khi gateway phản hồi thành công (resultCode=0)
        with patch("app.services.momo_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            resp = self.client.post("/api/v1/payments/momo/create", json=payload)
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            assert "status" in data, f"KEYS IN DATA: {list(data.keys())}"
            self.assertEqual(data["status"], "SUCCESS")
            self.assertEqual(data["order_code"], self.order_code)
            self.assertEqual(data["amount"], 300000)
            self.assertIn("pay_url", data)
            self.assertIn("qr_code_url", data)

            # Kiểm tra bản ghi PaymentTransaction trong CSDL
            txn = self.db.query(PaymentTransaction).filter_by(order_id=self.order.id, provider="MOMO").first()
            self.assertIsNotNone(txn)
            self.assertEqual(txn.status, "PENDING")
            self.assertEqual(txn.amount, Decimal("300000.0"))

        # 2. Khi gateway bị ngắt kết nối -> Trả về 502 Fail-Safe và không tạo Simulated URL
        with patch("app.services.momo_service.httpx.Client") as mock_fail_cls:
            mock_fail = MagicMock()
            mock_fail_cls.return_value.__enter__.return_value = mock_fail
            mock_fail.post.side_effect = Exception("Gateway unreachable")
            fail_resp = self.client.post("/api/v1/payments/momo/create", json=payload)
            self.assertEqual(fail_resp.status_code, 502)

    def test_03_momo_ipn_webhook_success_completes_order(self):
        """IPN Webhook từ MoMo với resultCode=0 xác nhận đơn hàng đã thanh toán thành công."""
        # Chuẩn bị dữ liệu IPN giả lập có chữ ký chuẩn
        secret = settings.momo_secret_key
        access = settings.momo_access_key
        partner = settings.momo_partner_code
        amount = "300000"
        order_id = self.order_code
        request_id = f"REQ-{order_id}-1"
        trans_id = f"MOMO-TRANS-{random.randint(1000000, 9999999)}"
        result_code = "0"
        message = "Giao dịch thành công"
        order_info = "Thanh toan don thuoc"
        order_type = "momo_wallet"
        pay_type = "qr"
        response_time = str(int(time.time() * 1000))
        extra_data = ""

        raw_signature = (
            f"accessKey={access}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"message={message}&"
            f"orderId={order_id}&"
            f"orderInfo={order_info}&"
            f"orderType={order_type}&"
            f"partnerCode={partner}&"
            f"payType={pay_type}&"
            f"requestId={request_id}&"
            f"responseTime={response_time}&"
            f"resultCode={result_code}&"
            f"transId={trans_id}"
        )
        sig = MomoPaymentService.generate_signature(raw_signature, secret)

        ipn_payload = {
            "partnerCode": partner,
            "orderId": order_id,
            "requestId": request_id,
            "amount": int(amount),
            "orderInfo": order_info,
            "orderType": order_type,
            "transId": trans_id,
            "resultCode": int(result_code),
            "message": message,
            "payType": pay_type,
            "responseTime": int(response_time),
            "extraData": extra_data,
            "signature": sig,
        }

        resp = self.client.post("/api/v1/payments/momo/webhook", json=ipn_payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["resultCode"], 0)

        self.db.expire_all()
        self.db.refresh(self.order)
        self.assertEqual(self.order.payment_status, "PAID")
        self.assertEqual(self.order.order_status, "CONFIRMED")
        self.assertEqual(self.order.fulfillment_status, "ALLOCATED")

        # Kiểm tra Thẻ thanh toán (PaymentTransaction) chuyển sang SUCCESS
        txn = self.db.query(PaymentTransaction).filter_by(order_id=self.order.id).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.status, "SUCCESS")
        self.assertEqual(txn.provider_trans_id, trans_id)

        # Kiểm tra PaymentWebhookEvent đã lưu log
        evt = self.db.query(PaymentWebhookEvent).filter_by(event_id=trans_id).first()
        self.assertIsNotNone(evt)
        self.assertTrue(evt.processed)

    def test_04_momo_ipn_invalid_signature_rejected(self):
        """Từ chối Webhook khi chữ ký số không khớp hoặc bị sửa đổi (HTTP 400)."""
        ipn_payload = {
            "partnerCode": settings.momo_partner_code,
            "orderId": self.order_code,
            "requestId": f"REQ-{self.order_code}",
            "amount": 300000,
            "orderInfo": "Thanh toan don thuoc",
            "orderType": "momo_wallet",
            "transId": "FORGED-9999",
            "resultCode": 0,
            "message": "Giao dịch thành công",
            "payType": "qr",
            "responseTime": int(time.time() * 1000),
            "extraData": "",
            "signature": "fake_forged_invalid_signature_1234567890",
        }

        resp = self.client.post("/api/v1/payments/momo/webhook", json=ipn_payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid HMAC Signature", resp.json()["detail"])

        # Trạng thái đơn vẫn là PENDING
        self.db.refresh(self.order)
        self.assertEqual(self.order.payment_status, "PENDING")

    def test_05_idempotent_replay_does_not_duplicate_processing(self):
        """Gửi lặp IPN Webhook nhiều lần không gây lỗi và bảo toàn trạng thái (Idempotency)."""
        # Mô phỏng thanh toán lần 1 thành công
        sim_resp1 = self.client.post(
            "/api/v1/payments/momo/simulate",
            json={"order_code": self.order_code, "success": True},
        )
        self.assertEqual(sim_resp1.status_code, 200)

        self.db.refresh(self.order)
        self.assertEqual(self.order.payment_status, "PAID")

        # Mô phỏng gửi lại lần 2
        sim_resp2 = self.client.post(
            "/api/v1/payments/momo/simulate",
            json={"order_code": self.order_code, "success": True},
        )
        self.assertEqual(sim_resp2.status_code, 200)
        self.assertEqual(sim_resp2.json()["resultCode"], 0)

        # Đơn vẫn giữ nguyên trạng thái PAID
        self.db.refresh(self.order)
        self.assertEqual(self.order.payment_status, "PAID")

    def test_06_query_payment_status(self):
        """Tra cứu trạng thái thanh toán đơn hàng qua API với kiểm tra xác thực."""
        # Không có số điện thoại hoặc token -> 401 hoặc 403
        resp_unauth = self.client.get(f"/api/v1/payments/orders/{self.order_code}/status")
        self.assertIn(resp_unauth.status_code, [401, 403])

        # Chỉ có số điện thoại (không có token) -> 403 Forbidden
        resp_phone_only = self.client.get(f"/api/v1/payments/orders/{self.order_code}/status?phone_verify={self.order.customer_phone}")
        self.assertEqual(resp_phone_only.status_code, 403)

        # Có token bảo mật hợp lệ -> 200
        from app.core.security import create_guest_order_token
        valid_token = create_guest_order_token(self.order_code, self.order.customer_phone)
        resp = self.client.get(
            f"/api/v1/payments/orders/{self.order_code}/status",
            headers={"X-Order-Token": valid_token},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        self.assertEqual(data["order_code"], self.order_code)
        self.assertEqual(data["payment_status"], "PENDING")
        self.assertEqual(data["payment_method"], "MOMO")
        self.assertEqual(data["total_amount"], 300000.0)

    def test_07_momo_ipn_wrong_amount_rejected(self):
        """Từ chối Webhook khi số tiền thanh toán không khớp với đơn hàng (HTTP 400)."""
        secret = settings.momo_secret_key
        access = settings.momo_access_key
        partner = settings.momo_partner_code
        amount = "100000"  # Sai số tiền (đơn là 300,000)
        order_id = self.order_code
        request_id = f"REQ-{order_id}-wrong-amount"
        trans_id = f"MOMO-TRANS-{random.randint(1000000, 9999999)}"
        result_code = "0"
        message = "Giao dịch thành công"
        order_info = "Thanh toan don thuoc"
        order_type = "momo_wallet"
        pay_type = "qr"
        response_time = str(int(time.time() * 1000))
        extra_data = ""

        raw_signature = (
            f"accessKey={access}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"message={message}&"
            f"orderId={order_id}&"
            f"orderInfo={order_info}&"
            f"orderType={order_type}&"
            f"partnerCode={partner}&"
            f"payType={pay_type}&"
            f"requestId={request_id}&"
            f"responseTime={response_time}&"
            f"resultCode={result_code}&"
            f"transId={trans_id}"
        )
        sig = MomoPaymentService.generate_signature(raw_signature, secret)

        ipn_payload = {
            "partnerCode": partner,
            "orderId": order_id,
            "requestId": request_id,
            "amount": int(amount),
            "orderInfo": order_info,
            "orderType": order_type,
            "transId": trans_id,
            "resultCode": int(result_code),
            "message": message,
            "payType": pay_type,
            "responseTime": int(response_time),
            "extraData": extra_data,
            "signature": sig,
        }

        resp = self.client.post("/api/v1/payments/momo/webhook", json=ipn_payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("không khớp", resp.json()["detail"])

        # Đơn hàng KHÔNG được chuyển sang PAID
        self.db.expire_all()
        self.db.refresh(self.order)
        self.assertNotEqual(self.order.payment_status, "PAID")

    def test_08_momo_ipn_wrong_partner_code_rejected(self):
        """Từ chối Webhook khi partnerCode không khớp cấu hình hệ thống (HTTP 400)."""
        secret = settings.momo_secret_key
        access = settings.momo_access_key
        partner = "WRONG_PARTNER_CODE"
        amount = "300000"
        order_id = self.order_code
        request_id = f"REQ-{order_id}-wrong-partner"
        trans_id = f"MOMO-TRANS-{random.randint(1000000, 9999999)}"
        result_code = "0"
        message = "Giao dịch thành công"
        order_info = "Thanh toan don thuoc"
        order_type = "momo_wallet"
        pay_type = "qr"
        response_time = str(int(time.time() * 1000))
        extra_data = ""

        raw_signature = (
            f"accessKey={access}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"message={message}&"
            f"orderId={order_id}&"
            f"orderInfo={order_info}&"
            f"orderType={order_type}&"
            f"partnerCode={partner}&"
            f"payType={pay_type}&"
            f"requestId={request_id}&"
            f"responseTime={response_time}&"
            f"resultCode={result_code}&"
            f"transId={trans_id}"
        )
        sig = MomoPaymentService.generate_signature(raw_signature, secret)

        ipn_payload = {
            "partnerCode": partner,
            "orderId": order_id,
            "requestId": request_id,
            "amount": int(amount),
            "orderInfo": order_info,
            "orderType": order_type,
            "transId": trans_id,
            "resultCode": int(result_code),
            "message": message,
            "payType": pay_type,
            "responseTime": int(response_time),
            "extraData": extra_data,
            "signature": sig,
        }

        resp = self.client.post("/api/v1/payments/momo/webhook", json=ipn_payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("partnerCode", resp.json()["detail"])

    def test_09_momo_ipn_uninitialized_transaction_rejected(self):
        """Từ chối Webhook khi đơn hàng chưa từng khởi tạo giao dịch thanh toán MoMo (Requirement II.6 & II.7)."""
        # Xóa PaymentTransaction của đơn này
        self.db.query(PaymentTransaction).filter_by(order_id=self.order.id).delete()
        self.db.commit()

        secret = settings.momo_secret_key
        access = settings.momo_access_key
        partner = settings.momo_partner_code
        amount = "300000"
        order_id = self.order_code
        request_id = f"REQ-{order_id}-no-txn"
        trans_id = f"MOMO-TRANS-{random.randint(1000000, 9999999)}"
        result_code = "0"
        message = "Giao dịch thành công"
        order_info = "Thanh toan don thuoc"
        order_type = "momo_wallet"
        pay_type = "qr"
        response_time = str(int(time.time() * 1000))
        extra_data = ""

        raw_signature = (
            f"accessKey={access}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"message={message}&"
            f"orderId={order_id}&"
            f"orderInfo={order_info}&"
            f"orderType={order_type}&"
            f"partnerCode={partner}&"
            f"payType={pay_type}&"
            f"requestId={request_id}&"
            f"responseTime={response_time}&"
            f"resultCode={result_code}&"
            f"transId={trans_id}"
        )
        sig = MomoPaymentService.generate_signature(raw_signature, secret)

        ipn_payload = {
            "partnerCode": partner,
            "orderId": order_id,
            "requestId": request_id,
            "amount": int(amount),
            "orderInfo": order_info,
            "orderType": order_type,
            "transId": trans_id,
            "resultCode": int(result_code),
            "message": message,
            "payType": pay_type,
            "responseTime": int(response_time),
            "extraData": extra_data,
            "signature": sig,
        }

        resp = self.client.post("/api/v1/payments/momo/webhook", json=ipn_payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Không tìm thấy phiên giao dịch thanh toán MoMo đã khởi tạo", resp.json()["detail"])

    def test_10_momo_ipn_late_webhook_on_cancelled_order_routes_to_reconciliation(self):
        """Webhook đến muộn khi đơn đã bị hủy trước đó: ghi nhận tiền vào nhưng KHÔNG kích hoạt lại đơn (Requirement II.9)."""
        # Đánh dấu đơn là CANCELLED
        self.order.order_status = "CANCELLED"
        self.order.fulfillment_status = "CANCELLED"
        self.db.commit()

        # Tạo lại PaymentTransaction PENDING
        tx = PaymentTransaction(
            order_id=self.order.id,
            transaction_code=f"TXN-LATE-{self.order_code}",
            provider="MOMO",
            amount=self.order.total_amount,
            currency="VND",
            status="PENDING",
        )
        self.db.add(tx)
        self.db.commit()

        secret = settings.momo_secret_key
        access = settings.momo_access_key
        partner = settings.momo_partner_code
        amount = "300000"
        order_id = self.order_code
        request_id = f"REQ-{order_id}-late"
        trans_id = f"MOMO-LATE-{random.randint(1000000, 9999999)}"
        result_code = "0"
        message = "Giao dịch thành công"
        order_info = "Thanh toan don thuoc"
        order_type = "momo_wallet"
        pay_type = "qr"
        response_time = str(int(time.time() * 1000))
        extra_data = ""

        raw_signature = (
            f"accessKey={access}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"message={message}&"
            f"orderId={order_id}&"
            f"orderInfo={order_info}&"
            f"orderType={order_type}&"
            f"partnerCode={partner}&"
            f"payType={pay_type}&"
            f"requestId={request_id}&"
            f"responseTime={response_time}&"
            f"resultCode={result_code}&"
            f"transId={trans_id}"
        )
        sig = MomoPaymentService.generate_signature(raw_signature, secret)

        ipn_payload = {
            "partnerCode": partner,
            "orderId": order_id,
            "requestId": request_id,
            "amount": int(amount),
            "orderInfo": order_info,
            "orderType": order_type,
            "transId": trans_id,
            "resultCode": int(result_code),
            "message": message,
            "payType": pay_type,
            "responseTime": int(response_time),
            "extraData": extra_data,
            "signature": sig,
        }

        resp = self.client.post("/api/v1/payments/momo/webhook", json=ipn_payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("reconciliation_required"))

        # Đơn hàng vẫn giữ nguyên trạng thái CANCELLED, KHÔNG bị chuyển sang ALLOCATED
        self.db.expire_all()
        self.db.refresh(self.order)
        self.assertEqual(self.order.order_status, "CANCELLED")
        self.assertEqual(self.order.fulfillment_status, "CANCELLED")

        # Thẻ thanh toán ghi nhận SUCCESS để không làm mất vết dòng tiền
        tx_refreshed = self.db.query(PaymentTransaction).filter_by(order_id=self.order.id, provider="MOMO").first()
        self.assertEqual(tx_refreshed.status, "SUCCESS")

    def test_11_momo_query_transaction_status_reconciles(self):
        """Chủ động đối soát trạng thái giao dịch MoMo qua Query API khi mất IPN (Requirement II.10)."""
        from unittest.mock import MagicMock, patch
        from app.core.security import create_guest_order_token

        valid_token = create_guest_order_token(self.order_code, self.order.customer_phone)

        # Mock MoMo query gateway response thành công (resultCode=0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "partnerCode": settings.momo_partner_code,
            "orderId": self.order_code,
            "requestId": f"QUERY-{self.order_code}",
            "amount": 300000,
            "transId": "MOMO-QUERY-99999",
            "resultCode": 0,
            "message": "Giao dịch thành công",
            "payType": "qr",
            "responseTime": int(time.time() * 1000),
            "extraData": "",
            "signature": "mock_valid_signature",
        }

        with patch("app.services.momo_service.httpx.Client") as mock_client_cls, \
             patch.object(MomoPaymentService, "verify_ipn_signature", return_value=True):
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = mock_resp

            resp = self.client.post(
                f"/api/v1/payments/momo/check/{self.order_code}?phone_verify={self.order.customer_phone}",
                headers={"X-Order-Token": valid_token},
            )
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            self.assertTrue(data.get("is_paid"))
            self.assertEqual(data.get("payment_status"), "PAID")

            self.db.expire_all()
            self.db.refresh(self.order)
            self.assertEqual(self.order.payment_status, "PAID")
            self.assertEqual(self.order.fulfillment_status, "ALLOCATED")


if __name__ == "__main__":
    unittest.main()
