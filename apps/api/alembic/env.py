from logging.config import fileConfig
from typing import Optional, Any

from alembic import context
from alembic.ddl.impl import DefaultImpl
from sqlalchemy import (
    Column,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    engine_from_config,
    pool,
)

from app.core.config import settings
from app.db.base import Base
from app import models  # noqa: F401

config = context.config

# Alembic mặc định tạo cột version_num với kiểu String(32).
# Trên PostgreSQL, các revision ID có độ dài vượt quá 32 ký tự (ví dụ:
# 0003_after_sales_security_and_vouchers có 38 ký tự, 0006_user_account_security_and_management có 41 ký tự)
# sẽ gây ra lỗi nghiêm trọng: psycopg.errors.StringDataRightTruncation: value too long for type character varying(32).
# Ghi đè hook version_table_impl sang String(255) để Alembic sinh DDL an toàn cho mọi dialect.
def _custom_version_table_impl(
    self,
    *,
    version_table: str,
    version_table_schema: Optional[str] = None,
    version_table_pk: bool = True,
    **kw: Any,
) -> Table:
    vt = Table(
        version_table,
        MetaData(),
        Column("version_num", String(255), nullable=False),
        schema=version_table_schema,
    )
    if version_table_pk:
        vt.append_constraint(
            PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
        )
    return vt

DefaultImpl.version_table_impl = _custom_version_table_impl


def _canonicalize_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _determine_effective_url() -> str:
    """Xác định database URL chính xác cho Alembic migration.

    Quy tắc ưu tiên:
    1. Trên môi trường staging hoặc production: BẮT BUỘC sử dụng settings.database_url (đọc từ biến
       môi trường Render DATABASE_URL). Nghiêm cấm tuyệt đối việc fallback về SQLite làm mất dữ liệu.
    2. Trên môi trường development/testing:
       - Nếu test runner/fixture đã cấu hình URL tường minh vào config (ví dụ temp db trong pytest),
         thì tôn trọng URL đó.
       - Nếu không có URL từ test runner, ưu tiên settings.database_url.
       - Cuối cùng mới fallback về SQLite cục bộ cho dev máy cá nhân.
    """
    app_env = (settings.app_env or "").lower().strip()

    # 1. Chốt chặn an toàn cho Staging & Production
    if app_env in {"production", "prod", "staging"}:
        target_url = settings.database_url
        if not target_url or target_url.lower().startswith("sqlite"):
            raise RuntimeError(
                f"BẢO MẬT & TOÀN VẸN CSDL: Môi trường {app_env} bắt buộc phải dùng PostgreSQL (Neon). "
                "Tuyệt đối không được chạy migration trên SQLite cục bộ vì nguy cơ mất dữ liệu và chia tách worker!"
            )
        return _canonicalize_url(target_url)

    # 2. Môi trường Development / Testing
    # Kiểm tra xem có URL được set tường minh bởi test runner
    cfg_url = config.get_main_option("sqlalchemy.url")
    if cfg_url and cfg_url.strip() and not cfg_url.strip().startswith("%("):
        return _canonicalize_url(cfg_url.strip())

    if settings.database_url and settings.database_url.strip():
        return _canonicalize_url(settings.database_url.strip())

    return "sqlite:///./pharmatrust.db"


eff_url = _determine_effective_url()
config.set_main_option("sqlalchemy.url", eff_url)

if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def _ensure_alembic_version_table_length(connection):
    """Xử lý idempotent việc mở rộng cột alembic_version.version_num lên VARCHAR(255).

    Đặc biệt cần thiết khi database đã có sẵn bảng alembic_version từ các lần chạy trước
    (ví dụ Render đã chạy migration 0001 và 0002 với cột VARCHAR(32)).
    Lệnh ALTER COLUMN TYPE VARCHAR(255) trên PostgreSQL diễn ra tức thời, không làm mất dữ liệu
    và cho phép cập nhật các revision ID dài hơn 32 ký tự mà không gặp lỗi StringDataRightTruncation.
    """
    if connection.dialect.name == "postgresql":
        from sqlalchemy import text

        # 1. Tạo bảng trước nếu chưa có
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "    version_num VARCHAR(255) NOT NULL, "
                "    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            )
        )
        # 2. Mở rộng độ dài cột lên VARCHAR(255) nếu bảng đã tồn tại từ trước với VARCHAR(32)
        connection.execute(
            text(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
            )
        )
        connection.commit()


def run_migrations_offline():
    context.configure(
        url=eff_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = eff_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _ensure_alembic_version_table_length(connection)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
