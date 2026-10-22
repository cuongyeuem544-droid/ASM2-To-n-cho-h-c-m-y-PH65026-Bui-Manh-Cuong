"""Regression coverage for the four actions in the admin order dialog."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models import Order, OrderFulfillment, User, Warehouse
from app.models.enums import UserRole


@pytest.fixture
def status_order(database):
    with SessionLocal() as db:
        warehouse = db.scalar(select(Warehouse).limit(1))
        order = Order(
            order_code=f"STATUS-{uuid4().hex[:12]}",
            customer_name="Admin status regression",
            customer_phone="0900000000",
            shipping_address="Test address",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("100000"),
        )
        db.add(order)
        db.flush()
        fulfillment = OrderFulfillment(
            order_id=order.id,
            warehouse_id=warehouse.id,
            fulfillment_code=f"STATUS-FF-{uuid4().hex[:12]}",
            status="PENDING",
        )
        db.add(fulfillment)
        db.commit()
        return order.id, fulfillment.id


def set_statuses(order_id, fulfillment_id, order_status, fulfillment_status):
    with SessionLocal() as db:
        db.get(Order, order_id).order_status = order_status
        db.get(OrderFulfillment, fulfillment_id).status = fulfillment_status
        db.commit()


def test_pending_order_explains_unavailable_actions(client, admin_headers, status_order):
    order_id, _ = status_order
    response = client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)
    assert response.status_code == 200
    actions = {action["target_status"]: action for action in response.json()["status_actions"]}
    assert actions["CONFIRMED"]["allowed"] is True
    assert actions["CANCELLED"]["allowed"] is True
    assert actions["SHIPPING"]["allowed"] is False
    assert actions["SHIPPING"]["reason"]
    assert actions["COMPLETED"]["allowed"] is False
    assert actions["COMPLETED"]["reason"]


@pytest.mark.parametrize(
    ("current", "fulfillment_status", "target"),
    [
        ("PENDING", "PENDING", "CONFIRMED"),
        ("CONFIRMED", "SHIPPED", "SHIPPING"),
        ("SHIPPING", "DELIVERED", "COMPLETED"),
        ("PENDING", "PENDING", "CANCELLED"),
    ],
)
def test_admin_can_execute_each_valid_action(
    client, admin_headers, status_order, current, fulfillment_status, target
):
    order_id, fulfillment_id = status_order
    set_statuses(order_id, fulfillment_id, current, fulfillment_status)
    detail = client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers).json()
    action = next(item for item in detail["status_actions"] if item["target_status"] == target)
    assert action["allowed"] is True
    response = client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        headers=admin_headers,
        json={"order_status": target},
    )
    assert response.status_code == 200, response.text
    assert response.json()["order_status"] == target
    assert response.json()["payment_status"] == "PENDING"
    with SessionLocal() as db:
        assert db.get(Order, order_id).order_status == target


@pytest.mark.parametrize(
    ("current", "fulfillment_status", "target", "reason_fragment"),
    [
        ("CONFIRMED", "PACKED", "SHIPPING", "SHIPPED"),
        ("SHIPPING", "SHIPPED", "COMPLETED", "DELIVERED"),
        ("CONFIRMED", "SHIPPED", "CANCELLED", "Đổi / Trả"),
        ("COMPLETED", "DELIVERED", "CONFIRMED", "kết thúc"),
    ],
)
def test_action_reason_matches_backend_validation(
    client, admin_headers, status_order, current, fulfillment_status, target, reason_fragment
):
    order_id, fulfillment_id = status_order
    set_statuses(order_id, fulfillment_id, current, fulfillment_status)
    detail = client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers).json()
    action = next(item for item in detail["status_actions"] if item["target_status"] == target)
    assert action["allowed"] is False
    assert reason_fragment in action["reason"]
    response = client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        headers=admin_headers,
        json={"order_status": target},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == action["reason"]
    with SessionLocal() as db:
        assert db.get(Order, order_id).order_status == current


@pytest.mark.parametrize("role", [UserRole.CUSTOMER, UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF])
def test_non_admin_cannot_use_admin_actions(client, status_order, role):
    order_id, _ = status_order
    with SessionLocal() as db:
        user = User(
            email=f"status-{uuid4().hex}@example.com",
            full_name="Status RBAC regression",
            password_hash="unused-test-hash",
            role=role,
        )
        db.add(user)
        db.commit()
        token = create_access_token(str(user.id), role.value)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/admin/orders/{order_id}", headers=headers).status_code == 403
    for target in ("CONFIRMED", "SHIPPING", "COMPLETED", "CANCELLED"):
        response = client.patch(
            f"/api/v1/admin/orders/{order_id}/status",
            headers=headers,
            json={"order_status": target},
        )
        assert response.status_code == 403


def test_anonymous_cannot_update_status(client, status_order):
    order_id, _ = status_order
    response = client.patch(
        f"/api/v1/admin/orders/{order_id}/status", json={"order_status": "CONFIRMED"}
    )
    assert response.status_code == 401


def test_stale_action_metadata_cannot_bypass_fulfillment_guard(client, admin_headers, status_order):
    order_id, fulfillment_id = status_order
    detail = client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers).json()
    assert next(a for a in detail["status_actions"] if a["target_status"] == "CANCELLED")["allowed"]
    set_statuses(order_id, fulfillment_id, "CONFIRMED", "SHIPPED")
    response = client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        headers=admin_headers,
        json={"order_status": "CANCELLED"},
    )
    assert response.status_code == 400
    assert "Đổi / Trả" in response.json()["detail"]
