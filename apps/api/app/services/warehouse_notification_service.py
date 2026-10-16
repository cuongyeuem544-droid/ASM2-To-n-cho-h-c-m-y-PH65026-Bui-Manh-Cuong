"""Warehouse Notification Service.

Manages scoped, anti-IDOR notifications for Warehouse Managers and Warehouse Staff.
Enforces deduplication, batch expiry tiers (60d warning, 30d high, 7d critical, <=0 expired),
24h order SLA overdue detection, stock low (<=10) / out (==0), return workflow alerts,
and staff assignment alerts.
"""
from datetime import UTC, date, datetime, timedelta
import logging
from typing import Any, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import CanonicalProduct, Order, User
from app.models.inventory import (
    InventoryBatch,
    OrderFulfillment,
    ProductSku,
    StockTransfer,
    Warehouse,
    WarehouseBatchStock,
    WarehouseNotification,
)
from app.models.returns import ReturnEvidenceRequest, ReturnRequest

logger = logging.getLogger("pharmatrust.warehouse_notification_service")


def utcnow() -> datetime:
    return datetime.now(UTC)


class WarehouseNotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        warehouse_id: int,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "INFO",
        recipient_user_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action_url: Optional[str] = None,
        deduplication_key: Optional[str] = None,
    ) -> WarehouseNotification:
        """
        Creates a notification with strict deduplication check.
        If deduplication_key already exists, returns existing notification without creating duplicates.
        """
        if deduplication_key:
            existing = db.scalar(
                select(WarehouseNotification).where(
                    WarehouseNotification.deduplication_key == deduplication_key
                )
            )
            if existing:
                return existing

        notif = WarehouseNotification(
            warehouse_id=warehouse_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            action_url=action_url,
            is_read=False,
            created_at=utcnow(),
            deduplication_key=deduplication_key,
        )
        db.add(notif)
        db.flush()
        return notif

    @classmethod
    def notify_order_new(
        cls,
        db: Session,
        order: Order,
        warehouse_id: int,
    ) -> WarehouseNotification:
        """ORDER_NEW: Dispatched when an order is allocated to a warehouse."""
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="ORDER_NEW",
            title=f"Đơn hàng mới: {order.order_code}",
            message=f"Đơn hàng {order.order_code} đã được phân bổ về kho. Cần kiểm tra và soạn hàng.",
            severity="INFO",
            recipient_user_id=None,  # Broadcast to all warehouse managers and active staff
            entity_type="Order",
            entity_id=str(order.id),
            action_url=f"/warehouse/orders?order_id={order.id}",
            deduplication_key=f"ORDER_NEW_{order.id}_{warehouse_id}",
        )

    @classmethod
    def notify_order_cancelled(
        cls,
        db: Session,
        order: Order,
        warehouse_id: int,
        reason: Optional[str] = None,
    ) -> WarehouseNotification:
        """ORDER_CANCELLED: Dispatched when an allocated order is cancelled by customer or admin."""
        reason_text = f" (Lý do: {reason})" if reason else ""
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="ORDER_CANCELLED",
            title=f"Khách hủy đơn: {order.order_code}",
            message=f"Khách hàng hoặc hệ thống đã hủy đơn {order.order_code}{reason_text}. Vui lòng dừng soạn hàng và đóng gói.",
            severity="CRITICAL",
            recipient_user_id=None,  # Broadcast to both warehouse manager and staff
            entity_type="Order",
            entity_id=str(order.id),
            action_url=f"/warehouse/orders?order_id={order.id}&status=CANCELLED",
            deduplication_key=f"ORDER_CANCELLED_{order.id}_{warehouse_id}",
        )

    @classmethod
    def notify_order_assigned(
        cls,
        db: Session,
        order: Order,
        warehouse_id: int,
        staff_user_id: int,
    ) -> WarehouseNotification:
        """ORDER_ASSIGNED: Dispatched to specific warehouse staff assigned to an order."""
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="ORDER_ASSIGNED",
            title=f"Phân công đơn hàng: {order.order_code}",
            message=f"Bạn được phân công xử lý phiếu soạn đơn hàng {order.order_code}.",
            severity="INFO",
            recipient_user_id=staff_user_id,
            entity_type="Order",
            entity_id=str(order.id),
            action_url=f"/staff/picking-packing?order_id={order.id}",
            deduplication_key=f"ORDER_ASSIGNED_{order.id}_{staff_user_id}",
        )

    @classmethod
    def notify_return_new(
        cls,
        db: Session,
        return_req: ReturnRequest,
        warehouse_id: int,
    ) -> WarehouseNotification:
        """RETURN_NEW: Dispatched to warehouse manager when a return request is assigned."""
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="RETURN_NEW",
            title=f"Yêu cầu hoàn trả mới: {return_req.return_code}",
            message=f"Yêu cầu hoàn trả {return_req.return_code} cần quản lý chi nhánh tiếp nhận và thẩm định.",
            severity="WARNING",
            recipient_user_id=None,
            entity_type="ReturnRequest",
            entity_id=str(return_req.id),
            action_url="/warehouse/returns",
            deduplication_key=f"RETURN_NEW_{return_req.id}_{warehouse_id}",
        )

    @classmethod
    def notify_return_evidence_added(
        cls,
        db: Session,
        return_req: ReturnRequest,
        warehouse_id: int,
    ) -> WarehouseNotification:
        """RETURN_EVIDENCE_ADDED: Dispatched when customer uploads requested evidence."""
        today_str = date.today().isoformat()
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="RETURN_EVIDENCE_ADDED",
            title=f"Bổ sung minh chứng hoàn: {return_req.return_code}",
            message=f"Khách hàng đã nộp bổ sung hình ảnh minh chứng cho ca hoàn {return_req.return_code}.",
            severity="INFO",
            recipient_user_id=None,
            entity_type="ReturnRequest",
            entity_id=str(return_req.id),
            action_url="/warehouse/returns",
            deduplication_key=f"RETURN_EVID_ADDED_{return_req.id}_{warehouse_id}_{today_str}",
        )

    @classmethod
    def notify_return_evidence_deadline(
        cls,
        db: Session,
        evidence_req: ReturnEvidenceRequest,
        warehouse_id: int,
    ) -> WarehouseNotification:
        """RETURN_EVIDENCE_DEADLINE: Reminds manager about expiring customer evidence request (3-day limit)."""
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="RETURN_EVIDENCE_DEADLINE",
            title=f"Hồ sơ bổ sung sắp hết hạn: {evidence_req.request_code}",
            message=f"Yêu cầu bổ sung hình ảnh {evidence_req.request_code} sắp hết hạn thời hạn 3 ngày.",
            severity="WARNING",
            recipient_user_id=None,
            entity_type="ReturnEvidenceRequest",
            entity_id=str(evidence_req.id),
            action_url="/warehouse/returns",
            deduplication_key=f"RETURN_DEADLINE_{evidence_req.id}",
        )

    @classmethod
    def notify_transfer_assigned(
        cls,
        db: Session,
        transfer: StockTransfer,
        warehouse_id: int,
        staff_user_id: int,
    ) -> WarehouseNotification:
        """TRANSFER_ASSIGNED: Notifies staff assigned to incoming/outgoing transfer."""
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="TRANSFER_ASSIGNED",
            title=f"Phiếu điều chuyển kho: {transfer.transfer_code}",
            message=f"Bạn được giao thực hiện phiếu điều chuyển kho {transfer.transfer_code}.",
            severity="INFO",
            recipient_user_id=staff_user_id,
            entity_type="StockTransfer",
            entity_id=str(transfer.id),
            action_url="/staff/transfers",
            deduplication_key=f"TRANSFER_ASSIGNED_{transfer.id}_{staff_user_id}",
        )

    @classmethod
    def notify_task_updated(
        cls,
        db: Session,
        warehouse_id: int,
        staff_user_id: int,
        task_title: str,
        task_status: str,
        action_url: str = "/staff/today",
    ) -> WarehouseNotification:
        """TASK_UPDATED: Dispatched when assigned task changes."""
        today_str = date.today().isoformat()
        return cls.create_notification(
            db,
            warehouse_id=warehouse_id,
            notification_type="TASK_UPDATED",
            title=f"Cập nhật công việc: {task_title}",
            message=f"Nhiệm vụ {task_title} chuyển sang trạng thái: {task_status}.",
            severity="INFO",
            recipient_user_id=staff_user_id,
            action_url=action_url,
            deduplication_key=f"TASK_UPDATED_{warehouse_id}_{staff_user_id}_{task_title}_{task_status}_{today_str}",
        )

    @classmethod
    def scan_batch_expiries(
        cls,
        db: Session,
        warehouse_id: Optional[int] = None,
        target_date: Optional[date] = None,
    ) -> int:
        """
        Scans batches at warehouses with threshold 60 days:
        - 31-60 days: WARNING
        - 8-30 days: HIGH
        - 1-7 days: CRITICAL
        - <= 0 days: EXPIRED
        Deduplication key ensures no duplicate notifications are generated per tier.
        """
        today = target_date or date.today()
        created_count = 0

        query = (
            select(
                WarehouseBatchStock.warehouse_id,
                WarehouseBatchStock.batch_id,
                WarehouseBatchStock.quantity_available,
                InventoryBatch.batch_number,
                InventoryBatch.expiry_date,
            )
            .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
            .where(WarehouseBatchStock.quantity_available > 0)
        )
        if warehouse_id:
            query = query.where(WarehouseBatchStock.warehouse_id == warehouse_id)

        rows = db.execute(query).all()
        for wh_id, batch_id, qty, b_number, exp_date in rows:
            days_left = (exp_date - today).days

            if days_left > 60:
                continue

            if days_left <= 0:
                tier = "EXPIRED"
                severity = "EXPIRED"
                title = f"Lô {b_number} đã hết hạn!"
                msg = f"Lô thuốc {b_number} đã hết hạn vào ngày {exp_date}. Tuyệt đối không xuất bán, cần cách ly chờ xử lý."
                notif_type = "BATCH_EXPIRED"
            elif 1 <= days_left <= 7:
                tier = "CRITICAL"
                severity = "CRITICAL"
                title = f"Lô {b_number} khẩn cấp (còn {days_left} ngày)"
                msg = f"Lô thuốc {b_number} cận hạn nghiêm trọng, chỉ còn {days_left} ngày (HSD: {exp_date}). Số lượng: {qty}."
                notif_type = "BATCH_EXPIRING"
            elif 8 <= days_left <= 30:
                tier = "HIGH"
                severity = "HIGH"
                title = f"Lô {b_number} cận hạn cao (còn {days_left} ngày)"
                msg = f"Lô thuốc {b_number} còn {days_left} ngày sử dụng (HSD: {exp_date}). Cần ưu tiên phân bổ xuất kho FEFO."
                notif_type = "BATCH_EXPIRING"
            else:  # 31 to 60 days
                tier = "WARNING"
                severity = "WARNING"
                title = f"Lô {b_number} sắp hết hạn (còn {days_left} ngày)"
                msg = f"Lô thuốc {b_number} còn {days_left} ngày sử dụng (HSD: {exp_date}). Lưu ý theo dõi và xuất kho theo FEFO."
                notif_type = "BATCH_EXPIRING"

            dedup = f"EXPIRY-{wh_id}-{batch_id}-{tier}"
            existing = db.scalar(
                select(WarehouseNotification.id).where(WarehouseNotification.deduplication_key == dedup)
            )
            if not existing:
                cls.create_notification(
                    db,
                    warehouse_id=wh_id,
                    notification_type=notif_type,
                    title=title,
                    message=msg,
                    severity=severity,
                    recipient_user_id=None,
                    entity_type="InventoryBatch",
                    entity_id=str(batch_id),
                    action_url="/warehouse/batches",
                    deduplication_key=dedup,
                )
                created_count += 1

        db.commit()
        return created_count

    @classmethod
    def scan_stock_levels(
        cls,
        db: Session,
        warehouse_id: Optional[int] = None,
        low_stock_threshold: int = 10,
    ) -> int:
        """
        Scans stock levels:
        - available == 0: STOCK_OUT
        - 0 < available <= low_stock_threshold: STOCK_LOW
        """
        today_str = date.today().isoformat()
        created_count = 0

        # Group available quantity per (warehouse_id, canonical_product_id)
        query = (
            select(
                WarehouseBatchStock.warehouse_id,
                ProductSku.canonical_product_id,
                CanonicalProduct.canonical_name,
                func.sum(WarehouseBatchStock.quantity_available).label("total_avail"),
            )
            .join(InventoryBatch, WarehouseBatchStock.batch_id == InventoryBatch.id)
            .join(ProductSku, InventoryBatch.sku_id == ProductSku.id)
            .join(CanonicalProduct, ProductSku.canonical_product_id == CanonicalProduct.id)
            .group_by(WarehouseBatchStock.warehouse_id, ProductSku.canonical_product_id, CanonicalProduct.canonical_name)
        )
        if warehouse_id:
            query = query.where(WarehouseBatchStock.warehouse_id == warehouse_id)

        rows = db.execute(query).all()
        for wh_id, prod_id, prod_name, total_avail in rows:
            avail = int(total_avail or 0)
            if avail == 0:
                dedup = f"STOCK_OUT_{wh_id}_{prod_id}_{today_str}"
                existing = db.scalar(select(WarehouseNotification.id).where(WarehouseNotification.deduplication_key == dedup))
                if not existing:
                    cls.create_notification(
                        db,
                        warehouse_id=wh_id,
                        notification_type="STOCK_OUT",
                        title=f"Hết hàng: {prod_name}",
                        message=f"Sản phẩm {prod_name} đã hết tồn kho khả dụng tại chi nhánh.",
                        severity="CRITICAL",
                        recipient_user_id=None,
                        entity_type="CanonicalProduct",
                        entity_id=str(prod_id),
                        action_url="/warehouse/stock",
                        deduplication_key=dedup,
                    )
                    created_count += 1
            elif avail <= low_stock_threshold:
                dedup = f"STOCK_LOW_{wh_id}_{prod_id}_{today_str}"
                existing = db.scalar(select(WarehouseNotification.id).where(WarehouseNotification.deduplication_key == dedup))
                if not existing:
                    cls.create_notification(
                        db,
                        warehouse_id=wh_id,
                        notification_type="STOCK_LOW",
                        title=f"Tồn kho thấp: {prod_name}",
                        message=f"Sản phẩm {prod_name} chỉ còn {avail} đơn vị khả dụng (ngưỡng: {low_stock_threshold}).",
                        severity="WARNING",
                        recipient_user_id=None,
                        entity_type="CanonicalProduct",
                        entity_id=str(prod_id),
                        action_url="/warehouse/stock",
                        deduplication_key=dedup,
                    )
                    created_count += 1

        db.commit()
        return created_count

    @classmethod
    def scan_overdue_orders(
        cls,
        db: Session,
        warehouse_id: Optional[int] = None,
        sla_hours: int = 24,
    ) -> int:
        """
        Scans orders not DELIVERED or CANCELLED created more than sla_hours ago.
        """
        now = utcnow()
        cutoff = now - timedelta(hours=sla_hours)
        created_count = 0

        query = select(Order).where(
            Order.assigned_warehouse_id.is_not(None),
            Order.order_status.not_in(["COMPLETED", "CANCELLED"]),
            Order.fulfillment_status != "DELIVERED",
            Order.created_at <= cutoff,
        )
        if warehouse_id:
            query = query.where(Order.assigned_warehouse_id == warehouse_id)

        orders = db.scalars(query).all()
        for o in orders:
            wh_id = o.assigned_warehouse_id
            if not wh_id:
                continue

            dedup = f"ORDER_OVERDUE_{wh_id}_{o.id}"
            existing = db.scalar(select(WarehouseNotification.id).where(WarehouseNotification.deduplication_key == dedup))
            if not existing:
                cls.create_notification(
                    db,
                    warehouse_id=wh_id,
                    notification_type="ORDER_OVERDUE",
                    title=f"Đơn hàng quá hạn: {o.order_code}",
                    message=f"Đơn hàng {o.order_code} đã chờ xử lý quá {sla_hours} giờ. Cần đẩy nhanh tiến trình soạn/giao.",
                    severity="CRITICAL",
                    recipient_user_id=None,
                    entity_type="Order",
                    entity_id=str(o.id),
                    action_url=f"/warehouse/orders?order_id={o.id}",
                    deduplication_key=dedup,
                )
                created_count += 1

        db.commit()
        return created_count

    @classmethod
    def run_all_scans(cls, db: Session, warehouse_id: Optional[int] = None) -> dict[str, int]:
        """Runs batch expiry, stock levels, and overdue orders scans."""
        exp_count = cls.scan_batch_expiries(db, warehouse_id=warehouse_id)
        stock_count = cls.scan_stock_levels(db, warehouse_id=warehouse_id, low_stock_threshold=10)
        overdue_count = cls.scan_overdue_orders(db, warehouse_id=warehouse_id, sla_hours=24)
        return {
            "expiries_created": exp_count,
            "stock_alerts_created": stock_count,
            "overdue_orders_created": overdue_count,
        }
