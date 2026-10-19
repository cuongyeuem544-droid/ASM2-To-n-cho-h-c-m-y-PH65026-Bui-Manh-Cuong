from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user, require_roles
from app.core.config import settings
from app.core.security import verify_guest_order_token
from app.db.session import get_db
from app.models import Order, PaymentTransaction, User
from app.models.enums import UserRole
from app.services.audit import write_audit
from app.services.fulfillment_service import FulfillmentRoutingService
from app.services.momo_service import MomoPaymentService
from app.services.payos_service import PayOSPaymentService
from app.services.payment_intent_service import PaymentIntentService
from app.services.reconciliation_service import PaymentReconciliationService
from app.services.vietqr_service import VietQrService

payments_router = APIRouter(prefix="/payments", tags=["Cổng thanh toán & Đối soát H4CARE"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class CreateMomoPaymentRequest(BaseModel):
    order_code: str = Field(..., min_length=5, max_length=50)
    return_url: Optional[str] = None
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


class CreatePayOSPaymentRequest(BaseModel):
    order_code: str = Field(..., min_length=5, max_length=50)
    return_url: Optional[str] = None
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


class ConfirmPayOSWebhookRequest(BaseModel):
    webhook_url: str = Field(..., min_length=10, max_length=255)


class SimulatePaymentRequest(BaseModel):
    order_code: str = Field(..., min_length=5, max_length=50)
    success: bool = True


class CreateVietQrPaymentRequest(BaseModel):
    order_code: str = Field(..., min_length=5, max_length=50)
    return_url: Optional[str] = None
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


class SimulateVietQrRequest(BaseModel):
    code: str = Field(..., min_length=5, max_length=50)
    success: bool = True
    amount: Optional[int] = None


class CreatePaymentIntentRequest(BaseModel):
    order_code: str = Field(..., min_length=5, max_length=50)
    payment_method: str = Field(default="COD")
    return_url: Optional[str] = None
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


class RetryPaymentRequest(BaseModel):
    order_code: str = Field(..., min_length=5, max_length=50)
    new_payment_method: str = Field(..., min_length=2, max_length=30)
    return_url: Optional[str] = None
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


class CreateExchangeIntentRequest(BaseModel):
    exchange_code: str = Field(..., min_length=5, max_length=50)
    payment_method: str = Field(default="VIETQR")
    return_url: Optional[str] = None
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


class SimulateExchangePaymentRequest(BaseModel):
    exchange_code: str = Field(..., min_length=5, max_length=50)
    success: bool = True
    amount: Optional[int] = None


class CancelOrderRequest(BaseModel):
    reason: Optional[str] = "Khách hàng yêu cầu hủy đơn hàng"
    phone_verify: Optional[str] = None
    order_token: Optional[str] = None


# ==============================================================================
# SECURITY HELPERS (Fail-Closed Simulation & Order Ownership Verification)
# ==============================================================================

def _assert_simulation_allowed() -> None:
    """
    Cơ chế Fail-Closed: Chỉ cho phép mô phỏng thanh toán khi:
    - app_env thuộc nhóm ['development', 'dev', 'test', 'local']
    - enable_payment_simulator được bật tường minh là True.
    Mọi trường hợp khác (production, staging, public, hoặc cấu hình sai/thiếu):
    chặn lập tức với HTTP 403 Forbidden.
    """
    if not getattr(settings, "is_simulator_permitted", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chức năng mô phỏng thanh toán bị vô hiệu hóa hoàn toàn trên môi trường công khai / production.",
        )


def _verify_order_payment_access(
    order: Order,
    current_user: Optional[User],
    phone_verify: Optional[str] = None,
    order_token: Optional[str] = None,
    action_name: str = "thao tác trên đơn hàng",
) -> None:
    """
    Xác thực quyền thao tác trên đơn hàng cho các tác vụ thanh toán/hủy đơn (Anti-IDOR).
    - Nhân viên (ADMIN, PHARMACIST, DATA_REVIEWER): Toàn quyền.
    - Khách hàng đã đăng nhập (CUSTOMER): Chỉ thao tác trên đơn của chính mình (order.user_id == current_user.id).
    - Khách vãng lai: Bắt buộc cung cấp token đơn hàng hợp lệ (order_token/guest_access_token).
      Số điện thoại không phải là bằng chứng duy nhất để cấp quyền thao tác.
    """
    is_staff = current_user and getattr(current_user, "role", "") in [UserRole.ADMIN, UserRole.PHARMACIST, UserRole.WAREHOUSE_MANAGER]
    if is_staff:
        return

    is_token_valid = verify_guest_order_token(order_token, order.order_code)

    if current_user and getattr(current_user, "role", "") == "CUSTOMER":
        if order.user_id is not None and order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bạn không có quyền {action_name} này.",
            )
        if order.user_id is None:
            clean_user_phone = (current_user.phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")
            clean_order_phone = (order.customer_phone or "").strip().replace(" ", "").replace(".", "").replace("-", "")
            if clean_user_phone != clean_order_phone and not is_token_valid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Bạn không có quyền {action_name} này.",
                )
    else:
        # Khách vãng lai chưa đăng nhập: Yêu cầu token ký điện tử hợp lệ
        if not is_token_valid:
            if phone_verify:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Số điện thoại không phải là bằng chứng duy nhất để xác thực quyền sở hữu đơn. Vui lòng cung cấp token đơn hàng hợp lệ (order_token) để {action_name}.",
                )
            if not order_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Vui lòng đăng nhập hoặc cung cấp token đơn hàng hợp lệ để {action_name}.",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token đơn hàng không hợp lệ hoặc đã hết hạn để {action_name}.",
            )


