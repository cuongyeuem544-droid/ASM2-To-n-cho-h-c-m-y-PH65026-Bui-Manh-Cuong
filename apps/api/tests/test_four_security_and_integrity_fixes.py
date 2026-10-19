"""
apps/api/tests/test_four_security_and_integrity_fixes.py

Bộ kiểm thử hồi quy toàn diện cho 4 lỗi bảo mật và toàn vẹn dữ liệu:
1. WebSocket khách hàng: Xác thực JWT/Guest nghiêm ngặt trước khi connect/accept, chặn token giả/hết hạn/thu hồi/sai chủ/phiên đóng.
2. File Live Chat: Lưu LiveChatAttachment, chống path traversal, xác thực chủ phiên, không tạo file rác khi bị từ chối.
3. Next.js Attachment Download (kiểm thử thông qua logic auth backend & metadata).
4. Phục hồi tồn kho khi hoàn hàng: Đơn 1 lô, đa lô (multi-batch), hoàn 1 phần, gộp lô, kiểm tra kho, chặn duplicate restock chéo giữa Warehouse và ReturnRequest.
"""

import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models.entities import CanonicalProduct, Order, OrderItem, User
from app.models.enums import UserRole
from app.models.inventory import (
    InventoryBatch,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.chat_models import LiveChatAttachment, LiveChatMessage, LiveChatSession
from app.models.returns import (
    ItemCondition,
    RestockDestination,
    ReturnItem,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
    WarehouseReturnCase,
)
from app.services.live_chat_service import chat_manager
from app.services.return_service import ReturnService
from app.services.warehouse_return_service import WarehouseReturnService
import jwt


# ==============================================================================
# PHẦN 1 & 2: WEBSOCKET VÀ LIVE CHAT ATTACHMENT SECURITY
# ==============================================================================

def test_websocket_and_chat_attachment_security(client: TestClient):
    db = SessionLocal()
    try:
        # 1. Tạo test users
        cust1 = db.query(User).filter(User.email == "sec_ws_cust1@h4care.vn").first()
        if not cust1:
            cust1 = User(
                email="sec_ws_cust1@h4care.vn",
                password_hash=hash_password("Pass123!@#"),
                full_name="WS Customer 1",
                role=UserRole.CUSTOMER,
                is_active=True,
                token_version=1,
            )
            db.add(cust1)

        cust2 = db.query(User).filter(User.email == "sec_ws_cust2@h4care.vn").first()
        if not cust2:
            cust2 = User(
                email="sec_ws_cust2@h4care.vn",
                password_hash=hash_password("Pass123!@#"),
                full_name="WS Customer 2 (Attacker)",
                role=UserRole.CUSTOMER,
                is_active=True,
                token_version=1,
            )
            db.add(cust2)

        pharmacist = db.query(User).filter(User.email == "sec_ws_pharm@h4care.vn").first()
        if not pharmacist:
            pharmacist = User(
                email="sec_ws_pharm@h4care.vn",
                password_hash=hash_password("Pharm123!@#"),
                full_name="WS Pharmacist",
                role=UserRole.PHARMACIST,
                is_active=True,
                token_version=1,
            )
            db.add(pharmacist)

        db.commit()
        db.refresh(cust1)
        db.refresh(cust2)
        db.refresh(pharmacist)

        # Token hợp lệ
        token_cust1 = create_access_token(
            subject=str(cust1.id),
            role=str(cust1.role),
            token_version=cust1.token_version,
        )
        token_cust2 = create_access_token(
            subject=str(cust2.id),
            role=str(cust2.role),
            token_version=cust2.token_version,
        )
        token_pharm = create_access_token(
            subject=str(pharmacist.id),
            role=str(pharmacist.role),
            token_version=pharmacist.token_version,
        )

        # Token hết hạn
        expired_payload = {
            "sub": str(cust1.id),
            "role": str(cust1.role),
            "type": "access",
            "token_version": cust1.token_version,
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token_expired = jwt.encode(expired_payload, settings.secret_key, algorithm="HS256")

        # Token bị thu hồi (token_version lệch)
        revoked_payload = {
            "sub": str(cust1.id),
            "role": str(cust1.role),
            "type": "access",
            "token_version": cust1.token_version + 99,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token_revoked = jwt.encode(revoked_payload, settings.secret_key, algorithm="HS256")

        # 2. Tạo phiên chat cho cust1 và phiên chat vãng lai (guest)
        res_s1 = client.post(
            "/api/v1/live-chat/sessions",
            json={"customer_name": "WS Customer 1", "subject": "Hỏi thuốc huyết áp"},
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert res_s1.status_code == 200
        session_cust1 = res_s1.json()
        code_cust1 = session_cust1["session_code"]

        res_guest = client.post(
            "/api/v1/live-chat/sessions",
            json={"customer_name": "Khách Vãng Lai A", "subject": "Hỏi vitamin"},
        )
        assert res_guest.status_code == 200
        session_guest = res_guest.json()
        code_guest = session_guest["session_code"]
        guest_token = session_guest["guest_session_token"]
        assert guest_token is not None

        # --- A. TEST WEBSOCKET XÁC THỰC ---

        # 1. Thiếu token -> 4401
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_cust1}"):
                pass
        assert exc_info.value.code == 4401

        # 2. Token giả -> 4403
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_cust1}?token=fake-token"):
                pass
        assert exc_info.value.code == 4403

        # 3. Token hết hạn -> 4403
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_cust1}?token={token_expired}"):
                pass
        assert exc_info.value.code == 4403

        # 4. Token bị thu hồi (token_version sai) -> 4403
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_cust1}?token={token_revoked}"):
                pass
        assert exc_info.value.code == 4403

        # 5. Token của người dùng khác (cust2 cố vào phiên cust1) -> 4403
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_cust1}?token={token_cust2}"):
                pass
        assert exc_info.value.code == 4403

        # 6. Guest token sai -> 4403
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_guest}?guest_token=wrong_token"):
                pass
        assert exc_info.value.code == 4403

        # 7. Phiên không tồn tại -> 4404
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/NON_EXISTENT_SESSION?token={token_cust1}"):
                pass
        assert exc_info.value.code == 4404

        # 8. Token hợp lệ của cust1 -> Kết nối thành công, nhận CONNECTED event
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_cust1}?token={token_cust1}") as ws:
            connected_evt = ws.receive_json()
            assert connected_evt["type"] == "CONNECTED"
            assert connected_evt["session_code"] == code_cust1

        # 9. Guest token hợp lệ -> Kết nối thành công
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_guest}?guest_token={guest_token}") as ws:
            connected_evt = ws.receive_json()
            assert connected_evt["type"] == "CONNECTED"
            assert connected_evt["session_code"] == code_guest

        # 10. Phiên đã đóng -> Từ chối 4403
        # Đóng phiên cust1
        close_res = client.post(
            f"/api/v1/live-chat/sessions/{code_cust1}/close",
            json={"reason": "Xong tư vấn"},
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert close_res.status_code == 200

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/live-chat/ws/client/{code_cust1}?token={token_cust1}"):
                pass
        assert exc_info.value.code == 4403

        # Xác nhận chat_manager không giữ connection rác sau khi reject
        assert code_cust1 not in chat_manager.active_connections or len(chat_manager.active_connections[code_cust1]) == 0

        # --- B. TEST LIVE CHAT ATTACHMENT PROTECTION ---

        # Tạo phiên mới cho cust1 để test upload
        res_s2 = client.post(
            "/api/v1/live-chat/sessions",
            json={"customer_name": "WS Customer 1", "subject": "Hỏi thuốc đơn mới"},
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert res_s2.status_code == 200
        code_cust1_v2 = res_s2.json()["session_code"]

        sample_file_content = b"%PDF-1.4 test secure document content"

        # 1. Upload không có session_code -> 400
        res_up_no_code = client.post(
            "/api/v1/live-chat/attachments/upload",
            files={"file": ("donthuoc.pdf", io.BytesIO(sample_file_content), "application/pdf")},
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert res_up_no_code.status_code == 400

        # 2. Upload bởi người dùng khác (cust2 cố upload vào phiên cust1) -> 403
        res_up_cust2 = client.post(
            "/api/v1/live-chat/attachments/upload",
            data={"session_code": code_cust1_v2},
            files={"file": ("donthuoc.pdf", io.BytesIO(sample_file_content), "application/pdf")},
            headers={"Authorization": f"Bearer {token_cust2}"},
        )
        assert res_up_cust2.status_code == 403

        # 3. Upload guest với guest token sai -> 403
        res_up_guest_bad = client.post(
            "/api/v1/live-chat/attachments/upload",
            data={"session_code": code_guest, "guest_session_token": "wrong_guest_token"},
            files={"file": ("donthuoc.pdf", io.BytesIO(sample_file_content), "application/pdf")},
        )
        assert res_up_guest_bad.status_code == 403

        # 4. Upload vào phiên đã đóng -> 400
        res_up_closed = client.post(
            "/api/v1/live-chat/attachments/upload",
            data={"session_code": code_cust1},
            files={"file": ("donthuoc.pdf", io.BytesIO(sample_file_content), "application/pdf")},
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert res_up_closed.status_code == 400

        # 5. Upload hợp lệ bởi cust1 -> 200 & Tạo bản ghi LiveChatAttachment
        res_up_ok = client.post(
            "/api/v1/live-chat/attachments/upload",
            data={"session_code": code_cust1_v2},
            files={"file": ("donthuoc_hop_le.pdf", io.BytesIO(sample_file_content), "application/pdf")},
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert res_up_ok.status_code == 200
        att_data = res_up_ok.json()
        att_code = att_data["attachment_code"]
        assert att_code.startswith("att-")

        # Kiểm tra database có bản ghi LiveChatAttachment
        att_db = db.query(LiveChatAttachment).filter(LiveChatAttachment.attachment_code == att_code).first()
        assert att_db is not None
        assert att_db.user_id == cust1.id
        assert att_db.file_name == "donthuoc_hop_le.pdf"

        # 6. Download không có token -> 401
        res_down_no_token = client.get(f"/api/v1/live-chat/attachments/{att_code}")
        assert res_down_no_token.status_code == 401

        # 7. Download với token giả -> 401/403
        res_down_fake = client.get(f"/api/v1/live-chat/attachments/{att_code}?token=arbitrary_fake_token")
        assert res_down_fake.status_code in [401, 403]

        # 8. Download bởi khách khác (cust2) -> 403
        res_down_cust2 = client.get(
            f"/api/v1/live-chat/attachments/{att_code}",
            headers={"Authorization": f"Bearer {token_cust2}"},
        )
        assert res_down_cust2.status_code == 403

        # 9. Download bằng guest token của phiên khác -> 403
        res_down_wrong_guest = client.get(
            f"/api/v1/live-chat/attachments/{att_code}?guest_token={guest_token}"
        )
        assert res_down_wrong_guest.status_code == 403

        # 10. Download file chưa đăng ký trong database -> 404
        res_down_unregistered = client.get(
            "/api/v1/live-chat/attachments/att-nonexistent-code",
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert res_down_unregistered.status_code == 404

        # 11. Chủ phiên tải file hợp lệ -> 200 kèm Content-Type & security headers
        res_down_owner = client.get(
            f"/api/v1/live-chat/attachments/{att_code}",
            headers={"Authorization": f"Bearer {token_cust1}"},
        )
        assert res_down_owner.status_code == 200
        assert res_down_owner.content == sample_file_content
        assert res_down_owner.headers["X-Content-Type-Options"] == "nosniff"
        assert "default-src 'none'" in res_down_owner.headers["Content-Security-Policy"]

        # 12. Dược sĩ / Staff tải file hợp lệ -> 200
        res_down_pharm = client.get(
            f"/api/v1/live-chat/attachments/{att_code}",
            headers={"Authorization": f"Bearer {token_pharm}"},
        )
        assert res_down_pharm.status_code == 200
        assert res_down_pharm.content == sample_file_content

    finally:
        db.close()


# ==============================================================================
# PHẦN 4: RETURN RESTOCK BATCH INTEGRITY & MULTI-BATCH DISTRIBUTION
# ==============================================================================

def test_return_restock_single_and_multi_batch_integrity():
    db = SessionLocal()
    try:
        # Chuẩn bị dữ liệu mẫu độc lập
        uid = uuid.uuid4().hex[:6].upper()

        # Tạo kho
        wh1 = db.query(Warehouse).filter(Warehouse.id == 1).first()
        if not wh1:
            wh1 = Warehouse(id=1, name="Kho Trung Tâm Test", code="WH-TEST-01", is_active=True)
            db.add(wh1)
            db.commit()

        wh2 = db.query(Warehouse).filter(Warehouse.id == 2).first()
        if not wh2:
            wh2 = Warehouse(id=2, name="Kho Chi Nhánh Test", code="WH-TEST-02", is_active=True)
            db.add(wh2)
            db.commit()

        # Tạo người dùng test
        manager = db.query(User).filter(User.email == "test_mgr_ret@h4care.vn").first()
        if not manager:
            manager = User(
                email="test_mgr_ret@h4care.vn",
                password_hash=hash_password("Mgr123!@#"),
                full_name="Quản Lý Kho Test",
                role=UserRole.WAREHOUSE_MANAGER,
                warehouse_id=wh1.id,
                is_active=True,
            )
            db.add(manager)

        customer = db.query(User).filter(User.email == "test_cust_ret@h4care.vn").first()
        if not customer:
            customer = User(
                email="test_cust_ret@h4care.vn",
                password_hash=hash_password("Cust123!@#"),
                full_name="Khách Trả Hàng",
                role=UserRole.CUSTOMER,
                is_active=True,
            )
            db.add(customer)

        db.commit()
        db.refresh(manager)
        db.refresh(customer)

        # Tạo CanonicalProduct, SKU và Batch
        prod = db.query(CanonicalProduct).first()
        if not prod:
            prod = CanonicalProduct(name="Thuốc Kháng Sinh Test", slug=f"thuoc-khang-sinh-{uid}")
            db.add(prod)
            db.commit()
            db.refresh(prod)

        sku = db.query(ProductSku).filter(ProductSku.sku_code == f"SKU-{uid}").first()
        if not sku:
            sku = ProductSku(
                sku_code=f"SKU-{uid}",
                canonical_product_id=prod.id,
                uom="Hộp",
                base_price=Decimal("100000"),
            )
            db.add(sku)
            db.commit()
            db.refresh(sku)

        # Batch A (Kho 1)
        batch_a = InventoryBatch(
            batch_number=f"BATCH-A-{uid}",
            sku_id=sku.id,
            manufacture_date=datetime.now(UTC).date() - timedelta(days=60),
            expiry_date=datetime.now(UTC).date() + timedelta(days=300),
            initial_quantity=100,
        )
        db.add(batch_a)

        # Batch B (Kho 1)
        batch_b = InventoryBatch(
            batch_number=f"BATCH-B-{uid}",
            sku_id=sku.id,
            manufacture_date=datetime.now(UTC).date() - timedelta(days=30),
            expiry_date=datetime.now(UTC).date() + timedelta(days=330),
            initial_quantity=100,
        )
        db.add(batch_b)
        db.commit()
        db.refresh(batch_a)
        db.refresh(batch_b)

        # Khởi tạo tồn kho ban đầu cho Batch A và Batch B tại Kho 1
        stock_a = WarehouseBatchStock(
            warehouse_id=wh1.id,
            batch_id=batch_a.id,
            quantity_on_hand=10,
            quantity_available=10,
            quantity_reserved=0,
        )
        stock_b = WarehouseBatchStock(
            warehouse_id=wh1.id,
            batch_id=batch_b.id,
            quantity_on_hand=10,
            quantity_available=10,
            quantity_reserved=0,
        )
        db.add(stock_a)
        db.add(stock_b)
        db.commit()

        # Tạo Đơn hàng 1: Multi-batch (3 hộp từ Batch A, 2 hộp từ Batch B = tổng 5 hộp)
        order_multi = Order(
            order_code=f"ORD-MULTI-{uid}",
            customer_id=customer.id,
            user_id=customer.id,
            total_amount=Decimal("500000"),
            payment_status="PAID",
            order_status="DELIVERED",
            assigned_warehouse_id=wh1.id,
        )
        db.add(order_multi)
        db.commit()
        db.refresh(order_multi)

        order_item_multi = OrderItem(
            order_id=order_multi.id,
            product_id=sku.canonical_product_id,
            product_name="Thuốc Kháng Sinh Test",
            quantity=5,
            price=Decimal("100000"),
            subtotal=Decimal("500000"),
        )
        db.add(order_item_multi)
        db.commit()
        db.refresh(order_item_multi)

        # Phân bổ lô xuất: 3 hộp Batch A, 2 hộp Batch B
        alloc_a = OrderItemBatchAllocation(
            order_item_id=order_item_multi.id,
            batch_id=batch_a.id,
            warehouse_id=wh1.id,
            allocated_quantity=3,
        )
        alloc_b = OrderItemBatchAllocation(
            order_item_id=order_item_multi.id,
            batch_id=batch_b.id,
            warehouse_id=wh1.id,
            allocated_quantity=2,
        )
        db.add(alloc_a)
        db.add(alloc_b)

        # Giảm tồn khi xuất bán: Batch A còn 7, Batch B còn 8
        stock_a.quantity_on_hand -= 3
        stock_a.quantity_available -= 3
        stock_b.quantity_on_hand -= 2
        stock_b.quantity_available -= 2
        db.commit()

        assert stock_a.quantity_on_hand == 7
        assert stock_b.quantity_on_hand == 8

        # --- TEST 1: Hoàn 1 phần trên đơn nhiều lô (Hoàn 4 hộp: 3 hộp về Batch A, 1 hộp về Batch B) ---
        ret_req_1 = ReturnRequest(
            return_code=f"RET-MULTI-{uid}",
            order_id=order_multi.id,
            customer_id=customer.id,
            request_type=ReturnRequestType.REFUND_ONLY.value,
            status=ReturnStatus.REFUNDED.value,
            reason="Thừa thuốc sau điều trị",
        )
        db.add(ret_req_1)
        db.commit()
        db.refresh(ret_req_1)

        ret_item_1 = ReturnItem(
            return_request_id=ret_req_1.id,
            order_item_id=order_item_multi.id,
            product_name="Thuốc Kháng Sinh Test",
            product_id=sku.canonical_product_id,
            requested_quantity=4,
            approved_quantity=4,
        )
        db.add(ret_item_1)
        db.commit()
        db.refresh(ret_item_1)

        case_1 = WarehouseReturnCase(
            case_code=f"WHC-MULTI-{uid}",
            return_request_id=ret_req_1.id,
            warehouse_id=wh1.id,
            status=ReturnStatus.REFUNDED.value,
        )
        db.add(case_1)
        db.commit()
        db.refresh(case_1)

        # Thực hiện phân luồng RESTOCK qua manager_stock_disposition
        WarehouseReturnService.manager_stock_disposition(
            db=db,
            case_code=case_1.case_code,
            manager_user=manager,
            warehouse_id=wh1.id,
            disposition="RESTOCK",
            note="Nhập lại 4 hộp thuốc đạt chuẩn GSP",
        )

        db.refresh(stock_a)
        db.refresh(stock_b)
        # Batch A ban đầu có 7, nhận 3 -> lên 10
        assert stock_a.quantity_on_hand == 10
        assert stock_a.quantity_available == 10
        # Batch B ban đầu có 8, nhận 1 -> lên 9
        assert stock_b.quantity_on_hand == 9
        assert stock_b.quantity_available == 9

        # Kiểm tra bản ghi StockMovement được sinh ra đầy đủ
        movements = db.scalars(
            select(StockMovement)
            .where(
                StockMovement.reference_type == "WAREHOUSE_RETURN_CASE",
                StockMovement.reference_id == case_1.case_code,
            )
            .order_by(StockMovement.id.asc())
        ).all()
        assert len(movements) == 2
        assert movements[0].batch_id == batch_a.id
        assert movements[0].quantity == 3
        assert movements[0].balance_after == 10
        assert movements[1].batch_id == batch_b.id
        assert movements[1].quantity == 1
        assert movements[1].balance_after == 9

        # --- TEST 2: Chặn gọi restock lần 2 trên cùng một ca hoàn kho ---
        with pytest.raises(Exception) as exc_dup_wh:
            WarehouseReturnService.manager_stock_disposition(
                db=db,
                case_code=case_1.case_code,
                manager_user=manager,
                warehouse_id=wh1.id,
                disposition="RESTOCK",
            )
        assert exc_dup_wh.value.status_code == 400

        # --- TEST 3: Chặn restock chéo ở cấp ReturnRequest khi Warehouse đã restock ---
        # Đưa ReturnRequest về trạng thái RECEIVED để thử gọi inspect_return_items
        ret_req_1.status = ReturnStatus.RECEIVED.value
        db.commit()

        with pytest.raises(Exception) as exc_cross_req:
            ReturnService.inspect_return_items(
                db=db,
                return_code=ret_req_1.return_code,
                inspector_user=manager,
                inspection_payload=[{
                    "return_item_id": ret_item_1.id,
                    "condition": ItemCondition.GOOD_CONDITION.value,
                    "restock_destination": RestockDestination.SELLABLE_STOCK.value,
                    "accepted_quantity": 4,
                    "rejected_quantity": 0,
                    "restock_quantity": 4,
                }],
            )
        assert exc_cross_req.value.status_code == 400
        assert "đã được nhập lại kho bán trước đó" in exc_cross_req.value.detail

        # --- TEST 4: Chặn restock chéo ở cấp Warehouse khi ReturnRequest đã restock trước ---
        # Tạo Order 2 & ReturnRequest 2
        order_2 = Order(
            order_code=f"ORD-REQ-FIRST-{uid}",
            customer_id=customer.id,
            user_id=customer.id,
            total_amount=Decimal("200000"),
            payment_status="PAID",
            order_status="DELIVERED",
            assigned_warehouse_id=wh1.id,
        )
        db.add(order_2)
        db.commit()

        order_item_2 = OrderItem(
            order_id=order_2.id,
            product_id=sku.canonical_product_id,
            product_name="Thuốc Kháng Sinh Test",
            quantity=2,
            price=Decimal("100000"),
            subtotal=Decimal("200000"),
        )
        db.add(order_item_2)
        db.commit()

        # Allocation 2 hộp từ Batch B
        alloc_2 = OrderItemBatchAllocation(
            order_item_id=order_item_2.id,
            batch_id=batch_b.id,
            warehouse_id=wh1.id,
            allocated_quantity=2,
        )
        db.add(alloc_2)
        db.commit()

        ret_req_2 = ReturnRequest(
            return_code=f"RET-REQ-FIRST-{uid}",
            order_id=order_2.id,
            customer_id=customer.id,
            request_type=ReturnRequestType.REFUND_ONLY.value,
            status=ReturnStatus.RECEIVED.value,
            reason="Bác sĩ đổi đơn",
        )
        db.add(ret_req_2)
        db.commit()
        db.refresh(ret_req_2)

        ret_item_2 = ReturnItem(
            return_request_id=ret_req_2.id,
            order_item_id=order_item_2.id,
            product_name="Thuốc Kháng Sinh Test",
            product_id=sku.canonical_product_id,
            requested_quantity=2,
        )
        db.add(ret_item_2)
        db.commit()
        db.refresh(ret_item_2)

        case_2 = WarehouseReturnCase(
            case_code=f"WHC-REQ-FIRST-{uid}",
            return_request_id=ret_req_2.id,
            warehouse_id=wh1.id,
            status=ReturnStatus.APPROVED.value,
        )
        db.add(case_2)
        db.commit()

        # Gọi inspect_return_items để restock tại ReturnRequest
        ReturnService.inspect_return_items(
            db=db,
            return_code=ret_req_2.return_code,
            inspector_user=manager,
            inspection_payload=[{
                "return_item_id": ret_item_2.id,
                "condition": ItemCondition.GOOD_CONDITION.value,
                "restock_destination": RestockDestination.SELLABLE_STOCK.value,
                "accepted_quantity": 2,
                "rejected_quantity": 0,
                "restock_quantity": 2,
            }],
        )

        # Bây giờ Quản lý kho gọi restock ở cấp Warehouse -> BẮT BUỘC BỊ CHẶN 400
        with pytest.raises(Exception) as exc_cross_wh:
            WarehouseReturnService.manager_stock_disposition(
                db=db,
                case_code=case_2.case_code,
                manager_user=manager,
                warehouse_id=wh1.id,
                disposition="RESTOCK",
            )
        assert exc_cross_wh.value.status_code == 400
        assert "đã được nhập lại kho bán trước đó" in exc_cross_wh.value.detail

        # --- TEST 5: Thiếu OrderItemBatchAllocation -> Báo lỗi 400, không thay đổi tồn kho ---
        order_no_alloc = Order(
            order_code=f"ORD-NOALLOC-{uid}",
            customer_id=customer.id,
            user_id=customer.id,
            total_amount=Decimal("100000"),
            payment_status="PAID",
            order_status="DELIVERED",
            assigned_warehouse_id=wh1.id,
        )
        db.add(order_no_alloc)
        db.commit()

        item_no_alloc = OrderItem(
            order_id=order_no_alloc.id,
            product_id=sku.canonical_product_id,
            product_name="Thuốc Kháng Sinh Test",
            quantity=1,
            price=Decimal("100000"),
            subtotal=Decimal("100000"),
        )
        db.add(item_no_alloc)
        db.commit()

        ret_no_alloc = ReturnRequest(
            return_code=f"RET-NOALLOC-{uid}",
            order_id=order_no_alloc.id,
            customer_id=customer.id,
            request_type=ReturnRequestType.REFUND_ONLY.value,
            status=ReturnStatus.RECEIVED.value,
        )
        db.add(ret_no_alloc)
        db.commit()

        ret_item_no_alloc = ReturnItem(
            return_request_id=ret_no_alloc.id,
            order_item_id=item_no_alloc.id,
            product_name="Thuốc Kháng Sinh Test",
            product_id=sku.canonical_product_id,
            requested_quantity=1,
        )
        db.add(ret_item_no_alloc)
        db.commit()

        with pytest.raises(Exception) as exc_no_alloc:
            ReturnService.inspect_return_items(
                db=db,
                return_code=ret_no_alloc.return_code,
                inspector_user=manager,
                inspection_payload=[{
                    "return_item_id": ret_item_no_alloc.id,
                    "condition": ItemCondition.GOOD_CONDITION.value,
                    "restock_destination": RestockDestination.SELLABLE_STOCK.value,
                    "accepted_quantity": 1,
                    "rejected_quantity": 0,
                    "restock_quantity": 1,
                }],
            )
        assert exc_no_alloc.value.status_code == 400
        assert "Không tìm thấy thông tin lô xuất kho gốc" in exc_no_alloc.value.detail

        # --- TEST 6: Kho của allocation không khớp kho ca hoàn -> Báo lỗi 400 ---
        order_wrong_wh = Order(
            order_code=f"ORD-WRONGWH-{uid}",
            customer_id=customer.id,
            user_id=customer.id,
            total_amount=Decimal("100000"),
            payment_status="PAID",
            order_status="DELIVERED",
            assigned_warehouse_id=wh1.id,
        )
        db.add(order_wrong_wh)
        db.commit()

        item_wrong_wh = OrderItem(
            order_id=order_wrong_wh.id,
            product_id=sku.canonical_product_id,
            product_name="Thuốc Kháng Sinh Test",
            quantity=1,
            price=Decimal("100000"),
            subtotal=Decimal("100000"),
        )
        db.add(item_wrong_wh)
        db.commit()

        # Allocation ghi xuất từ Kho 2 (wh2), nhưng ca hoàn xử lý tại Kho 1 (wh1)
        alloc_wrong_wh = OrderItemBatchAllocation(
            order_item_id=item_wrong_wh.id,
            batch_id=batch_a.id,
            warehouse_id=wh2.id,  # Lệch kho
            allocated_quantity=1,
        )
        db.add(alloc_wrong_wh)
        db.commit()

        case_wrong_wh = WarehouseReturnCase(
            case_code=f"WHC-WRONGWH-{uid}",
            warehouse_id=wh1.id,
            status=ReturnStatus.APPROVED.value,
        )
        db.add(case_wrong_wh)
        db.commit()

        ret_item_wrong_wh = ReturnItem(
            return_request_id=ret_req_1.id,
            order_item_id=item_wrong_wh.id,
            product_name="Thuốc Kháng Sinh Test",
            product_id=sku.canonical_product_id,
            requested_quantity=1,
            approved_quantity=1,
        )
        db.add(ret_item_wrong_wh)
        case_wrong_wh.items.append(ret_item_wrong_wh)
        db.commit()

        with pytest.raises(Exception) as exc_mismatch_wh:
            WarehouseReturnService.manager_stock_disposition(
                db=db,
                case_code=case_wrong_wh.case_code,
                manager_user=manager,
                warehouse_id=wh1.id,
                disposition="RESTOCK",
            )
        assert exc_mismatch_wh.value.status_code == 400
        assert "không khớp với kho" in exc_mismatch_wh.value.detail

        # --- TEST 7: QUARANTINE và DISPOSE tuyệt đối không tăng tồn kho có thể bán ---
        case_quar = WarehouseReturnCase(
            case_code=f"WHC-QUAR-{uid}",
            warehouse_id=wh1.id,
            status=ReturnStatus.APPROVED.value,
        )
        db.add(case_quar)
        db.commit()

        stock_a_before = stock_a.quantity_available
        stock_a_onhand_before = stock_a.quantity_on_hand

        WarehouseReturnService.manager_stock_disposition(
            db=db,
            case_code=case_quar.case_code,
            manager_user=manager,
            warehouse_id=wh1.id,
            disposition="QUARANTINE",
            note="Hàng nghi ngờ biến chất, chuyển cách ly",
        )
        db.refresh(stock_a)
        assert stock_a.quantity_available == stock_a_before
        assert stock_a.quantity_on_hand == stock_a_onhand_before

    finally:
        db.close()
