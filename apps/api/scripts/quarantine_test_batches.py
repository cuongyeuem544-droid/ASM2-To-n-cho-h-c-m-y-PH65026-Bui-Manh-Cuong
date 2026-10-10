"""Script cách ly toàn bộ lô hàng thử nghiệm FEFO (LOT-%-2026-F và LOT-%-2024-N).
Chuyển trạng thái sang QUARANTINED và đưa tồn khả dụng (quantity_available) về 0.
Bảo toàn bản ghi để không làm vỡ quan hệ khóa ngoại, đồng thời ngăn chặn tuyệt đối việc bán hàng giả lập.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models import InventoryBatch, WarehouseBatchStock


def quarantine_test_batches():
    db = SessionLocal()
    try:
        batches = db.query(InventoryBatch).filter(
            (InventoryBatch.batch_number.like("LOT-%-2026-F")) |
            (InventoryBatch.batch_number.like("LOT-%-2024-N"))
        ).all()

        batch_ids = [b.id for b in batches]
        print(f"Tìm thấy {len(batches)} lô hàng thử nghiệm cần cách ly...")

        # 1. Chuyển status của lô sang QUARANTINED
        for b in batches:
            b.status = "QUARANTINED"
            b.certificate_url = "QUARANTINED_FIXTURE_AUDIT_20261011"

        # 2. Đưa tồn kho khả dụng về 0
        stock_updates = db.query(WarehouseBatchStock).filter(
            WarehouseBatchStock.batch_id.in_(batch_ids)
        ).all()

        for s in stock_updates:
            s.quantity_available = 0
            s.quantity_on_hand = 0

        db.commit()
        print(f"Đã cách ly thành công {len(batches)} lô và cập nhật {len(stock_updates)} bản ghi tồn kho.")
    except Exception as e:
        db.rollback()
        print(f"Lỗi: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    quarantine_test_batches()
