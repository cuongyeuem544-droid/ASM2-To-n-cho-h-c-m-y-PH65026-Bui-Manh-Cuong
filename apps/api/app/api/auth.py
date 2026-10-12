import secrets
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import CustomerRegisterRequest, LoginRequest, RefreshRequest, TokenPair, UserCreate, UserOut
from app.services.audit import write_audit
from app.services.otp_service import OtpService


router = APIRouter(prefix="/auth", tags=["Xác thực"])
users_router = APIRouter(prefix="/users", tags=["Người dùng"])


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    login_id = (payload.identifier or payload.email or "").strip()
    if not login_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng nhập Email hoặc Số điện thoại")

    clean_phone = login_id.replace(" ", "").replace("-", "")
    user = db.scalar(
        select(User).where(
            or_(
                User.email == login_id.lower(),
                User.phone == login_id,
                User.phone == clean_phone,
            )
        )
    )
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email, số điện thoại hoặc mật khẩu không đúng")
    user.last_login_at = datetime.now(UTC)
    write_audit(db, "LOGIN", "User", user.id, user=user, request=request)
    db.commit()
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value, user.token_version or 1),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register_customer(payload: CustomerRegisterRequest, request: Request, db: Session = Depends(get_db)):
    clean_phone = payload.phone.strip().replace(" ", "").replace("-", "")
    email = payload.email.strip().lower() if payload.email and payload.email.strip() else f"{clean_phone}@customer.pharmatrust.vn"

    if db.scalar(select(User.id).where(User.phone == clean_phone)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Số điện thoại này đã được đăng ký tài khoản")

    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email này đã được sử dụng")

    user = User(
        email=email,
        phone=clean_phone,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=UserRole.CUSTOMER,
        loyalty_points=50,
        is_active=True,
    )
    db.add(user)
    db.flush()
    write_audit(db, "REGISTER", "User", user.id, user=user, request=request, after={"email": email, "phone": clean_phone, "role": UserRole.CUSTOMER.value})
    db.commit()
    db.refresh(user)

    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value, user.token_version or 1),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token, "refresh")
        user_id = int(decoded["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token không hợp lệ") from None
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không còn hoạt động")
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@users_router.get("", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return db.scalars(select(User).order_by(User.created_at.desc())).all()


@users_router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    email = payload.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email đã tồn tại")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.flush()
    write_audit(db, "CREATE", "User", user.id, user=admin, request=request, after={"email": email, "role": payload.role.value})
    db.commit()
    db.refresh(user)
    return user


# ==============================================================================
# OTP & SECURE PASSWORD RESET SCHEMAS & ENDPOINTS
# ==============================================================================

class OtpRequestPayload(BaseModel):
    identifier: str
    purpose: str = "LOGIN"


class OtpLoginPayload(BaseModel):
    phone: str
    otp: str


class PasswordResetRequestPayload(BaseModel):
    identifier: str


class PasswordResetVerifyPayload(BaseModel):
    identifier: str
    otp: str


class PasswordResetConfirmPayload(BaseModel):
    reset_token: str
    new_password: str


@router.post("/otp/request")
def request_otp_code(payload: OtpRequestPayload, db: Session = Depends(get_db)):
    """
    Yêu cầu mã xác thực OTP (6 chữ số ngẫu nhiên, TTL 5 phút, băm SHA-256).
    Rate limit: tối đa 5 lần gửi / giờ. Không ghi log mã thô.
    """
    res = OtpService.request_otp(db, identifier=payload.identifier, purpose=payload.purpose)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/otp/login", response_model=TokenPair)
def login_with_otp(payload: OtpLoginPayload, request: Request, db: Session = Depends(get_db)):
    """
    Đăng nhập bằng số điện thoại và mã OTP một lần.
    Tự động đăng ký tài khoản khách hàng mới nếu số điện thoại chưa tồn tại.
    """
    clean_phone = payload.phone.strip().replace(" ", "").replace("-", "")
    verify_res = OtpService.verify_otp(db, identifier=clean_phone, otp_code=payload.otp, purpose="LOGIN")
    if not verify_res.get("success"):
        raise HTTPException(status_code=400, detail=verify_res.get("error"))

    user = db.scalar(select(User).where(User.phone == clean_phone))
    if not user:
        email = f"{clean_phone}@customer.pharmatrust.vn"
        user = User(
            phone=clean_phone,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(16)),
            full_name=f"Khách hàng {clean_phone[-4:]}",
            role=UserRole.CUSTOMER,
            loyalty_points=50,
            is_active=True,
            token_version=1,
        )
        db.add(user)
        db.flush()
        write_audit(db, "REGISTER_OTP", "User", user.id, user=user, request=request, after={"phone": clean_phone, "role": UserRole.CUSTOMER.value})

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không còn hoạt động")

    user.last_login_at = datetime.now(UTC)
    write_audit(db, "LOGIN_OTP", "User", user.id, user=user, request=request)
    db.commit()
    db.refresh(user)

    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value, user.token_version or 1),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/password-reset/request")
def request_password_reset_otp(payload: PasswordResetRequestPayload, db: Session = Depends(get_db)):
    """
    Yêu cầu gửi OTP đặt lại mật khẩu đến số điện thoại hoặc email đã đăng ký.
    """
    clean_id = payload.identifier.strip().replace(" ", "").replace("-", "").lower()
    user = db.scalar(select(User).where(or_(User.email == clean_id, User.phone == clean_id)))
    if not user or not user.is_active:
        return {"success": True, "message": "Nếu thông tin tài khoản tồn tại, mã xác thực OTP đã được gửi."}

    res = OtpService.request_otp(db, identifier=clean_id, purpose="RESET_PASSWORD")
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/password-reset/verify")
def verify_password_reset_otp(payload: PasswordResetVerifyPayload, db: Session = Depends(get_db)):
    """
    Xác minh OTP đặt lại mật khẩu và cấp token đổi mật khẩu một lần (TTL 15 phút).
    """
    clean_id = payload.identifier.strip().replace(" ", "").replace("-", "").lower()
    verify_res = OtpService.verify_otp(db, identifier=clean_id, otp_code=payload.otp, purpose="RESET_PASSWORD")
    if not verify_res.get("success"):
        raise HTTPException(status_code=400, detail=verify_res.get("error"))

    user = db.scalar(select(User).where(or_(User.email == clean_id, User.phone == clean_id), User.is_active == True))
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng.")

    raw_token = OtpService.create_password_reset_token(db, user)
    return {
        "success": True,
        "reset_token": raw_token,
        "message": "Xác thực OTP thành công. Vui lòng thiết lập mật khẩu mới trong vòng 15 phút.",
    }


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirmPayload, request: Request, db: Session = Depends(get_db)):
    """
    Thiết lập mật khẩu mới bằng token một lần. Thu hồi tất cả phiên đăng nhập cũ.
    """
    res = OtpService.reset_password_with_token(db, raw_token=payload.reset_token, new_password=payload.new_password)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


