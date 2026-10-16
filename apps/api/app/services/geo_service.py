import math
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Warehouse, AdministrativeUnit


PROVINCE_DEFAULT_COORDINATES: dict[str, tuple[float, float]] = {
    # 5 thành phố trực thuộc trung ương
    "01": (21.0285, 105.8542),  # Hà Nội
    "79": (10.7769, 106.7009),  # TP. Hồ Chí Minh
    "31": (20.8449, 106.6881),  # Hải Phòng
    "48": (16.0544, 108.2022),  # Đà Nẵng
    "92": (10.0452, 105.7469),  # Cần Thơ
    # Đồng bằng sông Hồng & Đông Bắc / Tây Bắc
    "02": (22.8233, 104.9839),  # Hà Giang
    "04": (22.6657, 106.2570),  # Cao Bằng
    "06": (22.1470, 105.8348),  # Bắc Kạn
    "08": (21.8234, 105.2140),  # Tuyên Quang
    "10": (22.4856, 103.9707),  # Lào Cai
    "11": (21.3860, 103.0230),  # Điện Biên
    "12": (22.3964, 103.4684),  # Lai Châu
    "14": (21.3283, 103.9148),  # Sơn La
    "15": (21.7168, 104.8967),  # Yên Bái
    "17": (20.8171, 105.3376),  # Hòa Bình
    "19": (21.5942, 105.8482),  # Thái Nguyên
    "20": (21.8537, 106.7615),  # Lạng Sơn
    "22": (21.0069, 107.2925),  # Quảng Ninh
    "24": (21.2731, 106.1946),  # Bắc Giang
    "25": (21.3990, 105.2280),  # Phú Thọ
    "26": (21.3089, 105.6049),  # Vĩnh Phúc
    "27": (21.1861, 106.0763),  # Bắc Ninh
    "30": (20.9373, 106.3150),  # Hải Dương
    "33": (20.6464, 106.0511),  # Hưng Yên
    "34": (20.4463, 106.3366),  # Thái Bình
    "35": (20.5843, 105.9220),  # Hà Nam
    "36": (20.4343, 106.1774),  # Nam Định
    "37": (20.2506, 105.9745),  # Ninh Bình
    # Bắc Trung Bộ & Duyên hải miền Trung
    "38": (19.8067, 105.7852),  # Thanh Hóa
    "40": (18.6796, 105.6813),  # Nghệ An
    "42": (18.3430, 105.9058),  # Hà Tĩnh
    "44": (17.4761, 106.5995),  # Quảng Bình
    "45": (16.8164, 107.1004),  # Quảng Trị
    "46": (16.4637, 107.5909),  # Thừa Thiên Huế
    "49": (15.5647, 108.4800),  # Quảng Nam
    "51": (15.1205, 108.7923),  # Quảng Ngãi
    "52": (13.7820, 109.2197),  # Bình Định
    "54": (13.0882, 109.3138),  # Phú Yên
    "56": (12.2388, 109.1967),  # Khánh Hòa
    "58": (11.5658, 108.9882),  # Ninh Thuận
    "60": (10.9333, 108.1000),  # Bình Thuận
    # Tây Nguyên
    "62": (14.3497, 108.0005),  # Kon Tum
    "64": (13.9833, 108.0000),  # Gia Lai
    "66": (12.6667, 108.0500),  # Đắk Lắk
    "67": (12.0040, 107.6870),  # Đắk Nông
    "68": (11.9404, 108.4583),  # Lâm Đồng
    # Đông Nam Bộ
    "70": (11.9333, 106.9167),  # Bình Phước
    "72": (11.3128, 106.0989),  # Tây Ninh
    "74": (11.1667, 106.6667),  # Bình Dương
    "75": (10.9574, 106.8427),  # Đồng Nai
    "77": (10.5425, 107.2429),  # Bà Rịa - Vũng Tàu
    # Đồng bằng sông Cửu Long
    "80": (10.5333, 106.4167),  # Long An
    "82": (10.3600, 106.3600),  # Tiền Giang
    "83": (10.2333, 106.3833),  # Bến Tre
    "84": (9.9347, 106.3455),   # Trà Vinh
    "86": (10.2537, 105.9722),  # Vĩnh Long
    "87": (10.4578, 105.6324),  # Đồng Tháp
    "89": (10.5216, 105.1259),  # An Giang
    "91": (10.0139, 105.0809),  # Kiên Giang
    "93": (9.7833, 105.4667),   # Hậu Giang
    "94": (9.6000, 105.9667),   # Sóc Trăng
    "95": (9.2833, 105.7167),   # Bạc Liêu
    "96": (9.1769, 105.1500),   # Cà Mau
}

