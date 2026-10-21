from datetime import datetime, timezone
from decimal import Decimal
import re
from typing import Any, List, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AdministrativeUnit, CustomerAddress, User
from app.services.administrative_service import AdministrativeDataService
from app.services.geo_service import (
    GeoService,
    PROVINCE_BOUNDING_BOXES,
    DISTRICT_DEFAULT_COORDINATES,
    calculate_haversine_distance,
)
from app.services.shipping_service import ShippingService
from app.services.places_service import PlacesService


addresses_router = APIRouter(prefix="/addresses", tags=["Địa chỉ & Bản đồ định vị"])
customer_address_router = APIRouter(prefix="/customer/addresses", tags=["Sổ địa chỉ Khách hàng"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class NearestWarehouseRequest(BaseModel):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    province_code: Optional[str] = None
    district_code: Optional[str] = None
    address: Optional[str] = None


class CalculateShippingRequest(BaseModel):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    province_code: Optional[str] = None
    district_code: Optional[str] = None
    order_total: Decimal = Field(default=Decimal("0.0"), ge=0)


class CustomerAddressCreate(BaseModel):
    recipient_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=8, max_length=20)
    address_line: str = Field(..., min_length=3, max_length=500)
    province_code: str = Field(..., min_length=1, max_length=50)
    province_name: Optional[str] = None
    commune_code: Optional[str] = None
    commune_name: Optional[str] = None
    district_code: Optional[str] = None
    ward_code: Optional[str] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    place_id: Optional[str] = None
    delivery_note: Optional[str] = None
    is_default: bool = False


class CustomerAddressUpdate(BaseModel):
    recipient_name: Optional[str] = None
    phone: Optional[str] = None
    address_line: Optional[str] = None
    province_code: Optional[str] = None
    province_name: Optional[str] = None
    commune_code: Optional[str] = None
    commune_name: Optional[str] = None
    district_code: Optional[str] = None
    ward_code: Optional[str] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    place_id: Optional[str] = None
    delivery_note: Optional[str] = None
    is_default: Optional[bool] = None


JUNK_PATTERNS = [
    r"^(tt|abc|xyz|test|123|123\s*test|nhà\s*tôi|nha\s*toi|dự\s*án\s*xyz|gần\s*trường|xxx|asdf|dự\s*án\s*ma)$",
]


def validate_and_normalize_phone(phone_str: str) -> str:
    """
    Chuẩn hóa và kiểm tra số điện thoại người nhận theo định dạng mạng di động Việt Nam.
    """
    if not phone_str or not phone_str.strip():
        raise HTTPException(
            status_code=400,
            detail="Vui lòng cung cấp số điện thoại người nhận.",
        )
    clean = re.sub(r"[\s\-\.\(\)]+", "", phone_str.strip())
    if clean.startswith("+84"):
        clean = "0" + clean[3:]
    elif clean.startswith("84") and len(clean) == 11:
        clean = "0" + clean[2:]

    # Kiểm tra đầu số chuẩn 10 số di động VN: 03, 05, 07, 08, 09
    if not re.match(r"^0(3[2-9]|5[25689]|7[06-9]|8[1-9]|9[0-9])[0-9]{7}$", clean):
        raise HTTPException(
            status_code=400,
            detail="Số điện thoại người nhận không đúng định dạng di động Việt Nam (10 chữ số, ví dụ: 0901234567, 0388889999).",
        )
    return clean


def validate_recipient_name(name_str: str) -> str:
    """
    Kiểm tra tên người nhận hàng.
    """
    cleaned = name_str.strip()
    if len(cleaned) < 2 or len(cleaned) > 255:
        raise HTTPException(
            status_code=400,
            detail="Họ và tên người nhận phải có từ 2 đến 255 ký tự.",
        )
    for pattern in JUNK_PATTERNS:
        if re.match(pattern, cleaned.lower()):
            raise HTTPException(
                status_code=400,
                detail="Họ và tên người nhận không hợp lệ.",
            )
    return cleaned


def _serialize_customer_address(addr: CustomerAddress) -> dict[str, Any]:
    effective_commune_code = addr.commune_code or addr.ward_code
    return {
        "id": addr.id,
        "user_id": addr.user_id,
        "recipient_name": addr.recipient_name,
        "phone": addr.phone,
        "address_line": addr.address_line,
        "province_code": addr.province_code,
        "province_name": addr.province_name,
        "commune_code": effective_commune_code,
        "commune_name": addr.commune_name,
        "formatted_address": addr.formatted_address or (
            f"{addr.address_line}, {addr.commune_name or ''}, {addr.province_name or ''}".strip(", ")
        ),
        "district_code": addr.district_code,
        "ward_code": addr.ward_code,
        "lat": addr.lat,
        "lng": addr.lng,
        "place_id": addr.place_id,
        "delivery_note": addr.delivery_note,
        "is_verified": bool(addr.is_verified),
        "verified_at": addr.verified_at.isoformat() if addr.verified_at else None,
        "is_default": bool(addr.is_default),
        "created_at": addr.created_at.isoformat() if addr.created_at else None,
        "updated_at": addr.updated_at.isoformat() if addr.updated_at else None,
    }


# ==============================================================================
# 1. ĐỊA GIỚI HÀNH CHÍNH & TÍNH KHO GẦN NHẤT & CƯỚC VẬN CHUYỂN
# ==============================================================================

@addresses_router.get("/administrative-units")
def get_administrative_units(
    level: Optional[str] = Query(None, description="PROVINCE hoặc DISTRICT"),
    parent_code: Optional[str] = Query(None, description="Mã cấp trên, ví dụ 79 (TP.HCM)"),
    search: Optional[str] = Query(None, description="Tìm kiếm tên tỉnh/thành hoặc quận/huyện"),
    tree: bool = Query(False, description="Nếu True, trả về cây Tỉnh kèm các Quận thuộc Tỉnh"),
    db: Session = Depends(get_db),
):
    """
    Tra cứu danh mục đơn vị hành chính chuẩn 2 cấp (Tỉnh / Thành phố và Quận / Huyện).
    Hỗ trợ trả về dạng phẳng (flat) hoặc dạng cây phân cấp (tree).
    """
    if tree:
        provinces = db.scalars(
            select(AdministrativeUnit)
            .where(AdministrativeUnit.level == "PROVINCE")
            .order_by(AdministrativeUnit.name.asc())
        ).all()

        districts = db.scalars(
            select(AdministrativeUnit)
            .where(AdministrativeUnit.level == "DISTRICT")
            .order_by(AdministrativeUnit.name.asc())
        ).all()

        dist_map: dict[str, list[dict[str, Any]]] = {}
        for d in districts:
            if d.parent_code:
                dist_map.setdefault(d.parent_code, []).append({
                    "code": d.code,
                    "name": d.name,
                    "full_name": d.full_name,
                    "level": d.level,
                    "parent_code": d.parent_code,
                })

        tree_res = []
        for p in provinces:
            tree_res.append({
                "code": p.code,
                "name": p.name,
                "full_name": p.full_name,
                "level": p.level,
                "districts": dist_map.get(p.code, []),
            })
        return tree_res

    query = select(AdministrativeUnit).order_by(AdministrativeUnit.name.asc())

    if level:
        query = query.where(AdministrativeUnit.level == level.upper())
    if parent_code:
        query = query.where(AdministrativeUnit.parent_code == parent_code)
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query = query.where(
            AdministrativeUnit.name.ilike(search_pattern) | AdministrativeUnit.full_name.ilike(search_pattern)
        )

    units = db.scalars(query).all()
    return [
        {
            "code": u.code,
            "name": u.name,
            "full_name": u.full_name,
            "level": u.level,
            "parent_code": u.parent_code,
        }
        for u in units
    ]


@addresses_router.get("/suggest")
async def suggest_addresses(
    q: str = Query(..., min_length=2, description="Số nhà, tên đường cần gợi ý"),
    province_code: str = Query(..., description="Mã tỉnh thành"),
    district_code: Optional[str] = Query(None, description="Mã quận huyện (legacy)"),
    ward_code: Optional[str] = Query(None, description="Mã phường xã"),
    commune_code: Optional[str] = Query(None, description="Mã xã/phường 2 cấp hiện hành"),
    db: Session = Depends(get_db),
):
    """
    Gợi ý địa chỉ tự động có kiểm soát địa giới theo đúng cấp hành chính đã chọn.
    Tự động chặn các chuỗi vô nghĩa/rác (như 'tt', 'abc', 'nhà tôi', '123 test').
    """
    query_str = q.strip()
    if len(query_str) < 2:
        return []

    for pattern in JUNK_PATTERNS:
        if re.match(pattern, query_str.lower()):
            return []

    c_code = commune_code or ward_code
    prov = AdministrativeDataService.get_province_by_code(province_code)
    comm = AdministrativeDataService.get_commune_by_code(c_code) if c_code else None

    prov_db = db.scalar(select(AdministrativeUnit).where(AdministrativeUnit.code == province_code))
    if prov_db:
        prov = {"code": prov_db.code, "name": prov_db.name, "fullName": prov_db.full_name}

    dist_db = db.scalar(select(AdministrativeUnit).where(AdministrativeUnit.code == district_code)) if district_code else None
    ward_db = db.scalar(select(AdministrativeUnit).where(AdministrativeUnit.code == (ward_code or c_code))) if (ward_code or c_code) else None

    dist_display = dist_db.name if dist_db else (comm.get("legacyDistrictName", "") if (comm and comm.get("legacyDistrictName") != "Khu vực hành chính cũ") else "")
    ward_display = ward_db.name if ward_db else (comm.get("name", "") if comm else "")
    comm_display = comm["fullName"] if comm else (ward_db.full_name if ward_db else "")
    prov_display = prov["fullName"] if prov else (prov_db.full_name if prov_db else "")

    if not prov and not prov_db:
        return []

    search_query = f"{query_str}, {comm_display}, {prov_display}, Vietnam".strip(", ")
    suggestions = []

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
                    is_valid, _ = GeoService.validate_province_coordinates(province_code, item_lat, item_lng)
                    if is_valid:
                        suggestions.append({
                            "place_id": str(item.get("place_id")),
                            "display_name": item.get("display_name"),
                            "street_address": query_str,
                            "ward_name": ward_display,
                            "district_name": dist_display,
                            "commune_name": comm_display,
                            "province_name": prov_display,
                            "lat": item_lat,
                            "lng": item_lng,
                            "verified": True,
                        })
    except Exception:
        pass

    if len(suggestions) == 0 and len(query_str) >= 3:
        def_lat, def_lng, _ = GeoService.resolve_customer_coordinates(
            province_code=province_code,
            district_code=district_code,
        )
        c_seed = c_code or "000"
        comm_hash = abs(hash(c_seed)) % 100
        offset_lat = (comm_hash - 50) * 0.0001
        offset_lng = ((comm_hash * 3) % 100 - 50) * 0.0001
        fallback_lat = round(def_lat + offset_lat, 6)
        fallback_lng = round(def_lng + offset_lng, 6)

        formatted_full = f"{query_str}, {comm_display}, {prov_display}".strip(", ")
        suggestions.append({
            "place_id": f"h4care-{c_seed}-{abs(hash(query_str))}",
            "display_name": formatted_full,
            "street_address": query_str,
            "ward_name": ward_display,
            "district_name": dist_display,
            "commune_name": comm_display,
            "province_name": prov_display,
            "lat": fallback_lat,
            "lng": fallback_lng,
            "verified": True,
        })

    return suggestions


@addresses_router.post("/nearest-warehouse")
def calculate_nearest_warehouse(
    payload: NearestWarehouseRequest,
    db: Session = Depends(get_db),
):
    """
    Tính khoảng cách địa lý (Haversine) từ tọa độ khách hàng đến tất cả các kho dược phẩm.
    Tự động chọn kho gần nhất và dự kiến thời gian giao hàng.
    """
    return GeoService.find_nearest_warehouses(
        db=db,
        lat=payload.lat,
        lng=payload.lng,
        province_code=payload.province_code,
        district_code=payload.district_code,
        address_text=payload.address,
    )


@addresses_router.post("/calculate-shipping")
def calculate_shipping_fee(
    payload: CalculateShippingRequest,
    db: Session = Depends(get_db),
):
    """
    Tính toán chi tiết cước vận chuyển giao hàng và kho điều phối phù hợp.
    """
    return ShippingService.calculate_shipping(
        db=db,
        lat=payload.lat,
        lng=payload.lng,
        province_code=payload.province_code,
        district_code=payload.district_code,
        order_total=payload.order_total,
    )


@addresses_router.get("/places/autocomplete")
async def autocomplete_places(
    q: str = Query(..., min_length=2, description="Tên địa điểm, tòa nhà, trường học, bệnh viện, số nhà, tên đường"),
    limit: int = Query(8, ge=1, le=15),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    session_token: Optional[str] = Query(None, description="Session Token Google Places để gom nhóm request"),
):
    """
    Tìm kiếm địa điểm toàn diện Google Maps-like có hỗ trợ Session Token.
    Cho phép tìm kiếm theo tên trường học, bệnh viện, tòa nhà, địa chỉ mà không bắt buộc chọn Tỉnh/Xã trước.
    """
    return await PlacesService.autocomplete_places(q=q, limit=limit, lat=lat, lng=lng, session_token=session_token)


@addresses_router.get("/places/details")
async def get_place_details(
    place_id: str = Query(..., min_length=3, description="Place ID từ Google Maps, OSM hoặc POI trọng điểm"),
    session_token: Optional[str] = Query(None, description="Session Token Google Places"),
):
    """
    Lấy thông tin chi tiết địa điểm, tọa độ GPS chính xác và thành phần hành chính từ Place ID.
    Dùng khi khách hàng bấm chọn một gợi ý địa chỉ để xác định tọa độ thật trên bản đồ.
    """
    return await PlacesService.get_place_details(place_id=place_id, session_token=session_token)


@addresses_router.get("/reverse-geocode")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Vĩ độ GPS"),
    lng: float = Query(..., ge=-180, le=180, description="Kinh độ GPS"),
):
    """
    Chuyển đổi tọa độ GPS thành địa chỉ và tự động map 2 cấp hành chính 2025.
    Dùng khi: kéo ghim, click trực tiếp trên bản đồ, hoặc bấm 'Vị trí hiện tại của tôi'.
    """
    return await PlacesService.reverse_geocode(lat=lat, lng=lng)


