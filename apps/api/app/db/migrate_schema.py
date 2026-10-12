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

        # 3. Tạo chỉ mục tối ưu hóa tốc độ truy vấn
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_publish_status ON canonical_products(publish_status);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_updated_at ON canonical_products(updated_at);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_overall_score ON canonical_products(overall_score);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_product_type ON canonical_products(product_type);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_canonical_prescription_status ON canonical_products(prescription_status);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_orders_order_status ON orders(order_status);"))
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
