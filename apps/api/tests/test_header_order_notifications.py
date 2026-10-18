import pytest
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.entities import Order, OrderItem, User
from app.models.enums import UserRole
from app.models.inventory import (
    InventoryBatch,
    ProductSku,
    UserWarehouseMembership,
    Warehouse,
    WarehouseBatchStock,
    WarehouseNotification,
)
from app.services.warehouse_notification_service import WarehouseNotificationService
from app.core.security import create_access_token


@pytest.fixture
def test_setup():
    with SessionLocal() as db_session:
        # Setup Warehouses: HN and HCM
        wh_hn = db_session.query(Warehouse).filter_by(code="KHO-HN-01").first()
        if not wh_hn:
            wh_hn = Warehouse(
                code="KHO-HN-01",
                name="Kho Dược Hà Nội",
                address="102 Thái Hà, Đống Đa, Hà Nội",
                city="Hà Nội",
                lat=21.0118,
                lng=105.8194,
                is_active=True,
                is_central=False,
            )
            db_session.add(wh_hn)

        wh_hcm = db_session.query(Warehouse).filter_by(code="KHO-HCM-01").first()
        if not wh_hcm:
            wh_hcm = Warehouse(
                code="KHO-HCM-01",
                name="Kho Dược TP.HCM",
                address="123 Nguyễn Huệ, Quận 1, TP.HCM",
                city="TP.HCM",
                lat=10.7769,
                lng=106.7009,
                is_active=True,
                is_central=True,
            )
            db_session.add(wh_hcm)

        db_session.commit()
        db_session.refresh(wh_hn)
        db_session.refresh(wh_hcm)

        from app.core.security import hash_password
        pwd = hash_password("123456")

        # Users
        admin = db_session.query(User).filter_by(email="admin_notif_test@pharmatrust.vn").first()
        if not admin:
            admin = User(
                email="admin_notif_test@pharmatrust.vn",
                password_hash=pwd,
                full_name="Admin Test",
                role=UserRole.ADMIN,
                is_active=True,
            )
            db_session.add(admin)

        manager_hn = db_session.query(User).filter_by(email="manager_hn_test@pharmatrust.vn").first()
        if not manager_hn:
            manager_hn = User(
                email="manager_hn_test@pharmatrust.vn",
                password_hash=pwd,
                full_name="Quản Lý Kho HN",
                role=UserRole.WAREHOUSE_MANAGER,
                is_active=True,
            )
            db_session.add(manager_hn)

        staff_hn = db_session.query(User).filter_by(email="staff_hn_test@pharmatrust.vn").first()
        if not staff_hn:
            staff_hn = User(
                email="staff_hn_test@pharmatrust.vn",
                password_hash=pwd,
                full_name="Nhân Viên Kho HN",
                role=UserRole.WAREHOUSE_STAFF,
                is_active=True,
            )
            db_session.add(staff_hn)

        manager_hcm = db_session.query(User).filter_by(email="manager_hcm_test@pharmatrust.vn").first()
        if not manager_hcm:
            manager_hcm = User(
                email="manager_hcm_test@pharmatrust.vn",
                password_hash=pwd,
                full_name="Quản Lý Kho HCM",
                role=UserRole.WAREHOUSE_MANAGER,
                is_active=True,
            )
            db_session.add(manager_hcm)

        db_session.commit()
        db_session.refresh(admin)
        db_session.refresh(manager_hn)
        db_session.refresh(staff_hn)
        db_session.refresh(manager_hcm)

        # Memberships
        for u, w in [(manager_hn, wh_hn), (staff_hn, wh_hn), (manager_hcm, wh_hcm)]:
            m = db_session.query(UserWarehouseMembership).filter_by(user_id=u.id).first()
            if not m:
                m = UserWarehouseMembership(
                    user_id=u.id,
                    warehouse_id=w.id,
                    role=u.role.value,
                    is_active=True,
                )
                db_session.add(m)
        db_session.commit()

        wh_hn_id = wh_hn.id
        wh_hcm_id = wh_hcm.id
        admin_id = admin.id
        mgr_hn_id = manager_hn.id
        staff_hn_id = staff_hn.id
        mgr_hcm_id = manager_hcm.id
        admin_email = admin.email
        mgr_hn_email = manager_hn.email
        staff_hn_email = staff_hn.email
        mgr_hcm_email = manager_hcm.email

    return {
        "wh_hn_id": wh_hn_id,
        "wh_hcm_id": wh_hcm_id,
        "admin_id": admin_id,
        "admin_email": admin_email,
        "mgr_hn_id": mgr_hn_id,
        "mgr_hn_email": mgr_hn_email,
        "staff_hn_id": staff_hn_id,
        "staff_hn_email": staff_hn_email,
        "mgr_hcm_id": mgr_hcm_id,
        "mgr_hcm_email": mgr_hcm_email,
    }


