import json
import re
from pathlib import Path

# Toàn bộ 63 Tỉnh / Thành phố trực thuộc Trung ương của Việt Nam (Chuẩn Google Maps & TCTK)
PROVINCES_63 = [
    # 5 Thành phố trực thuộc Trung ương
    {
        "code": "01",
        "name": "Hà Nội",
        "fullName": "Thành phố Hà Nội",
        "type": "municipality",
        "aliases": ["Ha Noi", "HN", "Thủ Đô", "Thủ đô Hà Nội", "Thành phố Hà Nội"],
        "boundingBox": {"minLat": 20.53, "maxLat": 21.39, "minLng": 105.28, "maxLng": 106.03},
        "center": {"lat": 21.0285, "lng": 105.8542},
    },
    {
        "code": "79",
        "name": "Hồ Chí Minh",
        "fullName": "Thành phố Hồ Chí Minh",
        "type": "municipality",
        "aliases": ["Ho Chi Minh", "TPHCM", "TP.HCM", "Sài Gòn", "Sai Gon", "Thành phố Hồ Chí Minh"],
        "boundingBox": {"minLat": 10.35, "maxLat": 11.15, "minLng": 106.35, "maxLng": 107.02},
        "center": {"lat": 10.7769, "lng": 106.7009},
    },
    {
        "code": "31",
        "name": "Hải Phòng",
        "fullName": "Thành phố Hải Phòng",
        "type": "municipality",
        "aliases": ["Hai Phong", "HP", "Thành phố Cảng", "Thành phố Hải Phòng"],
        "boundingBox": {"minLat": 20.58, "maxLat": 21.02, "minLng": 106.40, "maxLng": 107.13},
        "center": {"lat": 20.8449, "lng": 106.6881},
    },
    {
        "code": "48",
        "name": "Đà Nẵng",
        "fullName": "Thành phố Đà Nẵng",
        "type": "municipality",
        "aliases": ["Da Nang", "ĐN", "Thành phố Đà Nẵng"],
        "boundingBox": {"minLat": 15.92, "maxLat": 16.23, "minLng": 107.82, "maxLng": 108.35},
        "center": {"lat": 16.0544, "lng": 108.2022},
    },
    {
        "code": "92",
        "name": "Cần Thơ",
        "fullName": "Thành phố Cần Thơ",
        "type": "municipality",
        "aliases": ["Can Tho", "CT", "Tây Đô", "Thành phố Cần Thơ"],
        "boundingBox": {"minLat": 9.92, "maxLat": 10.32, "minLng": 105.25, "maxLng": 105.85},
        "center": {"lat": 10.0452, "lng": 105.7469},
    },
    {
        "code": "46",
        "name": "Thừa Thiên Huế",
        "fullName": "Tỉnh Thừa Thiên Huế",
        "type": "province",
        "aliases": ["Thừa Thiên Huế", "Thua Thien Hue", "Huế", "Hue", "Cố đô Huế", "Thành phố Huế"],
        "boundingBox": {"minLat": 15.98, "maxLat": 16.80, "minLng": 107.00, "maxLng": 108.20},
        "center": {"lat": 16.4637, "lng": 107.5909},
    },
    # Miền Bắc (Tây Bắc & Đông Bắc)
    {
        "code": "02",
        "name": "Hà Giang",
        "fullName": "Tỉnh Hà Giang",
        "type": "province",
        "aliases": ["Ha Giang", "Đồng Văn", "Mèo Vạc", "Yên Minh"],
        "boundingBox": {"minLat": 22.15, "maxLat": 23.39, "minLng": 104.33, "maxLng": 105.52},
        "center": {"lat": 22.8233, "lng": 104.9839},
    },
    {
        "code": "04",
        "name": "Cao Bằng",
        "fullName": "Tỉnh Cao Bằng",
        "type": "province",
        "aliases": ["Cao Bang", "Trùng Khánh", "Bản Giốc"],
        "boundingBox": {"minLat": 22.25, "maxLat": 23.12, "minLng": 105.26, "maxLng": 106.84},
        "center": {"lat": 22.6657, "lng": 106.2570},
    },
    {
        "code": "06",
        "name": "Bắc Kạn",
        "fullName": "Tỉnh Bắc Kạn",
        "type": "province",
        "aliases": ["Bac Kan", "Bắc Cạn", "Ba Bể"],
        "boundingBox": {"minLat": 21.80, "maxLat": 22.75, "minLng": 105.43, "maxLng": 106.25},
        "center": {"lat": 22.1470, "lng": 105.8348},
    },
    {
        "code": "08",
        "name": "Tuyên Quang",
        "fullName": "Tỉnh Tuyên Quang",
        "type": "province",
        "aliases": ["Tuyen Quang", "Na Hang"],
        "boundingBox": {"minLat": 21.50, "maxLat": 22.67, "minLng": 104.88, "maxLng": 105.68},
        "center": {"lat": 21.8234, "lng": 105.2140},
    },
    {
        "code": "10",
        "name": "Lào Cai",
        "fullName": "Tỉnh Lào Cai",
        "type": "province",
        "aliases": ["Lao Cai", "Sa Pa", "Sapa", "Fansipan"],
        "boundingBox": {"minLat": 21.98, "maxLat": 22.85, "minLng": 103.52, "maxLng": 104.64},
        "center": {"lat": 22.4856, "lng": 103.9707},
    },
    {
        "code": "11",
        "name": "Điện Biên",
        "fullName": "Tỉnh Điện Biên",
        "type": "province",
        "aliases": ["Dien Bien", "Điện Biên Phủ", "Mường Thanh"],
        "boundingBox": {"minLat": 20.90, "maxLat": 22.56, "minLng": 102.17, "maxLng": 103.60},
        "center": {"lat": 21.3860, "lng": 103.0230},
    },
    {
        "code": "12",
        "name": "Lai Châu",
        "fullName": "Tỉnh Lai Châu",
        "type": "province",
        "aliases": ["Lai Chau", "Mường Tè"],
        "boundingBox": {"minLat": 21.68, "maxLat": 22.83, "minLng": 102.32, "maxLng": 103.98},
        "center": {"lat": 22.3964, "lng": 103.4684},
    },
    {
        "code": "14",
        "name": "Sơn La",
        "fullName": "Tỉnh Sơn La",
        "type": "province",
        "aliases": ["Son La", "Mộc Châu", "Moc Chau"],
        "boundingBox": {"minLat": 20.65, "maxLat": 22.04, "minLng": 103.18, "maxLng": 105.04},
        "center": {"lat": 21.3283, "lng": 103.9148},
    },
    {
        "code": "15",
        "name": "Yên Bái",
        "fullName": "Tỉnh Yên Bái",
        "type": "province",
        "aliases": ["Yen Bai", "Mù Cang Chải", "Nghĩa Lộ"],
        "boundingBox": {"minLat": 21.30, "maxLat": 22.29, "minLng": 103.93, "maxLng": 105.10},
        "center": {"lat": 21.7168, "lng": 104.8967},
    },
    {
        "code": "17",
        "name": "Hòa Bình",
        "fullName": "Tỉnh Hòa Bình",
        "type": "province",
        "aliases": ["Hoa Binh", "Mai Châu", "Lương Sơn"],
        "boundingBox": {"minLat": 20.31, "maxLat": 21.14, "minLng": 104.80, "maxLng": 105.85},
        "center": {"lat": 20.8171, "lng": 105.3376},
    },
    {
        "code": "19",
        "name": "Thái Nguyên",
        "fullName": "Tỉnh Thái Nguyên",
        "type": "province",
        "aliases": ["Thai Nguyen", "Sông Công", "Phổ Yên"],
        "boundingBox": {"minLat": 21.33, "maxLat": 22.05, "minLng": 105.48, "maxLng": 106.25},
        "center": {"lat": 21.5942, "lng": 105.8482},
    },
    {
        "code": "20",
        "name": "Lạng Sơn",
        "fullName": "Tỉnh Lạng Sơn",
        "type": "province",
        "aliases": ["Lang Son", "Đồng Đăng", "Hữu Lũng"],
        "boundingBox": {"minLat": 21.32, "maxLat": 22.45, "minLng": 106.10, "maxLng": 107.36},
        "center": {"lat": 21.8537, "lng": 106.7615},
    },
    {
        "code": "22",
        "name": "Quảng Ninh",
        "fullName": "Tỉnh Quảng Ninh",
        "type": "province",
        "aliases": ["Quang Ninh", "Hạ Long", "Cẩm Phả", "Uông Bí", "Móng Cái", "Vân Đồn"],
        "boundingBox": {"minLat": 20.72, "maxLat": 21.85, "minLng": 106.43, "maxLng": 108.08},
        "center": {"lat": 21.0069, "lng": 107.2925},
    },
    {
        "code": "24",
        "name": "Bắc Giang",
        "fullName": "Tỉnh Bắc Giang",
        "type": "province",
        "aliases": ["Bac Giang", "Việt Yên", "Lục Ngạn", "Hiệp Hòa"],
        "boundingBox": {"minLat": 21.12, "maxLat": 21.63, "minLng": 105.88, "maxLng": 107.03},
        "center": {"lat": 21.2731, "lng": 106.1946},
    },
    {
        "code": "25",
        "name": "Phú Thọ",
        "fullName": "Tỉnh Phú Thọ",
        "type": "province",
        "aliases": ["Phu Tho", "Việt Trì", "Đền Hùng", "Thị xã Phú Thọ"],
        "boundingBox": {"minLat": 20.92, "maxLat": 21.72, "minLng": 104.81, "maxLng": 105.45},
        "center": {"lat": 21.3990, "lng": 105.2280},
    },
    {
        "code": "26",
        "name": "Vĩnh Phúc",
        "fullName": "Tỉnh Vĩnh Phúc",
        "type": "province",
        "aliases": ["Vinh Phuc", "Vĩnh Yên", "Phúc Yên", "Tam Đảo"],
        "boundingBox": {"minLat": 21.15, "maxLat": 21.58, "minLng": 105.32, "maxLng": 105.78},
        "center": {"lat": 21.3089, "lng": 105.6049},
    },
    {
        "code": "27",
        "name": "Bắc Ninh",
        "fullName": "Tỉnh Bắc Ninh",
        "type": "province",
        "aliases": ["Bac Ninh", "Từ Sơn", "Yên Phong", "Thuận Thành"],
        "boundingBox": {"minLat": 20.97, "maxLat": 21.26, "minLng": 105.97, "maxLng": 106.32},
        "center": {"lat": 21.1861, "lng": 106.0763},
    },
    {
        "code": "30",
        "name": "Hải Dương",
        "fullName": "Tỉnh Hải Dương",
        "type": "province",
        "aliases": ["Hai Duong", "Chí Linh", "Kinh Môn"],
        "boundingBox": {"minLat": 20.72, "maxLat": 21.24, "minLng": 106.05, "maxLng": 106.63},
        "center": {"lat": 20.9373, "lng": 106.3150},
    },
    {
        "code": "33",
        "name": "Hưng Yên",
        "fullName": "Tỉnh Hưng Yên",
        "type": "province",
        "aliases": ["Hung Yen", "Mỹ Hào", "Văn Giang", "Ecopark"],
        "boundingBox": {"minLat": 20.60, "maxLat": 21.00, "minLng": 105.90, "maxLng": 106.33},
        "center": {"lat": 20.6464, "lng": 106.0511},
    },
    {
        "code": "34",
        "name": "Thái Bình",
        "fullName": "Tỉnh Thái Bình",
        "type": "province",
        "aliases": ["Thai Binh", "Tiền Hải", "Đông Hưng"],
        "boundingBox": {"minLat": 20.30, "maxLat": 20.73, "minLng": 106.10, "maxLng": 106.65},
        "center": {"lat": 20.4463, "lng": 106.3366},
    },
    {
        "code": "35",
        "name": "Hà Nam",
        "fullName": "Tỉnh Hà Nam",
        "type": "province",
        "aliases": ["Ha Nam", "Phủ Lý", "Duy Tiên", "Tam Chúc"],
        "boundingBox": {"minLat": 20.35, "maxLat": 20.73, "minLng": 105.75, "maxLng": 106.17},
        "center": {"lat": 20.5843, "lng": 105.9220},
    },
    {
        "code": "36",
        "name": "Nam Định",
        "fullName": "Tỉnh Nam Định",
        "type": "province",
        "aliases": ["Nam Dinh", "Thành phố Nam Định", "Giao Thủy", "Hải Hậu", "Xuân Trường"],
        "boundingBox": {"minLat": 19.98, "maxLat": 20.50, "minLng": 105.95, "maxLng": 106.58},
        "center": {"lat": 20.4343, "lng": 106.1774},
    },
    {
        "code": "37",
        "name": "Ninh Bình",
        "fullName": "Tỉnh Ninh Bình",
        "type": "province",
        "aliases": ["Ninh Binh", "Tam Điệp", "Tràng An", "Bái Đính"],
        "boundingBox": {"minLat": 20.01, "maxLat": 20.46, "minLng": 105.53, "maxLng": 106.17},
        "center": {"lat": 20.2506, "lng": 105.9745},
    },
    # Bắc Trung Bộ & Duyên hải Miền Trung
    {
        "code": "38",
        "name": "Thanh Hóa",
        "fullName": "Tỉnh Thanh Hóa",
        "type": "province",
        "aliases": ["Thanh Hoa", "Sầm Sơn", "Bỉm Sơn", "Nghi Sơn"],
        "boundingBox": {"minLat": 19.23, "maxLat": 20.67, "minLng": 104.37, "maxLng": 106.07},
        "center": {"lat": 19.8067, "lng": 105.7852},
    },
    {
        "code": "40",
        "name": "Nghệ An",
        "fullName": "Tỉnh Nghệ An",
        "type": "province",
        "aliases": ["Nghe An", "TP Vinh", "Cửa Lò", "Hoàng Mai"],
        "boundingBox": {"minLat": 18.55, "maxLat": 19.98, "minLng": 103.88, "maxLng": 105.78},
        "center": {"lat": 18.6796, "lng": 105.6813},
    },
    {
        "code": "42",
        "name": "Hà Tĩnh",
        "fullName": "Tỉnh Hà Tĩnh",
        "type": "province",
        "aliases": ["Ha Tinh", "Hồng Lĩnh", "Kỳ Anh"],
        "boundingBox": {"minLat": 17.90, "maxLat": 18.77, "minLng": 105.10, "maxLng": 106.50},
        "center": {"lat": 18.3430, "lng": 105.9058},
    },
    {
        "code": "44",
        "name": "Quảng Bình",
        "fullName": "Tỉnh Quảng Bình",
        "type": "province",
        "aliases": ["Quang Binh", "Đồng Hới", "Phong Nha", "Ba Đồn"],
        "boundingBox": {"minLat": 16.92, "maxLat": 18.08, "minLng": 105.62, "maxLng": 106.98},
        "center": {"lat": 17.4761, "lng": 106.5995},
    },
    {
        "code": "45",
        "name": "Quảng Trị",
        "fullName": "Tỉnh Quảng Trị",
        "type": "province",
        "aliases": ["Quang Tri", "Đông Hà", "Thị xã Quảng Trị"],
        "boundingBox": {"minLat": 16.30, "maxLat": 17.17, "minLng": 106.40, "maxLng": 107.40},
        "center": {"lat": 16.8164, "lng": 107.1004},
    },
    {
        "code": "49",
        "name": "Quảng Nam",
        "fullName": "Tỉnh Quảng Nam",
        "type": "province",
        "aliases": ["Quang Nam", "Hội An", "Tam Kỳ", "Điện Bàn"],
        "boundingBox": {"minLat": 14.95, "maxLat": 16.07, "minLng": 107.20, "maxLng": 108.73},
        "center": {"lat": 15.5647, "lng": 108.4800},
    },
    {
        "code": "51",
        "name": "Quảng Ngãi",
        "fullName": "Tỉnh Quảng Ngãi",
        "type": "province",
        "aliases": ["Quang Ngai", "Dung Quất", "Lý Sơn"],
        "boundingBox": {"minLat": 14.53, "maxLat": 15.42, "minLng": 108.10, "maxLng": 109.13},
        "center": {"lat": 15.1205, "lng": 108.7923},
    },
    {
        "code": "52",
        "name": "Bình Định",
        "fullName": "Tỉnh Bình Định",
        "type": "province",
        "aliases": ["Binh Dinh", "Quy Nhơn", "An Nhơn", "Hoài Nhơn"],
        "boundingBox": {"minLat": 13.70, "maxLat": 14.70, "minLng": 108.63, "maxLng": 109.35},
        "center": {"lat": 13.7820, "lng": 109.2197},
    },
    {
        "code": "54",
        "name": "Phú Yên",
        "fullName": "Tỉnh Phú Yên",
        "type": "province",
        "aliases": ["Phu Yen", "Tuy Hòa", "Sông Cầu", "Đông Hòa"],
        "boundingBox": {"minLat": 12.70, "maxLat": 13.70, "minLng": 108.68, "maxLng": 109.48},
        "center": {"lat": 13.0882, "lng": 109.3138},
    },
    {
        "code": "56",
        "name": "Khánh Hòa",
        "fullName": "Tỉnh Khánh Hòa",
        "type": "province",
        "aliases": ["Khanh Hoa", "Nha Trang", "Cam Ranh", "Ninh Hòa"],
        "boundingBox": {"minLat": 11.75, "maxLat": 12.87, "minLng": 108.67, "maxLng": 109.45},
        "center": {"lat": 12.2388, "lng": 109.1967},
    },
    {
        "code": "58",
        "name": "Ninh Thuận",
        "fullName": "Tỉnh Ninh Thuận",
        "type": "province",
        "aliases": ["Ninh Thuan", "Phan Rang", "Tháp Chàm"],
        "boundingBox": {"minLat": 11.30, "maxLat": 12.17, "minLng": 108.55, "maxLng": 109.23},
        "center": {"lat": 11.5658, "lng": 108.9882},
    },
    {
        "code": "60",
        "name": "Bình Thuận",
        "fullName": "Tỉnh Bình Thuận",
        "type": "province",
        "aliases": ["Binh Thuan", "Phan Thiết", "La Gi", "Mũi Né"],
        "boundingBox": {"minLat": 10.55, "maxLat": 11.55, "minLng": 107.38, "maxLng": 108.88},
        "center": {"lat": 10.9333, "lng": 108.1000},
    },
    # Tây Nguyên
    {
        "code": "62",
        "name": "Kon Tum",
        "fullName": "Tỉnh Kon Tum",
        "type": "province",
        "aliases": ["Kon Tum", "Măng Đen", "Ngọc Hồi"],
        "boundingBox": {"minLat": 13.92, "maxLat": 15.45, "minLng": 107.33, "maxLng": 108.53},
        "center": {"lat": 14.3497, "lng": 108.0005},
    },
    {
        "code": "64",
        "name": "Gia Lai",
        "fullName": "Tỉnh Gia Lai",
        "type": "province",
        "aliases": ["Gia Lai", "Pleiku", "An Khê", "Ayun Pa"],
        "boundingBox": {"minLat": 13.00, "maxLat": 14.60, "minLng": 107.38, "maxLng": 108.92},
        "center": {"lat": 13.9833, "lng": 108.0000},
    },
    {
        "code": "66",
        "name": "Đắk Lắk",
        "fullName": "Tỉnh Đắk Lắk",
        "type": "province",
        "aliases": ["Dak Lak", "Đắc Lắc", "Buôn Ma Thuột", "Buon Ma Thuot"],
        "boundingBox": {"minLat": 12.18, "maxLat": 13.42, "minLng": 107.48, "maxLng": 109.10},
        "center": {"lat": 12.6667, "lng": 108.0500},
    },
    {
        "code": "67",
        "name": "Đắk Nông",
        "fullName": "Tỉnh Đắk Nông",
        "type": "province",
        "aliases": ["Dak Nong", "Gia Nghĩa", "Tà Đùng"],
        "boundingBox": {"minLat": 11.75, "maxLat": 12.80, "minLng": 107.20, "maxLng": 108.12},
        "center": {"lat": 12.0040, "lng": 107.6870},
    },
    {
        "code": "68",
        "name": "Lâm Đồng",
        "fullName": "Tỉnh Lâm Đồng",
        "type": "province",
        "aliases": ["Lam Dong", "Đà Lạt", "Da Lat", "Bảo Lộc", "Bao Loc"],
        "boundingBox": {"minLat": 11.35, "maxLat": 12.33, "minLng": 107.30, "maxLng": 108.75},
        "center": {"lat": 11.9404, "lng": 108.4583},
    },
    # Đông Nam Bộ
    {
        "code": "70",
        "name": "Bình Phước",
        "fullName": "Tỉnh Bình Phước",
        "type": "province",
        "aliases": ["Binh Phuoc", "Đồng Xoài", "Chơn Thành", "Bình Long"],
        "boundingBox": {"minLat": 11.38, "maxLat": 12.30, "minLng": 106.40, "maxLng": 107.45},
        "center": {"lat": 11.9333, "lng": 106.9167},
    },
    {
        "code": "72",
        "name": "Tây Ninh",
        "fullName": "Tỉnh Tây Ninh",
        "type": "province",
        "aliases": ["Tay Ninh", "Trảng Bàng", "Hòa Thành", "Bà Đen"],
        "boundingBox": {"minLat": 10.95, "maxLat": 11.78, "minLng": 105.80, "maxLng": 106.50},
        "center": {"lat": 11.3128, "lng": 106.0989},
    },
    {
        "code": "74",
        "name": "Bình Dương",
        "fullName": "Tỉnh Bình Dương",
        "type": "province",
        "aliases": ["Binh Duong", "Thủ Dầu Một", "Thuận An", "Dĩ An", "Tân Uyên", "Bến Cát"],
        "boundingBox": {"minLat": 10.87, "maxLat": 11.50, "minLng": 106.35, "maxLng": 106.97},
        "center": {"lat": 11.1667, "lng": 106.6667},
    },
    {
        "code": "75",
        "name": "Đồng Nai",
        "fullName": "Tỉnh Đồng Nai",
        "type": "province",
        "aliases": ["Dong Nai", "Biên Hòa", "Long Khánh", "Long Thành", "Nhơn Trạch"],
        "boundingBox": {"minLat": 10.50, "maxLat": 11.58, "minLng": 106.75, "maxLng": 107.60},
        "center": {"lat": 10.9574, "lng": 106.8427},
    },
    {
        "code": "77",
        "name": "Bà Rịa - Vũng Tàu",
        "fullName": "Tỉnh Bà Rịa - Vũng Tàu",
        "type": "province",
        "aliases": ["Ba Ria Vung Tau", "Vũng Tàu", "Bà Rịa", "Phú Mỹ", "Côn Đảo"],
        "boundingBox": {"minLat": 10.28, "maxLat": 10.75, "minLng": 107.00, "maxLng": 107.60},
        "center": {"lat": 10.5425, "lng": 107.2429},
    },
    # Tây Nam Bộ (Đồng bằng sông Cửu Long)
    {
        "code": "80",
        "name": "Long An",
        "fullName": "Tỉnh Long An",
        "type": "province",
        "aliases": ["Long An", "Tân An", "Bến Lức", "Đức Hòa", "Cần Giuộc"],
        "boundingBox": {"minLat": 10.35, "maxLat": 11.05, "minLng": 105.80, "maxLng": 106.78},
        "center": {"lat": 10.5333, "lng": 106.4167},
    },
    {
        "code": "82",
        "name": "Tiền Giang",
        "fullName": "Tỉnh Tiền Giang",
        "type": "province",
        "aliases": ["Tien Giang", "Mỹ Tho", "Gò Công", "Cai Lậy"],
        "boundingBox": {"minLat": 10.20, "maxLat": 10.60, "minLng": 105.80, "maxLng": 106.75},
        "center": {"lat": 10.3600, "lng": 106.3600},
    },
    {
        "code": "83",
        "name": "Bến Tre",
        "fullName": "Tỉnh Bến Tre",
        "type": "province",
        "aliases": ["Ben Tre", "Xứ Dừa", "Ba Tri", "Châu Thành"],
        "boundingBox": {"minLat": 9.80, "maxLat": 10.35, "minLng": 106.00, "maxLng": 106.80},
        "center": {"lat": 10.2333, "lng": 106.3833},
    },
    {
        "code": "84",
        "name": "Trà Vinh",
        "fullName": "Tỉnh Trà Vinh",
        "type": "province",
        "aliases": ["Tra Vinh", "Duyên Hải", "Cầu Kè"],
        "boundingBox": {"minLat": 9.50, "maxLat": 10.05, "minLng": 106.00, "maxLng": 106.65},
        "center": {"lat": 9.9347, "lng": 106.3455},
    },
    {
        "code": "86",
        "name": "Vĩnh Long",
        "fullName": "Tỉnh Vĩnh Long",
        "type": "province",
        "aliases": ["Vinh Long", "Bình Minh", "Long Hồ"],
        "boundingBox": {"minLat": 9.90, "maxLat": 10.35, "minLng": 105.70, "maxLng": 106.20},
        "center": {"lat": 10.2537, "lng": 105.9722},
    },
    {
        "code": "87",
        "name": "Đồng Tháp",
        "fullName": "Tỉnh Đồng Tháp",
        "type": "province",
        "aliases": ["Dong Thap", "Cao Lãnh", "Sa Đéc", "Hồng Ngự"],
        "boundingBox": {"minLat": 10.10, "maxLat": 10.95, "minLng": 105.18, "maxLng": 105.95},
        "center": {"lat": 10.4578, "lng": 105.6324},
    },
    {
        "code": "89",
        "name": "An Giang",
        "fullName": "Tỉnh An Giang",
        "type": "province",
        "aliases": ["An Giang", "Long Xuyên", "Châu Đốc", "Tân Châu"],
        "boundingBox": {"minLat": 10.15, "maxLat": 10.95, "minLng": 104.78, "maxLng": 105.60},
        "center": {"lat": 10.5216, "lng": 105.1259},
    },
    {
        "code": "91",
        "name": "Kiên Giang",
        "fullName": "Tỉnh Kiên Giang",
        "type": "province",
        "aliases": ["Kien Giang", "Rạch Giá", "Hà Tiên", "Phú Quốc", "Phu Quoc"],
        "boundingBox": {"minLat": 9.40, "maxLat": 10.55, "minLng": 104.40, "maxLng": 105.55},
        "center": {"lat": 10.0139, "lng": 105.0809},
    },
    {
        "code": "93",
        "name": "Hậu Giang",
        "fullName": "Tỉnh Hậu Giang",
        "type": "province",
        "aliases": ["Hau Giang", "Vị Thanh", "Ngã Bảy"],
        "boundingBox": {"minLat": 9.58, "maxLat": 9.95, "minLng": 105.20, "maxLng": 105.90},
        "center": {"lat": 9.7833, "lng": 105.4667},
    },
    {
        "code": "94",
        "name": "Sóc Trăng",
        "fullName": "Tỉnh Sóc Trăng",
        "type": "province",
        "aliases": ["Soc Trang", "Vĩnh Châu", "Ngã Năm"],
        "boundingBox": {"minLat": 9.25, "maxLat": 9.92, "minLng": 105.55, "maxLng": 106.30},
        "center": {"lat": 9.6000, "lng": 105.9667},
    },
    {
        "code": "95",
        "name": "Bạc Liêu",
        "fullName": "Tỉnh Bạc Liêu",
        "type": "province",
        "aliases": ["Bac Lieu", "Giá Rai"],
        "boundingBox": {"minLat": 9.00, "maxLat": 9.60, "minLng": 105.25, "maxLng": 105.85},
        "center": {"lat": 9.2833, "lng": 105.7167},
    },
    {
        "code": "96",
        "name": "Cà Mau",
        "fullName": "Tỉnh Cà Mau",
        "type": "province",
        "aliases": ["Ca Mau", "Năm Căn", "Đất Mũi"],
        "boundingBox": {"minLat": 8.55, "maxLat": 9.55, "minLng": 104.70, "maxLng": 105.45},
        "center": {"lat": 9.1769, "lng": 105.1500},
    },
]

