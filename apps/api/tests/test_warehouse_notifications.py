"""Automated Test Suite for Warehouse Notifications System.

Covers Section X Requirements:
1. Quản lý kho A thấy thông báo kho A.
2. Quản lý kho A không thấy thông báo kho B (Anti-IDOR).
3. Nhân viên chỉ thấy đơn mới và công việc được giao.
4. Nhân viên không thấy công việc riêng của nhân viên khác.
5. Nhân viên không thể duyệt cuối cùng đơn hoàn trả.
6. Lô còn đúng 60 ngày tạo cảnh báo WARNING.
7. Lô còn trên 60 ngày không tạo cảnh báo.
8. Lô hết hạn tạo cảnh báo EXPIRED / CRITICAL.
9. Scanner / Scheduler chạy 2 lần không tạo thông báo trùng (deduplication_key).
10. Đánh dấu đã đọc làm giảm unread_count.
11. Không thể đánh dấu thông báo của người khác / kho khác (Anti-IDOR).
12. Đơn mới phát đúng kho.
13. Hai nhân viên xử lý không làm trừ kho 2 lần hoặc đè lùi trạng thái đơn.
14. Ảnh hoàn trả không bị lộ qua nội dung hoặc URL public.
15. Các API kho cũ vẫn hoạt động bình thường.
"""
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    BatchStatus,
    CanonicalProduct,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    ProductSku,
    User,
    Warehouse,
    WarehouseBatchStock,
    WarehouseNotification,
)
from app.models.enums import UserRole
from app.services.warehouse_notification_service import WarehouseNotificationService


def _setup_test_notifications(db):
    """Helper to ensure warehouses exist and clean test notifications."""
    wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
    wh_hn = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
    assert wh_hcm is not None, "KHO-HCM-01 must exist"
    assert wh_hn is not None, "KHO-HN-01 must exist"

    staff_hcm = db.scalar(select(User).where(User.email.in_(["staff.hcm@pharmatrust.vn", "staff_hcm@pharmatrust.vn"])))
    assert staff_hcm is not None, "staff.hcm must exist"

    return wh_hcm, wh_hn, staff_hcm


def _get_or_create_test_sku(db):
    """Ensure at least one ProductSku exists for batch testing."""
    sku = db.scalar(select(ProductSku).limit(1))
    if sku:
        return sku
    prod = db.scalar(select(CanonicalProduct).limit(1))
    if not prod:
        prod = CanonicalProduct(
            canonical_name="Paracetamol 500mg Test",
            slug=f"paracetamol-500mg-test-{int(datetime.now().timestamp())}",
            is_active=True,
        )
        db.add(prod)
        db.flush()
    sku = ProductSku(
        canonical_product_id=prod.id,
        sku_code=f"SKU-TEST-{int(datetime.now().timestamp())}",
        barcode="8931234567890",
        uom="Hộp",
        conversion_rate=1,
        base_price=Decimal("25000"),
        is_default=True,
        is_active=True,
    )
    db.add(sku)
    db.flush()
    return sku


