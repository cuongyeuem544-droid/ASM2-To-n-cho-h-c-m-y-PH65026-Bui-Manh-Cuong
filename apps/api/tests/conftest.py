import os
from pathlib import Path

import pytest


TEST_DB = Path(__file__).parent / "test_pharmatrust.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests"
os.environ["STORAGE_ROOT"] = str(Path(__file__).parent / "test_storage")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_administrative_units, seed_demo_products, seed_sources, seed_users  # noqa: E402
from app.services.category_service import seed_standard_categories_and_types  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
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
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def viewer_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@pharmatrust.vn", "password": "Viewer@123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def manager_hcm_headers(client):
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
        json={"email": "manager_hn@pharmatrust.vn", "password": "Warehouse@2026!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

