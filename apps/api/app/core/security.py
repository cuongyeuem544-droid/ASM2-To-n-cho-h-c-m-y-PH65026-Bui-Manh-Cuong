import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.b64decode(salt_text)
        expected = base64.b64decode(digest_text)
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(subject: str, role: str, token_version: int = 1) -> str:
    return create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_minutes),
        {"role": role, "token_version": token_version},
    )


def create_refresh_token(subject: str) -> str:
    return create_token(subject, "refresh", timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Loại token không hợp lệ")
    return payload


def create_guest_order_token(order_code: str, phone: str, expires_days: int = 30) -> str:
    """
    Tạo token ký điện tử HS256 dành riêng cho khách vãng lai để thao tác trên đơn hàng.
    """
    clean_code = order_code.strip()
    clean_phone = phone.strip()
    return create_token(
        subject=clean_code,
        token_type="guest_order",
        expires_delta=timedelta(days=expires_days),
        extra={"order_code": clean_code, "phone": clean_phone},
    )


def verify_guest_order_token(token: str | None, expected_order_code: str) -> bool:
    """
    Xác thực chữ ký và tính hợp lệ của token đơn hàng khách vãng lai.
    """
    if not token or not str(token).strip():
        return False
    try:
        clean_tok = str(token).strip()
        if clean_tok.startswith("Bearer "):
            clean_tok = clean_tok[7:].strip()
        payload = decode_token(clean_tok, expected_type="guest_order")
        order_in_token = payload.get("order_code") or payload.get("sub")
        return bool(order_in_token and str(order_in_token).strip() == expected_order_code.strip())
    except Exception:
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    import re
    if len(password) < 8:
        return False, "Mật khẩu phải có tối thiểu 8 ký tự"
    if not re.search(r"[A-Z]", password):
        return False, "Mật khẩu phải chứa ít nhất 1 chữ cái in hoa (A-Z)"
    if not re.search(r"[a-z]", password):
        return False, "Mật khẩu phải chứa ít nhất 1 chữ cái in thường (a-z)"
    if not re.search(r"\d", password):
        return False, "Mật khẩu phải chứa ít nhất 1 chữ số (0-9)"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+]", password):
        return False, "Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt (!@#$%...)"
    return True, ""


def generate_secure_temporary_password(length: int = 12) -> str:
    import secrets
    import string
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%&*?")
    remaining = [secrets.choice(string.ascii_letters + string.digits + "!@#$%&*?") for _ in range(max(length - 4, 4))]
    all_chars = [upper, lower, digit, special] + remaining
    secrets.SystemRandom().shuffle(all_chars)
    return "".join(all_chars)

