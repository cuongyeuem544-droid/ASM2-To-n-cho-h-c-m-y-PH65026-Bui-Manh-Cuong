import io
import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models import User, LiveChatSession, LiveChatMessage
from app.models.entities import AuditLog
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
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/live-chat/ws/staff?token={token_cust}") as ws:
            pass
    assert exc_info.value.code == 1008

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


def test_staff_cannot_impersonate_customer_via_customer_endpoint(client: TestClient):
    """Khóa việc nhân viên gọi endpoint khách hàng để gửi tin nhắn dưới danh nghĩa CUSTOMER."""
    db_session = SessionLocal()
    pharmacist = db_session.query(User).filter(User.role == UserRole.PHARMACIST).first()
    customer = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()
    db_session.close()

    token_pharm = create_access_token(str(pharmacist.id), str(pharmacist.role))
    token_cust = create_access_token(str(customer.id), str(customer.role))

    h_pharm = {"Authorization": f"Bearer {token_pharm}"}
    h_cust = {"Authorization": f"Bearer {token_cust}"}

    # Tạo phiên bằng tài khoản khách hàng
    res = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Khách Test", "subject": "Tư vấn bảo mật"},
        headers=h_cust,
    )
    assert res.status_code == 200
    session_code = res.json()["session_code"]

    # Nhân viên cố gọi POST /sessions/{code}/messages (cổng khách hàng) -> Bị từ chối 403
    res_block = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/messages",
        json={"content": "Tôi là nhân viên nhưng muốn gửi giả mạo khách hàng"},
        headers=h_pharm,
    )
    assert res_block.status_code == 403
    assert "cổng nhân viên" in res_block.json()["detail"].lower()

    # Nhân viên cố gọi POST /sessions/{code}/close (cổng khách hàng) -> Bị từ chối 403
    res_close_block = client.post(
        f"/api/v1/live-chat/sessions/{session_code}/close",
        json={"rating": 1, "feedback": "Fake close"},
        headers=h_pharm,
    )
    assert res_close_block.status_code == 403


def test_guest_session_token_never_leaked_to_staff(client: TestClient):
    """Không để lộ guest_session_token cho nhân viên, admin hoặc người không phải chủ sở hữu."""
    db_session = SessionLocal()
    pharmacist = db_session.query(User).filter(User.role == UserRole.PHARMACIST).first()
    admin = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    db_session.close()

    token_pharm = create_access_token(str(pharmacist.id), str(pharmacist.role))
    token_admin = create_access_token(str(admin.id), str(admin.role))
    h_pharm = {"Authorization": f"Bearer {token_pharm}"}
    h_admin = {"Authorization": f"Bearer {token_admin}"}

    # 1. Khách vãng lai tạo ca -> Response có guest_session_token cho chính khách
    res_guest = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Khách Vãng Lai Test", "customer_phone": "0987654321"},
    )
    assert res_guest.status_code == 200
    guest_data = res_guest.json()
    session_code = guest_data["session_code"]
    real_guest_token = guest_data.get("guest_session_token")
    assert real_guest_token is not None and len(real_guest_token) > 10

    # 2. Nhân viên lấy danh sách phiên -> guest_session_token phải là None
    res_list = client.get("/api/v1/live-chat/staff/sessions", headers=h_pharm)
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    target_item = next((it for it in items if it["session_code"] == session_code), None)
    assert target_item is not None
    assert target_item.get("guest_session_token") is None

    # 3. Nhân viên lấy chi tiết phiên qua /sessions/{code} -> guest_session_token phải là None
    res_detail = client.get(f"/api/v1/live-chat/sessions/{session_code}", headers=h_pharm)
    assert res_detail.status_code == 200
    assert res_detail.json().get("guest_session_token") is None

    # 4. Nhân viên claim ca -> response claim guest_session_token là None
    res_claim = client.post(f"/api/v1/live-chat/staff/sessions/{session_code}/claim", headers=h_pharm)
    assert res_claim.status_code == 200
    assert res_claim.json().get("guest_session_token") is None

    # 5. Admin lấy chi tiết phiên -> guest_session_token cũng là None
    res_admin_detail = client.get(f"/api/v1/live-chat/sessions/{session_code}", headers=h_admin)
    assert res_admin_detail.status_code == 200
    assert res_admin_detail.json().get("guest_session_token") is None

    # 6. Khách vãng lai gọi với đúng guest_token -> nhận được thông tin kèm guest_session_token
    res_guest_own = client.get(
        f"/api/v1/live-chat/sessions/{session_code}",
        headers={"X-Chat-Guest-Token": real_guest_token},
    )
    assert res_guest_own.status_code == 200
    assert res_guest_own.json().get("guest_session_token") == real_guest_token


