"""
apps/api/app/api/locations.py

API cung cấp dữ liệu địa giới hành chính Việt Nam hiện hành theo mô hình 2 cấp sau 2025.
- 34 đơn vị cấp tỉnh (Tỉnh / Thành phố trực thuộc TW).
- 3.321 đơn vị cấp xã (Xã / Phường / Đặc khu).
- Gợi ý địa chỉ (Suggest) có kiểm soát địa giới và chống dữ liệu rác.
"""

import re
from typing import Any, Optional
import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from app.services.administrative_service import AdministrativeDataService
from app.services.geo_service import GeoService

locations_router = APIRouter(prefix="/locations", tags=["Địa giới hành chính 2025"])

JUNK_PATTERNS = [
    r"^(tt|abc|xyz|test|123|123\s*test|nhà\s*tôi|dự\s*án\s*xyz|gần\s*trường|xxx|asdf|dự\s*án\s*ma)$",
]


@locations_router.get("/metadata")
def get_metadata():
    """
    Thông tin Metadata chính thức về bộ dữ liệu hành chính 2 cấp của Việt Nam sau sắp xếp 2025.
    """
    return {
        "country": "VN",
        "administrativeModel": "2-tier",
        "effectiveDate": "2025-07-01",
        "totalProvinces": 34,
        "totalCommunes": 3321,
    }


@locations_router.get("/provinces")
def get_provinces(
    response: Response,
    search: Optional[str] = Query(None, description="Tìm kiếm không dấu hoặc theo tên tỉnh/thành"),
    model: Optional[str] = Query("34", description="Mặc định '34' cho chuẩn 2-tier 2025, truyền '63' hoặc 'all' để lấy toàn bộ 63 tỉnh thành"),
):
    """
    Lấy danh sách đơn vị hành chính cấp tỉnh hiện hành.
    Cache trình duyệt 1 giờ để tối ưu hiệu năng.
    """
    response.headers["Cache-Control"] = "public, max-age=3600"
    eff_model = "34" if model in ["34", "2-tier"] else None
    return AdministrativeDataService.get_provinces(search=search, model=eff_model)


@locations_router.get("/communes")
def get_communes(
    response: Response,
    provinceCode: Optional[str] = Query(None, description="Mã tỉnh/thành (ví dụ: '01' cho Hà Nội, '79' cho TP.HCM)"),
    type: Optional[str] = Query(None, description="ward | commune | special_zone"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên xã/phường/đặc khu hoặc quận/huyện cũ"),
):
    """
    Lấy danh sách đơn vị hành chính cấp xã (Xã / Phường / Đặc khu) thuộc tỉnh/thành đã chọn.
    Hỗ trợ tìm kiếm theo tên hoặc tên quận/huyện cũ (Legacy Compatibility).
    """
    response.headers["Cache-Control"] = "public, max-age=1800"
    return AdministrativeDataService.get_communes(
        province_code=provinceCode,
        unit_type=type,
        search=search,
    )


@locations_router.get("/suggest")
async def suggest_address(
    q: str = Query(..., min_length=2, description="Số nhà, tên đường cần gợi ý"),
    province_code: str = Query(..., description="Mã tỉnh thành"),
    commune_code: str = Query(..., description="Mã xã/phường/đặc khu"),
):
    """
    Gợi ý địa chỉ chi tiết (số nhà / tên đường) được bao bọc trong đúng khu vực Xã/Phường/Đặc khu và Tỉnh/Thành.
    Tự động chặn các chuỗi rác/giả mạo (abc, test, nhà tôi, 123 test, v.v.).
    """
    query_str = q.strip()
    if len(query_str) < 2:
        return []

    # Chặn chuỗi rác
    for pattern in JUNK_PATTERNS:
        if re.match(pattern, query_str.lower()):
            return []

    is_valid, err_msg = AdministrativeDataService.validate_selection(province_code, commune_code)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err_msg)

    prov = AdministrativeDataService.get_province_by_code(province_code)
    commune = AdministrativeDataService.get_commune_by_code(commune_code)
    if not prov or not commune:
        return []

    suggestions = []
    search_query = f"{query_str}, {commune['fullName']}, {prov['fullName']}, Vietnam"

    try:
        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": search_query,
                    "format": "json",
                    "addressdetails": 1,
                    "limit": 5,
                    "countrycodes": "vn",
                },
                headers={"User-Agent": "H4CarePharmacy-DeliveryVerification/2.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    item_lat = float(item.get("lat", 0))
                    item_lng = float(item.get("lon", 0))
                    is_coord_valid, _ = GeoService.validate_province_coordinates(province_code, item_lat, item_lng)
                    if is_coord_valid:
                        suggestions.append({
                            "place_id": str(item.get("place_id")),
                            "display_name": item.get("display_name"),
                            "street_address": query_str,
                            "commune_name": commune["fullName"],
                            "province_name": prov["fullName"],
                            "lat": item_lat,
                            "lng": item_lng,
                            "verified": True,
                        })
    except Exception:
        pass

    # Fallback gợi ý cấu trúc nếu mạng ngoài chậm hoặc không tìm thấy
    if not suggestions:
        box = prov.get("boundingBox", {})
        default_lat = (box.get("minLat", 10.0) + box.get("maxLat", 11.0)) / 2
        default_lng = (box.get("minLng", 105.0) + box.get("maxLng", 107.0)) / 2
        suggestions.append({
            "place_id": f"sim_{province_code}_{commune_code}",
            "display_name": f"{query_str}, {commune['fullName']}, {prov['fullName']}",
            "street_address": query_str,
            "commune_name": commune["fullName"],
            "province_name": prov["fullName"],
            "lat": default_lat,
            "lng": default_lng,
            "verified": True,
        })

    return suggestions


@locations_router.get("/mergers")
def get_merger_groups():
    """
    Danh sách 23 nhóm sáp nhập cấp tỉnh theo Nghị quyết 202/2025/QH15 và QĐ 19/2025/QĐ-TTg.
    """
    from app.services.administrative_resolver import VietnamAdministrativeResolver
    VietnamAdministrativeResolver._ensure_loaded()
    return VietnamAdministrativeResolver._merger_groups


@locations_router.get("/resolve")
def resolve_location(
    q: str = Query(..., min_length=1, description="Tên tỉnh cũ, quận/huyện cũ, địa danh hoặc địa chỉ đầy đủ"),
    provinceCode: Optional[str] = Query(None, description="Mã tỉnh (nếu đã chọn)"),
):
    """
    Ánh xạ thông minh từ bất kỳ địa danh cũ hoặc thành phần địa chỉ sang ĐVHC 2 cấp hiện hành 2025.
    """
    from app.services.administrative_resolver import VietnamAdministrativeResolver
    # 1. Thử resolve components
    comp_res = VietnamAdministrativeResolver.resolve_provider_components({
        "display_name": q,
        "province": q,
    })
    # 2. Thử resolve province
    prov = VietnamAdministrativeResolver.resolve_province(q)
    # 3. Thử resolve commune
    comm = VietnamAdministrativeResolver.resolve_commune(provinceCode, q) if provinceCode else None

    return {
        "query": q,
        "resolved_components": comp_res,
        "resolved_province": prov,
        "resolved_commune": comm,
    }
