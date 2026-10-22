# BÁO CÁO KIỂM TOÁN CHẤT LƯỢNG SẢN PHẨM & CẢI TIẾN HỆ THỐNG H4CARE
## H4CARE PRODUCTION QUALITY AUDIT & SYSTEM HARDENING REPORT

- **Dự án**: H4CARE Premium Online Pharmacy (Đồ án tốt nghiệp Dược - CNTT)
- **Phiên bản mã nguồn**: Sau kiểm toán commit `1b1d612`
- **Nhánh thực hiện**: `feature/p0-audit-and-data-hardening`
- **Thời gian lập**: 22/10/2026
- **Tiêu chuẩn áp dụng**: 
  - Luật Dược 2016 & Thông tư 02/2018/TT-BYT (Thực hành tốt nhà thuốc - GPP).
  - Tôn chỉ kỹ thuật: **LÀM ĐÂU KỸ ĐẤY. KHÔNG FAKE SUCCESS. KHÔNG DỮ LIỆU GIẢ. KIỂM THỬ ĐẦY ĐỦ.**

---

## 1. TỔNG QUAN KẾT QUẢ XỬ LÝ CÁC NHIỆM VỤ P0 & P1

| Mã | Nhiệm Vụ | Trạng Thái | File Can Thiệp | Kết Quả Kiểm Thử |
|:---:|---|:---:|---|---|
| **P0-01** | Sửa triệt để Modal Tư Vấn Toa Rx (`RxConsultModal`) | **HOÀN THÀNH** | `apps/storefront/src/components/product/RxConsultModal.tsx`, `apps/storefront/src/app/api/prescription/consult/route.ts` | Next.js Build Pass; validate MIME/kích thước thật, gửi API thật, không fake success |
| **P0-02** | Rà soát & gỡ bỏ tệp nhạy cảm trong Git | **HOÀN THÀNH** | `.gitignore`, index Git (`apps/storefront/storage/test-prescriptions/`, `pharmatrust.db.bak*`) | 11 tệp đơn thuốc test và 5 tệp sqlite backup đã gỡ khỏi git index mà không rewrite lịch sử commit cũ |
| **P0-03** | Chiến lược lưu trữ đơn thuốc bền vững | **HOÀN THÀNH** | `apps/storefront/src/lib/prescription/storage.ts` | Tích hợp bộ điều hợp chuẩn S3/Cloudflare R2 (SigV4) + cơ chế tự động chuyển hướng `/tmp` trên Serverless (Vercel) kèm cảnh báo vòng đời |
| **P0-04** | Tách bạch `FORMAT_VALID` & `OFFICIALLY_VERIFIED`, loại bỏ regex bắt tự do | **HOÀN THÀNH** | `apps/api/app/services/product_eligibility_service.py` | 13/13 unit test pass; chỉ SĐK có đối chiếu `RegulatoryRecord` mới gắn cờ `OFFICIALLY_VERIFIED`; xóa hoàn toàn fallback `PriceObservation` vào `base_price` |
| **P0-05** | Dọn sạch chuỗi placeholder dược phẩm & kiểm soát Rx | **HOÀN THÀNH** | `apps/api/app/api/storefront.py` | Loại bỏ `"Viên nén"`, `"PharmaTrust Hợp Tác"`, `"PharmaTrust"`; khóa bán Rx (`is_sale_eligible = False`); bổ sung API `POST /prescriptions/consult` |
| **P1-01** | Phân trang, sắp xếp & facet lọc phía máy chủ trang Danh mục | **HOÀN THÀNH** | `apps/storefront/src/app/category/[slug]/page.tsx` | Xóa bỏ `limit: 120`; đồng bộ server-side pagination, facets (brand, origin, dosageForm, priceRange) |
| **P1-02** | Ma trận kiểm thử & xác minh hệ thống | **HOÀN THÀNH** | Pytest, Next.js Build, Vite Web Build | 53/53 test backend pass 100% (6.74s); 17/17 page Next.js build pass; Vite build pass |

---

## 2. CHI TIẾT KỸ THUẬT CÁC HẠNG MỤC SỬA ĐỔI

