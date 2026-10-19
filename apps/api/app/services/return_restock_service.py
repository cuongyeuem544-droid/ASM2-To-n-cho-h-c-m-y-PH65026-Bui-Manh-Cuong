from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import User
from app.models.inventory import (
    InventoryBatch,
    OrderItemBatchAllocation,
    ProductSku,
    StockMovement,
    WarehouseBatchStock,
)
from app.models.returns import ReturnItem, ReturnRestockAllocation, ReturnStatus
from app.services.audit import write_audit

logger = logging.getLogger("return_restock")


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReturnRestockService:
    """
    Dịch vụ dùng chung duy nhất thực thi nhập kho hàng hoàn (Restock) cho cả Admin và Quản lý kho.
    Bảo đảm:
    - Thuật toán phân bổ đa lô (Multi-batch) chính xác: trừ lượng đã hoàn trước đó theo từng allocation/batch,
      không phân bổ lại từ batch đầu ở mỗi lần hoàn.
    - Tiền kiểm định (Pre-validation) 100% trước khi sửa đổi bất kỳ số liệu tồn kho nào.
    - Chống nhập trùng lặp hai chiều (Two-way Idempotency) và ràng buộc bền vững trong CSDL (ReturnRestockAllocation).
    - Kiểm tra giới hạn số lượng hoàn lũy kế của từng lô.
    - Sinh StockMovement loại RETURN_RESTOCK và WarehouseAuditLog đầy đủ trong cùng transaction.
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

        # 1. Xác định canonical_return_code và danh sách mã đối soát chéo (Admin / Kho)
        canonical_return_code = source_code
        check_codes = [source_code]
        if linked_reference_codes:
            check_codes.extend([c for c in linked_reference_codes if c])

        from app.models.returns import WarehouseReturnCase
        if source_type == "WAREHOUSE_RETURN_CASE":
            case_obj = db.scalar(
                select(WarehouseReturnCase).where(WarehouseReturnCase.case_code == source_code)
            )
            if case_obj and case_obj.return_request:
                canonical_return_code = case_obj.return_request.return_code
                if canonical_return_code not in check_codes:
                    check_codes.append(canonical_return_code)
        elif source_type == "RETURN_REQUEST":
            cases = db.scalars(
                select(WarehouseReturnCase).where(
                    WarehouseReturnCase.return_request.has(return_code=source_code)
                )
            ).all()
            for c in cases:
                if c.case_code not in check_codes:
                    check_codes.append(c.case_code)

        # 2. Chống nhập trùng hai chiều (Two-way Idempotency check)
        existing_alloc = db.scalar(
            select(ReturnRestockAllocation).where(
                or_(
                    ReturnRestockAllocation.canonical_return_code == canonical_return_code,
                    ReturnRestockAllocation.source_code.in_(check_codes),
                )
            )
        )
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
        if existing_alloc or existing_mv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chứng từ hoàn '{source_code}' hoặc ca hoàn liên quan đã được nhập lại kho bán trước đó. Không thể thực hiện nhập kho lần hai.",
            )

        # 3. Tiền kiểm định toàn bộ items TRƯỚC KHI cập nhật bất kỳ bản ghi nào
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

                # Gộp allocation nếu cùng lô xuất hiện nhiều lần trong cùng order item
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

            # Lấy lượng đã hoàn trước đó theo TỪNG BATCH của order_item này
            prior_alloc_rows = db.execute(
                select(ReturnRestockAllocation.batch_id, func.sum(ReturnRestockAllocation.quantity))
                .where(ReturnRestockAllocation.order_item_id == order_item_id)
                .group_by(ReturnRestockAllocation.batch_id)
            ).all()
            prior_by_batch: dict[int, int] = {row[0]: int(row[1]) for row in prior_alloc_rows}

            # Đối soát thêm với StockMovement của các lần hoàn trước đó nếu có (hỗ trợ dữ liệu lịch sử)
            prior_movements = db.scalars(
                select(StockMovement).where(
                    StockMovement.movement_type == "RETURN_RESTOCK",
                    StockMovement.batch_id.in_([g["batch_id"] for g in grouped_allocations]),
                    StockMovement.note.like(f"%[order_item_id:{order_item_id}]%"),
                )
            ).all()
            for mv in prior_movements:
                if mv.batch_id not in prior_by_batch:
                    prior_by_batch[mv.batch_id] = mv.quantity

            # Tính lượng còn có thể hoàn cho từng lô
            for g in grouped_allocations:
                bid = g["batch_id"]
                already_restocked = prior_by_batch.get(bid, 0)
                available_in_batch = max(0, g["allocated_quantity"] - already_restocked)
                g["already_restocked"] = already_restocked
                g["available_to_return"] = available_in_batch

            total_available = sum(g["available_to_return"] for g in grouped_allocations)

            # Kiểm tra số lượng hoàn lần này so với số lượng còn có thể hoàn
            if qty_restock > total_available:
                total_already_done = sum(g["already_restocked"] for g in grouped_allocations)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Số lượng hoàn ({qty_restock}) vượt quá số lượng còn có thể hoàn ({total_available}) "
                        f"từ các lô gốc của sản phẩm '{product_name}' (đã xuất {total_allocated}, đã hoàn {total_already_done})."
                    ),
                )

            # Phân bổ tuần tự theo các allocation còn dung lượng (không quay lại lô đầu nếu đã hoàn đủ)
            remaining_qty = qty_restock
            batch_plans: list[dict[str, Any]] = []
            for g in grouped_allocations:
                if remaining_qty <= 0:
                    break
                avail = g["available_to_return"]
                if avail <= 0:
                    continue
                portion = min(remaining_qty, avail)
                remaining_qty -= portion
                batch_plans.append({
                    "batch_id": g["batch_id"],
                    "warehouse_id": g["warehouse_id"],
                    "portion": portion,
                })

            if remaining_qty > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Không thể phân bổ đủ số lượng hoàn cho '{product_name}'. Thiếu {remaining_qty} đơn vị.",
                )

            plans.append({
                "it": it,
                "order_item_id": order_item_id,
                "qty_restock": qty_restock,
                "batch_plans": batch_plans,
            })

        # 4. Thực thi cập nhật tồn kho (nguyên tử trong cùng transaction sau khi 100% tiền kiểm định thành công)
        created_movements: list[StockMovement] = []
        try:
            for plan in plans:
                order_item_id = plan["order_item_id"]
                item_info = plan["it"]
                batch_plans = plan["batch_plans"]

                for bp in batch_plans:
                    portion = bp["portion"]
                    batch_id = bp["batch_id"]
                    wh_id = bp["warehouse_id"]

                    # Cập nhật WarehouseBatchStock
                    stock = db.scalar(
                        select(WarehouseBatchStock).where(
                            WarehouseBatchStock.warehouse_id == wh_id,
                            WarehouseBatchStock.batch_id == batch_id,
                        )
                    )
                    if stock:
                        stock.quantity_on_hand += portion
                        stock.quantity_available += portion
                    else:
                        stock = WarehouseBatchStock(
                            warehouse_id=wh_id,
                            batch_id=batch_id,
                            quantity_on_hand=portion,
                            quantity_available=portion,
                            quantity_reserved=0,
                        )
                        db.add(stock)
                    db.flush()

                    # Sinh bản ghi StockMovement
                    movement = StockMovement(
                        movement_code=f"MOV-RET-{uuid.uuid4().hex[:6].upper()}",
                        batch_id=batch_id,
                        warehouse_id=wh_id,
                        movement_type="RETURN_RESTOCK",
                        quantity=portion,
                        balance_after=stock.quantity_on_hand,
                        reference_type=source_type,
                        reference_id=source_code,
                        note=audit_note or f"Nhập lại kho bán {portion} hộp thuốc từ hoàn trả ({source_code}) [order_item_id:{order_item_id}]",
                        created_by=actor_user_id,
                        created_at=utcnow(),
                    )
                    db.add(movement)
                    db.flush()
                    created_movements.append(movement)

                    # Lưu bản ghi ReturnRestockAllocation với ràng buộc UniqueConstraint
                    restock_alloc = ReturnRestockAllocation(
                        canonical_return_code=canonical_return_code,
                        source_type=source_type,
                        source_code=source_code,
                        order_item_id=order_item_id,
                        batch_id=batch_id,
                        warehouse_id=wh_id,
                        quantity=portion,
                        stock_movement_id=movement.id,
                        created_at=utcnow(),
                    )
                    db.add(restock_alloc)

                    # Ghi nhận AuditLog
                    actor = db.scalar(select(User).where(User.id == actor_user_id)) if actor_user_id else None
                    write_audit(
                        db=db,
                        action="RETURN_RESTOCK",
                        entity_type=source_type,
                        entity_id=source_code,
                        user=actor,
                        details=f"Nhập lại kho bán {portion} đơn vị sản phẩm #{item_info.get('product_id')} ({item_info.get('product_name')}) vào lô #{batch_id}.",
                    )

            db.flush()
        except IntegrityError as ex:
            logger.exception("Xung đột Idempotency khi nhập kho hàng hoàn")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Chứng từ hoàn '{source_code}' đã được xử lý nhập kho bởi một phiên khác. Tránh nhập trùng.",
            ) from ex

        return created_movements
