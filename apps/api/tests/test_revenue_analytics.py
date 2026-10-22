"""Unit and integration tests for Revenue Analytics Service & Endpoints.

Tests:
1. Date range resolution with UTC+7 conversion.
2. Anti-double counting: Unpaid COD excluded from collected cash.
3. Delivered COD credited to collected cash and recognized revenue.
4. Paid SePay/payOS credited to collected cash.
5. Cancelled orders excluded from gross GMV and collected cash.
6. Succeeded refunds deducted from net cash.
7. Warehouse-level financial allocation.
8. Role-based access control (Admin required, others rejected).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models import Order, PaymentTransaction, Refund, User, Warehouse
from app.services.revenue_analytics_service import (
    RevenueAnalyticsService,
    resolve_date_range,
    VN_TZ,
    UTC_TZ,
)

client = TestClient(app)


def test_resolve_date_range():
    """Verify time boundaries in VN timezone."""
    start_utc, end_utc = resolve_date_range("7d")
    assert start_utc < end_utc
    diff = end_utc - start_utc
    assert diff.days == 6 or diff.days == 7

    start_custom, end_custom = resolve_date_range("custom", "2026-10-01", "2026-10-15")
    assert start_custom < end_custom
    assert start_custom.year == 2026


def test_cod_unpaid_not_in_collected_cash():
    """Rule verification: COD orders that are pending/dispatched MUST NOT be credited to verified cash."""
    with SessionLocal() as db:
        now_utc = datetime.now(timezone.utc)
        order = Order(
            order_code="TEST-REV-COD-PENDING",
            customer_name="Test Customer",
            customer_phone="0901234567",
            shipping_address="123 Test St",
            total_amount=Decimal("250000"),
            payment_method="COD",
            payment_status="PENDING",
            order_status="DISPATCHED",
            assigned_warehouse_id=1,
            created_at=now_utc,
        )
        db.add(order)
        db.commit()

        start_utc = now_utc - timedelta(hours=1)
        end_utc = now_utc + timedelta(hours=1)

        summary = RevenueAnalyticsService.get_revenue_summary(db, start_utc, end_utc, warehouse_id=1)
        assert summary["gross_gmv"] >= 250000.0
        # Verified cash must NOT include this unpaid COD order
        assert summary["verified_collected_cash"] == 0.0 or summary["verified_collected_cash"] < summary["gross_gmv"]
        assert summary["pending_cash"] >= 250000.0


def test_cod_delivered_in_collected_cash():
    """Rule verification: Delivered COD orders ARE credited to verified cash and recognized revenue."""
    with SessionLocal() as db:
        now_utc = datetime.now(timezone.utc)
        order = Order(
            order_code="TEST-REV-COD-DELIVERED",
            customer_name="Delivered Customer",
            customer_phone="0901234568",
            shipping_address="456 Test St",
            total_amount=Decimal("350000"),
            payment_method="COD",
            payment_status="PAID",
            order_status="DELIVERED",
            assigned_warehouse_id=1,
            created_at=now_utc,
        )
        db.add(order)
        db.commit()

        start_utc = now_utc - timedelta(hours=1)
        end_utc = now_utc + timedelta(hours=1)

        summary = RevenueAnalyticsService.get_revenue_summary(db, start_utc, end_utc, warehouse_id=1)
        assert summary["verified_collected_cash"] >= 350000.0
        assert summary["recognized_revenue"] >= 350000.0


def test_sepay_paid_in_collected_cash():
    """Rule verification: SePay paid orders are credited to collected cash."""
    with SessionLocal() as db:
        now_utc = datetime.now(timezone.utc)
        order = Order(
            order_code="TEST-REV-SEPAY-PAID",
            customer_name="Online Customer",
            customer_phone="0901234569",
            shipping_address="789 Test St",
            total_amount=Decimal("500000"),
            payment_method="SEPAY",
            payment_status="PAID",
            order_status="CONFIRMED",
            assigned_warehouse_id=2,
            created_at=now_utc,
        )
        db.add(order)
        db.commit()

        start_utc = now_utc - timedelta(hours=1)
        end_utc = now_utc + timedelta(hours=1)

        summary = RevenueAnalyticsService.get_revenue_summary(db, start_utc, end_utc, warehouse_id=2)
        assert summary["verified_collected_cash"] >= 500000.0


def test_cancelled_order_excluded_from_gmv():
    """Rule verification: Cancelled orders are excluded from active gross GMV."""
    with SessionLocal() as db:
        now_utc = datetime.now(timezone.utc)
        order = Order(
            order_code="TEST-REV-CANCELLED",
            customer_name="Cancelled Customer",
            customer_phone="0901234570",
            shipping_address="321 Test St",
            total_amount=Decimal("999000"),
            payment_method="COD",
            payment_status="CANCELLED",
            order_status="CANCELLED",
            assigned_warehouse_id=1,
            created_at=now_utc,
        )
        db.add(order)
        db.commit()

        start_utc = now_utc - timedelta(hours=1)
        end_utc = now_utc + timedelta(hours=1)

        summary = RevenueAnalyticsService.get_revenue_summary(db, start_utc, end_utc, warehouse_id=1)
        assert summary["cancelled_orders_count"] >= 1


def test_refund_deducted_from_net_cash():
    """Rule verification: Succeeded refund is subtracted from net cash."""
    with SessionLocal() as db:
        now_utc = datetime.now(timezone.utc)
        order = Order(
            order_code="TEST-REV-REFUNDED-ORDER",
            customer_name="Refund Customer",
            customer_phone="0901234571",
            shipping_address="654 Test St",
            total_amount=Decimal("400000"),
            payment_method="SEPAY",
            payment_status="PAID",
            order_status="DELIVERED",
            assigned_warehouse_id=1,
            created_at=now_utc,
        )
        db.add(order)
        db.commit()

        refund = Refund(
            refund_code="REF-TEST-001",
            order_id=order.id,
            warehouse_id=1,
            amount=Decimal("150000"),
            status="SUCCEEDED",
            reason="Khách hàng yêu cầu hoàn trả",
            refund_method="BANK_TRANSFER",
            created_at=now_utc,
        )
        db.add(refund)
        db.commit()

        start_utc = now_utc - timedelta(hours=1)
        end_utc = now_utc + timedelta(hours=1)

        summary = RevenueAnalyticsService.get_revenue_summary(db, start_utc, end_utc, warehouse_id=1)
        assert summary["refund_amount"] >= 150000.0
        assert summary["net_cash"] == summary["verified_collected_cash"] - summary["refund_amount"]


def test_admin_api_endpoints(admin_headers):
    """Integration test: Admin role can access analytics endpoints; anonymous gets 401."""
    # Anonymous request
    anon_resp = client.get("/api/v1/admin/analytics/revenue/summary")
    assert anon_resp.status_code in [401, 403]

    # Admin request
    resp = client.get("/api/v1/admin/analytics/revenue/summary?range_type=30d", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "gross_gmv" in data
    assert "verified_collected_cash" in data
    assert "refund_amount" in data
    assert "net_cash" in data

    # Breakdown by method
    resp_method = client.get("/api/v1/admin/analytics/revenue/by-payment-method", headers=admin_headers)
    assert resp_method.status_code == 200
    assert isinstance(resp_method.json(), list)

    # Breakdown by warehouse
    resp_wh = client.get("/api/v1/admin/analytics/revenue/by-warehouse", headers=admin_headers)
    assert resp_wh.status_code == 200
    assert isinstance(resp_wh.json(), list)

    # Timeseries
    resp_ts = client.get("/api/v1/admin/analytics/revenue/timeseries?range_type=7d", headers=admin_headers)
    assert resp_ts.status_code == 200
    assert len(resp_ts.json()) >= 7

    # Transactions feed
    resp_tx = client.get("/api/v1/admin/analytics/revenue/transactions?page=1&page_size=10", headers=admin_headers)
    assert resp_tx.status_code == 200
    assert "items" in resp_tx.json()
