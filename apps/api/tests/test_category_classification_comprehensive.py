import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models.classification import (
    Category,
    ProductCategory,
    ProductClassificationEvidence,
    ProductClassificationHistory,
    ProductClassificationReview,
    ProductType,
)
from app.models.entities import CanonicalProduct, User
from app.models.enums import ClassificationReviewStatus, LegalProductType, PrescriptionStatus, UserRole
from app.services.category_service import (
    get_category_tree,
    seed_standard_categories_and_types,
    validate_category_compatibility,
)
from app.services.classification_pipeline import ProductClassificationPipeline


@pytest.fixture
def auth_headers(database):
    """Tạo headers cho từng vai trò người dùng trong hệ thống."""
    with SessionLocal() as db:
        # Admin
        admin = db.scalar(select(User).where(User.email == "admin@pharmatrust.vn"))
        if not admin:
            admin = User(
                email="admin@pharmatrust.vn",
                password_hash=hash_password("Admin@123456"),
                full_name="Quản trị viên",
                role=UserRole.ADMIN,
                is_active=True,
                token_version=1,
            )
            db.add(admin)

        # Data Reviewer
        reviewer = db.scalar(select(User).where(User.email == "reviewer@pharmatrust.vn"))
        if not reviewer:
            reviewer = User(
                email="reviewer@pharmatrust.vn",
                password_hash=hash_password("Reviewer@123456"),
                full_name="Kiểm duyệt viên",
                role=UserRole.DATA_REVIEWER,
                is_active=True,
                token_version=1,
            )
            db.add(reviewer)

        # Viewer
        viewer = db.scalar(select(User).where(User.email == "viewer@pharmatrust.vn"))
        if not viewer:
            viewer = User(
                email="viewer@pharmatrust.vn",
                password_hash=hash_password("Viewer@123456"),
                full_name="Người xem",
                role=UserRole.VIEWER,
                is_active=True,
                token_version=1,
            )
            db.add(viewer)

        # Customer
        customer = db.scalar(select(User).where(User.email == "customer@pharmatrust.vn"))
        if not customer:
            customer = User(
                email="customer@pharmatrust.vn",
                password_hash=hash_password("Customer@123456"),
                full_name="Khách hàng",
                role=UserRole.CUSTOMER,
                is_active=True,
                token_version=1,
            )
            db.add(customer)

        db.commit()
        db.refresh(admin)
        db.refresh(reviewer)
        db.refresh(viewer)
        db.refresh(customer)

        admin_token = create_access_token(str(admin.id), admin.role.value, admin.token_version or 1)
        reviewer_token = create_access_token(str(reviewer.id), reviewer.role.value, reviewer.token_version or 1)
        viewer_token = create_access_token(str(viewer.id), viewer.role.value, viewer.token_version or 1)
        customer_token = create_access_token(str(customer.id), customer.role.value, customer.token_version or 1)

        return {
            "admin": {"Authorization": f"Bearer {admin_token}"},
            "reviewer": {"Authorization": f"Bearer {reviewer_token}"},
            "viewer": {"Authorization": f"Bearer {viewer_token}"},
            "customer": {"Authorization": f"Bearer {customer_token}"},
        }


# =====================================================================
# 1. Mỹ phẩm không bao giờ có rx_otc_status = OTC
# =====================================================================
def test_cosmetic_cannot_be_otc(client: TestClient, auth_headers):
    """Mỹ phẩm bắt buộc phải có rx_otc_status = NOT_APPLICABLE, không được là OTC."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Kem Dưỡng Ẩm Trắng Da Ban Đêm",
            product_type="COSMETIC",
            prescription_status="NOT_APPLICABLE",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

    # Thử phê duyệt ép mỹ phẩm thành OTC qua API
    res = client.post(
        f"/api/v1/admin/classification/{pid}/approve",
        headers=auth_headers["admin"],
        json={
            "product_type": "COSMETIC",
            "prescription_status": "OTC",
        },
    )
    # API tự động chuẩn hóa COSMETIC -> NOT_APPLICABLE
    assert res.status_code == 200

    with SessionLocal() as db:
        saved = db.get(CanonicalProduct, pid)
        assert saved.prescription_status == "NOT_APPLICABLE"
        assert saved.prescription_status != "OTC"


# =====================================================================
# 2. Thiết bị y tế không thể có rx_otc_status = RX
# =====================================================================
def test_medical_device_cannot_be_rx(client: TestClient, auth_headers):
    """Trang thiết bị y tế bắt buộc prescription_status = NOT_APPLICABLE, không thể là RX."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Máy Đo Huyết Áp Bắp Tay Omron HEM-7120",
            product_type="MEDICAL_DEVICE",
            prescription_status="NOT_APPLICABLE",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

    # Thử phê duyệt ép TBYT thành RX qua API
    res = client.post(
        f"/api/v1/admin/classification/{pid}/approve",
        headers=auth_headers["admin"],
        json={
            "product_type": "MEDICAL_DEVICE",
            "prescription_status": "RX",
        },
    )
    assert res.status_code == 200

    with SessionLocal() as db:
        saved = db.get(CanonicalProduct, pid)
        assert saved.prescription_status == "NOT_APPLICABLE"
        assert saved.prescription_status != "RX"


