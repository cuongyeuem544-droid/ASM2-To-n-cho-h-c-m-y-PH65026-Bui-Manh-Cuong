# H4CARE – BÁO CÁO KIỂM TOÁN TỔNG THỂ HỆ THỐNG (MASTER SYSTEM AUDIT)
**Mã dự án:** H4CARE E-Pharmacy Platform  
**Phiên bản kiểm toán:** Final Master Release  
**Mức độ ưu tiên:** P0 – CRITICAL  
**Ngày thực hiện:** 15/10/2026  
**Thẩm định viên:** Hệ thống Kiểm toán Antigravity Core Lead  

---

## I. TỔNG QUAN HỆ THỐNG & ĐỐI CHIẾU BASELINE

### 1.1. Hiện trạng Workspace & Git
- **Repository URL:** `https://github.com/hunglai1h3-source/du-an-website-ban-thuoc-`
- **Git Branch:** `main`
- **Baseline Commit:** `1267529c` (Đã đồng bộ với remote `origin/main`).
- **Quy tắc tuân thủ nghiệm thu:**
  - `apps/web` (Giao diện Quản trị viên): **0 CHỈNH SỬA TRỰC TIẾP**. Toàn bộ tính năng mở rộng quản lý kho và xử lý hàng hoàn được đóng gói nguyên trạng dưới dạng tệp `patches/admin_warehouse_integration.patch` kèm hợp đồng tích hợp `ADMIN_INTEGRATION_CONTRACT.md`.
  - Phân hệ Xác thực (`/login`, `/register`): Giữ nguyên trạng thái bảo mật khóa cứng.
  - Cơ sở dữ liệu vận hành (`pharmatrust.db`): Bảo tồn nguyên vẹn 100%, không phát sinh thao tác `DROP TABLE`, `DELETE` hay reset dữ liệu.
  - Remote Repository: Không tự ý `git push`, giữ nguyên trạng thái nghiệm thu trên local workspace.

### 1.2. Kiến trúc & Công nghệ Đang Vận Hành
| Phân hệ | Công nghệ | Cổng / Môi trường | Trách nhiệm & Phạm vi |
| :--- | :--- | :--- | :--- |
| **Backend API** | FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite (WAL mode) | `http://localhost:8000` | Điều phối nghiệp vụ, tính toán đơn giá, FEFO, phân bổ kho, FSM kiện hàng, bảo mật Anti-IDOR. |
| **Storefront** | Next.js 14 (App Router), React 18, Tailwind CSS, TypeScript | `http://localhost:3000` | Trải nghiệm mua sắm dược phẩm cho khách hàng, tra cứu thuốc, thanh toán, quản lý đơn hàng. |
| **Admin Dashboard** | React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons | `http://localhost:5173` | Giao diện dành cho Dược sĩ GSP và Quản trị viên điều phối kho, xử lý hoàn trả. |
| **Operational DB** | SQLite3 (`pharmatrust.db`) | Local File | Lưu trữ 207 danh mục thuốc quốc gia, 191 SKUs, 221 lô nhập kho GSP. |

---

## II. KẾT QUẢ KIỂM TOÁN TỪNG PHÂN HỆ NGHIỆP VỤ

### 2.1. Module A – Tìm Kiếm & Tra Cứu Dược Thư (Search Experience)
- **Tình trạng trước sửa:**
  - Khung tìm kiếm trên Storefront có kích thước nhỏ (`max-w-md`), chưa đạt tiêu chuẩn nhận diện thương hiệu dược phẩm (chuẩn Long Châu 680px – 900px).
  - Thiếu hàng tìm kiếm độc lập trên thiết bị di động (Mobile).
  - Khi API tìm kiếm gặp lỗi hoặc timeout, giao diện có nguy cơ fallback sang dữ liệu mock (`PRODUCTS_DATA`) gây sai lệch tồn kho và danh mục.
- **Biện pháp xử lý & Tình trạng sau sửa:**
  - Mở rộng container tìm kiếm lên `max-w-3xl xl:max-w-4xl` với chiều cao nút chuẩn `54px`, bổ sung nút "Tìm kiếm" gradient màu xanh y tế nổi bật.
  - Bổ sung thanh tìm kiếm chuyên dụng trên thiết bị di động (`pt-2 pb-0.5 md:hidden`).
  - Gỡ bỏ hoàn toàn fallback dữ liệu tĩnh trong catch-block; hiển thị rõ ràng thông báo trạng thái "Đang tra cứu từ Dược thư Quốc gia..." và cảnh báo lỗi kết nối minh bạch nếu mạng gián đoạn.

