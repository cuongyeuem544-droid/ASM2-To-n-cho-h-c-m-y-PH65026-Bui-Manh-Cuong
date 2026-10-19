"""
Regression tests for Issue 1 (Dòng 4): Dữ liệu người dùng không nhất quán.
Verifies:
1. Canonicalization of relative SQLite database URLs to the project root across different CWDs.
2. Production and Staging fail-fast check when SQLite is configured.
3. User persistence across database restarts and seeding (passwords are preserved, no unwanted reset).
4. Strict data isolation between User A and User B (orders, addresses).
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, _REPO_ROOT
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models.entities import Order, OrderItem, User
from app.models.inventory import CustomerAddress
from app.models.enums import UserRole
from app.db.session import SessionLocal
from app.seed import seed_users


def test_settings_canonicalize_database_url_from_any_cwd():
    """Kiểm tra đường dẫn SQLite tương đối luôn chuẩn hóa về thư mục gốc dự án dù CWD là đâu."""
    # 1. Đường dẫn mặc định sqlite:///./pharmatrust.db
    s1 = Settings(database_url="sqlite:///./pharmatrust.db")
    expected_default = f"sqlite:///{(_REPO_ROOT / 'pharmatrust.db').resolve().as_posix()}"
    assert s1.database_url == expected_default

    # 2. Đường dẫn không có ./
    s2 = Settings(database_url="sqlite:///pharmatrust.db")
    assert s2.database_url == expected_default

    # 3. Đường dẫn thư mục con tương đối
    s3 = Settings(database_url="sqlite:///data/custom.db")
    expected_sub = f"sqlite:///{(_REPO_ROOT / 'data' / 'custom.db').resolve().as_posix()}"
    assert s3.database_url == expected_sub

    # 4. In-memory và PostgreSQL không bị can thiệp
    s_mem = Settings(database_url="sqlite:///:memory:")
    assert s_mem.database_url == "sqlite:///:memory:"

    s_pg = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/pharma")
    assert s_pg.database_url == "postgresql+psycopg://user:pass@localhost:5432/pharma"


def test_production_failfast_on_sqlite():
    """Môi trường production/staging bắt buộc fail-fast nếu sử dụng SQLite."""
    with pytest.raises(ValueError, match="CSDL dùng chung"):
        Settings(
            app_env="production",
            database_url="sqlite:///pharmatrust.db",
            secret_key="a" * 32,
        )

    with pytest.raises(ValueError, match="CSDL dùng chung"):
        Settings(
            app_env="staging",
            database_url="sqlite:///./data.db",
            secret_key="a" * 32,
        )


def test_user_password_preserved_on_reseed():
    """Đảm bảo tài khoản người dùng đã đổi mật khẩu không bị reset khi chạy seed."""
    with SessionLocal() as db:
        test_email = "buyer@pharmatrust.vn"
        user = db.scalar(select(User).where(User.email == test_email))
        if not user:
            user = User(
                email=test_email,
                password_hash=hash_password("Original@123"),
                full_name="Người mua hàng",
                role=UserRole.CUSTOMER,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        original_hash = user.password_hash
        try:
            # Người dùng đổi mật khẩu thành mật khẩu mới
            new_custom_password = "MyNewCustomPass@2026!"
            user.password_hash = hash_password(new_custom_password)
            db.commit()

            # Chạy lại seed_users
            seed_users(db)
            db.commit()
            db.refresh(user)

            # Mật khẩu mới vẫn phải được bảo toàn, không bị ghi đè bởi seed
            assert verify_password(new_custom_password, user.password_hash) is True
        finally:
            user.password_hash = original_hash
            db.commit()


def test_user_data_isolation_between_customers(client: TestClient):
    """Người dùng A tạo đơn hàng và địa chỉ, Người dùng B không được nhìn thấy."""
    import uuid
    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        # Tạo User A
        user_a = User(
            email=f"user_a_{suffix}@test.vn",
            password_hash=hash_password("PassA@123456"),
            full_name="Nguyễn Văn A",
            phone=f"091100{suffix[:4]}",
            role=UserRole.CUSTOMER,
            is_active=True,
            token_version=1,
        )
        # Tạo User B
        user_b = User(
            email=f"user_b_{suffix}@test.vn",
            password_hash=hash_password("PassB@123456"),
            full_name="Trần Thị B",
            phone=f"091200{suffix[:4]}",
            role=UserRole.CUSTOMER,
            is_active=True,
            token_version=1,
        )
        db.add_all([user_a, user_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)

        # User A thêm địa chỉ
        addr_a = CustomerAddress(
            user_id=user_a.id,
            recipient_name="Nguyễn Văn A",
            phone="0911000001",
            address_line="10 Đường Số 1",
            province_code="79",
            district_code="760",
            commune_code="26734",
            formatted_address="10 Đường Số 1, Phường Bến Nghé, Quận 1, TP.HCM",
            is_default=True,
        )
        # User A có đơn hàng
        order_a = Order(
            order_code=f"ORD-ISO-A-{suffix}",
            user_id=user_a.id,
            customer_name="Nguyễn Văn A",
            customer_phone="0911000001",
            shipping_address="10 Đường Số 1, Phường Bến Nghé, Quận 1, TP.HCM",
            shipping_city="Hồ Chí Minh",
            order_status="PENDING",
            total_amount=150000,
        )
        db.add_all([addr_a, order_a])
        db.commit()
        db.refresh(addr_a)
        db.refresh(order_a)

        token_b = create_access_token(
            subject=str(user_b.id),
            role=user_b.role.value,
            token_version=user_b.token_version,
        )
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B truy vấn danh sách địa chỉ -> Phải rỗng đối với địa chỉ của A
        res_addr = client.get("/api/v1/customer/addresses", headers=headers_b)
        assert res_addr.status_code == 200
        addr_list = res_addr.json()
        assert all(a["id"] != addr_a.id for a in addr_list)

        # User B cố truy vấn chi tiết địa chỉ của User A bằng ID -> 404
        res_single_addr = client.get(f"/api/v1/customer/addresses/{addr_a.id}", headers=headers_b)
        assert res_single_addr.status_code == 404

        # User B truy vấn lịch sử đơn hàng của mình (/me) -> Không thấy đơn của User A
        res_orders = client.get("/api/v1/store/orders/me", headers=headers_b)
        assert res_orders.status_code == 200
        orders_data = res_orders.json().get("items", [])
        assert all(o["id"] != order_a.id for o in orders_data)

