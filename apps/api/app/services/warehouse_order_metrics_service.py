"""
apps/api/app/services/warehouse_order_metrics_service.py

Dịch vụ Tổng hợp Số liệu & Chỉ số KPI Đơn hàng Toàn Hệ thống & Từng Chi nhánh Kho:
- Phân biệt rành mạch:
  * "Số đơn khách hàng" (Distinct Order): Mỗi đơn chỉ tính 1 lần toàn hệ thống.
  * "Lượt xử lý tại kho" (Fulfillment): Đếm theo từng phân đoạn kho xử lý.
- Thống kê tiến độ từng công đoạn: Mới, Xác nhận, Lấy hàng, Đã lấy, Đóng gói, Chờ giao, Đang giao, Đã giao, Hủy.
- Thống kê đổi trả & hoàn tiền theo từng kho.
- Kiểm tra đơn quá hạn xử lý (SLA).
- Hiệu suất nhân viên kho & Nhật ký kiểm toán.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import AuditLog, Order, OrderItem, User
from app.models.inventory import (
    FulfillmentItem,
    OrderFulfillment,
    OrderItemBatchAllocation,
    UserWarehouseMembership,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.returns import (
    Refund,
    RefundStatus,
    ReturnItem,
    ReturnRequest,
    ReturnStatus,
    WarehouseReturnCase,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class WarehouseOrderMetricsService:
    @classmethod
    def get_system_orders_overview(
        cls,
        db: Session,
        time_range: str = "today",
        start_date: str | None = None,
        end_date: str | None = None,
        province: str | None = None,
        warehouse_id: int | None = None,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        """
        Tổng hợp KPI toàn hệ thống (Dashboard Admin).
        Đảm bảo bất biến: Order chỉ tính 1 lần, không đếm trùng khi có nhiều Fulfillment.
        """
        now = utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Base query cho Order
        order_q = select(Order)
        if time_range == "today":
            order_q = order_q.where(Order.created_at >= today_start)
        elif time_range == "7d":
            order_q = order_q.where(Order.created_at >= now - timedelta(days=7))
        elif time_range == "30d":
            order_q = order_q.where(Order.created_at >= now - timedelta(days=30))
        elif time_range == "custom" and start_date and end_date:
            try:
                s_dt = datetime.fromisoformat(start_date)
                e_dt = datetime.fromisoformat(end_date)
                order_q = order_q.where(Order.created_at >= s_dt, Order.created_at <= e_dt)
            except Exception:
                pass

        if province and province.strip():
            order_q = order_q.where(Order.shipping_city.ilike(f"%{province.strip()}%"))

        if warehouse_id:
            # Lọc các order có assigned_warehouse_id hoặc có fulfillment thuộc kho này
            wh_order_ids_subq = select(OrderFulfillment.order_id).where(OrderFulfillment.warehouse_id == warehouse_id)
            order_q = order_q.where(
                or_(
                    Order.assigned_warehouse_id == warehouse_id,
                    Order.id.in_(wh_order_ids_subq),
                )
            )

        if status_filter and status_filter.upper() != "ALL":
            order_q = order_q.where(Order.order_status == status_filter.upper())

        all_orders = db.scalars(order_q).all()
        order_ids = [o.id for o in all_orders]

        # Đếm tổng số đơn hôm nay (không phụ thuộc bộ lọc thời gian)
        orders_today_count = db.scalar(
            select(func.count(Order.id)).where(Order.created_at >= today_start)
        ) or 0

        # Phân loại trạng thái Order
        orders_processing = 0
        orders_shipping = 0
        orders_delivered = 0
        orders_cancelled = 0
        overdue_orders = 0

        for o in all_orders:
            st = (o.order_status or "").upper()
            fst = (o.fulfillment_status or "").upper()

            if st in ["PROCESSING", "CONFIRMED", "PENDING"] or fst in ["ALLOCATED", "PICKING", "PACKED", "WAITING_INTERNAL_TRANSFER"]:
                orders_processing += 1
            if st == "SHIPPING" or fst == "SHIPPED":
                orders_shipping += 1
            if st == "DELIVERED" or fst == "DELIVERED":
                orders_delivered += 1
            if st == "CANCELLED":
                orders_cancelled += 1

            # Kiểm tra quá hạn: đơn chưa giao và tạo > 24h
            if st not in ["DELIVERED", "CANCELLED"]:
                if o.created_at and (now - o.created_at.replace(tzinfo=UTC if o.created_at.tzinfo is None else o.created_at.tzinfo)).total_seconds() > 86400:
                    overdue_orders += 1

        # Tổng số đơn hoàn
        returns_q = select(func.count(func.distinct(ReturnRequest.id)))
        if order_ids:
            returns_q = returns_q.where(ReturnRequest.order_id.in_(order_ids))
        total_returns = db.scalar(returns_q) or 0

        # Tiền chờ hoàn & đã hoàn
        pending_refunds_q = select(func.sum(Refund.amount)).where(
            Refund.status.in_([RefundStatus.PENDING.value, RefundStatus.APPROVED.value, RefundStatus.PROCESSING.value])
        )
        if order_ids:
            pending_refunds_q = pending_refunds_q.where(Refund.order_id.in_(order_ids))
        pending_refund_sum = db.scalar(pending_refunds_q) or Decimal("0.0")

        succeeded_refunds_q = select(func.sum(Refund.amount)).where(
            Refund.status == RefundStatus.SUCCEEDED.value
        )
        if order_ids:
            succeeded_refunds_q = succeeded_refunds_q.where(Refund.order_id.in_(order_ids))
        succeeded_refund_sum = db.scalar(succeeded_refunds_q) or Decimal("0.0")

        # Số kho đang hoạt động
        active_warehouses_count = db.scalar(
            select(func.count(Warehouse.id)).where(Warehouse.is_active.is_(True))
        ) or 0

        # Tổng số lượt xử lý fulfillment
        ful_q = select(func.count(OrderFulfillment.id))
        if order_ids:
            ful_q = ful_q.where(OrderFulfillment.order_id.in_(order_ids))
        total_fulfillments_count = db.scalar(ful_q) or 0

        return {
            "total_orders_today": orders_today_count,
            "orders_processing": orders_processing,
            "orders_shipping": orders_shipping,
            "orders_delivered": orders_delivered,
            "orders_cancelled": orders_cancelled,
            "orders_returned": total_returns,
            "pending_refund_amount": float(pending_refund_sum),
            "refunded_amount": float(succeeded_refund_sum),
            "overdue_orders": overdue_orders,
            "active_warehouses": active_warehouses_count,
            "distinct_orders_count": len(all_orders),
            "total_fulfillments_count": total_fulfillments_count,
        }

    @classmethod
    def get_warehouses_overview_table(
        cls,
        db: Session,
        time_range: str = "today",
        start_date: str | None = None,
        end_date: str | None = None,
        province: str | None = None,
        warehouse_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Bảng chi tiết từng chi nhánh kho cho Admin:
        Mỗi dòng là 1 kho với toàn bộ chỉ số vận hành và tình trạng đơn.
        """
        now = utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        wh_query = select(Warehouse).order_by(Warehouse.id.asc())
        if province and province.strip():
            wh_query = wh_query.where(Warehouse.province.ilike(f"%{province.strip()}%"))
        if warehouse_id:
            wh_query = wh_query.where(Warehouse.id == warehouse_id)

        warehouses = db.scalars(wh_query).all()

        results = []
        for wh in warehouses:
            # 1. Tìm Quản lý kho
            manager_membership = db.scalar(
                select(UserWarehouseMembership)
                .options(selectinload(UserWarehouseMembership.user))
                .where(
                    UserWarehouseMembership.warehouse_id == wh.id,
                    UserWarehouseMembership.role == "WAREHOUSE_MANAGER",
                    UserWarehouseMembership.is_active.is_(True),
                )
            )
            manager_name = (
                manager_membership.user.full_name
                if manager_membership and manager_membership.user
                else "Chưa gán"
            )

            # 2. Lọc Fulfillments của kho theo thời gian
            ful_q = select(OrderFulfillment).where(OrderFulfillment.warehouse_id == wh.id)
            if time_range == "today":
                ful_q = ful_q.where(OrderFulfillment.created_at >= today_start)
            elif time_range == "7d":
                ful_q = ful_q.where(OrderFulfillment.created_at >= now - timedelta(days=7))
            elif time_range == "30d":
                ful_q = ful_q.where(OrderFulfillment.created_at >= now - timedelta(days=30))
            elif time_range == "custom" and start_date and end_date:
                try:
                    ful_q = ful_q.where(
                        OrderFulfillment.created_at >= datetime.fromisoformat(start_date),
                        OrderFulfillment.created_at <= datetime.fromisoformat(end_date),
                    )
                except Exception:
                    pass

            fulfillments = db.scalars(ful_q).all()

            orders_new = 0
            orders_confirming = 0
            orders_picking = 0
            orders_picked = 0
            orders_packing = 0
            orders_ready_to_ship = 0
            orders_shipping = 0
            orders_delivered = 0
            orders_cancelled = 0
            total_processing_seconds = 0
            completed_count = 0

            for f in fulfillments:
                st = (f.status or "").upper()
                if st in ["PENDING"]:
                    orders_new += 1
                elif st in ["ALLOCATED", "PICKING"]:
                    orders_picking += 1
                elif st in ["PICKED"]:
                    orders_picked += 1
                elif st in ["PACKED"]:
                    orders_packing += 1
                    orders_ready_to_ship += 1
                elif st in ["SHIPPED"]:
                    orders_shipping += 1
                elif st in ["DELIVERED"]:
                    orders_delivered += 1
                    if f.created_at and f.delivered_at:
                        c_tz = f.created_at.replace(tzinfo=UTC if f.created_at.tzinfo is None else f.created_at.tzinfo)
                        d_tz = f.delivered_at.replace(tzinfo=UTC if f.delivered_at.tzinfo is None else f.delivered_at.tzinfo)
                        total_processing_seconds += (d_tz - c_tz).total_seconds()
                        completed_count += 1
                elif st in ["CANCELLED"]:
                    orders_cancelled += 1

            avg_hours = round(total_processing_seconds / (completed_count * 3600), 1) if completed_count > 0 else 0.0

            # 3. Ca hoàn thuộc kho
            cases_q = select(WarehouseReturnCase).where(WarehouseReturnCase.warehouse_id == wh.id)
            if time_range == "today":
                cases_q = cases_q.where(WarehouseReturnCase.created_at >= today_start)
            cases = db.scalars(cases_q).all()

            returns_processing = sum(1 for c in cases if c.status not in ["CLOSED", "REJECTED"])
            returns_overdue = 0
            for c in cases:
                if c.status not in ["CLOSED", "REJECTED"] and c.created_at:
                    c_tz = c.created_at.replace(tzinfo=UTC if c.created_at.tzinfo is None else c.created_at.tzinfo)
                    if (now - c_tz).total_seconds() > 172800:  # > 48h
                        returns_overdue += 1

            # 4. Tổng số sản phẩm cần xuất (items_to_pick)
            pending_ful_ids = [f.id for f in fulfillments if f.status in ["PENDING", "ALLOCATED", "PICKING"]]
            items_to_pick = 0
            if pending_ful_ids:
                items_to_pick = db.scalar(
                    select(func.sum(FulfillmentItem.quantity)).where(
                        FulfillmentItem.fulfillment_id.in_(pending_ful_ids)
                    )
                ) or 0

            # 5. Số đơn thiếu hàng (cảnh báo tồn kho)
            stockout_orders = 0
            for f in fulfillments:
                if f.status in ["PENDING", "ALLOCATED"]:
                    # Kiểm tra xem có item nào kho không đủ tồn không
                    for fi in f.items:
                        # Tra cứu tồn khả dụng
                        total_avail = db.scalar(
                            select(func.sum(WarehouseBatchStock.quantity_available)).where(
                                WarehouseBatchStock.warehouse_id == wh.id
                            )
                        ) or 0
                        if total_avail < fi.quantity:
                            stockout_orders += 1
                            break

            results.append({
                "warehouse_id": wh.id,
                "warehouse_code": wh.code,
                "warehouse_name": wh.name,
                "province": wh.province or "N/A",
                "manager_name": manager_name,
                "total_fulfillments": len(fulfillments),
                "orders_new": orders_new,
                "orders_confirming": orders_confirming,
                "orders_picking": orders_picking,
                "orders_picked": orders_picked,
                "orders_packing": orders_packing,
                "orders_ready_to_ship": orders_ready_to_ship,
                "orders_shipping": orders_shipping,
                "orders_delivered": orders_delivered,
                "orders_cancelled": orders_cancelled,
                "returns_processing": returns_processing,
                "returns_overdue": returns_overdue,
                "items_to_pick": int(items_to_pick),
                "stockout_orders": stockout_orders,
                "avg_processing_time_hours": avg_hours,
                "is_active": wh.is_active,
            })

        return results

    @classmethod
    def get_warehouse_details_tab(
        cls,
        db: Session,
        warehouse_id: int,
    ) -> dict[str, Any]:
        """
        Chi tiết chi nhánh kho khi bấm vào từ Admin:
        - Tổng quan kho
        - Danh sách đơn hàng / fulfillments
        - Ca hoàn hàng
        - Hoàn tiền
        - Tồn kho liên quan
        - Hiệu suất nhân viên
        - Nhật ký hoạt động
        """
        wh = db.get(Warehouse, warehouse_id)
        if not wh:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy kho hàng ID {warehouse_id}.")

        # 1. Fulfillments gần đây
        recent_fulfillments = db.scalars(
            select(OrderFulfillment)
            .options(
                selectinload(OrderFulfillment.items).selectinload(FulfillmentItem.order_item),
                selectinload(OrderFulfillment.assigned_staff),
            )
            .where(OrderFulfillment.warehouse_id == warehouse_id)
            .order_by(desc(OrderFulfillment.id))
            .limit(30)
        ).all()

        # 2. Ca hoàn gần đây
        recent_returns = db.scalars(
            select(WarehouseReturnCase)
            .options(
                selectinload(WarehouseReturnCase.items),
                selectinload(WarehouseReturnCase.assigned_staff),
                selectinload(WarehouseReturnCase.return_request),
            )
            .where(WarehouseReturnCase.warehouse_id == warehouse_id)
            .order_by(desc(WarehouseReturnCase.id))
            .limit(30)
        ).all()

        # 3. Hoàn tiền của kho
        recent_refunds = db.scalars(
            select(Refund)
            .where(Refund.warehouse_id == warehouse_id)
            .order_by(desc(Refund.id))
            .limit(30)
        ).all()

        # 4. Hiệu suất nhân viên trong kho
        staff_memberships = db.scalars(
            select(UserWarehouseMembership)
            .options(selectinload(UserWarehouseMembership.user))
            .where(UserWarehouseMembership.warehouse_id == warehouse_id)
        ).all()

        staff_list = []
        for m in staff_memberships:
            u = m.user
            if not u:
                continue

            picked_count = db.scalar(
                select(func.count(OrderFulfillment.id)).where(
                    OrderFulfillment.assigned_staff_id == u.id,
                    OrderFulfillment.status.in_(["PICKED", "PACKED", "SHIPPED", "DELIVERED"]),
                )
            ) or 0

            inspected_count = db.scalar(
                select(func.count(WarehouseReturnCase.id)).where(
                    WarehouseReturnCase.inspected_by_user_id == u.id
                )
            ) or 0

            staff_list.append({
                "user_id": u.id,
                "full_name": u.full_name,
                "phone": u.phone,
                "role": m.role,
                "is_active": m.is_active,
                "orders_processed": picked_count,
                "returns_inspected": inspected_count,
            })

        # 5. Nhật ký hoạt động gần đây của kho
        audit_logs = db.scalars(
            select(AuditLog)
            .where(
                or_(
                    AuditLog.entity_id.ilike(f"%{wh.code}%"),
                    AuditLog.action.ilike(f"%WAREHOUSE%"),
                )
            )
            .order_by(desc(AuditLog.id))
            .limit(30)
        ).all()

        user_ids = [a.user_id for a in audit_logs if a.user_id]
        user_map = {}
        if user_ids:
            for u in db.scalars(select(User).where(User.id.in_(user_ids))).all():
                user_map[u.id] = u.full_name

        # 6. Tồn kho tóm tắt
        total_sku_count = db.scalar(
            select(func.count(func.distinct(WarehouseBatchStock.batch_id))).where(
                WarehouseBatchStock.warehouse_id == warehouse_id
            )
        ) or 0
        total_units = db.scalar(
            select(func.sum(WarehouseBatchStock.quantity_on_hand)).where(
                WarehouseBatchStock.warehouse_id == warehouse_id
            )
        ) or 0

        return {
            "warehouse": {
                "id": wh.id,
                "code": wh.code,
                "name": wh.name,
                "address": wh.address,
                "province": wh.province,
                "phone": wh.phone,
                "is_active": wh.is_active,
                "total_skus": total_sku_count,
                "total_units": int(total_units),
            },
            "fulfillments": [
                {
                    "id": f.id,
                    "fulfillment_code": f.fulfillment_code,
                    "order_id": f.order_id,
                    "status": f.status,
                    "carrier_name": f.carrier_name,
                    "tracking_code": f.tracking_code,
                    "assigned_staff": f.assigned_staff.full_name if f.assigned_staff else None,
                    "items_count": len(f.items),
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in recent_fulfillments
            ],
            "returns": [
                {
                    "id": r.id,
                    "case_code": r.case_code,
                    "return_code": r.return_request.return_code if r.return_request else None,
                    "status": r.status,
                    "assigned_staff": r.assigned_staff.full_name if r.assigned_staff else None,
                    "items_count": len(r.items),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in recent_returns
            ],
            "refunds": [
                {
                    "id": rf.id,
                    "refund_code": rf.refund_code,
                    "amount": float(rf.amount),
                    "refund_method": rf.refund_method,
                    "status": rf.status,
                    "created_at": rf.created_at.isoformat() if rf.created_at else None,
                }
                for rf in recent_refunds
            ],
            "staff_performance": staff_list,
            "audit_logs": [
                {
                    "id": a.id,
                    "action": a.action,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "actor_name": user_map.get(a.user_id, "Hệ thống"),
                    "details": str(a.after_json or a.action),
                    "timestamp": a.created_at.isoformat() if a.created_at else None,
                }
                for a in audit_logs
            ],
        }