def test_staff_assigned_isolation_rbac(client: TestClient):
    """
    Phân quyền Live Chat đa nhân viên:
    Khi phiên đã được gán cho Nhân viên A:
    - Nhân viên A và ADMIN được xem chi tiết, gửi tin, upload ảnh và đóng phiên.
    - Nhân viên B bị từ chối 403 Forbidden.
    - Chuyển phiên ghi nhận AuditLog hợp lệ.
    """
    db_session = SessionLocal()
    staff_a = db_session.query(User).filter(User.email == "test_staff_a@h4care.vn").first()
    if not staff_a:
        staff_a = User(
            email="test_staff_a@h4care.vn",
            password_hash=hash_password("StaffA123!@#"),
            full_name="Dược Sĩ A (Chủ ca)",
            role=UserRole.PHARMACIST,
            is_active=True,
        )
        db_session.add(staff_a)

    staff_b = db_session.query(User).filter(User.email == "test_staff_b@h4care.vn").first()
    if not staff_b:
        staff_b = User(
            email="test_staff_b@h4care.vn",
            password_hash=hash_password("StaffB123!@#"),
            full_name="Dược Sĩ B (Kẻ can thiệp)",
            role=UserRole.PHARMACIST,
            is_active=True,
        )
        db_session.add(staff_b)

    admin = db_session.query(User).filter(User.role == UserRole.ADMIN).first()
    db_session.commit()

    token_a = create_access_token(str(staff_a.id), str(staff_a.role))
    token_b = create_access_token(str(staff_b.id), str(staff_b.role))
    token_adm = create_access_token(str(admin.id), str(admin.role))

    h_a = {"Authorization": f"Bearer {token_a}"}
    h_b = {"Authorization": f"Bearer {token_b}"}
    h_adm = {"Authorization": f"Bearer {token_adm}"}

    # 1. Tạo phiên mới (WAITING)
    res_create = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Khách Hàng Cần Tư Vấn Riêng Tư", "subject": "Bệnh kín"},
    )
    assert res_create.status_code == 200
    session_code = res_create.json()["session_code"]

    # 2. Nhân viên A tiếp nhận ca (Claim)
    res_claim = client.post(f"/api/v1/live-chat/staff/sessions/{session_code}/claim", headers=h_a)
    assert res_claim.status_code == 200
    assert res_claim.json()["assigned_staff_id"] == staff_a.id

    # 3. Nhân viên B cố đọc nội dung phiên của A -> 403 Forbidden
    res_b_view = client.get(f"/api/v1/live-chat/sessions/{session_code}", headers=h_b)
    assert res_b_view.status_code == 403

    res_b_staff_view = client.get(f"/api/v1/live-chat/staff/sessions/{session_code}", headers=h_b)
    assert res_b_staff_view.status_code == 403

    # 4. Nhân viên B cố gửi tin nhắn vào phiên của A -> 403 Forbidden
    res_b_msg = client.post(
        f"/api/v1/live-chat/staff/sessions/{session_code}/messages",
        json={"content": "Tin nhắn từ nhân viên B không có thẩm quyền"},
        headers=h_b,
    )
    assert res_b_msg.status_code == 403

    # 5. Nhân viên B cố upload ảnh vào ca của A -> 403 Forbidden
    fake_img = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)
    res_b_upload = client.post(
        "/api/v1/live-chat/upload",
        data={"session_code": session_code},
        files={"file": ("test.jpg", io.BytesIO(fake_img.getvalue()), "image/jpeg")},
        headers=h_b,
    )
    assert res_b_upload.status_code == 403

    # 6. Nhân viên B cố đóng phiên của A -> 403 Forbidden
    res_b_close = client.post(f"/api/v1/live-chat/staff/sessions/{session_code}/close", headers=h_b)
    assert res_b_close.status_code == 403

    # 7. Nhân viên B cố giành giật (claim) phiên của A -> 403 Forbidden
    res_b_reclaim = client.post(f"/api/v1/live-chat/staff/sessions/{session_code}/claim", headers=h_b)
    assert res_b_reclaim.status_code == 403

    # 8. ADMIN xem chi tiết phiên của A -> 200 OK
    res_adm_view = client.get(f"/api/v1/live-chat/sessions/{session_code}", headers=h_adm)
    assert res_adm_view.status_code == 200

    # 9. ADMIN gửi tin nhắn điều phối -> 200 OK
    res_adm_msg = client.post(
        f"/api/v1/live-chat/staff/sessions/{session_code}/messages",
        json={"content": "Quản trị viên tham gia hỗ trợ ca"},
        headers=h_adm,
    )
    assert res_adm_msg.status_code == 200

    # 10. Chuyển phiên hợp lệ: Nhân viên A chuyển phiên cho Nhân viên B
    res_assign = client.post(
        f"/api/v1/live-chat/staff/sessions/{session_code}/assign",
        json={"staff_id": staff_b.id},
        headers=h_a,
    )
    assert res_assign.status_code == 200
    assert res_assign.json()["assigned_staff_id"] == staff_b.id

    # Kiểm tra AuditLog được tạo trong DB
    db_verify = SessionLocal()
    audit = db_verify.query(AuditLog).filter(
        AuditLog.action == "ASSIGN_LIVE_CHAT_SESSION",
        AuditLog.user_id == staff_a.id,
    ).order_by(AuditLog.id.desc()).first()
    assert audit is not None
    assert audit.after_json.get("assigned_staff_id") == staff_b.id
    db_verify.close()

    # Sau khi chuyển giao: Nhân viên B đã có quyền gửi tin và xem phiên
    res_b_view_now = client.get(f"/api/v1/live-chat/sessions/{session_code}", headers=h_b)
    assert res_b_view_now.status_code == 200

    res_b_msg_now = client.post(
        f"/api/v1/live-chat/staff/sessions/{session_code}/messages",
        json={"content": "Tôi là Dược Sĩ B, đã nhận chuyển giao và sẽ tư vấn tiếp cho bạn"},
        headers=h_b,
    )
    assert res_b_msg_now.status_code == 200

    # Nhân viên B kết thúc phiên
    res_b_close_ok = client.post(f"/api/v1/live-chat/staff/sessions/{session_code}/close", headers=h_b)
    assert res_b_close_ok.status_code == 200


