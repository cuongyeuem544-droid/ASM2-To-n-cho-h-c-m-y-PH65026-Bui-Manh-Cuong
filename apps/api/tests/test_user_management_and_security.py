"""Automated Security & RBAC Test Suite for PharmaTrust User & Staff Management.
Covers all 12 mandatory security and role scoping directives:
1. Admin tạo tài khoản quản lý kho: Thành công.
2. Admin tạo tài khoản nhân viên kho: Thành công.
3. Quản lý kho tạo nhân viên kho thuộc kho của mình: Thành công.
4. Quản lý kho cố tạo Admin: Bị từ chối (403).
5. Quản lý kho cố tạo tài khoản cho kho khác: Bị từ chối (403 hoặc buộc về kho của mình).
6. Quản lý kho cố xem/sửa/khóa nhân viên kho khác: Bị từ chối (403).
7. Admin đặt lại mật khẩu: Thành công, trả mật khẩu tạm thời, must_change_password = true, thu hồi token cũ.
8. Quản lý kho đặt lại mật khẩu cho nhân viên kho mình: Thành công.
9. Quản lý kho đặt lại mật khẩu cho nhân viên kho khác: Bị từ chối (403).
10. Đăng nhập với must_change_password = true: Trả cờ yêu cầu đổi mật khẩu.
11. Đổi mật khẩu thành công: must_change_password trở về false.
12. Tuyệt đối không có API nào trả password_hash.
"""
import pytest
from app.models.enums import UserRole


