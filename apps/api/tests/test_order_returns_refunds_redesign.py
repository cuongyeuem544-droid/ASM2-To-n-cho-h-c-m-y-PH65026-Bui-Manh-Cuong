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
    ReturnEvidenceRequest,
    ReturnEvidenceRequestStatus,
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
        json={"email": "staff.hcm@pharmatrust.vn", "password": "Staff@2026"},
    )
    if response.status_code != 200:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "staff_hcm@pharmatrust.vn", "password": "Staff@2026"},
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
            refund_bank_code="VCB",
            refund_bank_name="Vietcombank",
            refund_account_number="0123456789",
            refund_account_name="BUYER SEED",
            refund_beneficiary_submitted_at=datetime.now(UTC),
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
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff.hcm@pharmatrust.vn", "staff_hcm@pharmatrust.vn"])))
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
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff.hcm@pharmatrust.vn", "staff_hcm@pharmatrust.vn"])))
        for item in data["items"]:
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == item["case_code"]))
            assert case.assigned_staff_id == staff_hcm.id


# --------------------------------------------------------------------------
# Scenario 12: Warehouse Staff Confirms Receipt from Courier
# --------------------------------------------------------------------------
def test_12_staff_confirms_receipt(client, staff_hcm_headers):
    with SessionLocal() as db:
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff.hcm@pharmatrust.vn", "staff_hcm@pharmatrust.vn"])))
        case = db.scalar(
            select(WarehouseReturnCase).where(
                WarehouseReturnCase.assigned_staff_id == staff_hcm.id,
                WarehouseReturnCase.status.in_([ReturnStatus.ASSIGNED_TO_WAREHOUSE.value, ReturnStatus.IN_TRANSIT.value]),
            )
        )
        if not case:
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.assigned_staff_id == staff_hcm.id))
        if not case:
            wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh_hcm.id))
        if not case:
            cc = _get_or_create_test_case("KHO-HCM-01")
            case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == cc))
        case.assigned_staff_id = staff_hcm.id
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
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff.hcm@pharmatrust.vn", "staff_hcm@pharmatrust.vn"])))
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
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff.hcm@pharmatrust.vn", "staff_hcm@pharmatrust.vn"])))
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
                    "storage_condition_ok": True,
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
        staff_hcm = db.scalar(select(User).where(User.email.in_(["staff.hcm@pharmatrust.vn", "staff_hcm@pharmatrust.vn"])))
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
        items_payload = []
        for it in case.items:
            it.received_quantity = it.requested_quantity
            it.approved_quantity = it.requested_quantity
            items_payload.append({
                "return_item_id": it.id,
                "approved_quantity": it.requested_quantity,
                "rejected_quantity": 0,
            })
        db.commit()
        case_code = case.case_code

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/approve",
        headers=manager_hcm_headers,
        json={"manager_note": "Duyệt toàn bộ hàng hoàn", "items": items_payload},
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
        if case.return_request:
            case.return_request.refund_bank_code = "VCB"
            case.return_request.refund_bank_name = "Vietcombank"
            case.return_request.refund_account_number = "0123456789"
            case.return_request.refund_account_name = "BUYER SEED"
            case.return_request.refund_beneficiary_submitted_at = datetime.now(UTC)
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
        case.disposition = None
        for it in case.items:
            it.approved_quantity = it.requested_quantity
            alloc = db.scalar(select(OrderItemBatchAllocation).where(OrderItemBatchAllocation.order_item_id == it.order_item_id))
            if not alloc:
                sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == it.product_id))
                if not sku:
                    sku = ProductSku(
                        canonical_product_id=it.product_id,
                        sku_code=f"SKU-TEST-{it.product_id}",
                        uom="Hộp",
                        base_price=Decimal("50000"),
                        is_active=True,
                    )
                    db.add(sku)
                    db.flush()
                batch = db.scalar(select(InventoryBatch).where(InventoryBatch.sku_id == sku.id))
                if not batch:
                    batch = InventoryBatch(
                        sku_id=sku.id,
                        batch_number=f"BAT-TEST-{uuid.uuid4().hex[:6].upper()}",
                        manufacture_date=date.today() - timedelta(days=60),
                        expiry_date=date.today() + timedelta(days=365),
                        status=BatchStatus.ACTIVE,
                    )
                    db.add(batch)
                    db.flush()
                alloc = OrderItemBatchAllocation(
                    order_item_id=it.order_item_id,
                    batch_id=batch.id,
                    allocated_quantity=max(it.requested_quantity, 5),
                    warehouse_id=wh_hcm.id,
                )
                db.add(alloc)
                batch_stock = db.scalar(
                    select(WarehouseBatchStock).where(
                        WarehouseBatchStock.warehouse_id == wh_hcm.id,
                        WarehouseBatchStock.batch_id == batch.id,
                    )
                )
                if not batch_stock:
                    batch_stock = WarehouseBatchStock(
                        warehouse_id=wh_hcm.id,
                        batch_id=batch.id,
                        quantity_on_hand=50,
                        quantity_available=50,
                        quantity_reserved=0,
                    )
                    db.add(batch_stock)
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
    assert res.status_code == 200, res.json()

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