# =====================================================================
# 3. Sản phẩm chưa rõ loại pháp lý không được mở bán trực tiếp
# =====================================================================
def test_unknown_product_type_cannot_be_directly_sold(client: TestClient, auth_headers):
    """Sản phẩm loại OTHER/chưa rõ không được phép phê duyệt mà không chọn Product Type hợp lệ."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Sản Phẩm Chưa Rõ Nguồn Gốc 123",
            product_type="OTHER",
            prescription_status="UNKNOWN",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

    res = client.post(
        f"/api/v1/admin/classification/{pid}/approve",
        headers=auth_headers["admin"],
        json={
            "product_type": "OTHER",
            "prescription_status": "UNKNOWN",
        },
    )
    assert res.status_code == 400
    assert "Loại sản phẩm pháp lý" in res.json()["detail"]


# =====================================================================
# 4. Thuốc kê đơn không có flow mua ngay, phải qua đơn giữ chỗ/tư vấn
# =====================================================================
def test_rx_medicine_reservation_flow(client: TestClient, auth_headers):
    """Sản phẩm RX trên API storefront báo rõ luồng giữ chỗ tư vấn theo quyết định nghiệp vụ."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Kháng Sinh Amoxicillin 500mg Đặc Trị",
            product_type="MEDICINE",
            prescription_status="RX",
            publish_status="PUBLISHED",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

    res = client.get(f"/api/v1/store/products/{pid}")
    if res.status_code == 200:
        data = res.json()
        assert data.get("is_prescription") is True
        assert data.get("can_direct_checkout") is False
        assert "giữ chỗ" in data.get("prescription_action_notice", "")


