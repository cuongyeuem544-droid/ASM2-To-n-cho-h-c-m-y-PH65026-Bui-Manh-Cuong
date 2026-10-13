#!/usr/bin/env python3
"""
H4CARE / PharmaTrust - Legacy Order Linking Script
===================================================
Script liên kết các đơn hàng cũ chưa có user_id (user_id IS NULL) với tài khoản
người dùng đã đăng ký dựa trên Số điện thoại hoặc Email.

An toàn dữ liệu:
- Mặc định chạy ở chế độ DRY-RUN (--dry-run).
- Chỉ thực hiện cập nhật CSDL khi có cờ --commit rõ ràng.
- Ghi nhận chi tiết từng đơn hàng được liên kết.
"""

import argparse
import os
import sys
from pathlib import Path

# Đảm bảo mã hóa UTF-8 cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Thêm thư mục apps/api vào sys.path để import được app module
CURRENT_DIR = Path(__file__).resolve().parent
API_ROOT = CURRENT_DIR.parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlalchemy import select, and_, or_
from app.db.session import SessionLocal
from app.models import Order, User


def normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    digits = "".join(filter(str.isdigit, phone.strip()))
    # Chuẩn hóa đầu số 84 -> 0
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits


def normalize_email(email: str | None) -> str:
    if not email:
        return ""
    return email.strip().lower()


def main():
    parser = argparse.ArgumentParser(
        description="Liên kết đơn hàng lịch sử (user_id IS NULL) với tài khoản khách hàng PharmaTrust."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        default=False,
        help="Thực thi lưu thay đổi vào cơ sở dữ liệu. Mặc định là Dry-run chỉ kiểm tra thống kê.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Chế độ mô phỏng kiểm tra trước, không thay đổi CSDL.",
    )

    args = parser.parse_args()
    is_commit_mode = args.commit and not args.dry_run

    mode_label = "CHẾ ĐỘ THỰC THI (COMMIT)" if is_commit_mode else "CHẾ ĐỘ MÔ PHỎNG (DRY-RUN - AN TOÀN)"
    print("=" * 70)
    print(f"H4CARE / PharmaTrust - CÔNG CỤ DI CHUYỂN ĐƠN HÀNG LỊCH SỬ")
    print(f"Chế độ hoạt động: {mode_label}")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Lấy tất cả người dùng hợp lệ
        all_users = db.scalars(select(User)).all()
        phone_to_user: dict[str, User] = {}
        email_to_user: dict[str, User] = {}

        for u in all_users:
            if u.phone:
                p_norm = normalize_phone(u.phone)
                if p_norm:
                    phone_to_user[p_norm] = u
            if u.email:
                e_norm = normalize_email(u.email)
                if e_norm:
                    email_to_user[e_norm] = u

        # Lấy các đơn hàng chưa gán user_id
        legacy_orders = db.scalars(
            select(Order)
            .where(Order.user_id.is_(None))
            .order_by(Order.id.asc())
        ).all()

        total_legacy = len(legacy_orders)
        print(f"Tìm thấy tổng cộng: {total_legacy} đơn hàng chưa có user_id.")
        print("-" * 70)

        matched_by_phone = 0
        matched_by_email = 0
        unmatched_count = 0
        link_actions = []

        for order in legacy_orders:
            target_user = None
            match_reason = ""

            ord_phone_norm = normalize_phone(order.customer_phone)
            ord_email_norm = normalize_email(order.customer_email)

            if ord_phone_norm and ord_phone_norm in phone_to_user:
                target_user = phone_to_user[ord_phone_norm]
                match_reason = f"Số điện thoại ({order.customer_phone})"
                matched_by_phone += 1
            elif ord_email_norm and ord_email_norm in email_to_user:
                target_user = email_to_user[ord_email_norm]
                match_reason = f"Email ({order.customer_email})"
                matched_by_email += 1
            else:
                unmatched_count += 1

            if target_user:
                link_actions.append({
                    "order_id": order.id,
                    "order_code": order.order_code,
                    "customer_name": order.customer_name,
                    "matched_user_id": target_user.id,
                    "matched_user_name": target_user.full_name,
                    "reason": match_reason,
                })
                if is_commit_mode:
                    order.user_id = target_user.id

        # In kết quả chi tiết
        for act in link_actions[:30]:  # Giới hạn in 30 đơn tiêu biểu
            print(
                f"-> Đơn #{act['order_code']} ({act['customer_name']}) "
                f"==> Gán vào User #{act['matched_user_id']} ({act['matched_user_name']}) "
                f"qua {act['reason']}"
            )
        if len(link_actions) > 30:
            print(f"... và {len(link_actions) - 30} đơn hàng khác đã được khớp.")

        print("-" * 70)
        print("TỔNG KẾT THỐNG KÊ:")
        print(f"  • Tổng đơn chưa có user_id: {total_legacy}")
        print(f"  • Khớp qua số điện thoại:   {matched_by_phone}")
        print(f"  • Khớp qua địa chỉ email:   {matched_by_email}")
        print(f"  • Tổng đơn có thể liên kết: {len(link_actions)}")
        print(f"  • Đơn không khớp (khách vãng lai thật): {unmatched_count}")
        print("-" * 70)

        if is_commit_mode:
            db.commit()
            print(">>> THÀNH CÔNG: Đã commit toàn bộ thay đổi vào cơ sở dữ liệu.")
        else:
            print(">>> KẾT THÚC DRY-RUN: Không có dữ liệu nào bị thay đổi.")
            print(">>> Để áp dụng thật, hãy chạy: python scripts/link_legacy_orders.py --commit")

    except Exception as e:
        db.rollback()
        print(f"LỖI KHI THỰC HIỆN: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
