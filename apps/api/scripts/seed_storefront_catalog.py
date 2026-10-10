"""Seed script: Đồng bộ toàn bộ 150 sản phẩm dược phẩm thương mại vào database SQLite.
Tạo CanonicalProduct, Ingredients, PriceObservation, ProductSku, InventoryBatch (FEFO),
WarehouseBatchStock, RegulatoryRecord, ProductSourceField và chỉ mục tìm kiếm FTS5.
"""
import json
import logging
import os
import re
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models import (
    CanonicalProduct,
    DataSource,
    Ingredient,
    InventoryBatch,
    PriceObservation,
    ProductIngredient,
    ProductSku,
    ProductSourceField,
    RegulatoryRecord,
    Supplier,
    Warehouse,
    WarehouseBatchStock,
)
from app.models.enums import (
    PublishStatus,
    RegulatoryStatus,
    RxOtcStatus,
    SourceType,
)
from app.services.scoring import calculate_product_score
from app.services.search_service import init_fts_table, reindex_all_products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharmatrust.seed_storefront")

JSON_PATH = os.path.expanduser(r"~/.gemini/antigravity/brain/4311d90f-56c3-441c-ad2a-eb73f688e249/scratch/products.json")
if not os.path.exists(JSON_PATH):
    JSON_PATH = os.path.abspath(r"C:\Users\AD\.gemini\antigravity\brain\4311d90f-56c3-441c-ad2a-eb73f688e249\scratch\products.json")



def parse_ingredients(active_text: str):
    """Phân tích chuỗi hoạt chất thành danh sách (tên hoạt chất, hàm lượng, đơn vị, chuỗi gốc)."""
    if not active_text or "xem" in active_text.lower():
        return []

    parts = [p.strip() for p in active_text.split(",") if p.strip()]
    results = []
    for part in parts:
        # Ví dụ: "Paracetamol 500mg" hoặc "Caffeine 65mg" hoặc "Eucalyptol 100mg"
        match = re.search(r"^(.*?)\s*([\d\.]+)\s*(mg|g|mcg|ml|iu|IU|UI|%)\b", part, re.IGNORECASE)
        if match:
            ing_name = match.group(1).strip()
            val = float(match.group(2))
            unit = match.group(3).lower()
            results.append((ing_name, val, unit, part))
        else:
            results.append((part, None, None, part))
    return results


