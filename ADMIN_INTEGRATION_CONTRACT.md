# H4CARE – HỢP ĐỒNG TÍCH HỢP HỆ THỐNG (ADMIN INTEGRATION CONTRACT)
**Phiên bản:** 2.0 (Module B – Product Detail & Commercial Eligibility)  
**Phạm vi:** Core Commerce Backend $\leftrightarrow$ Admin Dashboard Interface  
**Trạng thái tuân thủ:** `apps/web` và Module Auth **ĐƯỢC KHÓA HOÀN TOÀN (0 chỉnh sửa)**  

---

## 1. MỤC ĐÍCH HỢP ĐỒNG

Tài liệu này xác định các giao diện lập trình ứng dụng (API), lược đồ cơ sở dữ liệu (Database Schema) và quy tắc nghiệp vụ dùng chung giữa:
- **Phần Storefront & Core Commerce Backend** (Do Agent/Kỹ sư phụ trách)
- **Phần Admin Dashboard & Management Features** (Do Thành viên khác phụ trách)

Mọi thay đổi trên Backend đã được thiết kế theo hướng tương thích ngược (Backward Compatible) và mở rộng cho nhóm Admin mà không làm phá vỡ bất kỳ màn hình quản trị hiện tại nào.

---

## 2. LƯỢC ĐỒ DỮ LIỆU DÙNG CHUNG (SHARED DATABASE SCHEMA)

### 2.1. Bảng `canonical_products`
Bổ sung các trường phân loại và chỉ số minh bạch:
- `publish_mode` (VARCHAR(50)):
  - `'SALE_ELIGIBLE'`: Sản phẩm đạt chuẩn thương mại, có chứng từ kho GSP và sẵn sàng mở bán trực tuyến.
  - `'VERIFIED_PRODUCT_DATA'`: Dữ liệu dược lý đã được đối chiếu chính thức với Cục Quản lý Dược (SĐK, hoạt chất, quy cách), nhưng chưa kích hoạt mở bán thương mại trực tuyến.
  - `'REFERENCE_ONLY'`: Sản phẩm thuộc danh mục tra cứu y tế tham khảo; khách hàng không thể thêm vào giỏ hàng online.
  - `'INTERNAL_TEST'`: Sản phẩm thử nghiệm nội bộ (`is_demo = True`), tự động ẩn khỏi Storefront.
- `registration_number` (VARCHAR(150)): Số đăng ký lưu hành chính thức được Bộ Y Tế / Cục Quản lý Dược cấp (VD: `VD-22709-15`, `VN-18235-14`). **Tuyệt đối không dùng số giả tạo `VD-{id}-22`**.
- `package_description` (VARCHAR(700)): Quy cách đóng gói thương mại (VD: `Hộp 24 gói x 1.5g`, `Hộp 10 vỉ x 10 viên`).
- `storage_conditions` (VARCHAR(500)): Điều kiện bảo quản theo hồ sơ GSP.

### 2.2. Bảng `product_skus` (Multi-SKU Packaging)
Hỗ trợ nhiều quy cách đóng gói cho cùng một sản phẩm:
- `id` (INTEGER, Primary Key)
- `canonical_product_id` (INTEGER, Foreign Key $\rightarrow$ `canonical_products.id`)
- `sku_code` (VARCHAR(100)): Mã quản lý SKU duy nhất (VD: `SKU-HAPA-250-BOX`, `SKU-HAPA-250-SACHET`).
- `uom` (VARCHAR(50)): Đơn vị tính (Hộp, Vỉ, Gói, Viên, Chai, Tuýp, Ống, Lọ).
- `conversion_rate` (INTEGER): Hệ số quy đổi ra đơn vị cơ bản (VD: 1 Hộp = 24 Gói thì conversion_rate = 24).
- `base_price` (NUMERIC(12, 2)): Giá bán lẻ niêm yết chính thức tính theo đơn vị `uom` tương ứng.
- `is_default` (BOOLEAN): Đơn vị mặc định khi hiển thị trên Storefront.
- `is_active` (BOOLEAN): Trạng thái kích hoạt.