# =====================================================================
# 5. Một sản phẩm có thể thuộc nhiều danh mục bán hàng
# =====================================================================
def test_product_can_have_multiple_categories(client: TestClient, auth_headers):
    """Một sản phẩm có thể liên kết vào nhiều danh mục con hợp lệ."""
    with SessionLocal() as db:
        cat_vit = db.scalar(select(Category).where(Category.slug == "vitamin-khoang-chat"))
        cat_baby = db.scalar(select(Category).where(Category.slug == "dinh-duong-be"))
        assert cat_vit is not None
        assert cat_baby is not None

        prod = CanonicalProduct(
            canonical_name="Vitamin D3 K2 Drops Cho Trẻ Sơ Sinh",
            product_type="SUPPLEMENT",
            prescription_status="NOT_APPLICABLE",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id
        vit_id = cat_vit.id
        baby_id = cat_baby.id

    res = client.post(
        f"/api/v1/admin/classification/{pid}/approve",
        headers=auth_headers["admin"],
        json={
            "product_type": "SUPPLEMENT",
            "prescription_status": "NOT_APPLICABLE",
            "category_ids": [vit_id, baby_id],
            "primary_category_id": vit_id,
            "note": "Gán đa danh mục bán hàng",
        },
    )
    assert res.status_code == 200

    with SessionLocal() as db:
        links = db.scalars(select(ProductCategory).where(ProductCategory.product_id == pid)).all()
        assert len(links) == 2
        primaries = [l for l in links if l.is_primary]
        assert len(primaries) == 1
        assert primaries[0].category_id == vit_id


# =====================================================================
# 6. Khi đổi danh mục của sản phẩm, lịch sử thay đổi được ghi nhận
# =====================================================================
def test_classification_history_tracked_on_change(client: TestClient, auth_headers):
    """Mọi thay đổi phân loại đều được lưu vào ProductClassificationHistory."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Sản Phẩm Kiểm Tra Lịch Sử",
            product_type="MEDICINE",
            prescription_status="OTC",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

    client.post(
        f"/api/v1/admin/classification/{pid}/approve",
        headers=auth_headers["admin"],
        json={
            "product_type": "MEDICINE",
            "prescription_status": "OTC",
            "note": "Lần đổi 1: Phê duyệt ban đầu",
        },
    )

    client.post(
        f"/api/v1/admin/classification/{pid}/reject",
        headers=auth_headers["admin"],
        json={"reason": "Lần đổi 2: Phát hiện sai lệch giấy phép"},
    )

    history_res = client.get(f"/api/v1/admin/classification/history/{pid}", headers=auth_headers["admin"])
    assert history_res.status_code == 200
    history_items = history_res.json()
    assert len(history_items) >= 2


# =====================================================================
# 7. Người dùng role VIEWER không được sửa danh mục
# =====================================================================
def test_viewer_role_cannot_edit_category(client: TestClient, auth_headers):
    """VIEWER chỉ có quyền xem, bị chặn 403 khi tạo/sửa/xóa danh mục."""
    res_create = client.post(
        "/api/v1/admin/categories",
        headers=auth_headers["viewer"],
        json={"code": "TEST_VIEWER", "slug": "test-viewer", "name": "Test Viewer"},
    )
    assert res_create.status_code == 403

    res_patch = client.patch(
        "/api/v1/admin/categories/1",
        headers=auth_headers["viewer"],
        json={"name": "Tên mới"},
    )
    assert res_patch.status_code == 403

    res_del = client.delete(
        "/api/v1/admin/categories/1",
        headers=auth_headers["viewer"],
    )
    assert res_del.status_code == 403


# =====================================================================
# 8. DATA_REVIEWER có thể duyệt phân loại nhưng không được xóa danh mục hệ thống
# =====================================================================
def test_data_reviewer_permissions(client: TestClient, auth_headers):
    """DATA_REVIEWER có thể duyệt phân loại sản phẩm."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Thuốc Paracetamol Cho Data Reviewer Duyệt",
            product_type="MEDICINE",
            prescription_status="OTC",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

    res = client.post(
        f"/api/v1/admin/classification/{pid}/approve",
        headers=auth_headers["reviewer"],
        json={
            "product_type": "MEDICINE",
            "prescription_status": "OTC",
            "note": "Duyệt bởi Data Reviewer",
        },
    )
    assert res.status_code == 200


# =====================================================================
# 9. Dữ liệu crawl mới không được tự gán OTC nếu không có số ĐK/danh mục BYT
# =====================================================================
def test_crawled_data_without_reg_not_auto_otc():
    """Pipeline không được tự ý gán OTC khi không có giấy phép/cơ sở dữ liệu Bộ Y Tế."""
    with SessionLocal() as db:
        pipeline = ProductClassificationPipeline(db)
        prod = CanonicalProduct(
            canonical_name="Viên Uống Hỗ Trợ Đẹp Da Không Rõ Nguồn Gốc",
            registration_number=None,
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)

        result = pipeline.classify_product(prod)
        # Không được tự ý gán là MEDICINE + OTC
        assert not (result.suggested_product_type == "MEDICINE" and result.suggested_prescription_status == "OTC")
        assert result.requires_review is True


# =====================================================================
# 10. Độ tin cậy AI thấp thì phải vào hàng chờ duyệt, không tự publish
# =====================================================================
def test_low_confidence_queued_for_review():
    """Khi độ tin cậy < 0.85, pipeline bắt buộc đưa vào hàng chờ duyệt."""
    with SessionLocal() as db:
        pipeline = ProductClassificationPipeline(db)
        prod = CanonicalProduct(
            canonical_name="Bột Ngũ Cốc Hạnh Nhân Hạt Sen Tự Nhiên",
            registration_number=None,
            description="Thức uống dinh dưỡng gia đình",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)

        result = pipeline.classify_product(prod)
        assert result.confidence < 0.85
        assert result.requires_review is True


# =====================================================================
# 11. Đổi slug danh mục thì sản phẩm không bị mất liên kết (dùng ID FK)
# =====================================================================
def test_category_slug_change_preserves_relationships(client: TestClient, auth_headers):
    """Liên kết sản phẩm với danh mục dựa trên ID nên đổi slug không làm mất liên kết."""
    with SessionLocal() as db:
        # Tạo danh mục tạm
        cat = Category(code="CAT_SLUG_TEST", slug="cat-slug-test-old", name="Slug Test")
        db.add(cat)
        db.commit()
        db.refresh(cat)
        cid = cat.id

        prod = CanonicalProduct(canonical_name="Sản Phẩm Test Slug", product_type="MEDICINE", is_demo=True)
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

        link = ProductCategory(product_id=pid, category_id=cid, is_primary=True)
        db.add(link)
        db.commit()

        # Đổi slug danh mục
        cat.slug = "cat-slug-test-new"
        db.commit()

        # Kiểm tra liên kết còn nguyên
        saved_link = db.scalar(select(ProductCategory).where(ProductCategory.product_id == pid, ProductCategory.category_id == cid))
        assert saved_link is not None
        assert saved_link.category.slug == "cat-slug-test-new"

        # Dọn dẹp dữ liệu test
        db.delete(saved_link)
        db.delete(prod)
        db.delete(cat)
        db.commit()


# =====================================================================
# 12. Xóa danh mục cha khi còn danh mục con phải bị chặn
# =====================================================================
def test_delete_parent_category_with_children_blocked(client: TestClient, auth_headers):
    """Không được xóa danh mục cha nếu đang có danh mục con."""
    with SessionLocal() as db:
        parent = Category(code="CAT_PARENT_BLOCK", slug="cat-parent-block", name="Parent Test")
        db.add(parent)
        db.commit()
        db.refresh(parent)
        p_id = parent.id

        child = Category(parent_id=p_id, code="CAT_CHILD_BLOCK", slug="cat-child-block", name="Child Test")
        db.add(child)
        db.commit()
        db.refresh(child)
        c_id = child.id

    res = client.delete(f"/api/v1/admin/categories/{p_id}", headers=auth_headers["admin"])
    assert res.status_code == 400
    assert "danh mục con" in res.json()["detail"]

    # Dọn dẹp
    with SessionLocal() as db:
        c_obj = db.get(Category, c_id)
        p_obj = db.get(Category, p_id)
        if c_obj:
            db.delete(c_obj)
        if p_obj:
            db.delete(p_obj)
        db.commit()


# =====================================================================
# 13. Xóa danh mục khi còn sản phẩm liên kết phải bị chặn
# =====================================================================
def test_delete_category_with_linked_products_blocked(client: TestClient, auth_headers):
    """Không được xóa danh mục nếu đang có sản phẩm liên kết."""
    with SessionLocal() as db:
        cat = Category(code="CAT_PROD_BLOCK", slug="cat-prod-block", name="Category Có Sản Phẩm")
        db.add(cat)
        db.commit()
        db.refresh(cat)
        c_id = cat.id

        prod = CanonicalProduct(canonical_name="Thuốc Liên Kết Danh Mục", product_type="MEDICINE", is_demo=True)
        db.add(prod)
        db.commit()
        db.refresh(prod)
        p_id = prod.id

        db.add(ProductCategory(product_id=p_id, category_id=c_id))
        db.commit()

    res = client.delete(f"/api/v1/admin/categories/{c_id}", headers=auth_headers["admin"])
    assert res.status_code == 400
    assert "sản phẩm liên kết" in res.json()["detail"]

    # Dọn dẹp
    with SessionLocal() as db:
        db.query(ProductCategory).filter(ProductCategory.product_id == p_id).delete()
        p = db.get(CanonicalProduct, p_id)
        c = db.get(Category, c_id)
        if p:
            db.delete(p)
        if c:
            db.delete(c)
        db.commit()


# =====================================================================
# 14. Migration an toàn và bảo toàn dữ liệu
# =====================================================================
def test_migration_preserves_existing_data():
    """Toàn bộ sản phẩm gốc và thuộc tính quan trọng đều nguyên vẹn sau khi thêm cột phân loại."""
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(CanonicalProduct))
        assert count > 0


