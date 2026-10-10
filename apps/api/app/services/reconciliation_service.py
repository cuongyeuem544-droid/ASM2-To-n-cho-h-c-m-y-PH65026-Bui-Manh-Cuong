import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import Order, PaymentTransaction, PaymentWebhookEvent
from app.services.alert_notifier import dispatch_alert

logger = logging.getLogger("pharmatrust.reconciliation")


def utcnow() -> datetime:
    return datetime.now(UTC)


class PaymentReconciliationService:
    """
    Dịch vụ Đối soát Tài chính & Cổng Thanh toán (Payment Reconciliation Engine) H4CARE:
    - Đối soát giữa giá trị đơn hàng thực tế và tổng tiền quyết toán thành công qua cổng (MoMo, VietQR, COD).
    - Phát hiện tức thì các trường hợp:
      + Khớp hoàn toàn (MATCHED)
      + Thừa tiền (OVERPAID - cảnh báo hoàn tiền phần thừa)
      + Thiếu tiền (UNDERPAID - cảnh báo thu thêm)
      + Trùng lặp giao dịch (DUPLICATE_PAYMENT - khách thanh toán 2 lần)
      + Sai lệch trạng thái dữ liệu (INCONSISTENT_STATUS - tiền đã vào nhưng đơn chưa chuyển PAID)
    - Tự động khắc phục sai lệch trạng thái an toàn (Auto-heal Inconsistency).
    - Xuất báo cáo kiểm toán đối soát định kỳ.
    """

    @classmethod
    def reconcile_order(cls, db: Session, order_code: str) -> dict[str, Any]:
        """
        Đối soát chi tiết một đơn hàng cụ thể.
        """
        clean_code = order_code.strip()
        order = db.scalar(select(Order).where(Order.order_code == clean_code))
        if not order:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{clean_code}'.")

        transactions = db.scalars(
            select(PaymentTransaction)
            .where(PaymentTransaction.order_id == order.id)
            .order_by(PaymentTransaction.id.asc())
        ).all()

        success_transactions = [t for t in transactions if t.status == "SUCCESS"]
        captured_amount = sum(t.amount for t in success_transactions)
        order_total = Decimal(str(order.total_amount))
        difference = captured_amount - order_total

        # Phân loại trạng thái đối soát
        discrepancy_type: Optional[str] = None
        reconciliation_status: str = "MATCHED"

        if len(success_transactions) > 1:
            reconciliation_status = "DISCREPANCY"
            discrepancy_type = "DUPLICATE_PAYMENT"
        elif captured_amount == Decimal("0.0"):
            if order.payment_status == "PAID":
                reconciliation_status = "DISCREPANCY"
                discrepancy_type = "PAID_WITHOUT_TRANSACTION"
            else:
                reconciliation_status = "UNPAID"
        elif difference > Decimal("0.0"):
            reconciliation_status = "DISCREPANCY"
            discrepancy_type = "OVERPAID"
        elif difference < Decimal("0.0"):
            reconciliation_status = "DISCREPANCY"
            discrepancy_type = "UNDERPAID"
        elif captured_amount == order_total and order.payment_status != "PAID":
            reconciliation_status = "DISCREPANCY"
            discrepancy_type = "INCONSISTENT_STATUS"
        else:
            reconciliation_status = "MATCHED"

        return {
            "order_code": order.order_code,
            "order_total": float(order_total),
            "captured_amount": float(captured_amount),
            "difference": float(difference),
            "order_payment_status": order.payment_status,
            "order_status": order.order_status,
            "reconciliation_status": reconciliation_status,
            "discrepancy_type": discrepancy_type,
            "success_transaction_count": len(success_transactions),
            "total_transaction_count": len(transactions),
            "transactions": [
                {
                    "id": t.id,
                    "transaction_code": t.transaction_code,
                    "provider": t.provider,
                    "amount": float(t.amount),
                    "status": t.status,
                    "provider_trans_id": t.provider_trans_id,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in transactions
            ],
            "is_balanced": difference == Decimal("0.0") and order.payment_status == "PAID",
        }

    @classmethod
    def auto_heal_order(cls, db: Session, order_code: str) -> dict[str, Any]:
        """
        Tự động khắc phục sai lệch nếu tiền đã thực nhận đủ 100% nhưng đơn hàng chưa chuyển sang PAID.
        """
        recon = cls.reconcile_order(db=db, order_code=order_code)
        if recon["discrepancy_type"] == "INCONSISTENT_STATUS":
            order = db.scalar(select(Order).where(Order.order_code == order_code.strip()))
            if order:
                order.payment_status = "PAID"
                if order.order_status == "PENDING":
                    order.order_status = "CONFIRMED"
                db.commit()
                logger.info(f"[RECONCILIATION] Đã tự động chữa lành trạng thái đơn hàng {order.order_code} -> PAID / CONFIRMED")
                recon = cls.reconcile_order(db=db, order_code=order_code)
        return recon

    @classmethod
    def audit_system(cls, db: Session, limit: int = 100) -> dict[str, Any]:
        """
        Quét và kiểm toán toàn diện tình trạng đối soát các đơn hàng gần đây.
        """
        orders = db.scalars(
            select(Order).order_by(desc(Order.id)).limit(limit)
        ).all()

        total_orders = len(orders)
        matched_count = 0
        unpaid_count = 0
        discrepancy_count = 0
        overpaid_count = 0
        underpaid_count = 0
        duplicate_count = 0

        discrepancies: list[dict[str, Any]] = []

        for o in orders:
            res = cls.reconcile_order(db=db, order_code=o.order_code)
            status = res["reconciliation_status"]
            disc = res["discrepancy_type"]

            if status == "MATCHED":
                matched_count += 1
            elif status == "UNPAID":
                unpaid_count += 1
            elif status == "DISCREPANCY":
                discrepancy_count += 1
                if disc == "OVERPAID":
                    overpaid_count += 1
                elif disc == "UNDERPAID":
                    underpaid_count += 1
                elif disc == "DUPLICATE_PAYMENT":
                    duplicate_count += 1
                discrepancies.append(res)

        return {
            "total_orders_audited": total_orders,
            "matched_orders": matched_count,
            "unpaid_orders": unpaid_count,
            "discrepancy_orders": discrepancy_count,
            "breakdown": {
                "overpaid": overpaid_count,
                "underpaid": underpaid_count,
                "duplicate_payments": duplicate_count,
            },
            "discrepancies": discrepancies,
            "audited_at": utcnow().isoformat(),
        }
