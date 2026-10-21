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
from app.services.payos_service import PayOSPaymentService
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
        if method in ["BANK_TRANSFER", "VIETQR", "MOMO"]:
            raise HTTPException(
                status_code=400,
                detail=f"Phương thức thanh toán '{payment_method}' đã ngừng hỗ trợ cho đơn hàng mới. Vui lòng chọn COD hoặc Cổng thanh toán payOS.",
            )
        elif method == "PAYOS":
            if not getattr(settings, "is_payos_configured", False):
                raise HTTPException(
                    status_code=503,
                    detail="Cổng thanh toán payOS hiện chưa được cấu hình sẵn sàng trên máy chủ. Vui lòng chọn Thanh toán khi nhận hàng (COD) hoặc Chuyển khoản VietQR MBBank (SePay).",
                )
            provider = "PAYOS"
        elif method == "COD":
            provider = "COD"
        elif method == "SEPAY":
            provider = "SEPAY"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Phương thức thanh toán '{payment_method}' không được hỗ trợ. Vui lòng chọn COD, payOS hoặc SEPAY.",
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
            order.payment_method = "COD"
            if order.fulfillment_status == "WAITING_PAYMENT":
                order.fulfillment_status = "ALLOCATED"
                if order.assigned_warehouse_id:
                    try:
                        from app.services.warehouse_notification_service import WarehouseNotificationService
                        WarehouseNotificationService.notify_order_new(db, order, order.assigned_warehouse_id)
                    except Exception as n_err:
                        logger.warning(f"Failed to notify warehouse when switching to COD: {n_err}")

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

        elif provider == "PAYOS":
            pos_res = PayOSPaymentService.create_payment_request(db=db, order=order, return_url=return_url)
            pay_url = pos_res.get("checkout_url")
            qr_code_url = pos_res.get("qr_code")
            instructions = f"Quét mã VietQR trên bất kỳ ứng dụng ngân hàng nào hoặc mở cổng payOS để thanh toán {amount:,} đ."
            bank_details = {
                "bank_name": "payOS Gateway",
                "account_number": pos_res.get("account_number"),
                "account_name": pos_res.get("account_name"),
                "bin": pos_res.get("bin"),
                "payos_order_code": pos_res.get("payos_order_code"),
            }
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order.id,
                    PaymentTransaction.provider == "PAYOS",
                )
            )

        elif provider == "SEPAY":
            from app.services.sepay_service import SepayService
            sepay_res = SepayService.create_payment_request(db=db, order=order, return_url=return_url)
            qr_code_url = sepay_res.get("qr_code_url")
            instructions = f"Quét mã VietQR trên bất kỳ ứng dụng ngân hàng nào với số tiền {amount:,} đ và nội dung '{sepay_res.get('payment_code')}'."
            bank_details = {
                "bank_name": sepay_res.get("bank_name"),
                "bank_id": sepay_res.get("bank_id"),
                "account_number": sepay_res.get("account_number"),
                "account_holder": sepay_res.get("account_holder"),
                "payment_code": sepay_res.get("payment_code"),
                "transfer_memo": sepay_res.get("payment_code"),
            }
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order.id,
                    PaymentTransaction.provider == "SEPAY",
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
        - Sử dụng Row Locking (with_for_update) chống race condition.
        - Kiểm tra trạng thái thanh toán mới nhất trước khi chuyển.
        - Hủy link thanh toán đang mở trên cổng payOS nếu đổi phương thức.
        - Hủy các giao dịch PENDING trước đó an toàn.
        - Không tạo order_id mới: giữ nguyên mã đơn, danh sách thuốc, giá, kho và voucher.
        """
        clean_code = order_code.strip()
        # Row locking chống race condition
        order = db.scalar(select(Order).where(Order.order_code == clean_code).with_for_update())
        if not order:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{clean_code}'.")

        if order.payment_status == "PAID":
            raise HTTPException(status_code=400, detail="Đơn hàng này đã được thanh toán thành công, không thể thay đổi phương thức.")

        if order.order_status == "CANCELLED":
            raise HTTPException(status_code=400, detail="Đơn hàng này đã bị hủy, không thể tiếp tục thanh toán.")

        # Xác thực phương thức thanh toán mới trước khi thao tác
        method = new_payment_method.strip().upper()
        if method in ["BANK_TRANSFER", "VIETQR", "MOMO"]:
            raise HTTPException(
                status_code=400,
                detail=f"Phương thức thanh toán '{new_payment_method}' đã ngừng hỗ trợ cho giao dịch mới. Vui lòng chọn COD hoặc Cổng thanh toán payOS.",
            )
        if method not in ["COD", "PAYOS", "SEPAY"]:
            raise HTTPException(
                status_code=400,
                detail=f"Phương thức thanh toán '{new_payment_method}' không được hỗ trợ. Vui lòng chọn COD, payOS hoặc SEPAY.",
            )

        if method == "PAYOS" and not getattr(settings, "is_payos_configured", False):
            raise HTTPException(
                status_code=503,
                detail="Cổng thanh toán payOS hiện chưa được cấu hình sẵn sàng trên máy chủ. Vui lòng chọn COD hoặc SePay.",
            )

        # Nếu phương thức cũ là PAYOS và đang đổi sang phương thức khác -> Yêu cầu hủy link payOS đang mở
        if order.payment_method == "PAYOS" and method != "PAYOS":
            try:
                PayOSPaymentService.cancel_payment_link(
                    db=db,
                    order=order,
                    cancellation_reason=f"Khách hàng đổi sang phương thức {method}",
                )
            except Exception as e:
                logger.warning(f"Lỗi khi hủy link payOS cũ: {e}")

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

        # Vô hiệu hóa mã SePay cũ nếu đang đổi phương thức
        if order.payment_method == "SEPAY" and method != "SEPAY":
            from app.models.inventory import SepayPaymentCode
            old_code = db.scalar(select(SepayPaymentCode).where(SepayPaymentCode.order_id == order.id))
            if old_code:
                old_code.status = "CANCELLED"

        db.commit()

                # Tạo Payment Intent mới (hỗ trợ cả COD, SEPAY, PAYOS)
        return cls.create_intent(
            db=db,
            order_code=clean_code,
            payment_method=method,
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
        if method in ["BANK_TRANSFER", "VIETQR", "MOMO"]:
            raise HTTPException(
                status_code=400,
                detail=f"Phương thức thanh toán '{payment_method}' đã ngừng hỗ trợ cho phụ phí đổi hàng mới. Vui lòng chọn COD.",
            )
        elif method == "COD":
            provider = "COD"
        else:
            raise HTTPException(status_code=400, detail=f"Phương thức '{payment_method}' không hỗ trợ. Vui lòng chọn COD.")

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
        if clean_code.startswith("EXC-"):
            from app.models.returns import ExchangeOrder, ExchangeStatus
            exchange = db.scalar(select(ExchangeOrder).where(ExchangeOrder.exchange_code == clean_code))
            if not exchange:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn đổi hàng '{clean_code}'.")
            is_paid = exchange.status != ExchangeStatus.WAITING_PAYMENT.value
            return {
                "order_code": exchange.exchange_code,
                "payment_status": "PAID" if is_paid else "PENDING",
                "payment_method": "VIETQR",
                "order_status": exchange.status,
                "total_amount": float(exchange.price_difference),
                "customer_name": "Khách hàng đổi hàng",
                "can_retry": not is_paid,
                "latest_transaction": None,
                "transactions": [],
            }

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

        import urllib.parse
        from app.models.inventory import SepayPaymentCode

        sepay_code = None
        sepay_details = None
        if order.payment_method == "SEPAY":
            sepay_code = db.scalar(select(SepayPaymentCode.payment_code).where(SepayPaymentCode.order_id == order.id))
            if sepay_code:
                acc_num = (getattr(settings, "sepay_account_number", "") or "68207111222333").strip()
                acc_holder = (getattr(settings, "sepay_account_holder", "") or "LAI HOANG PHI HUNG").strip()
                amt = int(order.total_amount)
                qr_url = f"https://img.vietqr.io/image/MB-{acc_num}-compact2.png?amount={amt}&addInfo={sepay_code}&accountName={urllib.parse.quote(acc_holder)}"
                sepay_details = {
                    "payment_code": sepay_code,
                    "bank_name": "Ngân hàng TMCP Quân Đội (MBBank)",
                    "account_number": acc_num,
                    "account_holder": acc_holder,
                    "qr_code_url": qr_url,
                    "amount": amt,
                }

        serialized_items = []
        if getattr(order, "items", None):
            for item in order.items:
                img_url = None
                if getattr(item, "product", None) and hasattr(item.product, "image_url"):
                    img_url = item.product.image_url
                serialized_items.append({
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "price": float(item.price or 0),
                    "quantity": int(item.quantity or 1),
                    "subtotal": float(item.subtotal or 0),
                    "image_url": img_url,
                })

        # Kiểm tra tự động hết hạn intent (15 phút)
        is_intent_expired = False
        latest_expires_at = None
        if latest_trans:
            latest_expires_at = getattr(latest_trans, "expires_at", None)
            if latest_expires_at:
                exp_utc = latest_expires_at.replace(tzinfo=latest_expires_at.tzinfo or UTC)
                if exp_utc <= utcnow():
                    is_intent_expired = True
                    if latest_trans.status == "PENDING" and latest_trans.provider in ("SEPAY", "PAYOS"):
                        latest_trans.status = "EXPIRED"
                        latest_trans.updated_at = utcnow()
                        db.commit()

        if sepay_details:
            sepay_details["expires_at"] = latest_expires_at.isoformat() if latest_expires_at else None
            sepay_details["is_expired"] = is_intent_expired

        return {
            "order_code": order.order_code,
            "payment_code": sepay_code,
            "payment_status": order.payment_status,
            "payment_method": order.payment_method,
            "order_status": order.order_status,
            "fulfillment_status": getattr(order, "fulfillment_status", None),
            "total_amount": float(order.total_amount),
            "customer_name": order.customer_name,
            "customer_phone": getattr(order, "customer_phone", None),
            "shipping_address": getattr(order, "shipping_address", None),
            "shipping_fee": float(getattr(order, "shipping_fee", 0) or 0),
            "discount_amount": float(getattr(order, "discount_amount", 0) or 0),
            "items": serialized_items,
            "sepay_details": sepay_details,
            "expires_at": latest_expires_at.isoformat() if latest_expires_at else None,
            "is_expired": is_intent_expired,
            "server_time": utcnow().isoformat(),
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
