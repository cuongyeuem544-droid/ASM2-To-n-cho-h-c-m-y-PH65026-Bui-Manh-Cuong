"""
apps/api/tests/test_administrative_v2_comprehensive.py

COMPREHENSIVE TEST SUITE - VIETNAM ADMINISTRATIVE SYSTEM 2025 (CRITICAL FIX #4)
Căn cứ: Quyết định 19/2025/QĐ-TTg & Nghị quyết 202/2025/QH15.
Effective Date: 2025-07-01
Version: VN_ADMIN_2025_07_01

Nội dung kiểm thử:
1. 34 đơn vị hành chính cấp tỉnh (6 thành phố trực thuộc Trung ương, 28 tỉnh).
2. 3.321 đơn vị hành chính cấp xã (xã, phường, đặc khu).
3. 23 nhóm sáp nhập cấp tỉnh (Legacy Merger Mapping Test Matrix).
4. 11 tỉnh/thành không sáp nhập cấp tỉnh.
5. 7 đặc khu hành chính (Phú Quốc, Vân Đồn, Côn Đảo, Lý Sơn, Cô Tô, Trường Sa, Hoàng Sa).
6. Phường Nam Định và 8 phường khu vực Nam Định cũ tại Tỉnh Ninh Bình.
7. Ánh xạ thành phần nhà cung cấp Geocoding (Google Places / Nominatim).
8. SQLite Database Integrity (administrative_provinces, administrative_communes, administrative_mergers, administrative_aliases).
"""

import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.administrative_service import AdministrativeDataService
from app.services.administrative_resolver import VietnamAdministrativeResolver


@pytest.fixture(autouse=True, scope="module")
def setup_34_model():
    from pathlib import Path
    json_34 = Path("data/vietnam-administrative-units-34.json")
    if not json_34.exists():
        json_34 = Path(__file__).resolve().parent.parent.parent / "data" / "vietnam-administrative-units-34.json"
    AdministrativeDataService.initialize(str(json_34))
    VietnamAdministrativeResolver.initialize(str(json_34))
    yield
    AdministrativeDataService.initialize()
    VietnamAdministrativeResolver.initialize()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ==============================================================================
# TEST SUITE 1: CANONICAL 34 PROVINCES & 3,321 COMMUNES
# ==============================================================================

def test_canonical_provinces_count_and_types():
    provinces = AdministrativeDataService.get_provinces()
    assert len(provinces) == 34, f"Số tỉnh phải là 34, thực tế: {len(provinces)}"

    municipalities = [p for p in provinces if p["type"] == "municipality"]
    provs = [p for p in provinces if p["type"] == "province"]

    assert len(municipalities) == 6, f"Số TP trực thuộc TW phải là 6, thực tế: {len(municipalities)}"
    assert len(provs) == 28, f"Số Tỉnh phải là 28, thực tế: {len(provs)}"

    # 6 Municipalities must be Hà Nội, TP.HCM, Hải Phòng, Đà Nẵng, Cần Thơ, Huế
    muni_codes = {p["code"] for p in municipalities}
    expected_muni_codes = {"01", "79", "31", "48", "92", "46"}
    assert muni_codes == expected_muni_codes, f"Mã 6 TP trực thuộc TW sai: {muni_codes}"


def test_canonical_communes_count_and_no_orphans():
    VietnamAdministrativeResolver._ensure_loaded()
    communes = VietnamAdministrativeResolver._communes
    assert len(communes) == 3321, f"Số xã phải là 3321, thực tế: {len(communes)}"

    prov_codes = {p["code"] for p in VietnamAdministrativeResolver._provinces}
    for c in communes:
        assert c["provinceCode"] in prov_codes, f"Xã mồ côi: {c['name']} (mã tỉnh: {c['provinceCode']})"
        assert c["type"] in {"ward", "commune", "special_zone"}, f"Loại xã sai: {c['type']}"


