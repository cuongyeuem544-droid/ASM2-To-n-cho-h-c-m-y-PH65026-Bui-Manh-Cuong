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


def test_guest_conversation_ownership_protection(client: TestClient):
    """Kiểm tra Item 7: Lịch sử hội thoại khách vãng lai bắt buộc bằng chứng sở hữu session_id."""
    guest_session_id = "sess-guest-secret-987654"
    wrong_session_id = "sess-attacker-random"

    # 1. Khách vãng lai tạo cuộc trò chuyện
    create_res = client.post(
        "/api/v1/chat/conversations",
        json={
            "session_id": guest_session_id,
            "title": "Hỏi về đau đầu",
            "messages": [
                {"role": "user", "content": "Tôi bị đau đầu 2 ngày nay"},
                {"role": "assistant", "content": "Bạn có kèm theo sốt không?"},
            ],
        },
    )
    assert create_res.status_code == 200
    conv_code = create_res.json()["conversation_code"]
    assert conv_code is not None

    # 2. Kẻ tấn công biết conv_code nhưng không có session_id -> Bị chặn 403 khi đọc
    res_no_sess = client.get(f"/api/v1/chat/conversations/{conv_code}")
    assert res_no_sess.status_code == 403

    # 3. Kẻ tấn công dùng sai session_id -> Bị chặn 403 khi đọc
    res_wrong_sess = client.get(f"/api/v1/chat/conversations/{conv_code}?session_id={wrong_session_id}")
    assert res_wrong_sess.status_code == 403

    # 4. Kẻ tấn công cố đổi tên cuộc trò chuyện -> Bị chặn 403
    res_rename_wrong = client.patch(
        f"/api/v1/chat/conversations/{conv_code}?session_id={wrong_session_id}",
        json={"title": "Hack title"},
    )
    assert res_rename_wrong.status_code == 403

    # 5. Kẻ tấn công cố xóa cuộc trò chuyện -> Bị chặn 403
    res_del_wrong = client.delete(f"/api/v1/chat/conversations/{conv_code}?session_id={wrong_session_id}")
    assert res_del_wrong.status_code == 403

    # 6. Khách vãng lai hợp lệ có session_id khớp -> Đọc được 200
    res_ok = client.get(
        f"/api/v1/chat/conversations/{conv_code}",
        headers={"X-Session-ID": guest_session_id},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["title"] == "Hỏi về đau đầu"
    assert len(res_ok.json()["messages"]) == 2

    # 7. Khách vãng lai hợp lệ đổi tên -> 200
    res_rename_ok = client.patch(
        f"/api/v1/chat/conversations/{conv_code}?session_id={guest_session_id}",
        json={"title": "Hỏi về đau đầu và sốt"},
    )
    assert res_rename_ok.status_code == 200

    # 8. Khách vãng lai hợp lệ xóa cuộc trò chuyện -> 200
    res_del_ok = client.delete(
        f"/api/v1/chat/conversations/{conv_code}",
        headers={"X-Session-ID": guest_session_id},
    )
    assert res_del_ok.status_code == 200

