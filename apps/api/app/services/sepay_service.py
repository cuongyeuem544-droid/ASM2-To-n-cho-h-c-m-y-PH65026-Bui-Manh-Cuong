import hashlib
import hmac
import json
import logging
import random
import re
from datetime import UTC, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Order,
    PaymentTransaction,
    PaymentWebhookEvent,
    SepayInboundTransaction,
    SepayPaymentCode,
)
from app.services.alert_notifier import dispatch_alert

logger = logging.getLogger("pharmatrust.sepay")


def utcnow() -> datetime:
    return datetime.now(UTC)


class SepayService:
    """
    Dịch vụ Tích hợp Cổng thanh toán Chuyển khoản Tự động SePay Webhook + VietQR MBBank:
    - Sinh mã định danh thanh toán duy nhất cho mỗi đơn hàng (tiền tố HC + 8 chữ số).
    - Tạo mã VietQR Napas 247 động chuẩn ngân hàng MBBank.
    - Tiếp nhận và xác thực Webhook biến động số dư SePay bằng HMAC-SHA256 (raw body + X-SePay-Signature + X-SePay-Timestamp).
    - Chống Replay Attack bằng kiểm tra độ lệch Timestamp.
    - Chống trùng lặp giao dịch (Idempotency) tuyệt đối nhờ khóa UNIQUE sepay_id trên PostgreSQL.
    - Kiểm tra chặt chẽ: đúng tài khoản thụ hưởng, đúng mã thanh toán, đúng số tiền (sai/thiếu/dư chuyển đối soát).
    - Cập nhật Order, PaymentTransaction và thông báo Admin/Kho; chặn xuất kho khi chưa PAID.
    """

    BANK_BIN_MAPPING = {
        "MB": {"bin": "970422", "name": "Ngân hàng TMCP Quân Đội (MBBank)"},
        "MBBANK": {"bin": "970422", "name": "Ngân hàng TMCP Quân Đội (MBBank)"},
        "VCB": {"bin": "970436", "name": "Ngân hàng TMCP Ngoại Thương (Vietcombank)"},
        "TCB": {"bin": "970407", "name": "Ngân hàng TMCP Kỹ Thương (Techcombank)"},
        "BIDV": {"bin": "970418", "name": "Ngân hàng TMCP Đầu tư và Phát triển (BIDV)"},
        "VPB": {"bin": "970432", "name": "Ngân hàng TMCP Việt Nam Thịnh Vượng (VPBank)"},
        "ACB": {"bin": "970416", "name": "Ngân hàng TMCP Á Châu (ACB)"},
    }

    @classmethod
    def get_bank_info(cls, bank_id: Optional[str] = None) -> dict[str, str]:
        key = (bank_id or settings.sepay_bank_id or "MB").upper()
        if key in cls.BANK_BIN_MAPPING:
            return cls.BANK_BIN_MAPPING[key]
        return {"bin": "970422", "name": f"Ngân hàng {key}"}

    @classmethod
    def generate_payment_code(cls, db: Session, order: Order) -> SepayPaymentCode:
        """
        Tạo mã thanh toán duy nhất cho đơn hàng theo chuẩn SePay:
        Tiền tố 'HC' + 8 chữ số (ví dụ: HC10000045).
        Lưu vào bảng sepay_payment_codes và liên kết chặt chẽ với order_id.
        """
        existing = db.scalar(
            select(SepayPaymentCode).where(SepayPaymentCode.order_id == order.id)
        )
        if existing:
            return existing

        # Thử sinh mã từ order.id (nếu khả dụng)
        code_number: int | None = None
        payment_code: str | None = None

        if 1 <= order.id <= 99_999_999:
            # Thử với chính ID đơn hàng (hoặc 10000000 + order.id)
            candidate_num = order.id if order.id >= 10_000_000 else (10_000_000 + order.id)
            candidate_code = f"HC{candidate_num:08d}"
            conflict = db.scalar(
                select(SepayPaymentCode).where(
                    or_(
                        SepayPaymentCode.code_number == candidate_num,
                        SepayPaymentCode.payment_code == candidate_code,
                    )
                )
            )
            if not conflict:
                code_number = candidate_num
                payment_code = candidate_code

        # Nếu bị xung đột hoặc chưa có, sinh ngẫu nhiên 8 chữ số [10000000, 99999999]
        if code_number is None or payment_code is None:
            for _ in range(20):
                candidate_num = random.randint(10_000_000, 99_999_999)
                candidate_code = f"HC{candidate_num:08d}"
                conflict = db.scalar(
                    select(SepayPaymentCode).where(
                        or_(
                            SepayPaymentCode.code_number == candidate_num,
                            SepayPaymentCode.payment_code == candidate_code,
                        )
                    )
                )
                if not conflict:
                    code_number = candidate_num
                    payment_code = candidate_code
                    break

        if code_number is None or payment_code is None:
            raise HTTPException(
                status_code=500,
                detail="Không thể tạo mã thanh toán SePay duy nhất sau nhiều lần thử.",
            )

        code_obj = SepayPaymentCode(
            order_id=order.id,
            payment_code=payment_code,
            code_number=code_number,
        )
        db.add(code_obj)
        db.commit()
        db.refresh(code_obj)
        return code_obj

    @classmethod
    def generate_vietqr_url(
        cls,
        amount: int,
        payment_code: str,
        bank_id: Optional[str] = None,
        account_number: Optional[str] = None,
        account_holder: Optional[str] = None,
    ) -> str:
        """
        Sinh URL ảnh mã QR VietQR Napas 247 mã hóa sẵn thông tin chuyển khoản:
        - Ngân hàng thụ hưởng MBBank (hoặc cấu hình)
        - Số tài khoản & tên chủ tài khoản từ biến môi trường
        - Số tiền do Backend tính
        - Nội dung chuyển khoản là mã thanh toán HC + 8 số
        """
        b_id = bank_id or settings.sepay_bank_id or "MB"
        acc_no = account_number or settings.sepay_account_number
        holder = account_holder or settings.sepay_account_holder
        clean_code = payment_code.strip().upper()

        return (
            f"https://img.vietqr.io/image/{b_id}-{acc_no}-compact2.png"
            f"?amount={amount}&addInfo={quote(clean_code)}&accountName={quote(holder)}"
        )

    @classmethod
    def create_payment_request(
        cls,
        db: Session,
        order: Order,
        return_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Khởi tạo yêu cầu thanh toán SePay VietQR cho đơn hàng H4CARE.
        """
        if order.payment_status == "PAID":
            raise HTTPException(
                status_code=400,
                detail="Đơn hàng này đã được thanh toán thành công trước đó.",
            )

        if order.order_status == "CANCELLED":
            raise HTTPException(
                status_code=400,
                detail="Đơn hàng này đã bị hủy, không thể khởi tạo thanh toán.",
            )

        amount = int(order.total_amount)
        bank_info = cls.get_bank_info()
        payment_code_obj = cls.generate_payment_code(db, order)
        payment_code = payment_code_obj.payment_code

        qr_url = cls.generate_vietqr_url(amount=amount, payment_code=payment_code)

        metadata = {
            "provider": "SEPAY",
            "bank_id": settings.sepay_bank_id,
            "bank_name": bank_info["name"],
            "account_number": settings.sepay_account_number,
            "account_holder": settings.sepay_account_holder,
            "payment_code": payment_code,
            "qr_url": qr_url,
        }

        # Tạo hoặc cập nhật PaymentTransaction
        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "SEPAY",
            )
        )
        if not trans:
            trans = PaymentTransaction(
                order_id=order.id,
                transaction_code=f"TXN-SEPAY-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="SEPAY",
                amount=Decimal(str(amount)),
                currency="VND",
                status="PENDING",
                provider_pay_url=qr_url,
                provider_response_raw=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(trans)
        else:
            trans.amount = Decimal(str(amount))
            trans.status = "PENDING"
            trans.provider_pay_url = qr_url
            trans.provider_response_raw = json.dumps(metadata, ensure_ascii=False)

        order.payment_method = "SEPAY"
        order.fulfillment_status = "WAITING_PAYMENT"
        db.commit()
        db.refresh(trans)

        return {
            "status": "SUCCESS",
            "message": "Khởi tạo mã VietQR chuyển khoản SePay MBBank thành công.",
            "order_code": order.order_code,
            "payment_code": payment_code,
            "transaction_code": trans.transaction_code,
            "amount": amount,
            "currency": "VND",
            "provider": "SEPAY",
            "qr_code_url": qr_url,
            "bank_name": bank_info["name"],
            "bank_id": settings.sepay_bank_id,
            "account_number": settings.sepay_account_number,
            "account_holder": settings.sepay_account_holder,
            "transfer_memo": payment_code,
        }

    @classmethod
    def verify_webhook_signature(
        cls,
        raw_body: bytes,
        signature_header: Optional[str],
        timestamp_header: Optional[str],
        auth_header: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Xác thực chữ ký HMAC-SHA256 chuẩn SePay:
        - Format signature: sha256={hex_hash}
        - Message to sign: {timestamp}.{raw_body}
        - Kiểm tra độ lệch timestamp trong vòng 300 giây (5 phút) để chống Replay Attack.
        - Hỗ trợ fallback kiểm tra Token Authorization nếu SePay cấu hình dạng Token/API Key.
        """
        secret = (settings.sepay_webhook_secret or "").strip()

        # 1. Nếu hệ thống đã cấu hình Secret, bắt buộc phải xác thực
        if secret:
            # 1.1 Kiểm tra qua Header X-SePay-Signature và X-SePay-Timestamp
            if signature_header and timestamp_header:
                try:
                    ts = int(str(timestamp_header).strip())
                except (ValueError, TypeError):
                    return False, "Header X-SePay-Timestamp không đúng định dạng Unix timestamp."

                current_ts = int(datetime.now(timezone.utc).timestamp())
                diff = abs(current_ts - ts)
                if diff > 300:
                    return False, f"X-SePay-Timestamp đã quá hạn ({diff}s > 300s). Yêu cầu bị từ chối chống tấn công phát lại (Replay Attack)."

                incoming_hash = signature_header.strip()
                if incoming_hash.startswith("sha256="):
                    incoming_hash = incoming_hash[7:].strip()

                signed_payload = f"{ts}.".encode("utf-8") + raw_body
                calculated_hash = hmac.new(
                    secret.encode("utf-8"),
                    signed_payload,
                    hashlib.sha256,
                ).hexdigest()

                if not hmac.compare_digest(calculated_hash.lower(), incoming_hash.lower()):
                    return False, "Chữ ký HMAC-SHA256 (X-SePay-Signature) không khớp."

                return True, "HMAC_VERIFIED"

            # 1.2 Fallback: Xác thực qua Authorization Header (dạng Bearer token hoặc Apikey)
            if auth_header:
                token = (
                    auth_header.replace("Bearer ", "")
                    .replace("Apikey ", "")
                    .replace("apiKey ", "")
                    .strip()
                )
                if hmac.compare_digest(token, secret):
                    return True, "TOKEN_VERIFIED"

            return False, "Thiếu chữ ký xác thực Webhook hợp lệ (Yêu cầu X-SePay-Signature & X-SePay-Timestamp hoặc Authorization header)."

        # 2. Nếu chưa cấu hình secret trên môi trường development/local
        if (settings.app_env or "").lower() in ["production", "prod", "staging"]:
            return False, "SEPAY_WEBHOOK_SECRET bắt buộc phải được cấu hình trên môi trường production/staging."

        return True, "DEV_NO_SECRET_BYPASS"

    @classmethod
    def process_webhook(
        cls,
        db: Session,
        payload: dict[str, Any],
        raw_body: bytes,
        signature_header: Optional[str] = None,
        timestamp_header: Optional[str] = None,
        auth_header: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Tiếp nhận và xử lý Webhook biến động số dư SePay MBBank:
        1. Xác thực HMAC-SHA256 chống giả mạo và chống replay attack.
        2. Chống trùng lặp giao dịch (Idempotency) dựa trên khóa UNIQUE sepay_id.
        3. Kiểm tra hướng tiền (chỉ chấp nhận transferType == 'in').
        4. Kiểm tra số tài khoản nhận tiền.
        5. Trích xuất mã thanh toán dạng HC + 8 số và tìm đơn hàng tương ứng.
        6. Đối soát số tiền nhận được:
           - Thiếu hoặc dư tiền: Chuyển vào trạng thái đối soát (FLAGGED), KHÔNG tự động đánh dấu PAID.
           - Đúng số tiền: Cập nhật Order PAID, PaymentTransaction SUCCESS, mở khóa cho kho soạn hàng.
        """
        # 1. Xác thực chữ ký
        is_valid, auth_msg = cls.verify_webhook_signature(
            raw_body=raw_body,
            signature_header=signature_header,
            timestamp_header=timestamp_header,
            auth_header=auth_header,
        )
        if not is_valid:
            logger.warning(f"[SEPAY WEBHOOK] Xác thực thất bại: {auth_msg}")
            raise HTTPException(status_code=401, detail=auth_msg)

        # 2. Ghi nhật ký vào PaymentWebhookEvent
        raw_payload_str = raw_body.decode("utf-8", errors="replace")
        trans_id_raw = str(payload.get("id") or "")
        webhook_log = PaymentWebhookEvent(
            provider="SEPAY",
            event_id=trans_id_raw,
            signature=signature_header or auth_header,
            payload_raw=raw_payload_str,
            processed=False,
        )
        db.add(webhook_log)
        db.flush()

        # 3. Phân tích các trường dữ liệu SePay
        try:
            sepay_id = int(payload.get("id"))
        except (ValueError, TypeError):
            err = "Payload SePay thiếu trường 'id' hoặc không phải số nguyên hợp lệ."
            webhook_log.process_error = err
            db.commit()
            raise HTTPException(status_code=400, detail=err)

        gateway = payload.get("gateway")
        account_number = str(payload.get("accountNumber") or "").strip()
        transfer_type = str(payload.get("transferType") or "").lower().strip()
        transfer_amount = int(payload.get("transferAmount") or 0)
        accumulated = (
            int(payload.get("accumulated"))
            if payload.get("accumulated") is not None
            else None
        )
        code = str(payload.get("code") or "").strip().upper()
        content = str(payload.get("content") or "").strip()
        description = str(payload.get("description") or "").strip()
        ref_code = payload.get("referenceCode")

        trans_date = None
        if payload.get("transactionDate"):
            try:
                trans_date = datetime.strptime(
                    payload["transactionDate"], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
            except Exception:
                trans_date = None

        # 4. Kiểm tra Idempotency chống trùng lặp Webhook
        existing_inbound = db.scalar(
            select(SepayInboundTransaction).where(
                SepayInboundTransaction.sepay_id == sepay_id
            )
        )
        if existing_inbound:
            logger.info(
                f"[SEPAY WEBHOOK] Giao dịch sepay_id={sepay_id} đã được xử lý trước đó (Idempotent Hit)."
            )
            webhook_log.processed = True
            db.commit()
            return {
                "success": True,
                "message": f"Giao dịch SePay #{sepay_id} đã được xử lý thành công trước đó (Idempotent).",
                "sepay_id": sepay_id,
                "status": existing_inbound.status,
            }

        # 5. Kiểm tra loại giao dịch: Chỉ xử lý giao dịch tiền vào (transferType == 'in')
        if transfer_type != "in":
            logger.info(
                f"[SEPAY WEBHOOK] Bỏ qua giao dịch tiền ra: sepay_id={sepay_id}, type={transfer_type}"
            )
            inbound_rec = SepayInboundTransaction(
                sepay_id=sepay_id,
                gateway=gateway,
                account_number=account_number,
                transfer_type=transfer_type,
                transfer_amount=transfer_amount,
                accumulated=accumulated,
                code=code,
                content=content,
                reference_code=ref_code,
                description=description,
                transaction_date=trans_date,
                status="IGNORED_OUT",
                error_message="Giao dịch tiền ra (transferType != 'in'), bỏ qua.",
                raw_payload=raw_payload_str,
            )
            db.add(inbound_rec)
            webhook_log.processed = True
            db.commit()
            return {
                "success": True,
                "message": "Đã ghi nhận nhưng bỏ qua giao dịch tiền ra.",
                "sepay_id": sepay_id,
            }

        # 6. Kiểm tra số tài khoản nhận tiền
        configured_acc = (settings.sepay_account_number or "").strip()
        if configured_acc:
            clean_acc = account_number.lstrip("0")
            clean_conf = configured_acc.lstrip("0")
            if clean_acc != clean_conf and account_number != configured_acc:
                warn_msg = f"Tài khoản nhận tiền '{account_number}' không khớp với cấu hình '{configured_acc}'."
                logger.warning(f"[SEPAY WEBHOOK] {warn_msg}")
                inbound_rec = SepayInboundTransaction(
                    sepay_id=sepay_id,
                    gateway=gateway,
                    account_number=account_number,
                    transfer_type=transfer_type,
                    transfer_amount=transfer_amount,
                    accumulated=accumulated,
                    code=code,
                    content=content,
                    reference_code=ref_code,
                    description=description,
                    transaction_date=trans_date,
                    status="FLAGGED_WRONG_ACCOUNT",
                    error_message=warn_msg,
                    raw_payload=raw_payload_str,
                )
                db.add(inbound_rec)
                webhook_log.process_error = warn_msg
                db.commit()

                dispatch_alert(
                    title="CẢNH BÁO SEPAY: SAI SỐ TÀI KHOẢN NHẬN TIỀN",
                    message=(
                        f"Giao dịch SePay: <b>#{sepay_id}</b>\n"
                        f"Tài khoản nhận thực tế: <code>{account_number}</code>\n"
                        f"Tài khoản cấu hình hệ thống: <code>{configured_acc}</code>\n"
                        f"Số tiền: <b>{transfer_amount:,} đ</b>\n"
                        f"Nội dung: <code>{content}</code>"
                    ),
                    severity="WARNING",
                    alert_type="SEPAY_WRONG_ACCOUNT",
                )
                return {
                    "success": False,
                    "message": warn_msg,
                    "sepay_id": sepay_id,
                }

        # 7. Trích xuất mã thanh toán HC + 8 số
        matched_code: str | None = None
        if code and re.match(r"^HC\d{8}$", code):
            matched_code = code
        else:
            # Tìm trong nội dung chuyển khoản hoặc description
            search_text = f"{content} {description}".upper()
            found = re.findall(r"\b(HC\d{8})\b", search_text)
            if found:
                matched_code = found[0]

        if not matched_code:
            err_msg = f"Không tìm thấy mã thanh toán hợp lệ (HC + 8 chữ số) trong nội dung: '{content}'"
            logger.warning(f"[SEPAY WEBHOOK] {err_msg}")
            inbound_rec = SepayInboundTransaction(
                sepay_id=sepay_id,
                gateway=gateway,
                account_number=account_number,
                transfer_type=transfer_type,
                transfer_amount=transfer_amount,
                accumulated=accumulated,
                code=code or None,
                content=content,
                reference_code=ref_code,
                description=description,
                transaction_date=trans_date,
                status="FLAGGED_NO_CODE",
                error_message=err_msg,
                raw_payload=raw_payload_str,
            )
            db.add(inbound_rec)
            webhook_log.process_error = err_msg
            db.commit()

            dispatch_alert(
                title="ĐỐI SOÁT SEPAY: CHUYỂN KHOẢN THIẾU MÃ ĐƠN HÀNG",
                message=(
                    f"Giao dịch SePay: <b>#{sepay_id}</b>\n"
                    f"Số tiền: <b>{transfer_amount:,} đ</b>\n"
                    f"Nội dung UNC: <code>{content}</code>\n"
                    f"Mô tả: <code>{description}</code>\n"
                    f"Hành động: <b>Cần đối soát thủ công và gán đơn bằng tay</b>"
                ),
                severity="WARNING",
                alert_type="SEPAY_UNMATCHED_CODE",
            )
            return {
                "success": False,
                "message": err_msg,
                "sepay_id": sepay_id,
            }

        # 8. Tra cứu mã thanh toán trong bảng sepay_payment_codes
        code_entry = db.scalar(
            select(SepayPaymentCode).where(
                SepayPaymentCode.payment_code == matched_code
            )
        )
        if not code_entry:
            err_msg = f"Mã thanh toán '{matched_code}' không tồn tại trong hệ thống H4CARE."
            logger.warning(f"[SEPAY WEBHOOK] {err_msg}")
            inbound_rec = SepayInboundTransaction(
                sepay_id=sepay_id,
                gateway=gateway,
                account_number=account_number,
                transfer_type=transfer_type,
                transfer_amount=transfer_amount,
                accumulated=accumulated,
                code=matched_code,
                content=content,
                reference_code=ref_code,
                description=description,
                transaction_date=trans_date,
                status="FLAGGED_CODE_NOT_FOUND",
                error_message=err_msg,
                raw_payload=raw_payload_str,
            )
            db.add(inbound_rec)
            webhook_log.process_error = err_msg
            db.commit()

            dispatch_alert(
                title="ĐỐI SOÁT SEPAY: MÃ THANH TOÁN KHÔNG TỒN TẠI",
                message=(
                    f"Mã UNC nhận được: <code>{matched_code}</code>\n"
                    f"Số tiền: <b>{transfer_amount:,} đ</b>\n"
                    f"Giao dịch: <b>#{sepay_id}</b>"
                ),
                severity="WARNING",
                alert_type="SEPAY_CODE_NOT_FOUND",
            )
            return {
                "success": False,
                "message": err_msg,
                "sepay_id": sepay_id,
            }

        # 9. Lấy thông tin đơn hàng
        order = db.get(Order, code_entry.order_id)
        if not order:
            err_msg = f"Đơn hàng ID={code_entry.order_id} liên kết với mã '{matched_code}' không tồn tại."
            inbound_rec = SepayInboundTransaction(
                sepay_id=sepay_id,
                gateway=gateway,
                account_number=account_number,
                transfer_type=transfer_type,
                transfer_amount=transfer_amount,
                accumulated=accumulated,
                code=matched_code,
                content=content,
                reference_code=ref_code,
                description=description,
                transaction_date=trans_date,
                status="FLAGGED_ORDER_NOT_FOUND",
                error_message=err_msg,
                raw_payload=raw_payload_str,
            )
            db.add(inbound_rec)
            webhook_log.process_error = err_msg
            db.commit()
            return {"success": False, "message": err_msg, "sepay_id": sepay_id}

        # 10. Kiểm tra nếu đơn hàng đã được đánh dấu PAID trước đó
        if order.payment_status == "PAID":
            logger.info(
                f"[SEPAY WEBHOOK] Đơn hàng {order.order_code} đã ở trạng thái PAID trước đó (Idempotent)."
            )
            inbound_rec = SepayInboundTransaction(
                sepay_id=sepay_id,
                gateway=gateway,
                account_number=account_number,
                transfer_type=transfer_type,
                transfer_amount=transfer_amount,
                accumulated=accumulated,
                code=matched_code,
                content=content,
                reference_code=ref_code,
                description=description,
                transaction_date=trans_date,
                status="DUPLICATE_PAID",
                order_id=order.id,
                error_message="Đơn hàng đã được thanh toán thành công trước đó.",
                raw_payload=raw_payload_str,
            )
            db.add(inbound_rec)
            webhook_log.processed = True
            db.commit()
            return {
                "success": True,
                "message": f"Đơn hàng {order.order_code} đã ở trạng thái PAID trước đó.",
                "order_code": order.order_code,
                "sepay_id": sepay_id,
            }

        # 11. Kiểm tra đối soát số tiền (Chống giao dịch sai/thiếu/dư tiền)
        expected_amount = int(order.total_amount)
        if transfer_amount < expected_amount:
            shortage = expected_amount - transfer_amount
            err_msg = f"Số tiền chuyển khoản {transfer_amount:,} đ không đủ cho đơn hàng {order.order_code} ({expected_amount:,} đ, thiếu {shortage:,} đ)."
            logger.warning(f"[SEPAY WEBHOOK] {err_msg}")
            inbound_rec = SepayInboundTransaction(
                sepay_id=sepay_id,
                gateway=gateway,
                account_number=account_number,
                transfer_type=transfer_type,
                transfer_amount=transfer_amount,
                accumulated=accumulated,
                code=matched_code,
                content=content,
                reference_code=ref_code,
                description=description,
                transaction_date=trans_date,
                status="FLAGGED_UNDERPAID",
                order_id=order.id,
                error_message=err_msg,
                raw_payload=raw_payload_str,
            )
            db.add(inbound_rec)
            webhook_log.process_error = err_msg
            db.commit()

            dispatch_alert(
                title="CẢNH BÁO SEPAY: KHÁCH CHUYỂN THIẾU TIỀN",
                message=(
                    f"Đơn hàng: <b>{order.order_code}</b> (Mã TT: <code>{matched_code}</code>)\n"
                    f"Số tiền yêu cầu: <b>{expected_amount:,} đ</b>\n"
                    f"Số tiền thực nhận: <b>{transfer_amount:,} đ</b>\n"
                    f"Số tiền còn thiếu: <b>{shortage:,} đ</b>\n"
                    f"Trạng thái: <b>Đã đưa vào đối soát thủ công (KHÔNG tự động PAID)</b>"
                ),
                severity="HIGH",
                alert_type="SEPAY_UNDERPAID",
            )
            return {
                "success": False,
                "message": err_msg,
                "order_code": order.order_code,
                "sepay_id": sepay_id,
            }

        if transfer_amount > expected_amount:
            surplus = transfer_amount - expected_amount
            err_msg = f"Số tiền chuyển khoản {transfer_amount:,} đ vượt quá giá trị đơn hàng {order.order_code} ({expected_amount:,} đ, dư {surplus:,} đ)."
            logger.warning(f"[SEPAY WEBHOOK] {err_msg}")
            inbound_rec = SepayInboundTransaction(
                sepay_id=sepay_id,
                gateway=gateway,
                account_number=account_number,
                transfer_type=transfer_type,
                transfer_amount=transfer_amount,
                accumulated=accumulated,
                code=matched_code,
                content=content,
                reference_code=ref_code,
                description=description,
                transaction_date=trans_date,
                status="FLAGGED_OVERPAID",
                order_id=order.id,
                error_message=err_msg,
                raw_payload=raw_payload_str,
            )
            db.add(inbound_rec)
            webhook_log.process_error = err_msg
            db.commit()

            dispatch_alert(
                title="CẢNH BÁO SEPAY: KHÁCH CHUYỂN DƯ TIỀN",
                message=(
                    f"Đơn hàng: <b>{order.order_code}</b> (Mã TT: <code>{matched_code}</code>)\n"
                    f"Số tiền yêu cầu: <b>{expected_amount:,} đ</b>\n"
                    f"Số tiền thực nhận: <b>{transfer_amount:,} đ</b>\n"
                    f"Số tiền chuyển dư: <b>{surplus:,} đ</b>\n"
                    f"Trạng thái: <b>Đã đưa vào đối soát kế toán (KHÔNG tự động duyệt)</b>"
                ),
                severity="WARNING",
                alert_type="SEPAY_OVERPAID",
            )
            return {
                "success": False,
                "message": err_msg,
                "order_code": order.order_code,
                "sepay_id": sepay_id,
            }

        # 12. Khớp chính xác 100% số tiền -> XÁC NHẬN THANH TOÁN THÀNH CÔNG
        order.payment_status = "PAID"
        order.order_status = "CONFIRMED"
        order.fulfillment_status = "UNFULFILLED"
        order.payment_method = "SEPAY"

        # Cập nhật PaymentTransaction
        trans = db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.order_id == order.id,
                PaymentTransaction.provider == "SEPAY",
            )
        )
        if not trans:
            trans = PaymentTransaction(
                order_id=order.id,
                transaction_code=f"TXN-SEPAY-{order.order_code}-{int(datetime.now().timestamp()) % 100000}",
                provider="SEPAY",
                amount=Decimal(str(transfer_amount)),
                currency="VND",
                status="SUCCESS",
                provider_trans_id=str(sepay_id),
            )
            db.add(trans)
        else:
            trans.status = "SUCCESS"
            trans.provider_trans_id = str(sepay_id)
            trans.amount = Decimal(str(transfer_amount))

        # Ghi bản ghi Inbound Transaction thành công
        inbound_rec = SepayInboundTransaction(
            sepay_id=sepay_id,
            gateway=gateway,
            account_number=account_number,
            transfer_type=transfer_type,
            transfer_amount=transfer_amount,
            accumulated=accumulated,
            code=matched_code,
            content=content,
            reference_code=ref_code,
            description=description,
            transaction_date=trans_date,
            status="PROCESSED",
            order_id=order.id,
            error_message=None,
            raw_payload=raw_payload_str,
        )
        db.add(inbound_rec)

        webhook_log.processed = True
        db.commit()

        # Bắn thông báo Admin & Kho dược
        dispatch_alert(
            title="THANH TOÁN SEPAY VIETQR THÀNH CÔNG",
            message=(
                f"Đơn hàng: <b>{order.order_code}</b>\n"
                f"Mã thanh toán: <code>{matched_code}</code>\n"
                f"Số tiền: <b>{transfer_amount:,} đ</b>\n"
                f"Cổng nhận: <b>MBBank (SePay #{sepay_id})</b>\n"
                f"Trạng thái: <b>ĐÃ THANH TOÁN (PAID) - Đã mở khóa cho kho soạn hàng</b>"
            ),
            severity="INFO",
            alert_type="SEPAY_PAID",
        )

        logger.info(
            f"[SEPAY WEBHOOK THÀNH CÔNG] Đơn {order.order_code} đã thanh toán thành công {transfer_amount:,} đ qua SePay #{sepay_id}."
        )

        return {
            "success": True,
            "message": f"Xác nhận thanh toán đơn hàng {order.order_code} thành công.",
            "order_code": order.order_code,
            "payment_code": matched_code,
            "amount": transfer_amount,
            "sepay_id": sepay_id,
        }
