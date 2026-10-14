import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import html
import logging
import smtplib
import socket
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Order, OrderItem
from app.models.inventory import (
    EmailOutbox,
    FulfillmentItem,
    InventoryBatch,
    OrderFulfillment,
    OrderItemBatchAllocation,
    Warehouse,
)

logger = logging.getLogger(__name__)


class EmailErrorCode:
    NOT_CONFIGURED = "EMAIL_PROVIDER_NOT_CONFIGURED"
    DNS_RESOLUTION_FAILED = "DNS_RESOLUTION_FAILED"
    CONNECTION_TIMEOUT = "SMTP_CONNECTION_TIMEOUT"
    AUTH_FAILED = "SMTP_AUTHENTICATION_FAILED"
    SSL_TLS_CONFLICT = "SMTP_SSL_TLS_CONFLICT"
    CONNECTION_REFUSED = "SMTP_CONNECTION_REFUSED"
    INVALID_RECIPIENT = "INVALID_RECIPIENT_EMAIL"
    RETRY_EXCEEDED = "RETRY_EXCEEDED"
    SEND_FAILED = "SMTP_SEND_FAILED"


class EmailService:
    @classmethod
    def classify_smtp_error(cls, e: Exception) -> tuple[str, bool, str]:
        """
        Phân loại lỗi SMTP chính xác, loại bỏ thông tin nhạy cảm.
        Trả về tuple: (error_code, is_retryable, sanitized_message)
        """
        raw_msg = str(e)
        if isinstance(e, ValueError) and ("Chưa cấu hình tài khoản SMTP" in raw_msg or "vô hiệu hóa" in raw_msg):
            return (EmailErrorCode.NOT_CONFIGURED, False, "Chưa cấu hình tài khoản SMTP trong biến môi trường (.env) hoặc dịch vụ đang bị vô hiệu hóa.")

        if isinstance(e, ValueError) and "xung đột" in raw_msg:
            return (EmailErrorCode.SSL_TLS_CONFLICT, False, "Cấu hình SMTP_SSL và SMTP_TLS đang bị xung đột (không thể bật cả hai).")

        if isinstance(e, socket.gaierror):
            return (
                EmailErrorCode.DNS_RESOLUTION_FAILED,
                True,
                f"Không thể phân giải tên miền máy chủ SMTP '{settings.smtp_host}' ([Errno {e.errno or 11001}] getaddrinfo failed).",
            )

        if isinstance(e, (TimeoutError, socket.timeout)):
            return (EmailErrorCode.CONNECTION_TIMEOUT, True, "Kết nối tới máy chủ SMTP bị quá thời gian (Connection Timeout).")

        if isinstance(e, smtplib.SMTPAuthenticationError):
            return (EmailErrorCode.AUTH_FAILED, False, "Xác thực tài khoản SMTP thất bại (Sai username hoặc App Password).")

        if isinstance(e, smtplib.SMTPRecipientsRefused):
            return (EmailErrorCode.INVALID_RECIPIENT, False, "Địa chỉ email người nhận bị máy chủ SMTP từ chối.")

        if isinstance(e, (ConnectionRefusedError, smtplib.SMTPConnectError)):
            return (EmailErrorCode.CONNECTION_REFUSED, True, "Máy chủ SMTP từ chối kết nối hoặc không phản hồi.")

        # Khử secret trong thông điệp lỗi trước khi lưu vết
        clean_msg = raw_msg
        if settings.smtp_password and settings.smtp_password in clean_msg:
            clean_msg = clean_msg.replace(settings.smtp_password, "********")

        return (EmailErrorCode.SEND_FAILED, True, f"Lỗi gửi email SMTP: {clean_msg}")

    @classmethod
    def build_order_confirmation_html(
        cls,
        db: Session,
        order: Order,
    ) -> Tuple[str, str, str]:
        """
        Sinh nội dung email xác nhận đơn hàng chuẩn HTML cho H4CARE / PharmaTrust.
        Hiển thị chi tiết thuốc, kiện hàng phân bổ theo kho, và số lô + hạn dùng (FEFO).
        Bảo mật: Toàn bộ dữ liệu khách hàng và sản phẩm được escape an toàn bằng html.escape.
        Trả về tuple: (subject, body_html, body_text)
        """
        safe_order_code = html.escape(order.order_code or "")
        safe_customer_name = html.escape(order.customer_name or "Quý khách")
        safe_customer_phone = html.escape(order.customer_phone or "Chưa cung cấp")
        safe_shipping_addr = html.escape(f"{order.shipping_address or ''}, {order.shipping_city or ''}".strip(", "))

        subject = f"[H4CARE] Xác nhận đơn hàng dược phẩm #{order.order_code}"
        created_str = (
            order.created_at.strftime("%d/%m/%Y %H:%M")
            if order.created_at
            else datetime.now().strftime("%d/%m/%Y %H:%M")
        )

        payment_label = {
            "COD": "Thanh toán khi nhận hàng (COD)",
            "MOMO": "Ví điện tử MoMo Sandbox",
            "BANK_TRANSFER": "Chuyển khoản ngân hàng VietQR",
        }.get(order.payment_method.upper(), order.payment_method)

        if order.payment_status == "PAID":
            payment_status_badge = '<span style="display:inline-block;padding:3px 8px;border-radius:4px;font-size:12px;font-weight:700;background:#dcfce7;color:#15803d;">✓ ĐÃ THANH TOÁN (Trực tuyến)</span>'
        elif order.payment_method.upper() == "COD":
            payment_status_badge = '<span style="display:inline-block;padding:3px 8px;border-radius:4px;font-size:12px;font-weight:700;background:#fef3c7;color:#b45309;">⏳ CHƯA THANH TOÁN (Thu tiền khi nhận hàng COD)</span>'
        else:
            payment_status_badge = '<span style="display:inline-block;padding:3px 8px;border-radius:4px;font-size:12px;font-weight:700;background:#fef3c7;color:#b45309;">⏳ CHỜ THANH TOÁN</span>'

        # 1. Truy vấn các kiện hàng (Fulfillments) và phân bổ Lô (FEFO allocations)
        fulfillments = db.scalars(
            select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)
        ).all()

        allocations = db.scalars(
            select(OrderItemBatchAllocation)
            .join(OrderItem, OrderItemBatchAllocation.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order.id)
        ).all()

        alloc_map: dict[int, list[OrderItemBatchAllocation]] = {}
        for alloc in allocations:
            alloc_map.setdefault(alloc.order_item_id, []).append(alloc)

        # 2. Xây dựng bảng thuốc (HTML Escaped)
        items_rows_html = ""
        items_text_list = []
        for item in order.items:
            unit_price_fmt = f"{item.price:,.0f} đ".replace(",", ".")
            subtotal_fmt = f"{item.subtotal:,.0f} đ".replace(",", ".")
            safe_prod_name = html.escape(item.product_name or "")
            safe_sku = html.escape(item.product_sku or "N/A")

            # Tìm danh sách lô FEFO cấp cho sản phẩm này
            item_allocs = alloc_map.get(item.id, [])
            batch_badges_html = ""
            batch_text_desc = ""
            if item_allocs:
                badges = []
                for a in item_allocs:
                    batch = a.batch
                    wh = a.warehouse
                    exp_str = batch.expiry_date.strftime("%d/%m/%Y") if batch.expiry_date else "N/A"
                    wh_code = html.escape(getattr(wh, "code", None) or getattr(wh, "warehouse_code", "") if wh else "")
                    badges.append(
                        f'<div style="font-size:11px;color:#0284c7;background:#f0f9ff;border:1px solid #bae6fd;border-radius:4px;padding:2px 6px;margin-top:3px;display:inline-block;">'
                        f'Lô: <b>{html.escape(batch.batch_number)}</b> (HSD: {exp_str}) | Kho: <b>{wh_code}</b> x {a.allocated_quantity}'
                        f'</div>'
                    )
                batch_badges_html = "".join(badges)
                batch_text_desc = f" [Lô: {', '.join([f'{a.batch.batch_number} (HSD: {a.batch.expiry_date})' for a in item_allocs])}]"

            items_rows_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="padding: 10px 12px; font-size: 13px; color: #1e293b;">
                <strong>{safe_prod_name}</strong>
                <div style="font-size: 11px; color: #64748b;">Mã SKU/SĐK: {safe_sku}</div>
                {batch_badges_html}
              </td>
              <td style="padding: 10px 12px; text-align: center; font-size: 13px; color: #334155;">{item.quantity}</td>
              <td style="padding: 10px 12px; text-align: right; font-size: 13px; color: #334155;">{unit_price_fmt}</td>
              <td style="padding: 10px 12px; text-align: right; font-size: 13px; font-weight: 700; color: #0f172a;">{subtotal_fmt}</td>
            </tr>
            """
            items_text_list.append(f"- {item.product_name} x {item.quantity} ({unit_price_fmt}) = {subtotal_fmt}{batch_text_desc}")

        # 3. Thông tin kiện hàng tách theo kho
        fulfillment_section_html = ""
        if fulfillments:
            fulfillment_blocks = []
            for f in fulfillments:
                wh = f.warehouse
                wh_name = html.escape(getattr(wh, "name", None) or getattr(wh, "warehouse_name", "Kho chính") if wh else "Kho chính")
                wh_code = html.escape(getattr(wh, "code", None) or getattr(wh, "warehouse_code", "") if wh else "")
                fulfillment_blocks.append(f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 12px;">
                  <div style="display: flex; justify-content: space-between; font-weight: 700; color: #1e40af;">
                    <span>Kiện hàng: {html.escape(f.fulfillment_code)}</span>
                    <span style="color: #0369a1;">Kho xuất: {wh_code} ({wh_name})</span>
                  </div>
                  <div style="color: #64748b; font-size: 11px; margin-top: 2px;">
                    Trạng thái điều phối: <b>{html.escape(f.status)}</b> | Đơn vị vận chuyển: {html.escape(f.carrier_name or 'Nội bộ H4CARE GSP Express')}
                  </div>
                </div>
                """)
            fulfillment_section_html = f"""
            <div style="margin-top: 18px;">
              <h4 style="margin: 0 0 8px; font-size: 13px; color: #334155; text-transform: uppercase; letter-spacing: 0.05em;">Chi tiết Kiện hàng & Xuất kho Đa Chi nhánh</h4>
              {''.join(fulfillment_blocks)}
            </div>
            """

        total_fmt = f"{order.total_amount:,.0f} đ".replace(",", ".")
        shipping_fmt = f"{order.shipping_fee:,.0f} đ".replace(",", ".") if order.shipping_fee > 0 else "Miễn phí"

        # 4. Giao diện HTML Template
        body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Xác nhận đơn hàng H4CARE</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 24px 0;">
    <tr>
      <td align="center">
        <table width="640" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
          <!-- HEADER -->
          <tr>
            <td style="background: linear-gradient(135deg, #1e40af 0%, #0284c7 100%); padding: 24px 28px; text-align: left;">
              <table width="100%">
                <tr>
                  <td>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: -0.02em;">
                      H4CARE <span style="font-weight: 400; font-size: 16px; opacity: 0.9;">| Hệ Thống Nhà Thuốc Chuẩn GPP</span>
                    </h1>
                    <p style="margin: 4px 0 0; font-size: 12px; color: #e0f2fe;">Hệ thống Thương mại Dược phẩm & Quản lý Kho Chuẩn GSP</p>
                  </td>
                  <td align="right">
                    <div style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 700; color: #ffffff;">
                      ĐƠN HÀNG MỚI
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="padding: 24px 28px;">
              <h2 style="margin: 0 0 12px; font-size: 18px; color: #0f172a;">Xác nhận đơn đặt thuốc thành công</h2>
              <p style="margin: 0 0 18px; font-size: 14px; line-height: 1.5; color: #475569;">
                Kính chào <b>{safe_customer_name}</b>,<br>
                Cảm ơn quý khách đã tin chọn Nhà thuốc <b>H4CARE</b>. Đơn hàng của quý khách đã được tiếp nhận vào hệ thống điều phối đa kho và đang được Dược sĩ phụ trách phân bổ theo tiêu chuẩn FEFO (Hạn dùng gần nhất xuất trước).
              </p>

              <!-- SUMMARY BOX -->
              <table width="100%" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; margin-bottom: 20px; font-size: 13px;">
                <tr>
                  <td width="50%" style="padding: 4px 8px; vertical-align: top;">
                    <div style="color: #64748b; font-size: 11px;">MÃ ĐƠN HÀNG:</div>
                    <div style="font-family: monospace; font-size: 15px; font-weight: 800; color: #0284c7; margin-top: 2px;">{safe_order_code}</div>
                  </td>
                  <td width="50%" style="padding: 4px 8px; vertical-align: top;">
                    <div style="color: #64748b; font-size: 11px;">THỜI GIAN ĐẶT:</div>
                    <div style="font-weight: 600; color: #1e293b; margin-top: 2px;">{created_str}</div>
                  </td>
                </tr>
                <tr>
                  <td width="50%" style="padding: 6px 8px 4px; vertical-align: top;">
                    <div style="color: #64748b; font-size: 11px;">NGƯỜI NHẬN & SĐT:</div>
                    <div style="font-weight: 600; color: #1e293b; margin-top: 2px;">{safe_customer_name} - {safe_customer_phone}</div>
                  </td>
                  <td width="50%" style="padding: 6px 8px 4px; vertical-align: top;">
                    <div style="color: #64748b; font-size: 11px;">PHƯƠNG THỨC THANH TOÁN:</div>
                    <div style="font-weight: 600; color: #1e293b; margin-top: 2px;">{payment_label} {payment_status_badge}</div>
                  </td>
                </tr>
                <tr>
                  <td colspan="2" style="padding: 6px 8px 4px; border-top: 1px solid #e2e8f0; margin-top: 6px;">
                    <div style="color: #64748b; font-size: 11px;">ĐỊA CHỈ NHẬN HÀNG:</div>
                    <div style="font-weight: 600; color: #0f172a; margin-top: 2px;">{safe_shipping_addr}</div>
                  </td>
                </tr>
              </table>

              <!-- ORDER ITEMS TABLE -->
              <h3 style="margin: 18px 0 10px; font-size: 14px; font-weight: 700; color: #1e293b; text-transform: uppercase; letter-spacing: 0.05em;">Danh mục sản phẩm thuốc đã đặt</h3>
              <table width="100%" cellspacing="0" cellpadding="0" style="border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-bottom: 16px;">
                <thead>
                  <tr style="background-color: #f1f5f9; border-bottom: 1px solid #e2e8f0;">
                    <th style="padding: 10px 12px; text-align: left; font-size: 12px; color: #475569; font-weight: 700;">Tên Thuốc / Dược phẩm</th>
                    <th style="padding: 10px 12px; text-align: center; font-size: 12px; color: #475569; font-weight: 700; width: 60px;">SL</th>
                    <th style="padding: 10px 12px; text-align: right; font-size: 12px; color: #475569; font-weight: 700; width: 90px;">Đơn giá</th>
                    <th style="padding: 10px 12px; text-align: right; font-size: 12px; color: #475569; font-weight: 700; width: 100px;">Thành tiền</th>
                  </tr>
                </thead>
                <tbody>
                  {items_rows_html}
                </tbody>
              </table>

              <!-- MULTI-WAREHOUSE FULFILLMENT BREAKDOWN -->
              {fulfillment_section_html}

              <!-- TOTAL CALCULATION -->
              <table width="100%" style="margin-top: 14px; font-size: 13px;">
                <tr>
                  <td align="right" style="padding: 4px 0; color: #64748b;">Phí vận chuyển chuẩn GSP:</td>
                  <td align="right" width="130" style="padding: 4px 0; font-weight: 600; color: #1e293b;">{shipping_fmt}</td>
                </tr>
                <tr style="border-top: 2px solid #e2e8f0;">
                  <td align="right" style="padding: 10px 0 4px; font-size: 15px; font-weight: 800; color: #0f172a;">TỔNG THANH TOÁN:</td>
                  <td align="right" width="130" style="padding: 10px 0 4px; font-size: 18px; font-weight: 900; color: #e11d48;">{total_fmt}</td>
                </tr>
              </table>

              <!-- ADVISORY NOTICE -->
              <div style="margin-top: 24px; padding: 14px; background-color: #ecfdf5; border-left: 4px solid #10b981; border-radius: 6px; font-size: 12px; color: #065f46;">
                <b>Lưu ý an toàn y tế từ Dược sĩ H4CARE:</b><br>
                Mọi loại thuốc được xuất kho đều được bảo quản theo chuẩn GSP nhiệt độ dưới 30°C và độ ẩm dưới 75%. Khi nhận hàng, quý khách vui lòng kiểm tra tem niêm phong và đối chiếu số lô in trên bao bì với biên lai này. Mọi thắc mắc về hướng dẫn sử dụng hoặc phản ứng phụ, xin liên hệ bộ phận hỗ trợ khách hàng: <b>support@pharmatrust.vn</b>.
              </div>

              <!-- LEGAL DISCLAIMER -->
              <div style="margin-top: 12px; padding: 10px 14px; background-color: #f8fafc; border-left: 4px solid #94a3b8; border-radius: 6px; font-size: 11px; color: #64748b;">
                <b>Lưu ý pháp lý:</b> Email này là thông báo xác nhận tiếp nhận đơn đặt hàng từ hệ thống Storefront H4CARE, không thay thế hóa đơn giá trị gia tăng (GTGT) điện tử. Khách hàng có nhu cầu xuất hóa đơn tài chính doanh nghiệp vui lòng đăng ký thông tin hợp lệ tại bước thanh toán.
              </div>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 18px 28px; text-align: center; font-size: 11px; color: #64748b; line-height: 1.6;">
              Email này được tạo tự động bởi Hệ thống H4CARE & PharmaTrust Data Hub.<br>
              Vui lòng không trả lời trực tiếp email này. Mọi phản hồi xin gửi về <b>support@pharmatrust.vn</b>.<br>
              © 2026 H4CARE. Bảo lưu mọi quyền.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        # 5. Fallback Plain-text version
        body_text = f"""
XÁC NHẬN ĐƠN HÀNG DƯỢC PHẨM - H4CARE / PHARMATRUST
Mã đơn hàng: {order.order_code}
Thời gian: {created_str}
Khách hàng: {order.customer_name} ({order.customer_phone})
Địa chỉ giao hàng: {order.shipping_address}, {order.shipping_city}
Phương thức thanh toán: {payment_label} [{order.payment_status}]

DANH SÁCH THUỐC ĐÃ ĐẶT:
{chr(10).join(items_text_list)}

Phí vận chuyển: {shipping_fmt}
TỔNG THANH TOÁN: {total_fmt}

Đơn thuốc được bảo quản và phân bổ tự động theo chuẩn FEFO tại hệ thống kho H4CARE GSP.
Liên hệ Dược sĩ hỗ trợ: support@pharmatrust.vn
(Lưu ý: Email này là xác nhận đơn đặt hàng, không phải hóa đơn điện tử GTGT).
        """.strip()

        return subject, body_html, body_text

    @classmethod
    def send_smtp_email(
        cls,
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> bool:
        """
        Thực hiện kết nối và gửi email thật qua giao thức SMTP (Gmail hoặc SMTP Server chỉ định).
        Nếu chưa cấu hình tài khoản SMTP (SMTP_USER hoặc SMTP_PASSWORD) trong .env,
        báo lỗi nghiêm ngặt theo đúng chuẩn kỹ thuật (Strict Mode).
        """
        if not settings.smtp_enabled:
            raise ValueError("Dịch vụ gửi email SMTP hiện đang bị vô hiệu hóa bởi cấu hình (SMTP_ENABLED=false).")

        if settings.smtp_ssl and settings.smtp_tls:
            raise ValueError("Cấu hình SMTP_SSL và SMTP_TLS đang bị xung đột (không thể bật đồng thời cả hai).")

        if not settings.smtp_user or not settings.smtp_user.strip() or not settings.smtp_password or not settings.smtp_password.strip():
            raise ValueError(
                "Chưa cấu hình tài khoản SMTP (SMTP_USER hoặc SMTP_PASSWORD) trong biến môi trường (.env). "
                "Vui lòng thiết lập tài khoản Gmail và Mật khẩu ứng dụng (App Password) để gửi email thật."
            )

        if not recipient_email or "@" not in recipient_email:
            raise ValueError(f"Địa chỉ email người nhận không hợp lệ: '{recipient_email}'")

        sender_email = settings.smtp_user.strip()
        sender_name = settings.smtp_from_name.strip() or "H4CARE Pharmacy"
        formatted_from = email.utils.formataddr((sender_name, sender_email))

        # Khởi tạo MIME Message
        msg = MIMEMultipart("alternative")
        msg["From"] = formatted_from
        msg["To"] = recipient_email.strip()
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # Kết nối SMTP với timeout hữu hạn 5 giây
        timeout_seconds = 5.0
        if settings.smtp_ssl:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=timeout_seconds)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout_seconds)
            if settings.smtp_tls:
                server.starttls()

        try:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(sender_email, [recipient_email.strip()], msg.as_string())
            logger.info(f"[EMAIL] Đã gửi thành công email tới '{recipient_email}' (Subject: {subject})")
            return True
        finally:
            try:
                server.quit()
            except Exception:
                pass

    @classmethod
    def queue_and_send_order_confirmation(
        cls,
        db: Session,
        order: Order,
        send_immediately: bool = True,
    ) -> Optional[EmailOutbox]:
        """
        Ghi nhận bản ghi email vào bảng email_outboxes và tiến hành gửi email tới khách hàng.
        - Chống gửi trùng lặp nếu đơn hàng đã được gửi thành công.
        - Phân loại lỗi và lưu vết chi tiết vào last_error.
        """
        if not order.customer_email or not order.customer_email.strip():
            logger.info(f"[EMAIL] Đơn hàng '{order.order_code}' không có email nhận, bỏ qua gửi email.")
            return None

        # 1. Chống gửi trùng lặp nếu đơn hàng đã có bản ghi EmailOutbox được gửi thành công
        existing_sent = db.scalar(
            select(EmailOutbox).where(
                EmailOutbox.reference_type == "ORDER_CONFIRMATION",
                EmailOutbox.reference_id == order.order_code,
                EmailOutbox.status == "SENT",
            )
        )
        if existing_sent:
            logger.info(f"[EMAIL] Đơn hàng '{order.order_code}' đã được gửi email xác nhận trước đó (Outbox #{existing_sent.id}), bỏ qua gửi trùng.")
            return existing_sent

        subject, body_html, body_text = cls.build_order_confirmation_html(db=db, order=order)

        outbox = EmailOutbox(
            recipient_email=order.customer_email.strip(),
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            reference_type="ORDER_CONFIRMATION",
            reference_id=order.order_code,
            status="PENDING",
            retry_count=0,
            max_retries=3,
        )
        db.add(outbox)
        db.flush()

        if send_immediately:
            try:
                cls.send_smtp_email(
                    recipient_email=outbox.recipient_email,
                    subject=outbox.subject,
                    body_html=outbox.body_html,
                    body_text=outbox.body_text,
                )
                outbox.status = "SENT"
                outbox.sent_at = datetime.now(timezone.utc)
                outbox.last_error = None
            except Exception as e:
                err_code, is_retryable, sanitized_msg = cls.classify_smtp_error(e)
                logger.warning(f"[EMAIL] Gửi email thất bại cho đơn '{order.order_code}' [{err_code}]: {sanitized_msg}")
                outbox.status = "FAILED"
                outbox.last_error = f"[{err_code}] {sanitized_msg}"
                outbox.retry_count += 1

        db.commit()
        db.refresh(outbox)
        return outbox

    @classmethod
    def resend_email(cls, db: Session, outbox_id: int) -> EmailOutbox:
        """
        Gửi lại một bức thư trong hàng đợi email_outboxes (Retry).
        Kiểm tra số lần thử tối đa và phân loại lỗi rõ ràng.
        """
        outbox = db.scalar(select(EmailOutbox).where(EmailOutbox.id == outbox_id))
        if not outbox:
            raise ValueError(f"Không tìm thấy bản ghi email outbox #{outbox_id}")

        if outbox.status == "SENT":
            logger.info(f"[EMAIL] Outbox #{outbox_id} đã được gửi thành công trước đó, không gửi lại.")
            return outbox

        if outbox.retry_count >= outbox.max_retries:
            outbox.status = "FAILED"
            outbox.last_error = f"[{EmailErrorCode.RETRY_EXCEEDED}] Đã vượt quá số lần thử gửi lại tối đa ({outbox.max_retries} lần)."
            db.commit()
            raise ValueError(f"Email #{outbox_id} đã vượt quá số lần thử tối đa ({outbox.max_retries}).")

        outbox.retry_count += 1
        try:
            cls.send_smtp_email(
                recipient_email=outbox.recipient_email,
                subject=outbox.subject,
                body_html=outbox.body_html,
                body_text=outbox.body_text,
            )
            outbox.status = "SENT"
            outbox.sent_at = datetime.now(timezone.utc)
            outbox.last_error = None
        except Exception as e:
            err_code, is_retryable, sanitized_msg = cls.classify_smtp_error(e)
            outbox.status = "FAILED"
            outbox.last_error = f"[{err_code}] {sanitized_msg}"
            raise e
        finally:
            db.commit()
            db.refresh(outbox)

        return outbox
