"""Warehouse and Inventory Batch Seeder for Multi-Warehouse Architecture.
Seeds >= 20 realistic pharmacy warehouses nationwide, warehouse manager accounts,
and distributed inventory batches with FEFO compliance.
"""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import logging
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    BatchStatus,
    CanonicalProduct,
    InventoryBatch,
    ProductSku,
    Supplier,
    User,
    Warehouse,
    WarehouseBatchStock,
    WarehouseLocation,
)
from app.models.enums import UserRole
from app.models.inventory import UserWarehouseMembership

logger = logging.getLogger("pharmatrust.seeder")


SEED_WAREHOUSES = [
    {
        "code": "KHO-HCM-01",
        "name": "Kho Tổng Miền Nam (Quận 1, TP. HCM)",
        "address": "Số 12 Nguyễn Thị Minh Khai, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
        "ward": "Phường Bến Nghé",
        "district": "Quận 1",
        "province": "Thành phố Hồ Chí Minh",
        "province_code": "79",
        "lat": 10.7872,
        "lng": 106.7001,
        "phone": "02838221234",
        "email": "kho.hcm01@pharmatrust.vn",
        "is_central": True,
        "service_radius_km": 35.0,
    },
    {
        "code": "KHO-HCM-02",
        "name": "Chi Nhánh Dược H4Care Quận 7 (TP. HCM)",
        "address": "Số 102 Nguyễn Đức Cảnh, Phường Tân Phong, Quận 7, TP. Hồ Chí Minh",
        "ward": "Phường Tân Phong",
        "district": "Quận 7",
        "province": "Thành phố Hồ Chí Minh",
        "province_code": "79",
        "lat": 10.7303,
        "lng": 106.7082,
        "phone": "02837715678",
        "email": "kho.hcm02@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 25.0,
    },
    {
        "code": "KHO-HCM-03",
        "name": "Chi Nhánh Dược H4Care Gò Vấp (TP. HCM)",
        "address": "Số 458 Quang Trung, Phường 10, Quận Gò Vấp, TP. Hồ Chí Minh",
        "ward": "Phường 10",
        "district": "Quận Gò Vấp",
        "province": "Thành phố Hồ Chí Minh",
        "province_code": "79",
        "lat": 10.8388,
        "lng": 106.6653,
        "phone": "02838942345",
        "email": "kho.hcm03@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 25.0,
    },
    {
        "code": "KHO-HCM-04",
        "name": "Chi Nhánh Dược H4Care TP. Thủ Đức (TP. HCM)",
        "address": "Số 216 Võ Văn Ngân, Phường Bình Thọ, TP. Thủ Đức, TP. Hồ Chí Minh",
        "ward": "Phường Bình Thọ",
        "district": "Thành phố Thủ Đức",
        "province": "Thành phố Hồ Chí Minh",
        "province_code": "79",
        "lat": 10.8504,
        "lng": 106.7719,
        "phone": "02837229876",
        "email": "kho.hcm04@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-HCM-05",
        "name": "Chi Nhánh Dược H4Care Bình Tân (TP. HCM)",
        "address": "Số 88 Tên Lửa, Phường An Lạc A, Quận Bình Tân, TP. Hồ Chí Minh",
        "ward": "Phường An Lạc A",
        "district": "Quận Bình Tân",
        "province": "Thành phố Hồ Chí Minh",
        "province_code": "79",
        "lat": 10.7511,
        "lng": 106.6083,
        "phone": "02838765432",
        "email": "kho.hcm05@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 25.0,
    },
    {
        "code": "KHO-HN-01",
        "name": "Kho Tổng Miền Bắc (Hoàn Kiếm, Hà Nội)",
        "address": "Số 45 Tràng Tiền, Phường Tràng Tiền, Quận Hoàn Kiếm, TP. Hà Nội",
        "ward": "Phường Tràng Tiền",
        "district": "Quận Hoàn Kiếm",
        "province": "Thành phố Hà Nội",
        "province_code": "01",
        "lat": 21.0253,
        "lng": 105.8552,
        "phone": "02438251234",
        "email": "kho.hn01@pharmatrust.vn",
        "is_central": True,
        "service_radius_km": 35.0,
    },
    {
        "code": "KHO-HN-02",
        "name": "Chi Nhánh Dược H4Care Cầu Giấy (Hà Nội)",
        "address": "Số 168 Cầu Giấy, Phường Quan Hoa, Quận Cầu Giấy, TP. Hà Nội",
        "ward": "Phường Quan Hoa",
        "district": "Quận Cầu Giấy",
        "province": "Thành phố Hà Nội",
        "province_code": "01",
        "lat": 21.0362,
        "lng": 105.7906,
        "phone": "02437678901",
        "email": "kho.hn02@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 25.0,
    },
    {
        "code": "KHO-HN-03",
        "name": "Chi Nhánh Dược H4Care Đống Đa (Hà Nội)",
        "address": "Số 250 Xã Đàn, Phường Nam Đồng, Quận Đống Đa, TP. Hà Nội",
        "ward": "Phường Nam Đồng",
        "district": "Quận Đống Đa",
        "province": "Thành phố Hà Nội",
        "province_code": "01",
        "lat": 21.0135,
        "lng": 105.8340,
        "phone": "02435734567",
        "email": "kho.hn03@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 25.0,
    },
    {
        "code": "KHO-HN-04",
        "name": "Chi Nhánh Dược H4Care Hà Đông (Hà Nội)",
        "address": "Số 120 Quang Trung, Phường Quang Trung, Quận Hà Đông, TP. Hà Nội",
        "ward": "Phường Quang Trung",
        "district": "Quận Hà Đông",
        "province": "Thành phố Hà Nội",
        "province_code": "01",
        "lat": 20.9716,
        "lng": 105.7766,
        "phone": "02433829012",
        "email": "kho.hn04@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 25.0,
    },
    {
        "code": "KHO-HN-05",
        "name": "Chi Nhánh Dược H4Care Nhổn (Bắc Từ Liêm, Hà Nội)",
        "address": "Số 32 Cầu Diễn, Phường Minh Khai, Quận Bắc Từ Liêm, TP. Hà Nội",
        "ward": "Phường Minh Khai",
        "district": "Quận Bắc Từ Liêm",
        "province": "Thành phố Hà Nội",
        "province_code": "01",
        "lat": 21.0558,
        "lng": 105.7412,
        "phone": "02437651234",
        "email": "kho.hn05@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-DN-01",
        "name": "Kho Tổng Miền Trung (Hải Châu, Đà Nẵng)",
        "address": "Số 78 Lê Duẩn, Phường Thạch Thang, Quận Hải Châu, TP. Đà Nẵng",
        "ward": "Phường Thạch Thang",
        "district": "Quận Hải Châu",
        "province": "Thành phố Đà Nẵng",
        "province_code": "48",
        "lat": 16.0678,
        "lng": 108.2208,
        "phone": "02363821234",
        "email": "kho.dn01@pharmatrust.vn",
        "is_central": True,
        "service_radius_km": 40.0,
    },
    {
        "code": "KHO-DN-02",
        "name": "Chi Nhánh Dược H4Care Ngũ Hành Sơn (Đà Nẵng)",
        "address": "Số 150 Võ Nguyên Giáp, Phường Mỹ An, Quận Ngũ Hành Sơn, TP. Đà Nẵng",
        "ward": "Phường Mỹ An",
        "district": "Quận Ngũ Hành Sơn",
        "province": "Thành phố Đà Nẵng",
        "province_code": "48",
        "lat": 16.0422,
        "lng": 108.2464,
        "phone": "02363956789",
        "email": "kho.dn02@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 25.0,
    },
    {
        "code": "KHO-HP-01",
        "name": "Chi Nhánh Dược H4Care Lạch Tray (Hải Phòng)",
        "address": "Số 85 Lạch Tray, Phường Lạch Tray, Quận Ngô Quyền, TP. Hải Phòng",
        "ward": "Phường Lạch Tray",
        "district": "Quận Ngô Quyền",
        "province": "Thành phố Hải Phòng",
        "province_code": "31",
        "lat": 20.8465,
        "lng": 106.6881,
        "phone": "02253845678",
        "email": "kho.hp01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-CT-01",
        "name": "Kho Tổng Miền Tây (Ninh Kiều, Cần Thơ)",
        "address": "Số 150 Đường 30 Tháng 4, Phường An Phú, Quận Ninh Kiều, TP. Cần Thơ",
        "ward": "Phường An Phú",
        "district": "Quận Ninh Kiều",
        "province": "Thành phố Cần Thơ",
        "province_code": "92",
        "lat": 10.0309,
        "lng": 105.7745,
        "phone": "02923812345",
        "email": "kho.ct01@pharmatrust.vn",
        "is_central": True,
        "service_radius_km": 40.0,
    },
    {
        "code": "KHO-BD-01",
        "name": "Chi Nhánh Dược H4Care Thủ Dầu Một (Bình Dương)",
        "address": "Số 320 Đại Lộ Bình Dương, Phường Phú Hòa, TP. Thủ Dầu Một, Bình Dương",
        "ward": "Phường Phú Hòa",
        "district": "Thành phố Thủ Dầu Một",
        "province": "Tỉnh Bình Dương",
        "province_code": "74",
        "lat": 10.9805,
        "lng": 106.6519,
        "phone": "02743834567",
        "email": "kho.bd01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-DNA-01",
        "name": "Chi Nhánh Dược H4Care Biên Hòa (Đồng Nai)",
        "address": "Số 95 Đồng Khởi, Phường Tân Hiệp, TP. Biên Hòa, Đồng Nai",
        "ward": "Phường Tân Hiệp",
        "district": "Thành phố Biên Hòa",
        "province": "Tỉnh Đồng Nai",
        "province_code": "75",
        "lat": 10.9574,
        "lng": 106.8427,
        "phone": "02513888999",
        "email": "kho.dna01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-KH-01",
        "name": "Chi Nhánh Dược H4Care Nha Trang (Khánh Hòa)",
        "address": "Số 42 Trần Phú, Phường Lộc Thọ, TP. Nha Trang, Khánh Hòa",
        "ward": "Phường Lộc Thọ",
        "district": "Thành phố Nha Trang",
        "province": "Tỉnh Khánh Hòa",
        "province_code": "56",
        "lat": 12.2388,
        "lng": 109.1967,
        "phone": "02583823456",
        "email": "kho.kh01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-HUE-01",
        "name": "Chi Nhánh Dược H4Care TP. Huế (Thừa Thiên Huế)",
        "address": "Số 15 Hùng Vương, Phường Phú Nhuận, TP. Huế, Thừa Thiên Huế",
        "ward": "Phường Phú Nhuận",
        "district": "Thành phố Huế",
        "province": "Tỉnh Thừa Thiên Huế",
        "province_code": "46",
        "lat": 16.4637,
        "lng": 107.5909,
        "phone": "02343825678",
        "email": "kho.hue01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-QN-01",
        "name": "Chi Nhánh Dược H4Care Hạ Long (Quảng Ninh)",
        "address": "Số 68 Lê Thánh Tông, Phường Bạch Đằng, TP. Hạ Long, Quảng Ninh",
        "ward": "Phường Bạch Đằng",
        "district": "Thành phố Hạ Long",
        "province": "Tỉnh Quảng Ninh",
        "province_code": "22",
        "lat": 20.9505,
        "lng": 107.0734,
        "phone": "02033827890",
        "email": "kho.qn01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-NA-01",
        "name": "Chi Nhánh Dược H4Care TP. Vinh (Nghệ An)",
        "address": "Số 112 Quang Trung, Phường Quang Trung, TP. Vinh, Nghệ An",
        "ward": "Phường Quang Trung",
        "district": "Thành phố Vinh",
        "province": "Tỉnh Nghệ An",
        "province_code": "40",
        "lat": 18.6734,
        "lng": 105.6813,
        "phone": "02383845678",
        "email": "kho.na01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-VT-01",
        "name": "Chi Nhánh Dược H4Care TP. Vũng Tàu (Bà Rịa - Vũng Tàu)",
        "address": "Số 56 Ba Cu, Phường 1, TP. Vũng Tàu, Bà Rịa - Vũng Tàu",
        "ward": "Phường 1",
        "district": "Thành phố Vũng Tàu",
        "province": "Tỉnh Bà Rịa - Vũng Tàu",
        "province_code": "77",
        "lat": 10.3541,
        "lng": 107.0843,
        "phone": "02543856789",
        "email": "kho.vt01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
    {
        "code": "KHO-LD-01",
        "name": "Chi Nhánh Dược H4Care TP. Đà Lạt (Lâm Đồng)",
        "address": "Số 75 Phan Đình Phùng, Phường 1, TP. Đà Lạt, Lâm Đồng",
        "ward": "Phường 1",
        "district": "Thành phố Đà Lạt",
        "province": "Tỉnh Lâm Đồng",
        "province_code": "68",
        "lat": 11.9404,
        "lng": 108.4377,
        "phone": "02633821234",
        "email": "kho.ld01@pharmatrust.vn",
        "is_central": False,
        "service_radius_km": 30.0,
    },
]


def seed_warehouses_and_managers(db: Session) -> dict[str, int]:
    """
    Tạo hoặc cập nhật danh sách kho hàng toàn quốc (>= 22 kho).
    Gán tài khoản Quản Lý Kho & Nhân Viên Kho mẫu cho các trung tâm.
    """
    logger.info("Bắt đầu khởi tạo dữ liệu kho hàng toàn quốc...")
    code_to_id: dict[str, int] = {}

    for w_data in SEED_WAREHOUSES:
        code = w_data["code"]
        existing = db.scalar(select(Warehouse).where(Warehouse.code == code))
        if not existing:
            # Check if old code like H4CARE exists for Nhổn
            if code == "KHO-HN-05":
                existing = db.scalar(select(Warehouse).where(Warehouse.code == "H4CARE"))

        if existing:
            for k, v in w_data.items():
                setattr(existing, k, v)
            existing.is_active = True
            db.flush()
            code_to_id[code] = existing.id
        else:
            new_wh = Warehouse(**w_data)
            db.add(new_wh)
            db.flush()
            code_to_id[code] = new_wh.id

            # Create default location A1-01
            loc = WarehouseLocation(
                warehouse_id=new_wh.id,
                code="A1-01",
                name="Khu Vực Xuất Nhập & Bảo Quản Chính",
                aisle="A",
                shelf="01",
                bin="01",
                is_active=True,
            )
            db.add(loc)
            db.flush()

    db.commit()

    # Seed Demo Warehouse Managers & Staff (Cả 2 định dạng email '.' và '_')
    demo_accounts = [
        # TP. Hồ Chí Minh
        {
            "email": "manager.hcm@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Hồ Chí Minh",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-HCM-01",
            "password": "Warehouse@2026",
        },
        {
            "email": "manager_hcm@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Hồ Chí Minh",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-HCM-01",
            "password": "Warehouse@2026",
        },
        {
            "email": "staff.hcm@pharmatrust.vn",
            "full_name": "Nhân Viên Soạn Hàng HCM",
            "role": UserRole.WAREHOUSE_STAFF,
            "wh_code": "KHO-HCM-01",
            "password": "Staff@2026",
        },
        {
            "email": "staff_hcm@pharmatrust.vn",
            "full_name": "Nhân Viên Soạn Hàng HCM",
            "role": UserRole.WAREHOUSE_STAFF,
            "wh_code": "KHO-HCM-01",
            "password": "Staff@2026",
        },
        # Hà Nội
        {
            "email": "manager.hn@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Hà Nội",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-HN-01",
            "password": "Warehouse@2026",
        },
        {
            "email": "manager_hn@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Hà Nội",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-HN-01",
            "password": "Warehouse@2026",
        },
        # Đà Nẵng
        {
            "email": "manager.dn@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Đà Nẵng",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-DN-01",
            "password": "Warehouse@2026",
        },
        {
            "email": "manager_dn@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Đà Nẵng",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-DN-01",
            "password": "Warehouse@2026",
        },
        # Cần Thơ
        {
            "email": "manager.ct@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Cần Thơ",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-CT-01",
            "password": "Warehouse@2026",
        },
        {
            "email": "manager_ct@pharmatrust.vn",
            "full_name": "Quản Lý Kho TP. Cần Thơ",
            "role": UserRole.WAREHOUSE_MANAGER,
            "wh_code": "KHO-CT-01",
            "password": "Warehouse@2026",
        },
    ]

    for acc in demo_accounts:
        user = db.scalar(select(User).where(User.email == acc["email"]))
        wh_id = code_to_id.get(acc["wh_code"])
        pwd = acc.get("password", "Warehouse@2026")
        if not user:
            user = User(
                email=acc["email"],
                full_name=acc["full_name"],
                role=acc["role"],
                warehouse_id=wh_id,
                password_hash=hash_password(pwd),
                is_active=True,
            )
            db.add(user)
            db.flush()
        else:
            user.role = acc["role"]
            user.warehouse_id = wh_id
            user.password_hash = hash_password(pwd)
            user.is_active = True
            db.flush()

        if wh_id:
            membership = db.scalar(
                select(UserWarehouseMembership).where(
                    UserWarehouseMembership.user_id == user.id,
                    UserWarehouseMembership.warehouse_id == wh_id,
                )
            )
            if not membership:
                m = UserWarehouseMembership(
                    user_id=user.id,
                    warehouse_id=wh_id,
                    role=acc["role"].value,
                    is_active=True,
                )
                db.add(m)
                db.flush()

    db.commit()
    return code_to_id


def seed_distributed_inventory(db: Session, max_skus: int = 250):
    """
    Phân bổ tồn kho thực tế qua các kho vệ tinh trên toàn quốc:
    - Đảm bảo mỗi kho có đủ thuốc thiết yếu phục vụ đơn tại địa phương.
    - Tạo các lô thuốc chuẩn hạn FEFO (hạn >= 180 ngày).
    - Tạo một số lô cận hạn (< 180 ngày) để kiểm thử bộ lọc an toàn FEFO.
    """
    today = date.today()
    skus = db.scalars(select(ProductSku).where(ProductSku.is_active == True).limit(max_skus)).all()
    if not skus:
        logger.warning("Không tìm thấy ProductSku nào để phân bổ tồn kho.")
        return

    all_warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active == True)).all()
    supplier = db.scalar(select(Supplier).limit(1))

    for wh in all_warehouses:
        # Check current stock count
        existing_stock_count = db.scalar(
            select(func.count(WarehouseBatchStock.id)).where(WarehouseBatchStock.warehouse_id == wh.id)
        ) or 0

        if existing_stock_count >= 50:
            # Already well stocked
            continue

        loc = db.scalar(select(WarehouseLocation).where(WarehouseLocation.warehouse_id == wh.id).limit(1))
        loc_id = loc.id if loc else None

        for sku in skus[:100]:
            # Create a valid FEFO batch (expiry in 12 - 24 months)
            batch_code = f"BAT-{wh.code[:7]}-{sku.id:04d}-V1"
            exp_date = today + timedelta(days=540)  # ~1.5 years

            batch = db.scalar(select(InventoryBatch).where(InventoryBatch.batch_number == batch_code))
            if not batch:
                batch = InventoryBatch(
                    sku_id=sku.id,
                    batch_number=batch_code,
                    manufacture_date=today - timedelta(days=90),
                    expiry_date=exp_date,
                    supplier_id=supplier.id if supplier else None,
                    initial_quantity=500,
                    status=BatchStatus.ACTIVE,
                )
                db.add(batch)
                db.flush()

            # Assign stock
            stock = db.scalar(
                select(WarehouseBatchStock).where(
                    WarehouseBatchStock.warehouse_id == wh.id,
                    WarehouseBatchStock.batch_id == batch.id,
                )
            )
            if not stock:
                stock = WarehouseBatchStock(
                    warehouse_id=wh.id,
                    batch_id=batch.id,
                    location_id=loc_id,
                    quantity_on_hand=300,
                    quantity_reserved=0,
                    quantity_available=300,
                )
                db.add(stock)

    db.commit()
    logger.info("Hoàn tất nạp tồn kho đa kho FEFO toàn quốc.")
