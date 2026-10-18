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


def test_websocket_rejects_unauthenticated_and_wrong_customer(client: TestClient):
    import uuid
    from starlette.websockets import WebSocketDisconnect

    suffix = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        owner = User(
            email=f"ws_owner_{suffix}@h4care.test",
            password_hash=hash_password("LocalTestPassword123!"),
            full_name="WS Owner",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        stranger = User(
            email=f"ws_other_{suffix}@h4care.test",
            password_hash=hash_password("LocalTestPassword123!"),
            full_name="WS Other",
            role=UserRole.CUSTOMER,
            is_active=True,
        )
        db.add_all([owner, stranger])
        db.commit()
        owner_id, stranger_id = owner.id, stranger.id

    owner_token = create_access_token(str(owner_id), UserRole.CUSTOMER.value)
    stranger_token = create_access_token(str(stranger_id), UserRole.CUSTOMER.value)
    response = client.post(
        "/api/v1/live-chat/sessions",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"subject": "WebSocket permission regression"},
    )
    assert response.status_code == 200
    session_code = response.json()["session_code"]

    with __import__("pytest").raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{session_code}"):
            pass

    with __import__("pytest").raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/live-chat/ws/client/{session_code}?token={stranger_token}"
        ):
            pass

    with client.websocket_connect(
        f"/api/v1/live-chat/ws/client/{session_code}?token={owner_token}"
    ) as ws:
        ws.send_json({"type": "PING"})
        assert ws.receive_json()["type"] == "PONG"

    with __import__("pytest").raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/live-chat/ws/staff?token={owner_token}"):
            pass