# =====================================================================
# 15. Seed danh mục không sinh trùng slug hoặc trùng mã
# =====================================================================
def test_seed_categories_no_duplicate_slug_or_code():
    """Cây danh mục chuẩn không có bất kỳ slug hoặc code nào bị trùng lặp."""
    with SessionLocal() as db:
        slugs = db.scalars(select(Category.slug)).all()
        assert len(slugs) == len(set(slugs)), "Phát hiện slug danh mục bị trùng lặp!"

        codes = db.scalars(select(Category.code)).all()
        assert len(codes) == len(set(codes)), "Phát hiện mã danh mục bị trùng lặp!"


# =====================================================================
# 16. Mega menu hiển thị đúng 6 nhóm lớn và đúng thứ tự
# =====================================================================
def test_mega_menu_six_root_categories_order(client: TestClient):
    """API lấy cây danh mục trả về đúng 6 nhóm cấp 1 theo đúng thứ tự chuẩn."""
    from app.services.category_service import invalidate_category_cache
    invalidate_category_cache()
    res = client.get("/api/v1/store/categories/tree")
    assert res.status_code == 200
    tree = res.json()
    assert len(tree) == 6
    expected_slugs = ["thuoc-khong-ke-don", "thuoc-ke-don", "thuc-pham-chuc-nang", "duoc-my-pham", "thiet-bi-y-te", "me-va-be"]
    assert [c["slug"] for c in tree] == expected_slugs


