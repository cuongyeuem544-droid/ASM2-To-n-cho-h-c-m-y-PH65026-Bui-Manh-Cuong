import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    ExchangeOrder,
    Order,
    PaymentTransaction,
    PaymentWebhookEvent,
)
from app.models.returns import ExchangeStatus
from app.services.alert_notifier import dispatch_alert

logger = logging.getLogger("pharmatrust.vietqr")


def utcnow() -> datetime:
    return datetime.now(UTC)


class VietQrService:
    """
    Dịch vụ Thanh toán Chuyển khoản Tự động VietQR (Napas 247 Chuẩn Quốc Gia):
    - Tạo mã QR động với số tiền và nội dung chuyển khoản mã hóa chính xác.
    - Tiếp nhận Webhook thông báo nhận tiền tự động (Auto-reconcile Bank Webhook).
    - Hỗ trợ thanh toán đơn hàng Storefront và thanh toán bổ sung cho đơn đổi hàng (ExchangeOrder).
    - Hỗ trợ Sandbox simulator chạy thử nghiệm tức thì.
    """

    BANK_BIN_MAPPING = {
        "MB": {"bin": "970422", "name": "Ngân hàng TMCP Quân Đội (MBBank)"},
        "VCB": {"bin": "970436", "name": "Ngân hàng TMCP Ngoại Thương (Vietcombank)"},
        "TCB": {"bin": "970407", "name": "Ngân hàng TMCP Kỹ Thương (Techcombank)"},
        "BIDV": {"bin": "970418", "name": "Ngân hàng TMCP Đầu tư và Phát triển (BIDV)"},
        "VPB": {"bin": "970432", "name": "Ngân hàng TMCP Việt Nam Thịnh Vượng (VPBank)"},
        "ACB": {"bin": "970416", "name": "Ngân hàng TMCP Á Châu (ACB)"},
    }

    @classmethod
    def get_bank_info(cls, bank_id: Optional[str] = None) -> dict[str, str]:
        key = (bank_id or settings.vietqr_bank_id).upper()
        if key in cls.BANK_BIN_MAPPING:
            return cls.BANK_BIN_MAPPING[key]
        return {"bin": "970422", "name": f"Ngân hàng {key}"}

    @classmethod
    def generate_vietqr_url(
        cls,
        amount: int,
        memo: str,
        bank_id: Optional[str] = None,
        account_number: Optional[str] = None,
        account_holder: Optional[str] = None,
    ) -> str:
        b_id = bank_id or settings.vietqr_bank_id
        acc_no = account_number or settings.vietqr_account_number
        holder = account_holder or settings.vietqr_account_holder
        clean_memo = memo.strip().upper()
        return (
            f"https://img.vietqr.io/image/{b_id}-{acc_no}-compact2.png"
            f"?amount={amount}&addInfo={quote(clean_memo)}&accountName={quote(holder)}"
        )

    @classmethod
    def create_payment_request(
        cls,
        db: Session,
        order: Order,
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Khởi tạo yêu cầu thanh toán VietQR cho đơn hàng thuốc.
        """
        if order.payment_status == "PAID":
            raise HTTPException(status_code=400, detail="Đơn hàng này đã được thanh toán thành công trước đó.")

        amount = int(order.total_amount)
        bank_info = cls.get_bank_info()
        transfer_memo = order.order_code
        qr_url = cls.generate_vietqr_url(amount=amount, memo=transfer_memo)

        # Lưu hoặc cập nhật PaymentTransaction
        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "VIETQR",
            )
        )
        metadata = {
            "bank_id": settings.vietqr_bank_id,
            "bank_name": bank_info["name"],
            "account_number": settings.vietqr_account_number,
            "account_holder": settings.vietqr_account_holder,
            "transfer_memo": transfer_memo,
            "qr_url": qr_url,
        }

        if not trans:
            trans = PaymentTransaction(
                order_id=order.id,
                transaction_code=f"TXN-VQR-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="VIETQR",
                amount=Decimal(str(amount)),
                currency="VND",
                status="PENDING",
                provider_pay_url=qr_url,
                provider_response_raw=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(trans)
        else:
            trans.amount = Decimal(str(amount))
            trans.provider_pay_url = qr_url
            trans.provider_response_raw = json.dumps(metadata, ensure_ascii=False)
            trans.status = "PENDING"

        order.payment_method = "BANK_TRANSFER"
        db.commit()
        db.refresh(trans)

        return {
            "status": "SUCCESS",
            "message": "Khởi tạo mã VietQR Napas 247 thành công.",
            "order_code": order.order_code,
            "transaction_code": trans.transaction_code,
            "amount": amount,
            "currency": "VND",
            "provider": "VIETQR",
            "qr_code_url": qr_url,
            "bank_name": bank_info["name"],
            "bank_id": settings.vietqr_bank_id,
            "account_number": settings.vietqr_account_number,
            "account_holder": settings.vietqr_account_holder,
            "transfer_memo": transfer_memo,
        }

    @classmethod
    def create_exchange_payment_request(
        cls,
        db: Session,
        exchange: ExchangeOrder,
    ) -> dict[str, Any]:
        """
        Khởi tạo VietQR thanh toán phần chênh lệch phát sinh khi đổi hàng thuốc.
        """
        if exchange.status != ExchangeStatus.WAITING_PAYMENT.value:
            raise HTTPException(
                status_code=400,
                detail=f"Đơn đổi hàng '{exchange.exchange_code}' hiện không ở trạng thái chờ thanh toán chênh lệch (Trạng thái hiện tại: {exchange.status}).",
            )

        amount = int(exchange.price_difference)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Đơn đổi hàng này không yêu cầu thanh toán phụ phí.")

        bank_info = cls.get_bank_info()
        transfer_memo = exchange.exchange_code
        qr_url = cls.generate_vietqr_url(amount=amount, memo=transfer_memo)

        # Lưu hoặc cập nhật PaymentTransaction cho exchange
        metadata = {
            "exchange_code": exchange.exchange_code,
            "bank_id": settings.vietqr_bank_id,
            "bank_name": bank_info["name"],
            "account_number": settings.vietqr_account_number,
            "account_holder": settings.vietqr_account_holder,
            "transfer_memo": transfer_memo,
            "qr_url": qr_url,
        }

        trans = PaymentTransaction(
            order_id=exchange.original_order_id,
            transaction_code=f"TXN-EXC-VQR-{exchange.exchange_code}-{int(datetime.now().timestamp()) % 100000}",
            provider="VIETQR",
            amount=Decimal(str(amount)),
            currency="VND",
            status="PENDING",
            provider_pay_url=qr_url,
            provider_response_raw=json.dumps(metadata, ensure_ascii=False),
        )
        db.add(trans)
        db.flush()

        exchange.additional_payment_transaction_id = trans.id
        exchange.additional_payment_required = Decimal(str(amount))
        db.commit()
        db.refresh(trans)

        return {
            "status": "SUCCESS",
            "message": "Khởi tạo mã VietQR phụ phí đổi hàng thành công.",
            "exchange_code": exchange.exchange_code,
            "transaction_code": trans.transaction_code,
            "amount": amount,
            "currency": "VND",
            "provider": "VIETQR",
            "qr_code_url": qr_url,
            "bank_name": bank_info["name"],
            "bank_id": settings.vietqr_bank_id,
            "account_number": settings.vietqr_account_number,
            "account_holder": settings.vietqr_account_holder,
            "transfer_memo": transfer_memo,
        }

    @classmethod
    def verify_webhook_token(cls, token: Optional[str]) -> bool:
        if not token:
            return False
        expected = settings.vietqr_webhook_secret
        return token.strip() == expected.strip()

    @classmethod
    def process_webhook(
        cls,
        db: Session,
        payload: dict[str, Any],
        auth_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Xử lý Webhook biến động số dư ngân hàng (SePay / Napas / Cashtrack):
        1. Xác thực auth_token.
        2. Ghi nhật ký vào PaymentWebhookEvent.
        3. Phân tích nội dung chuyển khoản để tìm Order code hoặc Exchange code.
        4. Xác thực số tiền nhận được >= số tiền yêu cầu.
        5. Đảm bảo Idempotency (không xử lý trùng lặp).
        6. Cập nhật Order / ExchangeOrder và PaymentTransaction.
        """
        if not cls.verify_webhook_token(auth_token):
            raise HTTPException(status_code=401, detail="Xác thực Webhook không thành công (Invalid Authorization Token)")

        raw_text = json.dumps(payload, ensure_ascii=False)
        trans_id = str(payload.get("transaction_id") or payload.get("id") or payload.get("referenceCode") or f"VQR-{int(datetime.now().timestamp())}")
        memo = str(payload.get("content") or payload.get("description") or payload.get("transfer_content") or "").strip().upper()
        received_amount = int(payload.get("amount") or payload.get("transfer_amount") or 0)

        webhook_log = PaymentWebhookEvent(
            provider="VIETQR",
            event_id=trans_id,
            signature=auth_token,
            payload_raw=raw_text,
            processed=False,
        )
        db.add(webhook_log)
        db.flush()

        # 1. Thử khớp với Đơn hàng đổi (ExchangeOrder)
        if "EXC-" in memo:
            parts = [w for w in memo.replace(":", " ").replace("-", " ").split() if w.startswith("EXC") or "EXC" in w]
            target_code = None
            for p in memo.split():
                if "EXC-" in p:
                    target_code = p.strip()
                    break

            exchange = db.scalar(select(ExchangeOrder).where(ExchangeOrder.exchange_code == target_code)) if target_code else None
            if exchange:
                if exchange.status != ExchangeStatus.WAITING_PAYMENT.value:
                    webhook_log.processed = True
                    db.commit()
                    return {"resultCode": 0, "message": "Đơn đổi hàng đã được xử lý trước đó (Idempotent Hit)."}

                required_diff = int(exchange.price_difference)
                if received_amount < required_diff:
                    err_msg = f"Số tiền chuyển khoản {received_amount:,} đ không đủ cho phụ phí {required_diff:,} đ"
                    webhook_log.process_error = err_msg
                    db.commit()
                    raise HTTPException(status_code=400, detail=err_msg)

                # Chuyển trạng thái đơn đổi hàng
                exchange.status = ExchangeStatus.ALLOCATING_STOCK.value
                if exchange.additional_payment_transaction_id:
                    trans = db.get(PaymentTransaction, exchange.additional_payment_transaction_id)
                    if trans:
                        trans.status = "SUCCESS"
                        trans.provider_trans_id = trans_id

                webhook_log.processed = True
                db.commit()

                dispatch_alert(
                    title="THANH TOÁN PHỤ PHÍ ĐỔI HÀNG THÀNH CÔNG",
                    message=(
                        f"Mã đổi hàng: <b>{exchange.exchange_code}</b>\n"
                        f"Số tiền đã nhận: <b>{received_amount:,} đ</b>\n"
                        f"Nội dung: <code>{memo}</code>\n"
                        f"Trạng thái: <b>Đã phân bổ kho thay thế (ALLOCATING_STOCK)</b>"
                    ),
                    severity="INFO",
                    alert_type="EXCHANGE_PAID",
                )
                return {
                    "resultCode": 0,
                    "message": "Xác nhận phụ phí đổi hàng thành công.",
                    "exchange_code": exchange.exchange_code,
                    "status": exchange.status,
                }

        # 2. Khớp với Đơn hàng mua thuốc (Order)
        matched_order_code = None
        for token in memo.replace(":", " ").replace("/", " ").replace("_", " ").split():
            if token.startswith("PT-"):
                matched_order_code = token
                break

        if not matched_order_code:
            # Tra cứu chính xác nếu memo chứa PT-
            order = db.scalar(select(Order).where(Order.order_code == memo))
            if order:
                matched_order_code = order.order_code

        if not matched_order_code:
            err_msg = f"Không tìm thấy mã đơn hàng hợp lệ trong nội dung chuyển khoản: '{memo}'"
            webhook_log.process_error = err_msg
            db.commit()
            raise HTTPException(status_code=404, detail=err_msg)

        order = db.scalar(select(Order).where(Order.order_code == matched_order_code))
        if not order:
            err_msg = f"Đơn hàng '{matched_order_code}' không tồn tại trong hệ thống."
            webhook_log.process_error = err_msg
            db.commit()
            raise HTTPException(status_code=404, detail=err_msg)

        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "VIETQR",
            )
        )
        if not trans:
            trans = PaymentTransaction(
                order_id=order.id,
                transaction_code=f"TXN-VQR-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="VIETQR",
                amount=Decimal(str(received_amount or order.total_amount)),
                currency="VND",
                status="PENDING",
            )
            db.add(trans)
            db.flush()

        # Idempotency
        if trans.status == "SUCCESS" and order.payment_status == "PAID":
            webhook_log.processed = True
            db.commit()
            return {"resultCode": 0, "message": "Giao dịch đã được ghi nhận thành công từ trước (Idempotent Hit)."}

        # Kiểm tra số tiền chuyển khoản
        order_total = int(order.total_amount)
        if received_amount > 0 and received_amount < order_total:
            trans.status = "UNDERPAID"
            err_msg = f"Số tiền chuyển khoản ({received_amount:,} đ) ít hơn tổng đơn hàng ({order_total:,} đ)"
            webhook_log.process_error = err_msg
            db.commit()
            raise HTTPException(status_code=400, detail=err_msg)

        # Thanh toán thành công
        trans.status = "SUCCESS"
        trans.provider_trans_id = trans_id
        trans.amount = Decimal(str(received_amount or order_total))
        order.payment_status = "PAID"
        order.payment_method = "BANK_TRANSFER"
        if order.order_status == "PENDING":
            order.order_status = "CONFIRMED"

        webhook_log.processed = True
        db.commit()

        dispatch_alert(
            title="THANH TOÁN VIETQR CHUYỂN KHOẢN THÀNH CÔNG",
            message=(
                f"Đơn hàng: <b>{order.order_code}</b>\n"
                f"Khách hàng: <b>{order.customer_name}</b>\n"
                f"Số tiền nhận: <b>{int(trans.amount):,} đ</b>\n"
                f"Nội dung UNC: <code>{memo}</code>\n"
                f"Trạng thái đơn: <b>Đã xác nhận & Sẵn sàng đóng gói</b>"
            ),
            severity="INFO",
            alert_type="PAYMENT_RECEIVED",
            details={
                "Mã đơn": order.order_code,
                "Cổng": "VietQR Napas 247",
                "Số tiền": f"{int(trans.amount):,} VND",
                "TransId": trans_id,
            },
        )

        return {
            "resultCode": 0,
            "message": "Xử lý thanh toán VietQR thành công.",
            "order_code": order.order_code,
            "payment_status": order.payment_status,
            "transaction_code": trans.transaction_code,
        }

    @classmethod
    def simulate_payment(
        cls,
        db: Session,
        code: str,
        success: bool = True,
        amount: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Mô phỏng khách hàng quét mã chuyển khoản thành công trên môi trường DEV/DEMO.
        """
        clean_code = code.strip().upper()
        if not success:
            return {"resultCode": -1, "message": "Mô phỏng thanh toán bị hủy bỏ."}

        # Kiểm tra order hoặc exchange
        if "EXC-" in clean_code:
            exchange = db.scalar(select(ExchangeOrder).where(ExchangeOrder.exchange_code == clean_code))
            if not exchange:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn đổi {clean_code}")
            sim_amount = amount or int(exchange.price_difference)
        else:
            order = db.scalar(select(Order).where(Order.order_code == clean_code))
            if not order:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng {clean_code}")
            sim_amount = amount or int(order.total_amount)

        sim_payload = {
            "transaction_id": f"SIM-VQR-{int(datetime.now().timestamp() * 1000) % 10000000}",
            "amount": sim_amount,
            "content": clean_code,
            "description": f"Chuyen khoan thanh toan {clean_code}",
            "bank_code": settings.vietqr_bank_id,
        }

        return cls.process_webhook(
            db=db,
            payload=sim_payload,
            auth_token=settings.vietqr_webhook_secret,
        )