def test_header_notifications_admin_manager_staff(client: TestClient, test_setup: dict):
    wh_hn_id = test_setup["wh_hn_id"]
    wh_hcm_id = test_setup["wh_hcm_id"]
    admin_id = test_setup["admin_id"]
    admin_email = test_setup["admin_email"]
    mgr_hn_id = test_setup["mgr_hn_id"]
    mgr_hn_email = test_setup["mgr_hn_email"]
    staff_hn_id = test_setup["staff_hn_id"]
    staff_hn_email = test_setup["staff_hn_email"]
    mgr_hcm_id = test_setup["mgr_hcm_id"]
    mgr_hcm_email = test_setup["mgr_hcm_email"]

    with SessionLocal() as db_session:
        # Clear old test notifications
        db_session.query(WarehouseNotification).filter(
            WarehouseNotification.warehouse_id.in_([wh_hn_id, wh_hcm_id])
        ).delete(synchronize_session=False)
        db_session.commit()

        # Create order allocated to HN
        order_hn = Order(
            order_code="TEST-ORD-HN-001",
            customer_name="Khách Hà Nội",
            customer_phone="0911222333",
            shipping_address="Hà Nội",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("150000"),
            assigned_warehouse_id=wh_hn_id,
        )
        db_session.add(order_hn)
        db_session.commit()
        db_session.refresh(order_hn)

        # Dispatch ORDER_NEW to HN
        notif_hn = WarehouseNotificationService.notify_order_new(db_session, order_hn, wh_hn_id)
        db_session.commit()
        db_session.refresh(notif_hn)
        notif_hn_id = notif_hn.id

        # Create order allocated to HCM
        order_hcm = Order(
            order_code="TEST-ORD-HCM-001",
            customer_name="Khách HCM",
            customer_phone="0988777666",
            shipping_address="TP.HCM",
            payment_method="COD",
            payment_status="PENDING",
            order_status="PENDING",
            total_amount=Decimal("250000"),
            assigned_warehouse_id=wh_hcm_id,
        )
        db_session.add(order_hcm)
        db_session.commit()
        db_session.refresh(order_hcm)

        # Dispatch ORDER_NEW to HCM
        notif_hcm = WarehouseNotificationService.notify_order_new(db_session, order_hcm, wh_hcm_id)
        db_session.commit()
        db_session.refresh(notif_hcm)

    # 1. ADMIN TEST: Admin sees unread count = 2 (all warehouses)
    admin_token = create_access_token(str(admin_id), UserRole.ADMIN.value)
    resp_admin = client.get(
        "/api/v1/warehouse-portal/notifications/unread-count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["unread_count"] == 2

    # Admin lists notifications: both HN and HCM appear, with warehouse details
    list_admin = client.get(
        "/api/v1/warehouse-portal/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_admin.status_code == 200
    items = list_admin.json()["items"]
    assert len(items) == 2
    wh_codes = [it["warehouse_code"] for it in items]
    assert "KHO-HN-01" in wh_codes
    assert "KHO-HCM-01" in wh_codes

    # 2. MANAGER HN TEST: Manager HN only sees unread count = 1 (wh_hn)
    mgr_hn_token = create_access_token(str(mgr_hn_id), UserRole.WAREHOUSE_MANAGER.value)
    resp_mgr_hn = client.get(
        "/api/v1/warehouse-portal/notifications/unread-count",
        headers={"Authorization": f"Bearer {mgr_hn_token}"},
    )
    assert resp_mgr_hn.status_code == 200
    assert resp_mgr_hn.json()["unread_count"] == 1

    list_mgr_hn = client.get(
        "/api/v1/warehouse-portal/notifications",
        headers={"Authorization": f"Bearer {mgr_hn_token}"},
    )
    assert list_mgr_hn.status_code == 200
    assert list_mgr_hn.json()["total"] == 1
    assert list_mgr_hn.json()["items"][0]["warehouse_code"] == "KHO-HN-01"
    assert list_mgr_hn.json()["items"][0]["notification_type"] == "ORDER_NEW"

    # 3. STAFF HN TEST: Staff HN sees broadcast ORDER_NEW for their warehouse
    staff_hn_token = create_access_token(str(staff_hn_id), UserRole.WAREHOUSE_STAFF.value)
    resp_staff_hn = client.get(
        "/api/v1/warehouse-portal/notifications/unread-count",
        headers={"Authorization": f"Bearer {staff_hn_token}"},
    )
    assert resp_staff_hn.status_code == 200
    assert resp_staff_hn.json()["unread_count"] == 1

    # 4. ANTI-IDOR TEST: Manager HCM cannot mark HN notification as read
    mgr_hcm_token = create_access_token(str(mgr_hcm_id), UserRole.WAREHOUSE_MANAGER.value)
    read_forbidden = client.patch(
        f"/api/v1/warehouse-portal/notifications/{notif_hn_id}/read",
        headers={"Authorization": f"Bearer {mgr_hcm_token}"},
    )
    assert read_forbidden.status_code == 403

    # 5. ADMIN READ TEST: Admin can mark HN notification as read
    read_admin = client.patch(
        f"/api/v1/warehouse-portal/notifications/{notif_hn_id}/read",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert read_admin.status_code == 200
    assert read_admin.json()["is_read"] is True

    # After reading 1, Admin unread count is 1, Manager HN unread count is 0
    resp_admin_after = client.get(
        "/api/v1/warehouse-portal/notifications/unread-count",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin_after.json()["unread_count"] == 1

    resp_mgr_hn_after = client.get(
        "/api/v1/warehouse-portal/notifications/unread-count",
        headers={"Authorization": f"Bearer {mgr_hn_token}"},
    )
    assert resp_mgr_hn_after.json()["unread_count"] == 0
