import io


def test_health_and_login(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    response = client.post("/api/v1/auth/login", json={"email": "admin@pharmatrust.vn", "password": "wrong-password"})
    assert response.status_code == 401


def test_dashboard_and_product_detail(client, admin_headers):
    summary = client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["products"] >= 20
    detail = client.get("/api/v1/products/1", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["is_demo"] is True
    assert detail.json()["latest_score"] is not None


def test_viewer_cannot_create_source(client, viewer_headers):
    response = client.post(
        "/api/v1/sources",
        headers=viewer_headers,
        json={
            "code": "TEST_SOURCE",
            "name": "Nguồn kiểm thử",
            "source_type": "MANUAL_UPLOAD",
            "authority_level": 2,
            "authority_weight": 0.5,
        },
    )
    assert response.status_code == 403


def test_csv_import_is_idempotent(client, admin_headers):
    from app.db.session import SessionLocal
    from app.models import CanonicalProduct, ProductCandidate, RawDocument
    with SessionLocal() as db:
        for r in db.query(ProductCandidate).filter(ProductCandidate.registration_number_text == "DEMO-CSV-01").all():
            db.delete(r)
        for p in db.query(CanonicalProduct).filter_by(registration_number="DEMO-CSV-01").all():
            db.delete(p)
        for doc in db.query(RawDocument).filter(RawDocument.raw_text.contains("DEMO-CSV-01")).all():
            db.delete(doc)
        db.commit()

    sources = client.get("/api/v1/sources", headers=admin_headers).json()
    source_id = next(item["id"] for item in sources if item["code"] == "MANUAL")
    content = "ten_thuoc,so_dang_ky,nha_san_xuat,hoat_chat\nThuoc CSV Demo,DEMO-CSV-01,Cong ty Demo,Hoat chat A 500 mg\n".encode()
    files = {"file": ("products.csv", io.BytesIO(content), "text/csv")}
    data = {"source_id": str(source_id), "is_demo": "true"}
    first = client.post("/api/v1/imports/file", headers=admin_headers, files=files, data=data)
    assert first.status_code == 201
    assert first.json()["created"] == 1
    files = {"file": ("products.csv", io.BytesIO(content), "text/csv")}
    second = client.post("/api/v1/imports/file", headers=admin_headers, files=files, data=data)
    assert second.status_code == 201
    assert second.json()["skipped"] == 1


def test_public_api_excludes_demo_products(client):
    response = client.get("/api/v1/public/products")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_critical_strength_conflict_is_blocked(client, admin_headers):
    response = client.post("/api/v1/products/9/recalculate", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["new_score"] <= 25
    assert body["confidence_label"] == "BLOCKED"


def test_open_medium_conflict_cannot_reach_high_match(client, admin_headers):
    response = client.post("/api/v1/products/12/recalculate", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["new_score"] <= 84
    assert response.json()["confidence_label"] == "REVIEW_REQUIRED"