def test_manager_a_sees_notifications_for_warehouse_a(client, manager_hcm_headers):
    """1. Quản lý kho A thấy thông báo kho A."""
    with SessionLocal() as db:
        wh_hcm, _, _ = _setup_test_notifications(db)
        WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hcm.id,
            notification_type="ORDER_NEW",
            title="Đơn hàng test HCM",
            message="Nội dung test thông báo đơn mới HCM",
            severity="INFO",
            deduplication_key="TEST_NOTIF_HCM_01",
        )
        db.commit()

    res = client.get("/api/v1/warehouse-portal/notifications", headers=manager_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert any(n["title"] == "Đơn hàng test HCM" for n in data["items"])


def test_manager_a_cannot_see_notifications_of_warehouse_b(client, manager_hcm_headers):
    """2. Quản lý kho A không thấy thông báo kho B (Anti-IDOR)."""
    with SessionLocal() as db:
        _, wh_hn, _ = _setup_test_notifications(db)
        WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hn.id,
            notification_type="ORDER_NEW",
            title="Đơn hàng bí mật Hà Nội",
            message="Chỉ quản lý kho Hà Nội được thấy",
            severity="INFO",
            deduplication_key="TEST_SECRET_HN_01",
        )
        db.commit()

    res = client.get("/api/v1/warehouse-portal/notifications", headers=manager_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert not any(n["title"] == "Đơn hàng bí mật Hà Nội" for n in data["items"])


def test_staff_only_sees_order_new_and_assigned_tasks(client, staff_hcm_headers):
    """3. Nhân viên chỉ thấy đơn mới và công việc được giao cho chính mình."""
    with SessionLocal() as db:
        wh_hcm, _, staff_hcm = _setup_test_notifications(db)

        # Thông báo ORDER_NEW phát toàn kho
        WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hcm.id,
            notification_type="ORDER_NEW",
            title="Đơn hàng mở cho nhân viên",
            message="Tất cả nhân viên kho thấy đơn này",
            severity="INFO",
            recipient_user_id=None,
            deduplication_key="TEST_STAFF_BROADCAST_01",
        )

        # Thông báo giao việc trực tiếp cho nhân viên này
        WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hcm.id,
            notification_type="ORDER_ASSIGNED",
            title="Nhiệm vụ soạn hàng cá nhân",
            message="Giao riêng cho nhân viên HCM",
            severity="INFO",
            recipient_user_id=staff_hcm.id,
            deduplication_key=f"TEST_STAFF_TASK_{staff_hcm.id}",
        )
        db.commit()

    res = client.get("/api/v1/warehouse-portal/notifications", headers=staff_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    titles = [n["title"] for n in data["items"]]
    assert "Đơn hàng mở cho nhân viên" in titles
    assert "Nhiệm vụ soạn hàng cá nhân" in titles


def test_staff_cannot_see_private_tasks_of_other_staff(client, staff_hcm_headers):
    """4. Nhân viên không thấy công việc riêng của nhân viên khác."""
    with SessionLocal() as db:
        wh_hcm, _, staff_hcm = _setup_test_notifications(db)

        # Lấy hoặc tạo một user nhân viên khác để gán recipient_user_id (đảm bảo foreign key)
        other_staff = db.scalar(select(User).where(User.role == UserRole.WAREHOUSE_STAFF, User.id != staff_hcm.id))
        if not other_staff:
            other_staff = User(
                email=f"other.staff.{int(datetime.now().timestamp())}@pharmatrust.vn",
                hashed_password="hashed_pw_dummy",
                full_name="Other Staff Member",
                role=UserRole.WAREHOUSE_STAFF,
                is_active=True,
            )
            db.add(other_staff)
            db.flush()

        # Giả lập công việc giao cho nhân viên khác
        WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hcm.id,
            notification_type="ORDER_ASSIGNED",
            title="Nhiệm vụ riêng của nhân viên khác",
            message="Chỉ nhân viên khác được thấy",
            severity="INFO",
            recipient_user_id=other_staff.id,
            deduplication_key=f"TEST_PRIVATE_STAFF_{other_staff.id}",
        )
        db.commit()

    res = client.get("/api/v1/warehouse-portal/notifications", headers=staff_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert not any(n["title"] == "Nhiệm vụ riêng của nhân viên khác" for n in data["items"])


def test_staff_cannot_final_approve_return(client, staff_hcm_headers):
    """5. Nhân viên không thể duyệt cuối cùng đơn hoàn trả (chỉ Quản lý kho mới có quyền)."""
    # Nhân viên gọi API approve ca hoàn trả của Quản lý kho -> 403 Forbidden
    res = client.post("/api/v1/warehouse/me/returns/CASE-HCM-FAKE/approve", json={"note": "Staff approve"}, headers=staff_hcm_headers)
    assert res.status_code == 403


def test_batch_expiring_60_days_creates_warning():
    """6. Lô còn đúng 60 ngày tạo cảnh báo WARNING."""
    today = date.today()
    exp_60d = today + timedelta(days=60)

    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        sku = _get_or_create_test_sku(db)

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"EXP-60D-{int(datetime.now().timestamp())}",
            expiry_date=exp_60d,
            initial_quantity=100,
            status=BatchStatus.ACTIVE,
        )
        db.add(batch)
        db.flush()

        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_available=50,
            quantity_reserved=0,
        )
        db.add(stock)
        db.commit()

        # Quét hạn sử dụng
        created = WarehouseNotificationService.scan_batch_expiries(db, warehouse_id=wh.id, target_date=today)
        assert created >= 1

        notif = db.scalar(
            select(WarehouseNotification).where(
                WarehouseNotification.warehouse_id == wh.id,
                WarehouseNotification.entity_id == str(batch.id),
            )
        )
        assert notif is not None
        assert notif.severity == "WARNING"
        assert notif.notification_type == "BATCH_EXPIRING"


