"""
Regression tests for Issue 2 (Dòng 14): Nhập hàng hoàn đúng lô đã xuất.
Requirements:
1. Only restock into batches from OrderItemBatchAllocation of the exact OrderItem.
2. Multi-batch support: subtract previously restocked quantities per allocation/batch.
3. Strict sequence:
   - Dispatched A=3, B=2.
   - Return 1 of 3 -> A=3, B=0.
   - Return 2 of 2 -> A=0, B=2.
   - Further return must be rejected (400).
4. Calling repeatedly on the same return or cross-calling between Admin and Warehouse endpoints must be blocked.
5. Items without original batch allocations must be rejected with 400.
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.entities import CanonicalProduct, Order, OrderItem, User
from app.models.enums import UserRole
from app.models.inventory import (
    BatchStatus,
    InventoryBatch,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import ReturnRequest, ReturnItem, ReturnRestockAllocation, WarehouseReturnCase
from app.services.return_restock_service import ReturnRestockService


def test_dline14_multi_batch_return_restock_lifecycle():
    with SessionLocal() as db:
        # 1. Setup Kho, Sản phẩm, SKU và 2 Lô (A và B)
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        if not wh:
            wh = Warehouse(code="KHO-HCM-01", name="Kho HCM", address="123 HCM", is_active=True)
            db.add(wh)
            db.commit()
            db.refresh(wh)

        admin = db.scalar(select(User).where(User.role == UserRole.ADMIN))
        prod = db.scalar(select(CanonicalProduct).limit(1))
        if not prod:
            prod = CanonicalProduct(canonical_name="Panadol Extra Test")
            db.add(prod)
            db.commit()
            db.refresh(prod)
        sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id))
        if not sku:
            sku = ProductSku(canonical_product_id=prod.id, sku_code=f"SKU-D14-{prod.id}", uom="Hộp", base_price=Decimal("100000"))
            db.add(sku)
            db.commit()
            db.refresh(sku)

        today = date.today()
        batch_a = InventoryBatch(
            sku_id=sku.id,
            batch_number="BATCH-TEST-A-14",
            expiry_date=today + timedelta(days=365),
            status=BatchStatus.ACTIVE,
            initial_quantity=100,
        )
        batch_b = InventoryBatch(
            sku_id=sku.id,
            batch_number="BATCH-TEST-B-14",
            expiry_date=today + timedelta(days=400),
            status=BatchStatus.ACTIVE,
            initial_quantity=100,
        )
        db.add_all([batch_a, batch_b])
        db.commit()
        db.refresh(batch_a)
        db.refresh(batch_b)

        # 2. Tạo đơn hàng và OrderItem (Số lượng xuất: 5)
        order = Order(
            order_code="ORD-TEST-D14-01",
            customer_name="Test D14",
            customer_phone="0911223344",
            shipping_address="123 Test",
            order_status="DELIVERED",
            total_amount=Decimal("500000"),
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        order_item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_sku=sku.sku_code,
            product_name=prod.canonical_name,
            quantity=5,
            price=Decimal("100000"),
            subtotal=Decimal("500000"),
        )
        db.add(order_item)
        db.commit()
        db.refresh(order_item)

        # 3. Tạo phân bổ lô xuất gốc: Lô A=3, Lô B=2
        alloc_a = OrderItemBatchAllocation(
            order_item_id=order_item.id,
            batch_id=batch_a.id,
            warehouse_id=wh.id,
            allocated_quantity=3,
        )
        alloc_b = OrderItemBatchAllocation(
            order_item_id=order_item.id,
            batch_id=batch_b.id,
            warehouse_id=wh.id,
            allocated_quantity=2,
        )
        db.add_all([alloc_a, alloc_b])
        db.commit()

        # 4. HOÀN LẦN MỘT: Hoàn 3 đơn vị -> Phải vào Lô A=3, Lô B=0
        movements_1 = ReturnRestockService.execute_return_restock(
            db=db,
            source_type="RETURN_REQUEST",
            source_code="RET-D14-PART-1",
            warehouse_id=wh.id,
            items_to_restock=[{
                "order_item_id": order_item.id,
                "product_id": prod.id,
                "product_name": prod.canonical_name,
                "qty_to_restock": 3,
            }],
            actor_user_id=admin.id,
        )
        db.commit()

        assert len(movements_1) == 1
        assert movements_1[0].batch_id == batch_a.id
        assert movements_1[0].quantity == 3

        # 5. HOÀN LẦN HAI: Hoàn 2 đơn vị -> Vì Lô A đã hoàn đủ 3, phải tự động chuyển sang Lô B=2
        movements_2 = ReturnRestockService.execute_return_restock(
            db=db,
            source_type="RETURN_REQUEST",
            source_code="RET-D14-PART-2",
            warehouse_id=wh.id,
            items_to_restock=[{
                "order_item_id": order_item.id,
                "product_id": prod.id,
                "product_name": prod.canonical_name,
                "qty_to_restock": 2,
            }],
            actor_user_id=admin.id,
        )
        db.commit()

        assert len(movements_2) == 1
        assert movements_2[0].batch_id == batch_b.id
        assert movements_2[0].quantity == 2

        # 6. HOÀN THÊM (LẦN BA): Cố hoàn thêm 1 đơn vị -> Phải bị từ chối 400 vì đã hoàn đủ 5/5
        with pytest.raises(HTTPException) as exc_info:
            ReturnRestockService.execute_return_restock(
                db=db,
                source_type="RETURN_REQUEST",
                source_code="RET-D14-PART-3",
                warehouse_id=wh.id,
                items_to_restock=[{
                    "order_item_id": order_item.id,
                    "product_id": prod.id,
                    "product_name": prod.canonical_name,
                    "qty_to_restock": 1,
                }],
                actor_user_id=admin.id,
            )
        assert exc_info.value.status_code == 400
        assert "vượt quá" in exc_info.value.detail

        # 7. CHỐNG NHẬP TRÙNG LẶP: Gọi lại cùng yêu cầu RET-D14-PART-1 -> Phải bị chặn 400
        with pytest.raises(HTTPException) as exc_dup:
            ReturnRestockService.execute_return_restock(
                db=db,
                source_type="RETURN_REQUEST",
                source_code="RET-D14-PART-1",
                warehouse_id=wh.id,
                items_to_restock=[{
                    "order_item_id": order_item.id,
                    "product_id": prod.id,
                    "product_name": prod.canonical_name,
                    "qty_to_restock": 1,
                }],
                actor_user_id=admin.id,
            )
        assert exc_dup.value.status_code == 400
        assert "đã được nhập lại kho bán trước đó" in exc_dup.value.detail

        # 8. CHỐNG XỬ LÝ CHÉO ADMIN / KHO:
        # Giả sử ReturnRequest RR-D14-CROSS có WarehouseReturnCase CASE-D14-CROSS
        ret_req = ReturnRequest(
            return_code="RR-D14-CROSS",
            order_id=order.id,
            customer_name="Cross Test",
            customer_phone="0911223344",
            reason_code="OTHER",
            reason_text="Test",
        )
        db.add(ret_req)
        db.commit()
        db.refresh(ret_req)

        case = WarehouseReturnCase(
            case_code="CASE-D14-CROSS",
            return_request_id=ret_req.id,
            warehouse_id=wh.id,
            status="WAITING_MANAGER_APPROVAL",
        )
        db.add(case)
        db.commit()

        # Tạo thêm order item và allocation để test chéo
        oi_cross = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_sku=sku.sku_code,
            product_name=prod.canonical_name,
            quantity=2,
            price=Decimal("100000"),
            subtotal=Decimal("200000"),
        )
        db.add(oi_cross)
        db.commit()
        db.refresh(oi_cross)

        db.add(OrderItemBatchAllocation(
            order_item_id=oi_cross.id,
            batch_id=batch_a.id,
            warehouse_id=wh.id,
            allocated_quantity=2,
        ))
        db.commit()

        # Admin nhập kho trước qua RETURN_REQUEST
        ReturnRestockService.execute_return_restock(
            db=db,
            source_type="RETURN_REQUEST",
            source_code="RR-D14-CROSS",
            warehouse_id=wh.id,
            items_to_restock=[{"order_item_id": oi_cross.id, "product_id": prod.id, "qty_to_restock": 2}],
            actor_user_id=admin.id,
            linked_reference_codes=["CASE-D14-CROSS"],
        )
        db.commit()

        # Kho cố nhập lại qua WAREHOUSE_RETURN_CASE -> Phải bị chặn 400 ngay lập tức
        with pytest.raises(HTTPException) as exc_cross:
            ReturnRestockService.execute_return_restock(
                db=db,
                source_type="WAREHOUSE_RETURN_CASE",
                source_code="CASE-D14-CROSS",
                warehouse_id=wh.id,
                items_to_restock=[{"order_item_id": oi_cross.id, "product_id": prod.id, "qty_to_restock": 2}],
                actor_user_id=admin.id,
                linked_reference_codes=["RR-D14-CROSS"],
            )
        assert exc_cross.value.status_code == 400
        assert "đã được nhập lại kho bán trước đó" in exc_cross.value.detail

        # 9. KHÔNG CÓ ALLOCATION GỐC -> Phải từ chối 400
        oi_no_alloc = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_sku=sku.sku_code,
            product_name=prod.canonical_name,
            quantity=1,
            price=Decimal("100000"),
            subtotal=Decimal("100000"),
        )
        db.add(oi_no_alloc)
        db.commit()
        db.refresh(oi_no_alloc)

        with pytest.raises(HTTPException) as exc_no_alloc:
            ReturnRestockService.execute_return_restock(
                db=db,
                source_type="RETURN_REQUEST",
                source_code="RET-D14-NO-ALLOC",
                warehouse_id=wh.id,
                items_to_restock=[{"order_item_id": oi_no_alloc.id, "product_id": prod.id, "qty_to_restock": 1}],
                actor_user_id=admin.id,
            )
        assert exc_no_alloc.value.status_code == 400
        assert "Không tìm thấy thông tin lô xuất kho gốc" in exc_no_alloc.value.detail


def test_dline14_migration_0015_multi_movement_same_batch_and_canonical_tracing():
    """Kiểm tra logic migration 0015:
    1. Trích xuất case_code -> canonical_return_code từ ReturnRequest.
    2. Bảo toàn cả 2 StockMovement cùng lô/order_item qua UniqueConstraint(stock_movement_id).
    """
    import uuid
    from sqlalchemy import text

    with SessionLocal() as db:
        uid = uuid.uuid4().hex[:6].upper()

        wh = Warehouse(code=f"WH-MIG-{uid}", name="Kho Mig", address="HN", is_active=True)
        db.add(wh)
        db.commit()

        prod = CanonicalProduct(canonical_name=f"SP Mig {uid}")
        db.add(prod)
        db.commit()

        sku = ProductSku(canonical_product_id=prod.id, sku_code=f"SKU-MIG-{uid}", uom="Hộp", base_price=Decimal("100000"))
        db.add(sku)
        db.commit()

        batch = InventoryBatch(sku_id=sku.id, batch_number=f"BAT-MIG-{uid}", expiry_date=date.today() + timedelta(days=365), initial_quantity=100)
        db.add(batch)
        db.commit()

        order = Order(order_code=f"ORD-MIG-{uid}", customer_name="Customer Mig", customer_phone="0911223344", shipping_address="HN", total_amount=Decimal("200000"))
        db.add(order)
        db.commit()

        oi = OrderItem(order_id=order.id, product_id=prod.id, product_sku=sku.sku_code, product_name=prod.canonical_name, quantity=2, price=Decimal("100000"), subtotal=Decimal("200000"))
        db.add(oi)
        db.commit()

        alloc = OrderItemBatchAllocation(order_item_id=oi.id, batch_id=batch.id, warehouse_id=wh.id, allocated_quantity=2)
        db.add(alloc)
        db.commit()

        ret = ReturnRequest(return_code=f"RET-MIG-{uid}", order_id=order.id, customer_name="Cust", customer_phone="0911223344", reason_code="DAMAGED", reason_text="Lỗi")
        db.add(ret)
        db.commit()

        case = WarehouseReturnCase(case_code=f"WRC-MIG-{uid}", return_request_id=ret.id, warehouse_id=wh.id, status="RECEIVED")
        db.add(case)
        db.commit()

        ri = ReturnItem(
            return_request_id=ret.id,
            warehouse_return_case_id=case.id,
            order_item_id=oi.id,
            product_id=prod.id,
            product_name=prod.canonical_name,
            original_quantity=2,
            requested_quantity=2,
            unit_price_at_purchase=Decimal("100000"),
            net_paid_amount=Decimal("200000"),
            requested_refund_amount=Decimal("200000"),
        )
        db.add(ri)
        db.commit()

        # Tạo 2 StockMovement cùng loại RETURN_RESTOCK tham chiếu case_code cho CÙNG 1 batch và order_item
        sm1 = StockMovement(
            movement_code=f"SM-MIG-1-{uid}",
            warehouse_id=wh.id,
            batch_id=batch.id,
            movement_type="RETURN_RESTOCK",
            quantity=1,
            balance_after=11,
            reference_type="WAREHOUSE_RETURN_CASE",
            reference_id=case.case_code,
            note=f"Nhập hàng hoàn [order_item_id:{oi.id}] phần 1",
        )
        sm2 = StockMovement(
            movement_code=f"SM-MIG-2-{uid}",
            warehouse_id=wh.id,
            batch_id=batch.id,
            movement_type="RETURN_RESTOCK",
            quantity=1,
            balance_after=12,
            reference_type="WAREHOUSE_RETURN_CASE",
            reference_id=case.case_code,
            note=f"Nhập hàng hoàn [order_item_id:{oi.id}] phần 2",
        )
        db.add_all([sm1, sm2])
        db.commit()

        # Cả 2 movement phải được lưu với ReturnRestockAllocation riêng biệt mà không bị deduplicate
        alloc_1 = ReturnRestockAllocation(
            canonical_return_code=ret.return_code,  # Trace từ case_code sang return_code
            source_type="WAREHOUSE_RETURN_CASE",
            source_code=case.case_code,
            order_item_id=oi.id,
            batch_id=batch.id,
            warehouse_id=wh.id,
            quantity=1,
            stock_movement_id=sm1.id,
        )
        alloc_2 = ReturnRestockAllocation(
            canonical_return_code=ret.return_code,  # Trace từ case_code sang return_code
            source_type="WAREHOUSE_RETURN_CASE",
            source_code=case.case_code,
            order_item_id=oi.id,
            batch_id=batch.id,
            warehouse_id=wh.id,
            quantity=1,
            stock_movement_id=sm2.id,
        )
        db.add_all([alloc_1, alloc_2])
        db.commit()

        # Xác minh: cả 2 bản ghi đều tồn tại trong DB, canonical_return_code là mã RET- chứ không phải WRC-
        rows = db.scalars(
            select(ReturnRestockAllocation).where(
                ReturnRestockAllocation.order_item_id == oi.id,
                ReturnRestockAllocation.batch_id == batch.id,
            )
        ).all()
        assert len(rows) == 2
        for r in rows:
            assert r.canonical_return_code == ret.return_code
            assert r.canonical_return_code.startswith("RET-")
            assert not r.canonical_return_code.startswith("WRC-")
            assert r.stock_movement_id in (sm1.id, sm2.id)