def test_special_zones():
    VietnamAdministrativeResolver._ensure_loaded()
    special_zones = [c for c in VietnamAdministrativeResolver._communes if c["type"] == "special_zone"]
    assert len(special_zones) >= 7, f"Số đặc khu phải >= 7, thực tế: {len(special_zones)}"

    sz_map = {sz["name"]: sz for sz in special_zones}
    assert "Phú Quốc" in sz_map and sz_map["Phú Quốc"]["provinceCode"] == "89"  # An Giang
    assert "Vân Đồn" in sz_map and sz_map["Vân Đồn"]["provinceCode"] == "22"   # Quảng Ninh
    assert "Côn Đảo" in sz_map and sz_map["Côn Đảo"]["provinceCode"] == "79"   # TP.HCM
    assert "Lý Sơn" in sz_map and sz_map["Lý Sơn"]["provinceCode"] == "51"     # Quảng Ngãi
    assert "Cô Tô" in sz_map and sz_map["Cô Tô"]["provinceCode"] == "22"       # Quảng Ninh
    assert "Trường Sa" in sz_map and sz_map["Trường Sa"]["provinceCode"] == "56" # Khánh Hòa
    assert "Hoàng Sa" in sz_map and sz_map["Hoàng Sa"]["provinceCode"] == "48" # Đà Nẵng


# ==============================================================================
# TEST SUITE 2: TEST MATRIX - TOÀN BỘ 23 NHÓM SÁP NHẬP
# ==============================================================================

MERGER_TEST_MATRIX = [
    ("Tuyên Quang", "08", ["Hà Giang", "Tuyên Quang"]),
    ("Lào Cai", "10", ["Yên Bái", "Lào Cai"]),
    ("Thái Nguyên", "19", ["Bắc Kạn", "Thái Nguyên"]),
    ("Phú Thọ", "25", ["Vĩnh Phúc", "Hòa Bình", "Phú Thọ"]),
    ("Bắc Ninh", "27", ["Bắc Giang", "Bắc Ninh"]),
    ("Hưng Yên", "33", ["Thái Bình", "Hưng Yên"]),
    ("Hải Phòng", "31", ["Hải Dương", "Hải Phòng"]),
    ("Ninh Bình", "37", ["Hà Nam", "Nam Định", "Ninh Bình"]),
    ("Quảng Trị", "45", ["Quảng Bình", "Quảng Trị"]),
    ("Đà Nẵng", "48", ["Quảng Nam", "Đà Nẵng"]),
    ("Quảng Ngãi", "51", ["Kon Tum", "Quảng Ngãi"]),
    ("Gia Lai", "64", ["Bình Định", "Gia Lai"]),
    ("Khánh Hòa", "56", ["Ninh Thuận", "Khánh Hòa"]),
    ("Lâm Đồng", "68", ["Đắk Nông", "Bình Thuận", "Lâm Đồng"]),
    ("Đắk Lắk", "66", ["Phú Yên", "Đắk Lắk"]),
    ("Hồ Chí Minh", "79", ["Bình Dương", "Bà Rịa - Vũng Tàu", "Hồ Chí Minh"]),
    ("Đồng Nai", "75", ["Bình Phước", "Đồng Nai"]),
    ("Tây Ninh", "72", ["Long An", "Tây Ninh"]),
    ("Cần Thơ", "92", ["Sóc Trăng", "Hậu Giang", "Cần Thơ"]),
    ("Vĩnh Long", "86", ["Bến Tre", "Trà Vinh", "Vĩnh Long"]),
    ("Đồng Tháp", "87", ["Tiền Giang", "Đồng Tháp"]),
    ("Cà Mau", "96", ["Bạc Liêu", "Cà Mau"]),
    ("An Giang", "89", ["Kiên Giang", "An Giang"]),
]


@pytest.mark.parametrize("target_name, target_code, old_provinces", MERGER_TEST_MATRIX)
def test_all_23_merger_groups(target_name, target_code, old_provinces):
    # Kiểm tra tỉnh đích tồn tại
    prov = VietnamAdministrativeResolver.resolve_province(target_code)
    assert prov is not None, f"Không tìm thấy tỉnh đích {target_name} ({target_code})"
    assert prov["code"] == target_code

    # Kiểm tra toàn bộ tỉnh cũ ánh xạ chính xác sang tỉnh đích
    for old_p in old_provinces:
        resolved = VietnamAdministrativeResolver.resolve_province(old_p)
        assert resolved is not None, f"Không giải quyết được tỉnh cũ '{old_p}'"
        assert resolved["code"] == target_code, f"'{old_p}' giải quyết ra mã {resolved['code']}, kỳ vọng {target_code} ({target_name})"