### 2.1. P0-01: Khắc phục Modal Tư Vấn Thuốc Kê Đơn (`RxConsultModal.tsx`)
- **Vấn đề cũ**: Click chọn tệp bị gán cứng tên file giả (`"don-thuoc-benh-vien-cho-ray.jpg"`), nhấn gửi chỉ gọi `setIsSubmitted(true)` mà không gửi dữ liệu tới máy chủ; cam kết phản hồi 5-10 phút vô căn cứ.
- **Giải pháp triển khai**:
  1. Tích hợp `input type="file"` thật với cơ chế kiểm soát định dạng nghiêm ngặt (`image/jpeg`, `image/png`, `image/webp`, `application/pdf`) và giới hạn kích thước tối đa 10MB.
  2. Xây dựng endpoint Next.js `/api/prescription/consult` làm nhiệm vụ proxy xác thực dữ liệu và gọi API FastAPI `/api/v1/store/prescriptions/consult`.
  3. Gửi tệp đơn thuốc lên `/api/prescription/upload` và lưu trữ an toàn trước khi chuyển thông tin tư vấn.
  4. Nếu máy chủ phản hồi lỗi hoặc mất kết nối, hiển thị thanh cảnh báo đỏ cùng nút "Thử lại", **tuyệt đối không hiển thị màn hình chúc mừng giả**.
  5. Thay thế cam kết "5-10 phút" bằng thông tin thời gian làm việc thực tế của Dược sĩ: `8h00 - 21h30 hàng ngày`.

### 2.2. P0-02: Rà soát & Bảo mật dữ liệu trong Git
- **Vấn đề cũ**: 11 tệp hình ảnh đơn thuốc mẫu tại `apps/storefront/storage/test-prescriptions/` và 5 tệp sao lưu CSDL SQLite (`pharmatrust.db.bak*`) nằm trong chỉ mục commit của Git.
- **Giải pháp triển khai**:
  1. Cập nhật `.gitignore` với các quy tắc chặn toàn diện:
     ```gitignore
     # Storage & Prescriptions (Health Data Safety)
     storage/
     apps/storefront/storage/
     apps/api/storage/
     *.db*
     *.bak*
     pharmatrust.db*
     ```
  2. Thực hiện `git rm --cached -r` loại bỏ các tệp nhạy cảm khỏi git tree mà không làm mất tệp cục bộ phục vụ phát triển.
  3. Tuân thủ nguyên tắc an toàn: Không force-push hay tự ý xóa lịch sử commit cũ trên remote nếu chưa có phê duyệt từ Quản trị viên.

### 2.3. P0-03: Kiến trúc lưu trữ đơn thuốc bền vững (`storage.ts`)
- **Vấn đề cũ**: Tệp đơn thuốc lưu tại thư mục cục bộ của ứng dụng Next.js. Khi chạy trên môi trường Serverless như Vercel, hệ thống tệp là tạm thời (ephemeral) và sẽ bị xóa khi hàm serverless giải phóng hoặc khi có bản deploy mới.
- **Giải pháp triển khai**:
  1. Thiết kế giao diện trừu tượng `PrescriptionStorageService` chuẩn hóa các thao tác `saveFile`, `getFile`, `deleteFile`, `generateStorageKey`.
  2. Xây dựng bộ điều hợp `S3CompatiblePrescriptionStorage` hỗ trợ lưu trữ đám mây tương thích AWS S3, Cloudflare R2, MinIO bằng chuẩn AWS Signature Version 4 (SigV4) thông qua native Node.js `crypto` và `fetch` (không phát sinh dependency bên thứ ba).
  3. Cơ chế fallback an toàn: Tự động nhận diện môi trường `process.env.VERCEL` để lưu tạm vào thư mục `/tmp/prescriptions` (hỗ trợ tối đa 512MB trên Vercel) kèm nhật ký cảnh báo chi tiết về vòng đời dữ liệu.
  4. Thiết lập chính sách bảo mật: Quyền truy cập tệp luôn đặt ở chế độ `private`, không cung cấp URL tĩnh công khai ra internet.

