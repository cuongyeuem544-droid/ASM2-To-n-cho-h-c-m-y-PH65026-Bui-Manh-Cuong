# H4CARE – BÁO CÁO RỦI RO CÒN LẠI & PHỤ THUỘC MÔI TRƯỜNG (REMAINING RISKS & DEPENDENCIES)
**Mã dự án:** H4CARE Online Pharmacy  
**Phiên bản:** Master Release 1.0  
**Mức độ:** P0 – CRITICAL  
**Ngày phát hành:** 15/10/2026  
**Đơn vị thẩm định:** Antigravity System Audit Lead  

---

## I. MỤC ĐÍCH BÁO CÁO
Báo cáo này cung cấp cái nhìn trung thực, khách quan và minh bạch về toàn bộ các **yếu tố rủi ro còn lại**, các **phụ thuộc vào bên thứ ba (External Dependencies)**, và các **hướng dẫn vận hành bắt buộc** trước khi đưa hệ thống H4CARE vào khai thác thương mại chính thức.

---

## II. DANH MỤC PHỤ THUỘC BÊN NGOÀI (EXTERNAL DEPENDENCIES)

### 1. Dịch Vụ Gửi Email (SMTP Gateway)
- **Hiện trạng nội bộ:**
  - Toàn bộ các bài kiểm thử tự động (Unit & Integration tests) sử dụng `MockSMTPClient` và cơ chế `EmailOutbox` đều đạt **100% PASS**.
  - Kiểm thử mô phỏng chứng minh logic tạo nội dung email xác nhận đơn hàng, email OTP và thông báo hoàn tiền hoạt động hoàn toàn chính xác.
- **Rủi ro môi trường thực:**
  - Việc kiểm thử Mock PASS **không đồng nghĩa** với việc email thật đã được gửi đến hòm thư người dùng thực tế nếu chưa cấu hình thông tin xác thực SMTP của nhà cung cấp bên ngoài.
- **Biện pháp vận hành cần thiết:**
  - Khi triển khai môi trường Production/Staging, quản trị viên cần thiết lập biến môi trường trong file `.env`:
    ```env
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=no-reply@h4care.vn
    SMTP_PASSWORD=<Google-App-Password-16-ký-tự>
    SMTP_FROM="H4CARE Pharmacy <no-reply@h4care.vn>"
    ```

### 2. Cổng Thanh Toán MoMo & VietQR
- **Hiện trạng nội bộ:**
  - Cơ chế thanh toán đã được khóa chặt theo nguyên tắc **Fail-Closed**: Loại bỏ hoàn toàn việc tự sinh URL thành công ảo `SimulatedSuccess` khi cổng thanh toán gặp sự cố; chặn đứng mọi endpoint giả lập trên môi trường Production (`is_simulator_permitted = False`).
  - Đã có cơ chế dò trạng thái thanh toán và giải phóng tồn kho treo (`StockReservation`) tự động sau 30 phút.
- **Rủi ro môi trường thực:**
  - Khóa API MoMo hiện tại trong file cấu hình dev là thông tin Test Sandbox. Khi người dùng thực thanh toán bằng tiền thật, giao dịch sẽ không thể hoàn tất nếu chưa ký hợp đồng thương mại với MoMo và VietQR Gateway.
- **Biện pháp vận hành cần thiết:**
  - Đăng ký tài khoản MoMo Doanh nghiệp chính thức để nhận: `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY`.
  - Cập nhật webhook IP whitelist và cấu hình SSL HTTPS công khai để nhận MoMo IPN callbacks.

### 3. Dịch Vụ Định Vị Địa Lý & Chuẩn Hóa Địa Chỉ (Places & OSM Service)
- **Hiện trạng nội bộ:**
  - Bộ đệm xác định tọa độ (`PlacesCache`) và thuật toán gán mã hành chính hoạt động tất định (Deterministic 100% PASS), định vị chính xác khoảng cách địa lý đến Kho TP.HCM hoặc Kho Hà Nội.