def test_jwt_revocation_and_invalid_token_enforcement(client: TestClient):
    """Chuẩn hóa xác thực JWT: token bị thu hồi (token_version mismatch) hoặc token rác bị từ chối 401."""
    db_session = SessionLocal()
    user = db_session.query(User).filter(User.email == "test_revoke_user@h4care.vn").first()
    if not user:
        user = User(
            email="test_revoke_user@h4care.vn",
            password_hash=hash_password("RevokePass123!"),
            full_name="Người Dùng Kiểm Tra Thu Hồi",
            role=UserRole.CUSTOMER,
            is_active=True,
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()
    db_session.close()

    # 1. Token hợp lệ version 1
    valid_token = create_access_token(str(user.id), str(user.role), token_version=1)
    res_valid = client.get("/api/v1/live-chat/staff-status", headers={"Authorization": f"Bearer {valid_token}"})
    assert res_valid.status_code == 200

    # 2. Người dùng đổi mật khẩu -> tăng token_version lên 2
    db_update = SessionLocal()
    user_db = db_update.get(User, user.id)
    user_db.token_version = 2
    db_update.commit()
    db_update.close()

    # 3. Gọi REST endpoint bằng token cũ (token_version=1) -> 401 UNAUTHORIZED
    res_revoked = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Test Revoked", "subject": "Test"},
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert res_revoked.status_code == 401
    assert "thu hồi" in res_revoked.json()["detail"].lower()

    # 4. Gửi token sai định dạng/rác -> 401 UNAUTHORIZED
    res_garbage = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Test Garbage", "subject": "Test"},
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert res_garbage.status_code == 401


def test_client_websocket_access_control(client: TestClient):
    """Kiểm tra WebSocket khách hàng /ws/client/{session_code} kiểm tra quyền sở hữu và guest token."""
    db_session = SessionLocal()
    customer = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()
    other_customer = db_session.query(User).filter(User.email == "test_cust2@h4care.vn").first()
    db_session.close()

    token_cust = create_access_token(str(customer.id), str(customer.role))
    token_other = create_access_token(str(other_customer.id), str(other_customer.role))

    # 1. Phiên của khách hàng có tài khoản
    res_s = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": customer.full_name, "subject": "Test WS Auth"},
        headers={"Authorization": f"Bearer {token_cust}"},
    )
    assert res_s.status_code == 200
    code_user = res_s.json()["session_code"]

    # Khách hàng khác kết nối vào phiên của khách này -> Bị đóng 4403
    with pytest.raises(WebSocketDisconnect) as exc1:
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_user}?token={token_other}") as ws:
            pass
    assert exc1.value.code == 4403

    # Đúng khách hàng chủ phiên -> Kết nối thành công, nhận CONNECTED
    with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_user}?token={token_cust}") as ws:
        msg = ws.receive_json()
        assert msg.get("type") == "CONNECTED"
        ws.send_text('{"type": "PING"}')
        pong = ws.receive_json()
        assert pong.get("type") == "PONG"

    # 2. Phiên của khách vãng lai (Guest)
    res_g = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Khách Vãng Lai WS", "customer_phone": "0912345678"},
    )
    assert res_g.status_code == 200
    code_guest = res_g.json()["session_code"]
    real_guest_token = res_g.json()["guest_session_token"]

    # Kết nối với guest token sai -> Bị đóng 4403
    with pytest.raises(WebSocketDisconnect) as exc2:
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_guest}?guest_token=wrong_token") as ws:
            pass
    assert exc2.value.code == 4403

    # Kết nối không có token -> Bị đóng 4401
    with pytest.raises(WebSocketDisconnect) as exc3:
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_guest}") as ws:
            pass
    assert exc3.value.code == 4401

    # Kết nối đúng guest token -> Thành công
    with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_guest}?guest_token={real_guest_token}") as ws:
        msg = ws.receive_json()
        assert msg.get("type") == "CONNECTED"