PROVINCE_KEYWORDS: list[tuple[list[str], tuple[float, float]]] = [
    (["hồ chí minh", "tp.hcm", "tphcm", "sài gòn", "sai gon"], (10.7769, 106.7009)),
    (["hà nội", "ha noi", "thủ đô"], (21.0285, 105.8542)),
    (["đà nẵng", "da nang"], (16.0544, 108.2022)),
    (["hải phòng", "hai phong"], (20.8449, 106.6881)),
    (["cần thơ", "can tho"], (10.0452, 105.7469)),
    (["bình dương", "binh duong", "thủ dầu một", "dĩ an", "thuận an"], (11.1667, 106.6667)),
    (["đồng nai", "dong nai", "biên hòa", "bien hoa"], (10.9574, 106.8427)),
    (["bà rịa", "vũng tàu", "vung tau", "ba ria"], (10.5425, 107.2429)),
    (["long an", "tân an", "tan an"], (10.5333, 106.4167)),
    (["tiền giang", "tien giang", "mỹ tho", "my tho"], (10.3600, 106.3600)),
    (["bến tre", "ben tre"], (10.2333, 106.3833)),
    (["vĩnh long", "vinh long"], (10.2537, 105.9722)),
    (["đồng tháp", "dong thap", "cao lãnh", "sa đéc"], (10.4578, 105.6324)),
    (["an giang", "long xuyên", "châu đốc"], (10.5216, 105.1259)),
    (["kiên giang", "kien giang", "rạch giá", "phú quốc", "phu quoc"], (10.0139, 105.0809)),
    (["khánh hòa", "khanh hoa", "nha trang", "cam ranh"], (12.2388, 109.1967)),
    (["bình định", "binh dinh", "quy nhơn", "quy nhon"], (13.7820, 109.2197)),
    (["thừa thiên huế", "thừa thiên", "huế", "hue"], (16.4637, 107.5909)),
    (["quảng nam", "quang nam", "tam kỳ", "hội an"], (15.5647, 108.4800)),
    (["quảng ngãi", "quang ngai"], (15.1205, 108.7923)),
    (["quảng ninh", "quang ninh", "hạ long", "cẩm phả"], (21.0069, 107.2925)),
    (["nghệ an", "nghe an", "vinh"], (18.6796, 105.6813)),
    (["thanh hóa", "thanh hoa"], (19.8067, 105.7852)),
    (["bắc ninh", "bac ninh"], (21.1861, 106.0763)),
    (["bắc giang", "bac giang"], (21.2731, 106.1946)),
    (["hải dương", "hai duong"], (20.9373, 106.3150)),
    (["nam định", "nam dinh"], (20.4343, 106.1774)),
    (["thái bình", "thai binh"], (20.4463, 106.3366)),
    (["vĩnh phúc", "vinh phuc"], (21.3089, 105.6049)),
    (["phú thọ", "phu tho", "việt trì"], (21.3990, 105.2280)),
    (["thái nguyên", "thai nguyen"], (21.5942, 105.8482)),
    (["lâm đồng", "lam dong", "đà lạt", "da lat", "bảo lộc"], (11.9404, 108.4583)),
    (["đắk lắk", "dak lak", "buôn ma thuột"], (12.6667, 108.0500)),
    (["bình thuận", "binh thuan", "phan thiết"], (10.9333, 108.1000)),
    (["ninh thuận", "ninh thuan", "phan rang"], (11.5658, 108.9882)),
    (["phú yên", "phu yen", "tuy hòa"], (13.0882, 109.3138)),
    (["quảng bình", "quang binh", "đồng hới"], (17.4761, 106.5995)),
    (["quảng trị", "quang tri", "đông hà"], (16.8164, 107.1004)),
    (["hà tĩnh", "ha tinh"], (18.3430, 105.9058)),
    (["hòa bình", "hoa binh"], (20.8171, 105.3376)),
    (["sơn la", "son la"], (21.3283, 103.9148)),
    (["lào cai", "lao cai", "sa pa"], (22.4856, 103.9707)),
    (["lạng sơn", "lang son"], (21.8537, 106.7615)),
    (["yên bái", "yen bai"], (21.7168, 104.8967)),
    (["tuyên quang", "tuyen quang"], (21.8234, 105.2140)),
    (["hà giang", "ha giang"], (22.8233, 104.9839)),
    (["cao bằng", "cao bang"], (22.6657, 106.2570)),
    (["bắc kạn", "bac kan"], (22.1470, 105.8348)),
]

