# Kiểm tra và sửa nút trạng thái đơn Admin

## Phạm vi trước khi sửa

- Mục tiêu: bốn nút Xác nhận đơn, Đang giao hàng, Hoàn thành, Hủy đơn hoạt động theo điều kiện hiện có và thông báo rõ ngay trong cửa sổ chi tiết.
- Phiên bản làm mốc: main, commit f360b36887867476085520c08136041710dd0043; checkout ban đầu sạch.
- Branch: fix/admin-order-status-actions.
- File dự kiến: API đơn hàng, policy điều kiện dùng chung, OrdersPage, component các nút và test; cập nhật tài liệu kiểm tra và bài học GEMINI.
- API: thêm trường `status_actions` vào GET /api/v1/admin/orders/{id}; không bỏ trường cũ. PATCH giữ nguyên quyền ADMIN, validation và hợp đồng response.
- Database: không migration, không thay dữ liệu vận hành.
- Vai trò: ADMIN dùng các nút; CUSTOMER, WAREHOUSE_MANAGER, WAREHOUSE_STAFF vẫn không được dùng API admin.
- Luồng giữ nguyên: phân quyền, điều kiện kiện hàng, thanh toán, tồn kho, hoàn tiền, ảnh sản phẩm và storefront.
- Rủi ro: frontend cần backend đã hỗ trợ trường mới; thay đổi đồng thời ở kho có thể làm metadata cũ. Mutation luôn xác minh dữ liệu DB hiện tại.
- Tiêu chí: điều kiện nút khớp backend, thông báo trong modal, cập nhật từ server, test quyền và chuyển trạng thái qua, build qua.

## Kết quả và nguyên nhân

Trạng thái: đã sửa code và kiểm thử local; chưa triển khai hoặc xác nhận trên website/tài khoản thật.

Ảnh đính kèm xác định đúng bốn nút ở cuối modal. API đã dùng `require_roles(UserRole.ADMIN)` và test gốc xác nhận admin chuyển PENDING -> CONFIRMED thành công. Ảnh không có HTTP status hoặc nội dung lỗi, nên chưa có bằng chứng kết luận tài khoản thật bị 403.

Hai lỗi được xác minh bằng code:

1. UI bật cả bốn nút trên mọi đơn chưa kết thúc, dù backend chặn chuyển sai thứ tự, giao khi chưa SHIPPED, hoàn thành khi chưa DELIVERED, hủy sau khi xuất kho.
2. `notification` hiển thị ở trang nền, nằm ngoài lớp modal z-index 1000. Thông báo lỗi/thành công bị che trong lúc bấm nút.

Thay đổi:

- Backend cung cấp các thao tác được phép và lý do chưa thực hiện được; validation mutation dùng cùng policy như trước.
- Nút không đủ điều kiện bị khóa và có lý do đọc được, có nút làm mới sau khi kho cập nhật tiến độ.
- Lỗi và thành công hiển thị trong panel thao tác ở modal, dùng role alert/status.
- Giao diện lấy trạng thái server sau thao tác; không tự gán trạng thái theo yêu cầu gửi đi.
- Khóa request bằng ref chống bấm lặp trong cùng giao diện; chặn thao tác đơn và kiện đồng thời. Không tuyên bố cung cấp idempotency phân tán mới.
- Nếu đã lưu nhưng tải chi tiết thất bại, nói rõ đã lưu, khóa điều kiện cũ và hướng dẫn làm mới.
- Không thay đổi quyền truy cập hoặc quy tắc thanh toán; không cập nhật payment_status thủ công.

## Kiểm thử và bằng chứng

Môi trường: Python 3.12, Node 24, dependency theo requirements và npm lockfile hiện có. Test sử dụng SQLite riêng; không dùng dữ liệu hoặc dịch vụ thanh toán thật.

Làm mốc trước sửa:

- `PYTHONPATH=apps/api python -m pytest -q apps/api/tests/test_orders.py apps/api/tests/test_order_security.py`: 11 passed.
- `npm test` tại apps/web: 2 passed.
- `npm run build` tại apps/web: passed.
- Test mới `test_pending_order_explains_unavailable_actions` thất bại trên code cũ vì thiếu status_actions; qua sau sửa.