### 2.4. P0-04: Động cơ thẩm định tính khả dụng thương mại (`product_eligibility_service.py`)
- **Vấn đề cũ**: Regex `DAV_REG_REGEX` có đoạn bắt tự do `^[A-Z0-9\-\.\/]{6,30}$`, tự động coi bất kỳ chuỗi ký tự nào đủ dài là số đăng ký hợp lệ. Ngoài ra, code tự động copy giá quan sát thị trường `PriceObservation.observed_price` sang `base_price` và coi các trạng thái trung gian (`MANUAL_REVIEW`, `VERIFIED_PRODUCT_DATA`) là đủ điều kiện bán lẻ (`can_add_to_cart = True`).
- **Giải pháp triển khai**:
  1. Loại bỏ hoàn toàn regex bắt tự do; chỉ giữ lại các định dạng số đăng ký chính thống do Cục Quản lý Dược (Bộ Y Tế) ban hành (`VD`, `VN`, `QLĐB`, `GC`, `ĐKSP`, `BYT-TB-CT`).
  2. Tách bạch rõ 2 cấp độ xác minh:
     - `is_valid_registration_format`: Kiểm tra cú pháp hình thức (Format Valid).
     - `verify_official_registration`: Đối chiếu sự tồn tại thực tế của hồ sơ trong bảng `RegulatoryRecord`.
  3. Cập nhật nhãn minh bạch:
     - Đã có chứng từ trong DB: `"ĐÃ ĐỐI CHIẾU SỐ ĐĂNG KÝ VỚI CƠ QUAN QUẢN LÝ"` (`OFFICIALLY_VERIFIED`).
     - Chỉ đúng cú pháp: `"ĐÚNG ĐỊNH DẠNG SĐK - CHƯA ĐỐI CHIẾU CHỨNG TỪ GỐC"` (`FORMAT_VALID_UNVERIFIED_EVIDENCE`).
  4. Loại bỏ 100% việc gán `PriceObservation.observed_price` vào `base_price`. Giá bán lẻ chỉ được lấy từ `ProductSku.base_price` được duyệt.
  5. Khóa chặt Pillar 7: Chỉ `publish_mode == "SALE_ELIGIBLE"` và `publish_status == PublishStatus.PUBLISHED` mới được phép `can_add_to_cart = True`.

### 2.5. P0-05: Loại bỏ chuỗi placeholder & Gating thuốc kê đơn (`storefront.py`)
- **Vấn đề cũ**: Các trường thông tin thuốc bị gán giá trị mặc định thiếu căn cứ (`"Viên nén"`, `"PharmaTrust Hợp Tác"`), thuốc Rx bị set `is_sale_eligible = True`.
- **Giải pháp triển khai**:
  1. Thay thế toàn bộ placeholder bằng các chuỗi phản ánh đúng thực trạng: `"Đang cập nhật theo hồ sơ đăng ký"`, `"Chưa có thông tin xuất xứ"`.
  2. Thuốc kê đơn (Rx) được gán cố định: `is_sale_eligible = False`, `can_add_to_cart = False`, `cta_type = "RX_PRESCRIPTION"`, `cta_label = "Gửi Đơn Thuốc Để Dược Sĩ Tư Vấn"`.
  3. Query giá bán `prices_map` trong danh sách sản phẩm chuyển sang truy vấn trực tiếp từ `ProductSku.base_price` của SKU mặc định đang kích hoạt (`is_active == True`).
  4. Xây dựng endpoint tiếp nhận tư vấn `POST /api/v1/store/prescriptions/consult` ghi nhận bản ghi cảnh báo `AdminAlert` vào CSDL cho đội ngũ Dược sĩ.

### 2.6. P1-01: Phân trang & Lọc Facet phía Server trang Danh mục (`category/[slug]/page.tsx`)
- **Vấn đề cũ**: Gọi API cố định `limit: 120`, sau đó tự lọc, sắp xếp và cắt trang thủ công tại Client; thiếu các nút bấm chuyển trang trên giao diện.
- **Giải pháp triển khai**:
  1. Xóa bỏ giới hạn 120 sản phẩm.
  2. Chuyển toàn bộ tham số lọc (`page`, `pageSize`, `category`, `subCategory`, `prescriptionType`, `brand`, `origin`, `dosageForm`, `priceRange`, `sort`) về backend FastAPI xử lý tối ưu qua SQL index.
  3. Bổ sung hệ thống nút bấm phân trang (Trang trước, số trang, Trang sau) tương tự trang `/products`.
  4. Tiếp nhận động danh sách Facet từ backend (`availableBrands`, `availableOrigins`, `availableDosageForms`) để hiển thị chính xác theo từng nhóm danh mục.

---

## 3. BIÊN BẢN KIỂM THỬ KỸ THUẬT (VERIFICATION LOG)