# Tọa độ mặc định cho một số quận trung tâm
DISTRICT_DEFAULT_COORDINATES: dict[str, tuple[float, float]] = {
    # HCM
    "760": (10.7756, 106.7004),  # Quận 1
    "761": (10.8672, 106.6413),  # Quận 12
    "765": (10.8038, 106.7118),  # Bình Thạnh
    "766": (10.7992, 106.6534),  # Tân Bình
    "769": (10.8494, 106.7537),  # TP Thủ Đức
    "770": (10.7844, 106.6844),  # Quận 3
    "771": (10.7672, 106.6669),  # Quận 10
    # HN
    "001": (21.0341, 105.8277),  # Ba Đình
    "002": (21.0307, 105.8524),  # Hoàn Kiếm
    "004": (21.0181, 105.8267),  # Đống Đa
    "005": (21.0090, 105.8548),  # Hai Bà Trưng
    "009": (21.0362, 105.7906),  # Cầu Giấy
}

from app.services.administrative_service import AdministrativeDataService

PROVINCE_BOUNDING_BOXES: dict[str, dict[str, Any]] = {}
for _p in AdministrativeDataService.get_provinces():
    _bb = _p.get("boundingBox", {})
    if _bb:
        PROVINCE_BOUNDING_BOXES[_p["code"]] = {
            "min_lat": _bb.get("minLat", 8.0),
            "max_lat": _bb.get("maxLat", 24.0),
            "min_lng": _bb.get("minLng", 102.0),
            "max_lng": _bb.get("maxLng", 115.0),
            "name": _p.get("fullName", _p.get("name")),
        }

# Fallback mặc định cho 5 đô thị nếu chưa nạp file
if not PROVINCE_BOUNDING_BOXES:
    PROVINCE_BOUNDING_BOXES = {
        "01": {"min_lat": 20.50, "max_lat": 21.60, "min_lng": 105.20, "max_lng": 106.10, "name": "TP. Hà Nội"},
        "79": {"min_lat": 8.50, "max_lat": 11.60, "min_lng": 106.30, "max_lng": 107.60, "name": "TP. Hồ Chí Minh"},
        "48": {"min_lat": 14.80, "max_lat": 16.30, "min_lng": 107.10, "max_lng": 112.50, "name": "TP. Đà Nẵng"},
        "92": {"min_lat": 9.20, "max_lat": 10.40, "min_lng": 105.20, "max_lng": 106.40, "name": "TP. Cần Thơ"},
        "31": {"min_lat": 20.50, "max_lat": 21.30, "min_lng": 106.10, "max_lng": 107.20, "name": "TP. Hải Phòng"},
    }