# ==============================================================================
# 1. MOMO SANDBOX GATEWAY ENDPOINTS (Backward Compatible)
# ==============================================================================

@payments_router.post("/momo/create")
def create_momo_payment(
    payload: CreateMomoPaymentRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Khởi tạo yêu cầu thanh toán MoMo Sandbox cho đơn hàng.
    Trả về payUrl và qrCodeUrl để người mua quét mã thanh toán.
    """
    order = db.scalar(select(Order).where(Order.order_code == payload.order_code.strip()))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{payload.order_code}'")

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=payload.phone_verify,
        order_token=payload.order_token,
        action_name="tạo thanh toán MoMo",
    )

    if order.payment_status == "PAID":
        raise HTTPException(status_code=400, detail="Đơn hàng này đã được thanh toán thành công trước đó.")

    res = MomoPaymentService.create_payment_request(
        db=db,
        order=order,
        return_url=payload.return_url,
    )
    return res


@payments_router.post("/momo/webhook")
async def momo_ipn_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Endpoint tiếp nhận thông báo tức thì (IPN Webhook) từ Cổng thanh toán MoMo.
    Kiểm tra chữ ký số HMAC-SHA256, tự động cập nhật trạng thái đơn sang ĐÃ THANH TOÁN (PAID) và gửi cảnh báo.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload không đúng định dạng JSON.")

    result = MomoPaymentService.process_ipn_callback(db=db, payload=payload)
    return result


@payments_router.post("/momo/simulate")
def simulate_momo_payment(
    payload: SimulatePaymentRequest,
    db: Session = Depends(get_db),
):
    """
    [MÔI TRƯỜNG DEV/DEMO] Mô phỏng quét mã thanh toán MoMo thành công trực tiếp trên máy chủ cục bộ.
    Vô hiệu hóa tuyệt đối trên môi trường production/public (Fail-Closed).
    """
    _assert_simulation_allowed()
    return MomoPaymentService.simulate_payment(
        db=db,
        order_code=payload.order_code.strip(),
        success=payload.success,
    )


# ==============================================================================
# 2. VIETQR (NAPAS 247) GATEWAY ENDPOINTS
# ==============================================================================

@payments_router.post("/vietqr/create")
def create_vietqr_payment(
    payload: CreateVietQrPaymentRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Khởi tạo mã VietQR Napas 247 cho đơn hàng mua thuốc.
    Mã QR được mã hóa sẵn ngân hàng thụ hưởng, số tài khoản, số tiền và mã đơn.
    """
    order = db.scalar(select(Order).where(Order.order_code == payload.order_code.strip()))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{payload.order_code}'")

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=payload.phone_verify,
        order_token=payload.order_token,
        action_name="tạo mã VietQR",
    )

    return VietQrService.create_payment_request(
        db=db,
        order=order,
        return_url=payload.return_url,
    )