# ==============================================================================
# TEST SUITE 3: 11 TỈNH KHÔNG SÁP NHẬP
# ==============================================================================

UNCHANGED_PROVINCES = [
    ("Hà Nội", "01"),
    ("Huế", "46"),
    ("Cao Bằng", "04"),
    ("Điện Biên", "11"),
    ("Lai Châu", "12"),
    ("Sơn La", "14"),
    ("Lạng Sơn", "20"),
    ("Quảng Ninh", "22"),
    ("Thanh Hóa", "38"),
    ("Nghệ An", "40"),
    ("Hà Tĩnh", "42"),
]


@pytest.mark.parametrize("p_name, p_code", UNCHANGED_PROVINCES)
def test_11_unchanged_provinces(p_name, p_code):
    prov = VietnamAdministrativeResolver.resolve_province(p_name)
    assert prov is not None, f"Không tìm thấy {p_name}"
    assert prov["code"] == p_code, f"{p_name} mã {prov['code']} != {p_code}"


# ==============================================================================
# TEST SUITE 4: PHƯỜNG NAM ĐỊNH & KHU VỰC THÀNH PHỐ NAM ĐỊNH CŨ
# ==============================================================================

def test_nam_dinh_core_wards():
    # Kiểm tra Nam Định giải quyết về Ninh Bình
    nb_prov = VietnamAdministrativeResolver.resolve_province("Nam Định")
    assert nb_prov["code"] == "37", "Nam Định phải thuộc Ninh Bình (37)"

    # Kiểm tra có Phường Nam Định
    nam_dinh_ward = VietnamAdministrativeResolver.resolve_commune("37", "Nam Định")
    assert nam_dinh_ward is not None, "Phải có 'Phường Nam Định' trong Tỉnh Ninh Bình!"
    assert nam_dinh_ward["name"] == "Nam Định"
    assert nam_dinh_ward["type"] == "ward"

    # Kiểm tra 8 phường cốt lõi
    core_wards = [
        "Nam Định",
        "Thiên Trường",
        "Đông A",
        "Vị Khê",
        "Thành Nam",
        "Trường Thi",
        "Hồng Quang",
        "Mỹ Lộc",
    ]
    for w_name in core_wards:
        w = VietnamAdministrativeResolver.resolve_commune("37", w_name)
        assert w is not None, f"Thiếu phường cốt lõi '{w_name}' thuộc Ninh Bình!"

    # Kiểm tra các phường/xã cũ resolve qua alias vào đúng phường mới
    old_names_mapping = [
        ("Vị Xuyên", "Nam Định"),
        ("Quang Trung", "Nam Định"),
        ("Lộc Vượng", "Nam Định"),
        ("Cửa Bắc", "Nam Định"),
        ("Trần Hưng Đạo", "Nam Định"),
        ("Năng Tĩnh", "Nam Định"),
        ("Cửa Nam", "Nam Định"),
        ("Mỹ Phúc", "Nam Định"),
        ("Lộc Hạ", "Thiên Trường"),
        ("Lộc Hòa", "Đông A"),
        ("Mỹ Xá", "Thành Nam"),
    ]
    for old_name, expected_ward in old_names_mapping:
        found_comm = VietnamAdministrativeResolver.resolve_commune("37", old_name)
        assert found_comm is not None, f"Không resolve được alias '{old_name}'"
        assert found_comm["name"] == expected_ward, f"'{old_name}' mapped to '{found_comm['name']}', expected '{expected_ward}'"


# ==============================================================================
# TEST SUITE 5: GEOCODING PROVIDER COMPONENT RESOLUTION
# ==============================================================================

