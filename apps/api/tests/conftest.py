import os
from pathlib import Path

import pytest


TEST_DB = Path(__file__).parent / "test_pharmatrust.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests"
os.environ["STORAGE_ROOT"] = str(Path(__file__).parent / "test_storage")
os.environ["APP_ENV"] = "test"
os.environ["ENABLE_PAYMENT_SIMULATOR"] = "true"
os.environ["MOMO_PARTNER_CODE"] = "MOMO"
os.environ["MOMO_ACCESS_KEY"] = "test_momo_access_key"
os.environ["MOMO_SECRET_KEY"] = "test_momo_secret_key"
os.environ["VIETQR_WEBHOOK_SECRET"] = "test_vietqr_secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.models  # noqa: F401, E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_administrative_units, seed_demo_products, seed_sources, seed_users  # noqa: E402
from app.services.category_service import seed_standard_categories_and_types  # noqa: E402

# Đảm bảo môi trường kiểm thử được bật simulator và sandbox keys
settings.enable_payment_simulator = True
settings.momo_partner_code = "MOMO"
settings.momo_access_key = "test_momo_access_key"
settings.momo_secret_key = "test_momo_secret_key"
settings.vietqr_webhook_secret = "test_vietqr_secret"


@pytest.fixture(scope="session", autouse=True)
def database():
    target_db_str = str(engine.url).lower()
    # Guard: TUYỆT ĐỐI không được drop hoặc thao tác trên database vận hành
    if ("pharmatrust.db" in target_db_str and "test_" not in target_db_str) or ("operational" in target_db_str):
        raise RuntimeError(
            f"SECURITY GUARD ABORT: Test suite is configured to target operational database: {engine.url}. "
            "Tests must ONLY run against isolated test database (e.g., test_pharmatrust.db)."
        )

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        from app.services.search_service import init_fts_table
        init_fts_table(db)
        seed_users(db)
        seed_sources(db)
        seed_administrative_units(db)
        seed_standard_categories_and_types(db)
        db.commit()
        seed_demo_products(db)
        db.commit()
        from app.services.warehouse_seeder import seed_warehouses_and_managers, seed_distributed_inventory
        seed_warehouses_and_managers(db)
        seed_distributed_inventory(db)
        db.commit()
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except (PermissionError, OSError):
            pass


@pytest.fixture
def client(database):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@pharmatrust.vn", "password": "Admin@123456"},
    )
    if response.status_code == 200:
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    # Fallback to direct token if rate limited during automated test suites
    token = create_access_token("1", "ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@pharmatrust.vn", "password": "Viewer@123456"},
    )
    if response.status_code == 200:
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    token = create_access_token("2", "VIEWER")
    return {"Authorization": f"Bearer {token}"}



@pytest.fixture
def manager_hcm_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "manager_hcm@pharmatrust.vn", "password": "Warehouse@2026"},
    )
    if response.status_code != 200:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "manager_hcm@pharmatrust.vn", "password": "Warehouse@2026!"},
        )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def manager_hn_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "manager_hn@pharmatrust.vn", "password": "Warehouse@2026"},
    )
    if response.status_code != 200:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "manager_hn@pharmatrust.vn", "password": "Warehouse@2026!"},
        )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def staff_hcm_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "staff.hcm@pharmatrust.vn", "password": "Staff@2026"},
    )
    if response.status_code != 200:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "staff_hcm@pharmatrust.vn", "password": "Staff@2026"},
        )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
