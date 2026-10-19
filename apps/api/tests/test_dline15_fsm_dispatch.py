from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.entities import CanonicalProduct, Order, OrderItem, User
from app.models.enums import UserRole
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
from app.services.fulfillment_service import FulfillmentRoutingService


def test_dline15_strict_fsm_and_dispatch():
    with SessionLocal() as db:
        uid = uuid.uuid4().hex[:6].upper()
        now = datetime.now(UTC)

        # 1. Setup Warehouses & Users
        wh1 = Warehouse(name=f"Kho HN {uid}", code=f"WH-HN-{uid}", address="123 Hà Nội", is_active=True)
        wh2 = Warehouse(name=f"Kho SG {uid}", code=f"WH-SG-{uid}", address="456 Sài Gòn", is_active=True)
        db.add_all([wh1, wh2])
        db.commit()

        staff_wh1 = User(email=f"staff1_{uid}@pharmatrust.vn", full_name="Nhân viên Kho 1", password_hash="dummy_hash", role=UserRole.WAREHOUSE_STAFF, warehouse_id=wh1.id, is_active=True)
        staff_wh2 = User(email=f"staff2_{uid}@pharmatrust.vn", full_name="Nhân viên Kho 2", password_hash="dummy_hash", role=UserRole.WAREHOUSE_STAFF, warehouse_id=wh2.id, is_active=True)
        admin = User(email=f"admin_{uid}@pharmatrust.vn", full_name="Quản trị viên", password_hash="dummy_hash", role=UserRole.ADMIN, warehouse_id=None, is_active=True)
        db.add_all([staff_wh1, staff_wh2, admin])
        db.commit()

        # 2. Setup Products & Batches
        prod1 = CanonicalProduct(canonical_name=f"Panadol Extra {uid}")
        prod2 = CanonicalProduct(canonical_name=f"Berberin {uid}")
        db.add_all([prod1, prod2])
        db.commit()

        sku1 = ProductSku(canonical_product_id=prod1.id, sku_code=f"SKU-PAN-{uid}", uom="Hộp", base_price=Decimal("50000"), is_active=True)
        sku2 = ProductSku(canonical_product_id=prod2.id, sku_code=f"SKU-BER-{uid}", uom="Lọ", base_price=Decimal("30000"), is_active=True)
        db.add_all([sku1, sku2])
        db.commit()

        b1 = InventoryBatch(
            sku_id=sku1.id,
            batch_number=f"BATCH-PAN-{uid}",
            status=BatchStatus.ACTIVE,
            manufacture_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
        )
        b2 = InventoryBatch(
            sku_id=sku2.id,
            batch_number=f"BATCH-BER-{uid}",
            status=BatchStatus.ACTIVE,
            manufacture_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
        )
        db.add_all([b1, b2])
        db.commit()

        stock1 = WarehouseBatchStock(warehouse_id=wh1.id, batch_id=b1.id, quantity_on_hand=100, quantity_reserved=10, quantity_available=90)
        stock2 = WarehouseBatchStock(warehouse_id=wh1.id, batch_id=b2.id, quantity_on_hand=50, quantity_reserved=5, quantity_available=45)
        db.add_all([stock1, stock2])
        db.commit()

        # 3. Setup Order with 2 Items
        order = Order(
            order_code=f"ORD-DLINE15-{uid}",
            customer_name="Khách Hàng Test",
            customer_phone="0912345678",
            shipping_address="123 Phố Huế, Hai Bà Trưng, Hà Nội",
            total_amount=Decimal("250000"),
            payment_status="PAID",
            order_status="PENDING",
            fulfillment_status="PENDING",
        )
        db.add(order)
        db.commit()

        oi1 = OrderItem(order_id=order.id, product_id=prod1.id, product_name="Panadol Extra", quantity=10, price=Decimal("50000"), subtotal=Decimal("500000"))
        oi2 = OrderItem(order_id=order.id, product_id=prod2.id, product_name="Berberin", quantity=5, price=Decimal("30000"), subtotal=Decimal("150000"))
        db.add_all([oi1, oi2])
        db.commit()

        # 4. Setup Fulfillment with 2 FulfillmentItems
        ff = OrderFulfillment(
            order_id=order.id,
            warehouse_id=wh1.id,
            fulfillment_code=f"FUL-DLINE15-{uid}",
            status="PENDING",
        )
        db.add(ff)
        db.commit()

        fi1 = FulfillmentItem(fulfillment_id=ff.id, order_item_id=oi1.id, quantity=10)
        fi2 = FulfillmentItem(fulfillment_id=ff.id, order_item_id=oi2.id, quantity=5)
        db.add_all([fi1, fi2])
        db.commit()

        # === TEST 1: Strict Sequential FSM ===
        # Cannot jump PENDING -> PACKED
        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "PACKED", user_id=admin.id)
        assert exc_info.value.status_code == 400
        assert "bắt buộc tuần tự" in exc_info.value.detail

        # Cannot jump PENDING -> SHIPPED
        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=admin.id)
        assert exc_info.value.status_code == 400

        # Step 1: PENDING -> PICKED (valid)
        ff = FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "PICKED", user_id=staff_wh1.id)
        assert ff.status == "PICKED"

        # Cannot jump PICKED -> SHIPPED
        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=admin.id)
        assert exc_info.value.status_code == 400

        # Step 2: PICKED -> PACKED (valid)
        ff = FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "PACKED", user_id=staff_wh1.id)
        assert ff.status == "PACKED"

        # === TEST 2: Warehouse Ownership Check (Chống can thiệp chéo kho) ===
        # Staff of WH2 cannot transition fulfillment of WH1
        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=staff_wh2.id)
        assert exc_info.value.status_code == 403
        assert "không có quyền thao tác trên kho này" in exc_info.value.detail

        # === TEST 3: Pre-SHIPPED Validation Fail-Closed (100% FulfillmentItems must be allocated) ===
        # Hiện tại: CHƯA có allocation nào được tạo cho fi1 và fi2
        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=staff_wh1.id)
        assert exc_info.value.status_code == 400
        assert "chưa được phân bổ đủ lô xuất kho" in exc_info.value.detail
        # Xác nhận: Trạng thái kiện hàng KHÔNG bị chuyển sang SHIPPED, vẫn là PACKED
        db.refresh(ff)
        assert ff.status == "PACKED"

        # Tạo allocation CHỈ cho item 1 (10 đơn vị), item 2 VẪN THIẾU
        alloc1 = OrderItemBatchAllocation(
            fulfillment_item_id=fi1.id,
            order_item_id=oi1.id,
            batch_id=b1.id,
            warehouse_id=wh1.id,
            allocated_quantity=10,
        )
        res1 = StockReservation(
            order_id=order.id,
            batch_id=b1.id,
            warehouse_id=wh1.id,
            quantity=10,
            status="RESERVED",
            expires_at=now + timedelta(hours=24),
        )
        db.add_all([alloc1, res1])
        db.commit()

        # Thử xuất kho khi Item 2 thiếu allocation -> Bị từ chối ngay lập tức
        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=staff_wh1.id)
        assert exc_info.value.status_code == 400
        assert "Berberin" in exc_info.value.detail
        assert "chưa được phân bổ đủ lô xuất kho" in exc_info.value.detail

        # Xác nhận: Không có tồn kho nào bị trừ, trạng thái vẫn là PACKED
        db.refresh(ff)
        db.refresh(stock1)
        db.refresh(res1)
        assert ff.status == "PACKED"
        assert stock1.quantity_on_hand == 100
        assert stock1.quantity_reserved == 10
        assert res1.status == "RESERVED"

        # Bây giờ bổ sung allocation cho Item 2 nhưng số lượng THIẾU (yêu cầu 5, chỉ cấp 3)
        alloc2_partial = OrderItemBatchAllocation(
            fulfillment_item_id=fi2.id,
            order_item_id=oi2.id,
            batch_id=b2.id,
            warehouse_id=wh1.id,
            allocated_quantity=3,
        )
        res2 = StockReservation(
            order_id=order.id,
            batch_id=b2.id,
            warehouse_id=wh1.id,
            quantity=5,
            status="RESERVED",
            expires_at=now + timedelta(hours=24),
        )
        db.add_all([alloc2_partial, res2])
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=staff_wh1.id)
        assert exc_info.value.status_code == 400
        assert "yêu cầu 5, phân bổ 3" in exc_info.value.detail

        # Điều chỉnh allocation Item 2 cho đủ 5
        alloc2_partial.allocated_quantity = 5
        db.commit()

        # === TEST 4: Dispatch Thành công 100% Kiểm định ===
        ff = FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=staff_wh1.id)
        assert ff.status == "SHIPPED"
        assert ff.shipped_at is not None

        # Kiểm tra tồn kho đã bị trừ chính xác
        db.refresh(stock1)
        db.refresh(stock2)
        assert stock1.quantity_on_hand == 90  # 100 - 10
        assert stock1.quantity_reserved == 0   # 10 - 10
        assert stock2.quantity_on_hand == 45  # 50 - 5
        assert stock2.quantity_reserved == 0   # 5 - 5

        # Kiểm tra reservations đã chuyển sang FULFILLED
        db.refresh(res1)
        db.refresh(res2)
        assert res1.status == "FULFILLED"
        assert res2.status == "FULFILLED"

        # Kiểm tra sinh đúng 1 StockMovement loại DISPATCH cho mỗi lô
        movements = db.scalars(
            select(StockMovement).where(
                StockMovement.reference_type == "ORDER_FULFILLMENT",
                StockMovement.reference_id == ff.fulfillment_code,
            )
        ).all()
        assert len(movements) == 2
        for m in movements:
            assert m.movement_type == "DISPATCH"
            assert m.warehouse_id == wh1.id
            assert m.quantity in (-10, -5)

        # === TEST 5: Idempotency (Không trừ tồn lần hai khi gọi lặp lại) ===
        ff_repeat = FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=staff_wh1.id)
        assert ff_repeat.status == "SHIPPED"
        db.refresh(stock1)
        db.refresh(stock2)
        assert stock1.quantity_on_hand == 90
        assert stock2.quantity_on_hand == 45

        repeat_movements = db.scalars(
            select(StockMovement).where(
                StockMovement.reference_type == "ORDER_FULFILLMENT",
                StockMovement.reference_id == ff.fulfillment_code,
            )
        ).all()
        assert len(repeat_movements) == 2  # Vẫn chỉ là 2 bản ghi, không tăng thêm


