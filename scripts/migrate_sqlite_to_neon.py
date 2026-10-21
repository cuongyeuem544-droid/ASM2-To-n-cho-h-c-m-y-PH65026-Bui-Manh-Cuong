#!/usr/bin/env python3
"""
scripts/migrate_sqlite_to_neon.py

Công cụ di chuyển dữ liệu tài khoản và phân quyền từ SQLite local sang Neon PostgreSQL staging/production.
Tuân thủ nghiêm ngặt quy tắc an toàn H4CARE:
1. Mặc định chạy ở chế độ --dry-run (không ghi dữ liệu thật nếu thiếu cờ --commit).
2. Không ghi đè hoặc xóa dữ liệu đã có trên Neon PostgreSQL.
3. Không log hoặc in thông tin cá nhân (PII), email, số điện thoại, password hash ra console.
4. Bảo toàn nguyên vẹn ID, vai trò (Role), liên kết kho (warehouse_id), và phân quyền nhân viên (user_warehouse_memberships).
5. Tự động đồng bộ PostgreSQL sequences sau khi insert ID tường minh.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Đảm bảo import được app.core.config nếu chạy từ root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

try:
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import Engine
except ImportError:
    print("LỖI: Chưa cài đặt SQLAlchemy. Vui lòng chạy trong môi trường ảo (.venv).", file=sys.stderr)
    sys.exit(1)


def parse_db_datetime(val: Any) -> datetime | None:
    """Chuyển đổi chuỗi ngày tháng từ SQLite thành datetime UTC có timezone."""
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
    """Chuẩn hóa URL PostgreSQL sang postgresql+psycopg://."""
    u = url.strip()
    if u.startswith("postgres://"):
        return "postgresql+psycopg://" + u[len("postgres://"):]
    if u.startswith("postgresql://") and not u.startswith("postgresql+"):
        return "postgresql+psycopg://" + u[len("postgresql://"):]
    return u


def load_sqlite_source_data(db_path: Path):
    """Đọc và kiểm tra tính toàn vẹn dữ liệu từ SQLite local."""
    if not db_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file SQLite tại: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Đọc kho (warehouses)
    c.execute("SELECT * FROM warehouses ORDER BY id")
    warehouses = [dict(row) for row in c.fetchall()]

    # 2. Đọc người dùng (users)
    c.execute("SELECT * FROM users ORDER BY id")
    users = [dict(row) for row in c.fetchall()]

    # 3. Đọc quyền kho (user_warehouse_memberships)
    c.execute("SELECT * FROM user_warehouse_memberships ORDER BY id")
    memberships = [dict(row) for row in c.fetchall()]

    conn.close()
    return warehouses, users, memberships


def audit_source_data(warehouses: list[dict], users: list[dict], memberships: list[dict]):
    """Kiểm tra và thống kê an toàn dữ liệu nguồn."""
    wh_ids = {w["id"] for w in warehouses}
    user_ids = {u["id"] for u in users}

    role_counts: dict[str, int] = {}
    active_counts: dict[str, int] = {}
    hash_counts: dict[str, int] = {"scrypt": 0, "legacy_dummy": 0}

    orphaned_user_wh = []
    for u in users:
        role = u.get("role") or "UNKNOWN"
        role_counts[role] = role_counts.get(role, 0) + 1
        if u.get("is_active"):
            active_counts[role] = active_counts.get(role, 0) + 1

        pw = u.get("password_hash") or ""
        if pw.startswith("scrypt$"):
            hash_counts["scrypt"] += 1
        else:
            hash_counts["legacy_dummy"] += 1

        wh_id = u.get("warehouse_id")
        if wh_id is not None and wh_id not in wh_ids:
            orphaned_user_wh.append(u["id"])

    orphaned_mem_user = [m["id"] for m in memberships if m["user_id"] not in user_ids]
    orphaned_mem_wh = [m["id"] for m in memberships if m["warehouse_id"] not in wh_ids]

    return {
        "total_warehouses": len(warehouses),
        "total_users": len(users),
        "total_memberships": len(memberships),
        "role_counts": role_counts,
        "active_counts": active_counts,
        "hash_counts": hash_counts,
        "orphaned_user_wh_count": len(orphaned_user_wh),
        "orphaned_mem_user_count": len(orphaned_mem_user),
        "orphaned_mem_wh_count": len(orphaned_mem_wh),
    }


