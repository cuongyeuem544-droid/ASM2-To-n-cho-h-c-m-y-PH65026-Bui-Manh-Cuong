import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "PharmaTrust Data Hub"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "development-only-secret-change-me-please"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    database_url: str = "sqlite:///./pharmatrust.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173"])
    public_api_min_score: int = 85
    storage_root: Path = Path("storage")
    max_upload_mb: int = 20
    allow_public_url_import: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ai_provider: str = "rule_based"
    demo_mode: bool = True
    enable_crawler: bool = False

    # Cấu hình tự động cào 24/7 và kiểm duyệt (Mặc định TẮT khỏi luồng chính)
    auto_crawl_enabled: bool = False
    auto_crawl_interval_hours: int = 6
    pharmacity_crawl_enabled: bool = False
    long_chau_crawl_enabled: bool = False
    default_publish_mode: str = "MANUAL_REVIEW"
    public_browser_fallback_enabled: bool = True
    category_ai_threshold: float = 0.85
    job_lease_timeout_seconds: int = 1800

    # Cấu hình Cảnh báo Telegram & Webhook cho Admin
    telegram_alerts_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    alert_webhook_url: str = ""

    # Cấu hình Cổng thanh toán MoMo Sandbox
    momo_partner_code: str = "MOMO"
    momo_access_key: str = "F8BBA842ECF85"
    momo_secret_key: str = "K951B6PE1waDMi640xX0huAHevg3hkVo"
    momo_endpoint: str = "https://test-payment.momo.vn/v2/gateway/api/create"
    momo_return_url: str = "http://localhost:3000/checkout/result"
    momo_ipn_url: str = "http://localhost:8000/api/v1/payments/momo/webhook"

    # Cấu hình Thanh toán Chuyển khoản VietQR (Napas 247)
    vietqr_bank_id: str = "MB"
    vietqr_account_number: str = "0901234567"
    vietqr_account_holder: str = "NHA THUOC PHARMATRUST"
    vietqr_webhook_secret: str = "h4care_vietqr_secret_2026"
    payment_expiry_minutes: int = 30

    # Cấu hình Dịch vụ Gửi Email thật qua Gmail SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "PharmaTrust System"
    smtp_from_email: str = "support@pharmatrust.vn"
    smtp_tls: bool = True
    smtp_ssl: bool = False
    smtp_enabled: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def resolve_database_url(cls, value):
        if isinstance(value, str) and value.startswith("sqlite:///./"):
            repo_root = Path(__file__).resolve().parents[4]
            db_file = repo_root / value.removeprefix("sqlite:///./")
            return f"sqlite:///{db_file.as_posix()}"
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                decoded = json.loads(value)
                if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
                    raise ValueError("CORS_ORIGINS JSON must be an array of strings")
                return [item.strip() for item in decoded if item.strip()]
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def raw_storage(self) -> Path:
        return self.storage_root / "raw"

    @property
    def upload_storage(self) -> Path:
        return self.storage_root / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
