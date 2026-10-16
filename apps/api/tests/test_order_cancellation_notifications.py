"""Tests for Order Cancellation Notifications & Warehouse Synchronization.

Verifies:
1. When an order is cancelled, FulfillmentRoutingService releases reservations, sets
   order.order_status = "CANCELLED", order.fulfillment_status = "CANCELLED",
   and creates an ORDER_CANCELLED WarehouseNotification.
2. Both WAREHOUSE_MANAGER and WAREHOUSE_STAFF receive the cancellation notification
   in their notifications list and unread count.
3. WAREHOUSE_STAFF can mark the broadcast ORDER_CANCELLED notification as read.
4. Cancelled orders are excluded from active warehouse fulfillment tabs (ALLOCATED, PICKING, etc.)
   and only returned under the CANCELLED tab.
5. Attempting to advance fulfillment status on a cancelled order is rejected with HTTP 400.
"""
from datetime import UTC, datetime
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    CanonicalProduct,
    Order,
    OrderFulfillment,
    OrderItem,
    ProductSku,
    User,
    Warehouse,
    WarehouseNotification,
)
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.warehouse_notification_service import WarehouseNotificationService


def _get_or_create_test_order(db, wh_id: int) -> Order:
    """Helper to ensure a clean allocated order exists for testing cancellation."""
    order = db.scalar(
        select(Order).where(
            Order.assigned_warehouse_id == wh_id,
            Order.order_status.in_(["PENDING", "PROCESSING"]),
            Order.fulfillment_status == "ALLOCATED",
        ).limit(1)
    )
    if order:
        return order

    import uuid
    uid = uuid.uuid4().hex[:8].upper()
    order = Order(
        order_code=f"PT-CANCEL-{uid}",
        customer_name="Nguyễn Văn Test Hủy",
        customer_phone="0912345678",
        shipping_address="123 Đường Test, Quận 1, TP. Hồ Chí Minh",
        total_amount=Decimal("150000"),
        payment_method="COD",
        payment_status="PENDING",
        order_status="PENDING",
        fulfillment_status="ALLOCATED",
        assigned_warehouse_id=wh_id,
        created_at=datetime.now(UTC),
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        product_name="Thuốc Kháng Sinh Test",
        product_sku="SKU-TEST-001",
        quantity=2,
        price=Decimal("75000"),
        subtotal=Decimal("150000"),
    )
    db.add(item)

    import uuid
    ff = OrderFulfillment(
        fulfillment_code=f"FF-{uuid.uuid4().hex[:8].upper()}",
        order_id=order.id,
        warehouse_id=wh_id,
        status="PENDING",
        created_at=datetime.now(UTC),
    )
    db.add(ff)
    db.commit()
    return order


def test_order_cancellation_releases_and_notifies_warehouse():
    """1. Kiểm tra giải phóng và bắn thông báo ORDER_CANCELLED tới kho."""
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        assert wh is not None, "KHO-HCM-01 must exist"

        order = _get_or_create_test_order(db, wh.id)
        order_id = order.id
        order_code = order.order_code

        # Thực hiện hủy đơn
        released = FulfillmentRoutingService.release_order_reservations(
            db=db,
            order_id=order_id,
            reason="Khách hàng tự hủy đơn",
        )

        db.refresh(order)
        assert order.order_status == "CANCELLED"
        assert order.fulfillment_status == "CANCELLED"

        # Kiểm tra bản ghi thông báo
        notif = db.scalar(
            select(WarehouseNotification).where(
                WarehouseNotification.warehouse_id == wh.id,
                WarehouseNotification.notification_type == "ORDER_CANCELLED",
                WarehouseNotification.entity_id == str(order_id),
            )
        )
        assert notif is not None, "ORDER_CANCELLED notification must be created"
        assert notif.severity == "CRITICAL"
        assert order_code in notif.title
        assert "dừng soạn hàng" in notif.message.lower()
        assert notif.recipient_user_id is None  # Broadcast cho cả quản lý và nhân viên


