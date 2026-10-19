from datetime import UTC, datetime
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import CanonicalProduct, Order, OrderItem, User
from app.models.enums import UserRole
from app.models.inventory import (
    FulfillmentItem,
    InventoryBatch,
    OrderFulfillment,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    StockReservation,
    Warehouse,
    WarehouseBatchStock,
    UserWarehouseMembership,
)
from app.models.returns import (
    ItemCondition,
    RestockDestination,
    ReturnItem,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
    WarehouseReturnCase,
)
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.refund_calculation_service import RefundCalculationService
from app.services.return_restock_service import ReturnRestockService
from app.services.return_service import ReturnService
from app.services.warehouse_return_service import WarehouseReturnService


def utcnow() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_final_five_security_and_integrity_fixes(db_session):
    client = TestClient(app)
    uid = uuid.uuid4().hex[:6].upper()

    # 1. SETUP MASTER DATA
    wh_hn = Warehouse(name=f"Kho Ha Noi {uid}", code=f"WH-HN-{uid}", address="123 Test HN", province="Hà Nội", district="Đống Đa", is_active=True)
    wh_sg = Warehouse(name=f"Kho Sai Gon {uid}", code=f"WH-SG-{uid}", address="456 Test SG", province="TP Hồ Chí Minh", district="Quận 1", is_active=True)
    db_session.add(wh_hn)
    db_session.add(wh_sg)
    db_session.commit()
    db_session.refresh(wh_hn)
    db_session.refresh(wh_sg)

    admin_user = User(
        email=f"admin_{uid}@pharmatrust.test",
        password_hash=hash_password("Pass@123"),
        full_name="System Admin",
        role=UserRole.ADMIN,
        is_active=True,
        token_version=1,
    )
    manager_hn = User(
        email=f"mgr_hn_{uid}@pharmatrust.test",
        password_hash=hash_password("Pass@123"),
        full_name="Manager HN",
        role=UserRole.WAREHOUSE_MANAGER,
        warehouse_id=wh_hn.id,
        is_active=True,
        token_version=1,
    )
    manager_sg = User(
        email=f"mgr_sg_{uid}@pharmatrust.test",
        password_hash=hash_password("Pass@123"),
        full_name="Manager SG",
        role=UserRole.WAREHOUSE_MANAGER,
        warehouse_id=wh_sg.id,
        is_active=True,
        token_version=1,
    )
    customer_a = User(
        email=f"cust_a_{uid}@pharmatrust.test",
        password_hash=hash_password("Pass@123"),
        full_name="Customer A",
        role=UserRole.CUSTOMER,
        is_active=True,
        token_version=1,
    )
    customer_b = User(
        email=f"cust_b_{uid}@pharmatrust.test",
        password_hash=hash_password("Pass@123"),
        full_name="Customer B",
        role=UserRole.CUSTOMER,
        is_active=True,
        token_version=1,
    )
    db_session.add_all([admin_user, manager_hn, manager_sg, customer_a, customer_b])
    db_session.commit()
    for u in [admin_user, manager_hn, manager_sg, customer_a, customer_b]:
        db_session.refresh(u)

    db_session.add_all([
        UserWarehouseMembership(
            user_id=manager_hn.id,
            warehouse_id=wh_hn.id,
            role=manager_hn.role.value,
            is_active=True,
        ),
        UserWarehouseMembership(
            user_id=manager_sg.id,
            warehouse_id=wh_sg.id,
            role=manager_sg.role.value,
            is_active=True,
        ),
    ])
    db_session.commit()

    product = CanonicalProduct(
        canonical_name=f"Kháng sinh Zithro {uid}",
        registration_number=f"VN-REG-{uid}",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    sku = ProductSku(
        canonical_product_id=product.id,
        sku_code=f"SKU-{uid}",
        barcode=f"BC-{uid}",
        uom="Hộp",
        base_price=Decimal("100000"),
        is_active=True,
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(sku)

    batch_1 = InventoryBatch(
        sku_id=sku.id,
        batch_number=f"BAT-1-{uid}",
        initial_quantity=50,
        expiry_date=datetime(2027, 12, 31, tzinfo=UTC).date(),
    )
    batch_2 = InventoryBatch(
        sku_id=sku.id,
        batch_number=f"BAT-2-{uid}",
        initial_quantity=50,
        expiry_date=datetime(2028, 6, 30, tzinfo=UTC).date(),
    )
    db_session.add_all([batch_1, batch_2])
    db_session.commit()
    db_session.refresh(batch_1)
    db_session.refresh(batch_2)

    stock_hn_1 = WarehouseBatchStock(
        warehouse_id=wh_hn.id,
        batch_id=batch_1.id,
        quantity_on_hand=50,
        quantity_available=50,
        quantity_reserved=0,
    )
    stock_hn_2 = WarehouseBatchStock(
        warehouse_id=wh_hn.id,
        batch_id=batch_2.id,
        quantity_on_hand=50,
        quantity_available=50,
        quantity_reserved=0,
    )
    db_session.add_all([stock_hn_1, stock_hn_2])
    db_session.commit()

    token_admin = create_access_token(str(admin_user.id), admin_user.role, 1)
    token_mgr_hn = create_access_token(str(manager_hn.id), manager_hn.role, 1)
    token_mgr_sg = create_access_token(str(manager_sg.id), manager_sg.role, 1)
    token_cust_a = create_access_token(str(customer_a.id), customer_a.role, 1)
    token_cust_b = create_access_token(str(customer_b.id), customer_b.role, 1)

    # =========================================================================
    # TASK 1: NEXT.JS ATTACHMENT LOAD / FASTAPI PERMISSIONS (LINE 11)
    # =========================================================================
    import io

    # Tạo phiên chat cho customer_a
    res_sess = client.post(
        "/api/v1/live-chat/sessions",
        json={"customer_name": "Customer A", "subject": "Tư vấn thuốc"},
        headers={"Authorization": f"Bearer {token_cust_a}"},
    )
    assert res_sess.status_code == 200
    sess_code = res_sess.json()["session_code"]

    # Upload attachment hợp lệ
    sample_content = b"%PDF-1.4 test document"
    res_up = client.post(
        "/api/v1/live-chat/attachments/upload",
        data={"session_code": sess_code},
        files={"file": ("don_thuoc.pdf", io.BytesIO(sample_content), "application/pdf")},
        headers={"Authorization": f"Bearer {token_cust_a}"},
    )
    assert res_up.status_code == 200
    att_code = res_up.json()["attachment_code"]

    # 1.1: Download không có token -> 401
    res = client.get(f"/api/v1/live-chat/attachments/{att_code}")
    assert res.status_code == 401

    # 1.2: Download bởi user khác (customer_b) -> 403
    res = client.get(
        f"/api/v1/live-chat/attachments/{att_code}",
        headers={"Authorization": f"Bearer {token_cust_b}"},
    )
    assert res.status_code == 403

    # 1.3: Download đúng chủ phiên (customer_a) -> 200
    res = client.get(
        f"/api/v1/live-chat/attachments/{att_code}",
        headers={"Authorization": f"Bearer {token_cust_a}"},
    )
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"

    # 1.4: Download file không tồn tại trong hệ thống -> 404
    res = client.get(
        "/api/v1/live-chat/attachments/att-nonexistent-12345",
        headers={"Authorization": f"Bearer {token_cust_a}"},
    )
    assert res.status_code == 404

    # =========================================================================
    # TASK 3: FULFILLMENT FSM & DISPATCH INTEGRITY (LINE 15)
    # =========================================================================
    # Create order with 2 fulfillments to test multi-fulfillment requirements
    order_ff = Order(
        order_code=f"ORD-FF-{uid}",
        user_id=customer_a.id,
        customer_name="Cust A",
        customer_phone="0911222333",
        shipping_address="Hà Nội",
        total_amount=Decimal("300000"),
        payment_status="PAID",
        order_status="PROCESSING",
        fulfillment_status="PENDING",
        assigned_warehouse_id=wh_hn.id,
    )
    db_session.add(order_ff)
    db_session.commit()
    db_session.refresh(order_ff)

    order_item_ff = OrderItem(
        order_id=order_ff.id,
        product_id=product.id,
        product_name=product.canonical_name,
        quantity=3,
        price=Decimal("100000"),
        subtotal=Decimal("300000"),
    )
    db_session.add(order_item_ff)
    db_session.commit()
    db_session.refresh(order_item_ff)

    ff_1 = OrderFulfillment(
        order_id=order_ff.id,
        fulfillment_code=f"FF1-{uid}",
        warehouse_id=wh_hn.id,
        status="PENDING",
    )
    ff_2 = OrderFulfillment(
        order_id=order_ff.id,
        fulfillment_code=f"FF2-{uid}",
        warehouse_id=wh_sg.id,
        status="PENDING",
    )
    db_session.add_all([ff_1, ff_2])
    db_session.commit()
    db_session.refresh(ff_1)
    db_session.refresh(ff_2)

    ff_item_1 = FulfillmentItem(
        fulfillment_id=ff_1.id,
        order_item_id=order_item_ff.id,
        quantity=2,
    )
    db_session.add(ff_item_1)
    db_session.commit()
    db_session.refresh(ff_item_1)

    # Allocations for ff_1: 2 units from batch_1 at wh_hn
    alloc_ff1 = OrderItemBatchAllocation(
        order_item_id=order_item_ff.id,
        fulfillment_item_id=ff_item_1.id,
        batch_id=batch_1.id,
        warehouse_id=wh_hn.id,
        allocated_quantity=2,
    )
    db_session.add(alloc_ff1)

    # Reserve 2 units in stock
    stock_hn_1.quantity_available -= 2
    stock_hn_1.quantity_reserved += 2

    resv_ff1 = StockReservation(
        order_id=order_ff.id,
        warehouse_id=wh_hn.id,
        batch_id=batch_1.id,
        quantity=2,
        status="RESERVED",
    )
    db_session.add(resv_ff1)
    db_session.commit()

    # 3.1: Multi-fulfillment order PATCH without fulfillment_id must return 400
    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_ff.id}/fulfillment",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"fulfillment_status": "PICKED"},
    )
    assert res.status_code == 400
    assert "chỉ định rõ 'fulfillment_id'" in res.json()["detail"]

    # 3.2: Multi-fulfillment order PATCH with warehouse mismatch must return 403
    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_ff.id}/fulfillment",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"fulfillment_id": ff_2.id, "fulfillment_status": "PICKED"},
    )
    assert res.status_code == 403

    # 3.3: Strict FSM check: cannot jump from PENDING directly to SHIPPED
    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_ff.id}/fulfillment",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"fulfillment_id": ff_1.id, "fulfillment_status": "SHIPPED"},
    )
    assert res.status_code == 400
    assert "Quy trình bắt buộc tuần tự" in res.json()["detail"]

    # 3.4: Normal flow: PENDING -> PICKED -> PACKED
    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_ff.id}/fulfillment",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"fulfillment_id": ff_1.id, "fulfillment_status": "PICKED"},
    )
    assert res.status_code == 200

    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_ff.id}/fulfillment",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"fulfillment_id": ff_1.id, "fulfillment_status": "PACKED"},
    )
    assert res.status_code == 200

    # 3.5: PACKED -> SHIPPED: Successfully pre-validates and atomically deducts stock
    prev_on_hand = stock_hn_1.quantity_on_hand
    prev_reserved = stock_hn_1.quantity_reserved

    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_ff.id}/fulfillment",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"fulfillment_id": ff_1.id, "fulfillment_status": "SHIPPED"},
    )
    assert res.status_code == 200

    db_session.refresh(stock_hn_1)
    db_session.refresh(resv_ff1)
    assert stock_hn_1.quantity_on_hand == prev_on_hand - 2
    assert stock_hn_1.quantity_reserved == prev_reserved - 2
    assert resv_ff1.status == "FULFILLED"

    # Verify DISPATCH StockMovement was generated
    dispatch_mv = db_session.scalar(
        select(StockMovement).where(
            StockMovement.reference_id == ff_1.fulfillment_code,
            StockMovement.movement_type == "DISPATCH",
        )
    )
    assert dispatch_mv is not None
    assert dispatch_mv.quantity == -2
    assert dispatch_mv.warehouse_id == wh_hn.id

    # 3.6: Idempotency check: sending SHIPPED again does not double deduct
    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_ff.id}/fulfillment",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"fulfillment_id": ff_1.id, "fulfillment_status": "SHIPPED"},
    )
    assert res.status_code == 200
    db_session.refresh(stock_hn_1)
    assert stock_hn_1.quantity_on_hand == prev_on_hand - 2

    # =========================================================================
    # TASK 4: INSPECTION SCHEMA ZERO DEFAULTS & SAFETY (LINE 16)
    # =========================================================================
    # Create return request for testing inspection
    ret_req_insp = ReturnRequest(
        return_code=f"RET-INSP-{uid}",
        order_id=order_ff.id,
        user_id=customer_a.id,
        customer_name="Cust A",
        customer_phone="0911222333",
        request_type=ReturnRequestType.RETURN.value,
        status=ReturnStatus.RECEIVED.value,
        reason_code="DAMAGED",
        reason_text="Bao bì rách",
    )
    db_session.add(ret_req_insp)
    db_session.commit()
    db_session.refresh(ret_req_insp)

    ret_item_insp = ReturnItem(
        return_request_id=ret_req_insp.id,
        order_item_id=order_item_ff.id,
        product_id=product.id,
        product_name=product.canonical_name,
        original_quantity=3,
        requested_quantity=1,
        received_quantity=1,
        unit_price_at_purchase=Decimal("100000"),
        net_paid_amount=Decimal("100000"),
        requested_refund_amount=Decimal("100000"),
    )
    db_session.add(ret_item_insp)
    db_session.commit()
    db_session.refresh(ret_item_insp)

    # 4.1: Missing condition -> 422
    payload_bad = {
        "items": [{
            "return_item_id": ret_item_insp.id,
            "restock_destination": "SELLABLE_STOCK",
            "accepted_quantity": 1,
            "rejected_quantity": 0,
            "restock_quantity": 1,
        }]
    }
    res = client.post(
        f"/api/v1/admin/returns/{ret_req_insp.return_code}/inspect",
        headers={"Authorization": f"Bearer {token_admin}"},
        json=payload_bad,
    )
    assert res.status_code == 422

    # 4.2: Missing restock_quantity when destination is SELLABLE_STOCK -> 422
    payload_bad_dest = {
        "items": [{
            "return_item_id": ret_item_insp.id,
            "condition": "GOOD_CONDITION",
            "restock_destination": "SELLABLE_STOCK",
            "accepted_quantity": 1,
            "rejected_quantity": 0,
        }]
    }
    res = client.post(
        f"/api/v1/admin/returns/{ret_req_insp.return_code}/inspect",
        headers={"Authorization": f"Bearer {token_admin}"},
        json=payload_bad_dest,
    )
    assert res.status_code == 422

    # 4.3: Damaged condition attempting SELLABLE_STOCK -> 422 (GSP compliance)
    payload_bad_gsp = {
        "items": [{
            "return_item_id": ret_item_insp.id,
            "condition": "DAMAGED",
            "restock_destination": "SELLABLE_STOCK",
            "accepted_quantity": 1,
            "rejected_quantity": 0,
            "restock_quantity": 1,
        }]
    }
    res = client.post(
        f"/api/v1/admin/returns/{ret_req_insp.return_code}/inspect",
        headers={"Authorization": f"Bearer {token_admin}"},
        json=payload_bad_gsp,
    )
    assert res.status_code == 422

    # =========================================================================
    # TASK 5: MANAGER APPROVAL FULL COVERAGE & STRICT QUANTITIES (LINE 17)
    # =========================================================================
    case_app = WarehouseReturnCase(
        case_code=f"WHC-APP-{uid}",
        return_request_id=ret_req_insp.id,
        warehouse_id=wh_hn.id,
        status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
    )
    db_session.add(case_app)
    db_session.commit()
    db_session.refresh(case_app)

    # 5.1: Missing items in ApproveReturnPayload -> 422
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_app.case_code}/approve",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"manager_note": "Approved"},
    )
    assert res.status_code == 422

    # 5.2: Total approved == 0 -> 400
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_app.case_code}/approve",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={
            "items": [{
                "return_item_id": ret_item_insp.id,
                "approved_quantity": 0,
                "rejected_quantity": 1,
                "rejection_reason": "Không đủ điều kiện hoàn",
            }]
        },
    )
    assert res.status_code == 400
    assert "Tổng số lượng sản phẩm được duyệt là 0" in res.json()["detail"]

    # 5.3: Rejected quantity > 0 but missing rejection_reason -> 422
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_app.case_code}/approve",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={
            "items": [{
                "return_item_id": ret_item_insp.id,
                "approved_quantity": 0,
                "rejected_quantity": 1,
            }]
        },
    )
    assert res.status_code == 422

    # 5.4: Valid approval of 1 unit -> 200, checks approved_refund_amount calculated correctly
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_app.case_code}/approve",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={
            "items": [{
                "return_item_id": ret_item_insp.id,
                "approved_quantity": 1,
                "rejected_quantity": 0,
            }]
        },
    )
    assert res.status_code == 200
    db_session.refresh(case_app)
    db_session.refresh(ret_item_insp)
    assert case_app.status == ReturnStatus.REFUND_PENDING.value
    assert ret_item_insp.approved_quantity == 1
    assert ret_item_insp.approved_refund_amount == Decimal("100000.00")

    # =========================================================================
    # TASK 2: MULTI-BATCH RETURN RESTOCK & CUMULATIVE INTEGRITY (LINE 14)
    # =========================================================================
    # Advance case to REFUNDED to allow disposition
    case_app.status = ReturnStatus.REFUNDED.value
    db_session.commit()

    # Pre-check stock before disposition
    prev_stock_hn_1 = stock_hn_1.quantity_on_hand

    # Perform RESTOCK disposition
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_app.case_code}/stock-disposition",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"disposition": "RESTOCK", "note": "Restock 1 unit"},
    )
    assert res.status_code == 200

    db_session.refresh(stock_hn_1)
    db_session.refresh(case_app)
    assert case_app.status == ReturnStatus.RESTOCKED.value
    assert stock_hn_1.quantity_on_hand == prev_stock_hn_1 + 1

    # Verify StockMovement RETURN_RESTOCK
    restock_mv = db_session.scalar(
        select(StockMovement).where(
            StockMovement.reference_id == case_app.case_code,
            StockMovement.movement_type == "RETURN_RESTOCK",
        )
    )
    assert restock_mv is not None
    assert restock_mv.quantity == 1
    assert restock_mv.batch_id == batch_1.id

    # 2.2: Idempotency: cannot restock case_app again -> 400
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_app.case_code}/stock-disposition",
        headers={"Authorization": f"Bearer {token_mgr_hn}"},
        json={"disposition": "RESTOCK"},
    )
    assert res.status_code == 400
    assert "đã được xử lý phân luồng" in res.json()["detail"] or "nhập lại kho bán trước đó" in res.json()["detail"]

    # 2.3: Cross-idempotency: Admin cannot restock parent return_request again -> 400
    res = client.post(
        f"/api/v1/admin/returns/{ret_req_insp.return_code}/inspect",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={
            "items": [{
                "return_item_id": ret_item_insp.id,
                "condition": "GOOD_CONDITION",
                "package_condition": "SEALED",
                "seal_intact": True,
                "batch_matched": True,
                "expiry_matched": True,
                "storage_condition_ok": True,
                "restock_destination": "SELLABLE_STOCK",
                "accepted_quantity": 1,
                "rejected_quantity": 0,
                "restock_quantity": 1,
            }]
        },
    )
    assert res.status_code == 400
    assert "đã được nhập lại kho bán trước đó" in res.json()["detail"]