### 2.3. Bảng `inventory_batches` & `warehouse_batch_stock` (FEFO Compliance)
- `status` (VARCHAR(50)):
  - `'ACTIVE'`: Lô hàng hợp lệ, sẵn sàng cấp phát.
  - `'QUARANTINED'`: Lô đang bị cách ly kiểm nghiệm hoặc thử nghiệm (Storefront và FEFO tự động loại trừ, tồn khả dụng = 0).
  - `'RECALLED'`: Lô hàng bị thu hồi.
  - `'EXPIRED'`: Lô hàng đã hết hạn sử dụng.
- **Quy tắc FEFO an toàn tại Backend:**
  Hệ thống tính tồn khả dụng chỉ quét các lô thỏa mãn:
  $$\text{status} == 'ACTIVE' \quad \text{AND} \quad \text{expiry\_date} > \text{today} \quad \text{AND} \quad \text{quantity\_available} > 0$$

---

## 3. HỢP ĐỒNG API CHO ADMIN VÀ KHÁCH HÀNG

### 3.1. Chi tiết sản phẩm & Thẩm định mở bán (Product Eligibility Engine)
**Endpoint:** `GET /api/v1/store/products/{slug_or_id}`  
**Query Params:** `skuId` (tùy chọn - khi chuyển đổi quy cách đóng gói)

**Cấu trúc dữ liệu trả về:**
```json
{
  "id": "pt-501",
  "dbId": 501,
  "name": "Thuốc hạ sốt Hapacol 250mg",
  "slug": "thuoc-ha-sot-hapacol-250mg-501",
  "sku": "VD-22709-15",
  "brand": "Công ty Cổ phần Dược Hậu Giang (DHG Pharma)",
  "price": 45000,
  "catalogTier": "VERIFIED_PRODUCT_DATA",
  "isSaleEligible": false,
  "canAddToCart": false,
  "ctaType": "CONSULT_PHARMACIST",
  "ctaLabel": "Tư Vấn Dược Sĩ (Chưa Mở Bán Trực Tuyến)",
  "primaryReason": "Dữ liệu dược khoa đã được đối chiếu chính thức, nhưng sản phẩm chưa kích hoạt mở bán thương mại trực tuyến.",
  "reasons": [
    "Hồ sơ đăng ký lưu hành đã được xác minh đối chiếu với Cục Quản lý Dược.",
    "Cần hoàn tất quy trình nghiệm thu chứng từ nhập kho vật lý GSP trước khi mở bán thương mại cho khách hàng."
  ],
  "transparency": {
    "source_name": "Dữ liệu Cục Quản lý Dược (Bộ Y Tế) & Hồ sơ nhà sản xuất",
    "registration_number": "VD-22709-15",
    "registration_status": "ĐÃ ĐỐI CHIẾU SỐ ĐĂNG KÝ LƯU HÀNH",
    "completeness_score": 95,
    "pending_verifications": [
      "Biên bản kiểm nghiệm chất lượng xuất xưởng (COA) của lô hàng vật lý",
      "Phiếu kiểm nhập kho GSP và hóa đơn GTGT của nhà phân phối hợp pháp"
    ],
    "last_audited_at": "2026-10-11",
    "disclaimer": "Chỉ số minh bạch dữ liệu phản ánh mức độ đầy đủ và nguồn gốc đối chiếu của hồ sơ thông tin, không phải đánh giá chất lượng sinh học hay hiệu quả điều trị của thuốc."
  },
  "skus": [
    {
      "id": 12,
      "sku_code": "SKU-HAPA-250-BOX",
      "uom": "Hộp",
      "conversion_rate": 24,
      "base_price": 45000,
      "is_default": true,
      "available_stock": 0
    },
    {
      "id": 163,
      "sku_code": "SKU-HAPA-250-SACHET",
      "uom": "Gói",
      "conversion_rate": 1,
      "base_price": 2000,
      "is_default": false,
      "available_stock": 0
    }
  ],
  "selectedSku": {
    "id": 12,
    "sku_code": "SKU-HAPA-250-BOX",
    "uom": "Hộp",
    "conversion_rate": 24,
    "base_price": 45000,
    "is_default": true,
    "available_stock": 0
  }
}
```

