# H4CARE – NHẬT KÝ DỌN DẸP MÃ NGUỒN & HẠ TẦNG (CLEANUP CHANGELOG)
**Dự án:** H4CARE Online Pharmacy Platform  
**Đợt cập nhật:** Final Master Cleanup & System Stabilization  
**Mức độ:** P0 – CRITICAL  
**Ngày hoàn tất:** 15/10/2026  

---

## I. TỔNG QUAN CÁC TỆP TIN ĐÃ THAY ĐỔI TRONG WORKSPACE

| Tệp tin | Phân hệ | Loại thay đổi | Mục đích & Rationale |
| :--- | :--- | :--- | :--- |
| `apps/api/app/api/orders.py` | Backend API | Security & Commercial Integrity | Thêm xác thực quyền sở hữu Idempotency Key (chống IDOR khi gửi trùng key); kiểm tra tính hợp lệ của `shipping_fee` (chặn âm, NaN, Infinite). |
| `apps/api/app/api/storefront.py` | Backend API | Code Hygiene & Deprecation Fix | Thay thế tham số truy vấn deprecated `regex=...` bằng `pattern=...` trong FastAPI Query, loại bỏ hoàn toàn cảnh báo (0 warnings). |
| `apps/api/app/core/config.py` | Backend Core | Security & Hardening | Cấu hình tường minh danh sách `cors_origins` (Storefront 3000 và Admin 5173 trên cả localhost và 127.0.0.1); loại bỏ nguy cơ cấu hình sai. |
| `apps/api/app/main.py` | Backend Core | Security & Hardening | Gỡ bỏ `allow_origin_regex=r"^https?://.*"` lỏng lẻo; mở rộng `allow_headers` hỗ trợ `X-Order-Token` và `X-Idempotency-Key`. |
| `apps/api/tests/test_p0_stability_regression.py` | Backend Tests | Quality Assurance | Bổ sung 4 bài test hồi quy bảo vệ P0 (test 7-10: Anti-IDOR Idempotency, chặn gian lận phí ship, ép ngưỡng miễn phí ship máy chủ, thắt chặt CORS). |
| `apps/storefront/next.config.mjs` | Storefront Config | Infrastructure | Chuyển đổi API Rewrite sang sử dụng biến môi trường linh hoạt `INTERNAL_API_URL` / `NEXT_PUBLIC_API_URL` thay vì hardcode localhost. |
| `apps/storefront/src/app/cart/page.tsx` | Storefront UI | Data Cleanliness & Security | Xóa bỏ 100% `mockMap` ("prod-01" $\rightarrow$ 17); xóa bỏ việc gắn `&token=` vào URL MoMo `returnUrl` (chống lộ token vào URL và trình duyệt). |
| `apps/storefront/src/components/layout/Header.tsx` | Storefront Layout | UI/UX Standard | Mở rộng vùng hiển thị thanh tìm kiếm trên Desktop (`max-w-3xl xl:max-w-4xl`), bổ sung hàng tìm kiếm chuyên dụng cho giao diện Mobile. |
| `apps/storefront/src/components/layout/SearchExperience.tsx` | Storefront Layout | UI/UX & Reliability | Thiết kế thanh tìm kiếm dược phẩm chuẩn (cao 54px, nút tìm kiếm gradient); xóa bỏ fallback sang dữ liệu mock tĩnh `PRODUCTS_DATA`; hiển thị trạng thái đang tra cứu từ Dược thư và thông báo lỗi rõ ràng. |
| `patches/admin_warehouse_integration.patch` | Admin Integration | Deliverable Package | Gói patch tích hợp giao diện Quản lý Kho, Kiện hàng FSM và Hàng hoàn cho Admin Dashboard mà không vi phạm quy tắc cấm sửa `apps/web`. |
| `ADMIN_INTEGRATION_CONTRACT.md` | Interface Spec | Contract Spec | Hợp đồng kỹ thuật chi tiết đặc tả Schema DB, Endpoints API và hướng dẫn áp dụng patch cho Admin lead. |

---

## II. CHI TIẾT CÁC HẠNG MỤC DỌN DẸP (CLEANUP BREAKDOWN)

### 1. Loại Bỏ Mock Data & Mapping Giả Lập (Zero Fake Data)
1. **Xóa bỏ `mockMap` trong `cart/page.tsx`:**
   - *Trước đây:* Giỏ hàng có đoạn ánh xạ dự phòng `"prod-01": 17, "prod-02": 24...`. Nếu khách hàng bấm vào một sản phẩm mẫu cũ, hệ thống tự động đổi sang ID 17.
   - *Sau khi sửa:* Loại bỏ hoàn toàn `mockMap`. Hệ thống chỉ chấp nhận ID sản phẩm thực (`dbId`) từ cơ sở dữ liệu quốc gia. Nếu sản phẩm không có ID số hợp lệ, hệ thống báo lỗi rõ ràng và yêu cầu tra cứu lại danh mục.
