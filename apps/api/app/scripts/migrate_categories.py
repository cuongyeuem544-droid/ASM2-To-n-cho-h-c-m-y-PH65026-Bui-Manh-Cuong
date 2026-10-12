from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import func, select
from app.db.session import SessionLocal
from app.models.classification import Category, ProductCategory
from app.models.entities import CanonicalProduct
from app.services.category_service import seed_standard_categories
from app.services.classification_pipeline import ProductClassificationPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def migrate_catalog_data(dry_run: bool = True, export_conflicts_path: str | None = None) -> dict:
    db = SessionLocal()
    report = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "total_products": 0,
        "successfully_classified": 0,
        "pending_review": 0,
        "uncategorized_remaining": 0,
        "conflicts_detected": 0,
        "suspicious_misclassified": 0,
        "facility_records_skipped": 0,
        "conflicts_list": [],
        "suspicious_list": [],
        "review_required_list": [],
    }

    try:
        # Đảm bảo danh mục chuẩn đã được seed
        if not dry_run:
            seed_standard_categories(db)

        pipeline = ProductClassificationPipeline(db)
        products = db.scalars(select(CanonicalProduct).order_by(CanonicalProduct.id.asc())).all()
        report["total_products"] = len(products)

        logger.info(f"Bắt đầu rà soát & di trú {len(products)} sản phẩm (dry_run={dry_run})...")

        seen_reg_numbers = {}

        for prod in products:
            name = prod.canonical_name or ""
            reg = prod.registration_number

            # 1. Bỏ qua / đánh dấu hồ sơ cơ sở dược bị import nhầm
            if name.startswith("Hồ sơ cơ sở"):
                report["facility_records_skipped"] += 1
                report["review_required_list"].append({
                    "id": prod.id,
                    "name": name,
                    "reason": "Hồ sơ cơ sở dược/phòng khám bị cào nhầm vào bảng sản phẩm",
                })
                continue

            # 2. Kiểm tra trùng số đăng ký
            if reg:
                clean_reg = reg.strip().upper()
                if clean_reg in seen_reg_numbers:
                    report["conflicts_detected"] += 1
                    conflict_item = {
                        "type": "DUPLICATE_REGISTRATION_NUMBER",
                        "product_id": prod.id,
                        "conflict_with_id": seen_reg_numbers[clean_reg],
                        "registration_number": clean_reg,
                        "name": name,
                    }
                    report["conflicts_list"].append(conflict_item)
                else:
                    seen_reg_numbers[clean_reg] = prod.id

            # 3. Chạy qua pipeline phân loại
            proposal = pipeline.classify_product(prod)

            # 4. Kiểm tra dấu hiệu phân loại sai
            name_lower = name.lower()
            old_rx = getattr(prod, "rx_otc_status", None)
            old_cat = prod.category_slug or ""

            # Mỹ phẩm hoặc bông/khăn trong thuốc
            if any(k in name_lower for k in ["mặt nạ", "bông tẩy trang", "khăn ướt", "sữa rửa mặt", "kem dưỡng", "serum"]):
                if old_rx == "OTC" or "thuoc" in old_cat:
                    report["suspicious_misclassified"] += 1
                    report["suspicious_list"].append({
                        "id": prod.id,
                        "name": name,
                        "reason": "Mặt nạ/Mỹ phẩm/Đồ dùng cá nhân đang bị gán OTC hoặc nằm trong Thuốc",
                    })

            # Thực phẩm chức năng mang tên thuốc
            if "berocca" in name_lower and old_rx == "PRESCRIPTION":
                report["suspicious_misclassified"] += 1
                report["suspicious_list"].append({
                    "id": prod.id,
                    "name": name,
                    "reason": "Viên sủi vitamin Berocca bị gán Thuốc kê đơn (PRESCRIPTION)",
                })

            if proposal.conflicts:
                report["conflicts_detected"] += len(proposal.conflicts)
                for cf in proposal.conflicts:
                    report["conflicts_list"].append({
                        "product_id": prod.id,
                        "name": name,
                        "conflict": cf,
                    })

            if proposal.requires_review:
                report["pending_review"] += 1
                report["review_required_list"].append({
                    "id": prod.id,
                    "name": name,
                    "proposed_type": proposal.suggested_product_type,
                    "proposed_rx": proposal.suggested_prescription_status,
                    "reasoning": proposal.reasoning,
                    "missing": proposal.missing_fields,
                })
            else:
                report["successfully_classified"] += 1

            # 5. Áp dụng vào CSDL nếu không phải dry-run
            if not dry_run:
                pipeline.apply_proposal(
                    product=prod,
                    proposal=proposal,
                    reason="Migrate to multi-tier classification system",
                )

        if not dry_run:
            db.commit()
            logger.info("Đã commit toàn bộ thay đổi di trú vào cơ sở dữ liệu.")
        else:
            db.rollback()
            logger.info("Dry-run hoàn tất, không có thay đổi nào được ghi vào cơ sở dữ liệu.")

    finally:
        db.close()

    if export_conflicts_path:
        out_p = Path(export_conflicts_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Đã xuất báo cáo mâu thuẫn ra file: {out_p}")

    return report


def backup_database(db_file: str) -> str:
    src = Path(db_file).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Không tìm thấy database tại: {src}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = src.parent / f"{src.name}.bak_{timestamp}"
    shutil.copy2(src, dest)
    logger.info(f"Đã sao lưu an toàn CSDL sang: {dest}")
    return str(dest)


def main():
    parser = argparse.ArgumentParser(description="Script di trú danh mục sản phẩm y tế H4CARE")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm kiểm tra, không ghi vào DB")
    parser.add_argument("--apply", action="store_true", help="Áp dụng thay đổi vào cơ sở dữ liệu (tự động backup trước)")
    parser.add_argument("--export-conflicts", type=str, default=None, help="Đường dẫn file JSON để xuất báo cáo xung đột")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Vui lòng chọn chế độ chạy: --dry-run hoặc --apply")
        sys.exit(1)

    is_dry = args.dry_run or (not args.apply)

    if args.apply:
        db_path = "pharmatrust.db"
        if os.path.exists(db_path):
            backup_database(db_path)

    report = migrate_catalog_data(dry_run=is_dry, export_conflicts_path=args.export_conflicts)

    print("\n" + "=" * 60)
    print("BÁO CÁO KẾT QUẢ DI TRÚ DANH MỤC SẢN PHẨM PHÁP LÝ")
    print("=" * 60)
    print(f"Chế độ chạy:                 {'DRY-RUN (Thử nghiệm)' if is_dry else 'APPLY (Ghi thật)'}")
    print(f"Tổng số sản phẩm quét:       {report['total_products']}")
    print(f"Phân loại thành công:        {report['successfully_classified']}")
    print(f"Chuyển vào hàng chờ duyệt:   {report['pending_review']}")
    print(f"Bản ghi cơ sở/tổ chức bỏ qua:{report['facility_records_skipped']}")
    print(f"Phát hiện mâu thuẫn/xung đột:{report['conflicts_detected']}")
    print(f"Sản phẩm nghi phân loại sai: {report['suspicious_misclassified']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
