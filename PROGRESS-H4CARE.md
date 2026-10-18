# BÁO CÁO TIẾN ĐỘ & BÀN GIAO KỸ THUẬT: H4CARE LIVE CHAT & NÂNG CẤP CHATBOT AI CHATGPT-STYLE

- **Dự án**: H4CARE / PharmaTrust E-Pharmacy
- **Thời điểm hoàn thành**: 18/10/2026
- **Trạng thái**: Hoàn tất 100% các hạng mục yêu cầu, toàn bộ test suite và production builds đạt chuẩn xanh (0 lỗi).

---

## 1. CÁC HẠNG MỤC ĐÃ HOÀN THÀNH

### I. Chuẩn hóa Lời chào mặc định AI & Cơ chế Tự động Nâng cấp Phiên cũ (Fix Vấn Đề 1)
1. **Lời chào mặc định mới (Frontend & Backend đồng bộ 100%)**:
   ```
   Chào bạn! Mình là trợ lý AI của H4CARE. Mình có thể hỗ trợ bạn tìm hiểu thông tin thuốc, sản phẩm và giải đáp các thắc mắc về sức khỏe.

   Bạn cần mình hỗ trợ điều gì hôm nay?
   ```
2. **Loại bỏ triệt để khẩu hiệu quảng cáo**:
   - Không còn cụm từ "Tra cứu thuốc chính hãng", "Dạ xin chào quý khách", "Em là hệ thống tự động".
   - Phong cách y khoa tự nhiên, ân cần, ngắn gọn và không lặp lại lời chào sau mỗi tin nhắn.
3. **Cơ chế Migrate an toàn (`migrateWelcomeMessage`)**:
   - Khi tải lại trang hoặc khôi phục phiên từ `localStorage`/`sessionStorage`, nếu tin nhắn đầu tiên là lời chào hệ thống cũ, hàm tự động chuẩn hóa sang lời chào mới.
   - Bảo toàn 100% các tin nhắn thật của khách hàng và câu trả lời tư vấn phía sau.

### II. Ẩn hoàn toàn Khu vực Gợi ý Cố định trên Ô nhập (Fix Vấn Đề 2)
1. **Xóa bỏ dứt điểm thanh gợi ý cố định**:
   - Ẩn hoàn toàn khối nút gợi ý cố định ("Tra cứu Panadol Extra", "Tôi bị sốt và đau đầu", "Chính sách đổi trả thuốc thế nào?", "Tôi muốn gặp nhân viên tư vấn") từng nằm chật chội phía trên ô nhập.
   - Không để lại khoảng trống thừa hay margin/padding lỗi. Khung chat cuộn mượt và nối liền trực tiếp vào thanh nhập liệu.
2. **Tập trung hóa câu hỏi gợi ý vào menu dấu cộng (+)**:
   - Toàn bộ dữ liệu gợi ý được chuyển vào mục **"Từ khóa & câu hỏi gợi ý"** trong menu `+`.
   - Cung cấp 5 nhóm câu hỏi y tế chuẩn hóa (A: Thông tin thuốc, B: Tư vấn sức khỏe, C: Sản phẩm tại H4CARE, D: Đơn hàng & chính sách, E: Tư vấn trực tiếp).
   - Có thanh tìm kiếm tức thì và bộ lọc theo nhóm.
   - **Khi chọn câu hỏi: Chỉ điền nội dung vào ô nhập (focus con trỏ), KHÔNG tự động gửi**, cho phép khách hàng chỉnh sửa linh hoạt trước khi gửi.

### III. Khôi phục hoàn toàn Hệ thống 2 Tab (Dual-Tab Navigation)
1. **Tab 1 – Trợ lý AI 24/7**:
   - Trò chuyện tự nhiên như ChatGPT với đầy đủ ngữ cảnh đa lượt, phân loại 10 intent chuẩn y khoa, nhận diện Red Flag cấp cứu P0.
   - Quản lý đa cuộc trò chuyện độc lập (Multi-conversation), tạo phiên mới, đổi tên, xóa, tìm kiếm và lưu trữ cục bộ an toàn (`ChatHistoryDrawer.tsx`).
2. **Tab 2 – Tư vấn trực tiếp (Người thật)**:
   - Tích hợp toàn diện component `LiveChatPanel.tsx` kết nối trực tiếp với Dược sĩ / Nhân viên chăm sóc khách hàng.
   - Quản lý trạng thái phiên (`WAITING`, `ACTIVE`, `CLOSED`), polling tin nhắn 2.5s, chime audio thông báo âm thanh khi có tin mới, gửi phản hồi đánh giá sao và khiếu nại.
   - Handoff mượt mà từ AI sang người thật: Tự động chuyển giao tóm tắt ngữ cảnh khi AI phát hiện câu hỏi phức tạp hoặc khách hàng yêu cầu.
   - Chuyển đổi giữa 2 tab bảo toàn 100% trạng thái và tin nhắn, không bị reset hay mất dữ liệu.