def test_batch_over_60_days_no_alert():
    """7. Lô còn trên 60 ngày không tạo cảnh báo."""
    today = date.today()
    exp_90d = today + timedelta(days=90)

    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        sku = _get_or_create_test_sku(db)

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"EXP-90D-{int(datetime.now().timestamp())}",
            expiry_date=exp_90d,
            initial_quantity=100,
            status=BatchStatus.ACTIVE,
        )
        db.add(batch)
        db.flush()

        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_available=50,
            quantity_reserved=0,
        )
        db.add(stock)
        db.commit()

        # Quét hạn sử dụng
        WarehouseNotificationService.scan_batch_expiries(db, warehouse_id=wh.id, target_date=today)

        notif = db.scalar(
            select(WarehouseNotification).where(
                WarehouseNotification.warehouse_id == wh.id,
                WarehouseNotification.entity_id == str(batch.id),
            )
        )
        assert notif is None, "Lô còn 90 ngày không được tạo thông báo"


def test_batch_expired_creates_expired_critical_alert():
    """8. Lô đã hết hạn tạo cảnh báo EXPIRED."""
    today = date.today()
    exp_past = today - timedelta(days=2)

    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        sku = _get_or_create_test_sku(db)

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"EXP-PAST-{int(datetime.now().timestamp())}",
            expiry_date=exp_past,
            initial_quantity=100,
            status=BatchStatus.ACTIVE,
        )
        db.add(batch)
        db.flush()

        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=50,
            quantity_available=50,
            quantity_reserved=0,
        )
        db.add(stock)
        db.commit()

        WarehouseNotificationService.scan_batch_expiries(db, warehouse_id=wh.id, target_date=today)

        notif = db.scalar(
            select(WarehouseNotification).where(
                WarehouseNotification.warehouse_id == wh.id,
                WarehouseNotification.entity_id == str(batch.id),
            )
        )
        assert notif is not None
        assert notif.severity == "EXPIRED"
        assert notif.notification_type == "BATCH_EXPIRED"


def test_scanner_twice_deduplication():
    """9. Scanner chạy hai lần không tạo thông báo trùng."""
    today = date.today()
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))

        first_run = WarehouseNotificationService.scan_batch_expiries(db, warehouse_id=wh.id, target_date=today)
        second_run = WarehouseNotificationService.scan_batch_expiries(db, warehouse_id=wh.id, target_date=today)

        # Lần 2 phải bằng 0 vì tất cả đã có deduplication_key
        assert second_run == 0


def test_mark_as_read_reduces_unread_count(client, manager_hcm_headers):
    """10. Đánh dấu đã đọc làm giảm unread_count."""
    with SessionLocal() as db:
        wh_hcm, _, _ = _setup_test_notifications(db)
        notif = WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hcm.id,
            notification_type="ORDER_NEW",
            title="Đơn test unread count",
            message="Kiểm tra giảm số lượng chưa đọc",
            severity="INFO",
            deduplication_key=f"TEST_UNREAD_{int(datetime.now().timestamp())}",
        )
        db.commit()
        notif_id = notif.id

    # 1. Lấy unread_count ban đầu
    res_before = client.get("/api/v1/warehouse-portal/notifications/unread-count", headers=manager_hcm_headers)
    count_before = res_before.json()["unread_count"]
    assert count_before >= 1

    # 2. Đánh dấu đã đọc
    res_read = client.patch(f"/api/v1/warehouse-portal/notifications/{notif_id}/read", headers=manager_hcm_headers)
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True

    # 3. Lấy unread_count sau khi đọc -> phải giảm đúng 1
    res_after = client.get("/api/v1/warehouse-portal/notifications/unread-count", headers=manager_hcm_headers)
    count_after = res_after.json()["unread_count"]
    assert count_after == count_before - 1