### 3.2. Endpoint kiểm tra tính khả dụng chuyên biệt
**Endpoint:** `GET /api/v1/store/products/{slug_or_id}/eligibility`  
**Query Params:** `skuId` (tùy chọn)  
Dùng để kiểm tra nhanh trạng thái mở bán và tồn khả dụng khi Admin hoặc Khách hàng chuyển đổi đơn vị đóng gói (Hộp $\leftrightarrow$ Vỉ $\leftrightarrow$ Gói).

---

## 4. HƯỚNG DẪN DÀNH CHO NHÓM PHÁT TRIỂN ADMIN

1. **Chuyển sản phẩm sang trạng thái mở bán (`SALE_ELIGIBLE`):**
   - Không được tự động chuyển `publish_mode = 'SALE_ELIGIBLE'` nếu sản phẩm:
     - Chưa có số đăng ký lưu hành Cục Quản lý Dược hợp lệ.
     - Là thuốc kê đơn (Rx) theo quy định Bộ Y Tế.
     - Chưa có phiếu nhập kho vật lý GSP (`StockReceipt`) và biên bản kiểm nghiệm (COA).
2. **Quản lý quy cách đóng gói (SKU Management):**
   - Khi Admin thêm hoặc chỉnh sửa quy cách đóng gói trong bảng `product_skus`, hệ thống Storefront sẽ tự động đồng bộ hiển thị các nút chọn đơn vị (Hộp, Vỉ, Gói...) và cập nhật giá tương ứng.
3. **Cách ly lô kiểm nghiệm:**
   - Khi Admin cần kiểm tra lô hoặc nghi ngờ chất lượng, chỉ cần cập nhật `status = 'QUARANTINED'` trên bảng `inventory_batches`. Toàn bộ Storefront và FEFO Engine sẽ lập tức loại trừ lô đó ra khỏi tồn bán được mà không làm lệch sổ cái kế toán.

---

## 5. BẢO MẬT PHÂN QUYỀN ĐƠN HÀNG, ĐỔI TRẢ & THANH TOÁN (SECURITY & ROLE CONTRACT)
**Cập nhật:** Module C Security Hardening & Commercial Integrity

### 5.1. Ma trận phân quyền vai trò (Role & Ownership Matrix)

| Endpoint / Nhóm API | Khách vãng lai (Guest) | Khách đăng nhập (`CUSTOMER`) | Dược sĩ (`PHARMACIST`) / Quản trị (`ADMIN`) |
| :--- | :--- | :--- | :--- |
| `GET /store/orders/{order_code}` | Bắt buộc `?phone=<sđt>` khớp `order.customer_phone` (403 nếu sai/thiếu) | Chỉ xem được đơn của chính mình (khớp `user_id` hoặc `phone`) | Toàn quyền tra cứu mọi đơn hàng |
| `GET /store/orders/customer/{phone}` | Bị từ chối (401 Unauthorized) | Bắt buộc đăng nhập; SĐT tra cứu phải khớp `current_user.phone` (403 nếu IDOR) | Toàn quyền tra cứu lịch sử đơn theo SĐT |
| `GET /returns/{return_code}` | Bắt buộc `?phone_verify=<sđt>` khớp `return.customer_phone` | Chỉ xem được yêu cầu đổi trả của chính mình | Toàn quyền tra cứu hồ sơ đổi trả |
| `GET /returns/my-requests` | Bị từ chối (401 Unauthorized) | Chỉ liệt kê yêu cầu đổi trả thuộc `current_user.id` | Toàn quyền tra cứu |
| `POST /payments/momo/create`, `/vietqr/create`, `/intent`, `/retry`, `/cancel` | Bắt buộc `phone_verify` trong JSON body khớp `order.customer_phone` | Khớp `order.user_id` hoặc `current_user.phone` | Toàn quyền thao tác trên mọi đơn |
| `POST /payments/reconciliation/*` | Bị cấm (403 Forbidden) | Bị cấm (403 Forbidden) | **Chỉ `ADMIN` hoặc `PHARMACIST`** có quyền đối soát tài chính ngân hàng |
| `POST /payments/auto-heal` | Bị cấm (403 Forbidden) | Bị cấm (403 Forbidden) | **Chỉ `ADMIN` hoặc `PHARMACIST`** có quyền chạy job tự động sửa lỗi trạng thái |
| `POST /payments/reservations/stale/release` | Bị cấm (403 Forbidden) | Bị cấm (403 Forbidden) | **Chỉ `ADMIN` hoặc `PHARMACIST`** có quyền giải phóng tồn kho treo |
| `POST /payments/*/simulate` | Bị cấm tuyệt đối trên Production (`is_simulator_permitted == False` $\rightarrow$ 403 Fail-Closed) | Bị cấm tuyệt đối | Chỉ kích hoạt trong môi trường dev cục bộ khi bật cờ |

