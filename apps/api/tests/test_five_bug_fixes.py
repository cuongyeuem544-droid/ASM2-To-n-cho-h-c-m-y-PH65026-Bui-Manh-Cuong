"""
Comprehensive Test Suite for 5 Critical Bug Fixes (H4CARE / PharmaTrust).

Tests:
- Bug 1: Restocking returns strictly into original allocated batches (no fake SKU/batch, no .first(), multi-batch distribution, idempotency).
- Bug 2: Fulfillment sequential FSM (PENDING -> PICKED -> PACKED -> SHIPPED -> DELIVERED), no skipping, anti-IDOR, single stock deduction on SHIPPED.
- Bug 3: Staff return inspection requires explicit selections (no defaults, 422 if missing), blocks RESTOCK if any safety check fails (400).
- Bug 4: No auto-promotion of approved_quantity to requested_quantity, rejects refund when total approved is 0, strict net unit price refund calculation.
- Bug 5: Customer live chat WebSocket authentication (4401 missing, 4403 invalid/mismatched/closed, valid guest & customer JWT accepted).
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import secrets
import uuid
import pytest
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import CanonicalProduct, Order, OrderItem, User
from app.models import LiveChatSession
from app.models.enums import UserRole
from app.models.returns import ReturnRequestType, ReturnStatus
from app.models.inventory import (
    BatchStatus,
    FulfillmentItem,
    InventoryBatch,
    OrderFulfillment,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    StockReservation,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import ItemCondition, Refund, RefundMethod, RefundStatus, ReturnItem, ReturnRequest, WarehouseReturnCase
from fastapi.testclient import TestClient


def _get_or_create_product_and_sku(db):
    prod = db.scalar(select(CanonicalProduct).limit(1))
    if not prod:
        prod = CanonicalProduct(
            canonical_name="Thuốc Kháng Sinh Clavamox 500mg Test",
            generic_name="Amoxicillin + Clavulanate",
            is_prescription=False,
            requires_pharmacist_consult=False,
        )
        db.add(prod)
        db.flush()

    sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id).limit(1))
    if not sku:
        sku = ProductSku(
            canonical_product_id=prod.id,
            sku_code=f"SKU-TEST-{prod.id}",
            uom="Hộp",
            base_price=Decimal("120000"),
            is_active=True,
        )
        db.add(sku)
        db.flush()
    return prod, sku


def _create_test_order_and_case(db, wh, prod, sku, batch_allocations: list[tuple[InventoryBatch, int]], return_status=ReturnStatus.REFUNDED.value):
    buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
    if not buyer:
        buyer = db.scalar(select(User).where(User.role == UserRole.CUSTOMER).limit(1))

    total_qty = sum(qty for _, qty in batch_allocations) if batch_allocations else 1
    total_price = Decimal(str(total_qty * 120000))

    order = Order(
        order_code=f"ORD-T-{uuid.uuid4().hex[:6].upper()}",
        user_id=buyer.id if buyer else 1,
        customer_name="Buyer Test",
        customer_phone="0911223344",
        shipping_address="123 Test Street, HCM",
        total_amount=total_price,
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
        product_sku=sku.sku_code,
        price=Decimal("120000"),
        quantity=total_qty,
        subtotal=total_price,
    )
    db.add(order_item)
    db.flush()

    ful = OrderFulfillment(
        order_id=order.id,
        warehouse_id=wh.id,
        fulfillment_code=f"FUL-T-{uuid.uuid4().hex[:6].upper()}",
        status="DELIVERED",
        shipping_fee=Decimal("0"),
    )
    db.add(ful)
    db.flush()

    ful_item = FulfillmentItem(fulfillment_id=ful.id, order_item_id=order_item.id, quantity=total_qty)
    db.add(ful_item)
    db.flush()

    for batch, qty in batch_allocations:
        alloc = OrderItemBatchAllocation(
            order_item_id=order_item.id,
            fulfillment_item_id=ful_item.id,
            batch_id=batch.id,
            allocated_quantity=qty,
            warehouse_id=wh.id,
        )
        db.add(alloc)

    ret = ReturnRequest(
        return_code=f"RET-T-{uuid.uuid4().hex[:6].upper()}",
        order_id=order.id,
        user_id=buyer.id if buyer else 1,
        customer_name="Buyer Test",
        customer_phone="0911223344",
        request_type=ReturnRequestType.RETURN.value,
        status=return_status,
        reason_code="WRONG_ITEM",
        reason_text="Hoàn thuốc",
        requested_at=datetime.now(UTC),
    )
    db.add(ret)
    db.flush()

    case = WarehouseReturnCase(
        case_code=f"WRC-T-{uuid.uuid4().hex[:6].upper()}",
        return_request_id=ret.id,
        warehouse_id=wh.id,
        fulfillment_id=ful.id,
        status=return_status,
    )
    db.add(case)
    db.flush()

    ri = ReturnItem(
        warehouse_return_case_id=case.id,
        return_request_id=ret.id,
        order_item_id=order_item.id,
        product_id=prod.id,
        product_name=prod.canonical_name,
        original_quantity=total_qty,
        requested_quantity=total_qty,
        approved_quantity=total_qty,
        condition_reported="SEALED",
        unit_price_at_purchase=Decimal("120000"),
        net_paid_amount=total_price,
        requested_refund_amount=total_price,
        approved_refund_amount=total_price,
    )
    db.add(ri)
    db.flush()

    return order, ful, case, ri


# ==============================================================================
# BUG 1 TESTS: HÀNG HOÀN CHỈ NHẬP VÀO ĐÚNG LÔ ĐÃ XUẤT CHO KHÁCH
# ==============================================================================

def test_bug1_return_single_batch_restock(client, manager_hcm_headers):
    """Hoàn trả sản phẩm xuất từ 1 lô gốc: tồn kho tăng đúng lô đó, tạo StockMovement RETURN_RESTOCK."""
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        prod, sku = _get_or_create_product_and_sku(db)

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"BAT-B1-S1-{uuid.uuid4().hex[:4].upper()}",
            manufacture_date=date.today() - timedelta(days=90),
            expiry_date=date.today() + timedelta(days=360),
            status=BatchStatus.ACTIVE,
        )
        db.add(batch)
        db.flush()

        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=10,
            quantity_available=10,
            quantity_reserved=0,
        )
        db.add(stock)
        db.flush()

        order, ful, case, ri = _create_test_order_and_case(
            db=db,
            wh=wh,
            prod=prod,
            sku=sku,
            batch_allocations=[(batch, 2)],
            return_status=ReturnStatus.REFUNDED.value,
        )
        db.commit()

        case_code = case.case_code
        batch_id = batch.id
        q_before = stock.quantity_available
        wh_id = wh.id

    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/stock-disposition",
        headers=manager_hcm_headers,
        json={"disposition": "RESTOCK", "note": "Nhập lại đúng lô gốc"},
    )
    assert res.status_code == 200, res.json()

    with SessionLocal() as db:
        st_after = db.scalar(
            select(WarehouseBatchStock).where(
                WarehouseBatchStock.warehouse_id == wh_id,
                WarehouseBatchStock.batch_id == batch_id,
            )
        )
        assert st_after.quantity_available == q_before + 2
        assert st_after.quantity_on_hand == q_before + 2

        mov = db.scalar(
            select(StockMovement).where(
                StockMovement.reference_id == case_code,
                StockMovement.movement_type == "RETURN_RESTOCK",
                StockMovement.batch_id == batch_id,
            )
        )
        assert mov is not None
        assert mov.quantity == 2


def test_bug1_return_multi_batch_restock(client, manager_hcm_headers):
    """Hoàn trả sản phẩm xuất từ NHIỀU lô: phân bổ tuần tự đúng từng lô, không dùng .first()."""
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        prod, sku = _get_or_create_product_and_sku(db)

        batch1 = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"BAT-MULTI-1-{uuid.uuid4().hex[:4].upper()}",
            manufacture_date=date.today() - timedelta(days=120),
            expiry_date=date.today() + timedelta(days=200),
            status=BatchStatus.ACTIVE,
        )
        batch2 = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"BAT-MULTI-2-{uuid.uuid4().hex[:4].upper()}",
            manufacture_date=date.today() - timedelta(days=60),
            expiry_date=date.today() + timedelta(days=350),
            status=BatchStatus.ACTIVE,
        )
        db.add_all([batch1, batch2])
        db.flush()

        stock1 = WarehouseBatchStock(warehouse_id=wh.id, batch_id=batch1.id, quantity_on_hand=5, quantity_available=5)
        stock2 = WarehouseBatchStock(warehouse_id=wh.id, batch_id=batch2.id, quantity_on_hand=5, quantity_available=5)
        db.add_all([stock1, stock2])
        db.flush()

        order, ful, case, ri = _create_test_order_and_case(
            db=db,
            wh=wh,
            prod=prod,
            sku=sku,
            batch_allocations=[(batch1, 1), (batch2, 2)],
            return_status=ReturnStatus.REFUNDED.value,
        )
        db.commit()

        case_code = case.case_code
        b1_id, b2_id = batch1.id, batch2.id
        wh_id = wh.id

    # 1. Gọi không truyền batch_allocations khi có nhiều lô -> Phải từ chối 422
    res_no_alloc = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/stock-disposition",
        headers=manager_hcm_headers,
        json={"disposition": "RESTOCK", "note": "Hoàn về 2 lô"},
    )
    assert res_no_alloc.status_code == 422
    assert "từng được xuất từ nhiều lô" in res_no_alloc.json()["detail"]

    # 2. Gọi kèm danh sách phân bổ lô rõ ràng -> Thành công 200
    res = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/stock-disposition",
        headers=manager_hcm_headers,
        json={
            "disposition": "RESTOCK",
            "note": "Hoàn về 2 lô",
            "batch_allocations": [
                {"batch_id": b1_id, "quantity": 1},
                {"batch_id": b2_id, "quantity": 2},
            ],
        },
    )
    assert res.status_code == 200, res.json()

    with SessionLocal() as db:
        s1 = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.batch_id == b1_id, WarehouseBatchStock.warehouse_id == wh_id))
        s2 = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.batch_id == b2_id, WarehouseBatchStock.warehouse_id == wh_id))
        assert s1.quantity_available == 6
        assert s2.quantity_available == 7

        movements = db.scalars(
            select(StockMovement).where(StockMovement.reference_id == case_code, StockMovement.movement_type == "RETURN_RESTOCK")
        ).all()
        assert len(movements) == 2
        batch_ids_moved = {m.batch_id: m.quantity for m in movements}
        assert batch_ids_moved[b1_id] == 1
        assert batch_ids_moved[b2_id] == 2


def test_bug1_missing_allocation_and_idempotency_rejected(client, manager_hcm_headers):
    """Không có thông tin allocation bị từ chối 400; gọi lại lần hai bị từ chối 400 (idempotency)."""
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        prod, sku = _get_or_create_product_and_sku(db)

        order, ful, case, ri = _create_test_order_and_case(
            db=db,
            wh=wh,
            prod=prod,
            sku=sku,
            batch_allocations=[],  # Rỗng, không có allocation
            return_status=ReturnStatus.REFUNDED.value,
        )
        db.commit()
        no_alloc_case_code = case.case_code

    # 1. Gọi RESTOCK khi không có allocation -> Phải bị từ chối HTTP 400
    res = client.post(
        f"/api/v1/warehouse/me/returns/{no_alloc_case_code}/stock-disposition",
        headers=manager_hcm_headers,
        json={"disposition": "RESTOCK", "note": "Thử restock không allocation"},
    )
    assert res.status_code == 400
    assert "Không tìm thấy thông tin lô xuất kho gốc" in res.json()["detail"]

    # 2. Kiểm tra Idempotency: Tạo một case đã RESTOCKED trước đó, gọi lại phải bị chặn
    with SessionLocal() as db:
        c_done = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == no_alloc_case_code))
        c_done.status = ReturnStatus.RESTOCKED.value
        db.commit()

    res_duplicate = client.post(
        f"/api/v1/warehouse/me/returns/{no_alloc_case_code}/stock-disposition",
        headers=manager_hcm_headers,
        json={"disposition": "RESTOCK", "note": "Gọi lại lần hai"},
    )
    assert res_duplicate.status_code == 400
    assert "đã được xử lý phân luồng hàng trước đó" in res_duplicate.json()["detail"]


# ==============================================================================
# BUG 2 TESTS: TRẠNG THÁI GIAO HÀNG & TRỪ TỒN KHO THỰC TẾ
# ==============================================================================

def test_bug2_sequential_fsm_and_single_stock_deduction(client, manager_hcm_headers):
    """
    FSM tuần tự: PENDING -> PICKED -> PACKED -> SHIPPED -> DELIVERED.
    Nhảy cóc (PENDING -> SHIPPED) bị từ chối 400.
    Trừ tồn kho đúng 1 lần khi chuyển sang SHIPPED; DELIVERED không trừ lần hai.
    """
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        prod, sku = _get_or_create_product_and_sku(db)
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"BAT-FSM-{uuid.uuid4().hex[:4].upper()}",
            manufacture_date=date.today() - timedelta(days=30),
            expiry_date=date.today() + timedelta(days=400),
            status=BatchStatus.ACTIVE,
        )
        db.add(batch)
        db.flush()

        stock = WarehouseBatchStock(
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity_on_hand=20,
            quantity_available=18,
            quantity_reserved=2,
        )
        db.add(stock)
        db.flush()

        order = Order(
            order_code=f"ORD-FSM-{uuid.uuid4().hex[:4].upper()}",
            user_id=buyer.id if buyer else 1,
            customer_name="Buyer FSM",
            customer_phone="0911223344",
            shipping_address="123 FSM Road, HCM",
            total_amount=Decimal("240000"),
            payment_status="PAID",
            order_status="PROCESSING",
            fulfillment_status="PENDING",
        )
        db.add(order)
        db.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            product_sku=sku.sku_code,
            price=Decimal("120000"),
            quantity=2,
            subtotal=Decimal("240000"),
        )
        db.add(order_item)
        db.flush()

        ful = OrderFulfillment(
            order_id=order.id,
            warehouse_id=wh.id,
            fulfillment_code=f"FUL-FSM-{uuid.uuid4().hex[:4].upper()}",
            status="PENDING",
            shipping_fee=Decimal("0"),
        )
        db.add(ful)
        db.flush()

        ful_item = FulfillmentItem(fulfillment_id=ful.id, order_item_id=order_item.id, quantity=2)
        db.add(ful_item)
        db.flush()

        resv = StockReservation(
            order_id=order.id,
            warehouse_id=wh.id,
            batch_id=batch.id,
            quantity=2,
            status="RESERVED",
        )
        db.add(resv)

        alloc = OrderItemBatchAllocation(
            order_item_id=order_item.id,
            fulfillment_item_id=ful_item.id,
            batch_id=batch.id,
            allocated_quantity=2,
            warehouse_id=wh.id,
        )
        db.add(alloc)
        db.commit()

        order_id = order.id
        batch_id = batch.id
        wh_id = wh.id

    # 1. Thử nhảy cóc PENDING -> SHIPPED -> Phải bị từ chối 400
    res_jump = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_id}/status",
        headers=manager_hcm_headers,
        json={"status": "SHIPPED"},
    )
    assert res_jump.status_code == 400
    assert "bắt buộc tuần tự" in res_jump.json()["detail"]

    # 2. Bước 1 hợp lệ: PENDING -> PICKED
    res_step1 = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_id}/status",
        headers=manager_hcm_headers,
        json={"status": "PICKED"},
    )
    assert res_step1.status_code == 200, res_step1.json()

    # 3. Bước 2 hợp lệ: PICKED -> PACKED
    res_step2 = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_id}/status",
        headers=manager_hcm_headers,
        json={"status": "PACKED"},
    )
    assert res_step2.status_code == 200, res_step2.json()

    # Kiểm tra tồn kho trước khi SHIPPED (vẫn on_hand=20, reserved=2)
    with SessionLocal() as db:
        st_mid = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.batch_id == batch_id, WarehouseBatchStock.warehouse_id == wh_id))
        assert st_mid.quantity_on_hand == 20
        assert st_mid.quantity_reserved == 2

    # 4. Bước 3 hợp lệ: PACKED -> SHIPPED (Trừ on_hand và reserved)
    res_step3 = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_id}/status",
        headers=manager_hcm_headers,
        json={"status": "SHIPPED"},
    )
    assert res_step3.status_code == 200, res_step3.json()

    with SessionLocal() as db:
        st_shipped = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.batch_id == batch_id, WarehouseBatchStock.warehouse_id == wh_id))
        assert st_shipped.quantity_on_hand == 18
        assert st_shipped.quantity_reserved == 0

        mov_dispatch = db.scalar(
            select(StockMovement).where(
                StockMovement.movement_type == "DISPATCH",
                StockMovement.batch_id == batch_id,
                StockMovement.warehouse_id == wh_id,
            )
        )
        assert mov_dispatch is not None
        assert abs(mov_dispatch.quantity) == 2

        r = db.scalar(select(StockReservation).where(StockReservation.order_id == order_id))
        assert r.status == "FULFILLED"

    # 5. Bước 4 hợp lệ: SHIPPED -> DELIVERED (Không trừ kho lần hai)
    res_step4 = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_id}/status",
        headers=manager_hcm_headers,
        json={"status": "DELIVERED"},
    )
    assert res_step4.status_code == 200, res_step4.json()

    with SessionLocal() as db:
        st_deliv = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.batch_id == batch_id, WarehouseBatchStock.warehouse_id == wh_id))
        assert st_deliv.quantity_on_hand == 18
        assert st_deliv.quantity_reserved == 0
        o_final = db.get(Order, order_id)
        assert o_final.order_status == "COMPLETED"
        assert o_final.fulfillment_status == "DELIVERED"


def test_bug2_cross_warehouse_idor_blocked(client, manager_hn_headers):
    """Kho Hà Nội cố tình cập nhật đơn của Kho HCM bị chặn 403 Forbidden."""
    with SessionLocal() as db:
        wh_hcm = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))

        order = Order(
            order_code=f"ORD-IDOR-{uuid.uuid4().hex[:4].upper()}",
            user_id=buyer.id if buyer else 1,
            customer_name="Buyer IDOR",
            customer_phone="0911223344",
            shipping_address="HCM Address",
            total_amount=Decimal("120000"),
            payment_status="PAID",
            order_status="PROCESSING",
        )
        db.add(order)
        db.flush()

        ful = OrderFulfillment(
            order_id=order.id,
            warehouse_id=wh_hcm.id,
            fulfillment_code=f"FUL-IDOR-{uuid.uuid4().hex[:4].upper()}",
            status="PENDING",
            shipping_fee=Decimal("0"),
        )
        db.add(ful)
        db.commit()
        order_id = order.id

    res = client.patch(
        f"/api/v1/warehouse-portal/orders/{order_id}/status",
        headers=manager_hn_headers,
        json={"status": "PICKED"},
    )
    assert res.status_code == 403
    assert "thuộc phạm vi xử lý của kho bạn" in res.json()["detail"]


# ==============================================================================
# BUG 3 TESTS: MẪU KIỂM HÀNG ĐIỀN SẴN ĐẠT CHUẨN
# ==============================================================================

def test_bug3_inspection_validation_and_restock_safety_block(client, staff_hcm_headers):
    """
    1. Thiếu bất kỳ trường kiểm tra nào trả về 422.
    2. Nếu có tiêu chí không đạt (seal_intact=False hoặc storage_condition_ok=False) mà đề xuất RESTOCK -> 400.
    3. Đạt toàn bộ kiểm tra mới cho phép RESTOCK.
    """
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        prod, sku = _get_or_create_product_and_sku(db)

        order, ful, case, ri = _create_test_order_and_case(
            db=db,
            wh=wh,
            prod=prod,
            sku=sku,
            batch_allocations=[],
            return_status=ReturnStatus.INSPECTING.value,
        )
        db.commit()

        case_code = case.case_code
        item_id = ri.id

    # 1. Gửi thiếu trường bắt buộc (ví dụ thiếu seal_intact và package_condition) -> 422
    res_missing = client.post(
        f"/api/v1/warehouse/staff/me/returns/{case_code}/inspect",
        headers=staff_hcm_headers,
        json={
            "inspections": [
                {
                    "return_item_id": item_id,
                    "batch_matched": True,
                    "expiry_matched": True,
                }
            ]
        },
    )
    assert res_missing.status_code == 422

    # 2. Tiêu chí không đạt (seal_intact=False) nhưng chọn RESTOCK -> 400
    res_unsafe = client.post(
        f"/api/v1/warehouse/staff/me/returns/{case_code}/inspect",
        headers=staff_hcm_headers,
        json={
            "inspections": [
                {
                    "return_item_id": item_id,
                    "received_quantity": 1,
                    "condition": "DAMAGED",
                    "package_condition": "DAMAGED",
                    "seal_intact": False,
                    "batch_matched": True,
                    "expiry_matched": True,
                    "storage_condition_ok": True,
                    "suggested_action": "RESTOCK",  # Vi phạm an toàn dược phẩm!
                    "accepted_quantity": 1,
                    "rejected_quantity": 0,
                }
            ]
        },
    )
    assert res_unsafe.status_code in (400, 422)
    assert "Tuyệt đối không được đề xuất hoặc nhập lại kho bán (RESTOCK)" in str(res_unsafe.json())

    # 3. Toàn bộ tiêu chí đạt chuẩn -> RESTOCK thành công
    res_valid = client.post(
        f"/api/v1/warehouse/staff/me/returns/{case_code}/inspect",
        headers=staff_hcm_headers,
        json={
            "inspections": [
                {
                    "return_item_id": item_id,
                    "received_quantity": 1,
                    "condition": "GOOD_CONDITION",
                    "package_condition": "SEALED",
                    "seal_intact": True,
                    "batch_matched": True,
                    "expiry_matched": True,
                    "storage_condition_ok": True,
                    "suggested_action": "RESTOCK",
                    "accepted_quantity": 1,
                    "rejected_quantity": 0,
                    "notes": "Hộp thuốc nguyên vẹn, tem GSP chuẩn",
                }
            ]
        },
    )
    assert res_valid.status_code == 200, res_valid.json()


# ==============================================================================
# BUG 4 TESTS: TỰ ĐỘNG THAY THẾ SỐ LƯỢNG DUYỆT BẰNG SỐ LƯỢNG YÊU CẦU
# ==============================================================================

def test_bug4_refund_approval_validation_and_calculation(client, manager_hcm_headers):
    """
    1. approved_quantity = 0 không bị ghi đè thành requested_quantity.
    2. Quản lý duyệt 0 sản phẩm bị từ chối 400.
    3. Duyệt một phần (khách yêu cầu 3 nhưng chỉ duyệt 2): tiền hoàn tính đúng 2 * net_unit_price.
    4. approved_quantity vượt quá requested_quantity bị từ chối 400.
    """
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        prod, sku = _get_or_create_product_and_sku(db)

        order, ful, case, ri = _create_test_order_and_case(
            db=db,
            wh=wh,
            prod=prod,
            sku=sku,
            batch_allocations=[],
            return_status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
        )
        ri.original_quantity = 3
        ri.requested_quantity = 3
        ri.approved_quantity = 0
        ri.unit_price_at_purchase = Decimal("120000")
        ri.net_paid_amount = Decimal("360000")
        ri.requested_refund_amount = Decimal("360000")
        ri.approved_refund_amount = Decimal("0")
        db.commit()

        case_code = case.case_code
        item_id = ri.id

    # 1. Quản lý duyệt 0 sản phẩm -> Phải bị từ chối 400
    res_zero = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/approve",
        headers=manager_hcm_headers,
        json={
            "accepted_items": [{"return_item_id": item_id, "approved_quantity": 0, "rejection_reason": "Không đủ điều kiện"}]
        },
    )
    assert res_zero.status_code == 400
    assert "Tổng số lượng sản phẩm được duyệt là 0" in res_zero.json()["detail"]

    # 2. Quản lý duyệt vượt quá requested_quantity (ví dụ duyệt 4) -> 400
    res_exceed = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/approve",
        headers=manager_hcm_headers,
        json={
            "accepted_items": [{"return_item_id": item_id, "approved_quantity": 4}]
        },
    )
    assert res_exceed.status_code == 400
    assert "không hợp lệ" in res_exceed.json()["detail"]

    # 3. Phê duyệt hợp lệ một phần (yêu cầu 3 nhưng chỉ duyệt 2)
    res_partial = client.post(
        f"/api/v1/warehouse/me/returns/{case_code}/approve",
        headers=manager_hcm_headers,
        json={
            "accepted_items": [{"return_item_id": item_id, "approved_quantity": 2, "rejection_reason": "1 hộp rách bao bì"}],
            "manager_note": "Duyệt 2 hộp đạt chuẩn",
        },
    )
    assert res_partial.status_code == 200, res_partial.json()

    with SessionLocal() as db:
        c_approved = db.scalar(select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == case_code))
        it_approved = c_approved.items[0]
        # approved_quantity phải chính xác là 2, KHÔNG bị thay thế thành 3
        assert it_approved.approved_quantity == 2
        assert it_approved.rejected_quantity == 1
        # Tiền hoàn tính chuẩn xác: 2 * 120,000 = 240,000
        assert it_approved.approved_refund_amount == Decimal("240000")


# ==============================================================================
# BUG 5 TESTS: WEBSOCKET CHAT AUTHENTICATION
# ==============================================================================

def test_bug5_websocket_auth_security(client):
    """
    1. Không truyền token -> Đóng kết nối mã 4401 trước accept.
    2. Truyền token sai -> Đóng kết nối mã 4403.
    3. Guest gửi đúng guest_session_token -> Kết nối thành công.
    4. Customer gửi đúng JWT access token của mình -> Kết nối thành công.
    5. Customer gửi JWT của mình nhưng truy cập phiên chat của người khác -> 4403.
    6. Kết nối vào phiên chat đã CLOSED -> 4403.
    """
    guest_token = secrets.token_urlsafe(32)

    with SessionLocal() as db:
        buyer = db.scalar(select(User).where(User.email == "buyer@pharmatrust.vn"))
        guest_sess = LiveChatSession(
            session_code=f"GUEST-WS-{uuid.uuid4().hex[:6].upper()}",
            guest_session_token=guest_token,
            customer_name="Khách vãng lai",
            status="ACTIVE",
        )
        user_sess = LiveChatSession(
            session_code=f"USER-WS-{uuid.uuid4().hex[:6].upper()}",
            customer_id=buyer.id,
            customer_name=buyer.full_name,
            status="ACTIVE",
        )
        closed_sess = LiveChatSession(
            session_code=f"CLOSED-WS-{uuid.uuid4().hex[:6].upper()}",
            guest_session_token="closed_token",
            status="CLOSED",
        )
        db.add_all([guest_sess, user_sess, closed_sess])
        db.commit()

        g_code = guest_sess.session_code
        u_code = user_sess.session_code
        c_code = closed_sess.session_code
        buyer_id = buyer.id
        buyer_role = buyer.role
        buyer_version = buyer.token_version or 1

    jwt_token = create_access_token(subject=str(buyer_id), role=buyer_role, token_version=buyer_version)

    # 1. Không truyền token -> 4401
    try:
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{g_code}"):
            pytest.fail("WebSocket must not connect without token")
    except WebSocketDisconnect as e:
        assert e.code == 4401

    # 2. Token sai -> 4403
    try:
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{g_code}?token=WRONG_TOKEN"):
            pytest.fail("WebSocket must not connect with invalid token")
    except WebSocketDisconnect as e:
        assert e.code == 4403

    # 3. Guest token hợp lệ -> Kết nối thành công
    with client.websocket_connect(f"/api/v1/live-chat/ws/client/{g_code}?token={guest_token}"):
        pass

    # 4. Customer JWT hợp lệ -> Kết nối thành công
    with client.websocket_connect(f"/api/v1/live-chat/ws/client/{u_code}?token={jwt_token}"):
        pass

    # 5. Customer JWT kết nối vào phiên của khách vãng lai -> 4403
    try:
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{g_code}?token={jwt_token}"):
            pytest.fail("Customer JWT must not access guest session")
    except WebSocketDisconnect as e:
        assert e.code == 4403

    # 6. Phiên chat đã đóng (CLOSED) -> 4403
    try:
        with client.websocket_connect(f"/api/v1/live-chat/ws/client/{c_code}?token=closed_token"):
            pytest.fail("WebSocket must reject closed sessions")
    except WebSocketDisconnect as e:
        assert e.code == 4403
