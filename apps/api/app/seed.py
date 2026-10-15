from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    AdministrativeUnit,
    CanonicalProduct,
    DataConflict,
    DataSource,
    Ingredient,
    ProductIngredient,
    ProductSourceField,
    RegulatoryRecord,
    User,
)
from app.models.enums import (
    ConflictSeverity,
    PublishStatus,
    RegulatoryStatus,
    RxOtcStatus,
    SourceType,
    UserRole,
)
from app.services.scoring import calculate_product_score


DEMO_USERS = [
    ("admin@pharmatrust.vn", "Admin@123456", "Quản trị viên", UserRole.ADMIN),
    ("manager_hn@pharmatrust.vn", "Warehouse@2026", "Quản lý kho Hà Nội", UserRole.WAREHOUSE_MANAGER),
    ("staff_hn@pharmatrust.vn", "Staff@2026", "Nhân viên kho Hà Nội", UserRole.WAREHOUSE_STAFF),
    ("buyer@pharmatrust.vn", "Buyer@123456", "Người mua hàng", UserRole.CUSTOMER),
]


def seed_users(db):
    for email, password, name, role in DEMO_USERS:
        if not db.scalar(select(User.id).where(User.email == email)):
            db.add(User(email=email, password_hash=hash_password(password), full_name=name, role=role))


REAL_SOURCES = [
    (
        "DAV_CONGBOTHUOC",
        "Cục Quản lý Dược Việt Nam (DAV - Công Bố Thuốc)",
        SourceType.REGULATORY,
        5,
        1.0,
        "https://dichvucong.dav.gov.vn/congbothuoc/index",
        "Cơ sở dữ liệu giấy phép lưu hành thuốc chính thức tại Việt Nam.",
    ),
    (
        "DRUGBANK_VN",
        "Ngân hàng Dữ liệu Dược Quốc gia (DrugBank VN)",
        SourceType.REGULATORY,
        5,
        1.0,
        "https://drugbank.vn",
        "Ngân hàng dữ liệu ngành Dược do Cục Quản lý Dược phát hành.",
    ),
    (
        "PHARMACITY",
        "Chuỗi Nhà thuốc Pharmacity",
        SourceType.RETAILER,
        2,
        0.6,
        "https://www.pharmacity.vn",
        "Dữ liệu danh mục sản phẩm từ hệ thống nhà thuốc Pharmacity.",
    ),
    (
        "LONG_CHAU",
        "Chuỗi Nhà thuốc FPT Long Châu",
        SourceType.RETAILER,
        2,
        0.6,
        "https://nhathuoclongchau.com.vn",
        "Dữ liệu danh mục sản phẩm từ hệ thống nhà thuốc Long Châu.",
    ),
    (
        "MANUAL_IMPORT",
        "Nhập tệp dữ liệu thuốc thật (CSV / Excel / PDF)",
        SourceType.MANUAL_UPLOAD,
        4,
        0.85,
        None,
        "Dữ liệu thuốc chính thức do quản trị viên tải lên từ tệp.",
    ),
    (
        "MANUAL",
        "Nhập tệp dữ liệu thủ công (CSV / Excel / PDF)",
        SourceType.MANUAL_UPLOAD,
        4,
        0.85,
        None,
        "Dữ liệu thuốc chính thức do quản trị viên tải lên từ tệp.",
    ),
]