### 3.1. Kiểm thử Động cơ Eligibility & Storefront (Pytest Backend)
- **Lệnh thực thi**:
  ```powershell
  $env:PYTHONPATH="apps/api"; .venv\Scripts\python.exe -m pytest apps/api/tests/test_product_eligibility.py apps/api/tests/test_storefront_category_products.py apps/api/tests/test_sepay_integration.py apps/api/tests/test_five_bug_fixes.py apps/api/tests/test_payment_expiry_and_lifecycle.py apps/api/tests/test_address_v2_comprehensive.py
  ```
- **Thời gian thực hiện**: 22/10/2026 12:25:04 (GMT+7)
- **Mã thoát (Exit Code)**: `0` (Success)
- **Kết quả chi tiết**:
  - `apps/api/tests/test_product_eligibility.py`: **13/13 PASSED** (Bao gồm các ca kiểm thử: SĐK đúng định dạng nhưng chưa có hồ sơ gốc, SĐK đã có hồ sơ Cục Dược, trạng thái trung gian MANUAL_REVIEW không được mua hàng, và endpoint tư vấn đơn thuốc).
  - `apps/api/tests/test_storefront_category_products.py`: **2/2 PASSED**
  - `apps/api/tests/test_sepay_integration.py`: **10/10 PASSED** (Bảo toàn kiểm thử Webhook HMAC-SHA256, Idempotency, Underpaid, Overpaid).
  - `apps/api/tests/test_five_bug_fixes.py`: **8/8 PASSED**
  - `apps/api/tests/test_payment_expiry_and_lifecycle.py`: **7/7 PASSED**
  - `apps/api/tests/test_address_v2_comprehensive.py`: **13/13 PASSED**
  - **Tổng kết**: **53 passed, 4 warnings in 6.74s**.

### 3.2. Kiểm thử Biên dịch Storefront (Next.js 14)
- **Lệnh thực thi**: `npm --prefix apps/storefront run build`
- **Mã thoát (Exit Code)**: `0` (Success)
- **Kết quả**:
  - Biên dịch thành công 100% Type-checking TypeScript và ESLint.
  - Tạo gói tĩnh và route động cho toàn bộ 17/17 trang.
  - Đăng ký hợp lệ các route handler mới: `/api/prescription/consult` và `/api/prescription/upload`.

### 3.3. Kiểm thử Biên dịch Web Quản Trị & Kho (Vite React)
- **Lệnh thực thi**: `npm --prefix apps/web run build`
- **Mã thoát (Exit Code)**: `0` (Success)
- **Kết quả**: Biên dịch 2521 module thành công trong 1.00s, không phát sinh lỗi Type-checking.

---

## 4. HƯỚNG DẪN CẤU HÌNH BIẾN MÔI TRƯỜNG CHO CLOUD STORAGE (S3/R2)

Để kích hoạt lưu trữ đơn thuốc trên nền tảng đám mây vĩnh viễn (production), quản trị viên cần bổ sung các biến môi trường sau vào Vercel Project Settings:

```env
# Cloudflare R2 / AWS S3 Storage Credentials for Prescriptions
S3_BUCKET="h4care-prescriptions-prod"
S3_REGION="auto"   # hoặc "ap-southeast-1" nếu dùng AWS S3 Singapore
S3_ENDPOINT="https://<account-id>.r2.cloudflarestorage.com"
S3_ACCESS_KEY_ID="<your-access-key-id>"
S3_SECRET_ACCESS_KEY="<your-secret-access-key>"
```

*Ghi chú*: Khi chưa cấu hình các biến trên, hệ thống sẽ tự động kích hoạt bộ nhớ đệm `/tmp/prescriptions` để đảm bảo ứng dụng không bị crash và ghi log cảnh báo rõ ràng.

---

## 5. KẾT LUẬN & CAM KẾT

Tất cả các tồn dư sau commit `1b1d612` đã được giải quyết triệt để theo đúng tôn chỉ:
1. Không còn bất kỳ luồng "fake success" hay dữ liệu giả nào trên giao diện tư vấn toa thuốc.
2. Không còn mã bắt số đăng ký tự do; tính hợp pháp của thuốc phải được đối chiếu với cơ sở dữ liệu dược thư.
3. Không đánh đồng giá quan sát tham khảo với giá bán lẻ niêm yết của nhà thuốc.
4. Hệ thống đã sẵn sàng cho quy trình đồng bộ và triển khai lên môi trường thử nghiệm trực tuyến Staging.
