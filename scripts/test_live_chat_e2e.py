import os
import sys
import io
from pathlib import Path

# Fix encoding on Windows terminal
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đảm bảo PYTHONPATH đúng
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models import User, LiveChatSession, LiveChatMessage
from app.models.enums import UserRole

client = TestClient(app)

def run_tests():
    print("=" * 60)
    print(">>> BẮT ĐẦU KIỂM THỬ TỰ ĐỘNG HỆ THỐNG LIVE CHAT & BẢO MẬT H4CARE")
    print("=" * 60)

    db = SessionLocal()

    # 1. Tạo tài khoản mẫu cho kiểm thử: 1 Dược sĩ, 1 Khách A, 1 Khách B (kẻ tấn công IDOR)
    pharmacist = db.query(User).filter(User.email == "test_pharmacist_chat@h4care.vn").first()
    if not pharmacist:
        pharmacist = User(
            email="test_pharmacist_chat@h4care.vn",
            password_hash=hash_password("Pharmacist123!@#"),
            full_name="DS. Trần Thu Trang",
            role=UserRole.PHARMACIST,
            is_active=True,
        )
        db.add(pharmacist)

    customer_a = db.query(User).filter(User.email == "test_customer_a@gmail.com").first()
    if not customer_a:
        customer_a = User(
            email="test_customer_a@gmail.com",
            password_hash=hash_password("CustomerA123!@#"),
            full_name="Nguyễn Văn Khách A",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db.add(customer_a)

    customer_b = db.query(User).filter(User.email == "test_customer_b@gmail.com").first()
    if not customer_b:
        customer_b = User(
            email="test_customer_b@gmail.com",
            password_hash=hash_password("CustomerB123!@#"),
            full_name="Lê Văn Kẻ Tấn Công B",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db.add(customer_b)

    db.commit()
    db.refresh(pharmacist)
    db.refresh(customer_a)
    db.refresh(customer_b)

    token_pharmacist = create_access_token(str(pharmacist.id), str(pharmacist.role))
    token_customer_a = create_access_token(str(customer_a.id), str(customer_a.role))
    token_customer_b = create_access_token(str(customer_b.id), str(customer_b.role))

    headers_pharmacist = {"Authorization": f"Bearer {token_pharmacist}"}
    headers_customer_a = {"Authorization": f"Bearer {token_customer_a}"}
    headers_customer_b = {"Authorization": f"Bearer {token_customer_b}"}

    # ========================================================
    # TEST 1: Kiểm tra trạng thái trực tuyến khi chưa có nhân viên kết nối WebSocket
    # ========================================================
    res = client.get("/api/v1/live-chat/staff-status")
    assert res.status_code == 200
    data = res.json()
    print("✓ Test 1: Kiểm tra staff status ->", data)
    assert "is_online" in data
    assert "support_hours" in data

    # ========================================================
    # TEST 2: Khách hàng A tạo phiên Live Chat (kèm chuyển tiếp từ AI)
    # ========================================================
    init_payload = {
        "customer_name": "Nguyễn Văn Khách A",
        "customer_phone": "0988123456",
        "subject": "Tư vấn tương tác thuốc Efferalgan và Paracetamol",
        "initial_context": "Khách vừa hỏi Trợ lý AI về liều dùng Paracetamol và tiền sử men gan cao.",
        "shared_ai_history": True,
    }
    res = client.post("/api/v1/live-chat/sessions", json=init_payload, headers=headers_customer_a)
    assert res.status_code == 200, res.text
    session_data = res.json()
    session_code = session_data["session_code"]
    guest_token = session_data["guest_session_token"]
    print(f"✓ Test 2: Khách A tạo phiên thành công -> Mã: {session_code}, Status: {session_data['status']}")
    assert session_data["status"] == "WAITING"
    assert session_data["customer_name"] == "Nguyễn Văn Khách A"
    assert len(session_data["messages"]) >= 1

    # ========================================================
    # TEST 3: Khách hàng A gửi tin nhắn hỏi dược sĩ
    # ========================================================
    msg_payload = {
        "content": "Chào dược sĩ, tôi bị sốt 38.5 độ và có tiền sử men gan cao thì nên dùng hạ sốt loại nào?",
        "client_msg_id": "msg-unique-001",
    }
    res = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/messages",
        json=msg_payload,
        headers=headers_customer_a,
    )
    assert res.status_code == 200
    sent_msg = res.json()
    print(f"✓ Test 3: Khách A gửi tin nhắn thành công -> Content: {sent_msg['content'][:50]}...")
    assert sent_msg["sender_type"] == "CUSTOMER"

    # ========================================================
    # TEST 4: Idempotency chống trùng lặp tin nhắn
    # ========================================================
    res_duplicate = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/messages",
        json=msg_payload,
        headers=headers_customer_a,
    )
    assert res_duplicate.status_code == 200
    assert res_duplicate.json()["id"] == sent_msg["id"], "Idempotency thất bại, đã tạo 2 tin nhắn trùng lặp!"
    print("✓ Test 4: Chống trùng tin nhắn (Idempotency) thành công -> Không sinh tin lặp.")

    # ========================================================
    # TEST 5: Nhân viên Dược sĩ đăng nhập, xem danh sách chờ
    # ========================================================
    res = client.get("/api/v1/live-chat/staff/sessions?status_filter=WAITING", headers=headers_pharmacist)
    assert res.status_code == 200
    staff_sessions = res.json()
    found = any(s["session_code"] == session_code for s in staff_sessions["items"])
    assert found, "Dược sĩ không nhìn thấy phiên chat đang chờ!"
    print(f"✓ Test 5: Dược sĩ xem danh sách chờ -> Tìm thấy ca {session_code} trong hàng đợi.")

    # ========================================================
    # TEST 6: Dược sĩ tiếp nhận ca (Claim)
    # ========================================================
    res = client.post(f"/api/v1/live-chat/staff/sessions/{session_code}/claim", headers=headers_pharmacist)
    assert res.status_code == 200
    claimed_data = res.json()
    assert claimed_data["status"] == "ACTIVE"
    assert claimed_data["assigned_staff_id"] == pharmacist.id
    assert claimed_data["assigned_staff_title"] == "Dược sĩ chuyên môn"
    print(f"✓ Test 6: Dược sĩ tiếp nhận ca thành công -> Phụ trách: {claimed_data['assigned_staff_name']} ({claimed_data['assigned_staff_title']})")

    # ========================================================
    # TEST 7: Dược sĩ trả lời tin nhắn của Khách
    # ========================================================
    reply_payload = {
        "content": "Chào bạn, với tiền sử men gan cao, bạn cần thận trọng tối đa khi dùng Paracetamol, liều tối đa không quá 2g/ngày và nên ưu tiên chườm ấm trước.",
        "client_msg_id": "staff-msg-001",
    }
    res = client.post(
        f"/api/v1/live-chat/staff/sessions/{session_code}/messages",
        json=reply_payload,
        headers=headers_pharmacist,
    )
    assert res.status_code == 200
    staff_msg = res.json()
    assert staff_msg["sender_type"] == "STAFF"
    assert staff_msg["sender_role_title"] == "Dược sĩ chuyên môn"
    print(f"✓ Test 7: Dược sĩ gửi phản hồi thành công -> Khách nhận được tin từ '{staff_msg['sender_role_title']}'.")

    # ========================================================
    # TEST 8: Upload hình ảnh đơn thuốc đính kèm
    # ========================================================
    fake_image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200  # Fake JPEG header
    files = {"file": ("don_thuoc.jpg", fake_image_bytes, "image/jpeg")}
    res = client.post("/api/v1/live-chat/upload", files=files, headers=headers_customer_a)
    assert res.status_code == 200
    upload_res = res.json()
    assert "url" in upload_res
    print(f"✓ Test 8: Upload hình ảnh đơn thuốc thành công -> URL: {upload_res['url']}")

    # Gửi tin nhắn kèm ảnh
    img_msg_payload = {
        "content": "Tôi gửi ảnh đơn thuốc gần nhất nhờ Dược sĩ xem giúp.",
        "attachment_url": f"http://127.0.0.1:8000{upload_res['url']}",
        "attachment_type": "image/jpeg",
        "client_msg_id": "msg-img-001",
    }
    res = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/messages",
        json=img_msg_payload,
        headers=headers_customer_a,
    )
    assert res.status_code == 200
    assert res.json()["attachment_url"] is not None
    print("✓ Test 8b: Gửi tin nhắn kèm ảnh thành công -> Ảnh được lưu và liên kết với phiên.")

    # ========================================================
    # TEST 9: KIỂM THỬ BẢO MẬT CHỐNG IDOR (BẢO VỆ DỮ LIỆU KHÁCH HÀNG)
    # Khách B cố tình đọc hoặc gửi tin nhắn vào phiên của Khách A
    # ========================================================
    res_idor = client.get(
        f"/api/v1/live-chat/sessions/{session_code}",
        headers=headers_customer_b,  # Token của Khách B
    )
    assert res_idor.status_code == 403, f"LỖI BẢO MẬT IDOR! Khách B đọc được tin của Khách A (Status {res_idor.status_code})"
    print("✓ Test 9a: Chống IDOR thành công -> Khách B bị từ chối 403 khi truy cập phiên của Khách A.")

    res_idor_post = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/messages",
        json={"content": "Tôi là Hacker B"},
        headers=headers_customer_b,
    )
    assert res_idor_post.status_code == 403, "LỖI BẢO MẬT IDOR! Khách B gửi được tin vào phiên của Khách A"
    print("✓ Test 9b: Chống IDOR thành công -> Khách B bị chặn 403 khi gửi tin vào phiên của Khách A.")

    # ========================================================
    # TEST 10: Tải lại trang (F5) - Khách A lấy lại toàn bộ lịch sử
    # ========================================================
    res_reload = client.get(
        f"/api/v1/live-chat/sessions/{session_code}",
        headers=headers_customer_a,
    )
    assert res_reload.status_code == 200
    reloaded_data = res_reload.json()
    assert len(reloaded_data["messages"]) >= 4
    print(f"✓ Test 10: Tải lại trang thành công -> Khôi phục đủ {len(reloaded_data['messages'])} tin nhắn.")

    # ========================================================
    # TEST 11: Kết thúc ca (Close) và Đánh giá (Rating)
    # ========================================================
    res_close = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/close",
        json={"rating": 5, "feedback": "Dược sĩ tư vấn rất tận tình và chính xác!"},
        headers=headers_customer_a,
    )
    assert res_close.status_code == 200
    print("✓ Test 11: Khách hàng kết thúc ca và gửi đánh giá 5 sao thành công.")

    # Kiểm tra trạng thái đã đóng
    res_after = client.get(f"/api/v1/live-chat/sessions/{session_code}", headers=headers_customer_a)
    assert res_after.json()["status"] == "CLOSED"
    assert res_after.json()["rating"] == 5

    print("\n" + "=" * 60)
    print(">>> TẤT CẢ 11 KỊCH BẢN KIỂM THỬ LIVE CHAT THẬT ĐÃ ĐẠT 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