### 5.2. Nguyên tắc an toàn thanh toán MoMo & VietQR
1. **Loại bỏ URL giả lập khi lỗi mạng (Zero Fake URLs):**
   - Khi MoMo Sandbox/Gateway trả lỗi hoặc timeout, Backend trả HTTP 502 Bad Gateway và ghi nhận transaction `FAILED`.
   - Tuyệt đối không sinh URL `SimulatedSuccess` giả lập làm người mua hiểu nhầm là đã thanh toán.
2. **Khởi tạo và đối soát VietQR:**
   - Client công khai sử dụng `/payments/orders/{order_code}/status` để thăm dò trạng thái thanh toán đơn hàng.
   - Các endpoint đối soát nội bộ `/payments/reconciliation/order` và `/payments/reconciliation/audit` yêu cầu Bearer token của Admin/Pharmacist.

### 5.3. Quy tắc phân bổ tồn kho FEFO đa quy cách (Multi-SKU FEFO Allocation)
- Khi khách đặt hàng theo một quy cách đóng gói cụ thể (ví dụ: `SKU-PAN-BOX-100` hoặc `SKU-PAN-SACHET-01`), hàm điều phối `route_and_allocate_order` phân bổ chính xác tồn kho theo SKU mà khách đã chọn thay vì mặc định về SKU hộp.
- Giá tiền, chiết khấu voucher và phí vận chuyển do Backend tính toán và xác thực tại thời điểm Checkout; Frontend không quyết định giá.

---

## 6. TÍCH HỢP ĐIỀU PHỐI KHO, QUẢN LÝ KIỆN HÀNG FSM VÀ KHO NHẬN HÀNG HOÀN (WAREHOUSE, FULFILLMENT & RETURNS)
**Cập nhật:** Final End-to-End Warehouse, Order & Returns Integration Repair

### 6.1. Danh Sách Endpoint Mới & Nâng Cấp

#### A. Danh Sách Kiện Hàng Thuộc Kho (Warehouse Fulfillment Queue)
- **Endpoint**: `GET /api/v1/admin/warehouses/{warehouse_id}/fulfillments` (hoặc alias `/api/v1/warehouses/{warehouse_id}/fulfillments`)
- **Quyền hạn**: `ADMIN`, `PHARMACIST`
- **Query Parameters**:
  - `status`: Lọc theo trạng thái kiện (`PENDING`, `PICKED`, `PACKED`, `SHIPPED`, `DELIVERED`, `CANCELLED`). Mặc định: tất cả.
  - `page`: Số trang (mặc định: `1`).
  - `page_size`: Số bản ghi mỗi trang (mặc định: `20`, tối đa `100`).
  - `search`: Tìm theo mã đơn hàng, mã kiện hàng, họ tên khách hàng hoặc số điện thoại.