@payments_router.post("/vietqr/webhook")
async def vietqr_bank_webhook(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Endpoint tiếp nhận Webhook biến động số dư chuyển khoản ngân hàng tự động (SePay / Cashtrack / Napas).
    Xác thực token bảo mật, tự động khớp nội dung UNC với mã đơn hàng hoặc đơn đổi hàng.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Dữ liệu Webhook không đúng định dạng JSON.")

    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split("Bearer ")[1].strip()
    elif x_api_key:
        auth_token = x_api_key.strip()
    elif payload.get("token"):
        auth_token = str(payload.get("token")).strip()

    return VietQrService.process_webhook(db=db, payload=payload, auth_token=auth_token)


@payments_router.post("/vietqr/simulate")
def simulate_vietqr_payment(
    payload: SimulateVietQrRequest,
    db: Session = Depends(get_db),
):
    """
    [MÔI TRƯỜNG DEV/DEMO] Giả lập nhận tiền chuyển khoản VietQR thành công trên local.
    Vô hiệu hóa tuyệt đối trên môi trường production/public (Fail-Closed).
    """
    _assert_simulation_allowed()
    return VietQrService.simulate_payment(
        db=db,
        code=payload.code.strip(),
        success=payload.success,
        amount=payload.amount,
    )


# ==============================================================================
# 2.5 PAYOS PAYMENT GATEWAY ENDPOINTS (Chính thức)
# ==============================================================================

@payments_router.post("/payos/create")
def create_payos_payment(
    payload: CreatePayOSPaymentRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Khởi tạo yêu cầu thanh toán qua Cổng payOS (QR Chuyển khoản / Thẻ / Ngân hàng).
    Trả về checkout_url và mã QR động để khách hàng quét và thanh toán tiền thật.
    """
    order = db.scalar(select(Order).where(Order.order_code == payload.order_code.strip()))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{payload.order_code}'")

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=payload.phone_verify,
        order_token=payload.order_token,
        action_name="tạo thanh toán payOS",
    )

    if order.payment_status == "PAID":
        raise HTTPException(status_code=400, detail="Đơn hàng này đã được thanh toán thành công trước đó.")

    return PayOSPaymentService.create_payment_request(
        db=db,
        order=order,
        return_url=payload.return_url,
    )


@payments_router.post("/payos/webhook")
async def payos_payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Endpoint tiếp nhận Webhook biến động thanh toán chính thức từ máy chủ payOS.
    Xác thực chữ ký số HMAC-SHA256 / Checksum chống giả mạo.
    Khi thanh toán thành công (code '00'), tự động:
    - Cập nhật Order.payment_status = PAID.
    - Cập nhật Order.fulfillment_status = ALLOCATED (Đơn chính thức xuất hiện trên danh sách xử lý của Kho & Admin).
    - Gửi thông báo cho nhân viên kho phụ trách đơn.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Dữ liệu Webhook payOS không đúng định dạng JSON.")

    return PayOSPaymentService.process_webhook(db=db, payload=payload)


@payments_router.post("/payos/check/{order_code}")
def check_payos_order_status(
    order_code: str,
    phone_verify: Optional[str] = Query(None),
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Kiểm tra và đồng bộ trạng thái thanh toán trực tiếp từ cổng payOS cho đơn hàng (On-demand sync).
    Chống IDOR: Khách hàng chỉ kiểm tra được đơn của chính mình; Admin toàn quyền.
    """
    clean_code = order_code.strip()
    order = db.scalar(select(Order).where(Order.order_code == clean_code))
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")

    effective_token = x_order_token
    if not effective_token and authorization and authorization.startswith("Bearer "):
        bearer_val = authorization[7:].strip()
        if verify_guest_order_token(bearer_val, clean_code):
            effective_token = bearer_val

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=phone_verify,
        order_token=effective_token,
        action_name="tra cứu trạng thái payOS",
    )

    return PayOSPaymentService.check_payment_status(db=db, order_code=clean_code)


@payments_router.post("/payos/confirm-webhook")
def confirm_payos_webhook_url(
    payload: ConfirmPayOSWebhookRequest,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Đăng ký và xác nhận Webhook URL với máy chủ payOS (Chỉ dành cho ADMIN khi cấu hình Tunnel).
    """
    return PayOSPaymentService.confirm_webhook_url(payload.webhook_url)


# ==============================================================================
# 3. UNIFIED PAYMENT INTENT & RETRY
# ==============================================================================

@payments_router.post("/intent")
def create_payment_intent(
    payload: CreatePaymentIntentRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Khởi tạo Payment Intent hợp nhất:
    Hỗ trợ COD, VietQR Napas 247, và MoMo Sandbox. Trả về thông tin đầy đủ để giao diện hiển thị.
    """
    order = db.scalar(select(Order).where(Order.order_code == payload.order_code.strip()))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{payload.order_code}'")

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=payload.phone_verify,
        order_token=payload.order_token,
        action_name="khởi tạo thanh toán",
    )

    return PaymentIntentService.create_intent(
        db=db,
        order_code=payload.order_code.strip(),
        payment_method=payload.payment_method,
        return_url=payload.return_url,
    )


@payments_router.post("/retry")
def retry_payment(
    payload: RetryPaymentRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Cơ chế Thử lại Thanh toán (Payment Retry) & Chuyển đổi Phương thức thanh toán:
    Hủy an toàn các giao dịch đang treo và tạo Intent mới với phương thức mong muốn.
    """
    order = db.scalar(select(Order).where(Order.order_code == payload.order_code.strip()))
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng '{payload.order_code}'")

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=payload.phone_verify,
        order_token=payload.order_token,
        action_name="thử lại thanh toán",
    )

    return PaymentIntentService.retry_payment(
        db=db,
        order_code=payload.order_code.strip(),
        new_payment_method=payload.new_payment_method,
        return_url=payload.return_url,
    )


# ==============================================================================
# 4. EXCHANGE ORDER ADDITIONAL PAYMENT (Phụ phí đổi hàng)
# ==============================================================================

@payments_router.post("/exchange/intent")
def create_exchange_payment_intent(
    payload: CreateExchangeIntentRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Khởi tạo Payment Intent thu phụ phí chênh lệch cho Đơn đổi hàng (ExchangeOrder).
    """
    from app.models.returns import ExchangeOrder
    clean_code = payload.exchange_code.strip().upper()
    exchange = db.scalar(select(ExchangeOrder).where(ExchangeOrder.exchange_code == clean_code))
    if not exchange:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn đổi hàng '{clean_code}'.")

    orig_order = db.get(Order, exchange.original_order_id)
    if orig_order:
        _verify_order_payment_access(
            orig_order,
            current_user,
            phone_verify=payload.phone_verify,
            order_token=payload.order_token,
            action_name="thanh toán phụ phí đổi hàng",
        )

    return PaymentIntentService.create_exchange_intent(
        db=db,
        exchange_code=clean_code,
        payment_method=payload.payment_method,
        return_url=payload.return_url,
    )


@payments_router.post("/exchange/simulate")
def simulate_exchange_payment(
    payload: SimulateExchangePaymentRequest,
    db: Session = Depends(get_db),
):
    """
    [MÔI TRƯỜNG DEV/DEMO] Mô phỏng khách hàng đã thanh toán phụ phí đổi hàng thành công.
    Vô hiệu hóa tuyệt đối trên môi trường production/public (Fail-Closed).
    """
    _assert_simulation_allowed()
    return VietQrService.simulate_payment(
        db=db,
        code=payload.exchange_code.strip(),
        success=payload.success,
        amount=payload.amount,
    )


# ==============================================================================
# 5. ORDER PAYMENT STATUS & TRANSACTION DETAIL
# ==============================================================================

@payments_router.get("/orders/{order_code}/status")
def get_order_payment_status(
    order_code: str,
    phone_verify: Optional[str] = Query(None, description="Số điện thoại đặt hàng để xác thực"),
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Kiểm tra trạng thái thanh toán hiện tại của đơn hàng, kèm toàn bộ lịch sử giao dịch.
    Hỗ trợ cả mã đơn thường và mã đơn đổi hàng (EXC-).
    Khách hàng chỉ xem được trạng thái đơn của chính mình (chống IDOR).
    ADMIN và nhân viên được xem.
    """
    clean_code = order_code.strip()

    effective_token = x_order_token
    if not effective_token and authorization and authorization.startswith("Bearer "):
        bearer_val = authorization[7:].strip()
        if verify_guest_order_token(bearer_val, clean_code):
            effective_token = bearer_val

    if clean_code.startswith("EXC-"):
        from app.models.returns import ExchangeOrder
        exchange = db.scalar(select(ExchangeOrder).where(ExchangeOrder.exchange_code == clean_code))
        if not exchange:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn đổi hàng.")
        orig_order = db.get(Order, exchange.original_order_id)
        if orig_order:
            _verify_order_payment_access(
                orig_order,
                current_user,
                phone_verify=phone_verify,
                order_token=effective_token,
                action_name="tra cứu thanh toán đổi hàng",
            )
        return PaymentIntentService.get_order_payment_summary(db=db, order_code=clean_code)

    order = db.scalar(select(Order).where(Order.order_code == clean_code))
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=phone_verify,
        order_token=effective_token,
        action_name="tra cứu thanh toán",
    )

    if order.payment_method == "PAYOS" and order.payment_status == "PENDING" and settings.is_payos_configured:
        try:
            PayOSPaymentService.check_payment_status(db, clean_code)
            db.refresh(order)
        except Exception:
            pass

    return PaymentIntentService.get_order_payment_summary(
        db=db,
        order_code=clean_code,
    )


@payments_router.get("/transactions/{transaction_code}/status")
def get_transaction_status(
    transaction_code: str,
    phone_verify: Optional[str] = Query(None),
    x_order_token: Optional[str] = Header(None, alias="X-Order-Token"),
    authorization: Optional[str] = Header(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Tra cứu chi tiết một giao dịch thanh toán theo mã giao dịch duy nhất.
    Yêu cầu truyền token qua Header X-Order-Token hoặc Authorization: Bearer, không dùng query string.
    Chỉ ADMIN và người sở hữu đơn hàng tương ứng được xem.
    """
    trans = db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.transaction_code == transaction_code.strip()
        )
    )
    if not trans:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch thanh toán.")

    if trans.order_id:
        order = db.get(Order, trans.order_id)
        if order:
            effective_token = x_order_token
            if not effective_token and authorization and authorization.startswith("Bearer "):
                bearer_val = authorization[7:].strip()
                if verify_guest_order_token(bearer_val, order.order_code):
                    effective_token = bearer_val
            _verify_order_payment_access(
                order,
                current_user,
                phone_verify=phone_verify,
                order_token=effective_token,
                action_name="tra cứu giao dịch",
            )

    return {
        "id": trans.id,
        "transaction_code": trans.transaction_code,
        "order_id": trans.order_id,
        "provider": trans.provider,
        "amount": float(trans.amount),
        "currency": trans.currency,
        "status": trans.status,
        "provider_trans_id": trans.provider_trans_id,
        "provider_pay_url": trans.provider_pay_url,
        "created_at": trans.created_at.isoformat() if trans.created_at else None,
        "updated_at": trans.updated_at.isoformat() if trans.updated_at else None,
    }


# ==============================================================================
# 6. PAYMENT RECONCILIATION CORE (CHỈ ADMIN)
# ==============================================================================

@payments_router.get("/reconciliation/order/{order_code}")
def reconcile_single_order(
    order_code: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Đối soát tài chính giữa số tiền đơn hàng và các giao dịch thanh toán thực nhận.
    Chỉ ADMIN được truy cập.
    """
    return PaymentReconciliationService.reconcile_order(
        db=db,
        order_code=order_code.strip(),
    )


@payments_router.post("/reconciliation/heal/{order_code}")
def auto_heal_order_status(
    order_code: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Tự động khắc phục sai lệch trạng thái nếu tiền đã vào cổng thành công 100% nhưng đơn hàng chưa chuyển PAID.
    Chỉ ADMIN được truy cập.
    """
    return PaymentReconciliationService.auto_heal_order(
        db=db,
        order_code=order_code.strip(),
    )


@payments_router.get("/reconciliation/audit")
def audit_payment_reconciliation(
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Báo cáo kiểm toán đối soát tổng thể toàn hệ thống cho các đơn hàng gần đây.
    Chỉ ADMIN được truy cập.
    """
    return PaymentReconciliationService.audit_system(
        db=db,
        limit=min(limit, 200),
    )


# ==============================================================================
# 7. INVENTORY RESERVATION LIFECYCLE & ORDER CANCELLATION
# ==============================================================================

@payments_router.post("/orders/{order_code}/cancel")
def cancel_order_and_release_stock(
    order_code: str,
    payload: CancelOrderRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Hủy đơn hàng có xác thực và phân quyền:
    - Buyer chỉ được hủy đơn của chính mình (chống IDOR).
    - Đơn còn ở trạng thái PENDING hoặc trong vòng 30 phút.
    - Idempotent: nếu đơn đã hủy thì trả về kết quả an toàn.
    - Ghi audit log đầy đủ.
    """
    clean_code = order_code.strip()
    order = db.scalar(select(Order).where(Order.order_code == clean_code))
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")

    _verify_order_payment_access(
        order,
        current_user,
        phone_verify=payload.phone_verify,
        order_token=payload.order_token,
        action_name="hủy đơn hàng",
    )

    if order.order_status == "CANCELLED":
        return {
            "status": "SUCCESS",
            "message": "Đơn hàng này đã được hủy trước đó.",
            "order_code": clean_code,
            "order_status": "CANCELLED",
        }

    if order.order_status in ["SHIPPING", "COMPLETED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Đơn hàng đang ở trạng thái '{order.order_status}', không thể tự hủy. Vui lòng liên hệ Dược sĩ trực tuyến.",
        )

    # Khách hàng chỉ được hủy khi PENDING hoặc trong vòng 30 phút sau khi đặt
    if current_user and getattr(current_user, "role", "") == UserRole.CUSTOMER:
        now = datetime.now(timezone.utc)
        order_time = order.created_at
        if order_time:
            if order_time.tzinfo is None:
                order_time = order_time.replace(tzinfo=timezone.utc)
            time_elapsed = (now - order_time).total_seconds()
            if order.order_status != "PENDING" and time_elapsed > 1800:
                raise HTTPException(
                    status_code=400,
                    detail="Đơn hàng đã được xác nhận quá 30 phút. Không thể tự hủy trực tuyến.",
                )

    before_status = order.order_status
    released_qty = FulfillmentRoutingService.release_order_reservations(
        db=db,
        order_id=order.id,
        reason=payload.reason or "Khách hàng yêu cầu hủy đơn",
    )
    order.order_status = "CANCELLED"
    order.fulfillment_status = "CANCELLED"

    write_audit(
        db,
        action="CANCEL_ORDER",
        entity_type="Order",
        entity_id=order.id,
        user=current_user,
        request=request,
        before={"order_status": before_status},
        after={"order_status": "CANCELLED", "released_quantity": released_qty, "reason": payload.reason},
    )

    db.commit()
    db.refresh(order)

    return {
        "status": "SUCCESS",
        "message": f"Đã hủy đơn hàng {clean_code} thành công và giải phóng {released_qty} đơn vị thuốc tồn kho.",
        "order_code": clean_code,
        "released_quantity": released_qty,
        "order_status": "CANCELLED",
    }


@payments_router.post("/reservations/expire-stale")
def trigger_stale_reservations_expiration(
    max_age_minutes: int = 30,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    [JOB BẢO TRÌ ĐỊNH KỲ] Tự động quét và giải phóng thuốc giữ chỗ cho các đơn hàng trực tuyến
    (MoMo/VietQR) đã quá thời hạn cho phép thanh toán mà khách chưa hoàn tất. Chỉ ADMIN được kích hoạt.
    """
    cancelled = FulfillmentRoutingService.expire_stale_reservations(
        db=db,
        max_age_minutes=max_age_minutes,
    )
    return {
        "status": "SUCCESS",
        "message": f"Đã quét và hủy {len(cancelled)} đơn hàng quá hạn thanh toán.",
        "cancelled_orders": cancelled,
    }