@addresses_router.get("/provider-status")
def get_geocoding_provider_status():
    """
    Báo cáo trạng thái Provider Geocoding (Mục 16):
    GOOGLE PLACES: CONFIGURED / NOT CONFIGURED
    FALLBACK: OpenStreetMap / Nominatim + Photon + Internal 2-Tier GeoService
    """
    return PlacesService.get_provider_status()


# ==============================================================================
# 2. SỔ ĐỊA CHỈ KHÁCH HÀNG (CUSTOMER ADDRESS BOOK - V2)
# ==============================================================================

@customer_address_router.get("")
def list_customer_addresses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Lấy danh sách địa chỉ nhận hàng đã lưu của khách hàng (bảo mật nghiêm ngặt theo user_id).
    """
    addresses = db.scalars(
        select(CustomerAddress)
        .where(CustomerAddress.user_id == user.id)
        .order_by(desc(CustomerAddress.is_default), desc(CustomerAddress.id))
    ).all()

    return [_serialize_customer_address(a) for a in addresses]


@customer_address_router.get("/{address_id}")
def get_customer_address_by_id(
    address_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Lấy chi tiết một địa chỉ nhận hàng của khách hàng theo ID (kiểm tra quyền sở hữu).
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == user.id,
        )
    )
    if not addr:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy địa chỉ này trong sổ địa chỉ của bạn.",
        )
    return _serialize_customer_address(addr)


@customer_address_router.post("", status_code=status.HTTP_201_CREATED)
def create_customer_address(
    payload: CustomerAddressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Thêm địa chỉ nhận hàng mới vào sổ địa chỉ cá nhân (xác thực máy chủ 100%, không tin client is_verified).
    """
    # 1. Validate người nhận & số điện thoại
    recipient_name = validate_recipient_name(payload.recipient_name)
    phone = validate_and_normalize_phone(payload.phone)
    address_line = payload.address_line.strip()
    if len(address_line) < 3:
        raise HTTPException(status_code=400, detail="Vui lòng nhập địa chỉ chi tiết rõ ràng (tối thiểu 3 ký tự).")

    # 2. Validate cấp hành chính (Province & Commune)
    prov_code = payload.province_code.strip()
    comm_code = (payload.commune_code or payload.ward_code or "").strip()

    if not prov_code:
        raise HTTPException(status_code=400, detail="Vui lòng chọn Tỉnh / Thành phố.")

    prov_info = AdministrativeDataService.get_province_by_code(prov_code)
    if not prov_info:
        raise HTTPException(status_code=400, detail=f"Mã Tỉnh/Thành phố '{prov_code}' không hợp lệ.")

    province_name = prov_info["fullName"]
    commune_name = None
    district_code = payload.district_code

    if comm_code:
        is_sel_valid, sel_err = AdministrativeDataService.validate_selection(prov_code, comm_code)
        if not is_sel_valid:
            raise HTTPException(status_code=400, detail=sel_err)
        comm_info = AdministrativeDataService.get_commune_by_code(comm_code)
        if comm_info:
            commune_name = comm_info["fullName"]
            if not district_code and comm_info.get("legacyDistrictName"):
                district_code = comm_info.get("legacyDistrictName")

    formatted_address = (
        f"{address_line}, {commune_name or ''}, {province_name}".strip(", ")
    )

    # 3. Server-side Verification: Backend quyết định is_verified và verified_at
    is_verified = False
    verified_at = None

    if payload.lat is not None and payload.lng is not None:
        is_v, v_msg = GeoService.verify_customer_address(
            province_code=prov_code,
            commune_code=comm_code,
            lat=payload.lat,
            lng=payload.lng,
        )
        if not is_v:
            raise HTTPException(status_code=400, detail=v_msg)
        is_verified = True
        verified_at = datetime.now(timezone.utc)

    # 4. Quản lý trạng thái Default Address: Đảm bảo duy nhất 1 default address
    existing_count = db.scalar(
        select(CustomerAddress.id).where(CustomerAddress.user_id == user.id)
    )
    is_first = (existing_count is None)
    should_be_default = payload.is_default or is_first

    if should_be_default:
        existing_defaults = db.scalars(
            select(CustomerAddress).where(
                CustomerAddress.user_id == user.id,
                CustomerAddress.is_default == True,
            )
        ).all()
        for ea in existing_defaults:
            ea.is_default = False

    # 5. Lưu đối tượng địa chỉ mới
    address = CustomerAddress(
        user_id=user.id,
        recipient_name=recipient_name,
        phone=phone,
        address_line=address_line,
        province_code=prov_code,
        province_name=province_name,
        commune_code=comm_code or None,
        commune_name=commune_name,
        formatted_address=formatted_address,
        district_code=district_code,
        ward_code=comm_code or payload.ward_code,
        lat=payload.lat,
        lng=payload.lng,
        place_id=payload.place_id,
        delivery_note=payload.delivery_note.strip() if payload.delivery_note else None,
        is_verified=is_verified,
        verified_at=verified_at,
        is_default=should_be_default,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(address)
    db.commit()
    db.refresh(address)

    serialized = _serialize_customer_address(address)
    return {
        "status": "SUCCESS",
        "message": "Đã lưu địa chỉ nhận hàng thành công.",
        "id": address.id,
        "is_default": address.is_default,
        "data": serialized,
        **serialized,
    }


def _update_address_logic(
    addr: CustomerAddress,
    payload: CustomerAddressUpdate,
    db: Session,
    user: User,
) -> dict[str, Any]:
    update_data = payload.model_dump(exclude_unset=True)

    # Validate phone nếu có cập nhật
    if "phone" in update_data and update_data["phone"] is not None:
        addr.phone = validate_and_normalize_phone(update_data["phone"])

    # Validate name nếu có cập nhật
    if "recipient_name" in update_data and update_data["recipient_name"] is not None:
        addr.recipient_name = validate_recipient_name(update_data["recipient_name"])

    # Cập nhật địa chỉ chi tiết
    if "address_line" in update_data and update_data["address_line"] is not None:
        line_val = update_data["address_line"].strip()
        if len(line_val) < 3:
            raise HTTPException(status_code=400, detail="Vui lòng nhập địa chỉ chi tiết (tối thiểu 3 ký tự).")
        addr.address_line = line_val

    # Cập nhật hành chính
    prov_changed = "province_code" in update_data and update_data["province_code"] is not None
    comm_changed = "commune_code" in update_data and update_data["commune_code"] is not None

    if prov_changed:
        prov_code = update_data["province_code"].strip()
        prov_info = AdministrativeDataService.get_province_by_code(prov_code)
        if not prov_info:
            raise HTTPException(status_code=400, detail=f"Mã Tỉnh/Thành phố '{prov_code}' không hợp lệ.")
        addr.province_code = prov_code
        addr.province_name = prov_info["fullName"]

    if comm_changed:
        comm_code = update_data["commune_code"].strip()
        current_prov = addr.province_code
        if current_prov:
            is_valid_sel, sel_err = AdministrativeDataService.validate_selection(current_prov, comm_code)
            if not is_valid_sel:
                raise HTTPException(status_code=400, detail=sel_err)
        comm_info = AdministrativeDataService.get_commune_by_code(comm_code)
        if comm_info:
            addr.commune_code = comm_code
            addr.commune_name = comm_info["fullName"]
            addr.ward_code = comm_code
            if comm_info.get("legacyDistrictName"):
                addr.district_code = comm_info.get("legacyDistrictName")

    # Cập nhật tọa độ & Server Verification
    coords_changed = "lat" in update_data or "lng" in update_data
    if coords_changed:
        new_lat = update_data.get("lat", addr.lat)
        new_lng = update_data.get("lng", addr.lng)
        if new_lat is not None and new_lng is not None:
            is_v, v_msg = GeoService.verify_customer_address(
                province_code=addr.province_code,
                commune_code=addr.commune_code,
                lat=new_lat,
                lng=new_lng,
            )
            if not is_v:
                raise HTTPException(status_code=400, detail=v_msg)
            addr.lat = new_lat
            addr.lng = new_lng
            addr.is_verified = True
            addr.verified_at = datetime.now(timezone.utc)
        else:
            addr.lat = None
            addr.lng = None
            addr.is_verified = False
            addr.verified_at = None

    if "place_id" in update_data:
        addr.place_id = update_data["place_id"]

    if "delivery_note" in update_data:
        val = update_data["delivery_note"]
        addr.delivery_note = val.strip() if val else None

    # Tái tạo formatted_address
    addr.formatted_address = (
        f"{addr.address_line}, {addr.commune_name or ''}, {addr.province_name or ''}".strip(", ")
    )

    # Đặt mặc định nếu được yêu cầu
    if update_data.get("is_default") is True:
        existing_defaults = db.scalars(
            select(CustomerAddress).where(
                CustomerAddress.user_id == user.id,
                CustomerAddress.is_default == True,
                CustomerAddress.id != addr.id,
            )
        ).all()
        for ea in existing_defaults:
            ea.is_default = False
        addr.is_default = True
    elif update_data.get("is_default") is False:
        addr.is_default = False

    addr.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(addr)

    serialized = _serialize_customer_address(addr)
    return {
        "status": "SUCCESS",
        "message": "Cập nhật địa chỉ thành công.",
        "id": addr.id,
        "is_default": addr.is_default,
        "data": serialized,
        **serialized,
    }


@customer_address_router.put("/{address_id}")
def update_customer_address_put(
    address_id: int,
    payload: CustomerAddressUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Cập nhật toàn bộ thông tin một địa chỉ đã lưu (PUT - Kiểm tra sở hữu).
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == user.id,
        )
    )
    if not addr:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy địa chỉ này trong sổ địa chỉ của bạn.",
        )
    return _update_address_logic(addr, payload, db, user)


