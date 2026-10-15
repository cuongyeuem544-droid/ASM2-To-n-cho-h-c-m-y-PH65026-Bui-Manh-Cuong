from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.entities import User
from app.models.security_and_promotions import PasswordResetToken, UserOtp

logger = logging.getLogger("pharmatrust.auth.otp")


class MockSmsProvider:
    """
    Mock / Sandbox Provider cho môi trường phát triển cục bộ và kiểm thử tự động.
    Lưu mã OTP trong bộ nhớ test để kiểm thử có thể đọc được, tuyệt đối KHÔNG ghi mã thô vào file log.
    """
    latest_otps: dict[str, str] = {}

    @classmethod
    def send_otp(cls, identifier: str, otp_code: str, purpose: str) -> bool:
        cls.latest_otps[identifier] = otp_code
        masked_id = f"{identifier[:3]}***{identifier[-2:]}" if len(identifier) > 5 else "***"
        logger.info(f"[SMS/MockProvider] Đã phát mã OTP cho {masked_id} (mục đích: {purpose})")
        return True

    @classmethod
    def get_test_otp(cls, identifier: str) -> str | None:
        return cls.latest_otps.get(identifier)


class OtpService:
    OTP_TTL_MINUTES = 5
    MAX_ATTEMPTS = 3
    MAX_REQUESTS_PER_HOUR = 5
    RESET_TOKEN_TTL_MINUTES = 15

    @classmethod
    def _hash_otp(cls, identifier: str, otp_code: str) -> str:
        salted = f"h4care_otp:{identifier.strip().lower()}:{otp_code.strip()}"
        return hashlib.sha256(salted.encode()).hexdigest()

    @classmethod
    def _hash_token(cls, token: str) -> str:
        return hashlib.sha256(f"h4care_reset:{token.strip()}".encode()).hexdigest()

    @classmethod
    def request_otp(
        cls,
        db: Session,
        identifier: str,
        purpose: str = "LOGIN",
    ) -> dict[str, Any]:
        clean_id = identifier.strip().replace(" ", "").replace("-", "").lower()
        if not clean_id or len(clean_id) < 5:
            return {"success": False, "error": "Số điện thoại hoặc Email không hợp lệ."}

        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)

        # 1. Kiểm tra giới hạn số lần gửi trong 1 giờ (Rate Limiting)
        sent_in_hour = db.scalar(
            select(func.count(UserOtp.id)).where(
                UserOtp.identifier == clean_id,
                UserOtp.created_at >= one_hour_ago,
            )
        ) or 0

        if sent_in_hour >= cls.MAX_REQUESTS_PER_HOUR:
            return {
                "success": False,
                "error": "Bạn đã yêu cầu gửi mã OTP quá nhiều lần trong 1 giờ. Vui lòng thử lại sau.",
            }

        # 2. Vô hiệu hóa các OTP chưa dùng trước đó cho cùng định danh và mục đích
        active_previous = db.scalars(
            select(UserOtp).where(
                UserOtp.identifier == clean_id,
                UserOtp.purpose == purpose,
                UserOtp.is_used == False,
                UserOtp.expires_at > now,
            )
        ).all()
        for prev in active_previous:
            prev.is_used = True

        # 3. Tạo mã ngẫu nhiên 6 chữ số an toàn bảo mật
        raw_otp = f"{secrets.randbelow(900000) + 100000}"
        otp_hash = cls._hash_otp(clean_id, raw_otp)
        expires_at = now + timedelta(minutes=cls.OTP_TTL_MINUTES)

        otp_record = UserOtp(
            identifier=clean_id,
            otp_hash=otp_hash,
            purpose=purpose,
            attempts=0,
            max_attempts=cls.MAX_ATTEMPTS,
            expires_at=expires_at,
            is_used=False,
            created_at=now,
        )
        db.add(otp_record)
        db.commit()

        # 4. Gửi qua Mock/Sandbox SMS Provider
        MockSmsProvider.send_otp(clean_id, raw_otp, purpose)

        return {
            "success": True,
            "message": "Mã xác thực OTP đã được gửi đến số điện thoại/email của bạn (hiệu lực 5 phút).",
            "expires_in": cls.OTP_TTL_MINUTES * 60,
        }

    @classmethod
    def verify_otp(
        cls,
        db: Session,
        identifier: str,
        otp_code: str,
        purpose: str = "LOGIN",
    ) -> dict[str, Any]:
        clean_id = identifier.strip().replace(" ", "").replace("-", "").lower()
        clean_code = otp_code.strip()

        if not clean_code or len(clean_code) != 6 or not clean_code.isdigit():
            return {"success": False, "error": "Mã OTP phải gồm đúng 6 chữ số."}

        now = datetime.now(UTC)

        # Tra cứu bản ghi OTP còn hạn và chưa dùng
        otp_record = db.scalar(
            select(UserOtp)
            .where(
                UserOtp.identifier == clean_id,
                UserOtp.purpose == purpose,
                UserOtp.is_used == False,
                UserOtp.expires_at > now,
            )
            .order_by(UserOtp.id.desc())
        )

        if not otp_record:
            return {
                "success": False,
                "error": "Mã OTP không tồn tại, đã hết hạn hoặc đã được sử dụng. Vui lòng yêu cầu mã mới.",
            }

        if otp_record.attempts >= otp_record.max_attempts:
            otp_record.is_used = True
            db.commit()
            return {
                "success": False,
                "error": "Bạn đã nhập sai mã OTP quá số lần cho phép. Mã này đã bị vô hiệu hóa.",
            }

        # Tăng số lần thử
        otp_record.attempts += 1
        expected_hash = cls._hash_otp(clean_id, clean_code)

        if secrets.compare_digest(otp_record.otp_hash, expected_hash):
            otp_record.is_used = True
            db.commit()
            return {"success": True, "message": "Xác thực OTP thành công."}
        else:
            remaining = otp_record.max_attempts - otp_record.attempts
            db.commit()
            if remaining <= 0:
                otp_record.is_used = True
                db.commit()
                return {
                    "success": False,
                    "error": "Mã OTP không chính xác. Bạn đã hết số lần thử. Vui lòng yêu cầu mã mới.",
                }
            return {
                "success": False,
                "error": f"Mã OTP không chính xác. Bạn còn {remaining} lần thử.",
            }

    @classmethod
    def create_password_reset_token(cls, db: Session, user: User) -> str:
        now = datetime.now(UTC)
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(raw_token)
        expires_at = now + timedelta(minutes=cls.RESET_TOKEN_TTL_MINUTES)

        # Hủy các token reset cũ chưa dùng
        old_tokens = db.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.is_used == False,
            )
        ).all()
        for ot in old_tokens:
            ot.is_used = True

        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            is_used=False,
            created_at=now,
        )
        db.add(reset_record)
        db.commit()
        return raw_token

    @classmethod
    def reset_password_with_token(
        cls,
        db: Session,
        raw_token: str,
        new_password: str,
    ) -> dict[str, Any]:
        if not new_password or len(new_password) < 6:
            return {"success": False, "error": "Mật khẩu mới phải có tối thiểu 6 ký tự."}

        token_hash = cls._hash_token(raw_token)
        now = datetime.now(UTC)

        reset_record = db.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.is_used == False,
                PasswordResetToken.expires_at > now,
            )
        )

        if not reset_record:
            return {
                "success": False,
                "error": "Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn (tối đa 15 phút).",
            }

        user = db.scalar(select(User).where(User.id == reset_record.user_id, User.is_active == True))
        if not user:
            return {"success": False, "error": "Không tìm thấy tài khoản người dùng."}

        # 1. Cập nhật mật khẩu mới
        user.password_hash = hash_password(new_password)

        # 2. Thu hồi toàn bộ phiên đăng nhập hiện tại bằng cách tăng token_version
        user.token_version = (user.token_version or 1) + 1

        # 3. Đánh dấu token đã được sử dụng (Một lần duy nhất)
        reset_record.is_used = True

        db.commit()
        return {
            "success": True,
            "message": "Đã đổi mật khẩu thành công và thu hồi tất cả phiên đăng nhập cũ. Vui lòng đăng nhập lại.",
        }