- **Cấu trúc Response**:
```json
{
  "warehouse": {
    "id": 1,
    "code": "WH-HCM-01",
    "name": "Kho Tổng TP. Hồ Chí Minh"
  },
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 101,
      "fulfillment_code": "FF-ORD261015001-WH-HCM-01",
      "order_id": 45,
      "order_code": "ORD261015001",
      "customer_name": "Nguyễn Văn A",
      "customer_phone": "0912345678",
      "shipping_address": "123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh",
      "status": "PENDING",
      "carrier_name": "GHTK Fast",
      "tracking_code": "TRACK-WH-HCM-01-101",
      "shipping_fee": 25000,
      "created_at": "2026-10-15T08:30:00Z",
      "items": [
        {
          "fulfillment_item_id": 201,
          "product_id": 12,
          "product_name": "Paracetamol 500mg Hộp 100 viên",
          "quantity": 2,
          "batches": [
            {
              "batch_id": 5,
              "batch_number": "LOT-PARA-2026A",
              "expiry_date": "2027-12-31",
              "allocated_quantity": 2
            }
          ]
        }
      ]
    }
  ]
}
```

#### B. Cập Nhật Trạng Thái Kiện Hàng (Fulfillment FSM Transition)
- **Endpoint**: `PATCH /api/v1/admin/orders/fulfillments/{fulfillment_id}/status`
- **Quyền hạn**: `ADMIN`, `PHARMACIST`
- **Request Body**:
```json
{
  "status": "PICKED"
}
```
- **Quy tắc chuyển đổi trạng thái (Strict Finite State Machine)**:
  - `PENDING` $\rightarrow$ `PICKED` hoặc `CANCELLED`
  - `PICKED` $\rightarrow$ `PACKED` hoặc `CANCELLED`
  - `PACKED` $\rightarrow$ `SHIPPED` hoặc `CANCELLED`
  - `SHIPPED` $\rightarrow$ `DELIVERED`
  - `DELIVERED`: Trạng thái cuối, không thể thay đổi tiếp.
  - `CANCELLED`: Trạng thái cuối, không thể phục hồi.
  - **Idempotency**: Gửi lại cùng một trạng thái sẽ trả về HTTP 200 kèm dữ liệu hiện tại, không gây lỗi 500 và không trừ kho lần 2.
  - **Hiệu ứng khi chuyển sang `SHIPPED`**:
    - Khấu trừ `quantity_on_hand` và giải phóng `quantity_reserved` trong kho tương ứng.
    - Đổi trạng thái `StockReservation` thành `FULFILLED`.
    - Tự động ghi thẻ kho (`StockMovement`) loại `DISPATCH` với số lượng âm.
  - **Hiệu ứng khi chuyển sang `CANCELLED`**:
    - Tự động giải phóng toàn bộ số lượng giữ chỗ (`quantity_reserved`) hoàn lại cho `quantity_available`.
    - Đổi trạng thái `StockReservation` thành `CANCELLED`.

#### C. Danh Sách Yêu Cầu Đổi/Trả Thuộc Kho (Warehouse Returns Queue)
- **Endpoint**: `GET /api/v1/admin/warehouses/{warehouse_id}/returns` (hoặc alias `/api/v1/warehouses/{warehouse_id}/returns`)
- **Quyền hạn**: `ADMIN`, `PHARMACIST`
- **Query Parameters**:
  - `status`: Lọc theo trạng thái yêu cầu (`REQUESTED`, `APPROVED`, `RECEIVED_AT_WAREHOUSE`, `INSPECTED`, `REJECTED`, `COMPLETED`).
  - `page`: Trang (mặc định: `1`).
  - `page_size`: Kích thước trang (mặc định: `20`).
