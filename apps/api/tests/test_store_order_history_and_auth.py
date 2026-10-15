from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import (
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderItem,
    ProductSku,
    User,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.inventory import BatchStatus
from app.models.enums import PublishStatus, RxOtcStatus, UserRole


@pytest.fixture
def auth_fixture(database):
    """Thiết lập các tài khoản kiểm thử và JWT headers tương ứng."""
    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        user_a = User(
            email=f"customer_a_{suffix}@pharmatrust.vn",
            password_hash=hash_password("Pass@123456"),
            full_name="Nguyễn Văn A (Khách Hàng A)",
            role=UserRole.CUSTOMER,
            phone="0901234567",
            is_active=True,
            token_version=1,
        )
        user_b = User(
            email=f"customer_b_{suffix}@pharmatrust.vn",
            password_hash=hash_password("Pass@123456"),
            full_name="Trần Thị B (Khách Hàng B)",
            role=UserRole.CUSTOMER,
            phone="0987654321",
            is_active=True,
            token_version=1,
        )
        admin = User(
            email=f"admin_{suffix}@pharmatrust.vn",
            password_hash=hash_password("Admin@123456"),
            full_name="Quản Trị Viên Hệ Thống",
            role=UserRole.ADMIN,
            phone="0909999999",
            is_active=True,
            token_version=1,
        )
        db.add_all([user_a, user_b, admin])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)
        db.refresh(admin)

        user_a_id = user_a.id
        user_b_id = user_b.id
        admin_id = admin.id

    token_a = create_access_token(subject=str(user_a_id), role="CUSTOMER", token_version=1)
    token_b = create_access_token(subject=str(user_b_id), role="CUSTOMER", token_version=1)
    token_admin = create_access_token(subject=str(admin_id), role="ADMIN", token_version=1)

    return {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "admin_id": admin_id,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
        "headers_admin": {"Authorization": f"Bearer {token_admin}"},
    }


@pytest.fixture
def product_sku_fixture(database):
    """Tạo sản phẩm OTC hợp lệ và tồn kho để kiểm thử checkout."""
    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name=f"Paracetamol 500mg Test {suffix}",
            publish_status=PublishStatus.PUBLISHED,
            rx_otc_status=RxOtcStatus.OTC,
            registration_number=f"VD-{suffix}",
        )
        db.add(prod)
        db.flush()

        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code=f"SKU-TEST-{suffix}",
            uom="Hộp",
            conversion_rate=1,
            base_price=Decimal("50000.0"),
            is_default=True,
            is_active=True,
        )
        db.add(sku)
        db.flush()

        wh = db.scalar(select(Warehouse).where(Warehouse.is_active == True))
        if not wh:
            wh = Warehouse(
                warehouse_code=f"WH-TEST-{suffix}",
                warehouse_name="Kho Trung Tâm Kiểm Thử",
                is_active=True,
            )
            db.add(wh)
            db.flush()

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"BATCH-{suffix}",
            expiry_date=datetime.now().date() + timedelta(days=365),
            initial_quantity=500,
            status=BatchStatus.ACTIVE,
        )
        db.add(batch)
        db.flush()

        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=500,
            quantity_reserved=0,
            quantity_available=500,
        )
        db.add(stock)
        db.commit()

        prod_id = prod.id
        sku_id = sku.id

    return {"prod_id": prod_id, "sku_id": sku_id}


def _build_checkout_payload(prod_id: int, sku_id: int, phone: str = "0901234567", idem_key: str | None = None):
    return {
        "customer_name": "Người Mua Kiểm Thử",
        "customer_phone": phone,
        "customer_email": "buyer.test@example.com",
        "shipping_address": "123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
        "shipping_city": "TP. Hồ Chí Minh",
        "province_code": "79",
        "district_code": "760",
        "ward_code": "26734",
        "lat": 10.7769,
        "lng": 106.7009,
        "is_verified": True,
        "payment_method": "COD",
        "idempotency_key": idem_key or f"IDEM-{uuid.uuid4().hex[:12]}",
        "items": [
            {
                "product_id": prod_id,
                "sku_id": sku_id,
                "quantity": 2,
            }
        ],
    }


# ==============================================================================
# 12 TEST CASES - BẢO MẬT & LỊCH SỬ ĐƠN HÀNG H4CARE
# ==============================================================================