Sau sửa:

- `PYTHONPATH=apps/api python -m pytest -q apps/api/tests/test_admin_order_status_actions.py apps/api/tests/test_orders.py apps/api/tests/test_order_security.py --tb=short`: **25 passed**.
- Test mới bao phủ đủ bốn thao tác ADMIN hợp lệ, mutation/DB đồng nhất, ba role khác bị 403, khách chưa đăng nhập bị 401, chặn chuyển trạng thái sai, metadata cũ không thể vượt validation backend.
- `npm test` tại apps/web: **7 passed** (5 test mới panel thao tác).
- `npm run build`: **passed**, gồm TypeScript build.
- ESLint cho OrdersPage và component/test mới: **0 errors**, 12 warnings có sẵn ở OrdersPage (import/biến cũ chưa dùng và dependencies effect cũ).
- Ruff cho policy và test Python mới: **passed**.
- `git diff --check`: **passed**.

Kiểm tra rộng hơn: `test_order_cancellation_notifications.py` có 3 test qua, 1 test lỗi ở kỳ vọng nội dung thông báo của thao tác kiện đã hủy. Đã chạy lại đúng test thất bại trong worktree sạch tại commit gốc f360b36 và gặp cùng lỗi: test mong “đã bị hủy”, API trả thông báo state machine CANCELLED -> PICKING bị chặn. Đây là lỗi có sẵn; không sửa test hoặc module kho ngoài phạm vi.

Kiểm tra trình duyệt: đã chuẩn bị fixture SQLite riêng và server chạy local. Playwright không khởi chạy vì thiếu Chromium; tải Chromium thất bại với lỗi tệp ZIP không hợp lệ. **Chưa xác minh click/visual bằng trình duyệt, responsive mobile hoặc website production.** Không sử dụng kết quả render component làm bằng chứng browser E2E.

## Ma trận ảnh hưởng

| Khu vực | Ảnh hưởng | Kiểm tra |
|---|---|---|
| Quyền Admin, auth | Giữ quyền, bổ sung test | 401/403 và ADMIN hợp lệ qua |
| Đơn hàng | Có | 4 thao tác, điều kiện và DB qua |
| Kiện hàng | Đọc điều kiện, refresh UI | guard SHIPPED/DELIVERED và metadata cũ qua |
| Kho/tồn kho | Không đổi thuật toán | hủy đơn hiện có và test đơn hàng; lỗi thông báo cũ ghi riêng |
| Thanh toán/hoàn tiền | Không đổi | test cũ cấm PATCH payment_status qua |
| Storefront/sản phẩm/ảnh | Không đổi | test đặt đơn và quyền tra cứu cũ qua |
| Database/migration | Không đổi | SQLite test riêng; không chạm DB thật |

## Áp dụng và hoàn tác

1. Review/merge PR khi sẵn sàng áp dụng.
2. Triển khai backend cùng frontend Admin; nếu triển khai riêng, backend trước. Không cần migration hoặc secret mới.
3. Đăng nhập bằng tài khoản ADMIN thật, mở một đơn có trạng thái và kiện hàng xác định. Kiểm tra API detail có status_actions, bấm thao tác hợp lệ và xem kết quả ngay trong modal.
4. Nếu còn báo 401/403, đối chiếu response `/auth/me`, role tài khoản và phiên đăng nhập trên đúng môi trường. Không tự sửa DB để nâng quyền, không tắt authorization.
5. Hoàn tác bằng revert commit bản sửa và triển khai lại cả backend/ứng dụng Admin theo quy trình hiện có.

## Dữ liệu và Git

- Database/test token/browser fixture chỉ ở môi trường scratch riêng, không đưa vào commit hoặc production.
- Chỉ stage tám file nguồn/test/tài liệu của nhiệm vụ; không commit dependency, dist, storage, database hay token.
- Không merge main hoặc triển khai website trong nhiệm vụ này.
