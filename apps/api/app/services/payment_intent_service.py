import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    ExchangeOrder,
    Order,
    PaymentTransaction,
)
from app.models.returns import ExchangeStatus
from app.services.momo_service import MomoPaymentService
from app.services.vietqr_service import VietQrService

logger = logging.getLogger("pharmatrust.payment_intent")


def utcnow() -> datetime:
    return datetime.now(UTC)


class PaymentIntentService:
    """
    Dịch vụ Điều phối Ý định Thanh toán Hợp nhất (Unified Payment Intent Engine) H4CARE:
    - Quản lý vòng đời Payment Intent cho đơn hàng Storefront và phụ phí đơn đổi hàng (ExchangeOrder).
    - Hỗ trợ đầy đủ COD, MoMo Sandbox, VietQR Napas 247.
    - Hỗ trợ cơ chế Thanh toán lại (Payment Retry) và chuyển đổi linh hoạt phương thức thanh toán.
    - Quản lý phiên giao dịch có thời hạn hết hạn (Timeout & Expiration).
    """

    @classmethod
    def create_intent(
        cls,
        db: Session,
        order_code: str,
        payment_method: str = "COD",
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Khởi tạo Payment Intent hợp nhất cho đơn hàng mua thuốc.
        """
        clean_code = order_code.strip()
        order = db.scalar(select(Order).where(Order.order_code == clean_code))
        if not order:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{clean_code}'.")

        if order.payment_status == "PAID":
            raise HTTPException(status_code=400, detail="Đơn hàng này đã hoàn tất thanh toán thành công trước đó.")

        if order.order_status == "CANCELLED":
            raise HTTPException(status_code=400, detail="Đơn hàng này đã bị hủy, không thể khởi tạo thanh toán.")

        method = payment_method.strip().upper()
        if method in ["BANK_TRANSFER", "VIETQR"]:
            provider = "VIETQR"
        elif method == "MOMO":
            provider = "MOMO"
        elif method == "COD":
            provider = "COD"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Phương thức thanh toán '{payment_method}' không được hỗ trợ. Chọn COD, VIETQR hoặc MOMO.",
            )

        amount = int(order.total_amount)
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.payment_expiry_minutes)

        intent_id = f"PI-{order.order_code}-{int(datetime.now().timestamp() * 1000) % 1000000}"
        pay_url: Optional[str] = None
        qr_code_url: Optional[str] = None
        deeplink: Optional[str] = None
        bank_details: Optional[dict[str, Any]] = None
        instructions: str = ""

        if provider == "COD":
            # Tạo hoặc cập nhật PaymentTransaction cho COD
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order.id,
                    PaymentTransaction.provider == "COD",
                )
            )
            if not trans:
                trans = PaymentTransaction(
                    order_id=order.id,
                    transaction_code=f"TXN-COD-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                    provider="COD",
                    amount=Decimal(str(amount)),
                    currency="VND",
                    status="PENDING",
                    provider_response_raw=json.dumps({"type": "COD", "intent_id": intent_id}, ensure_ascii=False),
                )
                db.add(trans)
            else:
                trans.amount = Decimal(str(amount))
                trans.status = "PENDING"

            order.payment_method = "COD"
            instructions = "Thanh toán bằng tiền mặt trực tiếp cho nhân viên giao hàng khi nhận và kiểm tra gói thuốc."
            db.commit()
            db.refresh(trans)

        elif provider == "VIETQR":
            vqr_res = VietQrService.create_payment_request(db=db, order=order, return_url=return_url)
            qr_code_url = vqr_res.get("qr_code_url")
            instructions = f"Quét mã VietQR trên bất kỳ ứng dụng ngân hàng nào với số tiền {amount:,} đ và nội dung '{order.order_code}'."
            bank_details = {
                "bank_name": vqr_res.get("bank_name"),
                "bank_id": vqr_res.get("bank_id"),
                "account_number": vqr_res.get("account_number"),
                "account_holder": vqr_res.get("account_holder"),
                "transfer_memo": vqr_res.get("transfer_memo"),
            }
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order.id,
                    PaymentTransaction.provider == "VIETQR",
                )
            )

        elif provider == "MOMO":
            momo_res = MomoPaymentService.create_payment_request(db=db, order=order, return_url=return_url)
            pay_url = momo_res.get("pay_url")
            qr_code_url = momo_res.get("qr_code_url")
            deeplink = momo_res.get("deeplink")
            instructions = "Mở ứng dụng MoMo để quét mã hoặc thanh toán trực tiếp qua cổng MoMo Sandbox."
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order.id,
                    PaymentTransaction.provider == "MOMO",
                )
            )

        return {
            "intent_id": intent_id,
            "order_code": order.order_code,
            "transaction_code": trans.transaction_code if trans else None,
            "provider": provider,
            "payment_method": order.payment_method,
            "amount": amount,
            "currency": "VND",
            "status": "PENDING",
            "pay_url": pay_url,
            "qr_code_url": qr_code_url,
            "deeplink": deeplink,
            "bank_details": bank_details,
            "instructions": instructions,
            "expires_at": expires_at.isoformat(),
        }

    @classmethod
    def retry_payment(
        cls,
        db: Session,
        order_code: str,
        new_payment_method: str,
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Cơ chế Thử lại Thanh toán (Payment Retry) & Chuyển đổi Cổng thanh toán:
        - Hủy giao dịch PENDING trước đó.
        - Khởi tạo Intent mới với phương thức mong muốn (COD, MOMO, VIETQR).
        """
        clean_code = order_code.strip()
        order = db.scalar(select(Order).where(Order.order_code == clean_code))
        if not order:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{clean_code}'.")

        if order.payment_status == "PAID":
            raise HTTPException(status_code=400, detail="Đơn hàng này đã được thanh toán thành công, không thể thanh toán lại.")

        if order.order_status == "CANCELLED":
            raise HTTPException(status_code=400, detail="Đơn hàng này đã bị hủy, không thể tiếp tục thanh toán.")

        # Hủy các giao dịch đang PENDING của đơn hàng này
        pending_transactions = db.scalars(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.status == "PENDING",
            )
        ).all()
        for t in pending_transactions:
            t.status = "CANCELLED"
            t.updated_at = utcnow()

        db.commit()

        # Tạo Payment Intent mới
        return cls.create_intent(
            db=db,
            order_code=clean_code,
            payment_method=new_payment_method,
            return_url=return_url,
        )

    @classmethod
    def create_exchange_intent(
        cls,
        db: Session,
        exchange_code: str,
        payment_method: str = "VIETQR",
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Khởi tạo Payment Intent thu phụ phí chênh lệch cho Đơn đổi hàng (ExchangeOrder).
        """
        clean_code = exchange_code.strip().upper()
        exchange = db.scalar(select(ExchangeOrder).where(ExchangeOrder.exchange_code == clean_code))
        if not exchange:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn đổi hàng '{clean_code}'.")

        if exchange.status != ExchangeStatus.WAITING_PAYMENT.value:
            raise HTTPException(
                status_code=400,
                detail=f"Đơn đổi hàng '{clean_code}' hiện không chờ thanh toán phụ phí (Trạng thái: {exchange.status}).",
            )

        amount = int(exchange.price_difference)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Đơn đổi hàng này không có phụ phí phát sinh.")

        method = payment_method.strip().upper()
        if method in ["BANK_TRANSFER", "VIETQR"]:
            provider = "VIETQR"
        elif method == "MOMO":
            provider = "MOMO"
        elif method == "COD":
            provider = "COD"
        else:
            raise HTTPException(status_code=400, detail=f"Phương thức '{payment_method}' không hỗ trợ.")

        intent_id = f"PI-EXC-{exchange.exchange_code}-{int(datetime.now().timestamp() * 1000) % 1000000}"
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.payment_expiry_minutes)

        if provider == "VIETQR":
            vqr_res = VietQrService.create_exchange_payment_request(db=db, exchange=exchange)
            return {
                "intent_id": intent_id,
                "exchange_code": exchange.exchange_code,
                "transaction_code": vqr_res.get("transaction_code"),
                "provider": "VIETQR",
                "payment_method": "BANK_TRANSFER",
                "amount": amount,
                "currency": "VND",
                "status": "PENDING",
                "qr_code_url": vqr_res.get("qr_code_url"),
                "bank_details": {
                    "bank_name": vqr_res.get("bank_name"),
                    "bank_id": vqr_res.get("bank_id"),
                    "account_number": vqr_res.get("account_number"),
                    "account_holder": vqr_res.get("account_holder"),
                    "transfer_memo": vqr_res.get("transfer_memo"),
                },
                "instructions": f"Quét mã VietQR trên ứng dụng ngân hàng với số tiền {amount:,} đ và nội dung '{exchange.exchange_code}'.",
                "expires_at": expires_at.isoformat(),
            }

        elif provider == "COD":
            metadata = {"exchange_code": exchange.exchange_code, "type": "EXCHANGE_COD"}
            trans = PaymentTransaction(
                order_id=exchange.original_order_id,
                transaction_code=f"TXN-EXC-COD-{exchange.exchange_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="COD",
                amount=Decimal(str(amount)),
                currency="VND",
                status="PENDING",
                provider_response_raw=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(trans)
            db.flush()
            exchange.additional_payment_transaction_id = trans.id
            db.commit()

            return {
                "intent_id": intent_id,
                "exchange_code": exchange.exchange_code,
                "transaction_code": trans.transaction_code,
                "provider": "COD",
                "payment_method": "COD",
                "amount": amount,
                "currency": "VND",
                "status": "PENDING",
                "instructions": "Thu phụ phí tiền mặt khi nhân viên giao kiện hàng thuốc mới thay thế.",
                "expires_at": expires_at.isoformat(),
            }

        else:  # MOMO
            # MoMo for exchange
            metadata = {"exchange_code": exchange.exchange_code, "type": "EXCHANGE_MOMO"}
            sim_url = f"{settings.momo_return_url}?orderId={exchange.exchange_code}&resultCode=0&message=SimulatedSuccess"
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=2|99|MOMO|{exchange.exchange_code}|{amount}"
            trans = PaymentTransaction(
                order_id=exchange.original_order_id,
                transaction_code=f"TXN-EXC-MOMO-{exchange.exchange_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="MOMO",
                amount=Decimal(str(amount)),
                currency="VND",
                status="PENDING",
                provider_pay_url=sim_url,
                provider_response_raw=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(trans)
            db.flush()
            exchange.additional_payment_transaction_id = trans.id
            db.commit()

            return {
                "intent_id": intent_id,
                "exchange_code": exchange.exchange_code,
                "transaction_code": trans.transaction_code,
                "provider": "MOMO",
                "payment_method": "MOMO",
                "amount": amount,
                "currency": "VND",
                "status": "PENDING",
                "pay_url": sim_url,
                "qr_code_url": qr_url,
                "deeplink": f"momo://app?action=payWithApp&orderId={exchange.exchange_code}&amount={amount}",
                "instructions": "Quét mã MoMo để thanh toán khoản tiền chênh lệch đổi hàng.",
                "expires_at": expires_at.isoformat(),
            }

    @classmethod
    def get_order_payment_summary(cls, db: Session, order_code: str) -> dict[str, Any]:
        """
        Tra cứu chi tiết lịch sử và tình trạng thanh toán của đơn hàng.
        """
        clean_code = order_code.strip()
        order = db.scalar(select(Order).where(Order.order_code == clean_code))
        if not order:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")

        transactions = db.scalars(
            select(PaymentTransaction)
            .where(PaymentTransaction.order_id == order.id)
            .order_by(desc(PaymentTransaction.id))
        ).all()

        latest_trans = transactions[0] if transactions else None
        can_retry = (
            order.payment_status in ["PENDING", "FAILED"]
            and order.order_status not in ["CANCELLED", "COMPLETED"]
        )

        return {
            "order_code": order.order_code,
            "payment_status": order.payment_status,
            "payment_method": order.payment_method,
            "order_status": order.order_status,
            "total_amount": float(order.total_amount),
            "customer_name": order.customer_name,
            "can_retry": can_retry,
            "latest_transaction": {
                "id": latest_trans.id,
                "transaction_code": latest_trans.transaction_code,
                "provider": latest_trans.provider,
                "amount": float(latest_trans.amount),
                "status": latest_trans.status,
                "provider_trans_id": latest_trans.provider_trans_id,
                "created_at": latest_trans.created_at.isoformat() if latest_trans.created_at else None,
            } if latest_trans else None,
            "transactions": [
                {
                    "id": t.id,
                    "transaction_code": t.transaction_code,
                    "provider": t.provider,
                    "amount": float(t.amount),
                    "status": t.status,
                    "provider_trans_id": t.provider_trans_id,
                    "provider_pay_url": t.provider_pay_url,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in transactions
            ],
        }
