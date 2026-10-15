from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models import CanonicalProduct, Order, OrderItem, ProductSku, User
from app.models.enums import PublishStatus, RxOtcStatus, UserRole


@pytest.fixture
def auth_tokens(database):
    """
    Sinh JWT token cho các role khác nhau:
    - Buyer A (UserRole.CUSTOMER)
    - Buyer B (UserRole.CUSTOMER)
    - Staff (UserRole.WAREHOUSE_STAFF)
    - Admin (UserRole.ADMIN)
    """
    with SessionLocal() as db:
        # Buyer A
        buyer_a = db.scalar(select(User).where(User.email == "buyer_a@pharmatrust.vn"))
        if not buyer_a:
            buyer_a = User(
                email="buyer_a@pharmatrust.vn",
                password_hash=hash_password("Pass@123456"),
                full_name="Nguyễn Văn A",
                role=UserRole.CUSTOMER,
                phone="0901111111",
                is_active=True,
                token_version=1,
            )
            db.add(buyer_a)

        # Buyer B
        buyer_b = db.scalar(select(User).where(User.email == "buyer_b@pharmatrust.vn"))
        if not buyer_b:
            buyer_b = User(
                email="buyer_b@pharmatrust.vn",
                password_hash=hash_password("Pass@123456"),
                full_name="Trần Thị B",
                role=UserRole.CUSTOMER,
                phone="0902222222",
                is_active=True,
                token_version=1,
            )
            db.add(buyer_b)

        # Admin
        admin = db.scalar(select(User).where(User.email == "admin@pharmatrust.vn"))
        if not admin:
            admin = User(
                email="admin@pharmatrust.vn",
                password_hash=hash_password("Admin@123456"),
                full_name="Admin Hệ Thống",
                role=UserRole.ADMIN,
                phone="0900000001",
                is_active=True,
                token_version=1,
            )
            db.add(admin)

        # Staff
        reviewer = db.scalar(select(User).where(User.email == "reviewer@pharmatrust.vn"))
        if not reviewer:
            reviewer = User(
                email="reviewer@pharmatrust.vn",
                password_hash=hash_password("Reviewer@123456"),
                full_name="Nhân Viên Kho",
                role=UserRole.WAREHOUSE_STAFF,
                phone="0900000002",
                is_active=True,
                token_version=1,
            )
            db.add(reviewer)

        db.commit()
        db.refresh(buyer_a)
        db.refresh(buyer_b)
        db.refresh(admin)
        db.refresh(reviewer)

        buyer_a_id = buyer_a.id
        buyer_b_id = buyer_b.id
        admin_id = admin.id
        reviewer_id = reviewer.id

    token_a = create_access_token(subject=str(buyer_a_id), role="CUSTOMER", token_version=1)
    token_b = create_access_token(subject=str(buyer_b_id), role="CUSTOMER", token_version=1)
    token_admin = create_access_token(subject=str(admin_id), role="ADMIN", token_version=1)
    token_rev = create_access_token(subject=str(reviewer_id), role="WAREHOUSE_STAFF", token_version=1)

    return {
        "buyer_a_id": buyer_a_id,
        "buyer_b_id": buyer_b_id,
        "admin_id": admin_id,
        "reviewer_id": reviewer_id,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
        "headers_admin": {"Authorization": f"Bearer {token_admin}"},
        "headers_reviewer": {"Authorization": f"Bearer {token_rev}"},
    }


