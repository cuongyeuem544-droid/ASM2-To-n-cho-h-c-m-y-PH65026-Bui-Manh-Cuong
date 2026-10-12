"""Script di trú dữ liệu vai trò cũ (Legacy Role Migration).
Hỗ trợ chuyển đổi an toàn các tài khoản DATA_REVIEWER và VIEWER sang WAREHOUSE_MANAGER hoặc WAREHOUSE_STAFF.
Có cờ --dry-run (chạy thử nghiệm kiểm tra) và --apply (áp dụng chính thức vào database).
"""
import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROLE_MAPPINGS = {
    "WAREHOUSE_MANAGER": "WAREHOUSE_MANAGER",
    "QUẢN LÝ KHO": "WAREHOUSE_MANAGER",
    "QUAN LY KHO": "WAREHOUSE_MANAGER",
    "MANAGER": "WAREHOUSE_MANAGER",
    "WAREHOUSE_STAFF": "WAREHOUSE_STAFF",
    "NHÂN VIÊN KHO": "WAREHOUSE_STAFF",
    "NHAN VIEN KHO": "WAREHOUSE_STAFF",
    "STAFF": "WAREHOUSE_STAFF",
}


def normalize_role(raw: str) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().upper()
    return ROLE_MAPPINGS.get(cleaned)


