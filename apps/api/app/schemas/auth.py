from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    identifier: str | None = None
    email: str | None = None
    password: str = Field(min_length=6, max_length=128)


class CustomerRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=9, max_length=20)
    email: str | None = None
    password: str = Field(min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: int
    email: str
    phone: str | None = None
    full_name: str
    role: UserRole
    loyalty_points: int = 50
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    warehouse_id: int | None = None
    warehouse_name: str | None = None
    must_change_password: bool = False
    password_changed_at: datetime | None = None
    created_by_user_id: int | None = None
    created_by_name: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut | None = None
    must_change_password: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    password: str | None = Field(default=None, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    phone: str | None = None
    role: UserRole = UserRole.CUSTOMER
    warehouse_id: int | None = None
    must_change_password: bool = True


class UserCreateResponse(BaseModel):
    user: UserOut
    temporary_password: str
    message: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = None
    role: UserRole | None = None
    warehouse_id: int | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    message: str
    temporary_password: str
    must_change_password: bool = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserActivityLogOut(BaseModel):
    id: int
    action: str
    created_at: datetime | None = None
    user_name: str | None = None
    ip_address: str | None = None
    details: Any = None
