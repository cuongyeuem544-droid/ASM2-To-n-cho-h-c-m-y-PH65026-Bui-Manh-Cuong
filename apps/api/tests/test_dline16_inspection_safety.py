from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import uuid
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
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
from app.models.returns import ReturnItem, ReturnRequest, ReturnStatus, WarehouseReturnCase
from app.api.admin_returns import ItemInspectionPayload
from app.api.warehouse_orders_returns import ItemInspectionItem
from app.services.return_service import ReturnService
from app.services.warehouse_return_service import WarehouseReturnService


def test_dline16_pydantic_schema_missing_fields_fail_422():
    # 1. Thiếu seal_intact -> ValidationError (422)
    with pytest.raises(ValidationError):
        ItemInspectionPayload.model_validate({
            "return_item_id": 1,
            "condition": "GOOD_CONDITION",
            "package_condition": "SEALED",
            # thiếu seal_intact
            "batch_matched": True,
            "expiry_matched": True,
            "storage_condition_ok": True,
            "accepted_quantity": 1,
            "rejected_quantity": 0,
            "restock_destination": "SELLABLE_STOCK",
            "restock_quantity": 1,
        })

    # 2. Thiếu package_condition và condition -> ValidationError (422)
    with pytest.raises(ValidationError):
        ItemInspectionItem.model_validate({
            "return_item_id": 1,
            "received_quantity": 1,
            "accepted_quantity": 1,
            "rejected_quantity": 0,
            "seal_intact": True,
            "batch_matched": True,
            "expiry_matched": True,
            "storage_condition_ok": True,
            "suggested_action": "RESTOCK",
        })

    # 3. rejected_quantity > 0 nhưng thiếu rejection_reason -> ValidationError (422)
    with pytest.raises(ValidationError):
        ItemInspectionPayload.model_validate({
            "return_item_id": 1,
            "condition": "DAMAGED",
            "package_condition": "DAMAGED",
            "seal_intact": False,
            "batch_matched": True,
            "expiry_matched": True,
            "storage_condition_ok": True,
            "accepted_quantity": 0,
            "rejected_quantity": 1,
            "restock_destination": "QUARANTINE",
            # thiếu rejection_reason
        })

    # 4. seal_intact=False nhưng chọn SELLABLE_STOCK / RESTOCK -> ValidationError (422)
    with pytest.raises(ValidationError):
        ItemInspectionPayload.model_validate({
            "return_item_id": 1,
            "condition": "SEALED",
            "package_condition": "SEALED",
            "seal_intact": False,  # Tiêu chí an toàn vi phạm
            "batch_matched": True,
            "expiry_matched": True,
            "storage_condition_ok": True,
            "accepted_quantity": 1,
            "rejected_quantity": 0,
            "restock_destination": "SELLABLE_STOCK",
            "restock_quantity": 1,
        })


def test_dline16_technical_inspection_does_not_approve_or_refund():
    with SessionLocal() as db:
        uid = uuid.uuid4().hex[:6].upper()
        now = datetime.now(UTC)

        wh = Warehouse(name=f"Kho D16 {uid}", code=f"WH-D16-{uid}", address="123 Đội Cấn, Hà Nội", is_active=True)
        db.add(wh)
        db.commit()

        pharmacist = User(
            email=f"pharma_{uid}@pharmatrust.vn",
            full_name="Dược sĩ Test",
            password_hash="dummy_hash",
            role=UserRole.PHARMACIST,
            warehouse_id=wh.id,
            is_active=True,
        )
        db.add(pharmacist)
        db.commit()

        prod = CanonicalProduct(canonical_name=f"Thuốc D16 {uid}")
        db.add(prod)
        db.commit()

        sku = ProductSku(canonical_product_id=prod.id, sku_code=f"SKU-D16-{uid}", uom="Hộp", base_price=Decimal("100000"), is_active=True)
        db.add(sku)
        db.commit()

        batch = InventoryBatch(
            sku_id=sku.id,
            batch_number=f"BATCH-D16-{uid}",
            status=BatchStatus.ACTIVE,
            manufacture_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
        )
        db.add(batch)
        db.commit()

        stock = WarehouseBatchStock(warehouse_id=wh.id, batch_id=batch.id, quantity_on_hand=50, quantity_reserved=0, quantity_available=50)
        db.add(stock)
        db.commit()

        order = Order(
            order_code=f"ORD-D16-{uid}",
            customer_name="Khách Hàng D16",
            customer_phone="0911223344",
            shipping_address="123 Đội Cấn, Ba Đình, Hà Nội",
            total_amount=Decimal("200000"),
            payment_status="PAID",
            order_status="DELIVERED",
            fulfillment_status="DELIVERED",
            assigned_warehouse_id=wh.id,
        )
        db.add(order)
        db.commit()

        oi = OrderItem(order_id=order.id, product_id=prod.id, product_name="Thuốc D16", quantity=2, price=Decimal("100000"), subtotal=Decimal("200000"))
        db.add(oi)
        db.commit()

        alloc = OrderItemBatchAllocation(order_item_id=oi.id, batch_id=batch.id, warehouse_id=wh.id, allocated_quantity=2)
        db.add(alloc)
        db.commit()

        ret = ReturnRequest(
            return_code=f"RET-D16-{uid}",
            order_id=order.id,
            customer_name="Khách Hàng D16",
            customer_phone="0911223344",
            reason_code="DAMAGED",
            reason_text="Bị hỏng khi giao",
            status=ReturnStatus.RECEIVED.value,
            request_type="REFUND",
        )
        db.add(ret)
        db.commit()

        ri = ReturnItem(
            return_request_id=ret.id,
            order_item_id=oi.id,
            product_id=prod.id,
            product_name="Thuốc D16",
            original_quantity=2,
            requested_quantity=2,
            unit_price_at_purchase=Decimal("100000"),
            net_paid_amount=Decimal("200000"),
            requested_refund_amount=Decimal("200000"),
            approved_quantity=0,
            received_quantity=2,
        )
        db.add(ri)
        db.commit()

        # Thực hiện kiểm định kỹ thuật (Inspect)
        payload = [{
            "return_item_id": ri.id,
            "condition": "GOOD_CONDITION",
            "package_condition": "SEALED",
            "seal_intact": True,
            "batch_matched": True,
            "expiry_matched": True,
            "storage_condition_ok": True,
            "accepted_quantity": 2,
            "rejected_quantity": 0,
            "restock_destination": "SELLABLE_STOCK",
            "restock_quantity": 2,
            "rejection_reason": None,
        }]

        ret_after = ReturnService.inspect_return_items(
            db=db,
            return_code=ret.return_code,
            inspector_user=pharmacist,
            inspection_payload=payload,
            general_inspection_note="Kiểm định kỹ thuật đạt chuẩn GSP",
        )

        db.refresh(ret_after)
        db.refresh(ri)

        # 1. Trạng thái KHÔNG được tự ý chuyển sang REFUND_PENDING mà phải là WAITING_MANAGER_APPROVAL
        assert ret_after.status == ReturnStatus.WAITING_MANAGER_APPROVAL.value
        assert ret_after.status != ReturnStatus.REFUND_PENDING.value

        # 2. approved_quantity KHÔNG được tự ý gán bởi kiểm định kỹ thuật (phải là 0 cho đến khi Quản lý duyệt)
        assert ri.approved_quantity == 0
        assert ri.approved_refund_amount == Decimal("0.0")
