"""Script phân loại rõ ràng 4 tầng dữ liệu thương mại trên toàn bộ CanonicalProduct:
1. INTERNAL_TEST: 20 sản phẩm DemoMed (is_demo=True, không phục vụ khách hàng)
2. REFERENCE_ONLY: 150 sản phẩm danh mục tra cứu thông tin y tế (Search & Lookup only, không mở bán)
3. VERIFIED_PRODUCT_DATA: 6 sản phẩm cơ sở đã chuẩn hóa số đăng ký (chờ biên bản nhập kho thực tế)
4. SALE_ELIGIBLE: 0 (Chưa có sản phẩm nào có phiếu nhập kho GSP thực tế)
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models import CanonicalProduct
from app.models.enums import PublishStatus


def classify_product_data_tiers():
    db = SessionLocal()
    try:
        prods = db.query(CanonicalProduct).all()
        internal_count = 0
        ref_count = 0
        verified_count = 0

        for p in prods:
            if "DemoMed" in p.canonical_name or p.is_demo:
                p.publish_mode = "INTERNAL_TEST"
                p.is_demo = True
                internal_count += 1
            elif p.id in [501, 88520, 99770, 106139, 111691, 124710]:
                p.publish_mode = "VERIFIED_PRODUCT_DATA"
                verified_count += 1
            else:
                p.publish_mode = "REFERENCE_ONLY"
                ref_count += 1

        db.commit()
        print(f"Phân loại thành công 176 sản phẩm:")
        print(f"  - INTERNAL_TEST: {internal_count}")
        print(f"  - REFERENCE_ONLY: {ref_count}")
        print(f"  - VERIFIED_PRODUCT_DATA: {verified_count}")
        print(f"  - SALE_ELIGIBLE: 0 (Đang chờ biên bản nhập kho thương mại thực tế)")
    except Exception as e:
        db.rollback()
        print(f"Lỗi: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    classify_product_data_tiers()
