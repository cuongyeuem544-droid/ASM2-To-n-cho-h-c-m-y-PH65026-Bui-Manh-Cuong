from pathlib import Path
import pytest

from app.services.normalization import normalize_registration_number, normalize_for_match


def test_dline22_technical_normalization_preserved():
    """Kiểm tra các hàm normalize chuỗi / sanitize / chuẩn hóa chuỗi kỹ thuật cơ bản vẫn hoạt động bình thường."""
    reg = normalize_registration_number("  VD-12345-20  ")
    assert reg == "VD-12345-20"

    norm_match = normalize_for_match("Paracetamol 500mg Hộp 10 Vỉ")
    assert "paracetamol" in norm_match
    assert "500mg" in norm_match


def test_dline22_admin_ui_and_storefront_normalization_removed():
    """Kiểm tra mã nguồn frontend web & storefront đã dọn sạch crawler và nhãn chuẩn hóa thuốc."""
    root_dir = Path(__file__).resolve().parent.parent.parent.parent

    # 1. Admin Web
    app_tsx = (root_dir / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "PharmacyCrawlerPage" not in app_tsx
    assert "pharmacy-crawler" not in app_tsx

    # File PharmacyCrawlerPage.tsx phải không còn tồn tại
    crawler_page = root_dir / "apps" / "web" / "src" / "pages" / "PharmacyCrawlerPage.tsx"
    assert not crawler_page.exists(), "PharmacyCrawlerPage.tsx must be completely deleted"

    # ProductDetailPage.tsx không còn 'Thông tin chuẩn hóa' và 'Giá trị chuẩn hóa'
    prod_detail_tsx = (root_dir / "apps" / "web" / "src" / "pages" / "ProductDetailPage.tsx").read_text(encoding="utf-8")
    assert "Thông tin chuẩn hóa" not in prod_detail_tsx
    assert "Giá trị chuẩn hóa" not in prod_detail_tsx

    # ProductsPage.tsx không còn 'Danh mục thuốc chuẩn hóa'
    products_page_tsx = (root_dir / "apps" / "web" / "src" / "pages" / "ProductsPage.tsx").read_text(encoding="utf-8")
    assert "Danh mục thuốc chuẩn hóa" not in products_page_tsx

    # 2. Storefront
    transparency_card = (root_dir / "apps" / "storefront" / "src" / "components" / "product" / "ProductTransparencyCard.tsx").read_text(encoding="utf-8")
    assert "% chuẩn hóa" not in transparency_card

    filter_sidebar = (root_dir / "apps" / "storefront" / "src" / "components" / "product" / "ProductFilterSidebar.tsx").read_text(encoding="utf-8")
    assert "100% Sản phẩm chuẩn hóa" not in filter_sidebar

    image_stage = (root_dir / "apps" / "storefront" / "src" / "components" / "product" / "ProductImageStage.tsx").read_text(encoding="utf-8")
    assert "Viên Nang Chuẩn Hóa" not in image_stage

    about_page = (root_dir / "apps" / "storefront" / "src" / "app" / "about-project" / "page.tsx").read_text(encoding="utf-8")
    assert "25 Sản Phẩm Chuẩn Hóa" not in about_page
