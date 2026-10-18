import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import User
from app.models.enums import UserRole


@pytest.fixture
def chat_auth_fixture(database):
    """Tạo user kiểm thử và JWT Bearer headers cho chat."""
    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        customer = User(
            email=f"chat_customer_{suffix}@pharmatrust.vn",
            password_hash=hash_password("Pass@123456"),
            full_name="Nguyễn Văn Chat",
            role=UserRole.CUSTOMER,
            phone="0912345678",
            is_active=True,
            token_version=1,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        token = create_access_token(str(customer.id), customer.role.value)

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": customer.id,
    }


def test_chat_unauthenticated_rejected(client: TestClient):
    """Kiểm tra gọi POST /api/v1/chat khi chưa đăng nhập sẽ bị từ chối 401."""
    res = client.post(
        "/api/v1/chat",
        json={"message": "Xin chào bác sĩ"},
    )
    assert res.status_code == 401
    assert "chưa đăng nhập" in res.json().get("detail", "").lower()


def test_chat_invalid_token_rejected(client: TestClient):
    """Kiểm tra gọi POST /api/v1/chat với token giả mạo bị từ chối 401."""
    res = client.post(
        "/api/v1/chat",
        headers={"Authorization": "Bearer invalid_token_xyz_123"},
        json={"message": "Xin chào bác sĩ"},
    )
    assert res.status_code == 401


def test_chat_authenticated_greeting(client: TestClient, chat_auth_fixture):
    """Kiểm tra chào hỏi trả về đúng mẫu câu chào tự nhiên của Trợ lý AI H4CARE."""
    res = client.post(
        "/api/v1/chat",
        headers=chat_auth_fixture["headers"],
        json={"message": "Xin chào shop"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "Chào bạn! Mình là trợ lý AI của H4CARE" in data["reply"]
    assert "Bạn cần mình hỗ trợ điều gì hôm nay?" in data["reply"]
    # Kiểm tra không chứa cụm từ quảng cáo
    assert "tra cứu thuốc chính hãng" not in data["reply"].lower()


def test_chat_authenticated_identity(client: TestClient, chat_auth_fixture):
    """Kiểm tra định danh trợ lý AI không chứa slogan quảng cáo."""
    res = client.post(
        "/api/v1/chat",
        headers=chat_auth_fixture["headers"],
        json={"message": "Bạn là ai vậy?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "Trợ lý AI H4CARE" in data["reply"]
    assert "tra cứu thuốc chính hãng" not in data["reply"].lower()


def test_chat_red_flag_emergency_alert(client: TestClient, chat_auth_fixture):
    """Kiểm tra dấu hiệu nguy hiểm (Red Flag) kích hoạt cảnh báo khẩn cấp 115."""
    res = client.post(
        "/api/v1/chat",
        headers=chat_auth_fixture["headers"],
        json={"message": "Bố tôi bị khó thở dữ dội"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["safety_alert"] is not None
    assert data["safety_alert"]["level"] == "emergency"
    assert "115" in data["safety_alert"]["emergency_number"]
    assert "CẢNH BÁO" in data["reply"]
