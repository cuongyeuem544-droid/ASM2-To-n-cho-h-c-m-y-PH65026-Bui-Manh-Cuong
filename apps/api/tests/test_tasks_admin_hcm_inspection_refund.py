"""
Tests for Admin HCM Picking & Packing, Return Inspection Safety Validation, and Approved Quantity & Direct Refund Integrity.
"""

from datetime import UTC, datetime
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import AuditLog, CanonicalProduct, Order, OrderItem, User
from app.models.enums import FulfillmentStatus, UserRole
from app.models.inventory import (
    BatchStatus,
    InventoryBatch,
    OrderFulfillment,
    ProductSku,
    UserWarehouseMembership,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import (
    Refund,
    RefundMethod,
    RefundStatus,
    ReturnItem,
    ReturnRequest,
    ReturnStatus,
    WarehouseReturnCase,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_setup():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]

    # Create Warehouses: HCM and HN
    hcm_wh = Warehouse(
        name=f"Kho Tổng HCM {suffix}",
        code=f"KHO-HCM-{suffix}".upper(),
        address="123 Quận 1, TP. HCM",
        is_central=True,
        is_active=True,
    )
    hn_wh = Warehouse(
        name=f"Kho Tổng HN {suffix}",
        code=f"KHO-HN-{suffix}".upper(),
        address="456 Hoàn Kiếm, Hà Nội",
        is_central=False,
        is_active=True,
    )
    db.add_all([hcm_wh, hn_wh])
    db.commit()
    db.refresh(hcm_wh)
    db.refresh(hn_wh)

    # Create Users: Admin, HCM Manager, HN Manager, HCM Staff
    admin = User(
        email=f"admin_{suffix}@pharmatrust.test",
        password_hash=hash_password("Admin@123456"),
        full_name="System Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    hcm_manager = User(
        email=f"mgr_hcm_{suffix}@pharmatrust.test",
        password_hash=hash_password("Mgr@123456"),
        full_name="HCM Manager",
        role=UserRole.WAREHOUSE_MANAGER,
        is_active=True,
    )
    hn_manager = User(
        email=f"mgr_hn_{suffix}@pharmatrust.test",
        password_hash=hash_password("Mgr@123456"),
        full_name="HN Manager",
        role=UserRole.WAREHOUSE_MANAGER,
        is_active=True,
    )
    hcm_staff = User(
        email=f"staff_hcm_{suffix}@pharmatrust.test",
        password_hash=hash_password("Staff@123456"),
        full_name="HCM Staff",
        role=UserRole.WAREHOUSE_STAFF,
        is_active=True,
    )
    customer = User(
        email=f"cust_{suffix}@pharmatrust.test",
        password_hash=hash_password("Cust@123456"),
        full_name="Customer Test",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db.add_all([admin, hcm_manager, hn_manager, hcm_staff, customer])
    db.commit()
    for u in [admin, hcm_manager, hn_manager, hcm_staff, customer]:
        db.refresh(u)

    # Memberships
    m1 = UserWarehouseMembership(user_id=hcm_manager.id, warehouse_id=hcm_wh.id, role="WAREHOUSE_MANAGER", is_active=True)
    m2 = UserWarehouseMembership(user_id=hn_manager.id, warehouse_id=hn_wh.id, role="WAREHOUSE_MANAGER", is_active=True)
    m3 = UserWarehouseMembership(user_id=hcm_staff.id, warehouse_id=hcm_wh.id, role="WAREHOUSE_STAFF", is_active=True)
    db.add_all([m1, m2, m3])

    # Products & SKUs
    prod = CanonicalProduct(canonical_name=f"Paracetamol 500mg {suffix}")
    db.add(prod)
    db.commit()
    db.refresh(prod)

    sku = ProductSku(
        canonical_product_id=prod.id,
        sku_code=f"SKU-{suffix}",
        base_price=Decimal("50000.0"),
        uom="Hộp",
        conversion_rate=1,
        is_active=True,
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)

    # Batches in HCM
    batch_hcm = InventoryBatch(
        sku_id=sku.id,
        batch_number=f"BATCH-HCM-{suffix}",
        status=BatchStatus.ACTIVE,
        initial_quantity=100,
        expiry_date=datetime(2028, 1, 1).date(),
    )
    db.add(batch_hcm)
    db.commit()
    db.refresh(batch_hcm)

    stock_hcm = WarehouseBatchStock(
        warehouse_id=hcm_wh.id,
        batch_id=batch_hcm.id,
        quantity_on_hand=100,
        quantity_reserved=0,
    )
    db.add(stock_hcm)
    db.commit()
    db.refresh(stock_hcm)

    # Order in HCM
    order = Order(
        order_code=f"ORD-HCM-{suffix}",
        user_id=customer.id,
        customer_name=customer.full_name,
        customer_phone="0912345678",
        shipping_address="123 Lê Lợi, Quận 1, TP. HCM",
        order_status="CONFIRMED",
        fulfillment_status=FulfillmentStatus.ALLOCATED.value,
        total_amount=Decimal("150000.0"),
        shipping_fee=Decimal("15000.0"),
        assigned_warehouse_id=hcm_wh.id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        product_sku=sku.sku_code,
        product_name=prod.canonical_name,
        quantity=2,
        price=Decimal("50000.0"),
        subtotal=Decimal("100000.0"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    ff = OrderFulfillment(
        order_id=order.id,
        warehouse_id=hcm_wh.id,
        status=FulfillmentStatus.ALLOCATED.value,
        fulfillment_code=f"FF-{suffix}",
    )
    db.add(ff)
    db.commit()
    db.refresh(ff)

    yield {
        "db": db,
        "hcm_wh": hcm_wh,
        "hn_wh": hn_wh,
        "admin": admin,
        "hcm_manager": hcm_manager,
        "hn_manager": hn_manager,
        "hcm_staff": hcm_staff,
        "customer": customer,
        "product": prod,
        "sku": sku,
        "batch_hcm": batch_hcm,
        "order": order,
        "order_item": item,
        "fulfillment": ff,
    }
    db.close()


def test_admin_hcm_picking_packing_and_anti_idor(client, test_setup):
    """
    Task 6:
    1. Admin accesses /warehouse-portal/orders with warehouse_code=KHO-HCM-..., gets orders.
    2. Admin accesses pick details and updates fulfillment status; audit log contains Admin user and HCM warehouse.
    3. HN Manager trying to access HCM warehouse_code or warehouse_id is rejected with 403 (Anti-IDOR).
    4. Admin providing ambiguous or nonexistent warehouse code gets 400 or 404.
    """
    admin = test_setup["admin"]
    hn_manager = test_setup["hn_manager"]
    hcm_wh = test_setup["hcm_wh"]
    order = test_setup["order"]

    admin_token = create_access_token(str(admin.id), admin.role)
    hn_token = create_access_token(str(hn_manager.id), hn_manager.role)

    # 1. Admin gets orders for HCM warehouse
    resp = client.get(
        f"/api/v1/warehouse-portal/orders?warehouse_code={hcm_wh.code}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert any(o["order_code"] == order.order_code for o in data["items"])

    # 2. Admin gets pick details
    resp_pick = client.get(
        f"/api/v1/warehouse-portal/orders/{order.id}/pick-details?warehouse_code={hcm_wh.code}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_pick.status_code == 200, resp_pick.text
    assert resp_pick.json()["order_code"] == order.order_code

    # 3. Admin updates fulfillment status
    resp_update = client.patch(
        f"/api/v1/warehouse-portal/orders/{order.id}/fulfillment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "fulfillment_status": "PICKING",
            "warehouse_code": hcm_wh.code,
            "note": "Admin picking test",
        },
    )
    assert resp_update.status_code == 200, resp_update.text

    # Verify AuditLog created with admin identity and HCM warehouse
    db = test_setup["db"]
    audit = db.scalar(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "Order",
            AuditLog.entity_id == str(order.id),
            AuditLog.action == "UPDATE_FULFILLMENT_STATUS",
            AuditLog.user_id == admin.id,
        )
        .order_by(AuditLog.id.desc())
    )
    assert audit is not None
    assert audit.after_json.get("warehouse_id") == hcm_wh.id
    assert audit.after_json.get("operator_role") == "ADMIN"

    # 4. Anti-IDOR: HN Manager trying to access HCM warehouse via code or ID
    resp_idor_code = client.get(
        f"/api/v1/warehouse-portal/orders?warehouse_code={hcm_wh.code}",
        headers={"Authorization": f"Bearer {hn_token}"},
    )
    assert resp_idor_code.status_code == 403

    resp_idor_id = client.get(
        f"/api/v1/warehouse-portal/orders?warehouse_id={hcm_wh.id}",
        headers={"Authorization": f"Bearer {hn_token}"},
    )
    assert resp_idor_id.status_code == 403

    # 5. Non-existent warehouse code for Admin returns 404
    resp_nonexistent = client.get(
        "/api/v1/warehouse-portal/orders?warehouse_code=NON_EXISTENT_KHO_999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_nonexistent.status_code == 404


def test_inspection_strict_safety_validation(client, test_setup):
    """
    Task 7:
    1. Submitting inspection with missing/null/empty boolean fields must return 422.
    2. Submitting string 'false' must be parsed as False (not True).
    3. If any safety check is False, RESTOCK / SELLABLE_STOCK is strictly rejected with 400.
    4. Only when 100% of safety criteria are True can RESTOCK be accepted.
    """
    db = test_setup["db"]
    hcm_staff = test_setup["hcm_staff"]
    hcm_wh = test_setup["hcm_wh"]
    order = test_setup["order"]
    order_item = test_setup["order_item"]
    customer = test_setup["customer"]

    staff_token = create_access_token(str(hcm_staff.id), hcm_staff.role)

    # Create ReturnRequest and WarehouseReturnCase
    ret_req = ReturnRequest(
        return_code=f"RET-TEST-{uuid.uuid4().hex[:6]}",
        order_id=order.id,
        user_id=customer.id,
        customer_name=customer.full_name,
        customer_phone=order.customer_phone,
        reason_code="DAMAGED",
        reason_text="Bao bì hỏng",
        status=ReturnStatus.RECEIVED.value,
    )
    db.add(ret_req)
    db.commit()
    db.refresh(ret_req)

    ret_item = ReturnItem(
        return_request_id=ret_req.id,
        order_item_id=order_item.id,
        product_id=order_item.product_id,
        product_name=order_item.product_name,
        original_quantity=order_item.quantity,
        requested_quantity=2,
        unit_price_at_purchase=order_item.price,
        allocated_discount=Decimal("0.0"),
        net_paid_amount=Decimal("100000.0"),
        requested_refund_amount=Decimal("100000.0"),
        received_quantity=2,
        approved_quantity=0,
    )
    db.add(ret_item)
    db.commit()
    db.refresh(ret_item)

    wcase = WarehouseReturnCase(
        case_code=f"CASE-{uuid.uuid4().hex[:6]}",
        return_request_id=ret_req.id,
        warehouse_id=hcm_wh.id,
        status=ReturnStatus.RECEIVED.value,
        assigned_staff_id=hcm_staff.id,
    )
    db.add(wcase)
    db.commit()
    db.refresh(wcase)

    # 1. Missing boolean fields -> 422
    resp_missing = client.post(
        f"/api/v1/warehouse/staff/me/returns/{wcase.case_code}/inspect",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={
            "inspections": [
                {
                    "return_item_id": ret_item.id,
                    "package_condition": "SEALED",
                    "received_quantity": 2,
                    "accepted_quantity": 2,
                    "rejected_quantity": 0,
                    "suggested_action": "RESTOCK",
                    # seal_intact, batch_matched, expiry_matched, storage_condition_ok are missing
                }
            ]
        },
    )
    assert resp_missing.status_code == 422

    # 2. String 'false' parsed as False, and since it is False, RESTOCK must be rejected with 400
    resp_false_string = client.post(
        f"/api/v1/warehouse/staff/me/returns/{wcase.case_code}/inspect",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={
            "inspections": [
                {
                    "return_item_id": ret_item.id,
                    "package_condition": "Nguyên vẹn",
                    "seal_intact": "false",  # string "false"
                    "batch_matched": "true",
                    "expiry_matched": "true",
                    "storage_condition_ok": "true",
                    "received_quantity": 2,
                    "accepted_quantity": 2,
                    "rejected_quantity": 0,
                    "suggested_action": "RESTOCK",
                }
            ]
        },
    )
    # Pydantic or service must reject RESTOCK because seal_intact is False!
    assert resp_false_string.status_code in (400, 422), resp_false_string.text
    assert "an toàn" in resp_false_string.text.lower() or "restock" in resp_false_string.text.lower()

    # 3. Damaged packaging cannot be RESTOCK -> 400 / 422
    resp_damaged = client.post(
        f"/api/v1/warehouse/staff/me/returns/{wcase.case_code}/inspect",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={
            "inspections": [
                {
                    "return_item_id": ret_item.id,
                    "package_condition": "Bao bì bị móp méo rách tem",
                    "seal_intact": True,
                    "batch_matched": True,
                    "expiry_matched": True,
                    "storage_condition_ok": True,
                    "received_quantity": 2,
                    "accepted_quantity": 2,
                    "rejected_quantity": 0,
                    "suggested_action": "RESTOCK",
                }
            ]
        },
    )
    assert resp_damaged.status_code in (400, 422), resp_damaged.text

    # 4. Valid inspection with DISPOSE when criteria fail
    resp_dispose = client.post(
        f"/api/v1/warehouse/staff/me/returns/{wcase.case_code}/inspect",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={
            "inspections": [
                {
                    "return_item_id": ret_item.id,
                    "package_condition": "Hư hỏng",
                    "seal_intact": False,
                    "batch_matched": False,
                    "expiry_matched": False,
                    "storage_condition_ok": False,
                    "received_quantity": 2,
                    "accepted_quantity": 0,
                    "rejected_quantity": 2,
                    "rejection_reason": "Thuốc hỏng niêm phong",
                    "suggested_action": "DISPOSE",
                }
            ]
        },
    )
    assert resp_dispose.status_code == 200, resp_dispose.text


def test_approved_quantity_and_admin_direct_refund_protection(client, test_setup):
    """
    Task 8:
    1. If approved_quantity is 0, it must NOT be auto-raised to requested_quantity.
    2. If total approved quantity is 0, approval must be rejected with 400.
    3. Calling Admin direct refund without return_code or when return is unapproved must be rejected.
    """
    db = test_setup["db"]
    hcm_manager = test_setup["hcm_manager"]
    hcm_wh = test_setup["hcm_wh"]
    order = test_setup["order"]
    order_item = test_setup["order_item"]
    customer = test_setup["customer"]
    admin = test_setup["admin"]

    mgr_token = create_access_token(str(hcm_manager.id), hcm_manager.role)
    admin_token = create_access_token(str(admin.id), admin.role)

    # Create ReturnRequest and Case
    ret_req = ReturnRequest(
        return_code=f"RET-APP-{uuid.uuid4().hex[:6]}",
        order_id=order.id,
        user_id=customer.id,
        customer_name=customer.full_name,
        customer_phone=order.customer_phone,
        reason_code="DAMAGED",
        reason_text="Không hài lòng",
        status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
    )
    db.add(ret_req)
    db.commit()
    db.refresh(ret_req)

    ret_item = ReturnItem(
        return_request_id=ret_req.id,
        order_item_id=order_item.id,
        product_id=order_item.product_id,
        product_name=order_item.product_name,
        original_quantity=order_item.quantity,
        requested_quantity=2,
        unit_price_at_purchase=order_item.price,
        allocated_discount=Decimal("0.0"),
        net_paid_amount=Decimal("100000.0"),
        requested_refund_amount=Decimal("100000.0"),
        received_quantity=2,
        approved_quantity=0,
    )
    db.add(ret_item)
    db.commit()
    db.refresh(ret_item)

    wcase = WarehouseReturnCase(
        case_code=f"CASE-APP-{uuid.uuid4().hex[:6]}",
        return_request_id=ret_req.id,
        warehouse_id=hcm_wh.id,
        status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
    )
    db.add(wcase)
    db.commit()
    db.refresh(wcase)

    # 1. Manager tries to approve with approved_quantity = 0 -> rejected with 400 (must use reject)
    resp_approve_zero = client.post(
        f"/api/v1/warehouse/me/returns/{wcase.case_code}/approve",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={
            "items": [
                {
                    "return_item_id": ret_item.id,
                    "approved_quantity": 0,
                    "rejected_quantity": 2,
                    "rejection_reason": "Từ chối hoàn",
                }
            ],
            "manager_note": "Không duyệt món nào",
        },
    )
    assert resp_approve_zero.status_code == 400
    assert "0" in resp_approve_zero.text

    # 2. Admin tries to create refund directly without return_code -> 422 or 400
    resp_admin_no_ret = client.post(
        "/api/v1/admin/refunds",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "order_code": order.order_code,
            "refund_amount": 100000.0,
            "refund_method": RefundMethod.BANK_TRANSFER.value,
            # return_code is omitted
        },
    )
    assert resp_admin_no_ret.status_code in (400, 422)

    # 3. Admin tries to create refund with unapproved return_code -> 400
    resp_admin_unapproved = client.post(
        "/api/v1/admin/refunds",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "order_code": order.order_code,
            "refund_amount": 100000.0,
            "refund_method": RefundMethod.BANK_TRANSFER.value,
            "return_code": ret_req.return_code,
        },
    )
    assert resp_admin_unapproved.status_code == 400
    assert "phê duyệt" in resp_admin_unapproved.text.lower() or "chưa có quyết định" in resp_admin_unapproved.text.lower()