### IV. Nâng cấp Thanh nhập liệu phong cách ChatGPT (Chat Input Experience)
1. **Menu tiện ích dấu cộng (+)** với đúng 5 công cụ chuẩn hóa:
   - **Thêm ảnh và tệp** (Tải lên JPG, PNG, WEBP, PDF, DOC, DOCX, TXT tối đa 10MB).
   - **Thêm ảnh từ thư viện** (Bộ lọc riêng cho ảnh JPG, JPEG, PNG, WEBP).
   - **Chụp ảnh** (Mở modal camera WebRTC trực tiếp với viewfinder, chụp nhanh, xem trước, chụp lại và xác nhận gửi).
   - **Ghi âm thành văn bản** (Tích hợp Web Speech API tiếng Việt `vi-VN` với sóng âm động).
   - **Từ khóa & câu hỏi gợi ý** (Mở popup modal tra cứu với 5 nhóm A-E và thanh tìm kiếm trực tiếp).
2. **Trải nghiệm nhập liệu cao cấp**:
   - Textarea tự co giãn chiều cao theo nội dung (tối đa 120px) kèm phím tắt gửi Enter, xuống dòng Shift+Enter.
   - Kéo thả file trực tiếp (Drag & Drop) vào khung chat với hiệu ứng viền nổi bật.
   - Dán ảnh trực tiếp từ clipboard (Ctrl + V).
   - Chip xem trước tệp đính kèm với thumbnail ảnh / icon định dạng tệp, kích thước và nút hủy (X).

### V. Trình xem ảnh phóng to (Lightbox Modal) & Tải tệp tài liệu
1. **Hiển thị hình ảnh trong tin nhắn**: Ảnh có viền bo tròn thẩm mỹ, hiệu ứng hover kèm icon phóng to. Khi click vào ảnh sẽ mở full-screen Lightbox tối nền, hỗ trợ xem độ phân giải cao, nút tải về và nút đóng (hoặc phím Esc).
2. **Hiển thị tài liệu (.pdf, .doc, .docx, .txt)**: Thẻ hiển thị chuyên biệt có icon tài liệu, tên file, dung lượng định dạng gọn (KB/MB) và nút tải về mở trong tab mới.

### VI. Bảo vệ xác thực nghiêm ngặt (Authentication Gating & Zero-Flash)
1. **Ẩn hoàn toàn trên các trang xác thực (Zero Flash)**:
   - Chatbot không bao giờ xuất hiện trên `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-otp`.
2. **Gating đối với khách chưa đăng nhập**:
   - Khi bấm vào nút chat ở các trang công khai, hiển thị Modal chuẩn:
     - Tiêu đề: `Đăng nhập để sử dụng H4CARE Support`
     - Mô tả: `Vui lòng đăng nhập để sử dụng Trợ lý AI, tư vấn trực tiếp và lưu lịch sử trò chuyện của bạn.`
     - Nút bấm: `Đăng nhập ngay` (chuyển hướng `/login?redirect=...`) và `Để sau`.
3. **Xử lý đăng xuất**: Đóng widget, xóa sạch session tạm và reset tin nhắn về trạng thái ban đầu.

---

## 2. DANH SÁCH FILE ĐÃ THAY ĐỔI & HOÀN THIỆN

### Backend (FastAPI & Database)
- `apps/api/app/api/chat.py`: Chuẩn hóa câu chào mặc định mới, loại bỏ slogan quảng cáo và làm sạch quick replies.
- `apps/api/tests/test_chat_auth_and_responses.py`: Cập nhật bộ test kiểm tra câu chào và định danh mới (100% pass).

### Storefront (Next.js 14)
- `apps/storefront/src/lib/chatbot/conversation-storage.ts`: Thiết lập `INITIAL_WELCOME_CONTENT` mới, bổ sung hàm `migrateWelcomeMessage` nâng cấp phiên cũ SSR-safe.
- `apps/storefront/src/lib/chatbot/ai-service.ts`: Cập nhật `buildSystemPrompt`, intent `GREETING`, `IDENTITY` và fallback tự nhiên không quảng cáo.
- `apps/storefront/src/components/chatbot/ChatbotWidget.tsx`: Ẩn hoàn toàn khu vực gợi ý cố định trên ô nhập, kết nối trực tiếp tin nhắn vào thanh chat, thêm cơ chế dọn dẹp cache phiên cũ.
- `apps/storefront/src/components/chatbot/SuggestedPromptsModal.tsx`: Tích hợp đầy đủ các câu hỏi gợi ý trọng tâm vào 5 nhóm A-E, cho phép tìm kiếm và điền vào ô nhập mà không tự gửi.
- `apps/storefront/src/components/chatbot/ChatInput.tsx`: Menu 5 công cụ trong dấu `+`, điền nội dung từ modal gợi ý vào textarea an toàn.

---

## 3. KẾT QUẢ KIỂM THỬ VÀ BIÊN DỊCH

1. **Next.js Storefront Build**:
   - Lệnh: `npm --prefix apps/storefront run build`
   - Kết quả: **Thành công 100% (0 lỗi)**. 17/17 routes được sinh tĩnh/động hoàn chỉnh.
2. **Vite Web Admin Build**:
   - Lệnh: `npm --prefix apps/web run build`
   - Kết quả: **Thành công 100% trong 1.81s (0 lỗi)**. Chuyển đổi 2532 modules trơn tru.
3. **Backend Pytest Suite**:
   - Lệnh: `$env:PYTHONPATH="apps/api"; .venv\Scripts\pytest apps/api/tests/test_live_chat.py apps/api/tests/test_chat_auth_and_responses.py`
   - Kết quả: **6 passed / 6 tests (100%)**.