### 2.2. Module B – Chi Tiết Sản Phẩm & Thẩm Định Mở Bán (Product Detail & Multi-SKU)
- **Tình trạng kiểm toán:**
  - Bảng `canonical_products` và `product_skus` vận hành đúng chuẩn: Thuốc chỉ mở bán (`publish_mode = 'SALE_ELIGIBLE'`) khi thỏa mãn đồng thời:
    1. Có số đăng ký Cục Quản lý Dược hợp lệ.
    2. Không phải thuốc kê đơn (Rx) nếu chưa có luồng kiểm duyệt đơn thuốc.
    3. Có lô kho vật lý hợp lệ (`status = 'ACTIVE'`, hạn sử dụng còn trên 180 ngày).
  - Loại bỏ hoàn toàn mã barcode ngẫu nhiên tự tạo (`TEST-BARCODE-xxx`) và số đăng ký giả lập (`VD-{id}-22`).

### 2.3. Module C – Giỏ Hàng, Đặt Hàng & Thẩm Quyền Giá (Commercial Cart & Checkout)
- **Tình trạng trước sửa:**
  - Trong `apps/storefront/src/app/cart/page.tsx`, tồn tại `mockMap` ("prod-01" $\rightarrow$ 17) gây lệch định danh sản phẩm khi thêm từ danh mục mẫu.
  - Client có thể gửi `shipping_fee` tùy ý mà máy chủ chưa chặn giá trị âm, `NaN` hoặc `Infinity`.
  - Chưa áp đặt cứng ngưỡng miễn phí vận chuyển tại máy chủ nếu client gửi lệch.
  - Khi MoMo trả về URL redirect, tham số `&token=` chứa Guest Order Token bị gắn vào query string, làm lộ token vào lịch sử trình duyệt và server log bên thứ ba.
- **Biện pháp xử lý & Tình trạng sau sửa:**
  - Xóa bỏ 100% `mockMap`. Client chỉ được phép gửi `product_id` nguyên vẹn từ cơ sở dữ liệu.
  - Máy chủ kiểm tra nghiêm ngặt `shipping_fee`: Bác bỏ ngay lập tức (HTTP 400) mọi giá trị âm, `NaN`, hoặc vô hạn.
  - Backend toàn quyền quyết định phí giao hàng: Tự động áp dụng 0đ nếu đơn hàng $\ge 300.000$đ hoặc khách chọn Nhận tại nhà thuốc (`STORE_PICKUP`).
  - Xóa bỏ việc đính kèm `&token=` vào URL MoMo `returnUrl`. Token của khách vãng lai được lưu an toàn trong `localStorage` và chuyển qua HTTP Header `X-Order-Token`.

### 2.4. Phân Hệ Quản Lý Kho & FEFO (Warehouse, Batch & Reservation Engine)
- **Cơ chế điều phối:**
  - Khi đơn hàng được tạo, `route_and_allocate_order` định vị kho gần nhất có sẵn hàng dựa trên tính toán khoảng cách tọa độ Haversine.
  - Thuật toán FEFO (First-Expired, First-Out) tự động quét và phân bổ các lô có hạn dùng gần nhất (`expiry_date` tăng dần).
  - Tồn kho được khóa giữ chỗ tạm thời (`StockReservation`) với trạng thái `HELD` trong 30 phút, ngăn chặn tuyệt đối tình trạng Overselling (bán vượt quá tồn thực).
  - Tự động sinh `OrderFulfillment` cho từng kho tương ứng kèm mã kiện hàng và mã vận đơn tracking.

### 2.5. Phân Hệ Tiếp Nhận & Xử Lý Hàng Hoàn (Warehouse Returns & Restock FSM)
- **Chu trình xử lý hoàn tiền / đổi trả:**
  1. Khách hàng tạo yêu cầu hoàn trả (`POST /returns/request`).
  2. Quản trị viên/Dược sĩ phê duyệt hồ sơ (`APPROVED`).
  3. Kiện hàng chuyển về kho vật lý $\rightarrow$ Dược sĩ kho xác nhận tiếp nhận (`POST /admin/returns/{id}/receive` $\rightarrow$ `RECEIVED_AT_WAREHOUSE`).
  4. Dược sĩ kiểm nghiệm chất lượng sản phẩm (`POST /admin/returns/{id}/inspect`):
     - `RESTOCK`: Thuốc đạt chuẩn $\rightarrow$ Hoàn trả tồn `quantity_on_hand` và `quantity_available` vào chính kho ban đầu; ghi thẻ kho `RETURN_RESTOCK`.
     - `QUARANTINE`: Cần theo dõi hoặc kiểm nghiệm thêm $\rightarrow$ Đưa vào khu vực biệt trữ.
     - `DISPOSE`: Hàng hỏng/vỡ $\rightarrow$ Lập biên bản tiêu hủy, không cộng tồn kho bán lẻ.

