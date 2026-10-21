#!/usr/bin/env python3
"""
scripts/migrate_catalog_to_neon.py

Công cụ di chuyển toàn bộ Danh mục Dược phẩm, SKU, Bảng giá, Lô thuốc (FEFO) và Tồn kho
từ SQLite local sang Neon PostgreSQL staging/production.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text


def parse_db_date(val: Any) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        cleaned = val.strip().split(" ")[0].split("T")[0]
        try:
            return date.fromisoformat(cleaned)
        except Exception:
            return None
    return None


def parse_db_datetime(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        cleaned = val.strip().replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(cleaned)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def canonicalize_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgres://"):
        return "postgresql+psycopg://" + u[len("postgres://"):]
    if u.startswith("postgresql://") and not u.startswith("postgresql+"):
        return "postgresql+psycopg://" + u[len("postgresql://"):]
    return u


def get_neon_url(cli_url: str | None = None) -> str | None:
    if cli_url:
        return cli_url
    for env_var in ["NEON_DATABASE_URL", "TARGET_DATABASE_URL", "DATABASE_URL"]:
        val = os.environ.get(env_var)
        if val and ("neon.tech" in val or "postgresql" in val):
            return val
    for p in [Path(".env.neon"), Path(".env.staging"), Path("apps/api/.env.neon")]:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NEON_DATABASE_URL=") or line.startswith("DATABASE_URL="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
    return None


def sanitize_row(tbl: str, row: dict, publish_drafts: bool = False) -> dict:
    clean = {}
    for col, val in row.items():
        # Publish drafts option
        if tbl == "canonical_products" and col == "publish_status":
            if publish_drafts and val == "DRAFT":
                val = "PUBLISHED"

        # Date handling
        if col in ("manufacture_date", "expiry_date", "effective_date", "registration_valid_from", "registration_valid_to"):
            clean[col] = parse_db_date(val)
        # DateTime handling
        elif col in ("created_at", "updated_at", "observed_at", "fetched_at", "last_success_at", "last_failure_at", "atc_verified_at"):
            clean[col] = parse_db_datetime(val)
        # JSON handling
        elif col in ("alternative_names", "external_codes", "ingredients_json"):
            if val is None:
                clean[col] = "[]"
            elif isinstance(val, (dict, list)):
                clean[col] = json.dumps(val)
            elif isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    clean[col] = json.dumps(parsed)
                except Exception:
                    clean[col] = val
            else:
                clean[col] = "[]"
        # Boolean handling
        elif col.startswith("is_") or col == "enabled":
            clean[col] = bool(val) if val is not None else False
        elif isinstance(val, str):
            # Clamp strings that exceed PostgreSQL column constraints
            if tbl == "ingredients" and col == "normalized_name" and len(val) > 300:
                clean[col] = val[:300]
            elif tbl == "canonical_products" and col == "storage_conditions" and len(val) > 500:
                clean[col] = val[:500]
            elif tbl == "product_ingredients" and col == "original_strength_text" and len(val) > 200:
                clean[col] = val[:200]
            else:
                clean[col] = val
        else:
            clean[col] = val
    return clean


def migrate_catalog(
    source_db_path: Path,
    target_url: str,
    dry_run: bool = True,
    publish_drafts: bool = False,
):
    print("=" * 75)
    print(" H4CARE CATALOG & INVENTORY MIGRATION: SQLITE -> NEON POSTGRESQL")
    print("=" * 75)
    print(f"[*] Chế độ thực thi       : {'DRY-RUN (MÔ PHỎNG AN TOÀN)' if dry_run else 'COMMIT (GHI THẬT)'}")
    print(f"[*] Nguồn SQLite           : {source_db_path.resolve()}")
    masked_target = target_url.split("@")[-1] if "@" in target_url else "configured"
    print(f"[*] Đích Neon PostgreSQL   : ...@{masked_target}")
    print("-" * 75)

    if not source_db_path.exists():
        raise FileNotFoundError(f"Không tìm thấy SQLite nguồn tại: {source_db_path}")

    conn_sq = sqlite3.connect(str(source_db_path))
    conn_sq.row_factory = sqlite3.Row
    c_sq = conn_sq.cursor()

    canonical_target = canonicalize_url(target_url)
    engine_pg = create_engine(canonical_target, echo=False)

    tables_order = [
        "data_sources",
        "suppliers",
        "warehouse_locations",
        "ingredients",
        "canonical_products",
        "product_ingredients",
        "product_skus",
        "price_observations",
        "regulatory_records",
        "product_source_fields",
        "inventory_batches",
        "warehouse_batch_stock",
    ]

    with engine_pg.connect() as check_conn:
        inspector = inspect(check_conn)
        print("\n[1] KIỂM TRA SCHEMA VÀ DỮ LIỆU HIỆN CÓ TRÊN NEON:")
        for tbl in tables_order:
            if not inspector.has_table(tbl):
                raise RuntimeError(f"Bảng '{tbl}' chưa tồn tại trên Neon. Vui lòng chạy Alembic migration trước.")
            cnt = check_conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar() or 0
            print(f"    • {tbl:25}: {cnt} bản ghi trên Neon")

    print("\n[2] ĐỌC DỮ LIỆU NGUỒN TỪ SQLITE LOCAL:")
    source_data: dict[str, list[dict]] = {}
    for tbl in tables_order:
        c_sq.execute(f"SELECT * FROM {tbl} ORDER BY id")
        source_data[tbl] = [dict(row) for row in c_sq.fetchall()]
        print(f"    • {tbl:25}: {len(source_data[tbl])} bản ghi nguồn")

    cp_list = source_data["canonical_products"]
    published_cnt = sum(1 for p in cp_list if p.get("publish_status") == "PUBLISHED")
    draft_cnt = sum(1 for p in cp_list if p.get("publish_status") == "DRAFT")
    review_cnt = sum(1 for p in cp_list if p.get("publish_status") == "REVIEW_REQUIRED")
    blocked_cnt = sum(1 for p in cp_list if p.get("publish_status") == "BLOCKED")

    print(f"\n    Trạng thái xuất bản thuốc trong nguồn:")
    print(f"      - PUBLISHED        : {published_cnt} thuốc (Hiển thị ngay trên Storefront)")
    print(f"      - DRAFT            : {draft_cnt} thuốc (Cần duyệt để hiển thị)")
    print(f"      - REVIEW_REQUIRED  : {review_cnt} thuốc (Chờ dược sĩ kiểm duyệt)")
    print(f"      - BLOCKED          : {blocked_cnt} thuốc (Bị chặn/thu hồi)")

    print("\n[3] BẮT ĐẦU NẠP DỮ LIỆU VÀO NEON POSTGRESQL:")
    with engine_pg.connect() as tx_conn:
        trans = tx_conn.begin()
        try:
            for tbl in tables_order:
                rows = source_data[tbl]
                if not rows:
                    continue

                cols = list(rows[0].keys())
                col_names = ", ".join(cols)
                placeholders = ", ".join(f":{c}" for c in cols)
                sql = text(f"INSERT INTO {tbl} ({col_names}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING")

                clean_rows = [sanitize_row(tbl, r, publish_drafts=publish_drafts) for r in rows]
                tx_conn.execute(sql, clean_rows)

                print(f"    [✓] Đã nạp {tbl:25}: {len(rows)} bản ghi")

            # Đồng bộ PostgreSQL Sequences
            for st in tables_order:
                tx_conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{st}', 'id'), COALESCE(MAX(id), 1)) FROM {st};"))
            print("    [✓] Đã đồng bộ toàn bộ PostgreSQL sequences")

            if dry_run:
                trans.rollback()
                print("\n[!] CHẾ ĐỘ DRY-RUN: Đã cuộn ngược (ROLLBACK) toàn bộ giao dịch mô phỏng.")
                print("[✓] Cơ sở dữ liệu Neon hoàn toàn không bị thay đổi.")
            else:
                trans.commit()
                print("\n[✓] COMMIT THÀNH CÔNG: Toàn bộ danh mục thuốc và tồn kho đã được nạp an toàn lên Neon!")

        except Exception as err:
            trans.rollback()
            raise err

    if not dry_run:
        with engine_pg.connect() as check_conn:
            print("\n[4] TỔNG KẾT SAU KHI NẠP TRÊN NEON POSTGRESQL:")
            for tbl in tables_order:
                cnt = check_conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                print(f"    • {tbl:25}: {cnt} bản ghi")

    print("=" * 75)


def main():
    parser = argparse.ArgumentParser(description="H4CARE Catalog Migration: SQLite -> Neon PostgreSQL")
    parser.add_argument("--source-db", default="pharmatrust.db", help="Đường dẫn file SQLite nguồn (mặc định: pharmatrust.db)")
    parser.add_argument("--target-url", default=None, help="Chuỗi kết nối Neon PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Chạy mô phỏng (mặc định)")
    parser.add_argument("--commit", action="store_true", help="Thực hiện ghi dữ liệu thật vào Neon")
    parser.add_argument("--publish-drafts", action="store_true", help="Chuyển các sản phẩm DRAFT thành PUBLISHED để hiển thị trên web")

    args = parser.parse_args()

    source_path = Path(args.source_db)
    target_url = get_neon_url(args.target_url)

    if not target_url:
        print("LỖI: Chưa cung cấp chuỗi kết nối Neon PostgreSQL.", file=sys.stderr)
        sys.exit(1)

    dry_run = not args.commit

    migrate_catalog(
        source_db_path=source_path,
        target_url=target_url,
        dry_run=dry_run,
        publish_drafts=args.publish_drafts,
    )


if __name__ == "__main__":
    main()