def test_01_authenticated_checkout_links_user_id(client: TestClient, auth_fixture, product_sku_fixture):
    """1. Đặt hàng khi đăng nhập: Order.user_id = current_user.id."""
    payload = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"])
    resp = client.post(
        "/api/v1/store/orders/checkout",
        json=payload,
        headers=auth_fixture["headers_a"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    order_code = data["order_code"]

    with SessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        assert order is not None
        assert order.user_id == auth_fixture["user_a_id"]
        assert len(order.items) == 1


def test_02_guest_checkout_without_token_sets_user_id_none(client: TestClient, product_sku_fixture):
    """2. Khách vãng lai đặt hàng không gửi token: Order.user_id = None."""
    payload = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"])
    resp = client.post("/api/v1/store/orders/checkout", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    order_code = data["order_code"]

    with SessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        assert order is not None
        assert order.user_id is None


def test_03_checkout_with_invalid_or_expired_token_returns_401(client: TestClient, product_sku_fixture):
    """3. Có gửi Authorization nhưng token sai/hết hạn: Trả HTTP 401, không tạo đơn."""
    payload = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"])
    resp = client.post(
        "/api/v1/store/orders/checkout",
        json=payload,
        headers={"Authorization": "Bearer invalid_or_expired_token_xyz"},
    )
    assert resp.status_code == 401
    assert "Token không hợp lệ hoặc đã hết hạn" in resp.json()["detail"]


def test_04_get_my_orders_with_valid_token(client: TestClient, auth_fixture, product_sku_fixture):
    """4. GET /store/orders/me với token hợp lệ: Trả đúng danh sách đơn của user, tải items."""
    # Tạo 2 đơn hàng cho User A
    p1 = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"])
    p2 = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"])
    r1 = client.post("/api/v1/store/orders/checkout", json=p1, headers=auth_fixture["headers_a"])
    r2 = client.post("/api/v1/store/orders/checkout", json=p2, headers=auth_fixture["headers_a"])
    assert r1.status_code == 200
    assert r2.status_code == 200

    resp = client.get("/api/v1/store/orders/me", headers=auth_fixture["headers_a"])
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 2
    # Đơn mới nhất xếp trước
    order_codes = [it["order_code"] for it in data["items"]]
    assert r2.json()["order_code"] in order_codes
    assert r1.json()["order_code"] in order_codes
    # Items eager loaded
    assert len(data["items"][0]["items"]) >= 1


def test_05_get_my_orders_without_token_returns_401(client: TestClient):
    """5. GET /store/orders/me không có token: Trả HTTP 401."""
    resp = client.get("/api/v1/store/orders/me")
    assert resp.status_code == 401


def test_06_get_my_orders_with_invalid_token_returns_401(client: TestClient):
    """6. GET /store/orders/me với token sai: Trả HTTP 401."""
    resp = client.get(
        "/api/v1/store/orders/me",
        headers={"Authorization": "Bearer invalid_bad_token_123"},
    )
    assert resp.status_code == 401


def test_07_idor_protection_user_b_cannot_see_user_a_orders(client: TestClient, auth_fixture, product_sku_fixture):
    """7. Kiểm tra IDOR: Khách B không thấy đơn của Khách A."""
    # Khách A tạo 1 đơn hàng
    p_a = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"])
    r_a = client.post("/api/v1/store/orders/checkout", json=p_a, headers=auth_fixture["headers_a"])
    order_code_a = r_a.json()["order_code"]

    # Khách B xem danh sách đơn của mình
    resp_b = client.get("/api/v1/store/orders/me", headers=auth_fixture["headers_b"])
    assert resp_b.status_code == 200
    b_order_codes = [it["order_code"] for it in resp_b.json()["items"]]
    assert order_code_a not in b_order_codes

    # Khách B cố truy cập đơn A qua GET /{order_code} -> Trả 403 Forbidden
    resp_detail = client.get(f"/api/v1/store/orders/{order_code_a}", headers=auth_fixture["headers_b"])
    assert resp_detail.status_code == 403


def test_08_idempotency_replay_same_user_returns_existing_order(client: TestClient, auth_fixture, product_sku_fixture):
    """8. Replay Idempotency key cùng User: Trả đơn cũ (200), is_idempotent_replay = True."""
    idem_key = f"IDEM-SAME-USER-{uuid.uuid4().hex[:8]}"
    payload = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"], idem_key=idem_key)

    r1 = client.post("/api/v1/store/orders/checkout", json=payload, headers=auth_fixture["headers_a"])
    assert r1.status_code == 200
    code1 = r1.json()["order_code"]

    # Gửi lại lần 2 với cùng User A
    r2 = client.post("/api/v1/store/orders/checkout", json=payload, headers=auth_fixture["headers_a"])
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["order_code"] == code1
    assert data2.get("is_idempotent_replay") is True


def test_09_idempotency_conflict_different_user_returns_409(client: TestClient, auth_fixture, product_sku_fixture):
    """9. Replay Idempotency key nhưng khác User: Trả HTTP 409 Conflict."""
    idem_key = f"IDEM-CONFLICT-{uuid.uuid4().hex[:8]}"
    payload = _build_checkout_payload(product_sku_fixture["prod_id"], product_sku_fixture["sku_id"], idem_key=idem_key)

    # User A tạo trước
    r1 = client.post("/api/v1/store/orders/checkout", json=payload, headers=auth_fixture["headers_a"])
    assert r1.status_code == 200

    # User B (hoặc Guest) dùng cùng idempotency key -> 409 Conflict
    r2 = client.post("/api/v1/store/orders/checkout", json=payload, headers=auth_fixture["headers_b"])
    assert r2.status_code == 409
    assert "xung đột" in r2.json()["detail"].lower()


def test_10_guest_lookup_matching_code_and_phone(client: TestClient, product_sku_fixture):
    """10. Guest lookup: Khớp cả mã đơn và SĐT -> Trả đơn hàng và che bớt số điện thoại."""
    guest_phone = "0912345678"
    payload = _build_checkout_payload(
        product_sku_fixture["prod_id"],
        product_sku_fixture["sku_id"],
        phone=guest_phone,
    )
    r_create = client.post("/api/v1/store/orders/checkout", json=payload)
    assert r_create.status_code == 200
    order_code = r_create.json()["order_code"]

    lookup_payload = {
        "order_code": order_code,
        "customer_phone": guest_phone,
    }
    r_lookup = client.post("/api/v1/store/orders/guest-lookup", json=lookup_payload)
    assert r_lookup.status_code == 200
    data = r_lookup.json()
    assert data["order_code"] == order_code
    assert "****" in data["customer_phone"]
    assert len(data["items"]) >= 1


def test_11_guest_lookup_mismatched_phone_returns_404(client: TestClient, product_sku_fixture):
    """11. Guest lookup: Sai số điện thoại -> Trả 404 Không tìm thấy (chống dò đơn)."""
    payload = _build_checkout_payload(
        product_sku_fixture["prod_id"],
        product_sku_fixture["sku_id"],
        phone="0911223344",
    )
    r_create = client.post("/api/v1/store/orders/checkout", json=payload)
    assert r_create.status_code == 200
    order_code = r_create.json()["order_code"]

    lookup_payload = {
        "order_code": order_code,
        "customer_phone": "0999999999",  # SĐT không khớp
    }
    r_lookup = client.post("/api/v1/store/orders/guest-lookup", json=lookup_payload)
    assert r_lookup.status_code == 404


def test_12_legacy_phone_endpoint_forbidden_for_non_admin(client: TestClient, auth_fixture):
    """12. GET /customer/{phone}: Cho phép khách hàng tra cứu đúng SĐT của mình; Chặn 403 đối với SĐT của người khác."""
    target_phone = "0901234567"
    other_phone = "0987654321"

    # Khách vãng lai gọi -> 401 hoặc 403
    r_anon = client.get(f"/api/v1/store/orders/customer/{target_phone}")
    assert r_anon.status_code in [401, 403]

    # Khách hàng gọi tra cứu số của người khác -> 403 Forbidden
    r_other = client.get(
        f"/api/v1/store/orders/customer/{other_phone}",
        headers=auth_fixture["headers_a"],
    )
    assert r_other.status_code == 403

    # Khách hàng gọi tra cứu số của chính mình -> 200 Thành công
    r_own = client.get(
        f"/api/v1/store/orders/customer/{target_phone}",
        headers=auth_fixture["headers_a"],
    )
    assert r_own.status_code == 200

    # Admin gọi -> 200 Thành công
    r_admin = client.get(
        f"/api/v1/store/orders/customer/{target_phone}",
        headers=auth_fixture["headers_admin"],
    )
    assert r_admin.status_code == 200
    assert isinstance(r_admin.json(), list)