@pytest.fixture
def sample_orders_a_and_b(database, auth_tokens):
    """Tạo 2 đơn hàng: 1 của Buyer A, 1 của Buyer B"""
    with SessionLocal() as db:
        prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.publish_status == PublishStatus.PUBLISHED))
        if not prod:
            prod = CanonicalProduct(
                canonical_name="Thuốc thử nghiệm",
                publish_status=PublishStatus.PUBLISHED,
                rx_otc_status=RxOtcStatus.OTC,
            )
            db.add(prod)
            db.flush()

        order_a = db.scalar(select(Order).where(Order.order_code == "PT-SEC-A001"))
        if not order_a:
            order_a = Order(
                order_code="PT-SEC-A001",
                user_id=auth_tokens["buyer_a_id"],
                customer_name="Nguyễn Văn A",
                customer_phone="0901111111",
                shipping_address="123 Lê Lợi, Q1, HCM",
                total_amount=Decimal("150000.0"),
                order_status="PENDING",
                payment_status="PENDING",
                created_at=datetime.now(UTC),
            )
            db.add(order_a)

        order_b = db.scalar(select(Order).where(Order.order_code == "PT-SEC-B002"))
        if not order_b:
            order_b = Order(
                order_code="PT-SEC-B002",
                user_id=auth_tokens["buyer_b_id"],
                customer_name="Trần Thị B",
                customer_phone="0902222222",
                shipping_address="456 Nguyễn Huệ, Q1, HCM",
                total_amount=Decimal("200000.0"),
                order_status="PENDING",
                payment_status="PENDING",
                created_at=datetime.now(UTC),
            )
            db.add(order_b)

        db.commit()

    return {"order_a_code": "PT-SEC-A001", "order_b_code": "PT-SEC-B002"}


# ==============================================================================
# 1. ANONYMOUS ACCESS TESTS (401 / 403)
# ==============================================================================

def test_anonymous_access_blocked(client: TestClient, sample_orders_a_and_b):
    """Người dùng chưa đăng nhập (không JWT) bị chặn truy cập tất cả API riêng tư"""
    code = sample_orders_a_and_b["order_a_code"]

    # 1. Xem đơn hàng store -> 401
    res = client.get(f"/api/v1/store/orders/{code}")
    assert res.status_code == 401

    # 2. Tìm kiếm theo SĐT -> 403 (bị vô hiệu hóa vì lý do bảo mật)
    res = client.get("/api/v1/store/orders/customer/0901111111")
    assert res.status_code == 403

    # 3. Xem trạng thái thanh toán -> 401
    res = client.get(f"/api/v1/payments/orders/{code}/status")
    assert res.status_code == 401

    # 4. Đối soát đơn hàng -> 401
    res = client.get(f"/api/v1/payments/reconciliation/order/{code}")
    assert res.status_code == 401

    # 5. Đối soát hệ thống -> 401
    res = client.get("/api/v1/payments/reconciliation/audit")
    assert res.status_code == 401

    # 6. Hủy đơn thanh toán -> 401
    res = client.post(f"/api/v1/payments/orders/{code}/cancel", json={"reason": "Test"})
    assert res.status_code == 401

    # 7. Me profile & orders -> 401
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me/orders").status_code == 401
    assert client.get("/api/v1/me/addresses").status_code == 401


# ==============================================================================
# 2. IDOR PROTECTION TESTS (Buyer A vs Buyer B)
# ==============================================================================

def test_idor_buyer_a_cannot_view_buyer_b_order(client: TestClient, auth_tokens, sample_orders_a_and_b):
    """Buyer A không được xem đơn hàng của Buyer B qua /store/orders/{code} (403)"""
    order_b_code = sample_orders_a_and_b["order_b_code"]
    res = client.get(f"/api/v1/store/orders/{order_b_code}", headers=auth_tokens["headers_a"])
    assert res.status_code == 403
    assert "không có quyền" in res.json()["detail"].lower()


def test_idor_buyer_a_cannot_view_buyer_b_via_me_orders(client: TestClient, auth_tokens, sample_orders_a_and_b):
    """Buyer A không tìm thấy đơn của Buyer B qua /me/orders/{code} (404)"""
    order_b_code = sample_orders_a_and_b["order_b_code"]
    res = client.get(f"/api/v1/me/orders/{order_b_code}", headers=auth_tokens["headers_a"])
    assert res.status_code == 404


