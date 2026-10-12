"""
Script Khởi tạo Dữ liệu Demo Idempotent cho Hệ thống PharmaTrust (H4CARE).
Chỉ thực thi khi DEMO_MODE=true (hoặc biến môi trường DEMO_MODE=1).
Bao gồm:
- 4 Tài khoản người dùng (Admin, Data Reviewer, Viewer, Buyer)
- 2 Kho dược phẩm (KHO-HCM-01, KHO-HN-01) kèm vị trí kệ hàng
- Nhà cung cấp dược phẩm (DHG, Sanofi, Central)
- 10+ Sản phẩm thuốc chuẩn hóa có số đăng ký, hoạt chất, chỉ định
- Các SKU đa dạng theo quy cách: Hộp, Vỉ, Tuýp, Chai, Viên
- Lô hàng theo chuẩn FEFO: Lô mới (active), Lô cận hạn (near-expiry), Lô hết hạn (expired), Lô cách ly (quarantined)
- 3 Mã giảm giá Voucher (H4CARENEW, FREESHIP, HEALTH2026)
- Đơn hàng mẫu các trạng thái (PENDING, PROCESSING, SHIPPED, COMPLETED)
"""
import os
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Thêm đường dẫn apps/api vào sys.path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AdministrativeUnit,
    CanonicalProduct,
    CustomerAddress,
    DataSource,
    Ingredient,
    InventoryBatch,
    Order,
    OrderFulfillment,
    OrderItem,
    PriceObservation,
    ProductIngredient,
    ProductSku,
    ProductSourceField,
    SeasonalCampaign,
    StockMovement,
    StockReceipt,
    StockReceiptItem,
    StockReservation,
    Supplier,
    User,
    Voucher,
    Warehouse,
    WarehouseBatchStock,
    WarehouseLocation,
)
from app.models.enums import (
    ConfidenceLabel,
    PublishStatus,
    RegulatoryStatus,
    RxOtcStatus,
    SourceType,
    UserRole,
)
from app.services.scoring import calculate_product_score
from app.services.search_service import init_fts_table, reindex_all_products