def test_order_cancellation_staff_and_manager_visibility(client, manager_hcm_headers, staff_hcm_headers):
    """2. Quản lý kho và nhân viên kho đều nhận được thông báo hủy đơn và có thể đánh dấu đã đọc."""
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        assert wh is not None
        order = _get_or_create_test_order(db, wh.id)
        FulfillmentRoutingService.release_order_reservations(db, order.id, reason="Khách hủy")
        notif = db.scalar(
            select(WarehouseNotification).where(
                WarehouseNotification.warehouse_id == wh.id,
                WarehouseNotification.notification_type == "ORDER_CANCELLED",
                WarehouseNotification.entity_id == str(order.id),
            )
        )
        assert notif is not None
        notif_id = notif.id

    # 1. Quản lý kho xem thông báo
    res_mgr = client.get("/api/v1/warehouse-portal/notifications", headers=manager_hcm_headers)
    assert res_mgr.status_code == 200
    items_mgr = res_mgr.json()["items"]
    assert any(n["id"] == notif_id and n["notification_type"] == "ORDER_CANCELLED" for n in items_mgr)

    # 2. Nhân viên kho xem thông báo (không bị chặn quyền broadcast ORDER_CANCELLED)
    res_staff = client.get("/api/v1/warehouse-portal/notifications", headers=staff_hcm_headers)
    assert res_staff.status_code == 200
    items_staff = res_staff.json()["items"]
    assert any(n["id"] == notif_id and n["notification_type"] == "ORDER_CANCELLED" for n in items_staff)

    # 3. Nhân viên kho kiểm tra unread-count
    res_unread = client.get("/api/v1/warehouse-portal/notifications/unread-count", headers=staff_hcm_headers)
    assert res_unread.status_code == 200
    assert res_unread.json()["unread_count"] >= 1

    # 4. Nhân viên kho đánh dấu đã đọc thông báo hủy đơn
    res_read = client.patch(f"/api/v1/warehouse-portal/notifications/{notif_id}/read", headers=staff_hcm_headers)
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True


def test_cancelled_order_excluded_from_active_tabs_and_visible_in_cancelled_tab(client, manager_hcm_headers):
    """3. Đơn đã hủy không xuất hiện trong tab Chờ soạn (ALLOCATED) và chỉ hiện ở tab CANCELLED."""
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        order = _get_or_create_test_order(db, wh.id)
        FulfillmentRoutingService.release_order_reservations(db, order.id, reason="Khách hủy")
        order_code = order.order_code

    # Tab Chờ soạn (ALLOCATED): KHÔNG chứa đơn đã hủy
    res_allocated = client.get("/api/v1/warehouse-portal/orders?status=ALLOCATED", headers=manager_hcm_headers)
    assert res_allocated.status_code == 200
    codes_allocated = [o["order_code"] for o in res_allocated.json()["items"]]
    assert order_code not in codes_allocated

    # Tab Đã hủy (CANCELLED): CÓ chứa đơn đã hủy
    res_cancelled = client.get("/api/v1/warehouse-portal/orders?status=CANCELLED", headers=manager_hcm_headers)
    assert res_cancelled.status_code == 200
    codes_cancelled = [o["order_code"] for o in res_cancelled.json()["items"]]
    assert order_code in codes_cancelled


def test_cannot_advance_fulfillment_on_cancelled_order(client, staff_hcm_headers):
    """4. Chặn thay đổi tiến trình soạn/gói đối với đơn hàng đã hủy."""
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        order = _get_or_create_test_order(db, wh.id)
        FulfillmentRoutingService.release_order_reservations(db, order.id, reason="Khách hủy")
        order_id = order.id

    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_id}/fulfillment",
        json={"fulfillment_status": "PICKING"},
        headers=staff_hcm_headers,
    )
    assert res.status_code == 400
    assert "đã bị hủy" in res.json()["detail"].lower()