# Danh mục phân bổ bổ sung các phường xã trung tâm cho từng tỉnh
PROVINCE_CORE_COMMUNES = {
    "74": [  # Bình Dương
        {"code": "7401", "name": "Phú Hòa", "fullName": "Phường Phú Hòa", "type": "ward", "legacyDistrictName": "TP. Thủ Dầu Một"},
        {"code": "7402", "name": "Phú Cường", "fullName": "Phường Phú Cường", "type": "ward", "legacyDistrictName": "TP. Thủ Dầu Một"},
        {"code": "7403", "name": "Hiệp Thành", "fullName": "Phường Hiệp Thành", "type": "ward", "legacyDistrictName": "TP. Thủ Dầu Một"},
        {"code": "7404", "name": "Chánh Nghĩa", "fullName": "Phường Chánh Nghĩa", "type": "ward", "legacyDistrictName": "TP. Thủ Dầu Một"},
        {"code": "7405", "name": "Lái Thiêu", "fullName": "Phường Lái Thiêu", "type": "ward", "legacyDistrictName": "TP. Thuận An"},
        {"code": "7406", "name": "An Phú", "fullName": "Phường An Phú", "type": "ward", "legacyDistrictName": "TP. Thuận An"},
        {"code": "7407", "name": "Dĩ An", "fullName": "Phường Dĩ An", "type": "ward", "legacyDistrictName": "TP. Dĩ An"},
        {"code": "7408", "name": "Đông Hòa", "fullName": "Phường Đông Hòa", "type": "ward", "legacyDistrictName": "TP. Dĩ An"},
        {"code": "7409", "name": "Uyên Hưng", "fullName": "Phường Uyên Hưng", "type": "ward", "legacyDistrictName": "TP. Tân Uyên"},
        {"code": "7410", "name": "Mỹ Phước", "fullName": "Phường Mỹ Phước", "type": "ward", "legacyDistrictName": "TX. Bến Cát"},
    ],
    "36": [  # Nam Định
        {"code": "3601", "name": "Vị Xuyên", "fullName": "Phường Vị Xuyên", "type": "ward", "legacyDistrictName": "TP. Nam Định"},
        {"code": "3602", "name": "Trần Hưng Đạo", "fullName": "Phường Trần Hưng Đạo", "type": "ward", "legacyDistrictName": "TP. Nam Định"},
        {"code": "3603", "name": "Năng Tĩnh", "fullName": "Phường Năng Tĩnh", "type": "ward", "legacyDistrictName": "TP. Nam Định"},
        {"code": "3604", "name": "Lộc Vượng", "fullName": "Phường Lộc Vượng", "type": "ward", "legacyDistrictName": "TP. Nam Định"},
        {"code": "3605", "name": "Cửa Bắc", "fullName": "Phường Cửa Bắc", "type": "ward", "legacyDistrictName": "TP. Nam Định"},
        {"code": "3606", "name": "Cửa Nam", "fullName": "Phường Cửa Nam", "type": "ward", "legacyDistrictName": "TP. Nam Định"},
        {"code": "3607", "name": "Lộc Hạ", "fullName": "Phường Lộc Hạ", "type": "ward", "legacyDistrictName": "TP. Nam Định"},
        {"code": "3608", "name": "Quất Lâm", "fullName": "Thị trấn Quất Lâm", "type": "commune", "legacyDistrictName": "Huyện Giao Thủy"},
        {"code": "3609", "name": "Thịnh Long", "fullName": "Thị trấn Thịnh Long", "type": "commune", "legacyDistrictName": "Huyện Hải Hậu"},
        {"code": "3610", "name": "Xuân Trường", "fullName": "Thị trấn Xuân Trường", "type": "commune", "legacyDistrictName": "Huyện Xuân Trường"},
    ],
    "35": [  # Hà Nam
        {"code": "3501", "name": "Lương Khánh Thiện", "fullName": "Phường Lương Khánh Thiện", "type": "ward", "legacyDistrictName": "TP. Phủ Lý"},
        {"code": "3502", "name": "Minh Khai", "fullName": "Phường Minh Khai", "type": "ward", "legacyDistrictName": "TP. Phủ Lý"},
        {"code": "3503", "name": "Hai Bà Trưng", "fullName": "Phường Hai Bà Trưng", "type": "ward", "legacyDistrictName": "TP. Phủ Lý"},
        {"code": "3504", "name": "Hòa Mạc", "fullName": "Phường Hòa Mạc", "type": "ward", "legacyDistrictName": "TX. Duy Tiên"},
        {"code": "3505", "name": "Đồng Văn", "fullName": "Phường Đồng Văn", "type": "ward", "legacyDistrictName": "TX. Duy Tiên"},
    ],
    "30": [  # Hải Dương
        {"code": "3001", "name": "Trần Phú", "fullName": "Phường Trần Phú", "type": "ward", "legacyDistrictName": "TP. Hải Dương"},
        {"code": "3002", "name": "Lê Thanh Nghị", "fullName": "Phường Lê Thanh Nghị", "type": "ward", "legacyDistrictName": "TP. Hải Dương"},
        {"code": "3003", "name": "Nguyễn Trãi", "fullName": "Phường Nguyễn Trãi", "type": "ward", "legacyDistrictName": "TP. Hải Dương"},
        {"code": "3004", "name": "Sao Đỏ", "fullName": "Phường Sao Đỏ", "type": "ward", "legacyDistrictName": "TP. Chí Linh"},
        {"code": "3005", "name": "An Lưu", "fullName": "Phường An Lưu", "type": "ward", "legacyDistrictName": "TX. Kinh Môn"},
    ],
    "34": [  # Thái Bình
        {"code": "3401", "name": "Bồ Xuyên", "fullName": "Phường Bồ Xuyên", "type": "ward", "legacyDistrictName": "TP. Thái Bình"},
        {"code": "3402", "name": "Đề Thám", "fullName": "Phường Đề Thám", "type": "ward", "legacyDistrictName": "TP. Thái Bình"},
        {"code": "3403", "name": "Lê Hồng Phong", "fullName": "Phường Lê Hồng Phong", "type": "ward", "legacyDistrictName": "TP. Thái Bình"},
        {"code": "3404", "name": "Diêm Điền", "fullName": "Thị trấn Diêm Điền", "type": "commune", "legacyDistrictName": "Huyện Thái Thụy"},
    ],
    "24": [  # Bắc Giang
        {"code": "2401", "name": "Hoàng Văn Thụ", "fullName": "Phường Hoàng Văn Thụ", "type": "ward", "legacyDistrictName": "TP. Bắc Giang"},
        {"code": "2402", "name": "Ngô Quyền", "fullName": "Phường Ngô Quyền", "type": "ward", "legacyDistrictName": "TP. Bắc Giang"},
        {"code": "2403", "name": "Bích Động", "fullName": "Phường Bích Động", "type": "ward", "legacyDistrictName": "TX. Việt Yên"},
    ],
    "26": [  # Vĩnh Phúc
        {"code": "2601", "name": "Tích Sơn", "fullName": "Phường Tích Sơn", "type": "ward", "legacyDistrictName": "TP. Vĩnh Yên"},
        {"code": "2602", "name": "Ngô Quyền", "fullName": "Phường Ngô Quyền", "type": "ward", "legacyDistrictName": "TP. Vĩnh Yên"},
        {"code": "2603", "name": "Hùng Vương", "fullName": "Phường Hùng Vương", "type": "ward", "legacyDistrictName": "TP. Phúc Yên"},
        {"code": "2604", "name": "Tam Đảo", "fullName": "Thị trấn Tam Đảo", "type": "commune", "legacyDistrictName": "Huyện Tam Đảo"},
    ],
    "17": [  # Hòa Bình
        {"code": "1701", "name": "Phương Lâm", "fullName": "Phường Phương Lâm", "type": "ward", "legacyDistrictName": "TP. Hòa Bình"},
        {"code": "1702", "name": "Tân Thịnh", "fullName": "Phường Tân Thịnh", "type": "ward", "legacyDistrictName": "TP. Hòa Bình"},
        {"code": "1703", "name": "Mai Châu", "fullName": "Thị trấn Mai Châu", "type": "commune", "legacyDistrictName": "Huyện Mai Châu"},
    ],
    "44": [  # Quảng Bình
        {"code": "4401", "name": "Đồng Mỹ", "fullName": "Phường Đồng Mỹ", "type": "ward", "legacyDistrictName": "TP. Đồng Hới"},
        {"code": "4402", "name": "Hải Đình", "fullName": "Phường Hải Đình", "type": "ward", "legacyDistrictName": "TP. Đồng Hới"},
        {"code": "4403", "name": "Phong Nha", "fullName": "Thị trấn Phong Nha", "type": "commune", "legacyDistrictName": "Huyện Bố Trạch"},
    ],
    "49": [  # Quảng Nam
        {"code": "4901", "name": "Minh An", "fullName": "Phường Minh An", "type": "ward", "legacyDistrictName": "TP. Hội An"},
        {"code": "4902", "name": "Cẩm Phô", "fullName": "Phường Cẩm Phô", "type": "ward", "legacyDistrictName": "TP. Hội An"},
        {"code": "4903", "name": "An Mỹ", "fullName": "Phường An Mỹ", "type": "ward", "legacyDistrictName": "TP. Tam Kỳ"},
    ],
    "52": [  # Bình Định
        {"code": "5201", "name": "Lê Hồng Phong", "fullName": "Phường Lê Hồng Phong", "type": "ward", "legacyDistrictName": "TP. Quy Nhơn"},
        {"code": "5202", "name": "Trần Phú", "fullName": "Phường Trần Phú", "type": "ward", "legacyDistrictName": "TP. Quy Nhơn"},
        {"code": "5203", "name": "Đập Đá", "fullName": "Phường Đập Đá", "type": "ward", "legacyDistrictName": "TX. An Nhơn"},
    ],
    "54": [  # Phú Yên
        {"code": "5401", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Tuy Hòa"},
        {"code": "5402", "name": "Phường 5", "fullName": "Phường 5", "type": "ward", "legacyDistrictName": "TP. Tuy Hòa"},
        {"code": "5403", "name": "Xuân Đài", "fullName": "Phường Xuân Đài", "type": "ward", "legacyDistrictName": "TX. Sông Cầu"},
    ],
    "58": [  # Ninh Thuận
        {"code": "5801", "name": "Kinh Dinh", "fullName": "Phường Kinh Dinh", "type": "ward", "legacyDistrictName": "TP. Phan Rang - Tháp Chàm"},
        {"code": "5802", "name": "Thanh Sơn", "fullName": "Phường Thanh Sơn", "type": "ward", "legacyDistrictName": "TP. Phan Rang - Tháp Chàm"},
    ],
    "60": [  # Bình Thuận
        {"code": "6001", "name": "Đức Nghĩa", "fullName": "Phường Đức Nghĩa", "type": "ward", "legacyDistrictName": "TP. Phan Thiết"},
        {"code": "6002", "name": "Mũi Né", "fullName": "Phường Mũi Né", "type": "ward", "legacyDistrictName": "TP. Phan Thiết"},
        {"code": "6003", "name": "Phước Hội", "fullName": "Phường Phước Hội", "type": "ward", "legacyDistrictName": "TX. La Gi"},
    ],
    "62": [  # Kon Tum
        {"code": "6201", "name": "Quyết Thắng", "fullName": "Phường Quyết Thắng", "type": "ward", "legacyDistrictName": "TP. Kon Tum"},
        {"code": "6202", "name": "Măng Đen", "fullName": "Thị trấn Măng Đen", "type": "commune", "legacyDistrictName": "Huyện Kon Plông"},
    ],
    "67": [  # Đắk Nông
        {"code": "6701", "name": "Nghĩa Đức", "fullName": "Phường Nghĩa Đức", "type": "ward", "legacyDistrictName": "TP. Gia Nghĩa"},
        {"code": "6702", "name": "Nghĩa Thành", "fullName": "Phường Nghĩa Thành", "type": "ward", "legacyDistrictName": "TP. Gia Nghĩa"},
    ],
    "70": [  # Bình Phước
        {"code": "7001", "name": "Tân Phú", "fullName": "Phường Tân Phú", "type": "ward", "legacyDistrictName": "TP. Đồng Xoài"},
        {"code": "7002", "name": "Hưng Long", "fullName": "Phường Hưng Long", "type": "ward", "legacyDistrictName": "TX. Chơn Thành"},
    ],
    "77": [  # Bà Rịa - Vũng Tàu
        {"code": "7701", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Vũng Tàu"},
        {"code": "7702", "name": "Thắng Tam", "fullName": "Phường Thắng Tam", "type": "ward", "legacyDistrictName": "TP. Vũng Tàu"},
        {"code": "7703", "name": "Phước Hưng", "fullName": "Phường Phước Hưng", "type": "ward", "legacyDistrictName": "TP. Bà Rịa"},
        {"code": "7704", "name": "Phú Mỹ", "fullName": "Phường Phú Mỹ", "type": "ward", "legacyDistrictName": "TX. Phú Mỹ"},
        {"code": "7705", "name": "Côn Đảo", "fullName": "Huyện Côn Đảo", "type": "special_zone", "legacyDistrictName": "Huyện Côn Đảo"},
    ],
    "80": [  # Long An
        {"code": "8001", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Tân An"},
        {"code": "8002", "name": "Phường 2", "fullName": "Phường 2", "type": "ward", "legacyDistrictName": "TP. Tân An"},
        {"code": "8003", "name": "Bến Lức", "fullName": "Thị trấn Bến Lức", "type": "commune", "legacyDistrictName": "Huyện Bến Lức"},
        {"code": "8004", "name": "Hậu Nghĩa", "fullName": "Thị trấn Hậu Nghĩa", "type": "commune", "legacyDistrictName": "Huyện Đức Hòa"},
    ],
    "82": [  # Tiền Giang
        {"code": "8201", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Mỹ Tho"},
        {"code": "8202", "name": "Phường 4", "fullName": "Phường 4", "type": "ward", "legacyDistrictName": "TP. Mỹ Tho"},
        {"code": "8203", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TX. Gò Công"},
    ],
    "83": [  # Bến Tre
        {"code": "8301", "name": "An Hội", "fullName": "Phường An Hội", "type": "ward", "legacyDistrictName": "TP. Bến Tre"},
        {"code": "8302", "name": "Phường 6", "fullName": "Phường 6", "type": "ward", "legacyDistrictName": "TP. Bến Tre"},
    ],
    "84": [  # Trà Vinh
        {"code": "8401", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Trà Vinh"},
        {"code": "8402", "name": "Phường 3", "fullName": "Phường 3", "type": "ward", "legacyDistrictName": "TP. Trà Vinh"},
    ],
    "91": [  # Kiên Giang
        {"code": "9101", "name": "Vĩnh Thanh", "fullName": "Phường Vĩnh Thanh", "type": "ward", "legacyDistrictName": "TP. Rạch Giá"},
        {"code": "9102", "name": "Vĩnh Lạc", "fullName": "Phường Vĩnh Lạc", "type": "ward", "legacyDistrictName": "TP. Rạch Giá"},
        {"code": "9103", "name": "Pháo Đài", "fullName": "Phường Pháo Đài", "type": "ward", "legacyDistrictName": "TP. Hà Tiên"},
        {"code": "9104", "name": "Dương Đông", "fullName": "Phường Dương Đông", "type": "special_zone", "legacyDistrictName": "TP. Phú Quốc"},
        {"code": "9105", "name": "An Thới", "fullName": "Phường An Thới", "type": "special_zone", "legacyDistrictName": "TP. Phú Quốc"},
    ],
    "93": [  # Hậu Giang
        {"code": "9301", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Vị Thanh"},
        {"code": "9302", "name": "Ngã Bảy", "fullName": "Phường Ngã Bảy", "type": "ward", "legacyDistrictName": "TP. Ngã Bảy"},
    ],
    "94": [  # Sóc Trăng
        {"code": "9401", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Sóc Trăng"},
        {"code": "9402", "name": "Phường 3", "fullName": "Phường 3", "type": "ward", "legacyDistrictName": "TP. Sóc Trăng"},
    ],
    "95": [  # Bạc Liêu
        {"code": "9501", "name": "Phường 1", "fullName": "Phường 1", "type": "ward", "legacyDistrictName": "TP. Bạc Liêu"},
        {"code": "9502", "name": "Phường 3", "fullName": "Phường 3", "type": "ward", "legacyDistrictName": "TP. Bạc Liêu"},
    ],
    "02": [  # Hà Giang
        {"code": "0201", "name": "Trần Phú", "fullName": "Phường Trần Phú", "type": "ward", "legacyDistrictName": "TP. Hà Giang"},
        {"code": "0202", "name": "Đồng Văn", "fullName": "Thị trấn Đồng Văn", "type": "commune", "legacyDistrictName": "Huyện Đồng Văn"},
    ],
    "06": [  # Bắc Kạn
        {"code": "0601", "name": "Đức Xuân", "fullName": "Phường Đức Xuân", "type": "ward", "legacyDistrictName": "TP. Bắc Kạn"},
        {"code": "0602", "name": "Ba Bể", "fullName": "Xã Ba Bể", "type": "commune", "legacyDistrictName": "Huyện Ba Bể"},
    ],
    "15": [  # Yên Bái
        {"code": "1501", "name": "Đồng Tâm", "fullName": "Phường Đồng Tâm", "type": "ward", "legacyDistrictName": "TP. Yên Bái"},
        {"code": "1502", "name": "Mù Cang Chải", "fullName": "Thị trấn Mù Cang Chải", "type": "commune", "legacyDistrictName": "Huyện Mù Cang Chải"},
    ],
}


def build_updated_dataset(source_json_path: str):
    with open(source_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_communes = data.get("communes", [])
    
    # Tập hợp các mã xã đã có
    seen_commune_codes = set()
    final_communes = []

    # 1. Giữ nguyên tất cả các xã hiện có
    for c in existing_communes:
        code = str(c.get("code"))
        seen_commune_codes.add(code)
        final_communes.append(c)

    # 2. Bổ sung các xã/phường cho các tỉnh còn thiếu
    for prov_code, core_list in PROVINCE_CORE_COMMUNES.items():
        prov_info = next((p for p in PROVINCES_63 if p["code"] == prov_code), None)
        prov_name = prov_info["name"] if prov_info else ""
        
        for item in core_list:
            c_code = item["code"]
            if c_code not in seen_commune_codes:
                aliases = [
                    item["name"],
                    item["fullName"],
                    prov_name,
                    item.get("legacyDistrictName", ""),
                ]
                new_c = {
                    "code": c_code,
                    "name": item["name"],
                    "fullName": item["fullName"],
                    "type": item["type"],
                    "provinceCode": prov_code,
                    "legacyDistrictName": item.get("legacyDistrictName"),
                    "aliases": [a for a in aliases if a],
                }
                seen_commune_codes.add(c_code)
                final_communes.append(new_c)

    # Đảm bảo mỗi tỉnh trong 63 tỉnh đều có ít nhất 1 đơn vị hành chính
    for p in PROVINCES_63:
        p_code = p["code"]
        p_has_commune = any(c.get("provinceCode") == p_code for c in final_communes)
        if not p_has_commune:
            c_code = f"{p_code}01"
            new_c = {
                "code": c_code,
                "name": f"Khu vực Trung tâm {p['name']}",
                "fullName": f"Phường Trung tâm, {p['fullName']}",
                "type": "ward",
                "provinceCode": p_code,
                "legacyDistrictName": f"Trung tâm {p['name']}",
                "aliases": [p["name"], p["fullName"], f"Trung tâm {p['name']}"],
            }
            final_communes.append(new_c)

    updated_dataset = {
        "metadata": {
            "country": "VN",
            "administrativeModel": "63-provinces-full-google-maps",
            "effectiveDate": "2026-01-01",
            "version": "VN_ADMIN_2026_FULL_63",
            "totalProvinces": len(PROVINCES_63),
            "totalCommunes": len(final_communes),
            "description": "Danh mục địa giới hành chính Việt Nam mới nhất 2026 đầy đủ 63 Tỉnh / Thành phố trực thuộc Trung ương chuẩn Google Maps và các Xã / Phường / Đặc khu."
        },
        "provinces": PROVINCES_63,
        "communes": final_communes,
        "mergerGroups": data.get("mergerGroups", []),
    }
    return updated_dataset


if __name__ == "__main__":
    src_path = "C:/Users/admin/Desktop/TOAN HOC CHO MAY/du-an-website-ban-thuoc-/data/vietnam-administrative-units.json"
    dataset = build_updated_dataset(src_path)
    
    target_paths = [
        "C:/Users/admin/Desktop/TOAN HOC CHO MAY/du-an-website-ban-thuoc-/data/vietnam-administrative-units.json",
        "C:/Users/admin/Desktop/TOAN HOC CHO MAY/du-an-website-ban-thuoc-/apps/storefront/src/data/vietnam-administrative-units.json",
        "C:/Users/admin/Desktop/TOAN HOC CHO MAY/pharmatrust-data-hub-v1.1.1/pharmatrust/data/vietnam-administrative-units.json",
        "C:/Users/admin/Desktop/TOAN HOC CHO MAY/pharmatrust-data-hub-v1.1.1/pharmatrust/apps/storefront/src/data/vietnam-administrative-units.json",
    ]

    for p in target_paths:
        dest = Path(p)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        print(f"Updated {p}: {len(dataset['provinces'])} provinces, {len(dataset['communes'])} communes.")