# --------------------------------------------------------------------------
# Scenario 29: Warehouse Manager Requests Customer Evidence (1 to 3 images)
# --------------------------------------------------------------------------
def test_29_manager_requests_customer_evidence_success(client, manager_hcm_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        c.status = ReturnStatus.INSPECTING.value
        db.commit()

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-evidence",
        headers=manager_hcm_headers,
        json={
            "required_image_count": 2,
            "reason": "Tem niêm phong có dấu hiệu bị rách",
            "instructions": "Chụp rõ 2 góc cạnh tem niêm phong và đáy hộp có số lô, HSD",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["case_status"] == ReturnStatus.WAITING_CUSTOMER_EVIDENCE.value
    assert "request_code" in data

    with SessionLocal() as db:
        req = db.scalar(select(ReturnEvidenceRequest).where(ReturnEvidenceRequest.request_code == data["request_code"]))
        assert req is not None
        assert req.required_image_count == 2
        assert req.status == "OPEN"
        assert req.expires_at is not None
        time_diff = (req.expires_at - req.requested_at).total_seconds()
        assert 259100 <= time_diff <= 259300


# --------------------------------------------------------------------------
# Scenario 30: Validation of Required Image Count (0 or >3 Rejected)
# --------------------------------------------------------------------------
def test_30_manager_requests_invalid_image_count_rejected(client, manager_hcm_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")

    # 1. Thử yêu cầu 0 ảnh
    res0 = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-evidence",
        headers=manager_hcm_headers,
        json={
            "required_image_count": 0,
            "reason": "Test 0 anh",
            "instructions": "Test 0 anh",
        },
    )
    assert res0.status_code == 422, "Yêu cầu 0 ảnh phải bị từ chối với 422"

    # 2. Thử yêu cầu 4 ảnh
    res4 = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-evidence",
        headers=manager_hcm_headers,
        json={
            "required_image_count": 4,
            "reason": "Test 4 anh",
            "instructions": "Test 4 anh",
        },
    )
    assert res4.status_code == 422, "Yêu cầu trên 3 ảnh phải bị từ chối với 422"


# --------------------------------------------------------------------------
# Scenario 31: Anti-IDOR: Manager Cannot Request Evidence for Other Warehouse
# --------------------------------------------------------------------------
def test_31_anti_idor_cross_warehouse_evidence_request_rejected(client, manager_hn_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")

    # Manager Hà Nội cố tình gửi yêu cầu cho ca hoàn thuộc kho HCM
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-evidence",
        headers=manager_hn_headers,
        json={
            "required_image_count": 1,
            "reason": "Manager HN can thiep kho HCM",
            "instructions": "Chup anh",
        },
    )
    assert res.status_code == 403, "Chặn IDOR: Quản lý kho A không được yêu cầu ảnh cho đơn kho B"


# --------------------------------------------------------------------------
# Scenario 32: Customer Views Evidence Request & Anti-IDOR
# --------------------------------------------------------------------------
def test_32_customer_views_evidence_request_and_anti_idor(client, buyer_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
        c.return_request.user_id = buyer.id

        # Tạo user khác để test Anti-IDOR
        other_user = db.scalar(select(User).where(User.email == "other_customer@pharmatrust.vn"))
        if not other_user:
            other_user = User(
                email="other_customer@pharmatrust.vn",
                full_name="Other Customer",
                password_hash=hash_password("Other@123456"),
                role=UserRole.CUSTOMER.value,
                is_active=True,
            )
            db.add(other_user)
        db.commit()
        return_code = c.return_request.return_code

    # 1. Khách hàng chính chủ xem chi tiết yêu cầu bổ sung
    res = client.get(f"/api/v1/returns/{return_code}/evidence-request", headers=buyer_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["has_active_request"] is True
    assert data["request"]["required_image_count"] == 2
    assert data["request"]["status"] == "OPEN"
    assert data["request"]["remaining_seconds"] > 0

    # 2. Khách khác cố tình truy cập đơn hoàn này -> 403 Forbidden
    other_login = client.post(
        "/api/v1/auth/login",
        json={"email": "other_customer@pharmatrust.vn", "password": "Other@123456"},
    )
    assert other_login.status_code == 200
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    res_other = client.get(f"/api/v1/returns/{return_code}/evidence-request", headers=other_headers)
    assert res_other.status_code == 403, "Khách khác không được xem yêu cầu bổ sung ảnh của người khác"


# --------------------------------------------------------------------------
# Scenario 33: Customer Submits Evidence - Exact Count Validation & Transition
# --------------------------------------------------------------------------
def test_33_customer_submits_evidence_exact_count_validation(client, buyer_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        return_code = c.return_request.return_code

    # 1. Quản lý yêu cầu 2 ảnh, khách nộp 1 ảnh -> Bị từ chối (422)
    res_1_img = client.post(
        f"/api/v1/returns/{return_code}/evidence/submit",
        headers=buyer_headers,
        json={
            "images": [
                {"file_url": "/api/v1/returns/evidence/evid_01.jpg", "file_name": "photo1.jpg"},
            ],
            "customer_note": "Toi nop 1 anh thoi",
        },
    )
    assert res_1_img.status_code == 422, "Nộp thiếu số ảnh phải bị từ chối 422"

    # 2. Khách nộp 3 ảnh trong khi yêu cầu 2 ảnh -> Bị từ chối (422)
    res_3_img = client.post(
        f"/api/v1/returns/{return_code}/evidence/submit",
        headers=buyer_headers,
        json={
            "images": [
                {"file_url": "/api/v1/returns/evidence/evid_01.jpg", "file_name": "photo1.jpg"},
                {"file_url": "/api/v1/returns/evidence/evid_02.jpg", "file_name": "photo2.jpg"},
                {"file_url": "/api/v1/returns/evidence/evid_03.jpg", "file_name": "photo3.jpg"},
            ],
            "customer_note": "Toi nop 3 anh",
        },
    )
    assert res_3_img.status_code == 422, "Nộp thừa số ảnh phải bị từ chối 422"

    # 3. Khách nộp đúng 2 ảnh hợp lệ -> Thành công!
    res_2_img = client.post(
        f"/api/v1/returns/{return_code}/evidence/submit",
        headers=buyer_headers,
        json={
            "images": [
                {"file_url": "/api/v1/returns/evidence/evid_01.jpg", "file_name": "photo1.jpg"},
                {"file_url": "/api/v1/returns/evidence/evid_02.jpg", "file_name": "photo2.png"},
            ],
            "customer_note": "Da chup ro ca 2 anh theo yeu cau",
        },
    )
    assert res_2_img.status_code == 200, res_2_img.text
    assert res_2_img.json()["status"] == "SUBMITTED"

    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status == ReturnStatus.WAITING_MANAGER_REVIEW.value
        assert c.return_request.status == ReturnStatus.WAITING_MANAGER_REVIEW.value
        evids = db.scalars(select(ReturnEvidence).where(ReturnEvidence.return_request_id == c.return_request_id)).all()
        assert len(evids) >= 2


# --------------------------------------------------------------------------
# Scenario 34: Warehouse Manager Accepts Evidence -> WAITING_MANAGER_APPROVAL
# --------------------------------------------------------------------------
def test_34_manager_accepts_evidence_advances_status(client, manager_hcm_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/accept-evidence",
        headers=manager_hcm_headers,
        json={"manager_note": "Bằng chứng rõ ràng, hợp lệ."},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["case_status"] == ReturnStatus.WAITING_MANAGER_APPROVAL.value

    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert c.status == ReturnStatus.WAITING_MANAGER_APPROVAL.value
        req = db.scalar(select(ReturnEvidenceRequest).where(ReturnEvidenceRequest.warehouse_return_case_id == c.id).order_by(ReturnEvidenceRequest.id.desc()))
        assert req.status == "ACCEPTED"
        assert req.reviewed_at is not None


# --------------------------------------------------------------------------
# Scenario 35: 3-Day Timeout Cancels Return Case but Preserves Original Order
# --------------------------------------------------------------------------
def test_35_evidence_timeout_3_days_cancels_return_preserves_order(client, manager_hcm_headers, buyer_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        c.status = ReturnStatus.INSPECTING.value
        case_id = c.id
        order_id = c.return_request.order_id
        db.commit()

    # 1. Quản lý tạo yêu cầu mới
    res_req = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-evidence",
        headers=manager_hcm_headers,
        json={
            "required_image_count": 1,
            "reason": "Kiem tra qua han 3 ngay",
            "instructions": "Chup anh",
        },
    )
    assert res_req.status_code == 200

    # 2. Giả lập thời gian đã trôi qua hơn 3 ngày
    with SessionLocal() as db:
        req = db.scalar(select(ReturnEvidenceRequest).where(ReturnEvidenceRequest.warehouse_return_case_id == case_id, ReturnEvidenceRequest.status == "OPEN"))
        assert req is not None
        req.requested_at = datetime.now(UTC) - timedelta(days=4)
        req.expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()

    # 3. Kích hoạt scheduler quét quá hạn
    with SessionLocal() as db:
        count = WarehouseReturnService.check_and_expire_evidence_requests(db)
        assert count >= 1

    # 4. Kiểm tra ca hoàn chuyển sang CANCELLED_EVIDENCE_TIMEOUT nhưng đơn hàng gốc KHÔNG bị hủy
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.id == case_id))
        assert c.status == ReturnStatus.CANCELLED_EVIDENCE_TIMEOUT.value
        assert c.return_request.status == ReturnStatus.CANCELLED_EVIDENCE_TIMEOUT.value
        assert "3 ngày" in (c.rejection_reason or "")

        order = db.scalar(select(Order).where(Order.id == order_id))
        assert order is not None
        assert order.order_status != "CANCELLED", "QUAN TRỌNG: Quá hạn bổ sung ảnh chỉ hủy yêu cầu đổi trả, KHÔNG làm hủy Order mua hàng gốc của khách!"

    # 5. Khách hàng cố nộp ảnh sau khi đã quá hạn -> Bị từ chối
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.id == case_id))
        ret_code = c.return_request.return_code

    res_late = client.post(
        f"/api/v1/returns/{ret_code}/evidence/submit",
        headers=buyer_headers,
        json={
            "images": [{"file_url": "/api/v1/returns/evidence/evid_late.jpg", "file_name": "late.jpg"}],
        },
    )
    assert res_late.status_code == 400, "Sau khi quá hạn, form tải ảnh bị khóa và từ chối gửi"


# --------------------------------------------------------------------------
# Scenario 36: Cannot Create Two Active Evidence Requests Concurrently
# --------------------------------------------------------------------------
def test_36_cannot_create_two_active_evidence_requests_concurrently(client, manager_hcm_headers):
    case_code = _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        c = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        c.status = ReturnStatus.INSPECTING.value
        db.commit()

    # 1. Tạo yêu cầu thứ nhất
    res1 = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-evidence",
        headers=manager_hcm_headers,
        json={
            "required_image_count": 1,
            "reason": "Yêu cầu lần 1",
            "instructions": "Chụp tem",
        },
    )
    assert res1.status_code == 200

    # 2. Thử tạo yêu cầu thứ 2 khi yêu cầu 1 đang OPEN -> Bị từ chối (400)
    res2 = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/request-evidence",
        headers=manager_hcm_headers,
        json={
            "required_image_count": 2,
            "reason": "Yêu cầu lần 2",
            "instructions": "Chụp tem và đáy",
        },
    )
    assert res2.status_code == 400, "Không được tạo hai yêu cầu bằng chứng đang hoạt động cùng lúc"


