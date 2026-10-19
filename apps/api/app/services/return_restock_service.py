from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import User
from app.models.inventory import (
    InventoryBatch,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    WarehouseBatchStock,
)
from app.models.returns import ReturnItem, ReturnStatus
from app.services.audit import write_audit

logger = logging.getLogger("return_restock")


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReturnRestockService:
    """
    Dịch vụ dùng chung duy nhất thực thi nhập kho hàng hoàn (Restock) cho cả Admin và Quản lý kho.
    Bảo đảm:
    - Thuật toán phân bổ đa lô (Multi-batch) chính xác.
    - Tiền kiểm định (Pre-validation) 100% trước khi sửa đổi bất kỳ số liệu tồn kho nào.
    - Chống nhập trùng lặp hai chiều (Two-way Idempotency).
    - Kiểm tra giới hạn số lượng hoàn lũy kế.
    - Sinh StockMovement loại RETURN_RESTOCK và WarehouseAuditLog đầy đủ.
    """

    @classmethod
    def execute_return_restock(
        cls,
        db: Session,
        source_type: str,  # "RETURN_REQUEST" | "WAREHOUSE_RETURN_CASE"
        source_code: str,
        warehouse_id: int,
        items_to_restock: list[dict[str, Any]],
        actor_user_id: int,
        audit_note: str | None = None,
        linked_reference_codes: list[str] | None = None,
    ) -> list[StockMovement]:
        if not items_to_restock:
            return []

        # 1. Chống nhập trùng hai chiều (Two-way Idempotency check)
        check_codes = [source_code]
        if linked_reference_codes:
            check_codes.extend([c for c in linked_reference_codes if c])

        existing_mv = db.scalar(
            select(StockMovement).where(
                StockMovement.movement_type == "RETURN_RESTOCK",
                or_(
                    and_(
                        StockMovement.reference_type == source_type,
                        StockMovement.reference_id == source_code,
                    ),
                    StockMovement.reference_id.in_(check_codes),
                ),
            )
        )
        if existing_mv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chứng từ hoàn '{source_code}' hoặc ca hoàn liên quan đã được nhập lại kho bán trước đó. Không thể thực hiện nhập kho lần hai.",
            )

        # 2. Tiền kiểm định toàn bộ items TRƯỚC KHI cập nhật bất kỳ bản ghi nào
        plans: list[dict[str, Any]] = []

        for it in items_to_restock:
            qty_restock = it.get("qty_to_restock", 0)
            if qty_restock <= 0:
                continue

            order_item_id = it.get("order_item_id")
            product_id = it.get("product_id")
            product_name = it.get("product_name") or f"Sản phẩm #{product_id}"

            if not order_item_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Thiếu thông tin order_item_id cho sản phẩm '{product_name}'.",
                )

            # Lấy tất cả OrderItemBatchAllocation của order_item này
            allocations = db.scalars(
                select(OrderItemBatchAllocation)
                .where(OrderItemBatchAllocation.order_item_id == order_item_id)
                .order_by(OrderItemBatchAllocation.id.asc())
            ).all()

            if not allocations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Không tìm thấy thông tin lô xuất kho gốc cho sản phẩm {product_name} (order_item #{order_item_id}). Không thể nhập lại kho bán được để đảm bảo toàn vẹn dữ liệu thuốc.",
                )

            grouped_allocations: list[dict[str, Any]] = []
            seen_batches: dict[int, dict[str, Any]] = {}

            for alloc in allocations:
                if not alloc.batch_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Thông tin phân bổ lô xuất kho bị thiếu batch_id cho sản phẩm #{product_name}.",
                    )

                batch = db.scalar(select(InventoryBatch).where(InventoryBatch.id == alloc.batch_id))
                if not batch:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Lô xuất gốc #{alloc.batch_id} không tồn tại trong hệ thống.",
                    )

                sku = db.scalar(select(ProductSku).where(ProductSku.id == batch.sku_id))
                if not sku or (product_id and sku.canonical_product_id != product_id):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Lô xuất gốc #{alloc.batch_id} (SKU #{batch.sku_id}) không thuộc sản phẩm #{product_id} ({product_name}).",
                    )

                # Kho của lô xuất gốc phải khớp đúng với kho tiếp nhận hàng hoàn
                if alloc.warehouse_id != warehouse_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Kho của lô xuất gốc #{alloc.batch_id} (Kho #{alloc.warehouse_id}) không khớp với kho tiếp nhận hàng hoàn (Kho #{warehouse_id}).",
                    )

                # Gộp allocation nếu cùng lô xuất hiện nhiều lần
                if alloc.batch_id not in seen_batches:
                    entry = {
                        "batch_id": alloc.batch_id,
                        "warehouse_id": alloc.warehouse_id,
                        "allocated_quantity": alloc.allocated_quantity,
                    }
                    seen_batches[alloc.batch_id] = entry
                    grouped_allocations.append(entry)
                else:
                    seen_batches[alloc.batch_id]["allocated_quantity"] += alloc.allocated_quantity

            total_allocated = sum(g["allocated_quantity"] for g in grouped_allocations)

            # Kiểm tra số lượng hoàn lần này so với số lượng xuất
            if qty_restock > total_allocated:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số lượng hoàn ({qty_restock}) vượt quá tổng số lượng đã xuất từ các lô gốc ({total_allocated}) cho sản phẩm '{product_name}'.",
                )

            # Kiểm tra giới hạn hoàn lũy kế (tổng số lượng đã hoàn từ trước đến nay + lần này không được vượt quá số lượng đã xuất)
            prior_restocked_query = (
                select(func.coalesce(func.sum(ReturnItem.restock_quantity), 0))
                .where(
                    ReturnItem.order_item_id == order_item_id,
                    ReturnItem.restock_quantity > 0,
                )
            )
            ret_item_id = it.get("return_item_id")
            if ret_item_id:
                prior_restocked_query = prior_restocked_query.where(ReturnItem.id != ret_item_id)

            prior_restocked = db.scalar(prior_restocked_query) or 0
            if (prior_restocked + qty_restock) > total_allocated:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tổng số lượng hoàn lũy kế ({prior_restocked + qty_restock}) vượt quá tổng số lượng đã xuất từ các lô gốc ({total_allocated}) cho sản phẩm '{product_name}'.",
                )

            plans.append({
                "it": it,
                "qty_restock": qty_restock,
                "grouped_allocations": grouped_allocations,
            })

        # 3. Thực thi cập nhật tồn kho (chỉ chạy khi toàn bộ tiền kiểm định pass 100%)
        created_movements: list[StockMovement] = []
        for plan in plans:
            qty_restock = plan["qty_restock"]
            grouped_allocations = plan["grouped_allocations"]
            item_info = plan["it"]

            remaining_qty = qty_restock
            for g in grouped_allocations:
                if remaining_qty <= 0:
                    break
                portion = min(remaining_qty, g["allocated_quantity"])
                remaining_qty -= portion

                # Cập nhật WarehouseBatchStock
                stock = db.scalar(
                    select(WarehouseBatchStock).where(
                        WarehouseBatchStock.warehouse_id == warehouse_id,
                        WarehouseBatchStock.batch_id == g["batch_id"],
                    )
                )
                if stock:
                    stock.quantity_on_hand += portion
                    stock.quantity_available += portion
                    db.add(stock)
                else:
                    stock = WarehouseBatchStock(
                        warehouse_id=warehouse_id,
                        batch_id=g["batch_id"],
                        quantity_on_hand=portion,
                        quantity_available=portion,
                        quantity_reserved=0,
                    )
                    db.add(stock)

                # Sinh bản ghi StockMovement
                movement = StockMovement(
                    movement_code=f"MOV-RET-{uuid.uuid4().hex[:6].upper()}",
                    batch_id=g["batch_id"],
                    warehouse_id=warehouse_id,
                    movement_type="RETURN_RESTOCK",
                    quantity=portion,
                    balance_after=stock.quantity_on_hand,
                    reference_type=source_type,
                    reference_id=source_code,
                    note=audit_note or f"Nhập lại kho bán {portion} hộp thuốc từ hoàn trả ({source_code})",
                    created_by=actor_user_id,
                    created_at=utcnow(),
                )
                db.add(movement)
                created_movements.append(movement)

                # Ghi nhận AuditLog
                actor = db.scalar(select(User).where(User.id == actor_user_id)) if actor_user_id else None
                write_audit(
                    db=db,
                    action="RETURN_RESTOCK",
                    entity_type=source_type,
                    entity_id=source_code,
                    user=actor,
                    details=f"Nhập lại kho bán {portion} đơn vị sản phẩm #{item_info.get('product_id')} ({item_info.get('product_name')}) vào lô #{g['batch_id']}.",
                )

        return created_movements
