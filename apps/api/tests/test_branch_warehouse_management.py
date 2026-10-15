"""Automated Test Suite for Branch Warehouse Management Module.

Covers:
1. Section 2: Warehouse Manager Dashboard with date range filtering & complete KPI cards.
2. Section 5 & 6: Warehouse Products listing & 5-tab detail payload (Admin shared medical info + Branch inventory).
3. Section 7 & 11: Multi-step CSV/Excel import pipeline (14-column template, preview, 180-day FEFO rule, duplicate prevention, atomic commit).
4. Section 12: Large inventory adjustment governance (threshold >= 50 items or >= 10M VND -> PENDING_ADMIN_APPROVAL + Admin approval).
5. Section 13: Warehouse alerts (near expiry, out of stock, large adjustment) & read management.
6. RBAC & IDOR isolation: Branch manager restricted to assigned warehouse_id.
"""
import io
import csv
import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    BatchStatus,
    Warehouse,
    ProductSku,
    CanonicalProduct,
    InventoryBatch,
    WarehouseBatchStock,
    StockAdjustment,
    WarehouseAlert,
    WarehouseImportJob,
)


def _ensure_test_warehouse_inventory():
    """Helper to ensure KHO-HCM-01 has a CanonicalProduct, ProductSku, Batch, and Stock."""
    today = date.today()
    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        assert wh is not None, "KHO-HCM-01 must exist"

        prod = db.scalar(select(CanonicalProduct).limit(1))
        if not prod:
            prod = CanonicalProduct(
                canonical_name="Paracetamol 500mg Dược Hậu Giang",
                registration_number="VN-21589-19",
                dosage_form="Viên nén",
                route="Uống",
                manufacturer="DHG Pharma",
                manufacturing_country="Việt Nam",
                package_description="Hộp 10 vỉ x 10 viên",
            )
            db.add(prod)
            db.flush()

        sku = db.scalar(select(ProductSku).where(ProductSku.canonical_product_id == prod.id).limit(1))
        if not sku:
            sku = ProductSku(
                canonical_product_id=prod.id,
                sku_code="SKU-PARA-500-BOX",
                uom="Hộp",
                conversion_rate=1,
                base_price=Decimal("45000"),
                is_default=True,
                is_active=True,
            )
            db.add(sku)
            db.flush()

        batch = db.scalar(select(InventoryBatch).where(InventoryBatch.sku_id == sku.id).limit(1))
        if not batch:
            batch = InventoryBatch(
                sku_id=sku.id,
                batch_number="BAT-PARA-2026-X1",
                manufacture_date=today - timedelta(days=60),
                expiry_date=today + timedelta(days=365),
                initial_quantity=500,
                status=BatchStatus.ACTIVE,
            )
            db.add(batch)
            db.flush()

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
                quantity_on_hand=200,
                quantity_reserved=10,
                quantity_available=190,
            )
            db.add(stock)
            db.flush()

        db.commit()


def test_branch_warehouse_dashboard_metrics_and_time_filters(client, manager_hcm_headers):
    """
    Section 2: Dashboard Quản lý kho hỗ trợ bộ lọc thời gian và trả về đầy đủ các thẻ số liệu.
    """
    _ensure_test_warehouse_inventory()

    # 1. Hôm nay
    res_today = client.get("/api/v1/warehouse-portal/me/dashboard?time_range=today", headers=manager_hcm_headers)
    assert res_today.status_code == 200
    data_today = res_today.json()
    assert data_today["time_range"] == "today"
    assert "kpi" in data_today

    kpi = data_today["kpi"]
    assert "total_assigned_orders" in kpi
    assert "total_skus" in kpi
    assert "total_batches" in kpi
    assert "total_available_quantity" in kpi
    assert "total_on_hand_quantity" in kpi
    assert "total_reserved_quantity" in kpi
    assert "low_stock_count" in kpi
    assert "near_expiry_batches" in kpi
    assert "expired_batches" in kpi
    assert "quarantined_batches" in kpi
    assert "pending_receipts_count" in kpi
    assert "unread_alerts_count" in kpi
    assert "order_status_counts" in kpi
    assert "fulfillment_counts" in kpi

    # 2. 7 ngày & 30 ngày
    res_7d = client.get("/api/v1/warehouse-portal/me/dashboard?time_range=7days", headers=manager_hcm_headers)
    assert res_7d.status_code == 200
    assert res_7d.json()["time_range"] == "7days"

    res_30d = client.get("/api/v1/warehouse-portal/me/dashboard?time_range=30days", headers=manager_hcm_headers)
    assert res_30d.status_code == 200
    assert res_30d.json()["time_range"] == "30days"