def test_idor_buyer_a_cannot_cancel_buyer_b_order(client: TestClient, auth_tokens, sample_orders_a_and_b):
    """Buyer A không thể hủy đơn của Buyer B qua cả 2 endpoint hủy đơn (403 / 404)"""
    order_b_code = sample_orders_a_and_b["order_b_code"]

    # Qua /payments/orders/{code}/cancel -> 403
    res1 = client.post(
        f"/api/v1/payments/orders/{order_b_code}/cancel",
        json={"reason": "Tấn công IDOR"},
        headers=auth_tokens["headers_a"],
    )
    assert res1.status_code == 403

    # Qua /me/orders/{code}/cancel -> 404 (do lọc theo user_id của Buyer A)
    res2 = client.post(
        f"/api/v1/me/orders/{order_b_code}/cancel",
        json={"reason": "Tấn công IDOR"},
        headers=auth_tokens["headers_a"],
    )
    assert res2.status_code == 404


def test_idor_buyer_a_cannot_view_buyer_b_payment_status(client: TestClient, auth_tokens, sample_orders_a_and_b):
    """Buyer A không thể xem trạng thái thanh toán của đơn hàng Buyer B (403)"""
    order_b_code = sample_orders_a_and_b["order_b_code"]
    res = client.get(f"/api/v1/payments/orders/{order_b_code}/status", headers=auth_tokens["headers_a"])
    assert res.status_code == 403


# ==============================================================================
# 3. RBAC & DATA REVIEWER PRIVILEGE ENFORCEMENT
# ==============================================================================

def test_warehouse_staff_cannot_view_or_process_admin_orders(client: TestClient, auth_tokens, sample_orders_a_and_b):
    """
    WAREHOUSE_STAFF không được xem đơn hàng của khách khác hoặc truy cập trang quản trị admin.
    """
    order_a_code = sample_orders_a_and_b["order_a_code"]

    # DATA_REVIEWER xem đơn hàng store -> 403
    res1 = client.get(f"/api/v1/store/orders/{order_a_code}", headers=auth_tokens["headers_reviewer"])
    assert res1.status_code == 403

    # DATA_REVIEWER xem danh sách đơn hàng admin -> 403
    res2 = client.get("/api/v1/admin/orders", headers=auth_tokens["headers_reviewer"])
    assert res2.status_code == 403

    # DATA_REVIEWER đối soát -> 403
    res3 = client.get("/api/v1/payments/reconciliation/audit", headers=auth_tokens["headers_reviewer"])
    assert res3.status_code == 403


def test_admin_can_view_and_reconcile(client: TestClient, auth_tokens, sample_orders_a_and_b):
    """ADMIN có toàn quyền xem đơn và đối soát"""
    order_a_code = sample_orders_a_and_b["order_a_code"]

    res1 = client.get(f"/api/v1/store/orders/{order_a_code}", headers=auth_tokens["headers_admin"])
    assert res1.status_code == 200
    assert res1.json()["order_code"] == order_a_code

    res2 = client.get("/api/v1/payments/reconciliation/audit", headers=auth_tokens["headers_admin"])
    assert res2.status_code == 200


# ==============================================================================
# 4. BUYER SELF-CANCEL BUSINESS RULE (PENDING or <= 30 mins)
# ==============================================================================

def test_buyer_can_cancel_own_pending_order(client: TestClient, auth_tokens, sample_orders_a_and_b):
    """Buyer A tự hủy đơn hàng PENDING của chính mình thành công & idempotent"""
    order_a_code = sample_orders_a_and_b["order_a_code"]

    res = client.post(
        f"/api/v1/me/orders/{order_a_code}/cancel",
        json={"reason": "Tôi đặt nhầm sản phẩm"},
        headers=auth_tokens["headers_a"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["order_status"] == "CANCELLED"

    # Idempotent retry: hủy lần 2 vẫn thành công và an toàn
    res_retry = client.post(
        f"/api/v1/me/orders/{order_a_code}/cancel",
        json={"reason": "Thử lại lần 2"},
        headers=auth_tokens["headers_a"],
    )
    assert res_retry.status_code == 200
    assert res_retry.json()["order_status"] == "CANCELLED"
