# H4CARE / PharmaTrust - Quy Chuẩn Kỹ Thuật & Bộ Nhớ Lỗi (Error Memory & Engineering Rules)

Tài liệu này được hệ thống tự động ghi nhớ và tuân thủ tuyệt đối cho mọi phiên làm việc tiếp theo của dự án H4CARE/PharmaTrust.

---

## 1. NGUYÊN TẮC BẮT BUỘC TỔNG THỂ

1. **Không đoán tên file, API, database, trạng thái**: Luôn đọc mã nguồn thực tế và kiểm tra trước khi sửa.
2. **Bảo toàn giao diện & nghiệp vụ Admin**: Không thay đổi layout, menu, quyền hạn hay luồng hoạt động của Admin.
3. **Phân quyền Đa kho (RBAC)**:
   - `ADMIN`: Toàn quyền hệ thống, mọi kho.
   - `WAREHOUSE_MANAGER`: Chỉ thuộc 1 kho, chỉ xem và quản lý dữ liệu/nhân viên thuộc đúng `warehouse_id` của mình. Chặn tuyệt đối việc can thiệp chéo kho.
   - `WAREHOUSE_STAFF`: Chỉ thực thi các tác vụ vận hành được giao trong kho của mình.
   - `CUSTOMER` / `BUYER`: Khách hàng mua sắm storefront.
4. **Bảo mật thông tin & Mật khẩu**:
   - Tuyệt đối không lưu hoặc hiển thị mật khẩu dạng plain text. Không trả `password_hash` về frontend/API.
   - Mật khẩu tạm thời chỉ hiển thị **1 lần duy nhất** sau khi tạo/reset kèm nút copy.
   - Bắt buộc đổi mật khẩu ở lần đăng nhập tiếp theo (`must_change_password = True`).
5. **Kiểm thử trước khi bàn giao**:
   - Chạy `npm run build` trên `apps/web` (0 TypeScript errors).
   - Chạy `pytest` trên `apps/api` (0 lỗi API/DB).

---

## 2. BỘ NHỚ CÁC LỖI ĐÃ XẢY RA VÀ QUY TẮC PHÒNG NGỪA (LESSONS LEARNED)

### 🔴 Lỗi 1: "Method Not Allowed" (405) / Lỗi kết nối khi cập nhật đơn hàng kho
- **Triệu chứng**: Khi bấm nút "Bàn giao" trên trang Đơn hàng kho (`/warehouse/orders`), trình duyệt báo lỗi `localhost:5173 says: Method Not Allowed` hoặc "lỗi kết nối máy chủ".
- **Nguyên nhân**:
  1. Frontend gọi `PATCH /api/v1/warehouse-portal/orders/{id}/status`, nhưng router backend chỉ đăng ký `/fulfillment`.
  2. Tiến trình FastAPI backend chạy không có cờ `--reload`, dẫn đến việc sửa code nhưng máy chủ không tự nạp vào bộ nhớ.
- **Quy tắc phòng ngừa**:
  1. Luôn khai báo endpoint có tính tương thích ngược: hỗ trợ cả route alias `@router.patch("/orders/{order_id}/status")` và `@router.patch("/orders/{order_id}/fulfillment")`.
  2. Luôn hỗ trợ cả 2 tham số payload: `status` và `fulfillment_status`.
  3. Khởi động server backend luôn dùng cờ `--reload` (`uvicorn app.main:app --app-dir apps\api --host 0.0.0.0 --port 8000 --reload`).
  4. Sau khi sửa API, luôn kiểm tra `openapi.json` để xác minh endpoint đã thực sự active trong RAM.

---

### 🔴 Lỗi 2: Lệch cổng và rò rỉ tiến trình trên môi trường Windows
- **Triệu chứng**: Gặp lỗi cổng bị chiếm dụng (8000, 5173, 3000) hoặc kết nối bị từ chối do tiến trình cũ vẫn giữ socket.
- **Nguyên nhân**: Quản lý task nền không dọn dẹp tiến trình cũ trước khi khởi động mới.
- **Quy tắc phòng ngừa**:
  1. Trước khi chạy dịch vụ mới, kiểm tra task list hoặc kill task cũ đúng cách.
  2. Đảm bảo cổng Backend luôn là `:8000`, Cổng Web Admin/Kho luôn là `:5173`, Cổng Storefront luôn là `:3000`.