def test_dline15_conflict_when_dispatch_movement_already_exists_while_packed():
    """Kiểm tra khi đã có StockMovement DISPATCH nhưng kiện hàng vẫn ở trạng thái PACKED thì trả về 409 Conflict."""
    with SessionLocal() as db:
        uid = uuid.uuid4().hex[:6].upper()
        now = datetime.now(UTC)

        wh = Warehouse(name=f"Kho Test {uid}", code=f"WH-CF-{uid}", address="123 Test", is_active=True)
        db.add(wh)
        db.commit()

        staff = User(email=f"staff_{uid}@pharmatrust.vn", full_name="Staff", password_hash="hash", role=UserRole.WAREHOUSE_STAFF, warehouse_id=wh.id, is_active=True)
        db.add(staff)
        db.commit()

        prod = CanonicalProduct(canonical_name=f"Thuốc Test {uid}")
        db.add(prod)
        db.commit()

        sku = ProductSku(canonical_product_id=prod.id, sku_code=f"SKU-CF-{uid}", uom="Hộp", base_price=Decimal("50000"), is_active=True)
        db.add(sku)
        db.commit()

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"BAT-CF-{uid}",
            status=BatchStatus.ACTIVE,
            expiry_date=date(2027, 1, 1),
        )
        db.add(batch)
        db.commit()

        stock = WarehouseBatchStock(warehouse_id=wh.id, batch_id=batch.id, quantity_on_hand=50, quantity_reserved=5, quantity_available=45)
        db.add(stock)
        db.commit()

        order = Order(
            order_code=f"ORD-CF-{uid}",
            customer_name="Cust CF",
            customer_phone="0911222333",
            shipping_address="Hà Nội",
            total_amount=Decimal("250000"),
            payment_status="PAID",
            order_status="PROCESSING",
            fulfillment_status="PENDING",
        )
        db.add(order)
        db.commit()

        oi = OrderItem(order_id=order.id, product_id=prod.id, product_name=prod.canonical_name, quantity=5, price=Decimal("50000"), subtotal=Decimal("250000"))
        db.add(oi)
        db.commit()

        ff = OrderFulfillment(order_id=order.id, warehouse_id=wh.id, fulfillment_code=f"FF-CF-{uid}", status="PACKED")
        db.add(ff)
        db.commit()

        fi = FulfillmentItem(fulfillment_id=ff.id, order_item_id=oi.id, quantity=5)
        alloc = OrderItemBatchAllocation(fulfillment_item_id=fi.id, order_item_id=oi.id, batch_id=batch.id, warehouse_id=wh.id, allocated_quantity=5)
        resv = StockReservation(order_id=order.id, batch_id=batch.id, warehouse_id=wh.id, quantity=5, status="RESERVED", expires_at=now + timedelta(hours=24))
        db.add_all([fi, alloc, resv])
        db.commit()

        # Tạo sẵn StockMovement DISPATCH với reference_id = ff.fulfillment_code (mô phỏng crash/retry giữa chừng)
        existing_mv = StockMovement(
            movement_code=f"MV-DISP-{uid}",
            warehouse_id=wh.id,
            batch_id=batch.id,
            movement_type="DISPATCH",
            quantity=-5,
            balance_after=45,
            reference_type="ORDER_FULFILLMENT",
            reference_id=ff.fulfillment_code,
            idempotency_key=f"DISPATCH:{ff.id}:{batch.id}",
        )
        db.add(existing_mv)
        db.commit()

        # Thử gọi transition sang SHIPPED -> Phải fail-closed với HTTP 409 Conflict
        prev_hand = stock.quantity_on_hand
        with pytest.raises(HTTPException) as exc_info:
            FulfillmentRoutingService.transition_fulfillment_status(db, ff.id, "SHIPPED", user_id=staff.id)
        assert exc_info.value.status_code == 409
        assert "đã tồn tại chứng từ xuất kho" in exc_info.value.detail

        # Đảm bảo không bị trừ tồn kho lần 2
        db.refresh(stock)
        assert stock.quantity_on_hand == prev_hand