def test_branch_warehouse_products_list_and_five_tab_details(client, manager_hcm_headers):
    """
    Section 5 & 6: Danh sách thuốc chi nhánh và hồ sơ chi tiết 5 Tab.
    """
    _ensure_test_warehouse_inventory()

    # 1. Danh sách thuốc tại kho HCM
    res = client.get("/api/v1/warehouse-portal/products", headers=manager_hcm_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1

    first_item = data["items"][0]
    sku_id = first_item["sku_id"]
    assert first_item["product_name"]
    assert first_item["total_on_hand"] >= 0
    assert first_item["total_available"] >= 0

    # 2. Chi tiết 5 mục của thuốc
    res_detail = client.get(f"/api/v1/warehouse-portal/products/{sku_id}", headers=manager_hcm_headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()

    # Tab A: Thông tin chung từ dữ liệu gốc Admin
    assert "general_info" in detail
    gen = detail["general_info"]
    assert "canonical_name" in gen
    assert "registration_number" in gen
    assert "active_ingredients" in gen
    assert "dosage_form" in gen
    assert "route_of_administration" in gen
    assert "manufacturer" in gen

    # Tab B: Mức tồn kho
    assert "stock_levels" in detail
    stock = detail["stock_levels"]
    assert "total_on_hand" in stock
    assert "total_available" in stock
    assert "total_reserved" in stock
    assert "min_stock" in stock
    assert "max_stock" in stock

    # Tab C: Danh sách lô theo FEFO
    assert "batches" in detail
    assert isinstance(detail["batches"], list)

    # Tab D: Lịch sử biến động kho
    assert "movements" in detail
    assert isinstance(detail["movements"], list)

    # Tab E: Đơn hàng liên quan
    assert "related_orders" in detail
    assert isinstance(detail["related_orders"], list)


def test_branch_warehouse_csv_template_and_import_pipeline(client, manager_hcm_headers):
    """
    Section 7 & 11: Tải template CSV 14 cột, kiểm tra preview, phát hiện lỗi HSD < 180 ngày và commit nhập kho.
    """
    _ensure_test_warehouse_inventory()

    # 1. Tải template CSV
    res_tpl = client.get("/api/v1/warehouse-portal/imports/template", headers=manager_hcm_headers)
    assert res_tpl.status_code == 200
    assert "text/csv" in res_tpl.headers["content-type"]
    tpl_text = res_tpl.text
    assert "registration_number" in tpl_text
    assert "batch_number" in tpl_text
    assert "expiry_date" in tpl_text
    assert "storage_location" in tpl_text

    with SessionLocal() as db:
        sku = db.scalar(select(ProductSku).where(ProductSku.sku_code != None).limit(1))
        assert sku is not None
        reg_number = sku.canonical_product.registration_number if sku.canonical_product else "VN-TEST-REG"
        sku_code = sku.sku_code

    today = date.today()
    valid_exp = (today + timedelta(days=365)).isoformat()
    invalid_exp = (today + timedelta(days=90)).isoformat()  # < 180 ngày -> Rule 1 vi phạm

    unique_lot_valid = f"LOT-VAL-{uuid.uuid4().hex[:6].upper()}"
    unique_lot_invalid = f"LOT-INV-{uuid.uuid4().hex[:6].upper()}"

    csv_data = io.StringIO()
    writer = csv.writer(csv_data)
    writer.writerow([
        "registration_number", "sku_code", "batch_number", "manufacturing_date", "expiry_date",
        "quantity", "uom", "unit_cost", "supplier_code", "invoice_number", "receipt_date",
        "storage_location", "storage_condition", "note"
    ])
    writer.writerow([
        reg_number, sku_code, unique_lot_valid, (today - timedelta(days=60)).isoformat(), valid_exp,
        "100", "Hộp", "15000", "NCC-DHG", "HD-TEST-01", today.isoformat(),
        "Khu A - Kệ 01", "Bảo quản mát", "Lô hàng hợp lệ"
    ])
    writer.writerow([
        reg_number, sku_code, unique_lot_invalid, (today - timedelta(days=300)).isoformat(), invalid_exp,
        "50", "Hộp", "15000", "NCC-DHG", "HD-TEST-02", today.isoformat(),
        "Khu A - Kệ 02", "Bảo quản mát", "Lô hàng HSD < 180 ngày"
    ])

    file_bytes = csv_data.getvalue().encode("utf-8")
    files = {"file": (f"test_import_{uuid.uuid4().hex[:6]}.csv", file_bytes, "text/csv")}

    # 3. Gửi Preview
    res_prev = client.post("/api/v1/warehouse-portal/imports/preview", files=files, headers=manager_hcm_headers)
    assert res_prev.status_code == 200
    prev_json = res_prev.json()
    assert prev_json["total_rows"] == 2
    assert prev_json["valid_count"] == 1
    assert prev_json["invalid_count"] == 1
    assert prev_json["can_commit"] is True

    # Kiểm tra dòng invalid có thông báo vi phạm Rule 1 (tối thiểu 180 ngày)
    invalid_row = prev_json["invalid_rows"][0]
    assert any("180" in err for err in invalid_row["errors"])

    import_id = prev_json["import_id"]

    # 4. Kiểm tra phát hiện trùng file SHA-256
    files_dup = {"file": ("test_import_dup.csv", file_bytes, "text/csv")}
    res_dup = client.post("/api/v1/warehouse-portal/imports/preview", files=files_dup, headers=manager_hcm_headers)
    assert res_dup.status_code == 400
    assert "đã được tải lên trước đó" in res_dup.json()["detail"]

    # 5. Commit phiên nhập kho hợp lệ
    res_commit = client.post(f"/api/v1/warehouse-portal/imports/{import_id}/commit", headers=manager_hcm_headers)
    assert res_commit.status_code == 200
    commit_data = res_commit.json()
    assert commit_data["success"] is True
    assert commit_data["total_items"] == 100
    assert "REC-" in commit_data["receipt_code"]

    # 6. Kiểm tra xem phiên nhập đã xuất hiện trong danh sách lịch sử
    res_hist = client.get("/api/v1/warehouse-portal/imports", headers=manager_hcm_headers)
    assert res_hist.status_code == 200
    hist_items = res_hist.json()["items"]
    assert any(h["id"] == import_id and h["status"] == "COMMITTED" for h in hist_items)


def test_large_stock_adjustment_requires_admin_approval(client, manager_hcm_headers, admin_headers):
    """
    Section 12: Biến động kiểm kê lớn (delta >= 50 sản phẩm hoặc >= 10M VNĐ)
    tự động chuyển sang trạng thái PENDING_ADMIN_APPROVAL và cần Admin duyệt.
    """
    _ensure_test_warehouse_inventory()

    with SessionLocal() as db:
        wh = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HCM-01"))
        bs = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.warehouse_id == wh.id))
        assert bs is not None
        batch_id = bs.batch_id
        original_qty = bs.quantity_on_hand

    # Tạo điều chỉnh lớn: delta = +60 sản phẩm (>= 50 units -> Rule 2 kích hoạt)
    large_delta_target = original_qty + 60
    payload = {
        "reason": "Kiểm kê định kỳ phát hiện thừa 60 sản phẩm do nhà cung cấp khuyến mãi thêm",
        "items": [
            {
                "batch_id": batch_id,
                "actual_quantity": large_delta_target,
                "reason": "Hàng khuyến mãi nhà cung cấp kèm thêm"
            }
        ]
    }

    res_adj = client.post("/api/v1/warehouse-portal/adjustments", json=payload, headers=manager_hcm_headers)
    assert res_adj.status_code == 201
    adj_data = res_adj.json()
    assert adj_data["status"] == "PENDING_ADMIN_APPROVAL", "Điều chỉnh lớn bắt buộc phải chuyển sang PENDING_ADMIN_APPROVAL"

    # Kiểm tra tồn kho chưa được cộng ngay khi chưa duyệt
    with SessionLocal() as db:
        bs_check = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.warehouse_id == wh.id, WarehouseBatchStock.batch_id == batch_id))
        assert bs_check.quantity_on_hand == original_qty, "Tồn kho không được thay đổi khi chưa có Admin phê duyệt"

        adj_obj = db.scalar(select(StockAdjustment).where(StockAdjustment.adjustment_code == adj_data["adjustment_code"]))
        adj_id = adj_obj.id

    # Admin tiến hành phê duyệt
    res_approve = client.post(f"/api/v1/warehouse-portal/adjustments/{adj_id}/admin-approve", headers=admin_headers)
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "CONFIRMED"

    # Kiểm tra tồn kho sau khi Admin duyệt đã được cập nhật thành công
    with SessionLocal() as db:
        bs_after = db.scalar(select(WarehouseBatchStock).where(WarehouseBatchStock.warehouse_id == wh.id, WarehouseBatchStock.batch_id == batch_id))
        assert bs_after.quantity_on_hand == large_delta_target, "Tồn kho phải được cập nhật đúng sau khi Admin duyệt"


