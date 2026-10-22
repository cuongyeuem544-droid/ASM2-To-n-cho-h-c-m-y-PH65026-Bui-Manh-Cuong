"""H4CARE Production Revenue Analytics Service

Calculates precise financial metrics for Admin Dashboard without fake data or double-counting.
- Gross GMV (all non-cancelled orders)
- Verified Collected Cash (SePay SUCCESS, payOS PAID, COD DELIVERED only)
- Refunds (Succeeded refunds only)
- Net Cash (Collected - Refunds)
- Recognized Revenue (Delivered + Paid)
- Pending Cash (COD in transit, pending online)
- Payment Method Breakdown (COD, SEPAY, PAYOS)
- Warehouse Breakdown (HCM, HN)
- Daily Time Series for charting
- Timezone safe (Asia/Ho_Chi_Minh UTC+7 conversion)
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Order, PaymentTransaction, Refund, Warehouse

# Vietnam Timezone (UTC+7)
VN_TZ = timezone(timedelta(hours=7))
UTC_TZ = timezone.utc


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Rule 12 compliant helper to ensure datetime is UTC aware or naive match."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(UTC_TZ)


def resolve_date_range(
    range_type: str = "30d",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> Tuple[datetime, datetime]:
    """Resolves date filter boundaries in Vietnam Time (UTC+7) and converts to UTC."""
    now_vn = datetime.now(VN_TZ)
    today_vn = now_vn.date()

    if range_type == "today":
        start_vn = datetime.combine(today_vn, time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(today_vn, time.max, tzinfo=VN_TZ)
    elif range_type == "yesterday":
        yest_vn = today_vn - timedelta(days=1)
        start_vn = datetime.combine(yest_vn, time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(yest_vn, time.max, tzinfo=VN_TZ)
    elif range_type == "7d":
        start_vn = datetime.combine(today_vn - timedelta(days=6), time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(today_vn, time.max, tzinfo=VN_TZ)
    elif range_type == "30d":
        start_vn = datetime.combine(today_vn - timedelta(days=29), time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(today_vn, time.max, tzinfo=VN_TZ)
    elif range_type == "this_month":
        start_vn = datetime.combine(today_vn.replace(day=1), time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(today_vn, time.max, tzinfo=VN_TZ)
    elif range_type == "last_month":
        first_of_this_month = today_vn.replace(day=1)
        last_day_of_last_month = first_of_this_month - timedelta(days=1)
        first_of_last_month = last_day_of_last_month.replace(day=1)
        start_vn = datetime.combine(first_of_last_month, time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(last_day_of_last_month, time.max, tzinfo=VN_TZ)
    elif range_type == "this_quarter":
        quarter_month = ((today_vn.month - 1) // 3) * 3 + 1
        first_of_quarter = today_vn.replace(month=quarter_month, day=1)
        start_vn = datetime.combine(first_of_quarter, time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(today_vn, time.max, tzinfo=VN_TZ)
    elif range_type == "this_year":
        start_vn = datetime.combine(today_vn.replace(month=1, day=1), time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(today_vn, time.max, tzinfo=VN_TZ)
    elif range_type == "custom" and start_date_str and end_date_str:
        sd = date.fromisoformat(start_date_str)
        ed = date.fromisoformat(end_date_str)
        start_vn = datetime.combine(sd, time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(ed, time.max, tzinfo=VN_TZ)
    else:
        # Default 30d
        start_vn = datetime.combine(today_vn - timedelta(days=29), time.min, tzinfo=VN_TZ)
        end_vn = datetime.combine(today_vn, time.max, tzinfo=VN_TZ)

    # Convert to UTC naive or UTC aware depending on DB backend
    start_utc = start_vn.astimezone(UTC_TZ)
    end_utc = end_vn.astimezone(UTC_TZ)
    return start_utc, end_utc


class RevenueAnalyticsService:
    @staticmethod
    def get_revenue_summary(
        db: Session,
        start_utc: datetime,
        end_utc: datetime,
        warehouse_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Calculates exact financial summary metrics for the given period."""
        # Clean datetime comparison: SQLite compatible
        # Order base filter
        order_filters = [
            Order.created_at >= start_utc.replace(tzinfo=None),
            Order.created_at <= end_utc.replace(tzinfo=None),
        ]
        if warehouse_id is not None:
            order_filters.append(Order.assigned_warehouse_id == warehouse_id)

        # 1. Orders aggregation query
        # Gross GMV excludes cancelled and rejected orders
        active_order_cond = and_(
            Order.order_status.notin_(["CANCELLED", "REJECTED"]),
        )
        delivered_cond = Order.order_status.in_(["DELIVERED", "COMPLETED"])
        paid_cond = Order.payment_status == "PAID"

        # COD collected = COD method + Delivered/Completed
        cod_collected_cond = and_(
            Order.payment_method == "COD",
            delivered_cond,
        )

        # Online collected = SePay or payOS + Paid
        online_collected_cond = and_(
            Order.payment_method.in_(["SEPAY", "PAYOS", "MOMO", "VIETQR"]),
            paid_cond,
        )

        # Pending COD = COD method + not delivered + not cancelled
        cod_pending_cond = and_(
            Order.payment_method == "COD",
            Order.order_status.notin_(["DELIVERED", "COMPLETED", "CANCELLED", "REJECTED"]),
        )

        # Pending Online = Online method + PENDING payment status + not cancelled
        online_pending_cond = and_(
            Order.payment_method.in_(["SEPAY", "PAYOS", "MOMO", "VIETQR"]),
            Order.payment_status == "PENDING",
            Order.order_status.notin_(["CANCELLED", "REJECTED"]),
        )

        order_stats = db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.coalesce(
                    func.sum(case((active_order_cond, Order.total_amount), else_=0)), 0
                ).label("gross_gmv"),
                func.coalesce(
                    func.sum(
                        case(
                            (or_(cod_collected_cond, online_collected_cond), Order.total_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("verified_collected_cash"),
                func.coalesce(
                    func.sum(
                        case(
                            (and_(delivered_cond, paid_cond), Order.total_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("recognized_revenue"),
                func.coalesce(
                    func.sum(
                        case(
                            (or_(cod_pending_cond, online_pending_cond), Order.total_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("pending_cash"),
                func.count(case((paid_cond, Order.id))).label("paid_orders_count"),
                func.count(
                    case((Order.order_status == "CANCELLED", Order.id))
                ).label("cancelled_orders_count"),
                func.count(
                    case((or_(cod_pending_cond, online_pending_cond), Order.id))
                ).label("pending_orders_count"),
            ).where(*order_filters)
        ).one()

        total_orders = int(order_stats.total_orders or 0)
        gross_gmv = float(order_stats.gross_gmv or 0)
        verified_collected_cash = float(order_stats.verified_collected_cash or 0)
        recognized_revenue = float(order_stats.recognized_revenue or 0)
        pending_cash = float(order_stats.pending_cash or 0)
        paid_orders_count = int(order_stats.paid_orders_count or 0)
        cancelled_orders_count = int(order_stats.cancelled_orders_count or 0)
        pending_orders_count = int(order_stats.pending_orders_count or 0)

        # 2. Refunds aggregation query
        refund_filters = [
            Refund.created_at >= start_utc.replace(tzinfo=None),
            Refund.created_at <= end_utc.replace(tzinfo=None),
            Refund.status == "SUCCEEDED",
        ]
        if warehouse_id is not None:
            refund_filters.append(Refund.warehouse_id == warehouse_id)

        refund_stats = db.execute(
            select(
                func.coalesce(func.sum(Refund.amount), 0).label("refund_amount"),
                func.count(Refund.id).label("refund_count"),
            ).where(*refund_filters)
        ).one()

        refund_amount = float(refund_stats.refund_amount or 0)
        refund_count = int(refund_stats.refund_count or 0)

        # Net Cash = Verified Collected Cash - Refunds
        net_cash = verified_collected_cash - refund_amount

        # Average Order Value (AOV) on active confirmed orders
        active_orders_count = total_orders - cancelled_orders_count
        aov = round(gross_gmv / active_orders_count, 2) if active_orders_count > 0 else 0.0

        return {
            "gross_gmv": gross_gmv,
            "verified_collected_cash": verified_collected_cash,
            "refund_amount": refund_amount,
            "refund_count": refund_count,
            "net_cash": net_cash,
            "recognized_revenue": recognized_revenue,
            "pending_cash": pending_cash,
            "total_orders": total_orders,
            "paid_orders_count": paid_orders_count,
            "cancelled_orders_count": cancelled_orders_count,
            "pending_orders_count": pending_orders_count,
            "average_order_value": aov,
            "time_range": {
                "start_utc": start_utc.isoformat(),
                "end_utc": end_utc.isoformat(),
            },
        }

    @staticmethod
    def get_revenue_by_payment_method(
        db: Session,
        start_utc: datetime,
        end_utc: datetime,
        warehouse_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates breakdown by payment method (COD, SEPAY, PAYOS, etc.)."""
        order_filters = [
            Order.created_at >= start_utc.replace(tzinfo=None),
            Order.created_at <= end_utc.replace(tzinfo=None),
        ]
        if warehouse_id is not None:
            order_filters.append(Order.assigned_warehouse_id == warehouse_id)

        active_cond = Order.order_status.notin_(["CANCELLED", "REJECTED"])
        delivered_cond = Order.order_status.in_(["DELIVERED", "COMPLETED"])
        paid_cond = Order.payment_status == "PAID"

        rows = db.execute(
            select(
                func.coalesce(Order.payment_method, "COD").label("method"),
                func.count(Order.id).label("total_orders"),
                func.coalesce(
                    func.sum(case((active_cond, Order.total_amount), else_=0)), 0
                ).label("gross_gmv"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    Order.payment_method == "COD",
                                    delivered_cond,
                                ),
                                Order.total_amount,
                            ),
                            (
                                and_(
                                    Order.payment_method.in_(["SEPAY", "PAYOS", "MOMO", "VIETQR"]),
                                    paid_cond,
                                ),
                                Order.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("collected_amount"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    Order.payment_method == "COD",
                                    Order.order_status.notin_(
                                        ["DELIVERED", "COMPLETED", "CANCELLED", "REJECTED"]
                                    ),
                                ),
                                Order.total_amount,
                            ),
                            (
                                and_(
                                    Order.payment_method.in_(["SEPAY", "PAYOS", "MOMO", "VIETQR"]),
                                    Order.payment_status == "PENDING",
                                    Order.order_status.notin_(["CANCELLED", "REJECTED"]),
                                ),
                                Order.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("pending_amount"),
                func.count(case((paid_cond, Order.id))).label("paid_count"),
                func.count(case((Order.payment_status == "FAILED", Order.id))).label("failed_count"),
            )
            .where(*order_filters)
            .group_by(Order.payment_method)
            .order_by(func.sum(Order.total_amount).desc())
        ).all()

        results = []
        for r in rows:
            results.append({
                "payment_method": r.method,
                "total_orders": int(r.total_orders or 0),
                "gross_gmv": float(r.gross_gmv or 0),
                "collected_amount": float(r.collected_amount or 0),
                "pending_amount": float(r.pending_amount or 0),
                "paid_count": int(r.paid_count or 0),
                "failed_count": int(r.failed_count or 0),
            })
        return results

    @staticmethod
    def get_revenue_by_warehouse(
        db: Session,
        start_utc: datetime,
        end_utc: datetime,
    ) -> List[Dict[str, Any]]:
        """Calculates breakdown by warehouse (HCM, HN, etc.)."""
        # Fetch all active warehouses
        warehouses = db.scalars(select(Warehouse).order_by(Warehouse.id)).all()
        wh_map = {w.id: {"code": w.code, "name": w.name} for w in warehouses}

        order_filters = [
            Order.created_at >= start_utc.replace(tzinfo=None),
            Order.created_at <= end_utc.replace(tzinfo=None),
        ]

        active_cond = Order.order_status.notin_(["CANCELLED", "REJECTED"])
        delivered_cond = Order.order_status.in_(["DELIVERED", "COMPLETED"])
        paid_cond = Order.payment_status == "PAID"

        rows = db.execute(
            select(
                Order.assigned_warehouse_id.label("wh_id"),
                func.count(Order.id).label("total_orders"),
                func.coalesce(
                    func.sum(case((active_cond, Order.total_amount), else_=0)), 0
                ).label("gross_gmv"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(Order.payment_method == "COD", delivered_cond),
                                Order.total_amount,
                            ),
                            (
                                and_(
                                    Order.payment_method.in_(["SEPAY", "PAYOS", "MOMO", "VIETQR"]),
                                    paid_cond,
                                ),
                                Order.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("collected_amount"),
                func.count(case((paid_cond, Order.id))).label("paid_orders_count"),
            )
            .where(*order_filters)
            .group_by(Order.assigned_warehouse_id)
        ).all()

        # Refunds by warehouse
        refund_rows = db.execute(
            select(
                Refund.warehouse_id.label("wh_id"),
                func.coalesce(func.sum(Refund.amount), 0).label("refund_amount"),
            )
            .where(
                Refund.created_at >= start_utc.replace(tzinfo=None),
                Refund.created_at <= end_utc.replace(tzinfo=None),
                Refund.status == "SUCCEEDED",
            )
            .group_by(Refund.warehouse_id)
        ).all()
        refund_map = {r.wh_id: float(r.refund_amount or 0) for r in refund_rows}

        results = []
        # Populate known warehouses
        seen_wh = set()
        for r in rows:
            wh_id = r.wh_id
            seen_wh.add(wh_id)
            meta = wh_map.get(wh_id, {"code": f"WH-{wh_id}", "name": f"Kho #{wh_id}"})
            ref = refund_map.get(wh_id, 0.0)
            col = float(r.collected_amount or 0)
            results.append({
                "warehouse_id": wh_id,
                "warehouse_code": meta["code"],
                "warehouse_name": meta["name"],
                "total_orders": int(r.total_orders or 0),
                "gross_gmv": float(r.gross_gmv or 0),
                "collected_amount": col,
                "refund_amount": ref,
                "net_cash": col - ref,
                "paid_orders_count": int(r.paid_orders_count or 0),
            })

        # Add warehouses with 0 orders if missing
        for w in warehouses:
            if w.id not in seen_wh:
                results.append({
                    "warehouse_id": w.id,
                    "warehouse_code": w.code,
                    "warehouse_name": w.name,
                    "total_orders": 0,
                    "gross_gmv": 0.0,
                    "collected_amount": 0.0,
                    "refund_amount": refund_map.get(w.id, 0.0),
                    "net_cash": 0.0 - refund_map.get(w.id, 0.0),
                    "paid_orders_count": 0,
                })

        return sorted(results, key=lambda x: x["gross_gmv"], reverse=True)

    @staticmethod
    def get_revenue_timeseries(
        db: Session,
        start_utc: datetime,
        end_utc: datetime,
        warehouse_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates daily time series for charting within the selected period."""
        # Query orders grouped by date
        # In SQLite/Postgres: func.date(Order.created_at)
        order_filters = [
            Order.created_at >= start_utc.replace(tzinfo=None),
            Order.created_at <= end_utc.replace(tzinfo=None),
        ]
        if warehouse_id is not None:
            order_filters.append(Order.assigned_warehouse_id == warehouse_id)

        active_cond = Order.order_status.notin_(["CANCELLED", "REJECTED"])
        delivered_cond = Order.order_status.in_(["DELIVERED", "COMPLETED"])
        paid_cond = Order.payment_status == "PAID"

        date_col = func.date(Order.created_at).label("day_str")

        order_rows = db.execute(
            select(
                date_col,
                func.count(Order.id).label("order_count"),
                func.coalesce(
                    func.sum(case((active_cond, Order.total_amount), else_=0)), 0
                ).label("gross_gmv"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(Order.payment_method == "COD", delivered_cond),
                                Order.total_amount,
                            ),
                            (
                                and_(
                                    Order.payment_method.in_(["SEPAY", "PAYOS", "MOMO", "VIETQR"]),
                                    paid_cond,
                                ),
                                Order.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("collected_cash"),
            )
            .where(*order_filters)
            .group_by(date_col)
            .order_by(date_col)
        ).all()

        order_daily = {
            str(r.day_str): {
                "order_count": int(r.order_count or 0),
                "gross_gmv": float(r.gross_gmv or 0),
                "collected_cash": float(r.collected_cash or 0),
            }
            for r in order_rows
        }

        # Query refunds grouped by date
        refund_filters = [
            Refund.created_at >= start_utc.replace(tzinfo=None),
            Refund.created_at <= end_utc.replace(tzinfo=None),
            Refund.status == "SUCCEEDED",
        ]
        if warehouse_id is not None:
            refund_filters.append(Refund.warehouse_id == warehouse_id)

        refund_date_col = func.date(Refund.created_at).label("day_str")
        refund_rows = db.execute(
            select(
                refund_date_col,
                func.coalesce(func.sum(Refund.amount), 0).label("refund_amount"),
            )
            .where(*refund_filters)
            .group_by(refund_date_col)
        ).all()
        refund_daily = {str(r.day_str): float(r.refund_amount or 0) for r in refund_rows}

        # Build contiguous list of days
        cur_day = start_utc.astimezone(VN_TZ).date()
        end_day = end_utc.astimezone(VN_TZ).date()
        series = []

        while cur_day <= end_day:
            day_key = cur_day.isoformat()
            o_data = order_daily.get(day_key, {"order_count": 0, "gross_gmv": 0.0, "collected_cash": 0.0})
            ref = refund_daily.get(day_key, 0.0)
            col = o_data["collected_cash"]
            series.append({
                "date": day_key,
                "order_count": o_data["order_count"],
                "gross_gmv": o_data["gross_gmv"],
                "collected_cash": col,
                "refund_amount": ref,
                "net_cash": col - ref,
            })
            cur_day += timedelta(days=1)

        return series

    @staticmethod
    def get_financial_transactions(
        db: Session,
        start_utc: datetime,
        end_utc: datetime,
        warehouse_id: Optional[int] = None,
        payment_method: Optional[str] = None,
        payment_status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Returns paginated order transactions with financial breakdown."""
        filters = [
            Order.created_at >= start_utc.replace(tzinfo=None),
            Order.created_at <= end_utc.replace(tzinfo=None),
        ]
        if warehouse_id is not None:
            filters.append(Order.assigned_warehouse_id == warehouse_id)
        if payment_method and payment_method != "ALL":
            filters.append(Order.payment_method == payment_method)
        if payment_status and payment_status != "ALL":
            filters.append(Order.payment_status == payment_status)
        if search and search.strip():
            kw = f"%{search.strip()}%"
            filters.append(
                or_(
                    Order.order_code.ilike(kw),
                    Order.customer_name.ilike(kw),
                    Order.customer_phone.ilike(kw),
                )
            )

        query = select(Order).where(*filters)
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

        offset = (page - 1) * page_size
        orders = db.scalars(query.order_by(Order.created_at.desc()).offset(offset).limit(page_size)).all()

        # Warehouses map
        warehouses = db.scalars(select(Warehouse)).all()
        wh_map = {w.id: w.name for w in warehouses}

        items = []
        for o in orders:
            # Determine cash collected status
            is_collected = False
            if o.payment_method == "COD" and o.order_status in ["DELIVERED", "COMPLETED"]:
                is_collected = True
            elif o.payment_method in ["SEPAY", "PAYOS", "MOMO", "VIETQR"] and o.payment_status == "PAID":
                is_collected = True

            items.append({
                "id": o.id,
                "order_code": o.order_code,
                "customer_name": o.customer_name or "Khách mua",
                "customer_phone": o.customer_phone or "—",
                "payment_method": o.payment_method or "COD",
                "payment_status": o.payment_status or "PENDING",
                "order_status": o.order_status or "PENDING",
                "total_amount": float(o.total_amount or 0),
                "shipping_fee": float(o.shipping_fee or 0),
                "discount_amount": float(o.discount_amount or 0),
                "warehouse_id": o.assigned_warehouse_id,
                "warehouse_name": wh_map.get(o.assigned_warehouse_id, "Kho trung tâm"),
                "is_cash_collected": is_collected,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

        import math
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }
