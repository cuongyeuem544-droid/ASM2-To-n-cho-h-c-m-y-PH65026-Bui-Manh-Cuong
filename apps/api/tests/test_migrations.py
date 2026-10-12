import os
import tempfile
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


@pytest.fixture
def temp_alembic_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_migration_upgrade_and_downgrade(temp_alembic_db):
    """
    Kiểm tra luồng nâng cấp từ 0001 -> 0002 -> 0003 và hạ cấp an toàn về 0002.
    Đảm bảo tính lặp lại (idempotent) và toàn vẹn của schema mới.
    """
    db_url = f"sqlite:///{temp_alembic_db.replace(chr(92), '/')}"
    
    # Configure alembic pointing to test db
    alembic_ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    
    # 1. Upgrade to head (0003)
    command.upgrade(alembic_cfg, "head")
    
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables_0003 = set(inspector.get_table_names())
    assert "warehouses" in tables_0003
    assert "return_requests" in tables_0003
    assert "refunds" in tables_0003
    assert "user_otps" in tables_0003
    assert "password_reset_tokens" in tables_0003
    assert "vouchers" in tables_0003
    
    order_cols = {col["name"] for col in inspector.get_columns("orders")}
    assert "idempotency_key" in order_cols
    assert "voucher_code" in order_cols
    assert "discount_amount" in order_cols
    
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    assert "token_version" in user_cols
    
    # 2. Test Re-run upgrade (Idempotency)
    command.upgrade(alembic_cfg, "head")
    
    # 3. Downgrade back to 0002
    command.downgrade(alembic_cfg, "0002_inventory_warehouse_batch")
    
    inspector = inspect(engine)
    tables_downgraded = set(inspector.get_table_names())
    assert "user_otps" not in tables_downgraded
    assert "vouchers" not in tables_downgraded
    assert "warehouses" in tables_downgraded
    
    # 4. Upgrade back to head from 0002
    command.upgrade(alembic_cfg, "head")
    inspector = inspect(engine)
    tables_reupgraded = set(inspector.get_table_names())
    assert "user_otps" in tables_reupgraded
    assert "vouchers" in tables_reupgraded
    
    engine.dispose()