def test_provider_components_resolution():
    cases = [
        # Trường hợp 1: Bình Dương (cũ) -> TPHCM (79)
        (
            {"province": "Bình Dương", "district": "Thành phố Dĩ An", "ward": "Đông Hòa"},
            "79",
            True
        ),
        # Trường hợp 2: Nam Định (cũ) -> Ninh Bình (37)
        (
            {"province": "Nam Định", "district": "Thành phố Nam Định", "ward": "Vị Xuyên"},
            "37",
            True
        ),
        # Trường hợp 3: Hải Dương (cũ) -> Hải Phòng (31)
        (
            {"province": "Hải Dương", "district": "Chí Linh", "ward": "Sao Đỏ"},
            "31",
            True
        ),
        # Trường hợp 4: Quảng Nam (cũ) -> Đà Nẵng (48)
        (
            {"province": "Quảng Nam", "district": "Thành phố Hội An", "ward": "Minh An"},
            "48",
            True
        ),
        # Trường hợp 5: Phú Quốc -> Đặc khu Phú Quốc thuộc An Giang (89)
        (
            {"district": "Phú Quốc", "display_name": "Bãi Trường, Dương Đông, Phú Quốc, Kiên Giang"},
            "89",
            True
        ),
    ]

    for comp, expected_prov_code, expected_resolved in cases:
        res = VietnamAdministrativeResolver.resolve_provider_components(comp)
        assert res["is_resolved"] == expected_resolved, f"Failed for {comp}"
        assert res["province_code"] == expected_prov_code, f"Expected province {expected_prov_code}, got {res['province_code']}"


# ==============================================================================
# TEST SUITE 6: REST API ENDPOINTS
# ==============================================================================

def test_api_metadata(client):
    res = client.get("/api/v1/locations/metadata")
    assert res.status_code == 200
    data = res.json()
    assert data["country"] == "VN"
    assert data["administrativeModel"] == "2-tier"
    assert data["totalProvinces"] == 34
    assert data["totalCommunes"] == 3321


def test_api_provinces(client):
    res = client.get("/api/v1/locations/provinces")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 34

    # Test search for legacy province 'Bình Dương' returns TP.HCM
    res_bd = client.get("/api/v1/locations/provinces?search=Bình Dương")
    assert res_bd.status_code == 200
    data_bd = res_bd.json()
    assert any(p["code"] == "79" for p in data_bd), "Tìm 'Bình Dương' phải trả về TP.HCM (79)"


def test_api_communes(client):
    # Test communes of Ninh Bình (37)
    res = client.get("/api/v1/locations/communes?provinceCode=37")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 104
    assert any(c["name"] == "Nam Định" for c in data), "Danh sách xã của Ninh Bình phải có 'Phường Nam Định'"


def test_api_mergers(client):
    res = client.get("/api/v1/locations/mergers")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 23


def test_api_resolve(client):
    res = client.get("/api/v1/locations/resolve?q=Thành phố Nam Định")
    assert res.status_code == 200
    data = res.json()
    assert data["resolved_province"]["code"] == "37"


# ==============================================================================
# TEST SUITE 7: SQLITE DATABASE ARCHITECTURE
# ==============================================================================

def test_sqlite_tables_integrity():
    conn = sqlite3.connect("pharmatrust.db")
    c = conn.cursor()

    # Check 34 provinces in administrative_provinces
    c.execute("SELECT COUNT(*) FROM administrative_provinces")
    assert c.fetchone()[0] == 34

    # Check 3321 communes in administrative_communes
    c.execute("SELECT COUNT(*) FROM administrative_communes")
    assert c.fetchone()[0] == 3321

    # Check 23 distinct merger targets
    c.execute("SELECT COUNT(DISTINCT target_code) FROM administrative_mergers")
    assert c.fetchone()[0] == 23

    # Check aliases table
    c.execute("SELECT COUNT(*) FROM administrative_aliases")
    assert c.fetchone()[0] > 1000

    # Check backward compatibility administrative_units
    c.execute("SELECT COUNT(*) FROM administrative_units WHERE level = 'PROVINCE'")
    assert c.fetchone()[0] in (34, 63)

    c.execute("SELECT COUNT(*) FROM administrative_units WHERE level != 'PROVINCE'")
    comm_cnt = c.fetchone()[0]
    assert comm_cnt in (3321, 3421) or comm_cnt >= 3321

    conn.close()