ADMINISTRATIVE_UNITS = [
    # --- Tỉnh / Thành phố ---
    ("79", "Hồ Chí Minh", None, "PROVINCE", "Thành phố Hồ Chí Minh"),
    ("01", "Hà Nội", None, "PROVINCE", "Thành phố Hà Nội"),
    ("48", "Đà Nẵng", None, "PROVINCE", "Thành phố Đà Nẵng"),
    ("92", "Cần Thơ", None, "PROVINCE", "Thành phố Cần Thơ"),
    ("31", "Hải Phòng", None, "PROVINCE", "Thành phố Hải Phòng"),

    # --- Quận / Huyện TP.HCM ---
    ("760", "Quận 1", "79", "DISTRICT", "Quận 1, TP. Hồ Chí Minh"),
    ("761", "Quận 12", "79", "DISTRICT", "Quận 12, TP. Hồ Chí Minh"),
    ("765", "Quận Bình Thạnh", "79", "DISTRICT", "Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("766", "Quận Tân Bình", "79", "DISTRICT", "Quận Tân Bình, TP. Hồ Chí Minh"),
    ("769", "Thành phố Thủ Đức", "79", "DISTRICT", "Thành phố Thủ Đức, TP. Hồ Chí Minh"),
    ("770", "Quận 3", "79", "DISTRICT", "Quận 3, TP. Hồ Chí Minh"),
    ("771", "Quận 10", "79", "DISTRICT", "Quận 10, TP. Hồ Chí Minh"),

    # --- Phường / Xã TP.HCM ---
    # Quận 1 (760)
    ("26734", "Phường Bến Nghé", "760", "WARD", "Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh"),
    ("26740", "Phường Bến Thành", "760", "WARD", "Phường Bến Thành, Quận 1, TP. Hồ Chí Minh"),
    ("26743", "Phường Tân Định", "760", "WARD", "Phường Tân Định, Quận 1, TP. Hồ Chí Minh"),
    ("26746", "Phường Đa Kao", "760", "WARD", "Phường Đa Kao, Quận 1, TP. Hồ Chí Minh"),
    ("26749", "Phường Phạm Ngũ Lão", "760", "WARD", "Phường Phạm Ngũ Lão, Quận 1, TP. Hồ Chí Minh"),
    ("26752", "Phường Cô Giang", "760", "WARD", "Phường Cô Giang, Quận 1, TP. Hồ Chí Minh"),
    ("26755", "Phường Cầu Kho", "760", "WARD", "Phường Cầu Kho, Quận 1, TP. Hồ Chí Minh"),
    ("26758", "Phường Cầu Ông Lãnh", "760", "WARD", "Phường Cầu Ông Lãnh, Quận 1, TP. Hồ Chí Minh"),
    ("26761", "Phường Nguyễn Cư Trinh", "760", "WARD", "Phường Nguyễn Cư Trinh, Quận 1, TP. Hồ Chí Minh"),
    ("26764", "Phường Nguyễn Thái Bình", "760", "WARD", "Phường Nguyễn Thái Bình, Quận 1, TP. Hồ Chí Minh"),
    # Quận Tân Bình (766)
    ("26950", "Phường 1", "766", "WARD", "Phường 1, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("26953", "Phường 2", "766", "WARD", "Phường 2, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("26956", "Phường 3", "766", "WARD", "Phường 3, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("26959", "Phường 4", "766", "WARD", "Phường 4, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("26962", "Phường 12", "766", "WARD", "Phường 12, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("26965", "Phường 13", "766", "WARD", "Phường 13, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("26968", "Phường 14", "766", "WARD", "Phường 14, Quận Tân Bình, TP. Hồ Chí Minh"),
    ("26971", "Phường 15", "766", "WARD", "Phường 15, Quận Tân Bình, TP. Hồ Chí Minh"),
    # Quận 3 (770)
    ("27139", "Phường Võ Thị Sáu", "770", "WARD", "Phường Võ Thị Sáu, Quận 3, TP. Hồ Chí Minh"),
    ("27142", "Phường 1", "770", "WARD", "Phường 1, Quận 3, TP. Hồ Chí Minh"),
    ("27145", "Phường 2", "770", "WARD", "Phường 2, Quận 3, TP. Hồ Chí Minh"),
    ("27148", "Phường 3", "770", "WARD", "Phường 3, Quận 3, TP. Hồ Chí Minh"),
    ("27151", "Phường 4", "770", "WARD", "Phường 4, Quận 3, TP. Hồ Chí Minh"),
    ("27154", "Phường 5", "770", "WARD", "Phường 5, Quận 3, TP. Hồ Chí Minh"),
    ("27157", "Phường 9", "770", "WARD", "Phường 9, Quận 3, TP. Hồ Chí Minh"),
    ("27160", "Phường 10", "770", "WARD", "Phường 10, Quận 3, TP. Hồ Chí Minh"),
    ("27163", "Phường 11", "770", "WARD", "Phường 11, Quận 3, TP. Hồ Chí Minh"),
    ("27166", "Phường 12", "770", "WARD", "Phường 12, Quận 3, TP. Hồ Chí Minh"),
    ("27169", "Phường 14", "770", "WARD", "Phường 14, Quận 3, TP. Hồ Chí Minh"),
    # Quận 10 (771)
    ("27181", "Phường 1", "771", "WARD", "Phường 1, Quận 10, TP. Hồ Chí Minh"),
    ("27184", "Phường 2", "771", "WARD", "Phường 2, Quận 10, TP. Hồ Chí Minh"),
    ("27187", "Phường 4", "771", "WARD", "Phường 4, Quận 10, TP. Hồ Chí Minh"),
    ("27190", "Phường 6", "771", "WARD", "Phường 6, Quận 10, TP. Hồ Chí Minh"),
    ("27193", "Phường 9", "771", "WARD", "Phường 9, Quận 10, TP. Hồ Chí Minh"),
    ("27196", "Phường 12", "771", "WARD", "Phường 12, Quận 10, TP. Hồ Chí Minh"),
    ("27199", "Phường 14", "771", "WARD", "Phường 14, Quận 10, TP. Hồ Chí Minh"),
    ("27202", "Phường 15", "771", "WARD", "Phường 15, Quận 10, TP. Hồ Chí Minh"),
    # Bình Thạnh (765)
    ("26884", "Phường 1", "765", "WARD", "Phường 1, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26887", "Phường 2", "765", "WARD", "Phường 2, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26890", "Phường 3", "765", "WARD", "Phường 3, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26893", "Phường 12", "765", "WARD", "Phường 12, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26896", "Phường 14", "765", "WARD", "Phường 14, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26899", "Phường 15", "765", "WARD", "Phường 15, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26902", "Phường 19", "765", "WARD", "Phường 19, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26905", "Phường 25", "765", "WARD", "Phường 25, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    ("26908", "Phường 26", "765", "WARD", "Phường 26, Quận Bình Thạnh, TP. Hồ Chí Minh"),
    # Quận 12 (761)
    ("26767", "Phường Thạnh Xuân", "761", "WARD", "Phường Thạnh Xuân, Quận 12, TP. Hồ Chí Minh"),
    ("26770", "Phường Thạnh Lộc", "761", "WARD", "Phường Thạnh Lộc, Quận 12, TP. Hồ Chí Minh"),
    ("26773", "Phường Hiệp Thành", "761", "WARD", "Phường Hiệp Thành, Quận 12, TP. Hồ Chí Minh"),
    ("26776", "Phường Thới An", "761", "WARD", "Phường Thới An, Quận 12, TP. Hồ Chí Minh"),
    ("26779", "Phường Tân Chánh Hiệp", "761", "WARD", "Phường Tân Chánh Hiệp, Quận 12, TP. Hồ Chí Minh"),
    ("26782", "Phường An Phú Đông", "761", "WARD", "Phường An Phú Đông, Quận 12, TP. Hồ Chí Minh"),
    ("26785", "Phường Tân Thới Hiệp", "761", "WARD", "Phường Tân Thới Hiệp, Quận 12, TP. Hồ Chí Minh"),
    ("26788", "Phường Trung Mỹ Tây", "761", "WARD", "Phường Trung Mỹ Tây, Quận 12, TP. Hồ Chí Minh"),
    ("26791", "Phường Tân Hưng Thuận", "761", "WARD", "Phường Tân Hưng Thuận, Quận 12, TP. Hồ Chí Minh"),
    ("26794", "Phường Đông Hưng Thuận", "761", "WARD", "Phường Đông Hưng Thuận, Quận 12, TP. Hồ Chí Minh"),
    ("26797", "Phường Tân Thới Nhất", "761", "WARD", "Phường Tân Thới Nhất, Quận 12, TP. Hồ Chí Minh"),
    # Thủ Đức (769)
    ("26815", "Phường Thảo Điền", "769", "WARD", "Phường Thảo Điền, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26818", "Phường An Phú", "769", "WARD", "Phường An Phú, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26821", "Phường Hiệp Phú", "769", "WARD", "Phường Hiệp Phú, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26824", "Phường Tăng Nhơn Phú A", "769", "WARD", "Phường Tăng Nhơn Phú A, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26827", "Phường Phước Long B", "769", "WARD", "Phường Phước Long B, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26830", "Phường Linh Trung", "769", "WARD", "Phường Linh Trung, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26833", "Phường Linh Chiểu", "769", "WARD", "Phường Linh Chiểu, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26836", "Phường Tam Phú", "769", "WARD", "Phường Tam Phú, TP. Thủ Đức, TP. Hồ Chí Minh"),
    ("26839", "Phường Bình Chiểu", "769", "WARD", "Phường Bình Chiểu, TP. Thủ Đức, TP. Hồ Chí Minh"),

    # --- Quận / Huyện Hà Nội ---
    ("001", "Quận Ba Đình", "01", "DISTRICT", "Quận Ba Đình, TP. Hà Nội"),
    ("002", "Quận Hoàn Kiếm", "01", "DISTRICT", "Quận Hoàn Kiếm, TP. Hà Nội"),
    ("004", "Quận Đống Đa", "01", "DISTRICT", "Quận Đống Đa, TP. Hà Nội"),
    ("005", "Quận Hai Bà Trưng", "01", "DISTRICT", "Quận Hai Bà Trưng, TP. Hà Nội"),
    ("009", "Quận Cầu Giấy", "01", "DISTRICT", "Quận Cầu Giấy, TP. Hà Nội"),

    # --- Phường / Xã Hà Nội ---
    # Ba Đình (001)
    ("00001", "Phường Phúc Xá", "001", "WARD", "Phường Phúc Xá, Quận Ba Đình, TP. Hà Nội"),
    ("00004", "Phường Trúc Bạch", "001", "WARD", "Phường Trúc Bạch, Quận Ba Đình, TP. Hà Nội"),
    ("00006", "Phường Vĩnh Phúc", "001", "WARD", "Phường Vĩnh Phúc, Quận Ba Đình, TP. Hà Nội"),
    ("00007", "Phường Cống Vị", "001", "WARD", "Phường Cống Vị, Quận Ba Đình, TP. Hà Nội"),
    ("00008", "Phường Liễu Giai", "001", "WARD", "Phường Liễu Giai, Quận Ba Đình, TP. Hà Nội"),
    ("00010", "Phường Nguyễn Trung Trực", "001", "WARD", "Phường Nguyễn Trung Trực, Quận Ba Đình, TP. Hà Nội"),
    ("00013", "Phường Quán Thánh", "001", "WARD", "Phường Quán Thánh, Quận Ba Đình, TP. Hà Nội"),
    ("00016", "Phường Ngọc Hà", "001", "WARD", "Phường Ngọc Hà, Quận Ba Đình, TP. Hà Nội"),
    ("00019", "Phường Điện Biên", "001", "WARD", "Phường Điện Biên, Quận Ba Đình, TP. Hà Nội"),
    ("00022", "Phường Đội Cấn", "001", "WARD", "Phường Đội Cấn, Quận Ba Đình, TP. Hà Nội"),
    ("00025", "Phường Ngọc Khánh", "001", "WARD", "Phường Ngọc Khánh, Quận Ba Đình, TP. Hà Nội"),
    ("00028", "Phường Kim Mã", "001", "WARD", "Phường Kim Mã, Quận Ba Đình, TP. Hà Nội"),
    ("00031", "Phường Giảng Võ", "001", "WARD", "Phường Giảng Võ, Quận Ba Đình, TP. Hà Nội"),
    ("00034", "Phường Thành Công", "001", "WARD", "Phường Thành Công, Quận Ba Đình, TP. Hà Nội"),
    # Hoàn Kiếm (002)
    ("00037", "Phường Hàng Bạc", "002", "WARD", "Phường Hàng Bạc, Quận Hoàn Kiếm, TP. Hà Nội"),
    ("00040", "Phường Hàng Buồm", "002", "WARD", "Phường Hàng Buồm, Quận Hoàn Kiếm, TP. Hà Nội"),
    ("00043", "Phường Hàng Đào", "002", "WARD", "Phường Hàng Đào, Quận Hoàn Kiếm, TP. Hà Nội"),
    ("00046", "Phường Hàng Gai", "002", "WARD", "Phường Hàng Gai, Quận Hoàn Kiếm, TP. Hà Nội"),
    ("00049", "Phường Tràng Tiền", "002", "WARD", "Phường Tràng Tiền, Quận Hoàn Kiếm, TP. Hà Nội"),
    ("00052", "Phường Phan Chu Trinh", "002", "WARD", "Phường Phan Chu Trinh, Quận Hoàn Kiếm, TP. Hà Nội"),
    ("00055", "Phường Cửa Nam", "002", "WARD", "Phường Cửa Nam, Quận Hoàn Kiếm, TP. Hà Nội"),
    ("00058", "Phường Lý Thái Tổ", "002", "WARD", "Phường Lý Thái Tổ, Quận Hoàn Kiếm, TP. Hà Nội"),
    # Đống Đa (004)
    ("00061", "Phường Cát Linh", "004", "WARD", "Phường Cát Linh, Quận Đống Đa, TP. Hà Nội"),
    ("00064", "Phường Văn Miếu", "004", "WARD", "Phường Văn Miếu, Quận Đống Đa, TP. Hà Nội"),
    ("00067", "Phường Quốc Tử Giám", "004", "WARD", "Phường Quốc Tử Giám, Quận Đống Đa, TP. Hà Nội"),
    ("00070", "Phường Láng Thượng", "004", "WARD", "Phường Láng Thượng, Quận Đống Đa, TP. Hà Nội"),
    ("00073", "Phường Ô Chợ Dừa", "004", "WARD", "Phường Ô Chợ Dừa, Quận Đống Đa, TP. Hà Nội"),
    ("00076", "Phường Trung Liệt", "004", "WARD", "Phường Trung Liệt, Quận Đống Đa, TP. Hà Nội"),
    ("00079", "Phường Khâm Thiên", "004", "WARD", "Phường Khâm Thiên, Quận Đống Đa, TP. Hà Nội"),
    ("00082", "Phường Nam Đồng", "004", "WARD", "Phường Nam Đồng, Quận Đống Đa, TP. Hà Nội"),
    ("00085", "Phường Kim Liên", "004", "WARD", "Phường Kim Liên, Quận Đống Đa, TP. Hà Nội"),
    ("00088", "Phường Phương Mai", "004", "WARD", "Phường Phương Mai, Quận Đống Đa, TP. Hà Nội"),
    # Hai Bà Trưng (005)
    ("00091", "Phường Nguyễn Du", "005", "WARD", "Phường Nguyễn Du, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00094", "Phường Bạch Đằng", "005", "WARD", "Phường Bạch Đằng, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00097", "Phường Phạm Đình Hổ", "005", "WARD", "Phường Phạm Đình Hổ, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00100", "Phường Lê Đại Hành", "005", "WARD", "Phường Lê Đại Hành, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00103", "Phường Đồng Nhân", "005", "WARD", "Phường Đồng Nhân, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00106", "Phường Phố Huế", "005", "WARD", "Phường Phố Huế, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00115", "Phường Thanh Nhàn", "005", "WARD", "Phường Thanh Nhàn, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00121", "Phường Bách Khoa", "005", "WARD", "Phường Bách Khoa, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00127", "Phường Bạch Mai", "005", "WARD", "Phường Bạch Mai, Quận Hai Bà Trưng, TP. Hà Nội"),
    ("00133", "Phường Vĩnh Tuy", "005", "WARD", "Phường Vĩnh Tuy, Quận Hai Bà Trưng, TP. Hà Nội"),
    # Cầu Giấy (009)
    ("00142", "Phường Nghĩa Đô", "009", "WARD", "Phường Nghĩa Đô, Quận Cầu Giấy, TP. Hà Nội"),
    ("00145", "Phường Nghĩa Tân", "009", "WARD", "Phường Nghĩa Tân, Quận Cầu Giấy, TP. Hà Nội"),
    ("00148", "Phường Mai Dịch", "009", "WARD", "Phường Mai Dịch, Quận Cầu Giấy, TP. Hà Nội"),
    ("00151", "Phường Dịch Vọng", "009", "WARD", "Phường Dịch Vọng, Quận Cầu Giấy, TP. Hà Nội"),
    ("00154", "Phường Dịch Vọng Hậu", "009", "WARD", "Phường Dịch Vọng Hậu, Quận Cầu Giấy, TP. Hà Nội"),
    ("00157", "Phường Quan Hoa", "009", "WARD", "Phường Quan Hoa, Quận Cầu Giấy, TP. Hà Nội"),
    ("00160", "Phường Yên Hòa", "009", "WARD", "Phường Yên Hòa, Quận Cầu Giấy, TP. Hà Nội"),
    ("00163", "Phường Trung Hòa", "009", "WARD", "Phường Trung Hòa, Quận Cầu Giấy, TP. Hà Nội"),

    # --- Đà Nẵng (48) ---
    ("490", "Quận Hải Châu", "48", "DISTRICT", "Quận Hải Châu, TP. Đà Nẵng"),
    ("492", "Quận Thanh Khê", "48", "DISTRICT", "Quận Thanh Khê, TP. Đà Nẵng"),
    ("493", "Quận Sơn Trà", "48", "DISTRICT", "Quận Sơn Trà, TP. Đà Nẵng"),
    ("49001", "Phường Hải Châu 1", "490", "WARD", "Phường Hải Châu 1, Quận Hải Châu, TP. Đà Nẵng"),
    ("49002", "Phường Hải Châu 2", "490", "WARD", "Phường Hải Châu 2, Quận Hải Châu, TP. Đà Nẵng"),
    ("49003", "Phường Thạch Thang", "490", "WARD", "Phường Thạch Thang, Quận Hải Châu, TP. Đà Nẵng"),
    ("49201", "Phường Tam Thuận", "492", "WARD", "Phường Tam Thuận, Quận Thanh Khê, TP. Đà Nẵng"),
    ("49202", "Phường Thanh Khê Tây", "492", "WARD", "Phường Thanh Khê Tây, Quận Thanh Khê, TP. Đà Nẵng"),
    ("49301", "Phường An Hải Bắc", "493", "WARD", "Phường An Hải Bắc, Quận Sơn Trà, TP. Đà Nẵng"),

    # --- Cần Thơ (92) ---
    ("916", "Quận Ninh Kiều", "92", "DISTRICT", "Quận Ninh Kiều, TP. Cần Thơ"),
    ("917", "Quận Bình Thủy", "92", "DISTRICT", "Quận Bình Thủy, TP. Cần Thơ"),
    ("91601", "Phường Cái Khế", "916", "WARD", "Phường Cái Khế, Quận Ninh Kiều, TP. Cần Thơ"),
    ("91602", "Phường An Hòa", "916", "WARD", "Phường An Hòa, Quận Ninh Kiều, TP. Cần Thơ"),
    ("91605", "Phường Tân An", "916", "WARD", "Phường Tân An, Quận Ninh Kiều, TP. Cần Thơ"),
    ("91701", "Phường Bình Thủy", "917", "WARD", "Phường Bình Thủy, Quận Bình Thủy, TP. Cần Thơ"),

    # --- Hải Phòng (31) ---
    ("303", "Quận Hồng Bàng", "31", "DISTRICT", "Quận Hồng Bàng, TP. Hải Phòng"),
    ("304", "Quận Ngô Quyền", "31", "DISTRICT", "Quận Ngô Quyền, TP. Hải Phòng"),
    ("30301", "Phường Hạ Lý", "303", "WARD", "Phường Hạ Lý, Quận Hồng Bàng, TP. Hải Phòng"),
    ("30302", "Phường Hoàng Văn Thụ", "303", "WARD", "Phường Hoàng Văn Thụ, Quận Hồng Bàng, TP. Hải Phòng"),
    ("30401", "Phường Máy Chai", "304", "WARD", "Phường Máy Chai, Quận Ngô Quyền, TP. Hải Phòng"),
]


def seed_administrative_units(db):
    for code, name, parent_code, level, full_name in ADMINISTRATIVE_UNITS:
        existing = db.scalar(select(AdministrativeUnit).where(AdministrativeUnit.code == code))
        if not existing:
            db.add(
                AdministrativeUnit(
                    code=code,
                    name=name,
                    parent_code=parent_code,
                    level=level,
                    full_name=full_name,
                )
            )
    db.flush()


def seed_sources(db):
    for code, name, source_type, level, weight, base_url, note in REAL_SOURCES:
        existing = db.scalar(select(DataSource).where(DataSource.code == code))
        if not existing:
            db.add(
                DataSource(
                    code=code,
                    name=name,
                    source_type=source_type,
                    authority_level=level,
                    authority_weight=weight,
                    base_url=base_url,
                    enabled=True,
                    robots_status="ALLOWED" if base_url else "NOT_APPLICABLE",
                    terms_note=note,
                )
            )
    db.flush()


def seed_demo_products(db):
    if db.scalar(select(CanonicalProduct.id).where(CanonicalProduct.is_demo.is_(True))):
        return
    official_source = db.scalar(select(DataSource).where(DataSource.code == "DAV_DEMO"))
    if not official_source:
        official_source = DataSource(
            code="DAV_DEMO",
            name="Cục Quản Lý Dược (Demo)",
            source_type=SourceType.REGULATORY,
            authority_level=5,
            authority_weight=1.0,
            enabled=True,
        )
        manufacturer_source = DataSource(
            code="MFR_DEMO",
            name="Nhà sản xuất (Demo)",
            source_type=SourceType.MANUFACTURER,
            authority_level=4,
            authority_weight=0.9,
            enabled=True,
        )
        retailer_source = DataSource(
            code="RETAIL_DEMO",
            name="Nhà thuốc (Demo)",
            source_type=SourceType.RETAILER,
            authority_level=2,
            authority_weight=0.65,
            enabled=True,
        )
        db.add_all([official_source, manufacturer_source, retailer_source])
        db.flush()
    else:
        manufacturer_source = db.scalar(select(DataSource).where(DataSource.code == "MFR_DEMO"))
        retailer_source = db.scalar(select(DataSource).where(DataSource.code == "RETAIL_DEMO"))
    ingredient = Ingredient(normalized_name="Hoạt chất minh họa A", alternative_names=["Demo active A"])
    db.add(ingredient)
    db.flush()

    for number in range(1, 21):
        registration = None if 6 <= number <= 8 else f"DEMO-VD-{number:04d}-26"
        manufacturer = "Công ty Dược Demo Việt Nam"
        regulatory_status = RegulatoryStatus.RECALLED if number in {14, 15} else RegulatoryStatus.ACTIVE
        complete = number not in {18, 19, 20}
        product = CanonicalProduct(
            canonical_name=f"DemoMed {number:03d}" if number != 17 else "DemoMed 016 Plus",
            registration_number=registration,
            dosage_form="Viên nén" if complete else None,
            route="Đường uống" if complete else None,
            manufacturer=("Nhà sản xuất quan sát khác" if number in {12, 13} else manufacturer),
            manufacturing_country="Việt Nam" if complete else None,
            package_description="Hộp 10 vỉ x 10 viên" if complete else None,
            regulatory_status=regulatory_status,
            rx_otc_status=RxOtcStatus.OTC if number <= 17 else RxOtcStatus.UNKNOWN,
            publish_status=PublishStatus.DRAFT,
            is_demo=True,
        )
        db.add(product)
        db.flush()
        strength = 50.0 if number in {9, 10, 11} else 500.0
        db.add(
            ProductIngredient(
                product_id=product.id,
                ingredient_id=ingredient.id,
                strength_value=strength,
                strength_unit="mg",
                original_strength_text=f"{strength:g} mg",
            )
        )

        if registration:
            db.add(
                RegulatoryRecord(
                    registration_number=registration,
                    official_name=product.canonical_name,
                    manufacturer=manufacturer,
                    ingredients_json=[{"name": ingredient.normalized_name, "strength_value": 500.0, "strength_unit": "mg"}],
                    dosage_form="Viên nén",
                    package_description="Hộp 10 vỉ x 10 viên",
                    rx_otc_status=RxOtcStatus.OTC if number <= 17 else RxOtcStatus.UNKNOWN,
                    regulatory_status=regulatory_status,
                    source_url=f"demo://regulatory/{registration}",
                )
            )

        for source, field_name, value, confidence in [
            (official_source, "registration_number", registration, 1.0),
            (official_source, "ingredient_strength", "Hoạt chất minh họa A 500 mg", 1.0),
            (manufacturer_source, "manufacturer", manufacturer, 0.9),
            (retailer_source, "package_description", "Hộp 10 vỉ x 10 viên", 0.65),
        ]:
            if value:
                db.add(
                    ProductSourceField(
                        product_id=product.id,
                        source_id=source.id,
                        field_name=field_name,
                        original_value=value,
                        normalized_value=value,
                        field_confidence=confidence,
                        is_selected_value=True,
                    )
                )

        if number in {9, 10, 11}:
            db.add(
                DataConflict(
                    product_id=product.id,
                    conflict_type="STRENGTH_CONFLICT",
                    severity=ConflictSeverity.CRITICAL,
                    field_name="ingredient_strength",
                    source_a_id=official_source.id,
                    value_a="500 mg",
                    source_b_id=retailer_source.id,
                    value_b="50 mg",
                    description="Hàm lượng quan sát không khớp nguồn chính thức.",
                    detected_by="DEMO_RULE_ENGINE",
                )
            )
        if number in {12, 13}:
            db.add(
                DataConflict(
                    product_id=product.id,
                    conflict_type="MANUFACTURER_CONFLICT",
                    severity=ConflictSeverity.MEDIUM,
                    field_name="manufacturer",
                    source_a_id=official_source.id,
                    value_a=manufacturer,
                    source_b_id=retailer_source.id,
                    value_b=product.manufacturer,
                    description="Tên nhà sản xuất giữa hai nguồn không đồng nhất.",
                    detected_by="DEMO_RULE_ENGINE",
                )
            )
        db.flush()

    db.flush()
    products = db.scalars(select(CanonicalProduct).where(CanonicalProduct.is_demo.is_(True))).all()
    for product in products:
        calculate_product_score(db, product, "Khởi tạo bộ dữ liệu demo")


def main():
    import os
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        seed_users(db)
        seed_sources(db)
        seed_administrative_units(db)
        db.commit()
        if os.environ.get("SEED_DEMO") == "1":
            seed_demo_products(db)
            db.commit()
            print("Đã tạo dữ liệu demo PharmaTrust.")
        else:
            print("Đã khởi tạo hệ thống PharmaTrust với các nguồn dữ liệu thật.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
