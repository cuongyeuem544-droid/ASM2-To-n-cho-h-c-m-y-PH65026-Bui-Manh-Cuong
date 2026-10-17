import sys
from pathlib import Path

# Thêm đường dẫn apps/api vào sys.path để chạy độc lập
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.db.session import engine, SessionLocal
from app.db.base import Base
import app.models

def migrate():
    # 1. Tạo các bảng mới nếu chưa tồn tại (crawl_locks, failed_crawl_items, admin_alerts)
    Base.metadata.create_all(bind=engine)
    
    # 2. Bổ sung các cột mới vào canonical_products nếu chưa có
    db = SessionLocal()
    try:
        cols = [c[1] for c in db.execute(text("PRAGMA table_info(canonical_products)")).fetchall()]
        new_cols = [
            ("category_slug", "VARCHAR(100)"),
            ("subcategory_slug", "VARCHAR(100)"),
            ("category_confidence", "FLOAT DEFAULT 0.0"),
            ("category_review_status", "VARCHAR(50) DEFAULT 'AUTO_RESOLVED'"),
            ("category_review_reason", "TEXT"),
            ("publish_mode", "VARCHAR(50) DEFAULT 'MANUAL_REVIEW'"),
            ("local_image_url", "VARCHAR(1000)"),
            ("local_thumbnail_url", "VARCHAR(1000)"),
            ("product_type", "VARCHAR(50) DEFAULT 'OTHER'"),
            ("prescription_status", "VARCHAR(50) DEFAULT 'UNKNOWN'"),
            ("target_audience", "VARCHAR(100)"),
            ("atc_code", "VARCHAR(50)"),
            ("atc_name", "VARCHAR(255)"),
            ("atc_level", "INTEGER"),
            ("atc_source", "VARCHAR(100)"),
            ("atc_verified_at", "DATETIME"),
        ]
        for name, defn in new_cols:
            if name not in cols:
                print(f"Adding column {name} to canonical_products...")
                db.execute(text(f"ALTER TABLE canonical_products ADD COLUMN {name} {defn}"))
        db.commit()

        # Multi-Warehouse Columns
        wh_cols = [c[1] for c in db.execute(text("PRAGMA table_info(warehouses)")).fetchall()]
        wh_new_cols = [
            ("email", "VARCHAR(255)"),
            ("province_code", "VARCHAR(50)"),
            ("ward_code", "VARCHAR(50)"),
            ("place_id", "VARCHAR(255)"),
            ("service_radius_km", "FLOAT DEFAULT 30.0"),
            ("timezone", "VARCHAR(50) DEFAULT 'Asia/Ho_Chi_Minh'"),
            ("max_orders_per_day", "INTEGER DEFAULT 500"),
        ]
        for name, defn in wh_new_cols:
            if name not in wh_cols:
                db.execute(text(f"ALTER TABLE warehouses ADD COLUMN {name} {defn}"))

        order_cols = [c[1] for c in db.execute(text("PRAGMA table_info(orders)")).fetchall()]
        order_new_cols = [
            ("assigned_warehouse_id", "INTEGER"),
            ("assignment_method", "VARCHAR(50)"),
            ("assignment_distance_km", "FLOAT"),
            ("fulfillment_status", "VARCHAR(50) DEFAULT 'PENDING_ALLOCATION'"),
            ("estimated_ready_at", "DATETIME"),
            ("assigned_at", "DATETIME"),
            ("accepted_at", "DATETIME"),
        ]
        for name, defn in order_new_cols:
            if name not in order_cols:
                db.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {defn}"))

        transfer_cols = [c[1] for c in db.execute(text("PRAGMA table_info(stock_transfers)")).fetchall()]
        if "order_id" not in transfer_cols:
            db.execute(text("ALTER TABLE stock_transfers ADD COLUMN order_id INTEGER"))
        db.commit()

        # 3. Tạo chỉ mục tối ưu hóa tốc độ truy vấn
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_publish_status ON canonical_products(publish_status);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_updated_at ON canonical_products(updated_at);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_overall_score ON canonical_products(overall_score);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_product_type ON canonical_products(product_type);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_prescription_status ON canonical_products(prescription_status);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_order_status ON orders(order_status);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_assigned_warehouse_id ON orders(assigned_warehouse_id);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_fulfillment_status ON orders(fulfillment_status);"))
        db.commit()

        # 4. Khởi tạo và nạp dữ liệu vào bảng tìm kiếm toàn văn FTS5
        from app.services.search_service import reindex_all_products
        cnt = reindex_all_products(db)
        print(f"FTS5 full-text search index initialized: indexed {cnt} products.")

        print("Schema migration completed successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