def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Tính khoảng cách giữa 2 điểm tọa độ địa lý (kinh độ, vĩ độ) bằng công thức Haversine.
    Kết quả trả về theo đơn vị Kilometers (km), làm tròn 2 chữ số thập phân.
    """
    R = 6371.0  # Bán kính Trái Đất (km)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return round(distance, 2)


def get_estimated_delivery_time(distance_km: float) -> str:
    """
    Ước tính thời gian giao hàng dựa trên khoảng cách địa lý đến kho.
    """
    if distance_km <= 10.0:
        return "Giao siêu tốc 1 - 2 giờ (Nội thành cùng kho)"
    elif distance_km <= 35.0:
        return "Giao trong ngày 3 - 6 giờ (Khu vực lân cận)"
    elif distance_km <= 150.0:
        return "Giao trong 24 giờ (Ngoại thành / Tỉnh lân cận)"
    else:
        return "Giao 24 - 48 giờ (Chuyển phát tiêu chuẩn liên tỉnh)"


class GeoService:
    @classmethod
    def resolve_customer_coordinates(
        cls,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
        address_text: Optional[str] = None,
    ) -> tuple[float, float, str]:
        """
        Xác định tọa độ giao hàng từ GPS/Map Pin hoặc tra cứu fallback theo Quận/Huyện/Tỉnh hoặc chuỗi địa chỉ.
        Trả về (lat, lng, resolution_source).
        """
        if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180 and not (abs(lat) < 0.0001 and abs(lng) < 0.0001):
            return float(lat), float(lng), "GPS_EXACT"

        if district_code and str(district_code) in DISTRICT_DEFAULT_COORDINATES:
            d_lat, d_lng = DISTRICT_DEFAULT_COORDINATES[str(district_code)]
            return d_lat, d_lng, "DISTRICT_CENTROID"

        if province_code:
            p_code_str = str(province_code).zfill(2) if str(province_code).isdigit() else str(province_code)
            if p_code_str in PROVINCE_DEFAULT_COORDINATES:
                p_lat, p_lng = PROVINCE_DEFAULT_COORDINATES[p_code_str]
                return p_lat, p_lng, "PROVINCE_CENTROID"

        if address_text:
            text_lower = address_text.lower()
            for keywords, coords in PROVINCE_KEYWORDS:
                if any(kw in text_lower for kw in keywords):
                    return coords[0], coords[1], "ADDRESS_KEYWORD_MATCH"

        # Tọa độ mặc định: Trung tâm TP. Hồ Chí Minh
        return 10.7769, 106.7009, "FALLBACK_DEFAULT"

    @classmethod
    def validate_province_coordinates(
        cls,
        province_code: Optional[str],
        lat: Optional[float],
        lng: Optional[float],
    ) -> tuple[bool, str]:
        """
        Kiểm tra tính hợp lệ của tọa độ GPS đối với Tỉnh/Thành phố được chọn.
        Chặn giả mạo: chọn Hà Nội nhưng tọa độ ở TP.HCM hoặc ngược lại.
        """
        if lat is None or lng is None:
            return False, "Thiếu tọa độ địa lý (vĩ độ, kinh độ)."

        # Chặn tọa độ vô nghĩa (0, 0)
        if abs(lat) < 0.0001 and abs(lng) < 0.0001:
            return False, "Tọa độ (0, 0) không hợp lệ."

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            return False, "Tọa độ vượt giới hạn hợp lệ."

        # Kiểm tra trong lãnh thổ Việt Nam
        if not (8.0 <= lat <= 24.0 and 102.0 <= lng <= 110.0):
            return False, f"Tọa độ ({lat:.4f}, {lng:.4f}) nằm ngoài lãnh thổ giao hàng Việt Nam."

        if province_code and province_code in PROVINCE_BOUNDING_BOXES:
            box = PROVINCE_BOUNDING_BOXES[province_code]
            if not (box["min_lat"] <= lat <= box["max_lat"] and box["min_lng"] <= lng <= box["max_lng"]):
                return (
                    False,
                    f"Tọa độ ({lat:.4f}, {lng:.4f}) không khớp với phạm vi địa lý của {box['name']}. Vui lòng chọn hoặc ghim đúng vị trí trên bản đồ.",
                )

        return True, "Hợp lệ"

    @classmethod
    def verify_customer_address(
        cls,
        province_code: Optional[str],
        commune_code: Optional[str],
        lat: Optional[float],
        lng: Optional[float],
    ) -> tuple[bool, str]:
        """
        Xác minh máy chủ (Server-side verification) cho địa chỉ khách hàng.
        Kiểm tra tính toàn vẹn: Tọa độ, giới hạn VN, bounding box Tỉnh, và không phải tọa độ giả mạo.
        """
        if lat is None or lng is None:
            return False, "Thiếu tọa độ địa lý định vị."

        if abs(lat) < 0.0001 and abs(lng) < 0.0001:
            return False, "Tọa độ (0, 0) không hợp lệ."

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            return False, "Tọa độ vượt ngoài giới hạn địa lý hợp lệ."

        is_prov_valid, prov_msg = cls.validate_province_coordinates(province_code, lat, lng)
        if not is_prov_valid:
            return False, prov_msg

        return True, "Địa chỉ đã được hệ thống xác minh hợp lệ"

    @classmethod
    def find_nearest_warehouses(
        cls,
        db: Session,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
        address_text: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Tìm kiếm và xếp hạng các kho hàng đang hoạt động theo khoảng cách địa lý đến khách hàng.
        """
        cust_lat, cust_lng, source = cls.resolve_customer_coordinates(
            lat=lat, lng=lng, province_code=province_code, district_code=district_code
        )

        warehouses = db.scalars(
            select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.id.asc())
        ).all()

        results = []
        for wh in warehouses:
            wh_lat = float(wh.lat) if wh.lat is not None else (10.7872 if "HCM" in wh.code else 21.0253)
            wh_lng = float(wh.lng) if wh.lng is not None else (106.7001 if "HCM" in wh.code else 105.8552)

            dist = calculate_haversine_distance(cust_lat, cust_lng, wh_lat, wh_lng)
            eta = get_estimated_delivery_time(dist)

            results.append({
                "warehouse_id": wh.id,
                "warehouse_code": wh.code,
                "warehouse_name": wh.name,
                "warehouse_address": wh.address,
                "lat": wh_lat,
                "lng": wh_lng,
                "distance_km": dist,
                "estimated_delivery_time": eta,
                "is_central": wh.is_central,
                "navigation_url": f"https://www.google.com/maps/dir/?api=1&origin={cust_lat},{cust_lng}&destination={wh_lat},{wh_lng}",
            })

        # Sắp xếp theo khoảng cách tăng dần
        results.sort(key=lambda x: x["distance_km"])

        nearest = results[0] if results else None

        return {
            "customer_location": {
                "lat": cust_lat,
                "lng": cust_lng,
                "source": source,
                "address": address_text or "",
            },
            "nearest_warehouse": nearest,
            "warehouses": results,
            "google_maps_view_url": f"https://www.google.com/maps/search/?api=1&query={cust_lat},{cust_lng}",
        }
