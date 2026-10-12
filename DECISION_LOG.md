# DECISION LOG: H4CARE MULTI-WAREHOUSE & RBAC ARCHITECTURE

> **Thời điểm xác nhận**: 2026-10-12T17:31:52+07:00  
> **Người phê duyệt**: Khách hàng / Product Owner  
> **Nhánh phát triển**: `feature/multi-warehouse-rbac`  
> **Nguyên tắc**: Không tự suy đoán nghiệp vụ. Mọi quyết định dưới đây là căn cứ pháp lý và kỹ thuật duy nhất để triển khai.

---

## 1. Mạng lưới kho và chi nhánh (Question 1)
* **Quyết định**: Khởi tạo mạng lưới phân tán gồm **ít nhất 20 kho dược và chi nhánh nhà thuốc H4CARE** trải dài khắp các tỉnh thành trên toàn quốc (Hà Nội, TP.HCM, Đà Nẵng, Cần Thơ, Hải Phòng, Quảng Ninh, Nam Định, Huế, Nha Trang, Bình Dương, Đồng Nai...).
* **Căn cứ**: Một tỉnh thành có thể có nhiều quầy thuốc/kho khác nhau để tối ưu bán kính phục vụ và thời gian giao hàng.
* **Tác động kỹ thuật**: Cấu hình bảng `warehouses` với tọa độ địa lý chuẩn (`lat`, `lng`), bán kính phục vụ (`service_radius_km`) và địa chỉ hành chính 2 cấp đầy đủ.

---

## 2. Cổng thanh toán ưu tiên (Question 2)
* **Quyết định**: Ưu tiên triển khai **VietQR (Chuyển khoản QR Động)** kết hợp **COD (Thanh toán khi nhận hàng)** trong chế độ Mock / Sandbox.
* **Căn cứ**: Đảm bảo hệ thống chạy mượt mà trên môi trường local phục vụ chấm điểm và kiểm thử tự động, không phụ thuộc vào kết nối API bên thứ ba.
* **Tác động kỹ thuật**: Sử dụng adapter thanh toán VietQR với thuật toán sinh mã QR chuẩn NAPAS và webhook kiểm tra chữ ký, số tiền chính xác từng đồng.

---

## 3. Tích hợp Bản đồ & Địa chỉ (Question 3)
* **Quyết định**: Sử dụng **Mock / OpenStreetMap Geocoding Provider** cho môi trường local.
* **Căn cứ**: Chưa có Google Maps API key trả phí. Tránh hard-code API key vào mã nguồn.
* **Tác động kỹ thuật**: Triển khai `GeocodingProvider` interface với Mock Geocoder hỗ trợ dữ liệu hành chính chuẩn Việt Nam, tính khoảng cách chính xác theo công thức Haversine để tự động tìm kho gần khách nhất.

---

## 4. Quản lý Giá bán tại từng kho (Question 4)
* **Quyết định**: **Quản lý kho KHÔNG ĐƯỢC thay đổi giá bán**. Giá bán niêm yết do **Admin tổng quản lý tập trung**.
* **Căn cứ**: Đảm bảo chính sách một giá thống nhất trên toàn hệ thống H4CARE, tránh gian lận giá giữa các chi nhánh.
* **Tác động kỹ thuật**: Quản lý kho (`WAREHOUSE_MANAGER`) chỉ có quyền quản lý tồn kho khả dụng, lô thuốc, hạn dùng, trạng thái bật/tắt bán tại kho và duyệt phiếu nhập/xuất kho.

---

## 5. Quyền tạo tài khoản nhân viên của Quản lý kho (Question 5)
* **Quyết định**: **Quản lý kho ĐƯỢC PHÉP tạo tài khoản nhân viên phụ thuộc kho của mình** (Lựa chọn B).
* **Căn cứ**: Phân cấp quản lý nhân sự tại chỗ cho từng chi nhánh kho (nhân viên đóng gói, nhân viên kho).
* **Tác động kỹ thuật**: Thêm vai trò `WAREHOUSE_STAFF` thuộc quyền quản lý của `WAREHOUSE_MANAGER` của kho đó. Backend kiểm tra chặt chẽ: Quản lý kho chỉ được tạo/sửa tài khoản nhân viên có `warehouse_id` thuộc kho mình phụ trách.

---

## 6. Xử lý khi Điều chuyển hàng thất bại sau thanh toán (Question 6)
* **Quyết định**: Khi hàng điều chuyển nội bộ giữa các kho bị hỏng, thất lạc hoặc không đủ để gom đơn sau khi khách đã thanh toán, hệ thống sẽ **Tự động hủy toàn bộ đơn hàng và hoàn tiền 100% cho khách hàng** kèm thông báo và audit log minh bạch (Lựa chọn A).
* **Căn cứ**: Tuân thủ nguyên tắc không giao đơn hàng chắp vá hoặc bắt khách hàng chờ đợi vô thời hạn nếu không đủ điều kiện cam kết.
* **Tác động kỹ thuật**: Kích hoạt state machine `CANCELLED` và tạo bản ghi hoàn tiền `refunds` với lý do `INTERNAL_TRANSFER_FAILED`, đồng thời hoàn lại các tồn kho đã giữ tại kho nguồn/kho đích.

---

## 7. Hạn sử dụng tối thiểu để xuất kho FEFO (Question 7)
* **Quyết định**: Lô thuốc phải còn hạn sử dụng **tối thiểu 6 tháng (180 ngày)** mới được phép tự động gán vào đơn giao cho khách hàng (Lựa chọn A).
* **Căn cứ**: Tiêu chuẩn an toàn dược phẩm H4CARE và chuẩn GSP/GDP, bảo vệ quyền lợi người bệnh.
* **Tác động kỹ thuật**: Thuật toán FEFO loại bỏ tất cả các lô có `expiry_date < current_date + 180 days`. Các lô cận hạn (< 180 ngày) được gắn cờ `NEAR_EXPIRY` và chỉ được điều chỉnh/thanh lý nội bộ hoặc bán tại quầy dưới sự giám sát.