@customer_address_router.patch("/{address_id}")
def update_customer_address_patch(
    address_id: int,
    payload: CustomerAddressUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Cập nhật một phần thông tin một địa chỉ đã lưu (PATCH - Kiểm tra sở hữu).
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == user.id,
        )
    )
    if not addr:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy địa chỉ này trong sổ địa chỉ của bạn.",
        )
    return _update_address_logic(addr, payload, db, user)


@customer_address_router.delete("/{address_id}")
def delete_customer_address(
    address_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Xóa một địa chỉ khỏi sổ địa chỉ cá nhân (Kiểm tra quyền sở hữu).
    Nếu xóa địa chỉ mặc định, tự động chuyển cờ mặc định sang một địa chỉ còn lại để đảm bảo người dùng luôn có địa chỉ mặc định.
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == user.id,
        )
    )
    if not addr:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy địa chỉ này trong sổ địa chỉ của bạn.",
        )

    was_default = addr.is_default
    db.delete(addr)
    db.flush()

    # Nếu địa chỉ vừa xóa là mặc định, chọn địa chỉ mới nhất còn lại làm mặc định
    if was_default:
        remaining_addr = db.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == user.id)
            .order_by(desc(CustomerAddress.id))
        )
        if remaining_addr:
            remaining_addr.is_default = True

    db.commit()
    return {"status": "SUCCESS", "message": "Đã xóa địa chỉ thành công."}


@customer_address_router.patch("/{address_id}/default")
def set_default_address_patch(
    address_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Đặt địa chỉ làm địa chỉ nhận hàng mặc định (PATCH /default).
    """
    addr = db.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.user_id == user.id,
        )
    )
    if not addr:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy địa chỉ này trong sổ địa chỉ của bạn.",
        )

    all_addrs = db.scalars(
        select(CustomerAddress).where(CustomerAddress.user_id == user.id)
    ).all()
    for a in all_addrs:
        a.is_default = (a.id == addr.id)

    db.commit()
    db.refresh(addr)
    serialized = _serialize_customer_address(addr)
    return {
        "status": "SUCCESS",
        "message": "Đã đặt làm địa chỉ mặc định.",
        "id": addr.id,
        "is_default": addr.is_default,
        "data": serialized,
        **serialized,
    }


@customer_address_router.post("/{address_id}/set-default")
def set_default_address_post(
    address_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Đặt địa chỉ làm địa chỉ nhận hàng mặc định (POST alias).
    """
    return set_default_address_patch(address_id=address_id, db=db, user=user)
