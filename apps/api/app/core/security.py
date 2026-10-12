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

