"""Script xuất danh sách tài khoản mang vai trò cũ (DATA_REVIEWER, VIEWER) ra file CSV.
File CSV mẫu dùng để người quản trị hoặc kỹ sư gán vai trò mới và mã kho trước khi chạy script di trú.
"""
import csv
import os
import sqlite3
import sys

# Đảm bảo UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def export_legacy_roles(db_path: str = "pharmatrust.db", output_csv: str = "legacy_role_migration_template.csv"):
    if not os.path.exists(db_path):
        print(f"[LỖI] Không tìm thấy database tại: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT id, email, role, full_name
    FROM users
    WHERE role IN ('DATA_REVIEWER', 'VIEWER')
    ORDER BY id ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("[THÔNG BÁO] Không có tài khoản nào thuộc nhóm DATA_REVIEWER hoặc VIEWER cần chuyển đổi.")
        return

    # Lấy danh sách kho hợp lệ để gợi ý
    cursor.execute("SELECT code, name FROM warehouses WHERE is_active = 1 ORDER BY id ASC")
    active_warehouses = cursor.fetchall()

    with open(output_csv, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "email", "vai_tro_cu", "vai_tro_moi", "ma_kho_gan_vao"])
        for r in rows:
            u_id, email, role, full_name = r
            # Để trống vai_tro_moi và ma_kho_gan_vao để người dùng điền
            writer.writerow([u_id, email, role, "", ""])

    print("=" * 70)
    print("XUẤT DANH SÁCH TÀI KHOẢN CŨ THÀNH CÔNG")
    print("=" * 70)
    print(f"Tổng số tài khoản cũ cần chuyển đổi: {len(rows)}")
    print(f"File CSV mẫu đã lưu tại: {os.path.abspath(output_csv)}")
    print("\nChi tiết tài khoản:")
    for r in rows:
        print(f"  - ID: {r[0]} | Email: {r[1]} | Vai trò cũ: {r[2]} | Họ tên: {r[3]}")

    print("\nHƯỚNG DẪN ĐIỀN FILE CSV:")
    print("1. 'vai_tro_moi': Chỉ được điền 'WAREHOUSE_MANAGER' (Quản lý kho) hoặc 'WAREHOUSE_STAFF' (Nhân viên kho)")
    print("2. 'ma_kho_gan_vao': Phải là mã kho hợp lệ đang hoạt động trong hệ thống.")
    print("   Một số mã kho mẫu có thể dùng:")
    for code, name in active_warehouses[:5]:
        print(f"     * {code}: {name}")
    print("3. Sau khi điền xong, chạy lệnh:")
    print(f"   python scripts/migrate_legacy_roles.py --csv {output_csv} --dry-run")
    print(f"   python scripts/migrate_legacy_roles.py --csv {output_csv} --apply")
    print("=" * 70)


if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else "pharmatrust.db"
    export_legacy_roles(db_file)