- **Cấu trúc Response**:
```json
{
  "warehouse": {
    "id": 1,
    "code": "WH-HCM-01",
    "name": "Kho Tổng TP. Hồ Chí Minh"
  },
  "total": 1,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": 12,
      "return_code": "RET202610150001",
      "order_id": 45,
      "order_code": "ORD261015001",
      "customer_name": "Nguyễn Văn A",
      "customer_phone": "0912345678",
      "type": "RETURN",
      "status": "APPROVED",
      "reason": "DEFECTIVE_PRODUCT",
      "reason_detail": "Bao bì bị rách trong quá trình vận chuyển",
      "origin_warehouse_id": 1,
      "refund_amount": 150000,
      "created_at": "2026-10-15T09:00:00Z",
      "items": [
        {
          "id": 31,
          "order_item_id": 201,
          "product_name": "Paracetamol 500mg Hộp 100 viên",
          "requested_quantity": 2,
          "inspection_result": null,
          "disposition": null
        }
      ]
    }
  ]
}
```

#### D. Dược Sĩ Tiếp Nhận Hàng Hoàn Tại Kho (Receive Return)
- **Endpoint**: `POST /api/v1/admin/returns/{return_request_id}/receive`
- **Quyền hạn**: `ADMIN`, `PHARMACIST`
- **Mô tả**: Chuyển trạng thái yêu cầu trả hàng từ `APPROVED` sang `RECEIVED_AT_WAREHOUSE` khi kiện hàng trả về đã đến kho vật lý.

#### E. Dược Sĩ Kiểm Nghiệm & Phân Loại Hàng Hoàn (Inspect Return)
- **Endpoint**: `POST /api/v1/admin/returns/{return_request_id}/inspect`
- **Quyền hạn**: `ADMIN`, `PHARMACIST`
- **Mô tả**: Đánh giá tình trạng thuốc hoàn lại và phân bổ xử lý kho theo đúng kho xuất phát điểm (`origin_warehouse_id`).
- **Request Body**:
```json
{
  "items": [
    {
      "return_item_id": 31,
      "inspected_quantity": 2,
      "inspection_result": "PASS",
      "disposition": "RESTOCK",
      "reason": "Hàng nguyên seal, tem bảo hành nguyên vẹn, nhập lại kho bán"
    }
  ],
  "note": "Đã kiểm nghiệm đạt tiêu chuẩn GSP"
}
```
- **Các giá trị Disposition hợp lệ**:
  - `RESTOCK`: Thuốc còn nguyên vẹn, đạt chuẩn GSP $\rightarrow$ Cộng lại `quantity_on_hand` và `quantity_available` vào chính kho ban đầu. Tạo Thẻ kho `RETURN_RESTOCK`.
  - `QUARANTINE`: Cần biệt trữ để theo dõi hoặc kiểm nghiệm thêm $\rightarrow$ Không cộng vào tồn bán lẻ, ghi nhận biên bản biệt trữ.
  - `DISPOSE`: Hỏng, vỡ, hết hạn hoặc rách niêm phong $\rightarrow$ Ghi nhận tiêu hủy, không cộng vào tồn bán lẻ.

#### F. Lọc Đơn Hàng Admin Theo Kho Điều Phối
- **Endpoint**: `GET /api/v1/admin/orders?warehouse_id={warehouse_id}&page={page}&page_size={page_size}`
- **Quyền hạn**: `ADMIN`, `PHARMACIST`
- **Mô tả**: Trả về danh sách đơn hàng được phân bổ từ kho tương ứng, kèm metadata phân trang chuẩn (`total`, `page`, `page_size`, `total_pages`).

### 6.2. Hướng Dẫn Áp Dụng Patch Cho Admin UI (`apps/web`)

File patch đã được chuẩn bị tại: `patches/admin_warehouse_integration.patch`.

#### Cách áp dụng:
```bash
# Kiểm tra tính tương thích trước khi áp dụng:
git apply --check patches/admin_warehouse_integration.patch

# Áp dụng patch:
git apply patches/admin_warehouse_integration.patch
```
