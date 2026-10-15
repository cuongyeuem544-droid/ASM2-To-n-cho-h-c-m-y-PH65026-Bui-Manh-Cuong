import secrets
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_temporary_password,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.db.session import get_db
from app.models import AuditLog, User
from app.models.enums import UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    CustomerRegisterRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenPair,
    UserActivityLogOut,
    UserCreate,
    UserCreateResponse,
    UserOut,
    UserUpdate,
)
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
    email_clean = login_id.lower()
    alt_email = email_clean.replace(".", "_") if "." in email_clean else email_clean.replace("_", ".")
    user = db.scalar(
        select(User).where(
            or_(
                User.email == email_clean,
                User.email == alt_email,
                User.phone == login_id,
                User.phone == clean_phone,
            )
        )
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc số điện thoại không tồn tại trong hệ thống")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.")

    is_pwd_valid = verify_password(payload.password, user.password_hash)
    if not is_pwd_valid:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mật khẩu không chính xác")

    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(UTC)
    write_audit(db, "LOGIN", "User", user.id, user=user, request=request)
    db.commit()
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value, user.token_version or 1),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
        must_change_password=bool(user.must_change_password),
    )


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Đổi mật khẩu người dùng (dùng cho đăng nhập lần đầu hoặc đổi định kỳ).
    """
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Mật khẩu mới không được trùng với mật khẩu hiện tại")

    valid, msg = validate_password_strength(payload.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    current_user.password_changed_at = datetime.now(UTC)
    current_user.token_version = (current_user.token_version or 1) + 1

    write_audit(
        db,
        "CHANGE_PASSWORD",
        "User",
        current_user.id,
        user=current_user,
        request=request,
    )
    db.commit()
    return {
        "success": True,
        "message": "Đổi mật khẩu thành công. Mật khẩu mới đã được cập nhật.",
        "must_change_password": False,
    }


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


def _resolve_user_warehouse_id(user: User, db: Session) -> int | None:
    if user.warehouse_id:
        return user.warehouse_id
    from app.models.inventory import UserWarehouseMembership
    wh_id = db.scalar(
        select(UserWarehouseMembership.warehouse_id).where(
            UserWarehouseMembership.user_id == user.id,
            UserWarehouseMembership.is_active.is_(True),
        )
    )
    if wh_id:
        user.warehouse_id = wh_id
        db.commit()
        return wh_id
    return None


@users_router.get("", response_model=list[UserOut])
def list_users(
    search: str | None = None,
    role: str | None = None,
    warehouse_id: int | None = None,
    is_active: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Danh sách người dùng:
    - ADMIN: Xem tất cả tài khoản, lọc theo vai trò, kho, trạng thái và tìm kiếm.
    - WAREHOUSE_MANAGER: CHỈ xem nhân viên kho (WAREHOUSE_STAFF) thuộc kho của mình.
    """
    if current_user.role == UserRole.ADMIN:
        stmt = select(User).order_by(User.created_at.desc())
        if role and role != "ALL":
            stmt = stmt.where(User.role == role)
        if warehouse_id:
            stmt = stmt.where(User.warehouse_id == warehouse_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if search and search.strip():
            s = f"%{search.strip().lower()}%"
            stmt = stmt.where(or_(User.full_name.ilike(s), User.email.ilike(s), User.phone.ilike(s)))
        return db.scalars(stmt).all()

    elif current_user.role == UserRole.WAREHOUSE_MANAGER:
        mgr_wh_id = _resolve_user_warehouse_id(current_user, db)
        if not mgr_wh_id:
            return []
        stmt = select(User).where(
            User.role == UserRole.WAREHOUSE_STAFF,
            User.warehouse_id == mgr_wh_id,
        ).order_by(User.created_at.desc())
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if search and search.strip():
            s = f"%{search.strip().lower()}%"
            stmt = stmt.where(or_(User.full_name.ilike(s), User.email.ilike(s), User.phone.ilike(s)))
        return db.scalars(stmt).all()

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập trang quản lý tài khoản")


@users_router.get("/{user_id}", response_model=UserOut)
def get_user_detail(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    if current_user.role == UserRole.WAREHOUSE_MANAGER:
        mgr_wh = _resolve_user_warehouse_id(current_user, db)
        tgt_wh = _resolve_user_warehouse_id(target, db)
        if target.role != UserRole.WAREHOUSE_STAFF or tgt_wh != mgr_wh:
            raise HTTPException(status_code=403, detail="Bạn chỉ có quyền xem nhân viên thuộc kho của bạn")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập tài khoản này")

    return target


@users_router.post("", response_model=UserCreateResponse, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.inventory import UserWarehouseMembership, Warehouse

    if current_user.role not in (UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER):
        raise HTTPException(status_code=403, detail="Bạn không có quyền tạo tài khoản")

    target_role = payload.role
    target_warehouse_id = payload.warehouse_id

    if current_user.role == UserRole.WAREHOUSE_MANAGER:
        if payload.role and payload.role != UserRole.WAREHOUSE_STAFF:
            raise HTTPException(status_code=403, detail="Quản lý kho chỉ được phép tạo tài khoản Nhân Viên Kho (WAREHOUSE_STAFF)")
        mgr_wh = _resolve_user_warehouse_id(current_user, db)
        if not mgr_wh:
            raise HTTPException(status_code=403, detail="Tài khoản Quản lý kho chưa được gán vào kho nào")
        if payload.warehouse_id and payload.warehouse_id != mgr_wh:
            raise HTTPException(status_code=403, detail="Quản lý kho không được phép tạo tài khoản cho chi nhánh kho khác")
        target_role = UserRole.WAREHOUSE_STAFF
        target_warehouse_id = mgr_wh

    email = payload.email.lower().strip()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email này đã được sử dụng trong hệ thống")

    if payload.password:
        valid, msg = validate_password_strength(payload.password)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)
        temp_pwd = payload.password
    else:
        temp_pwd = generate_secure_temporary_password()

    if target_warehouse_id:
        wh = db.get(Warehouse, target_warehouse_id)
        if not wh:
            raise HTTPException(status_code=404, detail="Không tìm thấy chi nhánh kho hàng")

    user = User(
        email=email,
        phone=payload.phone.strip() if payload.phone else None,
        password_hash=hash_password(temp_pwd),
        full_name=payload.full_name.strip(),
        role=target_role,
        warehouse_id=target_warehouse_id,
        is_active=True,
        must_change_password=True,
        created_by_user_id=current_user.id,
    )
    db.add(user)
    db.flush()

    if target_warehouse_id:
        membership = UserWarehouseMembership(
            user_id=user.id,
            warehouse_id=target_warehouse_id,
            role=target_role.value,
            is_active=True,
            assigned_by=current_user.id,
        )
        db.add(membership)
        db.flush()

    write_audit(
        db,
        "CREATE_USER",
        "User",
        user.id,
        user=current_user,
        request=request,
        after={
            "email": email,
            "role": target_role.value,
            "warehouse_id": target_warehouse_id,
            "must_change_password": True,
        },
    )
    db.commit()
    db.refresh(user)

    return UserCreateResponse(
        user=UserOut.model_validate(user),
        temporary_password=temp_pwd,
        message="Tạo tài khoản thành công! Mật khẩu tạm thời chỉ hiển thị một lần duy nhất này.",
    )


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.inventory import UserWarehouseMembership, Warehouse
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    if current_user.role == UserRole.WAREHOUSE_MANAGER:
        mgr_wh = _resolve_user_warehouse_id(current_user, db)
        tgt_wh = _resolve_user_warehouse_id(target, db)
        if target.role != UserRole.WAREHOUSE_STAFF or tgt_wh != mgr_wh:
            raise HTTPException(status_code=403, detail="Bạn chỉ có quyền sửa nhân viên thuộc kho của bạn")
        if payload.role is not None and payload.role != UserRole.WAREHOUSE_STAFF:
            raise HTTPException(status_code=403, detail="Quản lý kho không được phép thay đổi vai trò nhân viên")
        if payload.warehouse_id is not None and payload.warehouse_id != mgr_wh:
            raise HTTPException(status_code=403, detail="Quản lý kho không được phép đổi kho của nhân viên")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền chỉnh sửa tài khoản này")

    before_data = {
        "full_name": target.full_name,
        "email": target.email,
        "phone": target.phone,
        "role": target.role.value,
        "warehouse_id": target.warehouse_id,
    }

    if payload.full_name is not None:
        target.full_name = payload.full_name.strip()
    if payload.phone is not None:
        target.phone = payload.phone.strip() or None
    if payload.email is not None:
        email_clean = payload.email.lower().strip()
        if email_clean != target.email:
            if db.scalar(select(User.id).where(User.email == email_clean, User.id != target.id)):
                raise HTTPException(status_code=409, detail="Email này đã được sử dụng bởi tài khoản khác")
            target.email = email_clean

    if current_user.role == UserRole.ADMIN:
        if payload.role is not None:
            target.role = payload.role
        if payload.warehouse_id is not None:
            if payload.warehouse_id != target.warehouse_id:
                if payload.warehouse_id > 0:
                    wh = db.get(Warehouse, payload.warehouse_id)
                    if not wh:
                        raise HTTPException(status_code=404, detail="Không tìm thấy kho hàng được chỉ định")
                    target.warehouse_id = payload.warehouse_id
                    # Cập nhật membership
                    existing = db.scalars(
                        select(UserWarehouseMembership).where(
                            UserWarehouseMembership.user_id == target.id,
                            UserWarehouseMembership.is_active == True,
                        )
                    ).all()
                    for m in existing:
                        m.is_active = False
                        m.revoked_at = datetime.now(UTC)
                    db.add(UserWarehouseMembership(
                        user_id=target.id,
                        warehouse_id=payload.warehouse_id,
                        role=target.role.value,
                        is_active=True,
                        assigned_by=current_user.id,
                    ))
                else:
                    target.warehouse_id = None

    write_audit(
        db,
        "UPDATE_USER",
        "User",
        target.id,
        user=current_user,
        request=request,
        before=before_data,
        after={
            "full_name": target.full_name,
            "email": target.email,
            "phone": target.phone,
            "role": target.role.value,
            "warehouse_id": target.warehouse_id,
        },
    )
    db.commit()
    db.refresh(target)
    return target


@users_router.patch("/{user_id}/status", response_model=UserOut)
def toggle_user_status(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể tự khóa tài khoản của chính mình")

    if current_user.role == UserRole.WAREHOUSE_MANAGER:
        mgr_wh = _resolve_user_warehouse_id(current_user, db)
        tgt_wh = _resolve_user_warehouse_id(target, db)
        if target.role != UserRole.WAREHOUSE_STAFF or tgt_wh != mgr_wh:
            raise HTTPException(status_code=403, detail="Bạn chỉ có thể quản lý nhân viên thuộc kho của bạn")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện thao tác này")

    before_active = target.is_active
    target.is_active = not target.is_active
    if not target.is_active:
        target.token_version = (target.token_version or 1) + 1

    write_audit(
        db,
        "TOGGLE_USER_STATUS",
        "User",
        target.id,
        user=current_user,
        request=request,
        before={"is_active": before_active},
        after={"is_active": target.is_active},
    )
    db.commit()
    db.refresh(target)
    return target


@users_router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
def reset_user_password(
    user_id: int,
    request: Request,
    payload: ResetPasswordRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Đặt lại mật khẩu cho tài khoản người dùng:
    - Admin: Cho mọi tài khoản.
    - Quản lý kho: CHỈ cho nhân viên thuộc kho của mình.
    - Thu hồi toàn bộ phiên đăng nhập cũ (token_version + 1).
    - Đặt must_change_password = True.
    - Tuyệt đối không ghi mật khẩu vào audit log.
    - Mật khẩu tạm thời chỉ trả về trong response này đúng 1 lần.
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    if current_user.role == UserRole.WAREHOUSE_MANAGER:
        mgr_wh = _resolve_user_warehouse_id(current_user, db)
        tgt_wh = _resolve_user_warehouse_id(target, db)
        if target.role != UserRole.WAREHOUSE_STAFF or tgt_wh != mgr_wh:
            raise HTTPException(status_code=403, detail="Bạn chỉ có quyền đặt lại mật khẩu cho nhân viên thuộc kho của bạn")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền đặt lại mật khẩu cho tài khoản này")

    if payload and payload.new_password:
        valid, msg = validate_password_strength(payload.new_password)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)
        temp_pwd = payload.new_password
    else:
        temp_pwd = generate_secure_temporary_password()

    target.password_hash = hash_password(temp_pwd)
    target.must_change_password = True
    target.password_changed_at = datetime.now(UTC)
    target.token_version = (target.token_version or 1) + 1

    write_audit(
        db,
        "RESET_PASSWORD",
        "User",
        target.id,
        user=current_user,
        request=request,
        after={
            "target_user_id": target.id,
            "target_email": target.email,
            "target_role": target.role.value,
            "must_change_password": True,
        },
    )
    db.commit()

    return ResetPasswordResponse(
        message="Đặt lại mật khẩu thành công! Mật khẩu tạm thời này chỉ hiển thị duy nhất một lần.",
        temporary_password=temp_pwd,
        must_change_password=True,
    )


@users_router.get("/{user_id}/activity", response_model=list[UserActivityLogOut])
def get_user_activity(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng")

    if current_user.role == UserRole.WAREHOUSE_MANAGER:
        mgr_wh = _resolve_user_warehouse_id(current_user, db)
        tgt_wh = _resolve_user_warehouse_id(target, db)
        if target.role != UserRole.WAREHOUSE_STAFF or tgt_wh != mgr_wh:
            raise HTTPException(status_code=403, detail="Bạn chỉ có quyền xem lịch sử hoạt động của nhân viên thuộc kho của bạn")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem lịch sử tài khoản này")

    logs = db.scalars(
        select(AuditLog)
        .where(
            or_(
                AuditLog.user_id == target.id,
                and_(AuditLog.entity_type == "User", AuditLog.entity_id == str(target.id)),
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    ).all()

    results = []
    for l in logs:
        results.append(
            UserActivityLogOut(
                id=l.id,
                action=l.action,
                created_at=l.created_at,
                user_name=target.full_name,
                ip_address=l.ip_address,
                details=l.after_json or l.before_json,
            )
        )
    return results


@users_router.post("/{user_id}/warehouse/{warehouse_id}", response_model=UserOut)
def assign_user_warehouse(
    user_id: int,
    warehouse_id: int,
    request: Request,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    from app.models.inventory import UserWarehouseMembership, Warehouse
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    wh = db.get(Warehouse, warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Không tìm thấy kho hàng")

    existing = db.scalars(
        select(UserWarehouseMembership).where(
            UserWarehouseMembership.user_id == target.id,
            UserWarehouseMembership.is_active == True,
        )
    ).all()
    for m in existing:
        m.is_active = False
        m.revoked_at = datetime.now(UTC)

    target.warehouse_id = wh.id
    membership = UserWarehouseMembership(
        user_id=target.id,
        warehouse_id=wh.id,
        role=target.role.value,
        is_active=True,
        assigned_by=admin.id,
    )
    db.add(membership)
    write_audit(
        db,
        "ASSIGN_WAREHOUSE",
        "UserWarehouseMembership",
        target.id,
        user=admin,
        request=request,
        after={"user_id": target.id, "warehouse_id": wh.id},
    )
    db.commit()
    db.refresh(target)
    return target


@users_router.delete("/{user_id}/warehouse", response_model=UserOut)
def revoke_user_warehouse(
    user_id: int,
    request: Request,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    from app.models.inventory import UserWarehouseMembership
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    existing = db.scalars(
        select(UserWarehouseMembership).where(
            UserWarehouseMembership.user_id == target.id,
            UserWarehouseMembership.is_active == True,
        )
    ).all()
    for m in existing:
        m.is_active = False
        m.revoked_at = datetime.now(UTC)

    target.warehouse_id = None
    write_audit(
        db,
        "REVOKE_WAREHOUSE",
        "UserWarehouseMembership",
        target.id,
        user=admin,
        request=request,
    )
    db.commit()
    db.refresh(target)
    return target


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