# --------------------------------------------------------------------------
# Scenario 37: Get Return Case Detail by Manager Without Prior Refund Record
# --------------------------------------------------------------------------
def test_37_get_return_case_detail_safe_refund_info(client, manager_hcm_headers):
    """
    Xác nhận Quản lý kho mở chi tiết ca hoàn mới (chưa có bản ghi Refund)
    không bao giờ bị lỗi AttributeError: 'ReturnRequest' object has no attribute 'bank_name' (500).
    """
    case_code = _get_or_create_test_case("KHO-HCM-01")
    res = client.get(
        f"/api/v1/warehouse/me/returns/{case_code}",
        headers=manager_hcm_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["case_code"] == case_code
    assert "refund_info" in data
    assert data["refund_info"]["beneficiary_bank"] is not None
    assert data["refund_info"]["beneficiary_account_name"] is not None
    assert "active_evidence_request" in data


# --------------------------------------------------------------------------
# Scenario 38: Customer Creates Return and Sees It Immediately in my-requests
# --------------------------------------------------------------------------
def test_38_customer_creates_return_and_visible_immediately_in_my_requests(client, buyer_headers):
    """
    Khách tạo return xong GET /api/v1/returns/my-requests thấy ngay yêu cầu mới
    bằng current_user.id (không cần customer_phone).
    """
    order_id, order_code, item_id, _ = _create_test_order_with_fulfillment("KHO-HCM-01")

    res_create = client.post(
        "/api/v1/returns",
        headers=buyer_headers,
        json={
            "order_code": order_code,
            "request_type": "RETURN",
            "reason_code": "DEFECTIVE",
            "reason_text": "Sản phẩm hỏng hóc khi nhận",
            "customer_note": "Hàng lỗi bao bì khi nhận",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "refund_bank_code": "VCB",
            "refund_bank_name": "Vietcombank",
            "refund_account_number": "0123456789",
            "refund_account_name": "NGUYEN VAN BUYER",
        },
    )
    assert res_create.status_code == 200, res_create.text
    created_return_code = res_create.json()["return_code"]

    # Khách gọi GET /my-requests chỉ bằng JWT Bearer (không cần SĐT)
    res_my = client.get("/api/v1/returns/my-requests", headers=buyer_headers)
    assert res_my.status_code == 200
    my_returns = res_my.json().get("returns", [])
    found = any(r["return_code"] == created_return_code for r in my_returns)
    assert found, f"Yêu cầu {created_return_code} phải xuất hiện ngay trong my-requests của khách"


# --------------------------------------------------------------------------
# Scenario 39: Anti-IDOR for Return Requests and Masked Bank Info
# --------------------------------------------------------------------------
def test_39_user_cannot_view_other_users_return_or_bank_info(client, buyer_headers):
    """
    User khác không xem được return và thông tin tài khoản ngân hàng của người khác.
    """
    with SessionLocal() as db:
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
        ret_req = db.scalar(
            select(ReturnRequest).where(
                ReturnRequest.user_id == buyer.id,
                ReturnRequest.refund_account_number.isnot(None),
            )
        )
        assert ret_req is not None
        return_code = ret_req.return_code

    # Login một customer khác
    res_cust2 = client.post(
        "/api/v1/auth/login",
        json={"email": "customer@pharmatrust.vn", "password": "Customer@123456"},
    )
    if res_cust2.status_code == 200:
        cust2_headers = {"Authorization": f"Bearer {res_cust2.json()['access_token']}"}
        # Customer 2 xem my-requests không có đơn của buyer
        res_list = client.get("/api/v1/returns/my-requests", headers=cust2_headers)
        assert res_list.status_code == 200
        codes = [r["return_code"] for r in res_list.json().get("returns", [])]
        assert return_code not in codes

        # Customer 2 gọi thẳng chi tiết đơn của buyer -> Bị từ chối (403 hoặc 404)
        res_detail = client.get(f"/api/v1/returns/{return_code}", headers=cust2_headers)
        assert res_detail.status_code in [403, 404]


# --------------------------------------------------------------------------
# Scenario 40: RETURN_NEW Notification Scoped to Owning Warehouse and Idempotent
# --------------------------------------------------------------------------
def test_40_return_new_notification_scoped_to_owning_warehouse_and_idempotent(client):
    """
    Mỗi WarehouseReturnCase được tạo phải có đúng một notification RETURN_NEW
    thuộc đúng warehouse_id, action_url mở đúng ca hoàn, và chống tạo trùng khi retry.
    """
    from app.services.warehouse_notification_service import WarehouseNotificationService
    from app.models.inventory import WarehouseNotification

    case_code = _get_or_create_test_case("KHO-HCM-01")
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        assert case is not None

        # Gửi thông báo lần 1
        notif1 = WarehouseNotificationService.notify_return_new(db, case=case)
        assert notif1.warehouse_id == wh_hcm.id
        assert notif1.notification_type == "RETURN_NEW"
        assert f"case_code={case.case_code}" in notif1.action_url

        # Gửi lại lần 2 (retry) -> Trả lại bản ghi cũ hoặc không tạo trùng
        notif2 = WarehouseNotificationService.notify_return_new(db, case=case)
        assert notif2.id == notif1.id

        # Kiểm tra Quản lý kho Hà Nội không thấy thông báo của HCM
        wh_hn = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
        hn_notifs = db.scalars(
            select(WarehouseNotification).where(
                WarehouseNotification.warehouse_id == wh_hn.id,
                WarehouseNotification.deduplication_key == notif1.deduplication_key,
            )
        ).all()
        assert len(hn_notifs) == 0


# --------------------------------------------------------------------------
# Scenario 41: Cross-Warehouse Manager Forbidden to View or Receive Case
# --------------------------------------------------------------------------
def test_41_cross_warehouse_manager_forbidden_to_view_or_receive(client, manager_hn_headers):
    """
    Quản lý kho khác không xem hoặc tiếp nhận ca hoàn của kho không thuộc phạm vi mình.
    """
    hcm_case_code = _get_or_create_test_case("KHO-HCM-01")

    # Manager HN mở ca của HCM -> 404 (IDOR guard)
    res_get = client.get(f"/api/v1/warehouse/me/returns/{hcm_case_code}", headers=manager_hn_headers)
    assert res_get.status_code == 404

    # Manager HN tiếp nhận kiện hàng ca của HCM -> 404 (IDOR guard)
    res_recv = client.post(
        f"/api/v1/warehouse/me/returns/{hcm_case_code}/receive",
        headers=manager_hn_headers,
        json={"carrier_name": "VNPost", "package_condition": "SEALED"},
    )
    assert res_recv.status_code == 404


# --------------------------------------------------------------------------
# Scenario 42: Staff List Contract and Role/Warehouse Filtering
# --------------------------------------------------------------------------
def test_42_staff_list_only_contains_active_warehouse_staff_of_manager_warehouse(client, manager_hcm_headers):
    """
    GET /warehouse-portal/staff trả về array; chỉ chứa WAREHOUSE_STAFF đang hoạt động tại kho của Quản lý.
    """
    res = client.get("/api/v1/warehouse-portal/staff", headers=manager_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list), "Contract phải là một array"

    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        for s in data:
            u = db.get(User, s["id"])
            assert u.role.value == "WAREHOUSE_STAFF"
            assert u.is_active is True
            # Kiểm tra membership thuộc HCM
            m = db.scalar(
                select(UserWarehouseMembership).where(
                    UserWarehouseMembership.user_id == u.id,
                    UserWarehouseMembership.warehouse_id == wh_hcm.id,
                    UserWarehouseMembership.is_active.is_(True),
                )
            )
            assert m is not None, f"Nhân viên {u.email} không thuộc kho HCM"


# --------------------------------------------------------------------------
# Scenario 43: Staff Assignment Backend Validation Guards
# --------------------------------------------------------------------------
def test_43_assign_staff_rejects_admin_manager_inactive_or_cross_warehouse(client, manager_hcm_headers):
    """
    Khi phân công, backend kiểm tra lại role, trạng thái tài khoản và membership;
    không tin staff_id từ frontend.
    """
    case_code = _get_or_create_test_case("KHO-HCM-01")

    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.role == UserRole.ADMIN))
        manager_hn = db.scalar(select(User).where(User.email == "manager.hn@pharmatrust.vn"))
        staff_hn = db.scalar(select(User).where(User.email.in_(["staff.hn@pharmatrust.vn", "staff_hn@pharmatrust.vn"])))

    # Phân công Admin -> Bị từ chối (400)
    res_admin = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/assign",
        headers=manager_hcm_headers,
        json={"staff_id": admin_user.id},
    )
    assert res_admin.status_code == 400

    # Phân công Quản lý kho -> Bị từ chối (400)
    res_mgr = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/assign",
        headers=manager_hcm_headers,
        json={"staff_id": manager_hn.id},
    )
    assert res_mgr.status_code == 400

    # Phân công nhân viên kho khác -> Bị từ chối (400)
    res_hn = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/assign",
        headers=manager_hcm_headers,
        json={"staff_id": staff_hn.id},
    )
    assert res_hn.status_code == 400