def run_migration(
    source_db_path: Path,
    target_url: str | None,
    dry_run: bool = True,
    migrate_legacy: bool = False,
):
    print("=" * 70)
    print(" H4CARE DATABASE MIGRATION TOOL: LOCAL SQLITE -> NEON POSTGRESQL")
    print("=" * 70)
    print(f"[*] Chế độ thực thi       : {'DRY-RUN (MÔ PHỎNG - AN TOÀN)' if dry_run else 'COMMIT (GHI DỮ LIỆU THẬT)'}")
    print(f"[*] Nguồn SQLite           : {source_db_path.resolve()}")
    if target_url:
        masked_target = target_url.split("@")[-1] if "@" in target_url else "configured"
        print(f"[*] Đích Neon PostgreSQL   : ...@{masked_target}")
    else:
        print("[*] Đích Neon PostgreSQL   : Chưa cung cấp (chỉ kiểm toán nguồn)")
    print("-" * 70)

    # 1. Nạp và kiểm toán nguồn SQLite
    warehouses, users, memberships = load_sqlite_source_data(source_db_path)
    audit = audit_source_data(warehouses, users, memberships)

    print("\n[+] THỐNG KÊ DỮ LIỆU NGUỒN (LOCAL SQLITE):")
    print(f"    - Tổng số kho (warehouses)            : {audit['total_warehouses']}")
    print(f"    - Tổng số tài khoản (users)           : {audit['total_users']}")
    print(f"    - Tổng số phân quyền kho (memberships): {audit['total_memberships']}")
    print("\n    Phân bổ theo vai trò:")
    for role, count in audit["role_counts"].items():
        act = audit["active_counts"].get(role, 0)
        print(f"      • {role:20}: {count} tài khoản (Hoạt động: {act})")

    print("\n    Định dạng mật khẩu:")
    print(f"      • scrypt (Tương thích 100% login)   : {audit['hash_counts']['scrypt']} tài khoản")
    print(f"      • legacy (Cần đổi mật khẩu)         : {audit['hash_counts']['legacy_dummy']} tài khoản")

    if audit["orphaned_user_wh_count"] > 0 or audit["orphaned_mem_user_count"] > 0:
        print("\n[!] CẢNH BÁO: Phát hiện khóa ngoại mồ côi:")
        print(f"    - User có warehouse_id không hợp lệ: {audit['orphaned_user_wh_count']}")
        print(f"    - Membership trỏ đến user không tồn tại: {audit['orphaned_mem_user_count']}")
        print(f"    - Membership trỏ đến kho không tồn tại : {audit['orphaned_mem_wh_count']}")
    else:
        print("\n[✓] Tính toàn vẹn quan hệ (Foreign Keys): ĐẠT 100% — Không có khóa ngoại mồ côi.")

    if not target_url:
        print("\n[i] Không có chuỗi kết nối target_url. Hoàn thành kiểm toán dữ liệu nguồn.")
        return audit

    # 2. Kết nối và kiểm tra đích Neon PostgreSQL
    canonical_target = canonicalize_url(target_url)
    engine = create_engine(canonical_target, echo=False)

    with engine.connect() as conn:
        # Kiểm tra bảng đã tồn tại chưa
        inspector = inspect(conn)
        required_tables = ["warehouses", "users", "user_warehouse_memberships"]
        for tbl in required_tables:
            if not inspector.has_table(tbl):
                raise RuntimeError(f"Bảng '{tbl}' chưa tồn tại trên database đích. Vui lòng chạy Alembic migration trước.")

        # Kiểm tra dữ liệu hiện có trên Neon
        existing_user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        existing_wh_count = conn.execute(text("SELECT COUNT(*) FROM warehouses")).scalar() or 0
        existing_mem_count = conn.execute(text("SELECT COUNT(*) FROM user_warehouse_memberships")).scalar() or 0

        print("\n[+] TÌNH TRẠNG HIỆN TẠI TRÊN NEON POSTGRESQL:")
        print(f"    - Số kho hiện có        : {existing_wh_count}")
        print(f"    - Số tài khoản hiện có  : {existing_user_count}")
        print(f"    - Số phân quyền hiện có : {existing_mem_count}")

        # Lấy danh sách ID, email, phone, code đã có để chống trùng lặp
        existing_wh_ids = set(r[0] for r in conn.execute(text("SELECT id FROM warehouses")).fetchall())
        existing_wh_codes = set(r[0] for r in conn.execute(text("SELECT code FROM warehouses")).fetchall())
        existing_user_ids = set(r[0] for r in conn.execute(text("SELECT id FROM users")).fetchall())
        existing_user_emails = set(r[0] for r in conn.execute(text("SELECT lower(email) FROM users")).fetchall())
        existing_user_phones = set(r[0] for r in conn.execute(text("SELECT phone FROM users WHERE phone IS NOT NULL")).fetchall())
        existing_mem_ids = set(r[0] for r in conn.execute(text("SELECT id FROM user_warehouse_memberships")).fetchall())

    # 3. Lọc danh sách bản ghi cần di chuyển
    # A. Warehouses
    warehouses_to_insert = [
        w for w in warehouses
        if w["id"] not in existing_wh_ids and w["code"] not in existing_wh_codes
    ]

    # B. Users
    users_to_insert = []
    users_skipped_legacy = 0
    users_skipped_duplicate = 0

    for u in users:
        is_scrypt = (u.get("password_hash") or "").startswith("scrypt$")
        if not is_scrypt and not migrate_legacy:
            users_skipped_legacy += 1
            continue

        email = (u.get("email") or "").strip().lower()
        phone = (u.get("phone") or "").strip()

        if u["id"] in existing_user_ids or email in existing_user_emails or (phone and phone in existing_user_phones):
            users_skipped_duplicate += 1
            continue

        # Nếu là legacy và được bật migrate_legacy, bắt buộc đổi mật khẩu
        if not is_scrypt:
            u["must_change_password"] = True

        users_to_insert.append(u)

    # C. Memberships
    target_user_ids = existing_user_ids.union({u["id"] for u in users_to_insert})
    target_wh_ids = existing_wh_ids.union({w["id"] for w in warehouses_to_insert})

    memberships_to_insert = [
        m for m in memberships
        if m["id"] not in existing_mem_ids
        and m["user_id"] in target_user_ids
        and m["warehouse_id"] in target_wh_ids
    ]

    print("\n[+] KẾ HOẠCH DI CHUYỂN DỮ LIỆU:")
    print(f"    - Kho sẽ thêm mới                 : {len(warehouses_to_insert)} / {len(warehouses)}")
    print(f"    - Tài khoản sẽ thêm mới           : {len(users_to_insert)} / {len(users)}")
    print(f"      • Bỏ qua tài khoản test cũ      : {users_skipped_legacy}")
    print(f"      • Bỏ qua tài khoản trùng lặp    : {users_skipped_duplicate}")
    print(f"    - Phân quyền kho sẽ thêm mới      : {len(memberships_to_insert)} / {len(memberships)}")

    # 4. Thực thi insert trong Transaction
    with engine.connect() as tx_conn:
        trans = tx_conn.begin()
        try:
            # A. Insert warehouses
            if warehouses_to_insert:
                wh_insert_sql = text("""
                    INSERT INTO warehouses (
                        id, code, name, address, ward, district, province,
                        lat, lng, is_active, is_central, phone, email,
                        province_code, ward_code, place_id, service_radius_km,
                        timezone, max_orders_per_day, created_at, updated_at
                    ) VALUES (
                        :id, :code, :name, :address, :ward, :district, :province,
                        :lat, :lng, :is_active, :is_central, :phone, :email,
                        :province_code, :ward_code, :place_id, :service_radius_km,
                        :timezone, :max_orders_per_day, :created_at, :updated_at
                    )
                """)
                for w in warehouses_to_insert:
                    params = {
                        "id": w["id"],
                        "code": w["code"],
                        "name": w["name"],
                        "address": w["address"],
                        "ward": w.get("ward"),
                        "district": w.get("district"),
                        "province": w.get("province"),
                        "lat": w.get("lat"),
                        "lng": w.get("lng"),
                        "is_active": bool(w.get("is_active", 1)),
                        "is_central": bool(w.get("is_central", 0)),
                        "phone": w.get("phone"),
                        "email": w.get("email"),
                        "province_code": w.get("province_code"),
                        "ward_code": w.get("ward_code"),
                        "place_id": w.get("place_id"),
                        "service_radius_km": float(w.get("service_radius_km") or 30.0),
                        "timezone": w.get("timezone") or "Asia/Ho_Chi_Minh",
                        "max_orders_per_day": int(w.get("max_orders_per_day") or 500),
                        "created_at": parse_db_datetime(w.get("created_at")),
                        "updated_at": parse_db_datetime(w.get("updated_at")),
                    }
                    tx_conn.execute(wh_insert_sql, params)

            # B. Insert users
            if users_to_insert:
                user_insert_sql = text("""
                    INSERT INTO users (
                        id, email, phone, password_hash, full_name, role,
                        loyalty_points, is_active, token_version, last_login_at,
                        warehouse_id, must_change_password, password_changed_at,
                        failed_login_attempts, locked_until, created_by_user_id,
                        created_at, updated_at
                    ) VALUES (
                        :id, :email, :phone, :password_hash, :full_name, :role,
                        :loyalty_points, :is_active, :token_version, :last_login_at,
                        :warehouse_id, :must_change_password, :password_changed_at,
                        :failed_login_attempts, :locked_until, :created_by_user_id,
                        :created_at, :updated_at
                    )
                """)
                for u in users_to_insert:
                    params = {
                        "id": u["id"],
                        "email": u["email"],
                        "phone": u.get("phone"),
                        "password_hash": u["password_hash"],
                        "full_name": u["full_name"],
                        "role": u["role"],
                        "loyalty_points": int(u.get("loyalty_points") or 50),
                        "is_active": bool(u.get("is_active", 1)),
                        "token_version": int(u.get("token_version") or 1),
                        "last_login_at": parse_db_datetime(u.get("last_login_at")),
                        "warehouse_id": u.get("warehouse_id"),
                        "must_change_password": bool(u.get("must_change_password", 0)),
                        "password_changed_at": parse_db_datetime(u.get("password_changed_at")),
                        "failed_login_attempts": int(u.get("failed_login_attempts") or 0),
                        "locked_until": parse_db_datetime(u.get("locked_until")),
                        "created_by_user_id": u.get("created_by_user_id"),
                        "created_at": parse_db_datetime(u.get("created_at")),
                        "updated_at": parse_db_datetime(u.get("updated_at")),
                    }
                    tx_conn.execute(user_insert_sql, params)

            # C. Insert user_warehouse_memberships
            if memberships_to_insert:
                mem_insert_sql = text("""
                    INSERT INTO user_warehouse_memberships (
                        id, user_id, warehouse_id, role, is_active,
                        assigned_at, assigned_by, revoked_at
                    ) VALUES (
                        :id, :user_id, :warehouse_id, :role, :is_active,
                        :assigned_at, :assigned_by, :revoked_at
                    )
                """)
                for m in memberships_to_insert:
                    params = {
                        "id": m["id"],
                        "user_id": m["user_id"],
                        "warehouse_id": m["warehouse_id"],
                        "role": m["role"],
                        "is_active": bool(m.get("is_active", 1)),
                        "assigned_at": parse_db_datetime(m.get("assigned_at")),
                        "assigned_by": m.get("assigned_by"),
                        "revoked_at": parse_db_datetime(m.get("revoked_at")),
                    }
                    tx_conn.execute(mem_insert_sql, params)

            # D. Reset PostgreSQL sequences
            if engine.dialect.name == "postgresql":
                tx_conn.execute(text("SELECT setval(pg_get_serial_sequence('warehouses', 'id'), COALESCE(MAX(id), 1)) FROM warehouses;"))
                tx_conn.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE(MAX(id), 1)) FROM users;"))
                tx_conn.execute(text("SELECT setval(pg_get_serial_sequence('user_warehouse_memberships', 'id'), COALESCE(MAX(id), 1)) FROM user_warehouse_memberships;"))

            if dry_run:
                trans.rollback()
                print("\n[!] Chế độ DRY-RUN: Cuộn ngược (ROLLBACK) toàn bộ thao tác mô phỏng.")
                print("[✓] Cơ sở dữ liệu Neon hoàn toàn không bị thay đổi.")
            else:
                trans.commit()
                print("\n[✓] COMMIT THÀNH CÔNG: Dữ liệu tài khoản và phân quyền đã được di chuyển an toàn vào Neon.")
        except Exception as err:
            trans.rollback()
            raise err

    # 5. Kiểm tra lại sau commit (nếu không phải dry-run)
    if not dry_run:
        with engine.connect() as conn:
            final_user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
            final_wh_count = conn.execute(text("SELECT COUNT(*) FROM warehouses")).scalar() or 0
            final_mem_count = conn.execute(text("SELECT COUNT(*) FROM user_warehouse_memberships")).scalar() or 0
            print(f"\n[+] TỔNG KẾT SAU DI CHUYỂN TRÊN NEON:")
            print(f"    - Tổng số kho               : {final_wh_count}")
            print(f"    - Tổng số tài khoản         : {final_user_count}")
            print(f"    - Tổng số phân quyền kho    : {final_mem_count}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="H4CARE Migration: SQLite -> Neon PostgreSQL")
    parser.add_argument("--source-db", default="pharmatrust.db", help="Đường dẫn file SQLite (mặc định: pharmatrust.db)")
    parser.add_argument("--target-url", default=None, help="Chuỗi kết nối Neon PostgreSQL (hoặc qua biến NEON_DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Chạy mô phỏng không ghi dữ liệu (mặc định)")
    parser.add_argument("--commit", action="store_true", help="Thực hiện ghi thật vào Neon PostgreSQL")
    parser.add_argument("--migrate-legacy", action="store_true", help="Bao gồm cả 5 tài khoản test cũ (bắt buộc must_change_password=True)")

    args = parser.parse_args()

    source_path = Path(args.source_db)
    target_url = args.target_url or os.environ.get("NEON_DATABASE_URL") or os.environ.get("TARGET_DATABASE_URL")
    if not target_url:
        for env_path in [Path(".env.neon"), Path(".env.staging"), Path("apps/api/.env.neon")]:
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("NEON_DATABASE_URL=") or line.startswith("DATABASE_URL="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                target_url = val
                                break
            if target_url:
                break

    # Mặc định an toàn: dry_run = True trừ khi có cờ --commit
    dry_run = not args.commit

    run_migration(
        source_db_path=source_path,
        target_url=target_url,
        dry_run=dry_run,
        migrate_legacy=args.migrate_legacy,
    )


if __name__ == "__main__":
    main()
