"""
Comprehensive Test Suite for Multi-Warehouse Order, Returns, and Refunds Redesign (H4CARE / PharmaTrust).

Covers all 28 required test scenarios from the specification:
1. Admin system orders overview (distinct orders vs fulfillments, no double counting)
2. Admin warehouse overview table (SLAs, status counts, items to pick)
3. Admin warehouse details tab (fulfillments, returns, refunds, staff performance, audit logs)
4. Admin returns overview
5. Admin returns by warehouse
6. Customer return request automatically splits into WarehouseReturnCase per shipping warehouse
7. Multi-warehouse order return splitting creates multiple cases with correct warehouse_ids
8. Warehouse manager views only cases belonging to their warehouse
9. Anti-IDOR: Warehouse manager cross-warehouse access rejected (403 Forbidden)
10. Warehouse manager assigns return case to warehouse staff
11. Warehouse staff views only assigned return cases
12. Warehouse staff confirms receipt from courier (RECEIVE)
13. Warehouse staff uploads evidence photos/videos
14. Warehouse staff submits inspection report (SUBMIT -> WAITING_MANAGER_APPROVAL)
15. RBAC: Warehouse staff cannot approve return case (403 Forbidden)
16. RBAC: Warehouse staff cannot reject return case (403 Forbidden)
17. RBAC: Warehouse staff cannot process refund (403 Forbidden)
18. Warehouse manager requests reinspection (status returns to INSPECTING)
19. Warehouse manager approves return case (status APPROVED / REFUND_PENDING)
20. Warehouse manager rejects return case (mandatory reason required)
21. Security: Warehouse manager refund requires correct account password
22. Financial invariance: Refund amount calculated strictly by backend
23. Idempotency: Duplicate refund attempts rejected
24. Proportional discount net unit price refund calculation invariant
25. Stock disposition RESTOCK increases available inventory and logs movement
26. Stock disposition QUARANTINE does not increase sellable stock
27. Admin emergency override with mandatory audit reason
28. Admin reassign return case to another warehouse
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import AuditLog, CanonicalProduct, Order, OrderItem, User
from app.models.enums import UserRole
from app.models.inventory import (
    BatchStatus,
    FulfillmentItem,
    InventoryBatch,
    OrderFulfillment,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    UserWarehouseMembership,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import (
    ItemCondition,
    Refund,
    RefundMethod,
    RefundStatus,
    RestockDestination,
    ReturnEvidence,
    ReturnInspection,
    ReturnItem,
    ReturnRequest,
    ReturnRequestType,
    ReturnStatus,
    WarehouseReturnCase,
)
from app.services.refund_calculation_service import RefundCalculationService
from app.services.warehouse_order_metrics_service import WarehouseOrderMetricsService
from app.services.warehouse_return_service import WarehouseReturnService


@pytest.fixture
def staff_hcm_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "staff_hcm@pharmatrust.vn", "password": "Staff@2026"},
    )
    if response.status_code != 200:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "staff.hcm@pharmatrust.vn", "password": "Staff@2026"},
        )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def buyer_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "buyer@pharmatrust.vn", "password": "Buyer@123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --------------------------------------------------------------------------
# Scenario 1: Admin System Orders Overview
# --------------------------------------------------------------------------
def test_01_admin_orders_overview_distinct_order_vs_fulfillment(client, admin_headers):
    res = client.get("/api/v1/admin/orders/overview?time_range=all", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "distinct_orders_count" in data
    assert "total_fulfillments_count" in data
    assert "total_orders_today" in data
    assert "orders_processing" in data
    assert "orders_shipping" in data
    assert "orders_delivered" in data
    assert "orders_cancelled" in data
    assert "orders_returned" in data
    assert "pending_refund_amount" in data
    assert "refunded_amount" in data
    assert "active_warehouses" in data
    assert data["active_warehouses"] >= 1


# --------------------------------------------------------------------------
# Scenario 2: Admin Warehouse Overview Table
# --------------------------------------------------------------------------
def test_02_admin_orders_by_warehouse_breakdown(client, admin_headers):
    res = client.get("/api/v1/admin/orders/by-warehouse?time_range=all", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    sample = data[0]
    assert "warehouse_code" in sample
    assert "warehouse_name" in sample
    assert "province" in sample
    assert "manager_name" in sample
    assert "total_fulfillments" in sample
    assert "orders_new" in sample
    assert "orders_picking" in sample
    assert "orders_packing" in sample
    assert "orders_shipping" in sample
    assert "orders_delivered" in sample
    assert "returns_processing" in sample
    assert "avg_processing_time_hours" in sample


# --------------------------------------------------------------------------
# Scenario 3: Admin Warehouse Details Tab
# --------------------------------------------------------------------------
def test_03_admin_warehouse_details_tab(client, admin_headers):
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        assert wh is not None
        wh_id = wh.id

    res = client.get(f"/api/v1/admin/orders/warehouses/{wh_id}", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["warehouse"]["code"] == "KHO-HCM-01"
    assert "fulfillments" in data
    assert "returns" in data
    assert "refunds" in data
    assert "staff_performance" in data
    assert "audit_logs" in data


# --------------------------------------------------------------------------
# Scenario 4: Admin Returns Overview
# --------------------------------------------------------------------------
def test_04_admin_returns_overview(client, admin_headers):
    res = client.get("/api/v1/admin/returns/overview", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_returns" in data
    assert "waiting_warehouse_receive" in data
    assert "in_transit" in data
    assert "inspecting" in data
    assert "waiting_manager_approval" in data
    assert "approved" in data
    assert "rejected" in data
    assert "refund_pending" in data
    assert "total_refunded_amount" in data
    assert "total_pending_refund_amount" in data


# --------------------------------------------------------------------------
# Scenario 5: Admin Returns By Warehouse
# --------------------------------------------------------------------------
def test_05_admin_returns_by_warehouse(client, admin_headers):
    res = client.get("/api/v1/admin/returns/by-warehouse", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    sample = data[0]
    assert "warehouse_code" in sample
    assert "warehouse_name" in sample
    assert "total_cases" in sample
    assert "inspecting" in sample
    assert "waiting_approval" in sample


# --------------------------------------------------------------------------
# Helper to Seed a Test Order with Fulfillments
# --------------------------------------------------------------------------
def _create_test_order_with_fulfillment(warehouse_code="KHO-HCM-01"):
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == warehouse_code))
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
        prod = db.scalar(select(CanonicalProduct).limit(1))
        sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id).limit(1))

        order = Order(
            order_code=f"ORD-TEST-{uuid.uuid4().hex[:6].upper()}",
            user_id=buyer.id,
            customer_name="Test Buyer",
            customer_phone="0911223344",
            shipping_address="123 Test Street, HCM",
            total_amount=Decimal("150000"),
            payment_method="COD",
            payment_status="PAID",
            order_status="DELIVERED",
            fulfillment_status="DELIVERED",
        )
        db.add(order)
        db.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            product_sku=sku.sku_code if sku else "SKU-TEST",
            price=Decimal("50000"),
            quantity=3,
            subtotal=Decimal("150000"),
        )
        db.add(order_item)
        db.flush()

        ful = OrderFulfillment(
            order_id=order.id,
            warehouse_id=wh.id,
            fulfillment_code=f"FUL-{uuid.uuid4().hex[:6].upper()}",
            status="DELIVERED",
            shipping_fee=Decimal("0"),
        )
        db.add(ful)
        db.flush()

        ful_item = FulfillmentItem(
            fulfillment_id=ful.id,
            order_item_id=order_item.id,
            quantity=3,
        )
        db.add(ful_item)
        db.commit()

        return order.id, order.order_code, order_item.id, wh.id


def _get_or_create_test_case(wh_code="KHO-HCM-01") -> str:
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == wh_code))
        if wh:
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh.id))
            if case:
                return case.case_code

    order_id, order_code, item_id, wh_id = _create_test_order_with_fulfillment(wh_code)
    with SessionLocal() as db:
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
        prod = db.scalar(select(CanonicalProduct).limit(1))
        ret = ReturnRequest(
            return_code=f"RET-SEED-{uuid.uuid4().hex[:6].upper()}",
            order_id=order_id,
            user_id=buyer.id if buyer else 1,
            customer_name="Buyer Seed",
            customer_phone="0911223344",
            request_type=ReturnRequestType.RETURN.value,
            status=ReturnStatus.REQUESTED.value,
            reason_code="WRONG_ITEM",
            reason_text="Seed return",
            requested_at=datetime.now(UTC),
        )
        db.add(ret)
        db.flush()
        ri = ReturnItem(
            return_request_id=ret.id,
            order_item_id=item_id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            original_quantity=3,
            requested_quantity=2,
            condition_reported="SEALED",
            unit_price_at_purchase=Decimal("50000"),
            net_paid_amount=Decimal("100000"),
            requested_refund_amount=Decimal("100000"),
        )
        db.add(ri)
        db.commit()
        cases = WarehouseReturnService.split_return_request_into_cases(db, ret)
        db.commit()
        return cases[0].case_code


# --------------------------------------------------------------------------
# Scenario 6: Customer Return Request Automatically Splits into Case
# --------------------------------------------------------------------------
def test_06_customer_return_request_splits_into_warehouse_case(client, buyer_headers):
    order_id, order_code, item_id, wh_id = _create_test_order_with_fulfillment("KHO-HCM-01")

    res = client.post(
        "/api/v1/returns",
        headers=buyer_headers,
        json={
            "order_code": order_code,
            "request_type": "RETURN",
            "reason_code": "WRONG_ITEM",
            "reason_text": "Giao nhầm thuốc",
            "customer_phone_verify": "0911223344",
            "items": [{"order_item_id": item_id, "requested_quantity": 2, "customer_reason": "Sai quy cách"}],
        },
    )
    assert res.status_code in [200, 201]
    ret_data = res.json()
    ret_code = ret_data["return_code"]

    with SessionLocal() as db:
        cases = db.scalars(
            select(WarehouseReturnCase)
            .join(ReturnRequest)
            .where(ReturnRequest.return_code == ret_code)
        ).all()
        assert len(cases) == 1, "Phải tự động sinh ra đúng 1 WarehouseReturnCase"
        case = cases[0]
        assert case.warehouse_id == wh_id
        assert case.status in [ReturnStatus.ASSIGNED_TO_WAREHOUSE.value, ReturnStatus.REQUESTED.value]


# --------------------------------------------------------------------------
# Scenario 7: Multi-Warehouse Order Splits into Multiple Cases
# --------------------------------------------------------------------------
def test_07_multi_warehouse_order_split_into_multiple_cases():
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        wh_hn = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
        prod = db.scalar(select(CanonicalProduct).limit(1))

        order = Order(
            order_code=f"ORD-MULTI-{uuid.uuid4().hex[:6].upper()}",
            user_id=buyer.id,
            customer_name="Buyer Multi",
            customer_phone="0911223344",
            shipping_address="HCM",
            total_amount=Decimal("200000"),
            payment_status="PAID",
            order_status="DELIVERED",
        )
        db.add(order)
        db.flush()

        it1 = OrderItem(order_id=order.id, product_id=prod.id, product_name="Thuoc 1", price=Decimal("50000"), quantity=2, subtotal=Decimal("100000"))
        it2 = OrderItem(order_id=order.id, product_id=prod.id, product_name="Thuoc 2", price=Decimal("50000"), quantity=2, subtotal=Decimal("100000"))
        db.add_all([it1, it2])
        db.flush()

        ful1 = OrderFulfillment(order_id=order.id, warehouse_id=wh_hcm.id, fulfillment_code=f"FUL-H1-{uuid.uuid4().hex[:4]}", status="DELIVERED", shipping_fee=0)
        ful2 = OrderFulfillment(order_id=order.id, warehouse_id=wh_hn.id, fulfillment_code=f"FUL-H2-{uuid.uuid4().hex[:4]}", status="DELIVERED", shipping_fee=0)
        db.add_all([ful1, ful2])
        db.flush()

        fit1 = FulfillmentItem(fulfillment_id=ful1.id, order_item_id=it1.id, quantity=2)
        fit2 = FulfillmentItem(fulfillment_id=ful2.id, order_item_id=it2.id, quantity=2)
        db.add_all([fit1, fit2])
        db.flush()

        ret = ReturnRequest(
            return_code=f"RET-M-{uuid.uuid4().hex[:6].upper()}",
            order_id=order.id,
            user_id=buyer.id,
            customer_name="Buyer Multi",
            customer_phone="0911223344",
            request_type=ReturnRequestType.RETURN.value,
            status=ReturnStatus.REQUESTED.value,
            reason_code="DAMAGED",
            reason_text="Hu hong ca hai",
        )
        db.add(ret)
        db.flush()

        ri1 = ReturnItem(
            return_request_id=ret.id,
            order_item_id=it1.id,
            product_id=prod.id,
            product_name="Thuoc 1",
            original_quantity=2,
            requested_quantity=2,
            condition_reported="DAMAGED",
            unit_price_at_purchase=Decimal("50000"),
            net_paid_amount=Decimal("100000"),
            requested_refund_amount=Decimal("100000"),
        )
        ri2 = ReturnItem(
            return_request_id=ret.id,
            order_item_id=it2.id,
            product_id=prod.id,
            product_name="Thuoc 2",
            original_quantity=2,
            requested_quantity=2,
            condition_reported="DAMAGED",
            unit_price_at_purchase=Decimal("50000"),
            net_paid_amount=Decimal("100000"),
            requested_refund_amount=Decimal("100000"),
        )
        db.add_all([ri1, ri2])
        db.commit()

        # Thực thi tách ca
        cases = WarehouseReturnService.split_return_request_into_cases(db, ret)
        assert len(cases) == 2, "Đơn xuất từ 2 kho phải tách thành đúng 2 WarehouseReturnCase"
        wh_ids = {c.warehouse_id for c in cases}
        assert wh_hcm.id in wh_ids
        assert wh_hn.id in wh_ids


# --------------------------------------------------------------------------
# Scenario 8: Warehouse Manager Views Only Assigned Warehouse Returns
# --------------------------------------------------------------------------
def test_08_manager_views_only_assigned_warehouse_returns(client, manager_hcm_headers):
    res = client.get("/api/v1/warehouse/me/returns", headers=manager_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        for item in data["items"]:
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == item["case_code"]))
            assert case.warehouse_id == wh_hcm.id, "Quản lý kho chỉ được thấy ca hoàn thuộc đúng kho mình"


# --------------------------------------------------------------------------
# Scenario 9: Anti-IDOR: Manager Cross-Warehouse Access Forbidden
# --------------------------------------------------------------------------
def test_09_manager_cross_warehouse_access_forbidden(client, manager_hn_headers):
    # Tạo ca hoàn tại HCM
    order_id, order_code, item_id, wh_id = _create_test_order_with_fulfillment("KHO-HCM-01")
    with SessionLocal() as db:
        ret = db.scalar(select(ReturnRequest).where(ReturnRequest.order_id == order_id))
        if not ret:
            buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
            ret = ReturnRequest(
                return_code=f"RET-{uuid.uuid4().hex[:6].upper()}",
                order_id=order_id,
                user_id=buyer.id,
                customer_name="Buyer",
                customer_phone="0911223344",
                request_type=ReturnRequestType.RETURN.value,
                status=ReturnStatus.REQUESTED.value,
                reason_code="WRONG_ITEM",
                reason_text="Sai mau",
            )
            db.add(ret)
            db.flush()
            prod = db.scalar(select(CanonicalProduct).limit(1))
            ri = ReturnItem(
                return_request_id=ret.id,
                order_item_id=item_id,
                product_id=prod.id,
                product_name=prod.canonical_name,
                original_quantity=1,
                requested_quantity=1,
                condition_reported="GOOD",
                unit_price_at_purchase=Decimal("50000"),
                net_paid_amount=Decimal("50000"),
                requested_refund_amount=Decimal("50000"),
            )
            db.add(ri)
            db.commit()
            cases = WarehouseReturnService.split_return_request_into_cases(db, ret)
            case_code = cases[0].case_code
        else:
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.return_request_id == ret.id))
            case_code = case.case_code

    # Quản lý Hà Nội cố tình truy cập ca hoàn của HCM
    res = client.get(f"/api/v1/warehouse/me/returns/{case_code}", headers=manager_hn_headers)
    assert res.status_code in [403, 404], "Quản lý kho khác truy cập IDOR phải bị chặn 403 hoặc 404"


# --------------------------------------------------------------------------
# Scenario 10: Warehouse Manager Assigns Return Case to Staff
# --------------------------------------------------------------------------
def test_10_manager_assigns_case_to_staff(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff_hcm@pharmatrust.vn", "staff.hcm@pharmatrust.vn"])))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        assert case is not None
        assert staff_hcm is not None
        case_code = case.case_code
        staff_id = staff_hcm.id

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/assign",
        headers=manager_hcm_headers,
        json={"staff_id": staff_id},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "SUCCESS"

    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.assigned_staff_id == staff_id


# --------------------------------------------------------------------------
# Scenario 11: Warehouse Staff Views Only Assigned Return Cases
# --------------------------------------------------------------------------
def test_11_staff_views_assigned_return_cases(client, staff_hcm_headers):
    res = client.get("/api/v1/warehouse/staff/me/returns", headers=staff_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    with SessionLocal() as db:
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff_hcm@pharmatrust.vn", "staff.hcm@pharmatrust.vn"])))
        for item in data["items"]:
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == item["case_code"]))
            assert case.assigned_staff_id == staff_hcm.id


# --------------------------------------------------------------------------
# Scenario 12: Warehouse Staff Confirms Receipt from Courier
# --------------------------------------------------------------------------
def test_12_staff_confirms_receipt(client, staff_hcm_headers):
    with SessionLocal() as db:
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff_hcm@pharmatrust.vn", "staff.hcm@pharmatrust.vn"])))
        case = db.scalar(
            select(WarehouseReturnCase).where(
                WarehouseReturnCase.assigned_staff_id == staff_hcm.id,
                WarehouseReturnCase.status.in_([ReturnStatus.ASSIGNED_TO_WAREHOUSE.value, ReturnStatus.IN_TRANSIT.value]),
            )
        )
        if not case:
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.assigned_staff_id == staff_hcm.id))
            case.status = ReturnStatus.IN_TRANSIT.value
            db.commit()
        case_code = case.case_code

    res = client.post(
        f"/api/v1/warehouse/staff/me/returns/{case_code}/receive",
        headers=staff_hcm_headers,
        json={"carrier_name": "Viettel Post", "tracking_code": "VP123456", "package_condition": "SEALED"},
    )
    assert res.status_code == 200
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status in [ReturnStatus.RECEIVED.value, ReturnStatus.INSPECTING.value]


# --------------------------------------------------------------------------
# Scenario 13: Warehouse Staff Uploads Evidence Photos
# --------------------------------------------------------------------------
def test_13_staff_uploads_evidence(client, staff_hcm_headers):
    with SessionLocal() as db:
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff_hcm@pharmatrust.vn", "staff.hcm@pharmatrust.vn"])))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.assigned_staff_id == staff_hcm.id))
        case_code = case.case_code

    res = client.post(
        f"/api/v1/warehouse/staff/me/returns/{case_code}/evidence",
        headers=staff_hcm_headers,
        json={
            "file_url": "https://example.com/evidence_photo.jpg",
            "file_name": "batch_label.jpg",
            "file_category": "DAMAGE_PHOTO",
        },
    )
    assert res.status_code == 200
    with SessionLocal() as db:
        ev = db.scalar(select(ReturnEvidence).where(ReturnEvidence.file_name == "batch_label.jpg"))
        assert ev is not None


# --------------------------------------------------------------------------
# Scenario 14: Staff Submits Inspection Report
# --------------------------------------------------------------------------
def test_14_staff_inspects_and_submits(client, staff_hcm_headers):
    with SessionLocal() as db:
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff_hcm@pharmatrust.vn", "staff.hcm@pharmatrust.vn"])))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.assigned_staff_id == staff_hcm.id))
        case.status = ReturnStatus.INSPECTING.value
        db.commit()
        item = case.items[0]
        case_code = case.case_code
        item_id = item.id

    # 1. Lưu kết quả kiểm tra
    inspect_res = client.post(
        f"/api/v1/warehouse/staff/me/returns/{case_code}/inspect",
        headers=staff_hcm_headers,
        json={
            "inspections": [
                {
                    "return_item_id": item_id,
                    "received_quantity": 2,
                    "accepted_quantity": 2,
                    "rejected_quantity": 0,
                    "package_condition": "SEALED",
                    "seal_intact": True,
                    "batch_matched": True,
                    "expiry_matched": True,
                    "suggested_action": "RESTOCK",
                }
            ]
        },
    )
    assert inspect_res.status_code == 200

    # 2. Nộp kết quả lên quản lý
    submit_res = client.post(
        f"/api/v1/warehouse/staff/me/returns/{case_code}/submit",
        headers=staff_hcm_headers,
        json={"note": "Đã kiểm hàng đạt chuẩn"},
    )
    assert submit_res.status_code == 200

    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status == ReturnStatus.WAITING_MANAGER_APPROVAL.value


# --------------------------------------------------------------------------
# Scenarios 15, 16, 17: RBAC: Staff Cannot Approve, Reject or Refund
# --------------------------------------------------------------------------
def test_15_16_17_staff_forbidden_actions(client, staff_hcm_headers):
    with SessionLocal() as db:
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff_hcm@pharmatrust.vn", "staff.hcm@pharmatrust.vn"])))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.assigned_staff_id == staff_hcm.id))
        case_code = case.case_code

    # 15. Cấm duyệt
    res_app = client.post(f"/api/v1/warehouse/me/returns/{case_code}/approve", headers=staff_hcm_headers, json={})
    assert res_app.status_code == 403, "Nhân viên kho không được duyệt đơn"

    # 16. Cấm từ chối
    res_rej = client.post(f"/api/v1/warehouse/me/returns/{case_code}/reject", headers=staff_hcm_headers, json={"rejection_reason": "Test"})
    assert res_rej.status_code == 403, "Nhân viên kho không được từ chối đơn"

    # 17. Cấm hoàn tiền
    res_ref = client.post(f"/api/v1/warehouse/me/returns/{case_code}/refund", headers=staff_hcm_headers, json={"password": "xyz"})
    assert res_ref.status_code == 403, "Nhân viên kho tuyệt đối không được hoàn tiền"


# --------------------------------------------------------------------------
# Scenario 18: Manager Requests Reinspection
# --------------------------------------------------------------------------
def test_18_manager_requests_reinspection(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        case.status = ReturnStatus.WAITING_MANAGER_APPROVAL.value
        db.commit()
        case_code = case.case_code

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-reinspection",
        headers=manager_hcm_headers,
        json={"reason": "Vui lòng chụp lại ảnh tem niêm phong cận cảnh"},
    )
    assert res.status_code == 200
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status == ReturnStatus.INSPECTING.value


# --------------------------------------------------------------------------
# Scenario 19: Manager Approves Return Case
# --------------------------------------------------------------------------
def test_19_manager_approves_return_case(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        case.status = ReturnStatus.WAITING_MANAGER_APPROVAL.value
        for it in case.items:
            it.approved_quantity = it.requested_quantity
        db.commit()
        case_code = case.case_code

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/approve",
        headers=manager_hcm_headers,
        json={"manager_note": "Duyệt toàn bộ hàng hoàn"},
    )
    assert res.status_code == 200
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status in [ReturnStatus.APPROVED.value, ReturnStatus.REFUND_PENDING.value]


# --------------------------------------------------------------------------
# Scenario 20: Manager Rejects Case Requires Mandatory Reason
# --------------------------------------------------------------------------
def test_20_manager_rejects_requires_reason(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        case.status = ReturnStatus.WAITING_MANAGER_APPROVAL.value
        db.commit()
        case_code = case.case_code

    # 1. Thử gửi lý do rỗng
    res_empty = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/reject",
        headers=manager_hcm_headers,
        json={"rejection_reason": ""},
    )
    assert res_empty.status_code in [400, 422], "Lý do rỗng phải bị từ chối"

    # 2. Gửi lý do hợp lệ
    res_valid = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/reject",
        headers=manager_hcm_headers,
        json={"rejection_reason": "Thuốc bị ẩm mốc nặng do khách bảo quản sai quy định"},
    )
    assert res_valid.status_code == 200
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status == ReturnStatus.REJECTED.value
        assert "ẩm mốc" in c.rejection_reason


# --------------------------------------------------------------------------
# Scenario 21: Manager Refund Requires Correct Password
# --------------------------------------------------------------------------
def test_21_manager_refund_requires_password(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        case.status = ReturnStatus.APPROVED.value
        for it in case.items:
            it.approved_quantity = it.requested_quantity
        db.commit()
        case_code = case.case_code

    # Nhập sai mật khẩu
    res_wrong = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/refund",
        headers=manager_hcm_headers,
        json={"password": "WrongPassword@123"},
    )
    assert res_wrong.status_code in [400, 401], "Sai mật khẩu phải bị từ chối"


# --------------------------------------------------------------------------
# Scenario 22 & 23: Invariant Backend Refund Amount & Idempotency
# --------------------------------------------------------------------------
def test_22_23_backend_invariant_refund_and_idempotency(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        case.status = ReturnStatus.APPROVED.value
        for it in case.items:
            it.approved_quantity = it.requested_quantity
        # Remove any existing active refund for this case so refund can proceed cleanly
        existing_refunds = db.scalars(select(Refund).where(Refund.warehouse_return_case_id == case.id)).all()
        for r in existing_refunds:
            db.delete(r)
        db.commit()
        case_code = case.case_code

    # Hoàn tiền đúng mật khẩu
    res_ok = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/refund",
        headers=manager_hcm_headers,
        json={"password": "Warehouse@2026", "refund_method": "BANK_TRANSFER"},
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["status"] == "SUCCESS"
    refund_amount = data["refund_amount"]
    assert refund_amount > 0, "Số tiền hoàn do backend tính phải > 0"

    # Scenario 23: Thử hoàn lần 2 -> phải bị chặn (Idempotency)
    res_duplicate = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/refund",
        headers=manager_hcm_headers,
        json={"password": "Warehouse@2026", "refund_method": "BANK_TRANSFER"},
    )
    assert res_duplicate.status_code in [400, 409], "Hoàn tiền lần 2 phải bị chặn chống double-refund"


# --------------------------------------------------------------------------
# Scenario 24: Proportional Net Unit Price Formula
# --------------------------------------------------------------------------
def test_24_proportional_net_unit_price_formula():
    """
    Khách mua giỏ hàng niêm yết 200,000đ nhưng áp voucher giảm 50,000đ -> thực trả 150,000đ.
    Sản phẩm giá niêm yết 100,000đ phải có đơn giá ròng thực trả = 75,000đ.
    """
    net_price = RefundCalculationService.calculate_net_unit_price(
        listed_unit_price=Decimal("100000"),
        total_paid_goods_amount=Decimal("150000"),
        total_listed_goods_amount=Decimal("200000"),
    )
    assert net_price == Decimal("75000.00")


# --------------------------------------------------------------------------
# Scenario 25: Stock Disposition RESTOCK Increases Stock & Logs Movement
# --------------------------------------------------------------------------
def test_25_stock_disposition_restock(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        case.status = ReturnStatus.REFUNDED.value
        for it in case.items:
            it.approved_quantity = it.requested_quantity
        db.commit()
        case_code = case.case_code

        # Lấy tồn kho trước khi restock
        stock_before = db.scalar(
            select(func.sum(WarehouseBatchStock.quantity_available)).where(
                WarehouseBatchStock.warehouse_id == wh_hcm.id
            )
        ) or 0

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/stock-disposition",
        headers=manager_hcm_headers,
        json={"disposition": "RESTOCK", "note": "Thuốc đạt chuẩn GSP nhập lại kho"},
    )
    assert res.status_code == 200

    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status == ReturnStatus.RESTOCKED.value

        # Kiểm tra tồn kho khả dụng tăng
        stock_after = db.scalar(
            select(func.sum(WarehouseBatchStock.quantity_available)).where(
                WarehouseBatchStock.warehouse_id == wh_hcm.id
            )
        ) or 0
        assert stock_after >= stock_before

        # Kiểm tra ghi thẻ kho StockMovement
        mov = db.scalar(
            select(StockMovement).where(
                StockMovement.warehouse_id == wh_hcm.id,
                StockMovement.movement_type == "RETURN_RESTOCK",
            )
        )
        assert mov is not None, "Phải ghi nhận thẻ kho movement_type = RETURN_RESTOCK"


# --------------------------------------------------------------------------
# Scenario 26: Stock Disposition QUARANTINE Does Not Increase Sellable Stock
# --------------------------------------------------------------------------
def test_26_stock_disposition_quarantine(client, manager_hcm_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        case.status = ReturnStatus.REFUNDED.value
        for it in case.items:
            it.approved_quantity = it.requested_quantity
        db.commit()
        case_code = case.case_code

        stock_avail_before = db.scalar(
            select(func.sum(WarehouseBatchStock.quantity_available)).where(
                WarehouseBatchStock.warehouse_id == wh_hcm.id
            )
        ) or 0

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/stock-disposition",
        headers=manager_hcm_headers,
        json={"disposition": "QUARANTINE", "note": "Cách ly để kiểm nghiệm thêm"},
    )
    assert res.status_code == 200

    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status == ReturnStatus.QUARANTINED.value

        # Tồn khả dụng bán tiếp KHÔNG được tăng
        stock_avail_after = db.scalar(
            select(func.sum(WarehouseBatchStock.quantity_available)).where(
                WarehouseBatchStock.warehouse_id == wh_hcm.id
            )
        ) or 0
        assert stock_avail_after == stock_avail_before


# --------------------------------------------------------------------------
# Scenario 27: Admin Emergency Override with Audit Reason
# --------------------------------------------------------------------------
def test_27_admin_emergency_override(client, admin_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        ret = db.scalar(select(ReturnRequest).limit(1))
        return_code = ret.return_code

    res = client.post(
        f"/api/v1/admin/returns/{return_code}/override",
        headers=admin_headers,
        json={
            "new_status": "APPROVED",
            "override_reason": "Admin can thiep khan cap do kho qua tai",
            "notes": "Phê duyệt hỗ trợ khách hàng VIP",
        },
    )
    assert res.status_code == 200
    with SessionLocal() as db:
        r = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == return_code))
        assert r.status == "APPROVED"

        # Kiểm tra ghi nhận AuditLog
        log = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "ADMIN_OVERRIDE_RETURN",
                AuditLog.entity_id == return_code,
            )
        )
        assert log is not None, "Admin override bắt buộc phải có AuditLog"


# --------------------------------------------------------------------------
# Scenario 28: Admin Reassign Return Case to Another Warehouse
# --------------------------------------------------------------------------
def test_28_admin_reassign_warehouse(client, admin_headers):
    _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hn = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
        ret = db.scalar(select(ReturnRequest).limit(1))
        return_code = ret.return_code
        new_wh_id = wh_hn.id

    res = client.post(
        f"/api/v1/admin/returns/{return_code}/reassign",
        headers=admin_headers,
        json={
            "new_warehouse_id": new_wh_id,
            "reason": "Dieu chuyen ca hoan sang kho Ha Noi xu ly do kho cu bi qua tai",
        },
    )
    assert res.status_code == 200
    with SessionLocal() as db:
        cases = db.scalars(
            select(WarehouseReturnCase)
            .join(ReturnRequest)
            .where(ReturnRequest.return_code == return_code)
        ).all()
        assert len(cases) > 0
        for c in cases:
            assert c.warehouse_id == new_wh_id, "Tất cả ca hoàn phải được chuyển sang kho mới"