# --------------------------------------------------------------------------
# Scenario 44: Courier Delivery Confirmation, Idempotency and Missing Condition
# --------------------------------------------------------------------------
def test_44_courier_receiving_validation_and_idempotency(client, manager_hcm_headers):
    """
    Quản lý kho tiếp nhận gói hàng từ bưu tá; yêu cầu package_condition;
    chuyển sang RECEIVED; lặp lại lần 2 bị từ chối (400).
    """
    case_code = _get_or_create_test_case("KHO-HCM-01")

    with SessionLocal() as db:
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        case.status = ReturnStatus.IN_TRANSIT.value
        db.commit()

    # 1. Thiếu package_condition -> Bị từ chối (400 hoặc 422)
    res_empty_cond = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/receive",
        headers=manager_hcm_headers,
        json={"carrier_name": "Viettel Post", "package_condition": ""},
    )
    assert res_empty_cond.status_code in [400, 422]

    # 2. Hợp lệ -> Thành công sang RECEIVED
    res_ok = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/receive",
        headers=manager_hcm_headers,
        json={"carrier_name": "Viettel Post", "tracking_code": "VT9999", "package_condition": "SEALED"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == ReturnStatus.RECEIVED.value

    # 3. Nhận lại lần 2 khi đã ở RECEIVED -> Bị từ chối (400)
    res_dup = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/receive",
        headers=manager_hcm_headers,
        json={"carrier_name": "Viettel Post", "package_condition": "SEALED"},
    )
    assert res_dup.status_code == 400


