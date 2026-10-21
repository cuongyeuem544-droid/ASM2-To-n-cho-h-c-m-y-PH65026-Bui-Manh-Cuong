import pytest
from fastapi.testclient import TestClient
from app.api.storefront import get_category_products, get_store_products
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


def test_get_category_products_api_endpoint(database):
    """Xác minh endpoint /api/v1/store/categories/{slug}/products hoạt động không lỗi 500."""
    response = client.get("/api/v1/store/categories/thuoc-khong-ke-don/products")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_get_category_products_direct_python_call(database):
    """Xác minh gọi trực tiếp get_category_products và get_store_products không bị lỗi Query object."""
    with SessionLocal() as db:
        res1 = get_category_products(slug="thuoc-khong-ke-don", db=db)
        assert isinstance(res1, dict)
        assert "items" in res1
        assert "total" in res1

        res2 = get_store_products(category="giam-dau-ha-sot", db=db)
        assert isinstance(res2, dict)
        assert "items" in res2
        assert "total" in res2
