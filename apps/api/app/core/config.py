import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _resolve_repo_root() -> Path:
    """Xác định an toàn thư mục gốc dự án hoặc thư mục triển khai Backend.
    
    Tương thích cả 2 môi trường:
    - Local monorepo: <root>/apps/api/app/core/config.py (5 cấp thư mục)
    - Docker container: /app/app/core/config.py (3 cấp thư mục)
    Tuyệt đối không truy cập trực tiếp parents[4] để tránh IndexError trên Linux/Docker.
    """
    file_path = Path(__file__).resolve()
    for parent in file_path.parents:
        if (parent / ".git").exists() or (parent / "apps" / "api").exists():
            return parent
    if len(file_path.parents) >= 3:
        return file_path.parents[2]
    return file_path.parent


_REPO_ROOT = _resolve_repo_root()


def _resolve_env_files() -> tuple[Path, ...]:
    """Tìm danh sách các file .env ứng viên theo thứ tự ưu tiên."""
    candidates = [
        Path.cwd() / ".env",
        _REPO_ROOT / ".env",
        _REPO_ROOT / "apps" / "api" / ".env",
        Path(".env"),
    ]
    seen = set()
    env_files = []
    for c in candidates:
        try:
            resolved = c.resolve()
            if resolved not in seen:
                seen.add(resolved)
                env_files.append(c)
        except Exception:
            if c not in seen:
                seen.add(c)
                env_files.append(c)
    return tuple(env_files)