---

### 🔴 Lỗi 3: Truy vấn chéo kho hoặc lộ thông tin kho khác
- **Triệu chứng**: Quản lý kho có thể thấy hoặc chỉnh sửa nhân viên/đơn hàng/lô thuốc của kho khác nếu không chặn ID.
- **Nguyên nhân**: Thiếu bộ lọc `warehouse_id` hoặc thiếu kiểm tra quyền sở hữu trong các hàm update/delete.
- **Quy tắc phòng ngừa**:
  1. Mọi truy vấn của Quản lý kho bắt buộc phải gắn điều kiện lọc `warehouse_id = current_user.warehouse_id`.
  2. Tại mọi endpoint thao tác trên một bản ghi cụ thể (theo `id`), bắt buộc kiểm tra xem bản ghi đó có thuộc `warehouse_id` của người dùng hay không; nếu không, trả về HTTP `403 Forbidden` ngay lập tức.

---

### 🔴 Lỗi 4: Lỗi nhật ký kho (Warehouse Audit Log) và Ghi nhận vết
- **Triệu chứng**: Lịch sử hoạt động kho bị trống hoặc thiếu phân loại hành động.
- **Nguyên nhân**: Thiếu gọi service ghi audit log khi thực hiện các nghiệp vụ: nhập kho, kiểm kê, điều chỉnh tồn kho, đổi trạng thái đơn, đổi mật khẩu nhân viên.
- **Quy tắc phòng ngừa**:
  1. Mọi thao tác can thiệp dữ liệu trong kho đều phải tạo một bản ghi Audit Log chứa: `user_id`, `warehouse_id`, `action`, `entity_name`, `entity_id`, `details`, `timestamp`.

---

### 🔴 Lỗi 5: Lỗi 500 khi bấm "Phiếu Soạn" (Pick Details) do sai tên thuộc tính Model ORM
- **Triệu chứng**: Khi bấm nút "Phiếu Soạn" ở trang Đơn hàng kho (`/warehouse/orders`), hệ thống báo lỗi không có phản hồi hoặc không mở được modal.
- **Nguyên nhân**:
  1. Endpoint `get_order_picking_details` cố truy cập `item.sku_id`, `item.unit_price`, `item.line_total` trên model `OrderItem` (trong khi thực tế model có `item.product_id`, `item.product_sku`, `item.price`, `item.subtotal`).
  2. Truy cập `sku.unit_name` và `sku.product_id` trên `ProductSku` (trong khi thực tế là `sku.uom` và `sku.canonical_product_id`).
  3. Lọc FEFO sai logic làm loại bỏ các lô thuốc sắp hết hạn cần ưu tiên xuất trước.
- **Quy tắc phòng ngừa**:
  1. Tuyệt đối không đoán tên thuộc tính ORM/Entity. Phải mở `entities.py` hoặc `inventory.py` để tra cứu đúng schema trước khi truy xuất.
  2. Mọi endpoint trả về chi tiết (như Picking Slip) phải có test case tự động bao phủ trong `test_multi_warehouse_rbac_comprehensive.py`.
  3. Frontend luôn cung cấp phản hồi trực quan: nút hiển thị "Đang mở…" và hiển thị rõ huy hiệu trạng thái khi đơn đã bàn giao (SHIPPED / DELIVERED).

---

### 🔴 Lỗi 6: Sai thuộc tính ORM trên CanonicalProduct và ProductIngredient
- **Triệu chứng**: Gặp lỗi `AttributeError: type object 'CanonicalProduct' has no attribute 'primary_image_url'` hoặc `'ProductIngredient' object has no attribute 'ingredient_name'`.
- **Nguyên nhân**:
  1. `CanonicalProduct` dùng `image_url`, `route`, `manufacturing_country`, `rx_otc_status` (không có `primary_image_url`, `route_of_administration`, `country_of_origin`).
  2. `ProductIngredient` là bảng liên kết nối với `Ingredient`, tên hoạt chất nằm ở `ing.ingredient.normalized_name`.
