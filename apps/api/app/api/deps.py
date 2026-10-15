from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn chưa đăng nhập")
    try:
        payload = decode_token(credentials.credentials, "access")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ hoặc đã hết hạn") from None
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không còn hoạt động")
    token_ver = payload.get("token_version")
    if token_ver is not None and getattr(user, "token_version", 1) != token_ver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã bị thu hồi do thay đổi mật khẩu. Vui lòng đăng nhập lại.",
        )
    return user


def require_roles(*roles: UserRole) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền thực hiện thao tác này")
        return user

    return dependency


require_admin = require_roles(UserRole.ADMIN)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, "access")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    return db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))


def strict_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Dependency cho phép khách vãng lai hoặc người dùng đăng nhập:
    - Nếu KHÔNG gửi Authorization header: trả về None (khách vãng lai).
    - Nếu CÓ gửi Authorization header nhưng token sai/hết hạn: trả HTTP 401 UNAUTHORIZED (không âm thầm coi là khách vãng lai).
    - Nếu token hợp lệ: trả về đối tượng User.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, "access")
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.",
        ) from None

    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không còn hoạt động hoặc đã bị khóa.",
        )

    token_ver = payload.get("token_version")
    if token_ver is not None and getattr(user, "token_version", 1) != token_ver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã bị thu hồi do thay đổi mật khẩu. Vui lòng đăng nhập lại.",
        )

    return user


def get_user_warehouse_membership(user: User, db: Session):
    from app.models.inventory import UserWarehouseMembership
    return db.scalar(
        select(UserWarehouseMembership)
        .where(UserWarehouseMembership.user_id == user.id, UserWarehouseMembership.is_active.is_(True))
    )


def require_warehouse_manager(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, int | None]:
    """
    Cho phép ADMIN (toàn quyền) hoặc WAREHOUSE_MANAGER có membership hợp lệ.
    Trả về (user, warehouse_id). Nếu ADMIN, warehouse_id = None (toàn quyền).
    """
    if user.role == UserRole.ADMIN:
        return user, None
    if user.role == UserRole.WAREHOUSE_MANAGER:
        membership = get_user_warehouse_membership(user, db)
        if not membership:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản Quản lý kho chưa được gán vào kho hàng cụ thể")
        return user, membership.warehouse_id
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Quản Lý Kho hoặc Quản Trị Viên mới có quyền thực hiện")


def require_warehouse_staff_or_manager(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, int | None]:
    """
    Cho phép ADMIN, WAREHOUSE_MANAGER, hoặc WAREHOUSE_STAFF.
    """
    if user.role == UserRole.ADMIN:
        return user, None
    if user.role in (UserRole.WAREHOUSE_MANAGER, UserRole.WAREHOUSE_STAFF):
        membership = get_user_warehouse_membership(user, db)
        if not membership:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản kho chưa được gán vào kho hàng cụ thể")
        return user, membership.warehouse_id
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập nghiệp vụ kho hàng")


def check_warehouse_permission(user: User, warehouse_id: int, db: Session) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    membership = get_user_warehouse_membership(user, db)
    return bool(membership and membership.warehouse_id == warehouse_id)