_ENV_FILES = _resolve_env_files()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore", case_sensitive=False)

    app_name: str = "PharmaTrust Data Hub"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "development-only-secret-change-me-please"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    database_url: str = "sqlite:///./pharmatrust.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )
    cors_origin_regex: str | None = r"^https?:\/\/(localhost|127\.0\.0\.1|.*\.vercel\.app|.*\.onrender\.com)(:\d+)?$"
    public_api_min_score: int = 85
    storage_root: Path = Path("storage")
    max_upload_mb: int = 20
    allow_public_url_import: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ai_provider: str = "rule_based"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
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

    # Cấu hình Cổng thanh toán MoMo Sandbox (Được nạp từ biến môi trường/file .env, không lưu khóa thật vào code)
    momo_partner_code: str = "MOMO"
    momo_access_key: str = ""
    momo_secret_key: str = ""
    momo_endpoint: str = "https://test-payment.momo.vn/v2/gateway/api/create"
    momo_query_endpoint: str = "https://test-payment.momo.vn/v2/gateway/api/query"
    momo_return_url: str = "http://localhost:3000/checkout/result"
    momo_ipn_url: str = "http://localhost:8000/api/v1/payments/momo/webhook"

    # Cấu hình Cổng thanh toán payOS (Nạp tự động từ biến môi trường/file .env, không in giá trị khóa)
    payos_client_id: str = ""
    payos_api_key: str = ""
    payos_checksum_key: str = ""
    payos_return_url: str = "http://localhost:3000/checkout/result"
    payos_cancel_url: str = "http://localhost:3000/checkout/result"

    # Cấu hình Thanh toán Chuyển khoản VietQR (Napas 247)
    vietqr_bank_id: str = "MB"
    vietqr_account_number: str = ""
    vietqr_account_holder: str = ""
    vietqr_webhook_secret: str = ""
    payment_expiry_minutes: int = 30

    # Cấu hình Cổng Thanh toán Chuyển khoản SePay Webhook + VietQR MBBank
    sepay_enabled: bool = False
    sepay_bank_id: str = "MB"
    sepay_account_number: str = ""
    sepay_account_holder: str = ""
    sepay_webhook_secret: str = ""

    # Cấu hình Dịch vụ Bản đồ Google Maps Platform (Places Autocomplete, Geocoding, Routes)
    google_maps_api_key: str = ""
    google_maps_routes_enabled: bool = False

    # Cấu hình Dịch vụ Bản đồ VIETMAP (Reverse Geocoding v4, Services Key)
    vietmap_api_key: str = ""
    vietmap_services_key: str = "" 

    # Cơ chế kiểm soát Payment Simulator (Mặc định TẮT hoàn toàn - Fail Closed)
    enable_payment_simulator: bool = False

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

    @field_validator("database_url", mode="after")
    @classmethod
    def canonicalize_database_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        val = v.strip()
        # Chuẩn hóa postgres:// hoặc postgresql:// từ Render/Neon sang postgresql+psycopg:// (psycopg 3)
        if val.startswith("postgres://"):
            val = "postgresql+psycopg://" + val[len("postgres://"):]
        elif val.startswith("postgresql://") and not val.startswith("postgresql+"):
            val = "postgresql+psycopg://" + val[len("postgresql://"):]
        elif val.startswith("sqlite:///") and not val.startswith("sqlite:///:memory:"):
            raw_path = val[len("sqlite:///"):]
            if raw_path.startswith("./"):
                raw_path = raw_path[2:]
            path_obj = Path(raw_path)
            if not path_obj.is_absolute():
                canonical_db = (_REPO_ROOT / path_obj).resolve()
                return f"sqlite:///{canonical_db.as_posix()}"
        return val

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        env = (self.app_env or "").lower().strip()
        if env in {"production", "prod", "staging"}:
            if self.database_url.lower().startswith("sqlite"):
                raise ValueError(
                    "BẢO MẬT & TOÀN VẸN CSDL: Môi trường production/staging bắt buộc phải dùng CSDL dùng chung (PostgreSQL), tuyệt đối không được dùng SQLite cục bộ vì nguy cơ chia tách dữ liệu giữa các tiến trình worker."
                )
            if (
                not self.secret_key
                or self.secret_key == "development-only-secret-change-me-please"
                or len(self.secret_key) < 32
            ):
                raise ValueError(
                    "BẢO MẬT SẢN PHẨM: Môi trường production/staging bắt buộc phải cung cấp SECRET_KEY bảo mật từ biến môi trường (tối thiểu 32 ký tự), không được dùng secret mặc định."
                )
            if self.enable_payment_simulator:
                raise ValueError(
                    "BẢO MẬT SẢN PHẨM: Tuyệt đối không được kích hoạt ENABLE_PAYMENT_SIMULATOR=True trên môi trường production/staging."
                )
        return self

    @property
    def is_smtp_configured(self) -> bool:
        """Kiểm tra xem SMTP đã được bật và cấu hình đầy đủ tài khoản hay chưa."""
        return bool(
            self.smtp_enabled
            and self.smtp_user
            and self.smtp_user.strip()
            and self.smtp_password
            and self.smtp_password.strip()
            and self.smtp_host
            and self.smtp_host.strip()
        )

    @property
    def is_momo_configured(self) -> bool:
        """Kiểm tra xem MoMo Sandbox/Production đã được cấu hình đầy đủ API keys chưa."""
        return bool(
            self.momo_partner_code
            and self.momo_partner_code.strip()
            and self.momo_access_key
            and self.momo_access_key.strip()
            and self.momo_secret_key
            and self.momo_secret_key.strip()
        )

    @property
    def is_momo_production(self) -> bool:
        """Xác định cổng MoMo đang trỏ tới Production (Tiền thật) hay Sandbox (Thử nghiệm)."""
        return "test-payment.momo.vn" not in self.momo_endpoint.lower() and self.momo_partner_code != "MOMO"

    @property
    def is_payos_configured(self) -> bool:
        """Kiểm tra xem payOS đã được cấu hình đầy đủ API keys chưa."""
        return bool(
            self.payos_client_id
            and self.payos_client_id.strip()
            and self.payos_api_key
            and self.payos_api_key.strip()
            and self.payos_checksum_key
            and self.payos_checksum_key.strip()
        )

    @property
    def is_sepay_configured(self) -> bool:
        """Kiểm tra xem SePay đã được cấu hình tài khoản MBBank hay chưa."""
        return bool(
            self.sepay_account_number
            and self.sepay_account_number.strip()
            and self.sepay_account_holder
            and self.sepay_account_holder.strip()
        )

    @property
    def is_google_maps_configured(self) -> bool:
        """Kiểm tra xem Google Maps API Key đã được cấu hình hợp lệ hay chưa."""
        key = (self.google_maps_api_key or "").strip()
        return bool(key and len(key) >= 15 and not key.startswith("your_"))

    @property
    def is_vietmap_configured(self) -> bool:
        """Kiểm tra xem VIETMAP API Key (Services Key) đã được cấu hình hợp lệ hay chưa."""
        key = (self.vietmap_services_key or self.vietmap_api_key or "").strip()
        return bool(key and len(key) >= 10 and not key.startswith("your_"))

    @property
    def active_vietmap_key(self) -> str:
        """Lấy VIETMAP Services Key hiệu lực (hỗ trợ cả VIETMAP_SERVICES_KEY và VIETMAP_API_KEY)."""
        return (self.vietmap_services_key or self.vietmap_api_key or "").strip()

    @property
    def is_simulator_permitted(self) -> bool:
        """
        Cơ chế Fail-Closed: Chỉ cho phép chạy Simulator khi đồng thời thỏa mãn:
        1. Biến môi trường app_env thuộc nhóm ['development', 'dev', 'test', 'local'].
        2. Biến enable_payment_simulator được bật tường minh là True.
        Tuyệt đối chặn khi chạy trên production, staging, public hoặc khi biến bị thiếu/sai.
        """
        env = (self.app_env or "").lower().strip()
        return env in {"development", "dev", "test", "local"} and bool(self.enable_payment_simulator)

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