- **Rủi ro môi trường thực:**
  - Nếu khách hàng nhập địa chỉ mới chưa từng xuất hiện trong cache cục bộ mà máy chủ mất kết nối Internet quốc tế đến OpenStreetMap / Nominatim, hệ thống sẽ fallback về tọa độ trung tâm quận/huyện.
- **Biện pháp vận hành cần thiết:**
  - Xem xét tích hợp thêm Google Maps Geocoding API hoặc VietMap API Key vào biến môi trường để tối ưu hóa độ chính xác định vị cho các ngõ hẻm vùng sâu vùng xa.

---

## III. HIỆN TRẠNG TÍCH HỢP GIAO DIỆN QUẢN TRỊ (ADMIN UI INTEGRATION)

### 1. Cam Kết Ranh Giới Dự Án
- Tuân thủ nghiêm ngặt yêu cầu của Dự án: **0 CHỈNH SỬA TRỰC TIẾP VÀO THƯ MỤC `apps/web`** (do Admin lead phụ trách riêng).
- Toàn bộ các API mới phục vụ quản lý kho (`/admin/warehouses/{id}/fulfillments`), FSM kiện hàng (`/admin/orders/fulfillments/{id}/status`), tiếp nhận hàng hoàn (`/admin/returns/{id}/receive`) và kiểm nghiệm GSP (`/admin/returns/{id}/inspect`) đã được xây dựng hoàn tất trên Backend và kiểm thử 100% PASS.

### 2. Trạng Thái Nghiệm Thu Admin UI
- **Trạng thái ghi nhận:** `BACKEND READY – ADMIN INTEGRATION PENDING`.
- **Gói tích hợp sẵn sàng:**
  - Tệp Patch: `patches/admin_warehouse_integration.patch` (Đã xác minh tính tương thích: `git apply --check` trả về mã 0).
  - Hợp đồng tích hợp: `ADMIN_INTEGRATION_CONTRACT.md`.
- **Hành động bàn giao:**
  - Admin Lead chỉ cần thực hiện 2 lệnh đơn giản trên máy của mình:
    ```bash
    git apply patches/admin_warehouse_integration.patch
    npm --prefix apps/web run build
    ```
  - Sau khi apply, giao diện Quản lý Kho sẽ lập tức hiển thị đầy đủ danh sách kiện hàng cần xuất kho và hàng đổi trả cần kiểm nghiệm.

---

## IV. QUY TRÌNH KHUYẾN NGHỊ VẬN HÀNH & GIÁM SÁT (OPERATIONAL PLAYBOOK)

1. **Khởi động Môi trường An toàn:**
   - Đảm bảo biến môi trường `APP_ENV=production` được bật.
   - Khởi tạo chuỗi bí mật `SECRET_KEY` và `JWT_SECRET_KEY` ngẫu nhiên tối thiểu 64 ký tự bằng lệnh:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(64))"
     ```
2. **Cron Job Giải Phóng Tồn Treo:**
   - Thiết lập lịch định kỳ (mỗi 10 phút) gọi API nội bộ bằng token Admin/Pharmacist:
     `POST /api/v1/payments/reservations/stale/release`
     để tự động thu hồi tồn kho cho những đơn hàng khách bỏ giỏ hoặc không thanh toán quá 30 phút.
3. **Sao Lưu Cơ Sở Dữ Liệu:**
   - Cơ sở dữ liệu `pharmatrust.db` đang chạy chế độ SQLite WAL (Write-Ahead Logging). Thực hiện sao lưu định kỳ hàng ngày bằng công cụ sao lưu an toàn của SQLite (tránh copy trực tiếp khi đang ghi):
     ```bash
     sqlite3 pharmatrust.db ".backup 'backups/pharmatrust_$(date +%Y%m%d).db'"
     ```