class TestUserManagementAndSecurity:
    """Kiểm thử tự động phân quyền tài khoản & chính sách an ninh mật khẩu."""

    def test_01_admin_create_warehouse_manager(self, client, admin_headers):
        """1. Admin tạo tài khoản quản lý kho: Thành công."""
        payload = {
            "email": "test_wm_new@pharmatrust.vn",
            "full_name": "Quản Lý Kho Test",
            "phone": "0981112233",
            "role": "WAREHOUSE_MANAGER",
            "warehouse_id": 1,
            "must_change_password": True,
        }
        res = client.post("/api/v1/users", json=payload, headers=admin_headers)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["user"]["role"] == "WAREHOUSE_MANAGER"
        assert data["user"]["warehouse_id"] == 1
        assert data["user"]["must_change_password"] is True
        assert len(data["temporary_password"]) >= 8
        assert "password_hash" not in data
        assert "password_hash" not in data["user"]

    def test_02_admin_create_warehouse_staff(self, client, admin_headers):
        """2. Admin tạo tài khoản nhân viên kho: Thành công."""
        payload = {
            "email": "test_staff_new@pharmatrust.vn",
            "full_name": "Nhân Viên Kho Test",
            "phone": "0982223344",
            "role": "WAREHOUSE_STAFF",
            "warehouse_id": 1,
            "must_change_password": True,
        }
        res = client.post("/api/v1/users", json=payload, headers=admin_headers)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["user"]["role"] == "WAREHOUSE_STAFF"
        assert data["user"]["warehouse_id"] == 1
        assert data["user"]["must_change_password"] is True
        assert len(data["temporary_password"]) >= 8
        assert "password_hash" not in data
        assert "password_hash" not in data["user"]

    def test_03_manager_create_subordinate_staff(self, client, manager_hcm_headers):
        """3. Quản lý kho tạo nhân viên kho thuộc kho của mình: Thành công."""
        payload = {
            "email": "staff_hcm_subordinate@pharmatrust.vn",
            "full_name": "Nhân Viên Kho HCM 1",
            "phone": "0983334455",
            "role": "WAREHOUSE_STAFF",
            "must_change_password": True,
        }
        res = client.post("/api/v1/users", json=payload, headers=manager_hcm_headers)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["user"]["role"] == "WAREHOUSE_STAFF"
        assert data["user"]["must_change_password"] is True
        assert len(data["temporary_password"]) >= 8

    def test_04_manager_cannot_create_admin(self, client, manager_hcm_headers):
        """4. Quản lý kho cố tạo Admin: Bị từ chối (403)."""
        payload = {
            "email": "fake_admin_hacker@pharmatrust.vn",
            "full_name": "Fake Admin",
            "role": "ADMIN",
            "must_change_password": True,
        }
        res = client.post("/api/v1/users", json=payload, headers=manager_hcm_headers)
        assert res.status_code == 403, f"Expected 403 but got {res.status_code}"

    def test_05_manager_cannot_assign_other_warehouse(self, client, manager_hcm_headers):
        """5. Quản lý kho cố tạo tài khoản cho kho khác: Bị từ chối (403)."""
        payload = {
            "email": "cross_warehouse_staff@pharmatrust.vn",
            "full_name": "Cross Warehouse Staff",
            "role": "WAREHOUSE_STAFF",
            "warehouse_id": 9999,  # Cố tình chỉ định kho khác
            "must_change_password": True,
        }
        res = client.post("/api/v1/users", json=payload, headers=manager_hcm_headers)
        assert res.status_code == 403, f"Expected 403 but got {res.status_code}"

    def test_06_manager_cannot_view_edit_lock_other_warehouse_staff(
        self, client, admin_headers, manager_hcm_headers, manager_hn_headers
    ):
        """6. Quản lý kho cố xem/sửa/khóa nhân viên kho khác: Bị từ chối (403)."""
        # Tạo 1 nhân viên thuộc kho Hà Nội
        create_res = client.post(
            "/api/v1/users",
            json={
                "email": "staff_belong_to_hn@pharmatrust.vn",
                "full_name": "Nhân Viên Kho HN Chỉ Thuộc HN",
                "role": "WAREHOUSE_STAFF",
                "warehouse_id": 2,  # Kho Hà Nội
                "must_change_password": True,
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        hn_staff_id = create_res.json()["user"]["id"]

        # 6a. Quản lý kho HCM cố xem nhân viên kho HN -> 403
        get_res = client.get(f"/api/v1/users/{hn_staff_id}", headers=manager_hcm_headers)
        assert get_res.status_code == 403, f"Expected 403 but got {get_res.status_code}"

        # 6b. Quản lý kho HCM cố sửa nhân viên kho HN -> 403
        patch_res = client.patch(
            f"/api/v1/users/{hn_staff_id}",
            json={"full_name": "Hacked Name"},
            headers=manager_hcm_headers,
        )
        assert patch_res.status_code == 403, f"Expected 403 but got {patch_res.status_code}"

        # 6c. Quản lý kho HCM cố khóa nhân viên kho HN -> 403
        lock_res = client.patch(
            f"/api/v1/users/{hn_staff_id}/status",
            headers=manager_hcm_headers,
        )
        assert lock_res.status_code == 403, f"Expected 403 but got {lock_res.status_code}"

    def test_07_admin_reset_password_revokes_token(self, client, admin_headers):
        """7. Admin đặt lại mật khẩu: Thành công, trả mật khẩu tạm thời, must_change_password = true, thu hồi token cũ."""
        # Tạo user test
        res = client.post(
            "/api/v1/users",
            json={
                "email": "user_for_reset_test@pharmatrust.vn",
                "full_name": "User Cần Reset",
                "role": "CUSTOMER",
                "must_change_password": True,
            },
            headers=admin_headers,
        )
        assert res.status_code == 201
        user_id = res.json()["user"]["id"]
        temp_pwd1 = res.json()["temporary_password"]

        # Đăng nhập lấy access token
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "user_for_reset_test@pharmatrust.vn", "password": temp_pwd1},
        )
        assert login_res.status_code == 200
        old_access_token = login_res.json()["access_token"]
        assert login_res.json()["must_change_password"] is True

        # Xác nhận token cũ hoạt động
        old_auth_headers = {"Authorization": f"Bearer {old_access_token}"}
        me_res = client.get("/api/v1/auth/me", headers=old_auth_headers)
        assert me_res.status_code == 200

        # Admin thực hiện Đặt lại mật khẩu
        reset_res = client.post(
            f"/api/v1/users/{user_id}/reset-password",
            json={},
            headers=admin_headers,
        )
        assert reset_res.status_code == 200
        reset_data = reset_res.json()
        assert reset_data["must_change_password"] is True
        assert len(reset_data["temporary_password"]) >= 8
        assert "password_hash" not in reset_data

        # Kiểm tra token cũ BỊ THU HỒI NGAY LẬP TỨC (token_version đã tăng)
        revoked_check = client.get("/api/v1/auth/me", headers=old_auth_headers)
        assert revoked_check.status_code == 401, "Token cũ phải bị thu hồi sau khi reset password"

    def test_08_manager_reset_password_own_staff(self, client, manager_hcm_headers):
        """8. Quản lý kho đặt lại mật khẩu cho nhân viên kho mình: Thành công."""
        # Tạo nhân viên kho HCM
        create_res = client.post(
            "/api/v1/users",
            json={
                "email": "staff_reset_me@pharmatrust.vn",
                "full_name": "Nhân Viên Thuộc Kho HCM",
                "role": "WAREHOUSE_STAFF",
                "must_change_password": True,
            },
            headers=manager_hcm_headers,
        )
        assert create_res.status_code == 201
        staff_id = create_res.json()["user"]["id"]

        # Reset password
        reset_res = client.post(
            f"/api/v1/users/{staff_id}/reset-password",
            json={},
            headers=manager_hcm_headers,
        )
        assert reset_res.status_code == 200
        assert reset_res.json()["must_change_password"] is True
        assert len(reset_res.json()["temporary_password"]) >= 8

    def test_09_manager_cannot_reset_other_warehouse_staff(
        self, client, admin_headers, manager_hcm_headers
    ):
        """9. Quản lý kho đặt lại mật khẩu cho nhân viên kho khác: Bị từ chối (403)."""
        # Tạo nhân viên kho 2 (Hà Nội)
        create_res = client.post(
            "/api/v1/users",
            json={
                "email": "hn_staff_safe@pharmatrust.vn",
                "full_name": "Nhân Viên Thuộc Kho HN An Toàn",
                "role": "WAREHOUSE_STAFF",
                "warehouse_id": 2,
                "must_change_password": True,
            },
            headers=admin_headers,
        )
        assert create_res.status_code == 201
        hn_staff_id = create_res.json()["user"]["id"]

        # Quản lý HCM cố reset password -> 403
        reset_res = client.post(
            f"/api/v1/users/{hn_staff_id}/reset-password",
            json={},
            headers=manager_hcm_headers,
        )
        assert reset_res.status_code == 403, f"Expected 403 but got {reset_res.status_code}"

    def test_10_login_must_change_password_flag(self, client, admin_headers):
        """10. Đăng nhập với must_change_password = true: Trả cờ yêu cầu đổi mật khẩu."""
        res = client.post(
            "/api/v1/users",
            json={
                "email": "must_change_flag_check@pharmatrust.vn",
                "full_name": "Flag Check User",
                "role": "CUSTOMER",
                "must_change_password": True,
            },
            headers=admin_headers,
        )
        assert res.status_code == 201
        temp_pwd = res.json()["temporary_password"]

        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "must_change_flag_check@pharmatrust.vn", "password": temp_pwd},
        )
        assert login_res.status_code == 200
        payload = login_res.json()
        assert payload["must_change_password"] is True
        assert payload["user"]["must_change_password"] is True

    def test_11_change_password_clears_flag(self, client, admin_headers):
        """11. Đổi mật khẩu thành công: must_change_password trở về false."""
        res = client.post(
            "/api/v1/users",
            json={
                "email": "password_change_flow@pharmatrust.vn",
                "full_name": "Flow User",
                "role": "CUSTOMER",
                "must_change_password": True,
            },
            headers=admin_headers,
        )
        assert res.status_code == 201
        temp_pwd = res.json()["temporary_password"]

        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "password_change_flow@pharmatrust.vn", "password": temp_pwd},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Gọi change-password với mật khẩu mới đạt chuẩn
        change_res = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": temp_pwd,
                "new_password": "NewSecurePassword@2026!",
            },
            headers=headers,
        )
        assert change_res.status_code == 200

        # Đăng nhập lại bằng mật khẩu mới
        new_login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "password_change_flow@pharmatrust.vn", "password": "NewSecurePassword@2026!"},
        )
        assert new_login_res.status_code == 200
        new_data = new_login_res.json()
        assert new_data["must_change_password"] is False
        assert new_data["user"]["must_change_password"] is False

    def test_12_no_api_leaks_password_hash(self, client, admin_headers):
        """12. Tuyệt đối không có API nào trả password_hash."""
        # Kiểm tra danh sách người dùng
        users_res = client.get("/api/v1/users", headers=admin_headers)
        assert users_res.status_code == 200
        users = users_res.json()
        assert len(users) > 0
        for u in users:
            assert "password_hash" not in u
            assert "password" not in u
            assert "display_password" not in u

        # Kiểm tra chi tiết người dùng
        detail_res = client.get(f"/api/v1/users/{users[0]['id']}", headers=admin_headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert "password_hash" not in detail
        assert "password" not in detail
        assert "display_password" not in detail

        # Kiểm tra endpoint /me
        me_res = client.get("/api/v1/auth/me", headers=admin_headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert "password_hash" not in me_data
        assert "password" not in me_data
        assert "display_password" not in me_data