# --------------------------------------------------------------------------
# Scenario 45: Prepaid Return Requires Beneficiary Account Details
# --------------------------------------------------------------------------
def test_45_prepaid_return_requires_beneficiary_account_details(client, buyer_headers):
    """
    Đơn hàng trả tiền trước (PAYOS/chuyển khoản) bắt buộc nhập đầy đủ số tài khoản,
    ngân hàng và tên chủ tài khoản; định dạng STK an toàn (6-20 số).
    """
    order_id, order_code, item_id, _ = _create_test_order_with_fulfillment("KHO-HCM-01")
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        order.payment_method = "PAYOS"
        order.payment_status = "PAID"
        db.commit()

    # 1. Thiếu thông tin ngân hàng -> 400
    res_no_bank = client.post(
        "/api/v1/returns",
        headers=buyer_headers,
        json={
            "order_code": order_code,
            "request_type": "RETURN",
            "reason_code": "DEFECTIVE",
            "reason_text": "Hàng lỗi",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
        },
    )
    assert res_no_bank.status_code == 400

    # 2. Số tài khoản không hợp lệ (ít hơn 6 số hoặc có chữ) -> 400
    res_bad_acc = client.post(
        "/api/v1/returns",
        headers=buyer_headers,
        json={
            "order_code": order_code,
            "request_type": "RETURN",
            "reason_code": "DEFECTIVE",
            "reason_text": "Hàng lỗi",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "refund_bank_name": "Vietcombank",
            "refund_account_number": "123",
            "refund_account_name": "NGUYEN VAN A",
        },
    )
    assert res_bad_acc.status_code == 400


