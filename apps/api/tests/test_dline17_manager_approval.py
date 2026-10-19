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
    InventoryBatch,
    OrderItemBatchAllocation,
    ProductSku,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import ReturnInspection, ReturnItem, ReturnRequest, ReturnStatus, WarehouseReturnCase
from app.services.warehouse_return_service import WarehouseReturnService


def test_dline17_manager_approval_rules():
    with SessionLocal() as db:
        uid = uuid.uuid4().hex[:6].upper()
        now = datetime.now(UTC)

        wh = Warehouse(name=f"Kho D17 {uid}", code=f"WH-D17-{uid}", address="789 Nguyễn Trãi, Hà Nội", is_active=True)
        db.add(wh)
        db.commit()

        manager = User(
            email=f"manager_{uid}@pharmatrust.vn",
            full_name="Quản lý Kho Test",
            password_hash="dummy_hash",
            role=UserRole.WAREHOUSE_MANAGER,
            warehouse_id=wh.id,
            is_active=True,
        )
        db.add(manager)
        db.commit()

        prod1 = CanonicalProduct(canonical_name=f"Thuốc D17 A {uid}")
        prod2 = CanonicalProduct(canonical_name=f"Thuốc D17 B {uid}")
        db.add_all([prod1, prod2])
        db.commit()

        sku1 = ProductSku(canonical_product_id=prod1.id, sku_code=f"SKU-D17A-{uid}", uom="Hộp", base_price=Decimal("100000"), is_active=True)
        sku2 = ProductSku(canonical_product_id=prod2.id, sku_code=f"SKU-D17B-{uid}", uom="Lọ", base_price=Decimal("200000"), is_active=True)
        db.add_all([sku1, sku2])
        db.commit()

        b1 = InventoryBatch(sku_id=sku1.id, batch_number=f"BATCH-D17A-{uid}", status=BatchStatus.ACTIVE, expiry_date=date(2027, 1, 1))
        b2 = InventoryBatch(sku_id=sku2.id, batch_number=f"BATCH-D17B-{uid}", status=BatchStatus.ACTIVE, expiry_date=date(2027, 1, 1))
        db.add_all([b1, b2])
        db.commit()

        stock1 = WarehouseBatchStock(warehouse_id=wh.id, batch_id=b1.id, quantity_on_hand=50, quantity_reserved=0, quantity_available=50)
        stock2 = WarehouseBatchStock(warehouse_id=wh.id, batch_id=b2.id, quantity_on_hand=50, quantity_reserved=0, quantity_available=50)
        db.add_all([stock1, stock2])
        db.commit()

        order = Order(
            order_code=f"ORD-D17-{uid}",
            customer_name="Khách Hàng D17",
            customer_phone="0988776655",
            shipping_address="789 Nguyễn Trãi, Thanh Xuân, Hà Nội",
            total_amount=Decimal("500000"),
            payment_status="PAID",
            order_status="DELIVERED",
            fulfillment_status="DELIVERED",
            assigned_warehouse_id=wh.id,
        )
        db.add(order)
        db.commit()

        oi1 = OrderItem(order_id=order.id, product_id=prod1.id, product_name="Thuốc D17 A", quantity=3, price=Decimal("100000"), subtotal=Decimal("300000"))
        oi2 = OrderItem(order_id=order.id, product_id=prod2.id, product_name="Thuốc D17 B", quantity=1, price=Decimal("200000"), subtotal=Decimal("200000"))
        db.add_all([oi1, oi2])
        db.commit()

        alloc1 = OrderItemBatchAllocation(order_item_id=oi1.id, batch_id=b1.id, warehouse_id=wh.id, allocated_quantity=3)
        alloc2 = OrderItemBatchAllocation(order_item_id=oi2.id, batch_id=b2.id, warehouse_id=wh.id, allocated_quantity=1)
        db.add_all([alloc1, alloc2])
        db.commit()

        ret = ReturnRequest(
            return_code=f"RET-D17-{uid}",
            order_id=order.id,
            customer_name="Khách Hàng D17",
            customer_phone="0988776655",
            reason_code="DAMAGED",
            reason_text="Bị hỏng khi giao",
            status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
            request_type="REFUND",
        )
        db.add(ret)
        db.commit()

        case = WarehouseReturnCase(
            case_code=f"WRC-D17-{uid}",
            return_request_id=ret.id,
            warehouse_id=wh.id,
            status=ReturnStatus.WAITING_MANAGER_APPROVAL.value,
        )
        db.add(case)
        db.commit()

        ri1 = ReturnItem(
            return_request_id=ret.id,
            warehouse_return_case_id=case.id,
            order_item_id=oi1.id,
            product_id=prod1.id,
            product_name="Thuốc D17 A",
            original_quantity=3,
            requested_quantity=3,
            received_quantity=3,  # Đã nhận 3
            approved_quantity=0,
            unit_price_at_purchase=Decimal("100000"),
            net_paid_amount=Decimal("300000"),
            requested_refund_amount=Decimal("300000"),
        )
        ri2 = ReturnItem(
            return_request_id=ret.id,
            warehouse_return_case_id=case.id,
            order_item_id=oi2.id,
            product_id=prod2.id,
            product_name="Thuốc D17 B",
            original_quantity=1,
            requested_quantity=1,
            received_quantity=0,  # Chưa nhận (received = 0)
            approved_quantity=0,
            unit_price_at_purchase=Decimal("200000"),
            net_paid_amount=Decimal("200000"),
            requested_refund_amount=Decimal("200000"),
        )
        db.add_all([ri1, ri2])
        db.commit()

        # === TEST 1: Bắt buộc payload items không được rỗng ({}) ===
        with pytest.raises(HTTPException) as exc_info:
            WarehouseReturnService.manager_approve_case(
                db=db,
                case_code=case.case_code,
                manager_user=manager,
                warehouse_id=wh.id,
                items_approval=[],
            )
        assert exc_info.value.status_code == 400
        assert "Tuyệt đối không tự động duyệt khi thiếu dữ liệu" in exc_info.value.detail

        # === TEST 2: Chặn trùng lặp return_item_id trong items_approval ===
        with pytest.raises(HTTPException) as exc_info:
            WarehouseReturnService.manager_approve_case(
                db=db,
                case_code=case.case_code,
                manager_user=manager,
                warehouse_id=wh.id,
                items_approval=[
                    {"return_item_id": ri1.id, "approved_quantity": 2, "rejected_quantity": 1, "rejection_reason": "Bao bì rách"},
                    {"return_item_id": ri1.id, "approved_quantity": 1, "rejected_quantity": 2, "rejection_reason": "Bao bì rách"},
                ],
            )
        assert exc_info.value.status_code == 400
        assert "trùng lặp" in exc_info.value.detail

        # === TEST 3: Bắt buộc có mặt 100% ReturnItems của ca hoàn ===
        with pytest.raises(HTTPException) as exc_info:
            WarehouseReturnService.manager_approve_case(
                db=db,
                case_code=case.case_code,
                manager_user=manager,
                warehouse_id=wh.id,
                items_approval=[
                    {"return_item_id": ri1.id, "approved_quantity": 2, "rejected_quantity": 1, "rejection_reason": "Bao bì rách"},
                ],  # Thiếu ri2
            )
        assert exc_info.value.status_code == 400
        assert "Thiếu thông tin phê duyệt cho sản phẩm" in exc_info.value.detail

        # === TEST 4: approved_quantity + rejected_quantity != received_quantity ===
        # ri1 có received_quantity = 3, gửi approved = 2, rejected = 0 (tổng = 2 != 3) -> 400
        with pytest.raises(HTTPException) as exc_info:
            WarehouseReturnService.manager_approve_case(
                db=db,
                case_code=case.case_code,
                manager_user=manager,
                warehouse_id=wh.id,
                items_approval=[
                    {"return_item_id": ri1.id, "approved_quantity": 2, "rejected_quantity": 0},
                    {"return_item_id": ri2.id, "approved_quantity": 0, "rejected_quantity": 0},
                ],
            )
        assert exc_info.value.status_code == 400
        assert "phải bằng đúng số lượng thực nhận" in exc_info.value.detail

        # === TEST 5: approved_quantity > received_quantity ===
        # ri1 có received = 3, gửi approved = 4 -> 400
        with pytest.raises(HTTPException) as exc_info:
            WarehouseReturnService.manager_approve_case(
                db=db,
                case_code=case.case_code,
                manager_user=manager,
                warehouse_id=wh.id,
                items_approval=[
                    {"return_item_id": ri1.id, "approved_quantity": 4, "rejected_quantity": -1},
                    {"return_item_id": ri2.id, "approved_quantity": 0, "rejected_quantity": 0},
                ],
            )
        assert exc_info.value.status_code == 400

        # === TEST 6: received_quantity == 0 thì approved_quantity bắt buộc = 0 ===
        # ri2 có received = 0, nếu quản lý thử duyệt approved = 1 -> 400
        with pytest.raises(HTTPException) as exc_info:
            WarehouseReturnService.manager_approve_case(
                db=db,
                case_code=case.case_code,
                manager_user=manager,
                warehouse_id=wh.id,
                items_approval=[
                    {"return_item_id": ri1.id, "approved_quantity": 3, "rejected_quantity": 0},
                    {"return_item_id": ri2.id, "approved_quantity": 1, "rejected_quantity": -1},
                ],
            )
        assert exc_info.value.status_code == 400

        # === TEST 7: rejected_quantity > 0 bắt buộc có rejection_reason ===
        with pytest.raises(HTTPException) as exc_info:
            WarehouseReturnService.manager_approve_case(
                db=db,
                case_code=case.case_code,
                manager_user=manager,
                warehouse_id=wh.id,
                items_approval=[
                    {"return_item_id": ri1.id, "approved_quantity": 2, "rejected_quantity": 1, "rejection_reason": ""},
                    {"return_item_id": ri2.id, "approved_quantity": 0, "rejected_quantity": 0},
                ],
            )
        assert exc_info.value.status_code == 400
        assert "rejection_reason" in exc_info.value.detail

        # === TEST 8: Phê duyệt hợp lệ 100% ===
        # ri1: received 3 -> duyệt 2, từ chối 1 (lý do "Bao bì rách vỡ")
        # ri2: received 0 -> duyệt 0, từ chối 0
        approved_case = WarehouseReturnService.manager_approve_case(
            db=db,
            case_code=case.case_code,
            manager_user=manager,
            warehouse_id=wh.id,
            items_approval=[
                {"return_item_id": ri1.id, "approved_quantity": 2, "rejected_quantity": 1, "rejection_reason": "Bao bì rách vỡ"},
                {"return_item_id": ri2.id, "approved_quantity": 0, "rejected_quantity": 0},
            ],
            manager_note="Quản lý duyệt 2 hộp SP A, từ chối 1 hộp SP A do rách bao bì.",
        )

        db.refresh(approved_case)
        db.refresh(ri1)
        db.refresh(ri2)

        assert approved_case.status == ReturnStatus.REFUND_PENDING.value
        assert ri1.approved_quantity == 2
        assert ri1.rejected_quantity == 1
        # Tiền hoàn tính chính xác: 2 * 100,000 = 200,000
        assert ri1.approved_refund_amount == Decimal("200000.00")
        assert ri2.approved_quantity == 0
        assert ri2.approved_refund_amount == Decimal("0.00")
