"""H4CARE Admin Revenue Analytics Router

Endpoints for comprehensive financial reporting, double-counting audit,
and revenue dashboard for Admin role.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.services.revenue_analytics_service import (
    RevenueAnalyticsService,
    resolve_date_range,
)

router = APIRouter(
    prefix="/admin/analytics/revenue",
    tags=["Quản trị - Doanh thu & Dòng tiền"],
)


@router.get("/summary")
def get_revenue_summary(
    range_type: str = Query(
        default="30d",
        description="today, yesterday, 7d, 30d, this_month, last_month, this_quarter, this_year, custom",
    ),
    start_date: Optional[str] = Query(default=None, description="YYYY-MM-DD for custom range"),
    end_date: Optional[str] = Query(default=None, description="YYYY-MM-DD for custom range"),
    warehouse_id: Optional[int] = Query(default=None, description="Filter by warehouse ID"),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the master financial summary: Gross GMV, Verified Cash, Refunds, Net Cash, AOV."""
    start_utc, end_utc = resolve_date_range(range_type, start_date, end_date)
    return RevenueAnalyticsService.get_revenue_summary(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        warehouse_id=warehouse_id,
    )


@router.get("/by-payment-method")
def get_revenue_by_payment_method(
    range_type: str = Query(default="30d"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    warehouse_id: Optional[int] = Query(default=None),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns revenue breakdown by payment method (COD, SePay, payOS)."""
    start_utc, end_utc = resolve_date_range(range_type, start_date, end_date)
    return RevenueAnalyticsService.get_revenue_by_payment_method(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        warehouse_id=warehouse_id,
    )


@router.get("/by-warehouse")
def get_revenue_by_warehouse(
    range_type: str = Query(default="30d"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns revenue and refund allocation across warehouses (HCM, HN)."""
    start_utc, end_utc = resolve_date_range(range_type, start_date, end_date)
    return RevenueAnalyticsService.get_revenue_by_warehouse(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
    )


@router.get("/timeseries")
def get_revenue_timeseries(
    range_type: str = Query(default="30d"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    warehouse_id: Optional[int] = Query(default=None),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns daily time-series data points for charting GMV, Collected Cash, and Net Cash."""
    start_utc, end_utc = resolve_date_range(range_type, start_date, end_date)
    return RevenueAnalyticsService.get_revenue_timeseries(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        warehouse_id=warehouse_id,
    )


@router.get("/transactions")
def get_revenue_transactions(
    range_type: str = Query(default="30d"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    warehouse_id: Optional[int] = Query(default=None),
    payment_method: Optional[str] = Query(default=None),
    payment_status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns paginated financial transactions feed with search and status filters."""
    start_utc, end_utc = resolve_date_range(range_type, start_date, end_date)
    return RevenueAnalyticsService.get_financial_transactions(
        db=db,
        start_utc=start_utc,
        end_utc=end_utc,
        warehouse_id=warehouse_id,
        payment_method=payment_method,
        payment_status=payment_status,
        search=search,
        page=page,
        page_size=page_size,
    )