- **Quy tắc phòng ngừa**:
  1. Kiểm tra chính xác file `entities.py` trước khi thực hiện `select()` hoặc map dict.
  2. Dùng `getattr(ing, 'ingredient', None)` và xử lý fallback chuỗi an toàn.

---

### 🔴 Lỗi 7: Đụng độ UNIQUE constraint khi sinh mã phiên nhập file và kiểm tra trùng lặp
- **Triệu chứng**: Khi tải file kiểm thử trong cùng 1 giây, backend báo lỗi `IntegrityError: UNIQUE constraint failed: warehouse_import_jobs.import_code`.
- **Nguyên nhân**: Mã `IMP-...` chỉ định dạng theo giây `%y%m%d%H%M%S` mà không có hậu tố ngẫu nhiên.
- **Quy tắc phòng ngừa**:
  1. Luôn thêm hậu tố UUID ngắn (`f"-{uuid.uuid4().hex[:4].upper()}"`) vào mọi mã sinh tự động (`import_code`, `receipt_code`, `movement_code`).
  2. Kiểm tra mã băm SHA-256 cả ở trạng thái `PREVIEW` và `COMMITTED` để cảnh báo sớm cho người dùng.

### 🔴 Lỗi 8: Lỗi lịch sử đơn hàng khách hàng rỗng và nuốt lỗi API
- **Triệu chứng**: Khách hàng đã đăng nhập đặt đơn hàng thành công, đơn có trong Admin nhưng trang “Lịch sử đơn hàng” của khách hàng trả về danh sách rỗng.
- **Nguyên nhân**:
  1. Frontend `account/page.tsx` gọi endpoint tra cứu đơn hàng qua số điện thoại `user.phone` với URL cứng `http://localhost:8000`. Khi endpoint bị vô hiệu hóa vì bảo mật PII (trả 403), frontend tự nuốt lỗi `.catch(() => setOrders([]))` làm người dùng tưởng chưa từng đặt đơn.
  2. `POST /api/v1/store/orders/checkout` dùng `get_optional_current_user` nuốt token sai/hết hạn thành `None` thay vì trả 401.
  3. Idempotency key không kiểm tra quyền sở hữu `order.user_id`, có thể dẫn đến việc đơn của tài khoản khác bị replay.
- **Quy tắc phòng ngừa**:
  1. Tuyệt đối không tra cứu lịch sử đơn hàng qua số điện thoại (SĐT nhận hàng có thể khác SĐT tài khoản). Luôn xác thực qua JWT token bằng `GET /api/v1/store/orders/me` lọc nghiêm ngặt `Order.user_id == current_user.id`.
  2. Tạo dependency `strict_optional_current_user` cho checkout: không có header -> khách vãng lai (`None`); có header nhưng token sai -> trả ngay HTTP 401 Unauthorized (không âm thầm coi là khách vãng lai).
  3. Khi replay bằng `idempotency_key`, bắt buộc kiểm tra `existing_order.user_id == req_user_id`; nếu khác, trả HTTP 409 Conflict.
  4. Frontend phải hiển thị 4 trạng thái giao diện rõ ràng (`loading`, `success-empty`, `success-data`, `error` kèm nút "Thử lại"). Tuyệt đối không nuốt lỗi mạng/401/500 thành mảng rỗng `[]`.
  5. Đối với đơn hàng cũ chưa có `user_id`, cung cấp script `link_legacy_orders.py` với cờ an toàn `--dry-run` trước khi `--commit`.

---

## 3. CHECKLIST KIỂM TRA MỖI KHI XỬ LÝ LỖI
1. [ ] Đã xác định nguyên nhân gốc rễ (Root Cause) thay vì chỉ vá phần ngọn?
2. [ ] Backend API và Frontend types đã đồng bộ 100% về tên trường và URL?
3. [ ] Server đã nạp code mới (nếu sửa Python phải kiểm tra reload, nếu sửa React phải kiểm tra Vite HMR/build)?
4. [ ] Đã chạy test tự động (`pytest` và `npm run build`) xác nhận không phát sinh lỗi phụ?
5. [ ] Đã cập nhật vấn đề và bài học vào bộ nhớ `GEMINI.md` để không lặp lại?