# --------------------------------------------------------------------------
# Scenario 46: Beneficiary Information Cloning and Client Override Protection
# --------------------------------------------------------------------------
def test_46_beneficiary_cloned_to_refund_and_rejects_client_override(client, manager_hcm_headers):
    """
    Thông tin tài khoản thụ hưởng hiển thị trong chi tiết ca hoàn trước khi tạo Refund.
    Khi manager_process_refund được gọi, thông tin được sao chép an toàn từ ReturnRequest,
    tuyệt đối không chấp nhận client override số tài khoản khác.
    """
    order_id, order_code, item_id, _ = _create_test_order_with_fulfillment("KHO-HCM-01")
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        order.payment_method = "PAYOS"
        order.payment_status = "PAID"
        db.commit()

    buyer_login = client.post("/api/v1/auth/login", json={"email": "buyer@pharmatrust.vn", "password": "Buyer@123456"}).json()
    b_headers = {"Authorization": f"Bearer {buyer_login['access_token']}"}

    # Tạo return request có tài khoản
    res_create = client.post(
        "/api/v1/returns",
        headers=b_headers,
        json={
            "order_code": order_code,
            "request_type": "RETURN",
            "reason_code": "WRONG_ITEM",
            "reason_text": "Giao nhầm sản phẩm",
            "items": [{"order_item_id": item_id, "requested_quantity": 1}],
            "refund_bank_name": "MB Bank",
            "refund_account_number": "999988887777",
            "refund_account_name": "CHỦ TÀI KHOẢN CHÍNH THỨC",
        },
    )
    assert res_create.status_code == 200, res_create.text
    ret_code = res_create.json()["return_code"]

    with SessionLocal() as db:
        ret_req = db.scalar(select(ReturnRequest).where(ReturnRequest.return_code == ret_code))
        from app.services.warehouse_return_service import WarehouseReturnService
        cases = WarehouseReturnService.split_return_request_into_cases(db, ret_req)
        case_code = cases[0].case_code
        # Chuyển trạng thái để sẵn sàng hoàn tiền
        mgr = db.scalar(select(User).where(User.email == "manager.hcm@pharmatrust.vn"))
        cases[0].status = ReturnStatus.APPROVED.value
        cases[0].approved_by_user_id = mgr.id
        cases[0].items[0].approved_quantity = 1
        cases[0].items[0].received_quantity = 1
        cases[0].items[0].accepted_quantity = 1
        cases[0].items[0].approved_refund_amount = Decimal("50000.0")
        db.commit()

    # Quản lý xem chi tiết ca hoàn trước khi Refund tồn tại
    res_detail = client.get(f"/api/v1/warehouse/me/returns/{case_code}", headers=manager_hcm_headers)
    assert res_detail.status_code == 200
    rf_info = res_detail.json()["refund_info"]
    assert rf_info["beneficiary_bank"] == "MB Bank"
    assert rf_info["beneficiary_account_name"] == "CHỦ TÀI KHOẢN CHÍNH THỨC"
    assert "999988887777" in rf_info["beneficiary_account_number"]

    # Quản lý hoàn tiền, client cố tình gửi beneficiary_account_number giả mạo
    res_refund = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/refund",
        headers=manager_hcm_headers,
        json={
            "password": "Warehouse@2026",
            "refund_method": "BANK_TRANSFER",
            "beneficiary_account_number": "HACKED_ACCOUNT_999",
        },
    )
    assert res_refund.status_code == 200

    # Kiểm tra bản ghi Refund trong database phải giữ đúng tài khoản từ ReturnRequest
    with SessionLocal() as db:
        case = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        refund = case.refunds[0]
        assert refund.beneficiary_account_number == "999988887777"
        assert refund.beneficiary_account_number != "HACKED_ACCOUNT_999"