def seed_demo_data(db: Session, force: bool = False):
    if not force and not settings.demo_mode and os.getenv("DEMO_MODE", "").lower() not in ("true", "1"):
        print("[DEMO SEED] Bo qua vi DEMO_MODE=false.")
        return

    print("==================================================")
    print(" BAT DAU KHOI TAO DU LIEU DEMO IDEMPOTENT")
    print("==================================================")

    # 1. TÀI KHOẢN NGƯỜI DÙNG
    print("[1/7] Seeding Users...")
    users_data = [
        ("admin@pharmatrust.vn", "Admin@123456", "Quản Trị Viên Hệ Thống", UserRole.ADMIN, "0901234561"),
        ("reviewer@pharmatrust.vn", "Reviewer@123456", "Dược Sĩ Kiểm Duyệt Dữ Liệu", UserRole.DATA_REVIEWER, "0901234562"),
        ("viewer@pharmatrust.vn", "Viewer@123456", "Nhân Viên Giám Sát Xem Báo Cáo", UserRole.VIEWER, "0901234563"),
        ("buyer@pharmatrust.vn", "Buyer@123456", "Khách Hàng Mẫu Nguyễn Văn An", UserRole.CUSTOMER, "0901234567"),
    ]

    buyer_user = None
    for email, pwd, name, role, phone in users_data:
        u = db.scalar(select(User).where(User.email == email))
        if not u:
            u = User(
                email=email,
                password_hash=hash_password(pwd),
                full_name=name,
                role=role,
                phone=phone,
                is_active=True,
                loyalty_points=100 if role == UserRole.CUSTOMER else 0,
            )
            db.add(u)
            db.flush()
            print(f"  + User: {email} ({role.value})")
        else:
            u.role = role
            u.full_name = name
            u.phone = phone
            u.is_active = True
        if role == UserRole.CUSTOMER:
            buyer_user = u

    # Địa chỉ mặc định cho Buyer
    if buyer_user:
        addr = db.scalar(select(CustomerAddress).where(CustomerAddress.user_id == buyer_user.id))
        if not addr:
            db.add(CustomerAddress(
                user_id=buyer_user.id,
                recipient_name=buyer_user.full_name,
                phone=buyer_user.phone or "0901234567",
                address_line="123 Nguyễn Thị Minh Khai",
                province_code="79",
                province_name="Thành phố Hồ Chí Minh",
                commune_code="26734",
                commune_name="Phường Bến Nghé",
                district_code="Quận 1",
                formatted_address="123 Nguyễn Thị Minh Khai, Phường Bến Nghé, Quận 1, Thành phố Hồ Chí Minh",
                lat=10.7769,
                lng=106.7009,
                is_verified=True,
                is_default=True,
                verified_at=datetime.now(UTC),
            ))
            db.flush()

    # 2. KHO DƯỢC PHẨM & VỊ TRÍ KỆ
    print("[2/7] Seeding Warehouses & Shelf Locations...")
    wh_hcm = db.query(Warehouse).filter_by(code="KHO-HCM-01").first()
    if not wh_hcm:
        wh_hcm = Warehouse(
            code="KHO-HCM-01",
            name="Kho Trung Tâm Miền Nam (TP. Hồ Chí Minh)",
            address="Số 12 Nguyễn Thị Minh Khai, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="Thành phố Hồ Chí Minh",
            lat=10.7872,
            lng=106.7001,
            is_active=True,
            is_central=True,
            phone="028.3822.9988",
        )
        db.add(wh_hcm)
        db.flush()

    locs_hcm_def = [
        ("HCM-A1-S1-B01", "Kệ Thuốc Giảm đau Hạ sốt", "A1", "S1", "B01"),
        ("HCM-A1-S1-B02", "Kệ Thuốc Tiêu hóa Dạ dày", "A1", "S1", "B02"),
        ("HCM-B1-S2-B01", "Kệ Vitamin & TPCN", "B1", "S2", "B01"),
        ("HCM-C1-S1-B01", "Khu vực Cách ly & Hàng cận hạn", "C1", "S1", "B01"),
    ]
    for c, n, a, s, b in locs_hcm_def:
        if not db.query(WarehouseLocation).filter_by(code=c).first():
            db.add(WarehouseLocation(warehouse_id=wh_hcm.id, code=c, name=n, aisle=a, shelf=s, bin=b))

    wh_hn = db.query(Warehouse).filter_by(code="KHO-HN-01").first()
    if not wh_hn:
        wh_hn = Warehouse(
            code="KHO-HN-01",
            name="Kho Chi Nhánh Miền Bắc (Hà Nội)",
            address="Số 45 Tràng Tiền, Phường Tràng Tiền, Quận Hoàn Kiếm, TP. Hà Nội",
            ward="Phường Tràng Tiền",
            district="Quận Hoàn Kiếm",
            province="Thành phố Hà Nội",
            lat=21.0253,
            lng=105.8552,
            is_active=True,
            is_central=False,
            phone="024.3933.8866",
        )
        db.add(wh_hn)
        db.flush()

    locs_hn_def = [
        ("HN-A1-S1-B01", "Kệ Thuốc Thiết yếu HN", "A1", "S1", "B01"),
        ("HN-B1-S1-B01", "Kệ Tiêu hóa & Dạ dày HN", "B1", "S1", "B01"),
        ("HN-C1-S1-B01", "Khu vực Cách ly HN", "C1", "S1", "B01"),
    ]
    for c, n, a, s, b in locs_hn_def:
        if not db.query(WarehouseLocation).filter_by(code=c).first():
            db.add(WarehouseLocation(warehouse_id=wh_hn.id, code=c, name=n, aisle=a, shelf=s, bin=b))

    # 3. NHÀ CUNG CẤP & NGUỒN DỮ LIỆU
    print("[3/7] Seeding Suppliers & Sources...")
    suppliers = [
        ("NCC-DHG", "Công ty Cổ phần Dược Hậu Giang (DHG Pharma)", "1800156801", "0292.3891433", "dhg@dhgpharma.com.vn", "Cần Thơ", "GSP-0012/BYT-QLD"),
        ("NCC-SANOFI", "Công ty TNHH Sanofi-Aventis Việt Nam", "0302720979", "028.38298526", "contact.vn@sanofi.com", "TP. Hồ Chí Minh", "GSP-0045/BYT-QLD"),
        ("NCC-CENTRAL", "Công ty Cổ phần Dược phẩm Trung Ương 1 (Pharbaco)", "0100109988", "024.38454561", "info@pharbaco.com.vn", "Hà Nội", "GSP-0008/BYT-QLD"),
    ]
    supplier_map = {}
    for scode, sname, stax, sphone, semail, saddr, sgsp in suppliers:
        s = db.query(Supplier).filter_by(code=scode).first()
        if not s:
            s = Supplier(code=scode, name=sname, tax_code=stax, phone=sphone, email=semail, address=saddr, gsp_license_number=sgsp)
            db.add(s)
            db.flush()
        supplier_map[scode] = s

    dav_source = db.query(DataSource).filter_by(code="DAV_CONGBOTHUOC").first()
    if not dav_source:
        dav_source = DataSource(
            code="DAV_CONGBOTHUOC",
            name="Cục Quản lý Dược Việt Nam (DAV - Công Bố Thuốc)",
            source_type=SourceType.REGULATORY,
            authority_level=5,
            authority_weight=1.0,
            enabled=True,
        )
        db.add(dav_source)
        db.flush()

    # 4. MÃ GIẢM GIÁ (VOUCHERS)
    print("[4/7] Seeding Vouchers...")
    vouchers_def = [
        {
            "code": "H4CARENEW",
            "name": "Giảm 20.000đ cho đơn hàng đầu tiên",
            "discount_type": "FIXED",
            "discount_value": Decimal("20000.0"),
            "min_order_amount": Decimal("20000.0"),
            "max_discount_amount": Decimal("20000.0"),
            "usage_limit": 1000,
            "used_count": 5,
            "start_date": datetime.now(UTC) - timedelta(days=30),
            "end_date": datetime.now(UTC) + timedelta(days=365),
            "is_active": True,
        },
        {
            "code": "FREESHIP",
            "name": "Miễn phí vận chuyển toàn quốc (Giảm 25.000đ)",
            "discount_type": "SHIPPING",
            "discount_value": Decimal("25000.0"),
            "min_order_amount": Decimal("100000.0"),
            "max_discount_amount": Decimal("25000.0"),
            "usage_limit": 500,
            "used_count": 12,
            "start_date": datetime.now(UTC) - timedelta(days=30),
            "end_date": datetime.now(UTC) + timedelta(days=365),
            "is_active": True,
        },
        {
            "code": "HEALTH2026",
            "name": "Giảm 10% tối đa 50.000đ mừng năm mới 2026",
            "discount_type": "PERCENT",
            "discount_value": Decimal("10.0"),
            "min_order_amount": Decimal("150000.0"),
            "max_discount_amount": Decimal("50000.0"),
            "usage_limit": 200,
            "used_count": 8,
            "start_date": datetime.now(UTC) - timedelta(days=30),
            "end_date": datetime.now(UTC) + timedelta(days=365),
            "is_active": True,
        },
    ]

    for vdata in vouchers_def:
        v = db.scalar(select(Voucher).where(Voucher.code == vdata["code"]))
        if not v:
            db.add(Voucher(**vdata))
            print(f"  + Voucher: {vdata['code']} - {vdata['discount_type']}")
        else:
            for k, val in vdata.items():
                setattr(v, k, val)

    # 5. SẢN PHẨM THUỐC, SKUS & LÔ THEO FEFO
    print("[5/7] Seeding 10+ Canonical Products, SKUs & Inventory Batches (FEFO)...")
    today = date.today()

    demo_products = [
        {
            "name": "Thuốc giảm đau hạ sốt Panadol Extra Đỏ",
            "reg_num": "VD-22634-15",
            "manufacturer": "Công ty TNHH Sanofi-Aventis Việt Nam",
            "mfr_country": "Việt Nam",
            "dosage_form": "Viên nén bao phim",
            "package": "Hộp 15 vỉ x 12 viên",
            "desc": "Giảm đau từ nhẹ đến vừa: đau đầu, đau cơ, sốt do cảm cúm.",
            "indications": "Đau đầu, đau nửa đầu, đau cơ, đau răng, sốt cao.",
            "is_rx": False,
            "category": "giam-dau-ha-sot",
            "price": Decimal("230000.0"),
            "skus": [
                ("PANADOL-EXTRA-HOP", "Hộp", "Hộp 15 vỉ x 12 viên", Decimal("230000.0"), Decimal("190000.0"), True),
                ("PANADOL-EXTRA-VI", "Vỉ", "Vỉ 12 viên nén", Decimal("16000.0"), Decimal("13000.0"), False),
            ],
            "batches": [
                # batch_num, mfg_offset, exp_offset, initial, avail, reserved, quarantine, is_expired, is_quarantined
                ("LOT-PAN-2024A", -180, 540, 200, 150, 10, 0, False, False),  # Lô mới hạn xa
                ("LOT-PAN-2023B", -360, 60, 100, 40, 5, 0, False, False),    # Cận hạn (2 tháng)
                ("LOT-PAN-2022X", -720, -30, 50, 0, 0, 50, True, True),       # Hết hạn & cách ly
            ],
        },
        {
            "name": "Thuốc hạ sốt giảm đau sủi bọt Efferalgan 500mg",
            "reg_num": "VN-17180-13",
            "manufacturer": "UPSA SAS",
            "mfr_country": "Pháp",
            "dosage_form": "Viên sủi bọt",
            "package": "Hộp 4 vỉ x 4 viên",
            "desc": "Hạ sốt nhanh, giảm các cơn đau vừa và nhẹ.",
            "indications": "Sốt cao, đau răng, cảm cúm, đau nhức mình mẩy.",
            "is_rx": False,
            "category": "giam-dau-ha-sot",
            "price": Decimal("75000.0"),
            "skus": [
                ("EFFERALGAN-500-HOP", "Hộp", "Hộp 4 vỉ x 4 viên", Decimal("75000.0"), Decimal("60000.0"), True),
                ("EFFERALGAN-500-VI", "Vỉ", "Vỉ 4 viên sủi", Decimal("19000.0"), Decimal("15000.0"), False),
            ],
            "batches": [
                ("LOT-EFF-202401", -120, 600, 150, 120, 0, 0, False, False),
                ("LOT-EFF-202309", -300, 90, 80, 30, 0, 0, False, False),
            ],
        },
        {
            "name": "Thuốc giảm đau hạ sốt Hapacol 650",
            "reg_num": "VD-13245-10",
            "manufacturer": "Công ty Cổ phần Dược Hậu Giang (DHG Pharma)",
            "mfr_country": "Việt Nam",
            "dosage_form": "Viên nén bao phim",
            "package": "Hộp 10 vỉ x 10 viên",
            "desc": "Paracetamol 650mg thích hợp cho người lớn thể trọng trên 50kg.",
            "indications": "Đau nửa đầu, đau dây thần kinh, sốt do siêu vi.",
            "is_rx": False,
            "category": "giam-dau-ha-sot",
            "price": Decimal("65000.0"),
            "skus": [
                ("HAPACOL-650-HOP", "Hộp", "Hộp 10 vỉ x 10 viên", Decimal("65000.0"), Decimal("50000.0"), True),
                ("HAPACOL-650-VI", "Vỉ", "Vỉ 10 viên nén", Decimal("7000.0"), Decimal("5200.0"), False),
            ],
            "batches": [
                ("LOT-HAP-2401", -90, 720, 300, 250, 20, 0, False, False),
            ],
        },
        {
            "name": "Thuốc dạ dày Phosphalugel (Chữ P vàng)",
            "reg_num": "VN-17724-14",
            "manufacturer": "Pharmatis",
            "mfr_country": "Pháp",
            "dosage_form": "Hỗn dịch uống",
            "package": "Hộp 26 gói x 20g",
            "desc": "Nhôm phosphat dạng keo trung hòa acid dạ dày tức thì.",
            "indications": "Viêm dạ dày cấp và mạn, trào ngược dạ dày thực quản, ợ chua.",
            "is_rx": False,
            "category": "tieu-hoa-da-day",
            "price": Decimal("115000.0"),
            "skus": [
                ("PHOSPHALUGEL-HOP", "Hộp", "Hộp 26 gói x 20g", Decimal("115000.0"), Decimal("95000.0"), True),
                ("PHOSPHALUGEL-GOI", "Gói", "Gói hỗn dịch 20g", Decimal("5000.0"), Decimal("3800.0"), False),
            ],
            "batches": [
                ("LOT-PHOS-24A", -60, 480, 180, 140, 10, 0, False, False),
            ],
        },
        {
            "name": "Thuốc trị táo bón Duphalac 667g/l",
            "reg_num": "VN-16580-13",
            "manufacturer": "Abbott Biologicals B.V.",
            "mfr_country": "Hà Lan",
            "dosage_form": "Dung dịch uống",
            "package": "Chai 200ml",
            "desc": "Lactulose nhuận tràng thẩm thấu, an toàn cho cả phụ nữ mang thai và trẻ em.",
            "indications": "Táo bón, bệnh não gan.",
            "is_rx": False,
            "category": "tieu-hoa-da-day",
            "price": Decimal("130000.0"),
            "skus": [
                ("DUPHALAC-CHAI", "Chai", "Chai dung dịch 200ml", Decimal("130000.0"), Decimal("105000.0"), True),
            ],
            "batches": [
                ("LOT-DUPH-23C", -150, 400, 100, 80, 0, 0, False, False),
            ],
        },
        {
            "name": "Thuốc chống dị ứng Telfast HD 180mg",
            "reg_num": "VD-24538-16",
            "manufacturer": "Công ty TNHH Sanofi-Aventis Việt Nam",
            "mfr_country": "Việt Nam",
            "dosage_form": "Viên nén bao phim",
            "package": "Hộp 1 vỉ x 10 viên",
            "desc": "Fexofenadine HCl kháng histamin thế hệ 2 không gây buồn ngủ.",
            "indications": "Viêm mũi dị ứng theo mùa, mề đay mạn tính vô căn.",
            "is_rx": False,
            "category": "ho-cam-di-ung",
            "price": Decimal("95000.0"),
            "skus": [
                ("TELFAST-180-HOP", "Hộp", "Hộp 1 vỉ x 10 viên", Decimal("95000.0"), Decimal("78000.0"), True),
            ],
            "batches": [
                ("LOT-TEL-2402", -80, 500, 120, 95, 0, 0, False, False),
            ],
        },
        {
            "name": "Thuốc điều trị suy giãn tĩnh mạch Daflon 500mg",
            "reg_num": "VN-15682-12",
            "manufacturer": "Les Laboratoires Servier Industrie",
            "mfr_country": "Pháp",
            "dosage_form": "Viên nén bao phim",
            "package": "Hộp 4 vỉ x 15 viên",
            "desc": "Phân đoạn flavonoid vi hạt tinh chế giúp tăng trương lực tĩnh mạch và bảo vệ vi mạch.",
            "indications": "Suy tuần hoàn tĩnh mạch mãn tính ở chân, trĩ cấp và mạn tính.",
            "is_rx": False,
            "category": "tim-mach-huyet-ap",
            "price": Decimal("245000.0"),
            "skus": [
                ("DAFLON-500-HOP", "Hộp", "Hộp 4 vỉ x 15 viên", Decimal("245000.0"), Decimal("210000.0"), True),
                ("DAFLON-500-VI", "Vỉ", "Vỉ 15 viên nén", Decimal("63000.0"), Decimal("53000.0"), False),
            ],
            "batches": [
                ("LOT-DAF-23M", -200, 360, 90, 60, 5, 0, False, False),
            ],
        },
        {
            "name": "Viên sủi bổ sung vitamin Berocca Performance Hương cam",
            "reg_num": "VN-18234-14",
            "manufacturer": "Bayer Consumer Care AG",
            "mfr_country": "Indonesia",
            "dosage_form": "Viên sủi bọt",
            "package": "Tuýp 10 viên sủi",
            "desc": "Tổ hợp Vitamin nhóm B, Vitamin C, Canxi, Magie và Kẽm giúp tăng cường thể lực và tập trung trí não.",
            "indications": "Thiếu hụt vitamin, mệt mỏi thể chất, căng thẳng tinh thần.",
            "is_rx": False,
            "category": "vitamin-khoang-chat",
            "price": Decimal("85000.0"),
            "skus": [
                ("BEROCCA-TUYP", "Tuýp", "Tuýp 10 viên sủi", Decimal("85000.0"), Decimal("68000.0"), True),
            ],
            "batches": [
                ("LOT-BER-24K", -40, 650, 160, 130, 0, 0, False, False),
            ],
        },
        {
            "name": "Gel xoa bóp giảm đau Salonpas Gel 30g",
            "reg_num": "VD-21445-14",
            "manufacturer": "Công ty TNHH Dược phẩm Hisamitsu Việt Nam",
            "mfr_country": "Việt Nam",
            "dosage_form": "Gel bôi da",
            "package": "Tuýp 30g",
            "desc": "Methyl Salicylate và l-Menthol thẩm thấu sâu, xua tan cơn đau cơ tức thì.",
            "indications": "Mỏi cơ, đau cơ, đau vai, bong gân, bầm tím.",
            "is_rx": False,
            "category": "giam-dau-ha-sot",
            "price": Decimal("38000.0"),
            "skus": [
                ("SALONPAS-GEL-TUYP", "Tuýp", "Tuýp gel 30g", Decimal("38000.0"), Decimal("29000.0"), True),
            ],
            "batches": [
                ("LOT-SAL-24T", -90, 700, 200, 180, 0, 0, False, False),
            ],
        },
        {
            "name": "Dầu mù u trị bỏng mờ sẹo Calophyllum Inophyllum 30ml",
            "reg_num": "VD-18921-13",
            "manufacturer": "Công ty Cổ phần Dược phẩm OPC",
            "mfr_country": "Việt Nam",
            "dosage_form": "Dầu thuốc bôi ngoài",
            "package": "Chai 30ml",
            "desc": "Tinh dầu mù u nguyên chất giúp mau lành vết bỏng, kháng khuẩn da.",
            "indications": "Bỏng bô xe, phỏng nước sôi, trầy xước, côn trùng cắn.",
            "is_rx": False,
            "category": "cham-soc-da",
            "price": Decimal("25000.0"),
            "skus": [
                ("DAU-MUU-CHAI", "Chai", "Chai dầu 30ml", Decimal("25000.0"), Decimal("18000.0"), True),
            ],
            "batches": [
                ("LOT-MUU-24D", -30, 800, 250, 220, 0, 0, False, False),
            ],
        },
        {
            "name": "Thuốc kháng sinh Amoxicillin 500mg (Thuốc kê đơn Rx)",
            "reg_num": "VD-20150-13",
            "manufacturer": "Công ty Cổ phần Dược Hậu Giang (DHG Pharma)",
            "mfr_country": "Việt Nam",
            "dosage_form": "Viên nang cứng",
            "package": "Hộp 10 vỉ x 10 viên",
            "desc": "Kháng sinh nhóm Penicillin phổ rộng. Chỉ bán khi có đơn thuốc hợp lệ của Bác sĩ.",
            "indications": "Nhiễm khuẩn đường hô hấp, tai mũi họng, tiết niệu.",
            "is_rx": True,
            "category": "thuoc-ke-don",
            "price": Decimal("85000.0"),
            "skus": [
                ("AMOXICILLIN-500-HOP", "Hộp", "Hộp 10 vỉ x 10 viên", Decimal("85000.0"), Decimal("65000.0"), True),
            ],
            "batches": [
                ("LOT-AMOX-24B", -100, 500, 100, 90, 0, 0, False, False),
            ],
        },
    ]

    for pdata in demo_products:
        prod = db.scalar(select(CanonicalProduct).where(CanonicalProduct.registration_number == pdata["reg_num"]))
        rx_status = RxOtcStatus.PRESCRIPTION if pdata["is_rx"] else RxOtcStatus.OTC
        if not prod:
            prod = CanonicalProduct(
                canonical_name=pdata["name"],
                registration_number=pdata["reg_num"],
                dosage_form=pdata["dosage_form"],
                route="Đường uống" if "uống" in pdata["dosage_form"].lower() or "viên" in pdata["dosage_form"].lower() else "Bôi ngoài da",
                manufacturer=pdata["manufacturer"],
                manufacturing_country=pdata["mfr_country"],
                package_description=pdata["package"],
                description=pdata["desc"],
                indications=pdata["indications"],
                category_slug=pdata["category"],
                regulatory_status=RegulatoryStatus.ACTIVE,
                rx_otc_status=rx_status,
                publish_status=PublishStatus.PUBLISHED,
                publish_mode="PRESCRIPTION_COUNSEL_ONLY" if pdata["is_rx"] else "SALE_ELIGIBLE",
                is_demo=True,
            )
            db.add(prod)
            db.flush()
            print(f"  + Product: {prod.registration_number} - {rx_status.value}")
        else:
            prod.canonical_name = pdata["name"]
            prod.dosage_form = pdata["dosage_form"]
            prod.package_description = pdata["package"]
            prod.publish_status = PublishStatus.PUBLISHED
            prod.publish_mode = "PRESCRIPTION_COUNSEL_ONLY" if pdata["is_rx"] else "SALE_ELIGIBLE"

        # Price observation
        po = db.query(PriceObservation).filter_by(product_id=prod.id).first()
        if not po:
            db.add(PriceObservation(
                product_id=prod.id,
                source_id=dav_source.id,
                observed_price=pdata["price"],
                currency="VND",
                availability_text="Có sẵn",
                source_url=f"https://dichvucong.dav.gov.vn/congbothuoc/{pdata['reg_num']}",
            ))
            db.flush()

        # SKUs
        for scode, suom, sdesc, sbase, scost, sdef in pdata["skus"]:
            sku = db.query(ProductSku).filter_by(sku_code=scode).first()
            if not sku:
                sku = ProductSku(
                    canonical_product_id=prod.id,
                    sku_code=scode,
                    barcode=f"893{hash(scode) % 10000000000:010d}",
                    uom=suom,
                    conversion_rate=1 if sdef else 10,
                    base_price=sbase,
                    is_default=sdef,
                    is_active=True,
                )
                db.add(sku)
                db.flush()

            # Batches for this SKU
            for bnum, moff, eoff, init_q, avail_q, res_q, quar_q, is_exp, is_quar in pdata["batches"]:
                mfg = today + timedelta(days=moff)
                exp = today + timedelta(days=eoff)
                batch = db.query(InventoryBatch).filter_by(sku_id=sku.id, batch_number=bnum).first()
                if not batch:
                    b_status = "EXPIRED" if is_exp else ("QUARANTINED" if is_quar else "ACTIVE")
                    batch = InventoryBatch(
                        sku_id=sku.id,
                        batch_number=bnum,
                        manufacture_date=mfg,
                        expiry_date=exp,
                        initial_quantity=init_q,
                        status=b_status,
                    )
                    db.add(batch)
                    db.flush()

                # Warehouse Stock allocation
                wh_stock = db.query(WarehouseBatchStock).filter_by(warehouse_id=wh_hcm.id, batch_id=batch.id).first()
                if not wh_stock:
                    wh_stock = WarehouseBatchStock(
                        warehouse_id=wh_hcm.id,
                        batch_id=batch.id,
                        quantity_on_hand=avail_q + res_q + quar_q,
                        quantity_available=avail_q,
                        quantity_reserved=res_q,
                    )
                    db.add(wh_stock)
                    db.flush()

        # Tính điểm minh bạch tự động
        calculate_product_score(db, prod, "Khởi tạo dữ liệu demo hệ thống")

    # 6. ĐƠN HÀNG THỬ NGHIỆM (SAMPLE ORDERS)
    print("[6/7] Seeding Sample Orders...")
    panadol_sku = db.query(ProductSku).filter_by(sku_code="PANADOL-EXTRA-HOP").first()
    eff_sku = db.query(ProductSku).filter_by(sku_code="EFFERALGAN-500-HOP").first()

    sample_orders_def = [
        {
            "code": "PT-DEMO-0001",
            "status": "COMPLETED",
            "payment_status": "PAID",
            "payment_method": "BANK_TRANSFER",
            "amount": Decimal("230000.0"),
            "shipping_fee": Decimal("0.0"),
            "discount": Decimal("20000.0"),
            "voucher": "H4CARENEW",
            "created_offset": -5,
        },
        {
            "code": "PT-DEMO-0002",
            "status": "PENDING",
            "payment_status": "PENDING",
            "payment_method": "COD",
            "amount": Decimal("100000.0"),
            "shipping_fee": Decimal("25000.0"),
            "discount": Decimal("0.0"),
            "voucher": None,
            "created_offset": 0,
        },
    ]

    for so in sample_orders_def:
        o = db.scalar(select(Order).where(Order.order_code == so["code"]))
        if not o and buyer_user and panadol_sku:
            created_dt = datetime.now(UTC) + timedelta(days=so["created_offset"])
            o = Order(
                order_code=so["code"],
                user_id=buyer_user.id,
                customer_name=buyer_user.full_name,
                customer_phone=buyer_user.phone or "0901234567",
                customer_email=buyer_user.email,
                shipping_address="123 Nguyễn Thị Minh Khai, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
                shipping_city="TP. Hồ Chí Minh",
                payment_method=so["payment_method"],
                payment_status=so["payment_status"],
                order_status=so["status"],
                total_amount=so["amount"],
                shipping_fee=so["shipping_fee"],
                discount_amount=so["discount"],
                voucher_code=so["voucher"],
                created_at=created_dt,
            )
            db.add(o)
            db.flush()

            # Add OrderItem
            db.add(OrderItem(
                order_id=o.id,
                product_id=panadol_sku.canonical_product_id,
                product_name="Thuốc giảm đau hạ sốt Panadol Extra Đỏ",
                product_sku=panadol_sku.sku_code,
                price=panadol_sku.base_price,
                quantity=1,
                subtotal=panadol_sku.base_price,
            ))
            db.flush()
            print(f"  + Order: {so['code']} ({so['status']})")

    # 7. CHỈ MỤC TÌM KIẾM FTS5
    print("[7/7] Rebuilding Search Index (FTS5)...")
    try:
        init_fts_table(db)
        reindex_all_products(db)
    except Exception as e:
        print(f"  - FTS warning: {e}")

    # 8. SEED NATIONWIDE WAREHOUSES & DISTRIBUTED STOCK (Multi-warehouse RBAC)
    print("[8/8] Seeding 20+ Nationwide Warehouses & Distributed Inventory...")
    try:
        from app.services.warehouse_seeder import seed_warehouses_and_managers, seed_distributed_inventory
        seed_warehouses_and_managers(db)
        seed_distributed_inventory(db)
    except Exception as e:
        print(f"  - Warehouse seeder warning: {e}")

    db.commit()
    print("==================================================")
    print(" HOAN TAT KHOI TAO DU LIEU DEMO THANH CONG!")
    print("==================================================")


def main():
    db = SessionLocal()
    try:
        seed_demo_data(db, force=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
