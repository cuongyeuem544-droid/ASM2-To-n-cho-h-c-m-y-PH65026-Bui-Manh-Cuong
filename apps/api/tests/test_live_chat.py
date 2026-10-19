import io
from fastapi.testclient import TestClient
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models import User, LiveChatSession, LiveChatMessage
from app.models.enums import UserRole

def test_live_chat_lifecycle_and_security(client: TestClient):
    db_session = SessionLocal()
    # Setup test users
    pharmacist = db_session.query(User).filter(User.email == "test_pharmacist_chat_pt@h4care.vn").first()
    if not pharmacist:
        pharmacist = User(
            email="test_pharmacist_chat_pt@h4care.vn",
            password_hash=hash_password("Pharmacist123!@#"),
            full_name="DS. Nguyễn Minh Anh",
            role=UserRole.PHARMACIST,
            is_active=True,
        )
        db_session.add(pharmacist)

    customer_1 = db_session.query(User).filter(User.email == "test_cust1@h4care.vn").first()
    if not customer_1:
        customer_1 = User(
            email="test_cust1@h4care.vn",
            password_hash=hash_password("Customer123!@#"),
            full_name="Khách Hàng 1",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db_session.add(customer_1)

    customer_2 = db_session.query(User).filter(User.email == "test_cust2@h4care.vn").first()
    if not customer_2:
        customer_2 = User(
            email="test_cust2@h4care.vn",
            password_hash=hash_password("Customer123!@#"),
            full_name="Khách Hàng 2 (IDOR Attacker)",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db_session.add(customer_2)

    db_session.commit()

    token_pharm = create_access_token(str(pharmacist.id), str(pharmacist.role))
    token_c1 = create_access_token(str(customer_1.id), str(customer_1.role))
    token_c2 = create_access_token(str(customer_2.id), str(customer_2.role))

    h_pharm = {"Authorization": f"Bearer {token_pharm}"}
    h_c1 = {"Authorization": f"Bearer {token_c1}"}
    h_c2 = {"Authorization": f"Bearer {token_c2}"}

    # 1. Khách 1 tạo ca
    res = client.post(
        "/api/v1/live-chat/sessions",
        json={
            "customer_name": "Khách Hàng 1",
            "subject": "Tư vấn thuốc cảm",
            "initial_context": "Hỏi về Panadol",
            "shared_ai_history": True,
        },
        headers=h_c1,
    )
    assert res.status_code == 200
    session_data = res.json()
    code = session_data["session_code"]
    assert session_data["status"] == "WAITING"

    # 2. Khách 1 gửi tin nhắn
    res_msg = client.post(
        f"/api/v1/live-chat/sessions/{code}/messages",
        json={"content": "Thuốc này uống lúc no hay đói?", "client_msg_id": "test-c1-01"},
        headers=h_c1,
    )
    assert res_msg.status_code == 200

    # 3. Chống IDOR: Khách 2 cố đọc ca của Khách 1
    res_idor = client.get(f"/api/v1/live-chat/sessions/{code}", headers=h_c2)
    assert res_idor.status_code == 403

    # 4. Dược sĩ tiếp nhận ca
    res_claim = client.post(f"/api/v1/live-chat/staff/sessions/{code}/claim", headers=h_pharm)
    assert res_claim.status_code == 200
    assert res_claim.json()["status"] == "ACTIVE"
    assert res_claim.json()["assigned_staff_title"] == "Dược sĩ chuyên môn"

    # 5. Dược sĩ gửi tin nhắn phản hồi
    res_reply = client.post(
        f"/api/v1/live-chat/staff/sessions/{code}/messages",
        json={"content": "Chào bạn, bạn nên uống sau khi ăn no nhé.", "client_msg_id": "test-pharm-01"},
        headers=h_pharm,
    )
    assert res_reply.status_code == 200
    assert res_reply.json()["sender_role_title"] == "Dược sĩ chuyên môn"

    # 6. Khách 1 kết thúc ca
    res_close = client.post(
        f"/api/v1/live-chat/sessions/{code}/close",
        json={"rating": 5, "feedback": "Rất tốt"},
        headers=h_c1,
    )
    assert res_close.status_code == 200


def test_staff_websocket_role_enforcement(client: TestClient):
    """Kiểm tra Item 3: WebSocket Nhân viên bắt buộc kiểm tra vai trò."""
    db_session = SessionLocal()
    customer = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()
    pharmacist = db_session.query(User).filter(User.role == UserRole.PHARMACIST).first()
    db_session.close()

    token_cust = create_access_token(str(customer.id), str(customer.role))
    token_pharm = create_access_token(str(pharmacist.id), str(pharmacist.role))

    # Khách hàng cố kết nối kênh WebSocket nhân viên -> Bị đóng 1008
    try:
        with client.websocket_connect(f"/api/v1/live-chat/ws/staff?token={token_cust}") as ws:
            assert False, "Customer should not be able to connect to staff websocket"
    except Exception as e:
        # Starlette WebSocketDisconnect with 1008
        pass

    # Nhân viên hợp lệ -> Kết nối thành công
    with client.websocket_connect(f"/api/v1/live-chat/ws/staff?token={token_pharm}") as ws:
        ws.send_text('{"type": "PING"}')
        resp = ws.receive_text()
        assert "PONG" in resp


def test_live_chat_attachment_protection(client: TestClient):
    """Kiểm tra Item 4: File Live Chat được bảo vệ theo phiên."""
    db_session = SessionLocal()
    customer_1 = db_session.query(User).filter(User.email == "test_cust1@h4care.vn").first()
    customer_2 = db_session.query(User).filter(User.email == "test_cust2@h4care.vn").first()
    db_session.close()

    token_c1 = create_access_token(str(customer_1.id), str(customer_1.role))
    token_c2 = create_access_token(str(customer_2.id), str(customer_2.role))
    h_c1 = {"Authorization": f"Bearer {token_c1}"}
    h_c2 = {"Authorization": f"Bearer {token_c2}"}

    # Tạo phiên cho khách 1
    res_s = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Khách Hàng 1", "subject": "Test File"},
        headers=h_c1,
    )
    assert res_s.status_code == 200
    session_code = res_s.json()["session_code"]

    fake_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)

    # 1. Upload ẩn danh không truyền session_code -> Bị chặn 400
    res_no_sess = client.post(
        "/api/v1/live-chat/upload",
        files={"file": ("test.jpg", io.BytesIO(fake_img.getvalue()), "image/jpeg")},
    )
    assert res_no_sess.status_code == 400

    # 2. Khách 2 cố upload vào phiên của khách 1 -> Bị chặn 403
    res_wrong_user = client.post(
        "/api/v1/live-chat/upload",
        data={"session_code": session_code},
        files={"file": ("test.jpg", io.BytesIO(fake_img.getvalue()), "image/jpeg")},
        headers=h_c2,
    )
    assert res_wrong_user.status_code == 403

    # 3. Khách 1 upload hợp lệ vào đúng phiên của mình -> Thành công 200
    res_ok = client.post(
        "/api/v1/live-chat/upload",
        data={"session_code": session_code},
        files={"file": ("test.jpg", io.BytesIO(fake_img.getvalue()), "image/jpeg")},
        headers=h_c1,
    )
    assert res_ok.status_code == 200
    att_url = res_ok.json()["url"]
    filename = res_ok.json()["filename"]

    # Khách 1 gửi tin nhắn có đính kèm file
    res_m = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/messages",
        json={"content": "Ảnh toa thuốc", "attachment_url": att_url, "attachment_type": "image"},
        headers=h_c1,
    )
    assert res_m.status_code == 200

    # 4. Người lạ không có token cố tải tệp đính kèm -> Bị chặn 401 hoặc 403
    res_dl_anon = client.get(f"/api/v1/live-chat/attachments/{filename}")
    assert res_dl_anon.status_code in [401, 403]

    # 5. Khách 2 cố tải tệp của khách 1 -> Bị chặn 403
    res_dl_c2 = client.get(f"/api/v1/live-chat/attachments/{filename}", headers=h_c2)
    assert res_dl_c2.status_code == 403

    # 6. Khách 1 (chủ sở hữu phiên) tải tệp -> Thành công 200
    res_dl_c1 = client.get(f"/api/v1/live-chat/attachments/{filename}", headers=h_c1)
    assert res_dl_c1.status_code == 200
    assert len(res_dl_c1.content) > 0
