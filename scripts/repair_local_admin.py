"""Script Chuẩn Hóa / Khôi Phục Tài Khoản Admin Demo Cục Bộ (Local Admin Repair).

Mục đích:
- Kiểm tra hoặc thiết lập tài khoản admin@pharmatrust.vn với vai trò ADMIN và mật khẩu demo Admin@123456.
- Mặc định CHỈ KIỂM TRA (dry-run). Cần truyền cờ --apply để áp dụng thay đổi vào cơ sở dữ liệu.
- Tuyệt đối TỪ CHỐI thực thi trên môi trường Production hoặc Staging.
- Không in mật khẩu băm (password_hash) ra màn hình hoặc log.
- Không xóa hay thay đổi bất kỳ tài khoản hoặc dữ liệu nào khác.
"""
import argparse
import os
import sys
from pathlib import Path

# Thêm apps/api vào sys.path để nạp cấu hình và model
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "apps" / "api"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check_environment():
    from app.core.config import settings

    env = getattr(settings, "app_env", os.getenv("APP_ENV", "development")).lower()
    if env in ("production", "prod", "staging", "stag"):
        print(f"[TỪ CHỐI THỰC THI] Script này chỉ được phép chạy trong môi trường cục bộ (dev/local/test). Môi trường hiện tại: '{env}'.")
        sys.exit(1)
    return env


def repair_admin(apply_changes: bool = False):
    env_name = check_environment()

    from app.core.security import hash_password, verify_password
    from app.db.session import SessionLocal
    from app.models.entities import User
    from app.models.enums import UserRole
    from sqlalchemy import select

    admin_email = "admin@pharmatrust.vn"
    expected_pwd = "Admin@123456"

    print("=" * 75)
    mode_str = "[APPLY - GHI THAY ĐỔI VÀO DATABASE]" if apply_changes else "[DRY-RUN - CHỈ KIỂM TRA, KHÔNG SỬA ĐỔI]"
    print(f"H4CARE - KIỂM TRA & CHUẨN HÓA TÀI KHOẢN ADMIN DEMO {mode_str}")
    print(f"Môi trường thực thi: {env_name}")
    print("=" * 75)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == admin_email))

        print("\n1. TRẠNG THÁI HIỆN TẠI TRONG DATABASE:")
        print("-" * 50)
        if not user:
            print(f"  - Tài khoản '{admin_email}': CHƯA TỒN TẠI trong cơ sở dữ liệu.")
            current_status = "NOT_FOUND"
        else:
            role_val = getattr(user.role, "value", str(user.role))
            pwd_match = verify_password(expected_pwd, user.password_hash) if user.password_hash else False
            print(f"  - ID:                 {user.id}")
            print(f"  - Email:              {user.email}")
            print(f"  - Họ và tên:          {user.full_name}")
            print(f"  - Vai trò (Role):     {role_val} (Kỳ vọng: ADMIN)")
            print(f"  - Hoạt động:          {user.is_active} (Kỳ vọng: True)")
            print(f"  - Mật khẩu khớp demo: {'ĐÚNG (Khớp Admin@123456)' if pwd_match else 'KHÔNG KHỚP'}")
            print(f"  - Cần đổi mật khẩu:   {getattr(user, 'must_change_password', False)}")
            current_status = "EXISTS"

        needs_repair = False
        reasons = []

        if not user:
            needs_repair = True
            reasons.append("Cần tạo mới tài khoản admin@pharmatrust.vn")
        else:
            if user.role != UserRole.ADMIN:
                needs_repair = True
                reasons.append(f"Vai trò hiện tại là '{role_val}', cần cập nhật thành 'ADMIN'")
            if not user.is_active:
                needs_repair = True
                reasons.append("Tài khoản đang bị khóa (is_active=False), cần kích hoạt lại")
            if not verify_password(expected_pwd, user.password_hash):
                needs_repair = True
                reasons.append("Mật khẩu hiện tại không khớp với mật khẩu demo 'Admin@123456'")

        print("\n2. ĐÁNH GIÁ SỰ ĐỒNG BỘ:")
        print("-" * 50)
        if not needs_repair:
            print("  [HOÀN HẢO] Tài khoản Admin demo đã đúng chuẩn (Role: ADMIN, is_active: True, Mật khẩu: Admin@123456).")
            print("  Không cần thực hiện bất kỳ sửa đổi nào.")
            return

        print("  [CẦN CHUẨN HÓA] Phát hiện các điểm lệch cấu hình:")
        for r in reasons:
            print(f"    * {r}")

        if not apply_changes:
            print("\n" + "=" * 75)
            print("  THÔNG BÁO: Đang ở chế độ Dry-Run nên chưa có dữ liệu nào bị thay đổi.")
            print("  Để thực hiện chuẩn hóa, hãy chạy lại lệnh với tham số --apply:")
            print("    python scripts/repair_local_admin.py --apply")
            print("=" * 75)
            return

        print("\n3. THỰC HIỆN CẬP NHẬT (--apply):")
        print("-" * 50)
        new_hash = hash_password(expected_pwd)

        if not user:
            user = User(
                email=admin_email,
                password_hash=new_hash,
                full_name="Quản Trị Viên Hệ Thống",
                role=UserRole.ADMIN,
                phone="0901234561",
                is_active=True,
                must_change_password=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"  [ĐÃ TẠO MỚI] Tạo thành công tài khoản {admin_email} với quyền ADMIN.")
        else:
            user.role = UserRole.ADMIN
            user.is_active = True
            user.password_hash = new_hash
            if hasattr(user, "must_change_password"):
                user.must_change_password = False
            db.commit()
            db.refresh(user)
            print(f"  [ĐÃ CẬP NHẬT] Đã đồng bộ vai trò ADMIN và mật khẩu demo cho {admin_email}.")

        print("\n4. TRẠNG THÁI SAU KHI SỬA ĐỔI:")
        print("-" * 50)
        post_role = getattr(user.role, "value", str(user.role))
        post_pwd = verify_password(expected_pwd, user.password_hash)
        print(f"  - ID:                 {user.id}")
        print(f"  - Email:              {user.email}")
        print(f"  - Vai trò (Role):     {post_role}")
        print(f"  - Hoạt động:          {user.is_active}")
        print(f"  - Mật khẩu khớp demo: {'ĐÚNG' if post_pwd else 'LỖI'}")
        print("=" * 75)
        print("CHUẨN HÓA TÀI KHOẢN ADMIN DEMO THÀNH CÔNG!")
        print("=" * 75)


def main():
    parser = argparse.ArgumentParser(description="Kiểm tra và chuẩn hóa tài khoản Admin demo cho môi trường cục bộ.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Thực hiện ghi thay đổi vào cơ sở dữ liệu (mặc định chỉ kiểm tra).",
    )
    args = parser.parse_args()
    repair_admin(apply_changes=args.apply)


if __name__ == "__main__":
    main()
