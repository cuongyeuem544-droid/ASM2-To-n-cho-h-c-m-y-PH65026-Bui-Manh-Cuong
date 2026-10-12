from datetime import datetime

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
    last_login_at: datetime | None
    warehouse_id: int | None = None
    warehouse_name: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    phone: str | None = None
    role: UserRole = UserRole.CUSTOMER
    warehouse_id: int | None = None

