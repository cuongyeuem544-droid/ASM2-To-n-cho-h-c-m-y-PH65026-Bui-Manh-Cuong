import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from payos import PayOS
from payos.types.v2.payment_requests import CreatePaymentLinkRequest, ItemData
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Order, PaymentTransaction
from app.services.audit import write_audit

logger = logging.getLogger("pharmatrust.payos")


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
    def create_payment_request(
        cls,
        db: Session,
        order: Order,
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Khởi tạo yêu cầu thanh toán qua payOS:
        1. Kiểm tra tính hợp lệ của đơn hàng (chưa hủy, chưa thanh toán).
        2. Sinh mã số đơn hàng dạng số nguyên duy nhất (payos_order_code) cho payOS.
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

        # Sinh mã số nguyên duy nhất cho payOS (phù hợp giới hạn JS safe integer: < 9007199254740991)
        # Định dạng: YYMMDDHHMMSS + 2 chữ số từ order.id -> 14 chữ số
        now = datetime.now()
        numeric_time = now.strftime("%y%m%d%H%M%S")
        suffix = f"{order.id % 100:02d}"
        payos_order_code = int(f"{numeric_time}{suffix}")

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

        ret_url = return_url or f"{settings.payos_return_url}?order_code={order.order_code}"
        cancel_url = f"{settings.payos_cancel_url}?order_code={order.order_code}&status=CANCELLED"

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
        txn_code = f"TXN-PAYOS-{order.order_code}-{payos_order_code}"
        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "PAYOS",
                PaymentTransaction.status == "PENDING",
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
            trans.transaction_code = txn_code
            trans.amount = Decimal(str(amount))
            trans.provider_trans_id = str(payos_order_code)
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
        1. Xác thực tính toàn vẹn (checksum / signature) bằng checksum_key.
        2. Tìm giao dịch và đơn hàng tương ứng.
        3. Kiểm tra Idempotency chống cộng tiền / đổi trạng thái nhiều lần.
        4. Cập nhật Order sang PAID, OrderStatus sang CONFIRMED.
        5. ĐỔI fulfillment_status sang ALLOCATED -> Đơn hàng CHÍNH THỨC xuất hiện trong danh sách cần xử lý của Kho & Admin.
        6. Phát thông báo nội bộ cho nhân viên kho nhận đơn mới.
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

        logger.info(
            f"[PAYOS WEBHOOK] Nhận thanh toán cho mã số payOS {order_code_num}, "
            f"code={code}, amount={amount}, ref={ref_code}"
        )

        # 2. Xử lý webhook kiểm thử từ payOS dashboard (khi bấm Test Webhook trên payOS)
        if order_code_num in [123, 123456, 0] or "demo" in desc_text.lower():
            logger.info("[PAYOS WEBHOOK] Webhook thử nghiệm kết nối từ dashboard payOS thành công.")
            return {
                "success": True,
                "message": "Webhook thử nghiệm kết nối payOS đã được xác thực an toàn.",
            }

        # 3. Tìm giao dịch theo provider_trans_id hoặc mã đơn hàng
        trans = None
        if order_code_num:
            trans = db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.provider == "PAYOS",
                    PaymentTransaction.provider_trans_id == str(order_code_num),
                )
            )

        order = None
        if trans and trans.order_id:
            order = db.get(Order, trans.order_id)

        if not order and desc_text:
            # Fallback tìm đơn qua chuỗi mã đơn PT- trong description
            import re
            match = re.search(r"PT-\d{6}-\w+", desc_text)
            if match:
                extracted_code = match.group(0)
                order = db.scalar(select(Order).where(Order.order_code == extracted_code))
                if order and not trans:
                    trans = db.scalar(
                        select(PaymentTransaction).where(
                            PaymentTransaction.order_id == order.id,
                            PaymentTransaction.provider == "PAYOS",
                        ).order_by(desc(PaymentTransaction.id))
                    )

        if not order:
            logger.warning(f"[PAYOS WEBHOOK] Không tìm thấy đơn hàng cho payos_order_code={order_code_num}, desc={desc_text}")
            return {
                "success": False,
                "message": f"Không tìm thấy đơn hàng tương ứng với mã {order_code_num}.",
            }

        # 4. Kiểm tra mã phản hồi (code '00' là giao dịch thành công trong payOS)
        if str(code) == "00":
            # Chống trùng lặp (Idempotency check)
            if order.payment_status == "PAID":
                logger.info(f"[PAYOS WEBHOOK] Đơn hàng {order.order_code} đã ở trạng thái PAID trước đó (Idempotent).")
                return {
                    "success": True,
                    "message": f"Đơn hàng {order.order_code} đã được ghi nhận thanh toán trước đó.",
                    "order_code": order.order_code,
                    "already_paid": True,
                }

            before_payment_status = order.payment_status
            before_fulfillment_status = order.fulfillment_status

            # Cập nhật trạng thái giao dịch
            if trans:
                trans.status = "SUCCESS"
                trans.updated_at = utcnow()
                # Ghi thêm thông tin đối soát
                raw_info = {
                    "reference": ref_code,
                    "amount": amount,
                    "counter_bank": getattr(verified_data, "counter_account_bank_id", None),
                    "counter_acc": getattr(verified_data, "counter_account_number", None),
                    "counter_name": getattr(verified_data, "counter_account_name", None),
                    "paid_at": getattr(verified_data, "transaction_date_time", None),
                }
                trans.provider_response_raw = json.dumps(raw_info, ensure_ascii=False)

            # CẬP NHẬT ĐƠN HÀNG THÀNH CÔNG
            order.payment_status = "PAID"
            order.payment_method = "PAYOS"
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
                    "amount": amount,
                    "reference": ref_code,
                },
            )

            db.commit()
            db.refresh(order)

            logger.info(
                f"[PAYOS WEBHOOK THÀNH CÔNG] Đơn {order.order_code} đã thanh toán thành công {amount:,} đ. "
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
            # Giao dịch thất bại / bị hủy
            if trans and trans.status == "PENDING":
                trans.status = "FAILED"
                trans.updated_at = utcnow()
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
        payos_order_code = int(trans.provider_trans_id)

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
