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
