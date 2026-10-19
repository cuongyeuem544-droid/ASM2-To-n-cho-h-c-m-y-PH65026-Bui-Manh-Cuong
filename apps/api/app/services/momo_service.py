import hashlib
import hmac
import json
import logging
from datetime import datetime, UTC
from decimal import Decimal
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Order,
    PaymentTransaction,
    PaymentWebhookEvent,
)
from app.services.alert_notifier import dispatch_alert

logger = logging.getLogger("pharmatrust.momo")


def utcnow() -> datetime:
    return datetime.now(UTC)


class MomoPaymentService:
    """
    Dịch vụ Tích hợp Cổng thanh toán MoMo Sandbox và xử lý IPN Webhook bảo mật.
    """

    @classmethod
    def generate_signature(cls, raw_data: str, secret_key: str) -> str:
        """
        Sinh chữ ký số bảo mật HMAC-SHA256 theo chuẩn MoMo API.
        """
        return hmac.new(
            secret_key.encode("utf-8"),
            raw_data.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    def create_payment_request(
        cls,
        db: Session,
        order: Order,
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Khởi tạo giao dịch thanh toán MoMo QR / PayUrl cho đơn hàng.
        """
        partner_code = settings.momo_partner_code
        access_key = settings.momo_access_key
        secret_key = settings.momo_secret_key
        endpoint = settings.momo_endpoint

        order_id = order.order_code
        amount = int(order.total_amount)
        request_id = f"MOMO-{order.order_code}-{int(datetime.now().timestamp() * 1000) % 1000000}"
        order_info = f"Thanh toan don thuoc {order.order_code} tai Nha thuoc PharmaTrust"
        redirect_url = return_url or settings.momo_return_url
        ipn_url = settings.momo_ipn_url
        request_type = "captureWallet"
        extra_data = ""
        lang = "vi"

        # Chuỗi dữ liệu raw để sinh chữ ký theo chuẩn MoMo V2
        raw_signature = (
            f"accessKey={access_key}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"ipnUrl={ipn_url}&"
            f"orderId={order_id}&"
            f"orderInfo={order_info}&"
            f"partnerCode={partner_code}&"
            f"redirectUrl={redirect_url}&"
            f"requestId={request_id}&"
            f"requestType={request_type}"
        )
        signature = cls.generate_signature(raw_signature, secret_key)

        request_payload = {
            "partnerCode": partner_code,
            "partnerName": "Nhà thuốc PharmaTrust",
            "storeId": "PharmaTrustStore",
            "requestId": request_id,
            "amount": amount,
            "orderId": order_id,
            "orderInfo": order_info,
            "redirectUrl": redirect_url,
            "ipnUrl": ipn_url,
            "lang": lang,
            "extraData": extra_data,
            "requestType": request_type,
            "signature": signature,
        }

        pay_url: Optional[str] = None
        qr_code_url: Optional[str] = None
        deeplink: Optional[str] = None
        momo_response_raw: str = ""

        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.post(endpoint, json=request_payload)
                momo_response_raw = res.text
                if res.status_code == 200:
                    res_data = res.json()
                    if res_data.get("resultCode") == 0:
                        pay_url = res_data.get("payUrl")
                        qr_code_url = res_data.get("qrCodeUrl")
                        deeplink = res_data.get("deeplink")
                    else:
                        logger.warning(
                            f"[MOMO] Gateway returned non-zero code {res_data.get('resultCode')}: {res_data.get('message')}"
                        )
        except Exception as e:
            logger.warning(f"[MOMO] Không thể kết nối tới server MoMo Sandbox: {e}")
            momo_response_raw = f"NETWORK_ERROR: {str(e)}"

        # Nếu không lấy được pay_url từ MoMo: Tuyệt đối KHÔNG tự sinh đường dẫn SimulatedSuccess giả lập
        if not pay_url:
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order.id,
                    PaymentTransaction.provider == "MOMO",
                )
            )
            if not trans:
                trans = PaymentTransaction(
                    order_id=order.id,
                    transaction_code=f"TXN-MOMO-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                    provider="MOMO",
                    amount=Decimal(str(amount)),
                    currency="VND",
                    status="FAILED",
                    provider_pay_url=None,
                    provider_response_raw=momo_response_raw or "GATEWAY_UNAVAILABLE",
                )
                db.add(trans)
            else:
                trans.status = "FAILED"
                trans.provider_pay_url = None
                trans.provider_response_raw = momo_response_raw or "GATEWAY_UNAVAILABLE"
            db.commit()

            raise HTTPException(
                status_code=502,
                detail="Cổng thanh toán MoMo tạm thời không phản hồi hoặc đang bảo trì. Giao dịch chưa được khởi tạo, vui lòng thử lại sau hoặc chọn thanh toán VietQR / COD.",
            )

        # Ghi nhận / Cập nhật PaymentTransaction trong CSDL
        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "MOMO",
            )
        )
        if not trans:
            trans = PaymentTransaction(
                order_id=order.id,
                transaction_code=f"TXN-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="MOMO",
                amount=Decimal(str(amount)),
                currency="VND",
                status="PENDING",
                provider_pay_url=pay_url,
                provider_response_raw=momo_response_raw,
            )
            db.add(trans)
        else:
            trans.amount = Decimal(str(amount))
            trans.provider_pay_url = pay_url
            trans.provider_response_raw = momo_response_raw
            trans.status = "PENDING"

        # Cập nhật phương thức thanh toán của đơn hàng
        order.payment_method = "MOMO"
        order.payment_status = "PENDING"
        order.fulfillment_status = "WAITING_PAYMENT"
        db.commit()
        db.refresh(trans)
        db.refresh(order)

        return {
            "status": "SUCCESS",
            "message": "Tạo yêu cầu thanh toán MoMo thành công.",
            "order_code": order.order_code,
            "transaction_code": trans.transaction_code,
            "amount": amount,
            "pay_url": pay_url,
            "qr_code_url": qr_code_url,
            "deeplink": deeplink,
            "request_id": request_id,
        }

    @classmethod
    def verify_ipn_signature(cls, payload: dict[str, Any]) -> bool:
        """
        Xác thực tính toàn vẹn và nguồn gốc của Webhook IPN từ MoMo.
        """
        received_signature = payload.get("signature")
        if not received_signature:
            return False

        access_key = settings.momo_access_key
        secret_key = settings.momo_secret_key

        # Công thức ghép chuỗi IPN của MoMo V2
        partner_code = str(payload.get("partnerCode", ""))
        order_id = str(payload.get("orderId", ""))
        request_id = str(payload.get("requestId", ""))
        amount = str(payload.get("amount", ""))
        order_info = str(payload.get("orderInfo", ""))
        order_type = str(payload.get("orderType", ""))
        trans_id = str(payload.get("transId", ""))
        result_code = str(payload.get("resultCode", ""))
        message = str(payload.get("message", ""))
        pay_type = str(payload.get("payType", ""))
        response_time = str(payload.get("responseTime", ""))
        extra_data = str(payload.get("extraData", ""))

        raw_signature = (
            f"accessKey={access_key}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"message={message}&"
            f"orderId={order_id}&"
            f"orderInfo={order_info}&"
            f"orderType={order_type}&"
            f"partnerCode={partner_code}&"
            f"payType={pay_type}&"
            f"requestId={request_id}&"
            f"responseTime={response_time}&"
            f"resultCode={result_code}&"
            f"transId={trans_id}"
        )

        expected_signature = cls.generate_signature(raw_signature, secret_key)
        return hmac.compare_digest(expected_signature, received_signature)

    @classmethod
    def process_ipn_callback(cls, db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Xử lý thông điệp IPN từ MoMo:
        - Kiểm tra chữ ký bảo mật HMAC-SHA256
        - Bảo vệ chống xử lý lặp lại (Idempotency)
        - Cập nhật trạng thái PaymentTransaction và Order
        - Gửi cảnh báo thông báo thanh toán
        """
        # 1. Xác thực chữ ký
        if not cls.verify_ipn_signature(payload):
            logger.error(f"[MOMO IPN] Chữ ký không hợp lệ từ payload: {payload}")
            raise HTTPException(status_code=400, detail="Chữ ký xác thực MoMo không hợp lệ (Invalid HMAC Signature)")

        order_code = payload.get("orderId")
        result_code = int(payload.get("resultCode", -1))
        trans_id = str(payload.get("transId", ""))
        amount = payload.get("amount")

        # 2. Ghi nhận sự kiện webhook
        webhook_log = PaymentWebhookEvent(
            provider="MOMO",
            event_id=trans_id or f"EVT-{int(datetime.now().timestamp())}",
            signature=payload.get("signature"),
            payload_raw=json.dumps(payload, ensure_ascii=False),
            processed=False,
        )
        db.add(webhook_log)
        db.flush()

        # 3. Tìm đơn hàng
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        if not order:
            err_msg = f"Không tìm thấy đơn hàng {order_code} trong hệ thống"
            webhook_log.process_error = err_msg
            db.commit()
            raise HTTPException(status_code=404, detail=err_msg)

        # 4. Tìm giao dịch thanh toán
        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "MOMO",
            )
        )
        if not trans:
            trans = PaymentTransaction(
                order_id=order.id,
                transaction_code=f"TXN-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="MOMO",
                amount=Decimal(str(amount or order.total_amount)),
                currency="VND",
                status="PENDING",
            )
            db.add(trans)
            db.flush()

        # 5. Kiểm tra Idempotency (Tránh xử lý 2 lần nếu MoMo retry IPN)
        if trans.status == "SUCCESS":
            webhook_log.processed = True
            db.commit()
            logger.info(f"[MOMO IPN] Giao dịch {order_code} đã được xử lý trước đó (Idempotent Hit).")
            return {"resultCode": 0, "message": "Giao dịch đã được ghi nhận thành công từ trước."}

        # 6. Cập nhật trạng thái theo mã kết quả của MoMo (0 = Thành công)
        if result_code == 0:
            # Kiểm tra số tiền: Sai một đồng cũng không tự chuyển đơn sang PAID
            order_total = int(order.total_amount)
            paid_amount = int(amount) if amount is not None else None
            if paid_amount is not None and paid_amount != order_total:
                trans.status = "UNDERPAID" if paid_amount < order_total else "OVERPAID"
                err_msg = f"Số tiền thanh toán MoMo ({paid_amount:,} đ) không khớp với số tiền đơn hàng ({order_total:,} đ)"
                webhook_log.process_error = err_msg
                db.commit()
                raise HTTPException(status_code=400, detail=err_msg)

            trans.status = "SUCCESS"
            trans.provider_trans_id = trans_id
            order.payment_status = "PAID"
            if order.order_status in ["PENDING", "DRAFT"]:
                order.order_status = "CONFIRMED"

            # ĐƠN CHÍNH THỨC XUẤT HIỆN TRONG DANH SÁCH XỬ LÝ CỦA KHO & ADMIN
            order.fulfillment_status = "ALLOCATED"

            # Phát thông báo tới Kho phụ trách
            if order.assigned_warehouse_id:
                try:
                    from app.services.warehouse_notification_service import WarehouseNotificationService
                    WarehouseNotificationService.notify_order_new(db, order, order.assigned_warehouse_id)
                except Exception as n_err:
                    logger.warning(f"Không thể gửi thông báo kho cho đơn {order.order_code}: {n_err}")

            webhook_log.processed = True

            # Ghi Audit Log
            try:
                from app.services.audit import write_audit
                write_audit(
                    db,
                    action="MOMO_IPN_PAYMENT_SUCCESS",
                    entity_type="Order",
                    entity_id=order.id,
                    user=None,
                    request=None,
                    before={"payment_status": "PENDING", "fulfillment_status": "WAITING_PAYMENT"},
                    after={
                        "payment_status": "PAID",
                        "fulfillment_status": "ALLOCATED",
                        "trans_id": trans_id,
                        "amount": paid_amount,
                    },
                )
            except Exception as a_err:
                logger.warning(f"Failed to write audit log for MoMo: {a_err}")

            # Gửi thông báo tức thì tới Telegram Quản trị viên
            dispatch_alert(
                title="THANH TOÁN MOMO THÀNH CÔNG",
                message=(
                    f"Đơn hàng: <b>{order.order_code}</b>\n"
                    f"Khách hàng: <b>{order.customer_name}</b>\n"
                    f"Số tiền đã thanh toán: <b>{int(order.total_amount):,} đ</b>\n"
                    f"Mã giao dịch MoMo: <code>{trans_id}</code>\n"
                    f"Trạng thái đơn: <b>Đã xác nhận & Sẵn sàng đóng gói</b>"
                ),
                severity="INFO",
                alert_type="PAYMENT_RECEIVED",
                details={
                    "Mã đơn": order.order_code,
                    "Cổng": "MoMo Sandbox",
                    "Số tiền": f"{int(order.total_amount):,} VND",
                    "TransId": trans_id,
                },
            )
        else:
            trans.status = "FAILED"
            order.payment_status = "FAILED"
            webhook_log.process_error = f"MoMo resultCode {result_code}: {payload.get('message')}"

        db.commit()
        return {
            "resultCode": 0,
            "message": "Xử lý IPN MoMo thành công.",
            "order_code": order.order_code,
            "payment_status": order.payment_status,
        }

    @classmethod
    def simulate_payment(cls, db: Session, order_code: str, success: bool = True) -> dict[str, Any]:
        """
        Hàm mô phỏng thanh toán thành công (dành cho demo và chạy test local).
        """
        order = db.scalar(select(Order).where(Order.order_code == order_code))
        if not order:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn {order_code}")

        access_key = settings.momo_access_key
        secret_key = settings.momo_secret_key
        partner_code = settings.momo_partner_code
        request_id = f"MOMO-{order.order_code}-{int(datetime.now().timestamp() * 1000) % 1000000}"
        trans_id = f"SIM-{int(datetime.now().timestamp() * 1000) % 10000000}"
        amount = str(int(order.total_amount))
        result_code = "0" if success else "1006"
        message = "Giao dịch thành công qua MoMo Sandbox" if success else "Giao dịch bị từ chối bởi người dùng"
        order_info = f"Thanh toan don thuoc {order.order_code}"
        order_type = "momo_wallet"
        pay_type = "qr"
        response_time = str(int(datetime.now().timestamp() * 1000))
        extra_data = ""

        raw_signature = (
            f"accessKey={access_key}&"
            f"amount={amount}&"
            f"extraData={extra_data}&"
            f"message={message}&"
            f"orderId={order_code}&"
            f"orderInfo={order_info}&"
            f"orderType={order_type}&"
            f"partnerCode={partner_code}&"
            f"payType={pay_type}&"
            f"requestId={request_id}&"
            f"responseTime={response_time}&"
            f"resultCode={result_code}&"
            f"transId={trans_id}"
        )
        signature = cls.generate_signature(raw_signature, secret_key)

        sim_payload = {
            "partnerCode": partner_code,
            "orderId": order_code,
            "requestId": request_id,
            "amount": int(amount),
            "orderInfo": order_info,
            "orderType": order_type,
            "transId": trans_id,
            "resultCode": int(result_code),
            "message": message,
            "payType": pay_type,
            "responseTime": int(response_time),
            "extraData": extra_data,
            "signature": signature,
        }

        return cls.process_ipn_callback(db, sim_payload)