2. **Xóa bỏ fallback `PRODUCTS_DATA` trong `SearchExperience.tsx`:**
   - *Trước đây:* Khi kết nối API tìm kiếm bị gián đoạn, component tự động lọc từ mảng tĩnh `PRODUCTS_DATA` nội bộ, hiển thị những sản phẩm không còn tồn kho hoặc giá không đúng với DB thực tế.
   - *Sau khi sửa:* Xóa bỏ toàn bộ catch-fallback. Khi mạng lỗi, component hiển thị thông báo y tế: *"Không thể kết nối đến máy chủ tra cứu thuốc. Vui lòng thử lại sau."*
3. **Loại bỏ URL giả lập `SimulatedSuccess` trong `momo_service.py`:**
   - Khi MoMo Sandbox/Gateway gặp sự cố hoặc timeout, hệ thống trả về mã lỗi HTTP 502 và ghi nhận transaction `FAILED`. Tuyệt đối không sinh URL ảo khiến khách hàng hiểu lầm là đã thanh toán thành công.

### 2. Dọn Dẹp & Chuẩn Hóa Cấu Hình Môi Trường (Config Hygiene)
1. **Thắt chặt CORS Middleware (`main.py` & `config.py`):**
   - Loại bỏ biểu thức chính quy `allow_origin_regex=r"^https?://.*"`. Biểu thức này trước đây cho phép bất kỳ domain bên ngoài nào cũng có thể gửi request có kèm cookie/credentials đến API.
   - Giới hạn danh sách Origin hợp lệ:
     ```python
     cors_origins = [
         "http://localhost:3000",
         "http://localhost:5173",
         "http://127.0.0.1:3000",
         "http://127.0.0.1:5173",
     ]
     ```
2. **Hỗ trợ Custom Security Headers:**
   - Thêm `X-Order-Token` và `X-Idempotency-Key` vào `allow_headers` để các browser preflight requests (OPTIONS) được phản hồi hợp lệ mà không bị chặn bởi CORS policy.
3. **Cấu hình Rewrite Next.js (`next.config.mjs`):**
   - Không gắn cứng `http://localhost:8000`. Hỗ trợ biến môi trường ưu tiên:
     `process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`.

### 3. Tăng Cường Bảo Mật Nghiệp Vụ Thương Mại (Commercial & Security Hardening)
1. **Xác thực quyền sở hữu Idempotency Key (`orders.py`):**
   - Kẻ tấn công không thể sử dụng lại một idempotency key đã thành công của người khác để đánh cắp token hoặc đọc thông tin đơn hàng.
   - Nếu số điện thoại hoặc `user_id` trong payload mới không khớp với đơn hàng gốc gắn với key đó, máy chủ lập tức từ chối `HTTP 403 Forbidden`.
2. **Thẩm quyền Giá & Phí Vận Chuyển:**
   - Kiểm tra chặt chẽ `payload.shipping_fee` từ client gửi lên: Chặn mọi giá trị âm, giá trị `NaN`, hoặc `Infinity`.
   - Backend nắm toàn quyền áp đặt:
     - Đơn hàng $\ge 300.000$đ: Phí vận chuyển tự động tính bằng `0.0`đ.
     - Hình thức `STORE_PICKUP` (Nhận tại nhà thuốc): Phí vận chuyển tự động bằng `0.0`đ.
3. **Chống rò rỉ Guest Token qua URL:**
   - Trong `cart/page.tsx`, gỡ bỏ `&token=${encodeURIComponent(guestOrderToken)}` khỏi tham số `returnUrl` gửi sang MoMo.
   - Token chỉ lưu trữ trong `localStorage` trình duyệt của khách và gửi qua Header an toàn `X-Order-Token`.

### 4. Nâng Cấp Trải Nghiệm Giao Diện Người Dùng (UI/UX Alignment)
1. **Chuẩn hóa Thanh tìm kiếm Long Châu:**
   - Tăng độ rộng container từ `max-w-md` lên `max-w-3xl xl:max-w-4xl` (độ rộng thực tế 680px – 900px), chiều cao `54px`.
   - Nút tìm kiếm nổi bật với gradient màu xanh dương thương hiệu (`from-brand-blue-600 to-brand-blue-700`).
   - Bổ sung thanh tìm kiếm độc lập trên thiết bị di động (Mobile Search Row) nằm ngay dưới thanh tiêu đề chính.
2. **Hiển thị trạng thái tương tác trực quan:**
   - Khi đang gõ phím: Hiển thị spinner kèm văn bản *"Đang tra cứu từ Dược thư Quốc gia..."*.
   - Khi không tìm thấy: Hiển thị hướng dẫn tra cứu chi tiết với hoạt chất hoặc số đăng ký.
   - Khi gặp sự cố mạng: Hiển thị icon cảnh báo và thông báo lỗi rõ ràng, không treo giao diện.