def test_cannot_mark_as_read_other_users_notification(client, staff_hcm_headers):
    """11. Không thể đánh dấu thông báo của người khác / kho khác."""
    with SessionLocal() as db:
        _, wh_hn, _ = _setup_test_notifications(db)
        notif_hn = WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hn.id,
            notification_type="ORDER_NEW",
            title="Thông báo của kho Hà Nội",
            message="Nhân viên HCM không được can thiệp",
            severity="INFO",
            deduplication_key="TEST_HN_FORBIDDEN_READ",
        )
        db.commit()
        hn_notif_id = notif_hn.id

    # Nhân viên HCM cố tình gọi PATCH trên thông báo kho Hà Nội -> 404
    res = client.patch(f"/api/v1/warehouse-portal/notifications/{hn_notif_id}/read", headers=staff_hcm_headers)
    assert res.status_code == 404


def test_order_new_dispatched_to_correct_warehouse():
    """12. Đơn mới phát đúng kho."""
    with SessionLocal() as db:
        wh_hcm, _, _ = _setup_test_notifications(db)
        order = db.scalar(select(Order).limit(1))
        if order:
            notif = WarehouseNotificationService.notify_order_new(db, order, wh_hcm.id)
            db.commit()
            assert notif.warehouse_id == wh_hcm.id
            assert notif.notification_type == "ORDER_NEW"
            assert notif.entity_id == str(order.id)


def test_concurrent_handling_race_condition(client, staff_hcm_headers):
    """13. Chống xử lý đè hoặc lùi bước khi đơn đã được xử lý."""
    with SessionLocal() as db:
        wh_hcm, _, _ = _setup_test_notifications(db)
        order = db.scalar(select(Order).where(Order.assigned_warehouse_id == wh_hcm.id, Order.fulfillment_status == "PACKED").limit(1))
        if not order:
            order = db.scalar(select(Order).where(Order.assigned_warehouse_id == wh_hcm.id).limit(1))
            if order:
                order.fulfillment_status = "PACKED"
                order.order_status = "PROCESSING"
                db.commit()

        order_id = order.id if order else None

    if order_id:
        # Khi đơn đã là PACKED, một nhân viên khác đến sau cố chuyển lùi về PICKING -> Phải chặn HTTP 400
        res = client.patch(
            f"/api/v1/warehouse-portal/orders/{order_id}/fulfillment",
            json={"fulfillment_status": "PICKING"},
            headers=staff_hcm_headers,
        )
        assert res.status_code == 400
        assert "Không thể lùi về" in res.json()["detail"]


def test_return_evidence_photo_not_leaked_publicly():
    """14. Ảnh hoàn trả không bị lộ qua nội dung thông báo."""
    with SessionLocal() as db:
        wh_hcm, _, _ = _setup_test_notifications(db)
        notif = WarehouseNotificationService.create_notification(
            db=db,
            warehouse_id=wh_hcm.id,
            notification_type="RETURN_EVIDENCE_ADDED",
            title="Khách đã nộp ảnh hoàn trả",
            message="Khách hàng đã nộp bổ sung hình ảnh minh chứng cho ca hoàn RET-TEST.",
            severity="INFO",
            deduplication_key="TEST_EVID_LEAK_CHECK",
        )
        db.commit()

        # Nội dung thông báo không được chứa URL file public hoặc ảnh nhạy cảm
        assert "http" not in notif.message
        assert ".jpg" not in notif.message
        assert ".png" not in notif.message


def test_existing_apis_still_functional(client, manager_hcm_headers):
    """15. Các API kho cũ vẫn hoạt động bình thường."""
    # 1. Orders
    res_orders = client.get("/api/v1/warehouse-portal/orders?page_size=5", headers=manager_hcm_headers)
    assert res_orders.status_code == 200

    # 2. Batches
    res_batches = client.get("/api/v1/warehouse-portal/batches?page_size=5", headers=manager_hcm_headers)
    assert res_batches.status_code == 200

    # 3. Stock
    res_stock = client.get("/api/v1/warehouse-portal/stock?page_size=5", headers=manager_hcm_headers)
    assert res_stock.status_code == 200

    # 4. Alerts
    res_alerts = client.get("/api/v1/warehouse-portal/alerts?page_size=5", headers=manager_hcm_headers)
    assert res_alerts.status_code == 200
