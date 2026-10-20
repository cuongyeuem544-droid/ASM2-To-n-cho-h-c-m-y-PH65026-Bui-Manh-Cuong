import json
import logging
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from payos import PayOS
from payos.types.v2.payment_requests import CreatePaymentLinkRequest, ItemData
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Order, PaymentTransaction, PaymentWebhookEvent, PayosOrderCode
from app.services.alert_notifier import dispatch_alert
from app.services.audit import write_audit

logger = logging.getLogger("pharmatrust.payos")

_order_code_lock = threading.Lock()
_counter = 0


def utcnow() -> datetime:
    return datetime.now(UTC)


class PayOSPaymentService:
    """
    Dịch vụ Tích hợp Cổng thanh toán payOS (QR Chuyển khoản / Napas 247 / Thẻ):
    - Đọc cấu hình bảo mật từ biến môi trường (PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY).
    - Tạo link thanh toán payOS kèm mã QR động và hạn giao dịch.
    - Xử lý Webhook thanh toán thật, xác thực chữ ký HMAC SHA256 / Checksum chống giả mạo.
    - Đơn hàng trực tuyến CHỈ xuất hiện trong danh sách xử lý của Kho và Admin khi thanh toán thành công (PAID).
    - Đối soát trực tiếp và đồng bộ trạng thái đơn hàng.
    """

    _client: Optional[PayOS] = None

    @classmethod
    def get_client(cls) -> PayOS:
        """Khởi tạo PayOS client từ cấu hình môi trường bảo mật."""
        if not settings.is_payos_configured:
            raise HTTPException(
                status_code=503,
                detail="Cổng thanh toán payOS chưa được cấu hình đầy đủ keys trên máy chủ.",
            )
        return PayOS(
            client_id=settings.payos_client_id.strip(),
            api_key=settings.payos_api_key.strip(),
            checksum_key=settings.payos_checksum_key.strip(),
        )

    @classmethod
    def generate_unique_order_code(cls, db: Session, order_id: int) -> int:
        """
        Sinh mã số đơn hàng payos_order_code dạng số nguyên duy nhất (BUG-04):
        - Giới hạn JS Safe Integer (< 9,007,199,254,740,991, 15 chữ số).
        - Kết hợp Unix timestamp mili-giây (13 chữ số) + Counter nguyên tử (2 chữ số).
        - Ràng buộc UNIQUE được bảo đảm 100% bằng Database Constraint (bảng payos_order_codes).
        - Hỗ trợ retry loop tự động khi có xung đột nhiều request song song.
        """
        global _counter
        max_retries = 10
        for _ in range(max_retries):
            with _order_code_lock:
                _counter = (_counter + 1) % 100
                cnt = _counter

            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            candidate_code = now_ms * 100 + cnt

            try:
                record = PayosOrderCode(
                    order_id=order_id,
                    order_code_num=candidate_code,
                )
                db.add(record)
                db.flush()
                return candidate_code
            except IntegrityError:
                db.rollback()
                time.sleep(0.002)

        raise HTTPException(
            status_code=500,
            detail="Không thể tạo mã số đơn hàng duy nhất cho cổng payOS. Vui lòng thử lại.",
        )

    @classmethod
    def create_payment_request(
        cls,
        db: Session,
        order: Order,
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Khởi tạo yêu cầu thanh toán qua payOS:
        1. Kiểm tra tính hợp lệ của đơn hàng (chưa hủy, chưa thanh toán).
        2. Sinh mã số đơn hàng dạng số nguyên duy nhất (payos_order_code) có ràng buộc UNIQUE.
        3. Tạo link thanh toán qua payOS SDK.
        4. Ghi nhận PaymentTransaction ở trạng thái PENDING.
        5. Đặt fulfillment_status = WAITING_PAYMENT (kho chưa xử lý khi chưa thanh toán).
        """
        if order.payment_status == "PAID":
            raise HTTPException(
                status_code=400,
                detail="Đơn hàng này đã hoàn tất thanh toán thành công trước đó.",
            )

        if order.order_status == "CANCELLED":
            raise HTTPException(
                status_code=400,
                detail="Đơn hàng này đã bị hủy, không thể tiếp tục thanh toán.",
            )

        client = cls.get_client()

        # BUG-04: Sinh mã số nguyên duy nhất có ràng buộc UNIQUE trong Database
        payos_order_code = cls.generate_unique_order_code(db=db, order_id=order.id)

        amount = int(order.total_amount)
        if amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Số tiền đơn hàng không hợp lệ để tạo thanh toán.",
            )

        # Chuẩn bị danh sách sản phẩm cho payOS
        items = []
        for it in order.items:
            item_name = (it.product_name or "Thuốc").strip()
            if len(item_name) > 40:
                item_name = item_name[:37] + "..."
            items.append(
                ItemData(
                    name=item_name,
                    quantity=it.quantity,
                    price=int(it.price),
                )
            )

        if return_url:
            base_url = return_url.split("?")[0]
            ret_url = return_url
            cancel_url = f"{base_url}?order_code={order.order_code}&status=CANCELLED&cancel=true"
        else:
            ret_url = f"{settings.payos_return_url}?order_code={order.order_code}"
            cancel_url = f"{settings.payos_cancel_url}?order_code={order.order_code}&status=CANCELLED&cancel=true"

        # Mô tả giao dịch cho payOS (tối đa 25 ký tự)
        desc_text = f"DH {order.order_code}".strip()[:25]

        payment_data = CreatePaymentLinkRequest(
            order_code=payos_order_code,
            amount=amount,
            description=desc_text,
            items=items if items else None,
            return_url=ret_url,
            cancel_url=cancel_url,
            buyer_name=order.customer_name[:50] if order.customer_name else None,
            buyer_phone=order.customer_phone[:20] if order.customer_phone else None,
            buyer_address=order.shipping_address[:100] if order.shipping_address else None,
        )

        try:
            res = client.payment_requests.create(payment_data)
        except Exception as e:
            logger.error(f"Lỗi khi gọi payOS API: {e}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"Không thể kết nối tới cổng thanh toán payOS: {str(e)}",
            )

        # Ghi nhận hoặc cập nhật PaymentTransaction
        # Bảo toàn mapping: mỗi payos_order_code có một PaymentTransaction riêng biệt
        # Không ghi đè provider_trans_id của link cũ để khách thanh toán link cũ vẫn đối soát được
        txn_code = f"TXN-PAYOS-{order.order_code}-{payos_order_code}"
        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "PAYOS",
                PaymentTransaction.provider_trans_id == str(payos_order_code),
            )
        )
        metadata = {
            "payos_order_code": payos_order_code,
            "payment_link_id": getattr(res, "payment_link_id", None),
            "account_number": getattr(res, "account_number", None),
            "account_name": getattr(res, "account_name", None),
            "bin": getattr(res, "bin", None),
            "qr_code": getattr(res, "qr_code", None),
        }

        if not trans:
            trans = PaymentTransaction(
                order_id=order.id,
                transaction_code=txn_code,
                provider="PAYOS",
                amount=Decimal(str(amount)),
                currency="VND",
                status="PENDING",
                provider_trans_id=str(payos_order_code),
                provider_pay_url=getattr(res, "checkout_url", None),
                provider_response_raw=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(trans)
        else:
            trans.amount = Decimal(str(amount))
            trans.provider_pay_url = getattr(res, "checkout_url", None)
            trans.provider_response_raw = json.dumps(metadata, ensure_ascii=False)
            trans.updated_at = utcnow()

        order.payment_method = "PAYOS"
        order.payment_status = "PENDING"
        # Đơn trực tuyến chưa thanh toán: Đặt trạng thái WAITING_PAYMENT để kho không xử lý
        order.fulfillment_status = "WAITING_PAYMENT"

        db.commit()
        db.refresh(trans)
        db.refresh(order)

        return {
            "status": "SUCCESS",
            "provider": "PAYOS",
            "order_code": order.order_code,
            "payos_order_code": payos_order_code,
            "transaction_code": trans.transaction_code,
            "amount": amount,
            "checkout_url": getattr(res, "checkout_url", None),
            "qr_code": getattr(res, "qr_code", None),
            "account_number": getattr(res, "account_number", None),
            "account_name": getattr(res, "account_name", None),
            "bin": getattr(res, "bin", None),
            "payment_link_id": getattr(res, "payment_link_id", None),
            "instructions": f"Quét mã VietQR trên ứng dụng ngân hàng hoặc mở cổng payOS để thanh toán {amount:,} đ.",
        }

    @classmethod
    def process_webhook(cls, db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Tiếp nhận và xử lý Webhook biến động thanh toán từ payOS:
        1. Xác thực tính toàn vẹn (checksum / signature) bằng checksum_key qua SDK chính thức.
        2. Tìm PaymentTransaction chính xác bằng provider_trans_id == str(order_code_num) (BUG-03).
        3. Kiểm tra số tiền nhận được bằng đúng tổng tiền đơn hàng (BUG-01).
        4. Kiểm tra đơn đã hủy: KHÔNG tự động kích hoạt lại đơn đã CANCELLED (BUG-02).
        5. Kiểm tra Idempotency chống xử lý lặp lại nhiều lần.
        6. Cập nhật Order sang PAID, OrderStatus sang CONFIRMED, fulfillment_status sang ALLOCATED.
        7. Phát thông báo nội bộ cho kho nhận đơn đúng một lần duy nhất.
        """
        client = cls.get_client()

        # 1. Xác thực chữ ký webhook từ payOS
        try:
            verified_data = client.webhooks.verify(payload)
        except Exception as sig_err:
            logger.warning(f"Chữ ký webhook payOS không hợp lệ: {sig_err}")
            raise HTTPException(
                status_code=400,
                detail=f"Xác thực chữ ký webhook payOS thất bại: {str(sig_err)}",
            )

        if not verified_data:
            raise HTTPException(status_code=400, detail="Dữ liệu webhook trống sau khi giải mã.")

        order_code_num = getattr(verified_data, "order_code", None)
        code = getattr(verified_data, "code", "00")
        amount = getattr(verified_data, "amount", 0)
        desc_text = getattr(verified_data, "description", "") or ""
        ref_code = getattr(verified_data, "reference", "") or ""

        # Ghi nhận webhook event log
        webhook_log = PaymentWebhookEvent(
            provider="PAYOS",
            event_id=str(ref_code or order_code_num or f"EVT-{int(datetime.now().timestamp())}"),
            signature=payload.get("signature"),
            payload_raw=json.dumps(payload, ensure_ascii=False),
            processed=False,
        )
        db.add(webhook_log)
        db.flush()

        logger.info(
            f"[PAYOS WEBHOOK] Nhận webhook payOS #{order_code_num}, "
            f"code={code}, amount={amount}, ref={ref_code}"
        )

        # 2. Xử lý webhook kiểm thử từ payOS dashboard
        if order_code_num in [123, 123456, 0] or "demo" in desc_text.lower():
            logger.info("[PAYOS WEBHOOK] Webhook thử nghiệm kết nối từ dashboard payOS thành công.")
            webhook_log.processed = True
            db.commit()
            return {
                "success": True,
                "message": "Webhook thử nghiệm kết nối payOS đã được xác thực an toàn.",
            }

        # 3. BUG-03: Tìm giao dịch CHÍNH XÁC theo provider_trans_id.
        # Tuyệt đối không dùng regex parse order_code từ description làm bằng chứng xác thực duy nhất.
        trans = None
        if order_code_num:
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.provider == "PAYOS",
                    PaymentTransaction.provider_trans_id == str(order_code_num),
                )
            )

        if not trans:
            # Fallback tra cứu qua bảng payos_order_codes để đảm bảo mapping không bao giờ bị mất
            from app.models.inventory import PayosOrderCode
            poc = db.scalar(
                select(PayosOrderCode).where(PayosOrderCode.order_code_num == order_code_num)
            )
            if poc:
                matched_order = db.get(Order, poc.order_id)
                if matched_order:
                    trans = PaymentTransaction(
                        order_id=matched_order.id,
                        transaction_code=f"TXN-PAYOS-{matched_order.order_code}-{order_code_num}",
                        provider="PAYOS",
                        amount=Decimal(str(matched_order.total_amount)),
                        currency="VND",
                        status="PENDING",
                        provider_trans_id=str(order_code_num),
                    )
                    db.add(trans)
                    db.flush()

        if not trans:
            err_msg = f"Không tìm thấy PaymentTransaction đã khởi tạo cho payOS orderCode={order_code_num}."
            logger.warning(f"[PAYOS WEBHOOK] {err_msg}")
            webhook_log.process_error = err_msg
            db.commit()
            raise HTTPException(status_code=400, detail=err_msg)

        order = db.get(Order, trans.order_id)
        if not order:
            err_msg = f"Không tìm thấy đơn hàng liên kết với giao dịch {trans.transaction_code}."
            webhook_log.process_error = err_msg
            db.commit()
            raise HTTPException(status_code=404, detail=err_msg)

        # 4. Kiểm tra mã phản hồi (code '00' là giao dịch thành công trong payOS)
        if str(code) == "00":
            # BUG-01: Kiểm tra số tiền thanh toán nghiêm ngặt
            # Bắt buộc số tiền payOS nhận được phải khớp chính xác với số tiền Backend đã lưu
            order_total = int(order.total_amount)
            paid_amount = int(amount) if amount is not None else 0

            raw_info = {
                "reference": ref_code,
                "amount": paid_amount,
                "expected_amount": order_total,
                "counter_bank": getattr(verified_data, "counter_account_bank_id", None),
                "counter_acc": getattr(verified_data, "counter_account_number", None),
                "counter_name": getattr(verified_data, "counter_account_name", None),
                "paid_at": getattr(verified_data, "transaction_date_time", None),
            }

            if paid_amount != order_total:
                trans.status = "UNDERPAID" if paid_amount < order_total else "OVERPAID"
                trans.provider_response_raw = json.dumps(raw_info, ensure_ascii=False)
                trans.updated_at = utcnow()
                err_msg = (
                    f"Số tiền thanh toán payOS ({paid_amount:,} đ) "
                    f"{'thiếu' if paid_amount < order_total else 'thừa'} so với tổng đơn ({order_total:,} đ)."
                )
                webhook_log.process_error = err_msg
                write_audit(
                    db,
                    action="PAYOS_AMOUNT_MISMATCH",
                    entity_type="Order",
                    entity_id=order.id,
                    user=None,
                    request=None,
                    before={"payment_status": order.payment_status},
                    after={"status": trans.status, "paid_amount": paid_amount, "expected_amount": order_total},
                )
                dispatch_alert(
                    title=f"CẢNH BÁO: SAI LỆCH SỐ TIỀN PAYOS ({trans.status})",
                    message=f"Đơn: {order.order_code}, Cần thu: {order_total:,} đ, Thực nhận: {paid_amount:,} đ",
                    severity="WARNING",
                    alert_type="PAYMENT_MISMATCH",
                    details={"order_code": order.order_code, "paid_amount": paid_amount, "order_total": order_total},
                )
                db.commit()
                raise HTTPException(status_code=400, detail=err_msg)

            # BUG-02: Kiểm tra trạng thái đơn - Đơn đã hủy/hết hạn tuyệt đối không được kích hoạt lại kho
            if (
                order.order_status == "CANCELLED"
                or order.fulfillment_status == "CANCELLED"
                or order.payment_status in ["EXPIRED", "CANCELLED"]
            ):
                trans.status = "SUCCESS"
                trans.provider_response_raw = json.dumps(raw_info, ensure_ascii=False)
                trans.updated_at = utcnow()
                order.payment_status = "REFUND_PENDING"
                webhook_log.processed = True
                webhook_log.process_error = "Đơn hàng đã hủy hoặc hết hạn trước khi nhận tiền. Chuyển sang hàng đợi đối soát hoàn tiền."
                write_audit(
                    db,
                    action="PAYOS_WEBHOOK_ON_CANCELLED_ORDER",
                    entity_type="Order",
                    entity_id=order.id,
                    user=None,
                    request=None,
                    before={"order_status": order.order_status, "payment_status": order.payment_status},
                    after={"payment_status": "REFUND_PENDING", "paid_amount": paid_amount},
                )
                dispatch_alert(
                    title="THANH TOÁN ĐƠN ĐÃ HỦY/HẾT HẠN - CẦN ĐỐI SOÁT HOÀN TIỀN",
                    message=(
                        f"Đơn hàng <b>{order.order_code}</b> đã bị HỦY HOẶC HẾT HẠN trước đó nhưng nhận được thanh toán payOS thành công.\n"
                        f"Số tiền: <b>{paid_amount:,} đ</b>\n"
                        f"Mã tham chiếu: <code>{ref_code}</code>\n"
                        f"<b>Hệ thống KHÔNG xuất kho đơn này. Vui lòng lập phiếu hoàn tiền cho khách.</b>"
                    ),
                    severity="WARNING",
                    alert_type="REFUND_REQUIRED",
                    details={"order_code": order.order_code, "paid_amount": paid_amount, "ref_code": ref_code},
                )
                db.commit()
                return {
                    "success": True,
                    "message": f"Đơn hàng {order.order_code} đã bị hủy hoặc hết hạn trước đó. Ghi nhận tiền thành công và đưa vào danh sách đối soát hoàn tiền.",
                    "order_code": order.order_code,
                    "payment_status": "REFUND_PENDING",
                    "refund_pending": True,
                }

            # Chống xử lý hai lần nếu 2 link khác nhau của cùng 1 đơn đều được thanh toán (Duplicate Payment)
            if order.payment_status == "PAID":
                if trans.status == "SUCCESS":
                    webhook_log.processed = True
                    db.commit()
                    logger.info(f"[PAYOS WEBHOOK] Đơn hàng {order.order_code} đã ở trạng thái PAID trước đó (Idempotent).")
                    return {
                        "success": True,
                        "message": f"Đơn hàng {order.order_code} đã được ghi nhận thanh toán trước đó.",
                        "order_code": order.order_code,
                        "already_paid": True,
                    }
                else:
                    # Link thứ hai được thanh toán khi đơn đã PAID qua link thứ nhất!
                    trans.status = "OVERPAID"
                    trans.provider_response_raw = json.dumps(raw_info, ensure_ascii=False)
                    trans.updated_at = utcnow()
                    webhook_log.processed = True
                    webhook_log.process_error = f"Thanh toán trùng lặp: Đơn {order.order_code} đã thanh toán trước đó. Giao dịch #{order_code_num} cần hoàn tiền."
                    write_audit(
                        db,
                        action="PAYOS_DUPLICATE_PAYMENT_DETECTED",
                        entity_type="Order",
                        entity_id=order.id,
                        user=None,
                        request=None,
                        before={"payment_status": "PAID"},
                        after={"trans_id": trans.id, "payos_order_code": order_code_num, "amount": paid_amount},
                    )
                    dispatch_alert(
                        title="CẢNH BÁO: KHÁCH HÀNG THANH TOÁN TRÙNG 2 LẦN (DUPLICATE PAYMENT)",
                        message=(
                            f"Đơn hàng <b>{order.order_code}</b> nhận thêm khoản thanh toán từ link payOS #{order_code_num}.\n"
                            f"Số tiền: <b>{paid_amount:,} đ</b>\n"
                            f"Mã tham chiếu: <code>{ref_code}</code>\n"
                            f"<b>Hệ thống KHÔNG xuất kho thêm. Cần đối soát hoàn trả {paid_amount:,} đ cho khách hàng.</b>"
                        ),
                        severity="WARNING",
                        alert_type="DUPLICATE_PAYMENT_REFUND",
                        details={"order_code": order.order_code, "paid_amount": paid_amount, "ref_code": ref_code},
                    )
                    db.commit()
                    return {
                        "success": True,
                        "message": f"Đơn hàng {order.order_code} đã thanh toán trước đó. Khoản thanh toán mới #{order_code_num} được ghi nhận để đối soát hoàn trả tiền trùng.",
                        "order_code": order.order_code,
                        "duplicate_payment": True,
                        "refund_required": True,
                    }

            # Kiểm tra thuốc giữ chỗ: nếu đã bị giải phóng trước khi nhận tiền thì chuyển REFUND_PENDING, không xuất kho âm
            from app.models.inventory import StockReservation
            released_reservations = db.scalars(
                select(StockReservation).where(
                    StockReservation.order_id == order.id,
                    StockReservation.status == "RELEASED",
                )
            ).all()
            active_reservations = db.scalars(
                select(StockReservation).where(
                    StockReservation.order_id == order.id,
                    StockReservation.status == "RESERVED",
                )
            ).all()
            if released_reservations and not active_reservations:
                trans.status = "SUCCESS"
                trans.provider_response_raw = json.dumps(raw_info, ensure_ascii=False)
                trans.updated_at = utcnow()
                order.payment_status = "REFUND_PENDING"
                webhook_log.processed = True
                webhook_log.process_error = "Thuốc giữ chỗ đã bị giải phóng trước khi nhận tiền. Chuyển sang hàng đợi đối soát hoàn tiền."
                write_audit(
                    db,
                    action="PAYOS_LATE_PAYMENT_RESERVATION_RELEASED",
                    entity_type="Order",
                    entity_id=order.id,
                    user=None,
                    request=None,
                    before={"order_status": order.order_status, "payment_status": order.payment_status},
                    after={"payment_status": "REFUND_PENDING", "paid_amount": paid_amount},
                )
                dispatch_alert(
                    title="CẢNH BÁO: TỒN KHO THUỐC ĐÃ HẾT HẠN GIỮ CHỖ",
                    message=(
                        f"Đơn hàng <b>{order.order_code}</b> nhận thanh toán payOS {paid_amount:,} đ "
                        f"nhưng tồn kho giữ chỗ đã bị giải phóng trước đó.\n"
                        f"<b>Hệ thống KHÔNG xuất kho để chống tồn kho âm. Chuyển kế toán hoàn tiền.</b>"
                    ),
                    severity="WARNING",
                    alert_type="OUT_OF_STOCK_REFUND",
                    details={"order_code": order.order_code, "paid_amount": paid_amount, "ref_code": ref_code},
                )
                db.commit()
                return {
                    "success": True,
                    "message": f"Đơn hàng {order.order_code} đã hết hạn giữ chỗ tồn kho. Ghi nhận tiền thành công và đưa vào danh sách đối soát hoàn tiền.",
                    "order_code": order.order_code,
                    "payment_status": "REFUND_PENDING",
                    "refund_pending": True,
                }

            before_payment_status = order.payment_status
            before_fulfillment_status = order.fulfillment_status

            # Cập nhật trạng thái giao dịch
            trans.status = "SUCCESS"
            trans.updated_at = utcnow()
            trans.provider_response_raw = json.dumps(raw_info, ensure_ascii=False)

            # CẬP NHẬT ĐƠN HÀNG THÀNH CÔNG
            order.payment_status = "PAID"
            order.payment_method = "PAYOS"
            if order.order_status in ["PENDING", "DRAFT"]:
                order.order_status = "CONFIRMED"

            # ĐƠN CHÍNH THỨC XUẤT HIỆN TRONG DANH SÁCH XỬ LÝ CỦA KHO & ADMIN
            order.fulfillment_status = "ALLOCATED"
            webhook_log.processed = True

            # Phát thông báo tới Kho phụ trách đúng 1 lần
            if order.assigned_warehouse_id:
                try:
                    from app.services.warehouse_notification_service import WarehouseNotificationService
                    WarehouseNotificationService.notify_order_new(db, order, order.assigned_warehouse_id)
                except Exception as n_err:
                    logger.warning(f"Không thể gửi thông báo kho cho đơn {order.order_code}: {n_err}")

            # Ghi Audit Log
            write_audit(
                db,
                action="PAYOS_WEBHOOK_PAYMENT_SUCCESS",
                entity_type="Order",
                entity_id=order.id,
                user=None,
                request=None,
                before={"payment_status": before_payment_status, "fulfillment_status": before_fulfillment_status},
                after={
                    "payment_status": "PAID",
                    "fulfillment_status": "ALLOCATED",
                    "payos_order_code": order_code_num,
                    "amount": paid_amount,
                    "reference": ref_code,
                },
            )

            # Gửi cảnh báo Telegram
            dispatch_alert(
                title="THANH TOÁN PAYOS THÀNH CÔNG",
                message=(
                    f"Đơn hàng: <b>{order.order_code}</b>\n"
                    f"Khách hàng: <b>{order.customer_name}</b>\n"
                    f"Số tiền đã nhận: <b>{paid_amount:,} đ</b>\n"
                    f"Mã tham chiếu: <code>{ref_code}</code>\n"
                    f"Trạng thái: <b>Đã thanh toán (PAID) - Sẵn sàng xuất kho</b>"
                ),
                severity="INFO",
                alert_type="PAYMENT_RECEIVED",
                details={
                    "Mã đơn": order.order_code,
                    "Cổng": "payOS",
                    "Số tiền": f"{paid_amount:,} VND",
                    "Ref": ref_code,
                },
            )

            db.commit()
            db.refresh(order)

            logger.info(
                f"[PAYOS WEBHOOK THÀNH CÔNG] Đơn {order.order_code} đã thanh toán thành công {paid_amount:,} đ. "
                f"Fulfillment chuyển sang ALLOCATED, kho sẵn sàng chuẩn bị hàng."
            )

            return {
                "success": True,
                "message": f"Thanh toán đơn hàng {order.order_code} thành công.",
                "order_code": order.order_code,
                "payment_status": "PAID",
                "fulfillment_status": "ALLOCATED",
            }
        else:
            # Giao dịch thất bại / bị hủy từ payOS
            if trans and trans.status == "PENDING":
                trans.status = "FAILED"
                trans.updated_at = utcnow()
                webhook_log.process_error = f"payOS code {code}"
                db.commit()

            logger.info(f"[PAYOS WEBHOOK] Giao dịch không thành công cho đơn {order.order_code}, code={code}")
            return {
                "success": False,
                "message": f"Giao dịch payOS kết thúc với trạng thái {code}.",
                "order_code": order.order_code,
            }

    @classmethod
    def check_payment_status(cls, db: Session, order_code: str) -> dict[str, Any]:
        """
        Đối soát tức thời trạng thái thanh toán từ payOS API:
        Dùng cho Storefront Polling, trang Result hoặc Admin khi chưa nhận được Webhook.
        """
        clean_code = order_code.strip()
        order = db.scalar(select(Order).where(Order.order_code == clean_code))
        if not order:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{clean_code}'.")

        if order.payment_status == "PAID":
            return {
                "order_code": order.order_code,
                "payment_status": "PAID",
                "payment_method": order.payment_method,
                "fulfillment_status": order.fulfillment_status,
                "total_amount": float(order.total_amount),
                "is_paid": True,
            }

        # Tìm giao dịch payOS mới nhất
        trans = db.scalar(
            select(PaymentTransaction)
            .where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "PAYOS",
            )
            .order_by(desc(PaymentTransaction.id))
        )

        if not trans or not trans.provider_trans_id:
            return {
                "order_code": order.order_code,
                "payment_status": order.payment_status,
                "payment_method": order.payment_method,
                "fulfillment_status": order.fulfillment_status,
                "total_amount": float(order.total_amount),
                "is_paid": False,
                "message": "Chưa có giao dịch payOS nào được tạo cho đơn hàng này.",
            }

        client = cls.get_client()
        try:
            payos_order_code = int(trans.provider_trans_id)
        except (ValueError, TypeError):
            payos_order_code = 0

        if not payos_order_code:
            return {
                "order_code": order.order_code,
                "payment_status": order.payment_status,
                "fulfillment_status": order.fulfillment_status,
                "is_paid": False,
            }

        try:
            info = client.payment_requests.get(payos_order_code)
        except Exception as e:
            logger.error(f"Lỗi khi tra cứu trạng thái đơn payOS {payos_order_code}: {e}")
            return {
                "order_code": order.order_code,
                "payment_status": order.payment_status,
                "fulfillment_status": order.fulfillment_status,
                "is_paid": False,
                "error": str(e),
            }

        payos_status = getattr(info, "status", "")
        logger.info(f"[PAYOS RECONCILE] Tra cứu đơn {clean_code} (payOS #{payos_order_code}): trạng thái={payos_status}")

        if payos_status == "PAID":
            # BUG-01: Kiểm tra số tiền trả về từ payOS query API
            order_total = int(order.total_amount)
            paid_amount = int(getattr(info, "amountPaid", 0) or getattr(info, "amount", 0))
            if paid_amount != order_total:
                logger.warning(
                    f"[PAYOS RECONCILE] Lệch số tiền đơn {order.order_code}: "
                    f"cần thu {order_total:,} đ, thực nhận {paid_amount:,} đ"
                )
                return {
                    "order_code": order.order_code,
                    "payment_status": order.payment_status,
                    "fulfillment_status": order.fulfillment_status,
                    "total_amount": float(order.total_amount),
                    "is_paid": False,
                    "amount_mismatch": True,
                    "message": f"Số tiền thanh toán ({paid_amount:,} đ) không khớp với đơn hàng ({order_total:,} đ).",
                }

            # BUG-02: Kiểm tra đơn đã hủy hoặc hết hạn
            if (
                order.order_status == "CANCELLED"
                or order.fulfillment_status == "CANCELLED"
                or order.payment_status in ["EXPIRED", "CANCELLED"]
            ):
                trans.status = "SUCCESS"
                trans.updated_at = utcnow()
                order.payment_status = "REFUND_PENDING"
                db.commit()
                return {
                    "order_code": order.order_code,
                    "payment_status": "REFUND_PENDING",
                    "fulfillment_status": order.fulfillment_status,
                    "total_amount": float(order.total_amount),
                    "is_paid": True,
                    "refund_pending": True,
                    "is_cancelled": True,
                }

            # Kiểm tra thuốc giữ chỗ: nếu đã bị giải phóng trước khi nhận tiền thì chuyển REFUND_PENDING, không xuất kho âm
            from app.models.inventory import StockReservation
            released_reservations = db.scalars(
                select(StockReservation).where(
                    StockReservation.order_id == order.id,
                    StockReservation.status == "RELEASED",
                )
            ).all()
            active_reservations = db.scalars(
                select(StockReservation).where(
                    StockReservation.order_id == order.id,
                    StockReservation.status == "RESERVED",
                )
            ).all()
            if released_reservations and not active_reservations:
                trans.status = "SUCCESS"
                trans.updated_at = utcnow()
                order.payment_status = "REFUND_PENDING"
                db.commit()
                return {
                    "order_code": order.order_code,
                    "payment_status": "REFUND_PENDING",
                    "fulfillment_status": order.fulfillment_status,
                    "total_amount": float(order.total_amount),
                    "is_paid": True,
                    "refund_pending": True,
                    "reservation_expired": True,
                }

            trans.status = "SUCCESS"
            trans.updated_at = utcnow()
            order.payment_status = "PAID"
            order.payment_method = "PAYOS"
            if order.order_status in ["PENDING", "DRAFT"]:
                order.order_status = "CONFIRMED"
            order.fulfillment_status = "ALLOCATED"

            if order.assigned_warehouse_id:
                try:
                    from app.services.warehouse_notification_service import WarehouseNotificationService
                    WarehouseNotificationService.notify_order_new(db, order, order.assigned_warehouse_id)
                except Exception:
                    pass

            db.commit()
            db.refresh(order)

            return {
                "order_code": order.order_code,
                "payment_status": "PAID",
                "payment_method": "PAYOS",
                "fulfillment_status": "ALLOCATED",
                "total_amount": float(order.total_amount),
                "is_paid": True,
                "synced_from_gateway": True,
            }

        if payos_status in ["CANCELLED", "EXPIRED"]:
            if trans and trans.status == "PENDING":
                trans.status = payos_status
                trans.updated_at = utcnow()
                db.commit()
            return {
                "order_code": order.order_code,
                "payment_status": order.payment_status,
                "payment_method": order.payment_method,
                "fulfillment_status": order.fulfillment_status,
                "total_amount": float(order.total_amount),
                "is_paid": False,
                "is_cancelled": True,
                "payos_status": payos_status,
            }

        return {
            "order_code": order.order_code,
            "payment_status": order.payment_status,
            "payment_method": order.payment_method,
            "fulfillment_status": order.fulfillment_status,
            "total_amount": float(order.total_amount),
            "is_paid": False,
            "payos_status": payos_status,
        }

    @classmethod
    def confirm_webhook_url(cls, webhook_url: str) -> dict[str, Any]:
        """
        Đăng ký và xác nhận Webhook URL với máy chủ payOS (Admin/Setup tool).
        """
        client = cls.get_client()
        clean_url = webhook_url.strip()
        try:
            confirmed_res = client.webhooks.confirm(clean_url)
            wh_url = getattr(confirmed_res, "webhook_url", None) or clean_url
            return {
                "success": True,
                "webhook_url": str(wh_url),
                "message": "Webhook URL đã được đăng ký và xác nhận thành công với payOS.",
            }
        except Exception as e:
            logger.error(f"Lỗi khi xác nhận webhook URL với payOS: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"payOS từ chối xác nhận Webhook URL: {str(e)}",
            )