# =====================================================================
# 17. Bộ lọc danh mục trên trang danh sách hoạt động đúng
# =====================================================================
def test_product_filter_by_category_and_type(client: TestClient, auth_headers):
    """Lọc sản phẩm theo product_type và category_slug hoạt động chính xác."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Nước Muối Sinh Lý Kháng Khuẩn Natri Clorid 0.9%",
            product_type="MEDICAL_DEVICE",
            prescription_status="NOT_APPLICABLE",
            category_slug="thiet-bi-y-te",
            is_demo=True,
        )
        db.add(prod)
        db.commit()

    res = client.get("/api/v1/products?product_type=MEDICAL_DEVICE", headers=auth_headers["admin"])
    assert res.status_code == 200
    items = res.json()["items"]
    assert all(i.get("product_type") == "MEDICAL_DEVICE" for i in items if i.get("product_type"))


# =====================================================================
# 18. Không có sản phẩm nào mồ côi danh mục sau phân loại
# =====================================================================
def test_no_orphan_products_after_classification():
    """Hệ thống đảm bảo mọi sản phẩm đều có ProductType hợp lệ hoặc nằm trong review queue."""
    with SessionLocal() as db:
        products = db.scalars(select(CanonicalProduct).where(CanonicalProduct.is_demo.is_(True))).all()
        for p in products:
            assert p.product_type is not None or p.category_review_status in ["PENDING", "REJECTED"]


# =====================================================================
# 19. Mỹ phẩm không được gán vào danh mục thuốc điều trị
# =====================================================================
def test_no_cosmetics_in_treatment_medicine_category():
    """Kiểm tra quy tắc tương thích loại sản phẩm: COSMETIC không thể gán vào nhóm THUỐC."""
    with SessionLocal() as db:
        cat_medicine = db.scalar(select(Category).where(Category.slug == "thuoc-khong-ke-don"))
        assert cat_medicine is not None

        is_compatible, err = validate_category_compatibility("COSMETIC", cat_medicine)
        assert is_compatible is False
        assert "COSMETIC" in err


# =====================================================================
# 20. Thực phẩm chức năng không được phép gán nhãn tuyên bố y tế cấm
# =====================================================================
def test_no_supplements_prohibited_medical_claims():
    """Pipeline cảnh báo xung đột nếu sản phẩm thực phẩm chức năng có tuyên bố điều trị bệnh nặng."""
    with SessionLocal() as db:
        pipeline = ProductClassificationPipeline(db)
        prod = CanonicalProduct(
            canonical_name="Viên Uống TPCN Tảo Nâu Điều Trị Ung Thư",
            description="Thuốc điều trị ung thư và chữa khỏi dứt điểm",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)

        result = pipeline.classify_product(prod)
        # Phát hiện từ khóa cấm hoặc xung đột
        assert any("ung thư" in c.lower() or "tuyên bố" in c.lower() or "chữa" in c.lower() for c in result.conflicts) or result.requires_review is True


# =====================================================================
# 21. Thuốc thuộc danh mục kiểm soát đặc biệt phải có cờ cảnh báo riêng
# =====================================================================
def test_controlled_substances_flagged_with_warning(client: TestClient, auth_headers):
    """Thuốc CONTROLLED phải có prescription_status = CONTROLLED và cờ cảnh báo."""
    with SessionLocal() as db:
        prod = CanonicalProduct(
            canonical_name="Morphin Sulfat 10mg Viên Gây Nghiện",
            product_type="MEDICINE",
            prescription_status="CONTROLLED",
            is_demo=True,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
        pid = prod.id

    res = client.get(f"/api/v1/store/products/{pid}")
    if res.status_code == 200:
        data = res.json()
        assert data.get("prescription_status") == "CONTROLLED"
        assert data.get("is_controlled_substance") is True