def test_warehouse_alerts_realtime_and_mark_read(client, manager_hcm_headers):
    """
    Section 13: Cảnh báo bất thường kho và đánh dấu đã xem.
    """
    _ensure_test_warehouse_inventory()

    # 1. Lấy danh sách cảnh báo
    res = client.get("/api/v1/warehouse-portal/alerts", headers=manager_hcm_headers)
    assert res.status_code == 200
    alerts_data = res.json()
    assert "items" in alerts_data
    assert "unread_total" in alerts_data

    # 2. Đánh dấu tất cả đã đọc
    res_mark_all = client.post("/api/v1/warehouse-portal/alerts/mark-all-read", headers=manager_hcm_headers)
    assert res_mark_all.status_code == 200
    assert res_mark_all.json()["success"] is True

    # 3. Kiểm tra lại unread_total = 0
    res_after = client.get("/api/v1/warehouse-portal/alerts?is_read=false", headers=manager_hcm_headers)
    assert res_after.status_code == 200
    assert res_after.json()["total"] == 0


def test_strict_branch_warehouse_rbac_isolation(client, manager_hcm_headers):
    """
    Bảo vệ chống can thiệp chéo kho (Anti-IDOR):
    Quản lý kho HCM truyền warehouse_id của kho Hà Nội bị chặn 403 Forbidden.
    """
    with SessionLocal() as db:
        wh_hn = db.scalar(select(Warehouse).where(Warehouse.code == "KHO-HN-01"))
        assert wh_hn is not None
        hn_id = wh_hn.id

    # Quản lý kho HCM cố tình can thiệp xem dữ liệu kho Hà Nội
    res = client.get(f"/api/v1/warehouse-portal/me/dashboard?warehouse_id={hn_id}", headers=manager_hcm_headers)
    assert res.status_code == 403, "Bảo vệ RBAC: Quản lý kho không được xem dữ liệu kho khác và phải bị trả về 403 Forbidden"
