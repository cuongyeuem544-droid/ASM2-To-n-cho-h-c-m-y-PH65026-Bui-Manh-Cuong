import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import (
    Order,
    OrderItem,
    PaymentTransaction,
    PaymentWebhookEvent,
    SepayInboundTransaction,
    SepayPaymentCode,
    User,
    Warehouse,
)
from app.models.enums import UserRole
from app.services.sepay_service import SepayService

TEST_SECRET = "test_sepay_webhook_secret_key_12345"
TEST_ACCOUNT_NUMBER = "0901234567"
TEST_ACCOUNT_HOLDER = "PHARMATRUST / H4CARE"


@pytest.fixture(scope="module")
def setup_sepay_data():
    db = SessionLocal()

    # 1. User
    user = db.scalar(select(User).where(User.email == "sepay_customer@h4care.vn"))
    if not user:
        user = User(
            email="sepay_customer@h4care.vn",
            password_hash=hash_password("Customer123!"),
            full_name="Nguyễn Văn SePay",
            phone="0912345678",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 2. Warehouse
    wh = db.scalar(select(Warehouse).where(Warehouse.is_active.is_(True)))
    if not wh:
        wh = Warehouse(
            code="WH-SEPAY-01",
            name="Kho Dược SePay",
            address="123 Kim Mã, Ba Đình, Hà Nội",
            province="Hà Nội",
            district="Ba Đình",
            lat=21.0315,
            lng=105.8234,
            is_active=True,
            is_central=True,
        )
        db.add(wh)
        db.commit()
        db.refresh(wh)

    user_token = create_access_token(subject=str(user.id), role=user.role.value)
    auth_headers = {"Authorization": f"Bearer {user_token}"}

    yield {
        "user": user,
        "warehouse": wh,
        "auth_headers": auth_headers,
    }
    db.close()


def _create_test_order(db, user, total_amount=150000) -> Order:
    order_code = f"PT-SEP-{int(time.time() * 1000) % 10000000}"
    order = Order(
        order_code=order_code,
        user_id=user.id,
        customer_name=user.full_name,
        customer_phone=user.phone,
        shipping_address="123 Kim Mã, Ba Đình, Hà Nội",
        shipping_city="Hà Nội",
        is_verified=True,
        payment_method="SEPAY",
        payment_status="PENDING",
        order_status="PENDING",
        fulfillment_status="WAITING_PAYMENT",
        total_amount=Decimal(str(total_amount)),
        shipping_fee=Decimal("0"),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _generate_sepay_signature(raw_body: bytes, timestamp: int, secret: str) -> str:
    message = f"{timestamp}.".encode("utf-8") + raw_body
    return "sha256=" + hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class TestSepayIntegration:
    @classmethod
    def setup_class(cls):
        # Configure SePay test settings
        settings.sepay_enabled = True
        settings.sepay_bank_id = "MB"
        settings.sepay_account_number = TEST_ACCOUNT_NUMBER
        settings.sepay_account_holder = TEST_ACCOUNT_HOLDER
        settings.sepay_webhook_secret = TEST_SECRET

    def test_01_sepay_payment_code_format_and_uniqueness(self, setup_sepay_data):
        """Mã thanh toán SePay bắt buộc có tiền tố HC và đúng 8 chữ số hậu tố (HC + 8 số)."""
        with SessionLocal() as db:
            order1 = _create_test_order(db, setup_sepay_data["user"], 200000)
            order2 = _create_test_order(db, setup_sepay_data["user"], 300000)

            code1 = SepayService.generate_payment_code(db, order1)
            code2 = SepayService.generate_payment_code(db, order2)

            assert re.match(r"^HC\d{8}$", code1.payment_code)
            assert re.match(r"^HC\d{8}$", code2.payment_code)
            assert code1.payment_code != code2.payment_code
            assert code1.code_number != code2.code_number

            # Idempotency: Lấy lại mã cho cùng 1 đơn hàng phải ra chính xác mã cũ
            code1_again = SepayService.generate_payment_code(db, order1)
            assert code1_again.payment_code == code1.payment_code
            assert code1_again.id == code1.id

    def test_02_create_sepay_payment_api(self, setup_sepay_data):
        """API /api/v1/payments/sepay/create trả về URL VietQR MBBank và mã thanh toán HC hợp lệ."""
        client = TestClient(app)
        with SessionLocal() as db:
            order = _create_test_order(db, setup_sepay_data["user"], 185000)

        response = client.post(
            "/api/v1/payments/sepay/create",
            json={"order_code": order.order_code},
            headers=setup_sepay_data["auth_headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["order_code"] == order.order_code
        assert re.match(r"^HC\d{8}$", data["payment_code"])
        assert data["amount"] == 185000
        assert data["provider"] == "SEPAY"
        assert data["account_number"] == TEST_ACCOUNT_NUMBER
        assert data["account_holder"] == TEST_ACCOUNT_HOLDER
        assert "vietqr.io/image/MB-" in data["qr_code_url"]
        assert data["transfer_memo"] == data["payment_code"]

        with SessionLocal() as db:
            refreshed = db.scalar(select(Order).where(Order.order_code == order.order_code))
            assert refreshed.payment_method == "SEPAY"
            assert refreshed.fulfillment_status == "WAITING_PAYMENT"

    def test_03_sepay_webhook_hmac_sha256_success(self, setup_sepay_data):
        """Webhook SePay có chữ ký HMAC-SHA256 hợp lệ sẽ cập nhật đơn hàng thành PAID và mở khóa kho."""
        client = TestClient(app)
        with SessionLocal() as db:
            order = _create_test_order(db, setup_sepay_data["user"], 250000)
            code_obj = SepayService.generate_payment_code(db, order)
            payment_code = code_obj.payment_code

        sepay_id = int(time.time() * 1000) % 100000000
        payload = {
            "id": sepay_id,
            "gateway": "MBBank",
            "transactionDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "accountNumber": TEST_ACCOUNT_NUMBER,
            "subAccount": "",
            "code": payment_code,
            "content": f"{payment_code} thanh toan don thuoc",
            "transferType": "in",
            "description": f"Chuyen tien {payment_code}",
            "transferAmount": 250000,
            "accumulated": 10000000,
            "referenceCode": f"FT{sepay_id}",
        }

        raw_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        current_ts = int(time.time())
        signature = _generate_sepay_signature(raw_body, current_ts, TEST_SECRET)

        headers = {
            "Content-Type": "application/json",
            "X-SePay-Signature": signature,
            "X-SePay-Timestamp": str(current_ts),
        }

        response = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["success"] is True
        assert res_data["order_code"] == order.order_code

        # Kiểm tra database state
        with SessionLocal() as db:
            db_order = db.scalar(select(Order).where(Order.order_code == order.order_code))
            assert db_order.payment_status == "PAID"
            assert db_order.order_status == "CONFIRMED"
            assert db_order.fulfillment_status == "UNFULFILLED"

            tx = db.scalar(select(PaymentTransaction).where(PaymentTransaction.order_id == db_order.id, PaymentTransaction.provider == "SEPAY"))
            assert tx is not None
            assert tx.status == "SUCCESS"
            assert tx.provider_trans_id == str(sepay_id)

            inbound = db.scalar(select(SepayInboundTransaction).where(SepayInboundTransaction.sepay_id == sepay_id))
            assert inbound is not None
            assert inbound.status == "PROCESSED"
            assert inbound.order_id == db_order.id

    def test_04_sepay_webhook_idempotency_duplicate_protection(self, setup_sepay_data):
        """Gửi cùng 1 webhook sepay_id nhiều lần phải được trả về thành công tức thì không trùng lặp (Idempotent)."""
        client = TestClient(app)
        with SessionLocal() as db:
            order = _create_test_order(db, setup_sepay_data["user"], 120000)
            code_obj = SepayService.generate_payment_code(db, order)
            payment_code = code_obj.payment_code

        sepay_id = int(time.time() * 1000) % 100000000 + 1
        payload = {
            "id": sepay_id,
            "gateway": "MBBank",
            "transactionDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "accountNumber": TEST_ACCOUNT_NUMBER,
            "code": payment_code,
            "content": f"{payment_code} thanh toan",
            "transferType": "in",
            "transferAmount": 120000,
            "referenceCode": f"FT{sepay_id}",
        }
        raw_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        current_ts = int(time.time())
        signature = _generate_sepay_signature(raw_body, current_ts, TEST_SECRET)
        headers = {
            "Content-Type": "application/json",
            "X-SePay-Signature": signature,
            "X-SePay-Timestamp": str(current_ts),
        }

        # Lần 1: Thành công
        resp1 = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert resp1.status_code == 200
        assert resp1.json()["success"] is True

        # Lần 2: Trùng lặp (Idempotent hit)
        resp2 = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["success"] is True
        assert "trước đó" in resp2.json()["message"]

    def test_05_sepay_webhook_signature_mismatch_rejected(self, setup_sepay_data):
        """Chữ ký giả mạo hoặc sai SECRET phải bị trả về HTTP 401 Unauthorized ngay lập tức."""
        client = TestClient(app)
        payload = {
            "id": 999999,
            "accountNumber": TEST_ACCOUNT_NUMBER,
            "transferAmount": 100000,
            "transferType": "in",
            "content": "HC99999999 chuyen tien",
        }
        raw_body = json.dumps(payload).encode("utf-8")
        current_ts = int(time.time())
        bad_signature = "sha256=abcdef0123456789invalidhash"

        headers = {
            "Content-Type": "application/json",
            "X-SePay-Signature": bad_signature,
            "X-SePay-Timestamp": str(current_ts),
        }

        response = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert response.status_code == 401
        assert "không khớp" in response.json()["detail"].lower()

    def test_06_sepay_webhook_expired_timestamp_rejected(self, setup_sepay_data):
        """Webhook có timestamp quá 300 giây bị từ chối chống tấn công phát lại (Replay Attack)."""
        client = TestClient(app)
        payload = {
            "id": 888888,
            "accountNumber": TEST_ACCOUNT_NUMBER,
            "transferAmount": 100000,
            "transferType": "in",
            "content": "HC88888888",
        }
        raw_body = json.dumps(payload).encode("utf-8")
        stale_ts = int(time.time()) - 400  # Lệch 400 giây (> 300s)
        signature = _generate_sepay_signature(raw_body, stale_ts, TEST_SECRET)

        headers = {
            "Content-Type": "application/json",
            "X-SePay-Signature": signature,
            "X-SePay-Timestamp": str(stale_ts),
        }

        response = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert response.status_code == 401
        assert "quá hạn" in response.json()["detail"].lower()

    def test_07_sepay_webhook_underpaid_flagged_not_paid(self, setup_sepay_data):
        """Khách chuyển thiếu tiền: Đưa vào đối soát (FLAGGED_UNDERPAID), tuyệt đối KHÔNG đánh dấu PAID."""
        client = TestClient(app)
        with SessionLocal() as db:
            order = _create_test_order(db, setup_sepay_data["user"], 500000)
            code_obj = SepayService.generate_payment_code(db, order)
            payment_code = code_obj.payment_code

        sepay_id = int(time.time() * 1000) % 100000000 + 2
        payload = {
            "id": sepay_id,
            "gateway": "MBBank",
            "accountNumber": TEST_ACCOUNT_NUMBER,
            "code": payment_code,
            "content": f"{payment_code} chuyen thieu",
            "transferType": "in",
            "transferAmount": 300000,  # Thiếu 200,000 đ
        }
        raw_body = json.dumps(payload).encode("utf-8")
        current_ts = int(time.time())
        signature = _generate_sepay_signature(raw_body, current_ts, TEST_SECRET)
        headers = {
            "Content-Type": "application/json",
            "X-SePay-Signature": signature,
            "X-SePay-Timestamp": str(current_ts),
        }

        response = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["success"] is False
        assert "không đủ" in res_data["message"]

        with SessionLocal() as db:
            db_order = db.scalar(select(Order).where(Order.order_code == order.order_code))
            assert db_order.payment_status == "PENDING"  # KHÔNG ĐƯỢC PAID
            assert db_order.fulfillment_status == "WAITING_PAYMENT"

            inbound = db.scalar(select(SepayInboundTransaction).where(SepayInboundTransaction.sepay_id == sepay_id))
            assert inbound.status == "FLAGGED_UNDERPAID"

    def test_08_sepay_webhook_overpaid_flagged_not_paid(self, setup_sepay_data):
        """Khách chuyển thừa tiền: Đưa vào đối soát kế toán (FLAGGED_OVERPAID), KHÔNG tự động duyệt."""
        client = TestClient(app)
        with SessionLocal() as db:
            order = _create_test_order(db, setup_sepay_data["user"], 100000)
            code_obj = SepayService.generate_payment_code(db, order)
            payment_code = code_obj.payment_code

        sepay_id = int(time.time() * 1000) % 100000000 + 3
        payload = {
            "id": sepay_id,
            "gateway": "MBBank",
            "accountNumber": TEST_ACCOUNT_NUMBER,
            "code": payment_code,
            "content": f"{payment_code} chuyen thua",
            "transferType": "in",
            "transferAmount": 150000,  # Thừa 50,000 đ
        }
        raw_body = json.dumps(payload).encode("utf-8")
        current_ts = int(time.time())
        signature = _generate_sepay_signature(raw_body, current_ts, TEST_SECRET)
        headers = {
            "Content-Type": "application/json",
            "X-SePay-Signature": signature,
            "X-SePay-Timestamp": str(current_ts),
        }

        response = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert response.status_code == 200
        assert response.json()["success"] is False

        with SessionLocal() as db:
            db_order = db.scalar(select(Order).where(Order.order_code == order.order_code))
            assert db_order.payment_status == "PENDING"
            inbound = db.scalar(select(SepayInboundTransaction).where(SepayInboundTransaction.sepay_id == sepay_id))
            assert inbound.status == "FLAGGED_OVERPAID"

    def test_09_sepay_webhook_transfer_type_out_ignored(self, setup_sepay_data):
        """Giao dịch tiền ra (transferType == 'out') bị bỏ qua an toàn."""
        client = TestClient(app)
        sepay_id = int(time.time() * 1000) % 100000000 + 4
        payload = {
            "id": sepay_id,
            "gateway": "MBBank",
            "accountNumber": TEST_ACCOUNT_NUMBER,
            "transferType": "out",
            "transferAmount": 500000,
            "content": "Chuyen khoan chi phi",
        }
        raw_body = json.dumps(payload).encode("utf-8")
        current_ts = int(time.time())
        signature = _generate_sepay_signature(raw_body, current_ts, TEST_SECRET)
        headers = {
            "Content-Type": "application/json",
            "X-SePay-Signature": signature,
            "X-SePay-Timestamp": str(current_ts),
        }

        response = client.post("/api/v1/payments/sepay/webhook", content=raw_body, headers=headers)
        assert response.status_code == 200
        assert "tiền ra" in response.json()["message"]

        with SessionLocal() as db:
            inbound = db.scalar(select(SepayInboundTransaction).where(SepayInboundTransaction.sepay_id == sepay_id))
            assert inbound.status == "IGNORED_OUT"

    def test_10_payment_intent_and_retry_sepay(self, setup_sepay_data):
        """Khởi tạo Payment Intent và Retry đổi sang SEPAY hoạt động chuẩn xác."""
        client = TestClient(app)
        with SessionLocal() as db:
            order = _create_test_order(db, setup_sepay_data["user"], 99000)

        # 1. Tạo Intent với SEPAY
        resp_intent = client.post(
            "/api/v1/payments/intent",
            json={"order_code": order.order_code, "payment_method": "SEPAY"},
            headers=setup_sepay_data["auth_headers"],
        )
        assert resp_intent.status_code == 200
        intent_data = resp_intent.json()
        assert intent_data["provider"] == "SEPAY"
        assert intent_data["payment_method"] == "SEPAY"
        assert intent_data["status"] == "PENDING"
        assert "vietqr.io" in intent_data["qr_code_url"]

        # 2. Thử đổi phương thức qua Retry (sang COD rồi lại sang SEPAY)
        resp_retry1 = client.post(
            "/api/v1/payments/retry",
            json={"order_code": order.order_code, "new_payment_method": "COD"},
            headers=setup_sepay_data["auth_headers"],
        )
        assert resp_retry1.status_code == 200
        assert resp_retry1.json()["provider"] == "COD"

        resp_retry2 = client.post(
            "/api/v1/payments/retry",
            json={"order_code": order.order_code, "new_payment_method": "SEPAY"},
            headers=setup_sepay_data["auth_headers"],
        )
        assert resp_retry2.status_code == 200
        assert resp_retry2.json()["provider"] == "SEPAY"
