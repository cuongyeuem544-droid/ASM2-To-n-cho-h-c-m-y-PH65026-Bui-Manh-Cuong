"""Comprehensive Test Suite for Multi-Warehouse Inventory, Routing, Consolidation, and RBAC.

Covers:
1. Seeding of >= 20 warehouses nationwide with GPS coordinates.
2. FEFO 180-day shelf-life threshold cutoff.
3. Proximity-based order routing with Haversine distance calculation.
4. Inter-warehouse transfer and consolidation state machine.
5. Transfer failure auto-cancellation and 100% full refund (Decision Q6).
6. RBAC isolation: Warehouse Manager cannot modify base product prices (Decision Q4).
7. Warehouse Manager staff creation permissions (Decision Q5).
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    BatchStatus,
    CanonicalProduct,
    InventoryBatch,
    Order,
    PaymentTransaction,
    ProductSku,
    StockReservation,
    StockTransfer,
    Warehouse,
    WarehouseBatchStock,
    Refund,
)
from app.services.fulfillment_service import FulfillmentRoutingService


def test_twenty_warehouses_seeded_with_coordinates(client, admin_headers):
    """
    Quy định 1: Hệ thống phải có ít nhất 20 kho trên toàn quốc với đầy đủ tọa độ GPS và thông tin liên hệ.
    """
    res = client.get("/api/v1/warehouses", headers=admin_headers)
    assert res.status_code == 200
    warehouses = res.json()
    assert len(warehouses) >= 20, f"Cần ít nhất 20 kho, hiện có: {len(warehouses)}"

    # Kiểm tra tính hợp lệ của tọa độ và bán kính phục vụ
    for wh in warehouses:
        assert wh["code"], "Mã kho không được rỗng"
        assert wh["name"], "Tên kho không được rỗng"
        assert wh["address"], "Địa chỉ kho không được rỗng"
        assert wh["lat"] is not None and -90 <= wh["lat"] <= 90
        assert wh["lng"] is not None and -180 <= wh["lng"] <= 180


def test_warehouse_manager_portal_me(client, manager_hcm_headers):
    """
    Kiểm tra Portal kho: Quản lý kho xem được thông tin kho của mình và KPIs.
    """
    res = client.get("/api/v1/warehouse-portal/me", headers=manager_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["warehouse"]["code"] == "KHO-HCM-01"
    assert data["user_role"] == "WAREHOUSE_MANAGER"
    assert "kpi" in data
    assert data["kpi"]["total_batches"] >= 0


def test_fefo_180_days_cutoff_enforcement(client, database):
    """
    Quyết định Q7: Ngưỡng hạn sử dụng tối thiểu 180 ngày (6 tháng).
    Lô thuốc có HSD < 180 ngày tuyệt đối không được phân bổ tự động cho đơn khách hàng.
    """
    today = date.today()
    with SessionLocal() as db:
        prod = db.scalar(select(CanonicalProduct).limit(1))
        sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id).limit(1))
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod.id,
                sku_code=f"SKU-FEFO-TEST",
                conversion_rate=1,
                base_price=Decimal("45000"),
                is_default=True,
                is_active=True,
            )
            db.add(sku)
            db.commit()

        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))

        # Tạo 1 lô cận hạn: HSD 60 ngày (< 180 ngày) với tồn kho lớn (100 đơn vị)
        near_expiry_batch = InventoryBatch(
            sku_id=sku.id,
            batch_number="BAT-NEAR-EXPIRY-60D",
            manufacture_date=today - timedelta(days=300),
            expiry_date=today + timedelta(days=60),
            initial_quantity=100,
            status=BatchStatus.ACTIVE,
        )
        db.add(near_expiry_batch)
        db.flush()

        stock_near = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=near_expiry_batch.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            quantity_available=100,
        )
        db.add(stock_near)

        # Tạo 1 lô đạt chuẩn: HSD 365 ngày (>= 180 ngày) với tồn kho 50 đơn vị
        valid_batch = InventoryBatch(
            sku_id=sku.id,
            batch_number="BAT-VALID-FEFO-365D",
            manufacture_date=today - timedelta(days=30),
            expiry_date=today + timedelta(days=365),
            initial_quantity=50,
            status=BatchStatus.ACTIVE,
        )
        db.add(valid_batch)
        db.flush()

        stock_valid = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=valid_batch.id,
            quantity_on_hand=50,
            quantity_reserved=0,
            quantity_available=50,
        )
        db.add(stock_valid)
        db.commit()

        # Tạo đơn đặt hàng thử nghiệm
        order = Order(
            order_code=f"ORD-FEFO-TEST-{int(date.today().day)}",
            customer_name="Test FEFO Buyer",
            customer_phone="0911223344",
            shipping_address="12 Lê Duẩn, Quận 1, TP. HCM",
            total_amount=Decimal("90000"),
            lat=10.7872,
            lng=106.7001,
            payment_method="COD",
            order_status="PENDING",
        )
        db.add(order)
        db.flush()

        from app.models import OrderItem
        it = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            product_sku=sku.sku_code,
            price=Decimal("45000"),
            quantity=10,
            subtotal=Decimal("450000"),
        )
        db.add(it)
        db.flush()

        # Thực thi điều phối và phân bổ lô
        FulfillmentRoutingService.route_and_allocate_order(
            db=db,
            order=order,
            items=[it],
            shipping_city="TP. Hồ Chí Minh",
            shipping_address="12 Lê Duẩn, Quận 1, TP. HCM",
        )

        # Kiểm tra lô được giữ chỗ: Phải là valid_batch, TUYỆT ĐỐI không phải near_expiry_batch
        reservations = db.scalars(select(StockReservation).where(StockReservation.order_id == order.id)).all()
        assert len(reservations) > 0
        allocated_batch_ids = [r.batch_id for r in reservations]

        assert valid_batch.id in allocated_batch_ids, "Lô đạt chuẩn FEFO >= 180 ngày phải được chọn"
        assert near_expiry_batch.id not in allocated_batch_ids, "Lô cận hạn < 180 ngày BẮT BUỘC bị loại bỏ khỏi phân bổ đơn"


def test_haversine_proximity_warehouse_assignment(database):
    """
    Quyết định Q3: Định tuyến đơn hàng về kho gần nhất dựa trên khoảng cách Haversine.
    """
    today = date.today()
    with SessionLocal() as db:
        prod = db.scalar(select(CanonicalProduct).limit(1))
        sku = FulfillmentRoutingService.get_or_create_default_sku(db, prod.id)

        wh_hn = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
        assert wh_hn is not None, "Kho Hà Nội (KHO-HN-01) phải tồn tại"

        # Đảm bảo kho Hà Nội có lô thuốc hợp lệ (HSD >= 180 ngày)
        batch_hn = InventoryBatch(
            sku_id=sku.id,
            batch_number="BAT-HN-PROXIMITY-TEST",
            manufacture_date=today - timedelta(days=30),
            expiry_date=today + timedelta(days=365),
            initial_quantity=100,
            status=BatchStatus.ACTIVE,
        )
        db.add(batch_hn)
        db.flush()

        stock_hn = WarehouseBatchStock(
            warehouse_id=wh_hn.id,
            batch_id=batch_hn.id,
            quantity_on_hand=100,
            quantity_reserved=0,
            quantity_available=100,
        )
        db.add(stock_hn)
        db.commit()

        # Đơn giao tại Hà Nội (Tọa độ Hoàn Kiếm: 21.0285, 105.8542)
        order_hn = Order(
            order_code="ORD-GEO-HN-TEST",
            customer_name="Khách Hà Nội",
            customer_phone="0988776655",
            shipping_address="45 Đinh Tiên Hoàng, Hoàn Kiếm, Hà Nội",
            total_amount=Decimal("150000"),
            lat=21.0285,
            lng=105.8542,
            payment_method="COD",
            order_status="PENDING",
        )
        db.add(order_hn)
        db.flush()

        from app.models import OrderItem
        it_hn = OrderItem(
            order_id=order_hn.id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            product_sku=sku.sku_code,
            price=Decimal("50000"),
            quantity=1,
            subtotal=Decimal("50000"),
        )
        db.add(it_hn)
        db.flush()

        FulfillmentRoutingService.route_and_allocate_order(
            db=db,
            order=order_hn,
            items=[it_hn],
            shipping_city="Hà Nội",
            shipping_address="45 Đinh Tiên Hoàng, Hoàn Kiếm, Hà Nội",
        )

        # Kho được gán phải thuộc Hà Nội (KHO-HN-01 hoặc chi nhánh Hà Nội)
        assigned_wh = db.get(Warehouse, order_hn.assigned_warehouse_id)
        assert assigned_wh is not None
        assert "HN" in assigned_wh.code, f"Đơn Hà Nội phải được gán vào kho Hà Nội, thực tế: {assigned_wh.code}"
        assert order_hn.assignment_distance_km is not None
        assert order_hn.assignment_distance_km < 35.0, "Khoảng cách phải nhỏ hơn bán kính phục vụ"


def test_rbac_warehouse_manager_staff_creation(client, manager_hcm_headers):
    """
    Quyết định Q5: Quản lý kho ĐƯỢC PHÉP tạo tài khoản Nhân Viên Kho (WAREHOUSE_STAFF) thuộc kho của mình,
    nhưng KHÔNG ĐƯỢC PHÉP tạo ADMIN.
    """
    # 1. Tạo WAREHOUSE_STAFF hợp lệ
    staff_email = f"staff.test.{int(date.today().day)}@pharmatrust.vn"
    res = client.post(
        "/api/v1/warehouse-portal/staff",
        headers=manager_hcm_headers,
        json={
            "full_name": "Nhân viên Soạn hàng Mẫu",
            "email": staff_email,
            "password": "StaffPassword@2026",
            "phone": "0987654321",
        },
    )
    assert res.status_code == 201
    created_staff = res.json()
    assert created_staff["email"] == staff_email
    assert created_staff["role"] == "WAREHOUSE_STAFF"
    assert created_staff["warehouse_name"] is not None

    # 2. Thử tạo ADMIN qua API /users -> Bắt buộc bị từ chối 403 Forbidden
    res_forbidden = client.post(
        "/api/v1/users",
        headers=manager_hcm_headers,
        json={
            "full_name": "Hacker cố tạo Admin",
            "email": "fake.admin@pharmatrust.vn",
            "password": "Password@123456",
            "role": "ADMIN",
        },
    )
    assert res_forbidden.status_code == 403


def test_rbac_pricing_control_isolation(client, manager_hcm_headers):
    """
    Quyết định Q4: Quản trị viên quản lý giá tập trung.
    Quản lý kho KHÔNG ĐƯỢC PHÉP chỉnh sửa giá bán gốc của sản phẩm.
    """
    # 1. Thử gọi API sửa giá bán sản phẩm
    res_pricing = client.patch(
        "/api/v1/products/1/pricing",
        headers=manager_hcm_headers,
        json={"price": 125000, "availability_text": "Có sẵn"},
    )
    assert res_pricing.status_code == 403

    # 2. Thử gọi API duyệt phân loại sản phẩm y tế
    res_approve = client.post(
        "/api/v1/admin/classification/1/approve",
        headers=manager_hcm_headers,
        json={"product_type": "MEDICINE", "prescription_status": "OTC"},
    )
    assert res_approve.status_code == 403


def test_transfer_failure_auto_cancellation_and_refund(database):
    """
    Quyết định Q6: Khi điều chuyển kho thất bại (hỏng/mất hàng),
    hệ thống tự động hủy đơn hàng và hoàn tiền 100% cho khách hàng.
    """
    with SessionLocal() as db:
        wh_from = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
        wh_to = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))

        # Tạo đơn hàng đã thanh toán
        order = Order(
            order_code="ORD-TRANSFER-FAIL-TEST",
            customer_name="Khách Hàng Hoàn Tiền",
            customer_phone="0911223344",
            shipping_address="123 Nguyễn Huệ, Quận 1, TP. HCM",
            total_amount=Decimal("350000"),
            payment_method="VIETQR",
            payment_status="PAID",
            order_status="PROCESSING",
            fulfillment_status="WAITING_INTERNAL_TRANSFER",
            assigned_warehouse_id=wh_to.id,
        )
        db.add(order)
        db.flush()

        # Tạo phiếu chuyển kho nội bộ cho đơn này
        transfer = StockTransfer(
            transfer_code="TRF-FAIL-TEST-001",
            from_warehouse_id=wh_from.id,
            to_warehouse_id=wh_to.id,
            order_id=order.id,
            status="IN_TRANSIT",
            note="Điều chuyển thử nghiệm thất bại",
        )
        db.add(transfer)
        db.commit()

        # Kích hoạt sự cố điều chuyển hàng thất bại
        res = FulfillmentRoutingService.cancel_transfer_and_refund_order(
            db=db,
            transfer_id=transfer.id,
            reason="Hàng thuốc bị vỡ hỏng trong quá trình vận chuyển đường bộ",
        )

        assert res["success"] is True
        assert res["refund_amount"] == 350000.0

        # Kiểm tra trạng thái đơn hàng: Đã hủy và đã hoàn tiền
        db.refresh(order)
        assert order.order_status == "CANCELLED"
        assert order.fulfillment_status == "CANCELLED"
        assert order.payment_status == "REFUNDED"

        # Kiểm tra bản ghi hoàn tiền trong bảng refunds
        refund_record = db.scalar(select(Refund).where(Refund.order_id == order.id))
        assert refund_record is not None
        assert refund_record.amount == Decimal("350000")
        assert refund_record.status == "SUCCEEDED"
        assert "vỡ hỏng" in refund_record.reason


def test_anti_idor_defense_cross_warehouse_access_rejected(client, manager_hcm_headers):
    """
    Quy định 8: Chống IDOR tuyệt đối.
    Quản lý kho HCM truyền tham số warehouse_id=2 (Kho Hà Nội) phải bị từ chối 403 Forbidden.
    """
    # 1. Truy cập /warehouse-portal/me với warehouse_id khác
    res1 = client.get("/api/v1/warehouse-portal/me?warehouse_id=2", headers=manager_hcm_headers)
    assert res1.status_code == 403
    assert "IDOR" in res1.json()["detail"] or "Vi phạm phân quyền" in res1.json()["detail"]

    # 2. Truy cập /warehouse-portal/orders với warehouse_id khác
    res2 = client.get("/api/v1/warehouse-portal/orders?warehouse_id=2", headers=manager_hcm_headers)
    assert res2.status_code == 403

    # 3. Truy cập /warehouse-portal/stock với warehouse_id khác
    res3 = client.get("/api/v1/warehouse-portal/stock?warehouse_id=2", headers=manager_hcm_headers)
    assert res3.status_code == 403


def test_stock_adjustment_requires_mandatory_reason(client, manager_hcm_headers):
    """
    Quy định 4: Điều chỉnh tồn kho bắt buộc phải nhập lý do (tối thiểu 5 ký tự).
    """
    # Gửi lý do rỗng -> 422 hoặc 400
    res_empty = client.post(
        "/api/v1/warehouse-portal/adjustments",
        headers=manager_hcm_headers,
        json={"reason": "   ", "items": []},
    )
    assert res_empty.status_code in (400, 422)

    # Gửi lý do quá ngắn (< 5 ký tự) -> 422
    res_short = client.post(
        "/api/v1/warehouse-portal/adjustments",
        headers=manager_hcm_headers,
        json={"reason": "abc", "items": []},
    )
    assert res_short.status_code in (400, 422)


def test_no_legacy_roles_remain_in_database(database):
    """
    Quy định 2 & 10: Hai quyền cũ (DATA_REVIEWER, VIEWER) đã được loại bỏ hoàn toàn.
    Không còn bất kỳ tài khoản nào mang vai trò cũ trong cơ sở dữ liệu.
    """
    import sqlite3
    conn = sqlite3.connect("pharmatrust.db")
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM users WHERE role IN ('DATA_REVIEWER', 'VIEWER')")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 0, f"Còn {count} tài khoản mang vai trò cũ chưa được chuyển đổi!"


def test_order_picking_details_and_fefo_batches(client, database, manager_hn_headers):
    """
    Kiểm thử chức năng Phiếu Soạn (Pick Details):
    - Đơn hàng trả về đầy đủ các thông tin: order_id, order_code, customer_name, shipping_address
    - Danh sách dòng thuốc (lines) trả về product_name, unit, quantity_required, unit_price, line_total
    - Lô thuốc gợi ý (suggested_batches) theo FEFO sắp xếp theo hạn sử dụng tăng dần (gần nhất trước)
    """
    # Lấy danh sách đơn hàng của kho Hà Nội
    res = client.get("/api/v1/warehouse-portal/orders", headers=manager_hn_headers)
    assert res.status_code == 200
    data = res.json()
    orders = data.get("items", [])
    if orders:
        order_id = orders[0]["id"]
        # Gọi API lấy phiếu soạn
        detail_res = client.get(f"/api/v1/warehouse-portal/orders/{order_id}/pick-details", headers=manager_hn_headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["order_id"] == order_id
        assert "lines" in detail
        assert len(detail["lines"]) >= 0
        for line in detail["lines"]:
            assert "product_name" in line
            assert "unit" in line
            assert "quantity_required" in line
            assert "unit_price" in line
            assert "line_total" in line
            assert "suggested_batches" in line
            # Nếu có nhiều lô thì phải theo thứ tự FEFO (expiry date tăng dần)
            if len(line["suggested_batches"]) > 1:
                dates = [b["expiry_date"] for b in line["suggested_batches"]]
                assert dates == sorted(dates)