def migrate_roles(csv_file: str, db_file: str, apply_changes: bool = False):
    print("=" * 80)
    mode_str = "[APPLY - GHI VÀO DATABASE]" if apply_changes else "[DRY-RUN - CHẠY KIỂM TRA THỬ NGHIỆM]"
    print(f"H4CARE - MIGRATION TÀI KHOẢN VAI TRÒ CŨ {mode_str}")
    print("=" * 80)
    print(f"File CSV nguồn: {os.path.abspath(csv_file)}")
    print(f"Database đích:  {os.path.abspath(db_file)}")

    if not os.path.exists(csv_file):
        print(f"\n[LỖI NGHIÊM TRỌNG] Không tìm thấy file CSV: {csv_file}")
        sys.exit(1)

    if not os.path.exists(db_file):
        print(f"\n[LỖI NGHIÊM TRỌNG] Không tìm thấy database: {db_file}")
        sys.exit(1)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Tải danh sách kho hiện có để tra cứu
    cursor.execute("SELECT id, code, name, is_active FROM warehouses")
    warehouses_by_code = {}
    warehouses_by_id = {}
    for w_id, w_code, w_name, w_active in cursor.fetchall():
        info = {"id": w_id, "code": w_code, "name": w_name, "is_active": bool(w_active)}
        warehouses_by_code[w_code.strip().upper()] = info
        warehouses_by_id[w_id] = info

    # Đọc file CSV
    rows_to_process = []
    with open(csv_file, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required_headers = {"user_id", "email", "vai_tro_cu", "vai_tro_moi", "ma_kho_gan_vao"}
        if not required_headers.issubset(set(reader.fieldnames or [])):
            print(f"\n[LỖI] Header CSV không hợp lệ. Cần có: {required_headers}")
            sys.exit(1)

        for line_num, r in enumerate(reader, start=2):
            rows_to_process.append((line_num, r))

    if not rows_to_process:
        print("\n[CẢNH BÁO] File CSV không có dòng dữ liệu nào.")
        sys.exit(0)

    valid_rows = []
    error_rows = []

    print("\nKIỂM TRA DỮ LIỆU TỪNG DÒNG:")
    print("-" * 80)
    for line_num, r in rows_to_process:
        raw_uid = r.get("user_id", "").strip()
        raw_email = r.get("email", "").strip()
        raw_old_role = r.get("vai_tro_cu", "").strip().upper()
        raw_new_role = r.get("vai_tro_moi", "").strip()
        raw_wh = r.get("ma_kho_gan_vao", "").strip()

        errors = []

        # 1. Kiểm tra user_id
        if not raw_uid.isdigit():
            errors.append(f"user_id '{raw_uid}' không phải số nguyên")
            user_id = None
        else:
            user_id = int(raw_uid)
            cursor.execute("SELECT id, email, role, full_name FROM users WHERE id = ?", (user_id,))
            user_in_db = cursor.fetchone()
            if not user_in_db:
                errors.append(f"Không tìm thấy user id={user_id} trong database")
            else:
                db_email = user_in_db[1]
                db_role = user_in_db[2]
                if raw_email and raw_email.lower() != db_email.lower():
                    errors.append(f"Email không khớp (CSV: {raw_email} vs DB: {db_email})")
                if db_role not in ("DATA_REVIEWER", "VIEWER"):
                    errors.append(f"User id={user_id} hiện mang vai trò '{db_role}', không phải vai trò cũ cần di trú")

        # 2. Kiểm tra vai trò mới
        new_role = normalize_role(raw_new_role)
        if not new_role:
            errors.append(f"vai_tro_moi '{raw_new_role}' không hợp lệ. Chỉ chấp nhận 'WAREHOUSE_MANAGER' hoặc 'WAREHOUSE_STAFF'")

        # 3. Kiểm tra kho gắn vào
        target_wh = None
        if not raw_wh:
            errors.append("Chưa điền ma_kho_gan_vao")
        else:
            if raw_wh.isdigit() and int(raw_wh) in warehouses_by_id:
                target_wh = warehouses_by_id[int(raw_wh)]
            elif raw_wh.upper() in warehouses_by_code:
                target_wh = warehouses_by_code[raw_wh.upper()]
            else:
                errors.append(f"Mã hoặc ID kho '{raw_wh}' không tồn tại trong hệ thống")

            if target_wh and not target_wh["is_active"]:
                errors.append(f"Kho '{target_wh['code']}' ({target_wh['name']}) đang ở trạng thái ngừng hoạt động")

        if errors:
            error_rows.append((line_num, user_id, raw_email, errors))
            print(f"[Dòng {line_num}] ❌ THẤT BẠI: User #{raw_uid} ({raw_email})")
            for err in errors:
                print(f"      - {err}")
        else:
            valid_rows.append({
                "line_num": line_num,
                "user_id": user_id,
                "email": raw_email,
                "old_role": raw_old_role,
                "new_role": new_role,
                "warehouse": target_wh,
            })
            print(f"[Dòng {line_num}] ✅ HỢP LỆ: User #{user_id} ({raw_email}) -> {new_role} tại kho [{target_wh['code']}] {target_wh['name']}")

    print("-" * 80)
    print(f"TỔNG KẾT KIỂM DUYỆT:")
    print(f"  * Tổng số dòng xử lý: {len(rows_to_process)}")
    print(f"  * Số dòng hợp lệ:     {len(valid_rows)}")
    print(f"  * Số dòng có lỗi:     {len(error_rows)}")
    print("-" * 80)

    if error_rows:
        print("\n[DỪNG LẠI] Không thể áp dụng vì có dòng dữ liệu lỗi. Vui lòng sửa file CSV và thử lại.")
        conn.close()
        sys.exit(1)

    if not apply_changes:
        print("\n[CHẾ ĐỘ DRY-RUN HOÀN TẤT] Tất cả dữ liệu đều hợp lệ!")
        print("Để thực sự cập nhật vào database, hãy chạy lệnh với cờ --apply:")
        print(f"  python {sys.argv[0]} --csv \"{csv_file}\" --apply")
        conn.close()
        return

    # THỰC THI GHI VÀO DATABASE KHI CÓ --apply
    print("\nBẮT ĐẦU CẬP NHẬT DATABASE...")
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute("BEGIN TRANSACTION")

        for item in valid_rows:
            uid = item["user_id"]
            new_role = item["new_role"]
            wh_id = item["warehouse"]["id"]

            # 1. Cập nhật role trong bảng users
            cursor.execute(
                "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                (new_role, now_iso, uid),
            )

            # 2. Cập nhật hoặc thêm membership trong user_warehouse_memberships
            cursor.execute(
                "SELECT id FROM user_warehouse_memberships WHERE user_id = ? AND warehouse_id = ?",
                (uid, wh_id),
            )
            existing_m = cursor.fetchone()
            if existing_m:
                cursor.execute(
                    "UPDATE user_warehouse_memberships SET role = ?, is_active = 1 WHERE id = ?",
                    (new_role, existing_m[0]),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_warehouse_memberships (user_id, warehouse_id, role, is_active, assigned_at, assigned_by)
                    VALUES (?, ?, ?, 1, ?, 1)
                    """,
                    (uid, wh_id, new_role, now_iso),
                )

            # 3. Ghi audit log nếu bảng tồn tại
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'"
            )
            if cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO audit_logs (action, entity_type, entity_id, user_id, after_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "MIGRATE_LEGACY_ROLE",
                        "User",
                        str(uid),
                        1,
                        f'{{"old_role": "{item["old_role"]}", "new_role": "{new_role}", "warehouse_id": {wh_id}}}',
                        now_iso,
                    ),
                )

        conn.commit()
        print("✅ Đã cập nhật thành công toàn bộ tài khoản!")

        # 4. Kiểm tra hậu di trú
        cursor.execute("SELECT count(*) FROM users WHERE role IN ('DATA_REVIEWER', 'VIEWER')")
        remaining_legacy = cursor.fetchone()[0]
        print(f"\nKIỂM TRA HẬU DI TRÚ:")
        print(f"  * Số tài khoản còn mang vai trò DATA_REVIEWER hoặc VIEWER: {remaining_legacy}")

        if remaining_legacy == 0:
            print("  => HOÀN TOÀN SẠCH! Không còn bất kỳ tài khoản nào mang vai trò cũ.")
        else:
            print(f"  => CẢNH BÁO: Vẫn còn {remaining_legacy} tài khoản mang vai trò cũ!")

    except Exception as e:
        conn.rollback()
        print(f"\n[LỖI GHI DATABASE] Đã rollback toàn bộ thay đổi. Chi tiết lỗi: {e}")
        sys.exit(1)
    finally:
        conn.close()

    print("=" * 80)
    print("QUÁ TRÌNH DI TRÚ KẾT THÚC THÀNH CÔNG RỰC RỠ.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Di trú tài khoản có vai trò cũ sang RBAC mới")
    parser.add_argument("--csv", default="legacy_role_migration_template.csv", help="Đường dẫn file CSV dữ liệu")
    parser.add_argument("--db", default="pharmatrust.db", help="Đường dẫn file SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra tính hợp lệ, không sửa database")
    parser.add_argument("--apply", action="store_true", help="Áp dụng thay đổi vào database")

    args = parser.parse_args()

    # Mặc định dry-run nếu không truyền --apply
    apply_mode = args.apply
    migrate_roles(args.csv, args.db, apply_changes=apply_mode)