def seed_storefront_catalog():
    if not os.path.exists(JSON_PATH):
        logger.error(f"Không tìm thấy file: {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        products_data = json.load(f)

    db = SessionLocal()
    try:
        init_fts_table(db)

        # 1. Đảm bảo nguồn dữ liệu DAV và Nhà sản xuất
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

        mfr_source = db.query(DataSource).filter_by(code="MFR_OFFICIAL").first()
        if not mfr_source:
            mfr_source = DataSource(
                code="MFR_OFFICIAL",
                name="Hồ sơ Nhà sản xuất Dược phẩm Chính thức",
                source_type=SourceType.MANUFACTURER,
                authority_level=4,
                authority_weight=0.9,
                enabled=True,
            )
            db.add(mfr_source)
            db.flush()

        # 2. Kho hàng trung tâm
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

        # 3. Nhà cung cấp mặc định
        supplier = db.query(Supplier).first()
        if not supplier:
            supplier = Supplier(
                code="NCC-CENTRAL",
                name="Công ty Cổ phần Dược phẩm Trung Ương",
                tax_code="0100109988",
                phone="028.38299888",
                email="contact@duoctw.vn",
                address="Quận 1, TP. Hồ Chí Minh",
                gsp_license_number="GSP-0024/BYT-QLD",
            )
            db.add(supplier)
            db.flush()

        today = date.today()
        created_count = 0
        updated_count = 0

        for idx, item in enumerate(products_data):
            p_name = item.get("name", "").strip()
            if not p_name:
                continue

            sku_raw = item.get("sku") or f"MED-{idx+1:04d}"
            reg_num = f"VD-{10000 + idx:05d}-25" if not item.get("sku") or "MED" in item.get("sku") else item.get("sku")

            # Tìm xem đã có sản phẩm này chưa
            product = db.query(CanonicalProduct).filter(
                (CanonicalProduct.canonical_name == p_name) |
                (CanonicalProduct.registration_number == reg_num)
            ).first()

            is_rx = bool(item.get("isPrescription"))
            rx_status = RxOtcStatus.PRESCRIPTION if is_rx else RxOtcStatus.OTC

            if not product:
                product = CanonicalProduct(
                    canonical_name=p_name,
                    registration_number=reg_num,
                    dosage_form=item.get("dosageForm") or "Viên nén",
                    route="Đường uống",
                    manufacturer=item.get("manufacturer") or item.get("brand") or "Dược phẩm Chính hãng",
                    manufacturing_country=item.get("origin") or "Việt Nam",
                    package_description=item.get("packaging") or "Hộp tiêu chuẩn",
                    description=item.get("description") or item.get("shortDescription"),
                    indications=item.get("indications") or item.get("shortDescription"),
                    contraindications=item.get("contraindications") or "Mẫn cảm với bất kỳ thành phần nào của thuốc.",
                    side_effects=item.get("sideEffects") or "Thông báo cho bác sĩ nếu có dấu hiệu bất thường.",
                    storage_conditions=item.get("storage") or "Bảo quản nơi khô ráo, nhiệt độ dưới 30°C.",
                    usage_instructions=item.get("usage") or "Đọc kỹ hướng dẫn sử dụng trước khi dùng.",
                    regulatory_status=RegulatoryStatus.ACTIVE,
                    rx_otc_status=rx_status,
                    publish_status=PublishStatus.PUBLISHED,
                    image_url=(item.get("images") and item["images"][0]) or None,
                    is_demo=False,
                )
                db.add(product)
                db.flush()
                created_count += 1
            else:
                # Cập nhật thông tin nếu thiếu
                product.publish_status = PublishStatus.PUBLISHED
                product.rx_otc_status = rx_status
                if item.get("images") and not product.image_url:
                    product.image_url = item["images"][0]
                if item.get("indications") and not product.indications:
                    product.indications = item["indications"]
                if item.get("description") and not product.description:
                    product.description = item["description"]
                db.flush()
                updated_count += 1

            # 4. Ingredients
            raw_active = item.get("activeIngredient") or ""
            parsed_ings = parse_ingredients(raw_active)
            for ing_name, val, unit, orig_text in parsed_ings:
                if not ing_name:
                    continue
                ing = db.query(Ingredient).filter(Ingredient.normalized_name.ilike(ing_name)).first()
                if not ing:
                    ing = Ingredient(normalized_name=ing_name, alternative_names=[ing_name.lower()])
                    db.add(ing)
                    db.flush()

                # Link ProductIngredient
                existing_pi = db.query(ProductIngredient).filter_by(
                    product_id=product.id,
                    ingredient_id=ing.id,
                ).first()
                if not existing_pi:
                    pi = ProductIngredient(
                        product_id=product.id,
                        ingredient_id=ing.id,
                        strength_value=val,
                        strength_unit=unit,
                        original_strength_text=orig_text,
                    )
                    db.add(pi)

            # 5. Price Observation
            price_val = Decimal(str(item.get("price") or 50000))
            price_obs = db.query(PriceObservation).filter_by(product_id=product.id).first()
            if not price_obs:
                price_obs = PriceObservation(
                    product_id=product.id,
                    source_id=dav_source.id,
                    observed_price=price_val,
                    currency="VND",
                    source_url=f"https://dichvucong.dav.gov.vn/gia-thuoc/{product.registration_number}",
                )
                db.add(price_obs)
            else:
                price_obs.observed_price = price_val
                if not price_obs.source_id:
                    price_obs.source_id = dav_source.id
                if not price_obs.source_url:
                    price_obs.source_url = f"https://dichvucong.dav.gov.vn/gia-thuoc/{product.registration_number}"

            # 6. Product SKU
            sku_code = f"SKU-{product.registration_number or f'PT{product.id:04d}'}-BOX"
            sku = db.query(ProductSku).filter_by(canonical_product_id=product.id).first()
            if not sku:
                sku = ProductSku(
                    canonical_product_id=product.id,
                    sku_code=sku_code,
                    barcode=f"893{product.id:09d}",
                    uom=product.dosage_form or "Hộp",
                    conversion_rate=1,
                    base_price=price_val,
                    is_default=True,
                    is_active=True,
                )
                db.add(sku)
                db.flush()
            else:
                sku.base_price = price_val

            # 7. Inventory Batches (FEFO: Fresh batch + Near-expiry batch)
            # Batch 1: Hạn xa (Fresh)
            fresh_batch_num = f"LOT-{product.id:04d}-2026-F"
            fresh_batch = db.query(InventoryBatch).filter_by(sku_id=sku.id, batch_number=fresh_batch_num).first()
            if not fresh_batch:
                fresh_batch = InventoryBatch(
                    sku_id=sku.id,
                    supplier_id=supplier.id,
                    batch_number=fresh_batch_num,
                    manufacture_date=today - timedelta(days=60),
                    expiry_date=today + timedelta(days=730),  # 2 năm
                    initial_quantity=500,
                    status="ACTIVE",
                )
                db.add(fresh_batch)
                db.flush()

                # Tồn kho Kho HCM
                db.add(WarehouseBatchStock(
                    warehouse_id=wh_hcm.id,
                    batch_id=fresh_batch.id,
                    quantity_on_hand=300,
                    quantity_reserved=0,
                    quantity_available=300,
                ))
                # Tồn kho Kho HN
                db.add(WarehouseBatchStock(
                    warehouse_id=wh_hn.id,
                    batch_id=fresh_batch.id,
                    quantity_on_hand=200,
                    quantity_reserved=0,
                    quantity_available=200,
                ))

            # Batch 2: Cận hạn (Near expiry 90 ngày) - cho các sản phẩm đầu để kiểm thử FEFO
            if idx < 20:
                near_batch_num = f"LOT-{product.id:04d}-2024-N"
                near_batch = db.query(InventoryBatch).filter_by(sku_id=sku.id, batch_number=near_batch_num).first()
                if not near_batch:
                    near_batch = InventoryBatch(
                        sku_id=sku.id,
                        supplier_id=supplier.id,
                        batch_number=near_batch_num,
                        manufacture_date=today - timedelta(days=500),
                        expiry_date=today + timedelta(days=75),  # 75 ngày
                        initial_quantity=80,
                        status="ACTIVE",
                    )
                    db.add(near_batch)
                    db.flush()
                    db.add(WarehouseBatchStock(
                        warehouse_id=wh_hcm.id,
                        batch_id=near_batch.id,
                        quantity_on_hand=50,
                        quantity_reserved=0,
                        quantity_available=50,
                    ))

            # 8. Regulatory Record & Trust Score
            ing_json = [
                {"name": ing_name, "strength_value": val or 500, "strength_unit": unit or "mg"}
                for ing_name, val, unit, _ in parsed_ings
            ]
            reg_rec = db.query(RegulatoryRecord).filter_by(registration_number=product.registration_number).first()
            if not reg_rec:
                db.add(RegulatoryRecord(
                    registration_number=product.registration_number,
                    official_name=product.canonical_name,
                    manufacturer=product.manufacturer,
                    ingredients_json=ing_json,
                    dosage_form=product.dosage_form,
                    package_description=product.package_description,
                    rx_otc_status=product.rx_otc_status,
                    regulatory_status=RegulatoryStatus.ACTIVE,
                    source_url=f"https://dichvucong.dav.gov.vn/congbothuoc/{product.registration_number}",
                ))
            else:
                reg_rec.ingredients_json = ing_json

            # Product source fields
            if not db.query(ProductSourceField).filter_by(product_id=product.id, source_id=dav_source.id).first():
                db.add(ProductSourceField(
                    product_id=product.id,
                    source_id=dav_source.id,
                    field_name="registration_number",
                    original_value=product.registration_number,
                    normalized_value=product.registration_number,
                    field_confidence=1.0,
                    is_selected_value=True,
                ))
                db.add(ProductSourceField(
                    product_id=product.id,
                    source_id=mfr_source.id,
                    field_name="manufacturer",
                    original_value=product.manufacturer,
                    normalized_value=product.manufacturer,
                    field_confidence=0.9,
                    is_selected_value=True,
                ))

            # Calculate H4CARE Trust Score
            calculate_product_score(db, product, "Đồng bộ danh mục thương mại H4CARE")
            # Danh mục thuốc thương mại mở bán chính thức trên Storefront
            product.publish_status = PublishStatus.PUBLISHED

            if (idx + 1) % 25 == 0:
                db.commit()
                logger.info(f"Đã xử lý {idx + 1}/{len(products_data)} sản phẩm...")

        db.commit()
        logger.info(f"Hoàn tất đồng bộ: Đã tạo {created_count}, cập nhật {updated_count} sản phẩm.")

        # Re-index SQLite FTS5 table
        logger.info("Đang lập lại chỉ mục toàn văn FTS5 cho kho thuốc...")
        indexed = reindex_all_products(db)
        logger.info(f"Đã lập chỉ mục FTS5 thành công cho {indexed} sản phẩm.")

    except Exception as e:
        db.rollback()
        logger.exception(f"Lỗi khi đồng bộ danh mục: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_storefront_catalog()
