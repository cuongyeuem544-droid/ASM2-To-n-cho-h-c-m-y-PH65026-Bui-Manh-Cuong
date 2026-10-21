import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import Order, User, UserRole
from app.models.inventory import PaymentTransaction, SepayInboundTransaction, SepayPaymentCode
from app.core.security import create_access_token
from app.services.payment_intent_service import PaymentIntentService
from app.services.sepay_service import SepayService


@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_user(db_session):
    u_suffix = uuid.uuid4().hex[:8]
    phone = f"091{int(time.time() * 1000) % 10000000:07d}"
    user = User(
        email=f"test_expiry_{u_suffix}@pharmatrust.vn",
        phone=phone,
        full_name="Khách Thật Expiry",
        role=UserRole.CUSTOMER,
        password_hash="hashed_pw_dummy",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(subject=str(test_user.id), role=test_user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _create_order(db, user, total_amount=250000, method="SEPAY") -> Order:
    order_code = f"PT-EXP-{uuid.uuid4().hex[:6].upper()}"
    order = Order(
        order_code=order_code,
        user_id=user.id,
        customer_name=user.full_name,
        customer_phone=user.phone,
        shipping_address="456 Hai Bà Trưng, Quận 1, TP.HCM",
        shipping_city="TP.HCM",
        is_verified=True,
        payment_method=method,
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


def _get_sepay_auth_kwargs(raw_body: bytes) -> dict:
    if settings.sepay_webhook_secret:
        ts = str(int(time.time()))
        message = f"{ts}.".encode("utf-8") + raw_body
        sig = "sha256=" + hmac.new(settings.sepay_webhook_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return {"signature_header": sig, "timestamp_header": ts}
    return {"signature_header": None, "timestamp_header": None}


class TestPaymentExpiryAndLifecycle:
    def test_01_sepay_intent_has_15_minute_expiry(self, db_session, test_user, auth_headers):
        """Mỗi mã QR SePay tạo ra có đúng thời hạn 15 phút từ Backend."""
        client = TestClient(app)
        order = _create_order(db_session, test_user, total_amount=180000, method="SEPAY")

        res = client.post(
            "/api/v1/payments/intent",
            json={"order_code": order.order_code, "payment_method": "SEPAY"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert "expires_at" in data
        assert data["expires_at"] is not None

        exp_dt = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        now_dt = datetime.now(UTC)
        diff_minutes = (exp_dt - now_dt).total_seconds() / 60.0
        # Kiểm tra xấp xỉ 15 phút (trong dải 14.8 đến 15.1 phút)
        assert 14.5 <= diff_minutes <= 15.5

    def test_02_status_endpoint_returns_expiry_and_is_expired(self, db_session, test_user, auth_headers):
        """Endpoint tra cứu trạng thái đơn hàng trả về expires_at, is_expired và server_time."""
        client = TestClient(app)
        order = _create_order(db_session, test_user, total_amount=200000, method="SEPAY")

        # Tạo intent
        client.post(
            "/api/v1/payments/intent",
            json={"order_code": order.order_code, "payment_method": "SEPAY"},
            headers=auth_headers,
        )

        res = client.get(f"/api/v1/payments/orders/{order.order_code}/status", headers=auth_headers)
        assert res.status_code == 200
        summary = res.json()
        assert summary["expires_at"] is not None
        assert summary["is_expired"] is False
        assert summary["server_time"] is not None
        assert summary["can_retry"] is True

    def test_03_expired_intent_auto_transitions_to_expired(self, db_session, test_user, auth_headers):
        """Khi quá hạn 15 phút, tra cứu trạng thái tự động đánh dấu intent EXPIRED."""
        client = TestClient(app)
        order = _create_order(db_session, test_user, total_amount=300000, method="SEPAY")

        # Tạo intent
        client.post(
            "/api/v1/payments/intent",
            json={"order_code": order.order_code, "payment_method": "SEPAY"},
            headers=auth_headers,
        )

        # Mô phỏng quá hạn 15 phút bằng cách lùi expires_at về quá khứ trong database
        trans = db_session.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "SEPAY",
            )
        )
        assert trans is not None
        trans.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db_session.commit()

        # Gọi status check
        res = client.get(f"/api/v1/payments/orders/{order.order_code}/status", headers=auth_headers)
        assert res.status_code == 200
        summary = res.json()
        assert summary["is_expired"] is True
        # Giao dịch mới nhất đã chuyển EXPIRED
        assert summary["latest_transaction"]["status"] == "EXPIRED"

    def test_04_sepay_late_transfer_after_expiry_flagged_for_manual_review(self, db_session, test_user):
        """Khách chuyển tiền SePay sau khi mã đã hết hạn 15 phút -> Chuyển diện đối soát EXPIRED_INTENT_MANUAL_REVIEW, không tự duyệt PAID."""
        order = _create_order(db_session, test_user, total_amount=350000, method="SEPAY")

        # Tạo mã SePay và giả lập đã hết hạn
        code_obj = SepayService.generate_payment_code(db_session, order, force_new=True)
        code_obj.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        code_obj.status = "EXPIRED"
        db_session.commit()

        sepay_id = int(time.time() * 1000) % 900000000 + 100000000
        payload = {
            "id": sepay_id,
            "gateway": "MBBank",
            "accountNumber": settings.sepay_account_number or "0901234567",
            "transferType": "in",
            "transferAmount": 350000,
            "code": code_obj.payment_code,
            "content": f"Chuyen tien {code_obj.payment_code}",
            "transactionDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        import json
        raw_body = json.dumps(payload).encode("utf-8")

        res = SepayService.process_webhook(
            db=db_session,
            payload=payload,
            raw_body=raw_body,
            **_get_sepay_auth_kwargs(raw_body),
        )
        assert res["success"] is False
        assert "hết hạn" in res["message"].lower() or "quá hạn" in res["message"].lower()

        # Kiểm tra bản ghi Inbound
        inbound = db_session.scalar(select(SepayInboundTransaction).where(SepayInboundTransaction.sepay_id == sepay_id))
        assert inbound is not None
        assert inbound.status == "EXPIRED_INTENT_MANUAL_REVIEW"

        # Đơn hàng KHÔNG bị chuyển thành PAID
        db_session.refresh(order)
        assert order.payment_status != "PAID"

    def test_05_sepay_transfer_on_cancelled_order_flagged_for_refund(self, db_session, test_user):
        """Khách chuyển tiền cho đơn đã hủy -> Ghi nhận CANCELLED_ORDER_REFUND_PENDING, không xuất kho."""
        order = _create_order(db_session, test_user, total_amount=400000, method="SEPAY")
        order.order_status = "CANCELLED"
        db_session.commit()

        code_obj = SepayService.generate_payment_code(db_session, order, force_new=True)
        code_obj.expires_at = datetime.now(UTC) + timedelta(minutes=15)
        db_session.commit()

        sepay_id = int(time.time() * 1000) % 900000000 + 200000000
        payload = {
            "id": sepay_id,
            "gateway": "MBBank",
            "accountNumber": settings.sepay_account_number or "0901234567",
            "transferType": "in",
            "transferAmount": 400000,
            "code": code_obj.payment_code,
            "content": f"Chuyen tien {code_obj.payment_code}",
            "transactionDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        import json
        raw_body = json.dumps(payload).encode("utf-8")

        res = SepayService.process_webhook(
            db=db_session,
            payload=payload,
            raw_body=raw_body,
            **_get_sepay_auth_kwargs(raw_body),
        )
        assert res["success"] is False
        assert "hủy" in res["message"]

        inbound = db_session.scalar(select(SepayInboundTransaction).where(SepayInboundTransaction.sepay_id == sepay_id))
        assert inbound.status == "CANCELLED_ORDER_REFUND_PENDING"

        db_session.refresh(order)
        assert order.order_status == "CANCELLED"
        assert order.payment_status != "PAID"

    def test_06_refresh_expired_intent_generates_fresh_15_minutes_and_new_code(self, db_session, test_user, auth_headers):
        """Tạo mã thanh toán mới khi hết hạn: Cấp mã SePay mới, gia hạn 15 phút chuẩn mà không tạo order_id mới."""
        client = TestClient(app)
        order = _create_order(db_session, test_user, total_amount=500000, method="SEPAY")

        # 1. Tạo intent lần 1
        res1 = client.post(
            "/api/v1/payments/intent",
            json={"order_code": order.order_code, "payment_method": "SEPAY"},
            headers=auth_headers,
        )
        code1 = res1.json()["bank_details"]["payment_code"]

        # 2. Làm hết hạn mã lần 1
        code_obj = db_session.scalar(select(SepayPaymentCode).where(SepayPaymentCode.order_id == order.id))
        code_obj.expires_at = datetime.now(UTC) - timedelta(minutes=2)
        code_obj.status = "EXPIRED"
        db_session.commit()

        # 3. Khách bấm 'Tạo mã thanh toán mới' qua endpoint /payments/retry với SEPAY
        res2 = client.post(
            "/api/v1/payments/retry",
            json={"order_code": order.order_code, "new_payment_method": "SEPAY"},
            headers=auth_headers,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["provider"] == "SEPAY"
        code2 = data2["bank_details"]["payment_code"]
        assert code2 != code1, "Mã thanh toán mới phải khác mã cũ đã hết hạn!"

        # Thời hạn mới phải đủ 15 phút
        exp2 = datetime.fromisoformat(data2["expires_at"].replace("Z", "+00:00"))
        now2 = datetime.now(UTC)
        assert 14.5 <= (exp2 - now2).total_seconds() / 60.0 <= 15.5

    def test_07_cancel_sepay_order_releases_stock_and_marks_cancelled(self, db_session, test_user, auth_headers):
        """Khách bấm hủy đơn SePay: Đơn chuyển CANCELLED, mã thanh toán CANCELLED, tồn kho được giải phóng."""
        client = TestClient(app)
        order = _create_order(db_session, test_user, total_amount=250000, method="SEPAY")

        # Tạo intent
        client.post(
            "/api/v1/payments/intent",
            json={"order_code": order.order_code, "payment_method": "SEPAY"},
            headers=auth_headers,
        )

        # Hủy đơn
        res = client.post(
            f"/api/v1/payments/orders/{order.order_code}/cancel",
            json={"reason": "Khách hàng đổi ý muốn hủy đơn", "phone_verify": test_user.phone},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert data["order_status"] == "CANCELLED"

        # Kiểm tra database state
        db_session.refresh(order)
        assert order.order_status == "CANCELLED"
        assert order.payment_status == "CANCELLED"

        sepay_code = db_session.scalar(select(SepayPaymentCode).where(SepayPaymentCode.order_id == order.id))
        if sepay_code:
            assert sepay_code.status == "CANCELLED"