---

## III. KIỂM TOÁN AN TOÀN BẢO MẬT (SECURITY AUDIT)

### 3.1. Chống IDOR & Bảo Vệ Khách Vãng Lai (Guest Ownership Protection)
- **Cơ chế Token Mật mã học:**
  - Token khách vãng lai được sinh bằng HMAC-SHA256 kết hợp mã đơn hàng, số điện thoại đã chuẩn hóa và Secret Salt của hệ thống.
  - Token có thời hạn hợp lệ 48 giờ (`exp: 172800s`).
  - Chặn đứng lỗ hổng dò số điện thoại: Chỉ cung cấp số điện thoại sẽ bị từ chối `HTTP 403 Forbidden`. Bắt buộc phải có token mật mã hợp lệ trong Header `X-Order-Token`.
- **Bảo Vệ Tái Sử Dụng Idempotency Key (Idempotency Replay Anti-IDOR):**
  - Kẻ tấn công thử gửi lại một `idempotency_key` đã tồn tại của người khác nhưng dùng số điện thoại của mình sẽ bị máy chủ phát hiện và chặn đứng ngay với `HTTP 403 Forbidden` (*"Idempotency key này không thuộc về số điện thoại hoặc tài khoản của bạn"*), ngăn chặn rò rỉ token hoặc lộ dữ liệu đơn hàng cũ.

### 3.2. Cấu Hình CORS & Header Bảo Mật
- Loại bỏ hoàn toàn regex bắt lỏng lẻo `allow_origin_regex=r"^https?://.*"`.
- Giới hạn cứng danh sách Origin hợp lệ: `http://localhost:3000`, `http://localhost:5173`, `http://127.0.0.1:3000`, `http://127.0.0.1:5173`.
- Bổ sung các custom header an toàn vào danh sách `allow_headers`: `Authorization`, `Content-Type`, `X-Order-Token`, `X-Idempotency-Key`.

### 3.3. Cơ Chế Fail-Closed Đối Với Thanh Toán & Secrets
- `is_simulator_permitted` được thiết lập mặc định `False` khi triển khai production hoặc staging (`APP_ENV != 'local'`). Bất kỳ yêu cầu gọi endpoint mô phỏng nào đều bị từ chối `HTTP 403 Fail-Closed`.
- Trong `momo_service.py`, loại bỏ fallback tự tạo URL `SimulatedSuccess`. Khi MoMo Gateway không phản hồi hoặc trả lỗi, hệ thống trả về `HTTP 502 Bad Gateway` và ghi nhận giao dịch `FAILED`, bảo đảm tính trung thực tài chính.

---

## IV. TỔNG KẾT ĐÁNH GIÁ CHUNG

| Tiêu chuẩn kiểm toán | Hiện trạng | Kết luận |
| :--- | :--- | :--- |
| **Tính toàn vẹn Dữ liệu** | 207 Thuốc, 191 SKUs, 221 Lô GSP bảo toàn 100%, PRAGMA `ok` | **PASS** |
| **Thẩm quyền Giá & Phí** | 100% Phí giao hàng, Giảm giá và Tổng tiền do Backend quyết định | **PASS** |
| **Bảo mật & Chống IDOR** | HMAC Token, Xác thực Idempotency, CORS Whitelist | **PASS** |
| **Kho & Điều phối FEFO** | Tự động phân bổ, xuất đúng hạn dùng, FSM kiện hàng chuẩn hóa | **PASS** |
| **Xử lý Đổi trả & Nhập hoàn** | FSM tiếp nhận kho, phân loại GSP Restock / Quarantine / Dispose | **PASS** |
| **Tương thích Giao diện Admin** | Đóng gói Patch sạch, không sửa mã nguồn bị khóa `apps/web` | **PASS** |
| **Độ phủ Kiểm thử** | 324/324 Backend Tests PASS, 16/16 Next.js Pages Build PASS | **PASS** |
