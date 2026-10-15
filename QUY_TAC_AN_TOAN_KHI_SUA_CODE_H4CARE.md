# QUY TẮC AN TOÀN KHI SỬA CODE H4CARE / PHARMATRUST

> Tệp này là quy tắc bắt buộc dành cho lập trình viên, Antigravity, Codex và các công cụ AI trước khi sửa mã nguồn dự án. Mục tiêu là sửa đúng lỗi được giao, không làm hỏng phần đang chạy tốt và không tạo ảnh hưởng ngoài phạm vi.

## 1. Cách sử dụng tệp này

1. Đặt tệp tại thư mục gốc của repository.
2. Đọc toàn bộ tệp trước mỗi lần sửa code.
3. Mỗi yêu cầu sửa phải có phạm vi, tiêu chí hoàn thành và danh sách kiểm thử riêng.
4. Không được bắt đầu sửa nếu chưa xác định được luồng hiện tại và phần có thể bị ảnh hưởng.
5. Nếu yêu cầu chưa rõ, phải hỏi người dùng; không tự suy đoán.

## 2. Kiến trúc cần kiểm tra trước khi sửa

Kiến trúc hiện tại có thể gồm:

- `apps/api`: Backend Python/FastAPI, database, migration, service và API.
- `apps/web`: Giao diện Admin.
- `apps/storefront`: Giao diện khách hàng.
- Module đơn hàng, kho, lô thuốc, nhập hàng, điều chuyển, đổi trả, hoàn tiền, thanh toán và email.

Đây chỉ là thông tin định hướng. Trước khi sửa phải kiểm tra lại cấu trúc repository hiện tại, không được giả định tên file, model, API hoặc framework vẫn giống phiên bản cũ.

## 3. Nguyên tắc bắt buộc

### 3.1. Chỉ sửa đúng phạm vi

- Chỉ sửa file cần thiết cho yêu cầu hiện tại.
- Không sửa giao diện, API, database hoặc nghiệp vụ không liên quan.
- Không đổi tên hàng loạt file, class, biến hoặc endpoint nếu không bắt buộc.
- Không chạy công cụ format trên toàn repository.
- Không nâng phiên bản thư viện chỉ vì có phiên bản mới.
- Không tái cấu trúc toàn bộ module trong một yêu cầu sửa lỗi nhỏ.
- Không gộp nhiều lỗi không liên quan vào cùng một thay đổi.
- Nếu phát hiện lỗi khác, ghi vào báo cáo; không tự sửa khi chưa được cho phép.

### 3.2. Bảo vệ code đang chạy tốt

- Phải chạy test hoặc kiểm tra luồng hiện tại trước khi thay đổi để có kết quả làm mốc.
- Chức năng đã chạy tốt phải có test hồi quy trước hoặc trong cùng lần sửa.
- Không xóa code cũ cho đến khi xác nhận không còn nơi nào sử dụng.
- Không thay đổi response API hiện có nếu chưa kiểm tra tất cả nơi đang gọi API đó.
- Nếu cần thay API, phải giữ tương thích ngược hoặc có kế hoạch chuyển đổi rõ ràng.
- Không thay đổi dữ liệu mẫu, tài khoản seed hoặc cấu hình chạy chỉ để test vượt qua.
- Không che lỗi bằng `try/catch` trả dữ liệu rỗng hoặc thông báo thành công giả.

### 3.3. Không đoán mò

Phải dừng và hỏi người dùng nếu thiếu một trong các thông tin sau:

- Vai trò nào được phép thực hiện nghiệp vụ.
- Kho nào sở hữu đơn hàng hoặc tồn kho.
- Quy tắc tính giá, giảm giá, phí vận chuyển hoặc hoàn tiền.
- Trạng thái trước và sau của đơn hàng.
- Quy tắc xử lý thuốc kê đơn, thuốc bị thu hồi hoặc thuốc chưa được duyệt.
- Cách xử lý dữ liệu cũ khi thay đổi database.
- Credential hoặc môi trường sandbox của dịch vụ bên ngoài.
- Yêu cầu có làm thay đổi giao diện đang được giữ nguyên hay không.

## 4. Quy trình bắt buộc trước khi sửa

### Bước 1: Xác nhận phiên bản

Ghi lại:

- Branch hiện tại.
- Commit hiện tại.
- Kết quả `git status`.
- Các thay đổi chưa commit của người dùng.
- Phiên bản Python, Node.js và database đang sử dụng nếu có liên quan.

Không ghi đè, hoàn tác hoặc xóa thay đổi chưa commit của người dùng.

### Bước 2: Tái hiện lỗi

- Viết lại các bước gây lỗi.
- Ghi kết quả mong đợi.
- Ghi kết quả thực tế.
- Lưu status code và thông báo lỗi cần thiết.
- Không sử dụng dữ liệu thật hoặc giao dịch thật để tái hiện.

Không sửa nếu chưa tái hiện được lỗi, trừ khi người dùng xác nhận rõ rằng chỉ cần thay đổi theo đặc tả mới.

### Bước 3: Lập bản đồ ảnh hưởng

Trước khi viết code, phải liệt kê:

- File dự kiến sửa.
- Model/database liên quan.
- API liên quan.
- Giao diện gọi API.
- Vai trò bị ảnh hưởng.
- Luồng nghiệp vụ liên quan.
- Test cần chạy.
- Dữ liệu cũ cần bảo toàn.

Nếu thay đổi ảnh hưởng từ ba module trở lên, phải chia thành các bước nhỏ và kiểm tra sau từng bước.

### Bước 4: Chạy kiểm tra làm mốc

Chạy các test liên quan trước khi sửa. Ghi rõ test nào đã lỗi từ trước và test nào phát sinh sau thay đổi.

Không được tuyên bố một lỗi do thay đổi mới gây ra nếu lỗi đó đã tồn tại trong kết quả làm mốc.

## 5. Hợp đồng phạm vi thay đổi

Trước khi sửa, phải tạo bản tóm tắt theo mẫu:

```text
Mục tiêu:
Không thay đổi:
File dự kiến sửa:
Database/API bị ảnh hưởng:
Vai trò bị ảnh hưởng:
Rủi ro:
Test làm mốc:
Tiêu chí hoàn thành:
```

Nếu trong lúc làm cần sửa thêm file hoặc mở rộng phạm vi, phải giải thích lý do. Nếu đó là thay đổi nghiệp vụ mới, phải xin xác nhận trước.

## 6. Quy tắc sửa backend và API

- Backend phải là nguồn quyết định cuối cùng cho quyền hạn, giá, tồn kho, trạng thái và số tiền.
- Không tin `user_id`, `warehouse_id`, role, giá, số tiền hoàn hoặc trạng thái do frontend gửi lên.
- Lấy danh tính và phạm vi kho từ access token hoặc session hợp lệ.
- Token sai hoặc hết hạn phải trả `401`, không được âm thầm chuyển thành khách vãng lai.
- Vượt quyền phải trả `403`.
- Không trả lỗi hệ thống dưới dạng thông báo thành công.
- Không để API thành công khi transaction đã rollback.
- Các thao tác quan trọng phải có idempotency để chống bấm hoặc gửi lặp.
- Không trả `password_hash`, secret, token, SMTP password hoặc khóa thanh toán trong response.
- Không log dữ liệu bí mật.
- Danh sách lớn phải có phân trang, lọc và giới hạn hợp lý.
- Tránh truy vấn N+1 và không tải toàn bộ bảng khi giao diện chỉ cần một trang dữ liệu.
- Endpoint mới phải có schema request/response và test phân quyền.

## 7. Quy tắc sửa frontend

- Giữ nguyên giao diện nếu yêu cầu không nói thay đổi thiết kế.
- Không làm thay đổi trang hoặc component không liên quan.
- Không viết cứng `localhost`, URL API, ID sản phẩm, ID kho hoặc tài khoản vào component.
- Sử dụng cấu hình môi trường hoặc API client dùng chung.
- Khi cần đăng nhập, phải gửi access token đúng cách.
- Phân biệt rõ trạng thái `loading`, `success`, `empty` và `error`.
- Không biến lỗi `401`, `403`, `404` hoặc `500` thành danh sách rỗng.
- Không chỉ ẩn nút để phân quyền; backend vẫn phải từ chối thao tác trái phép.
- Không tải toàn bộ dữ liệu khi trang chỉ hiển thị một phần.
- Các thay đổi form phải giữ dữ liệu người dùng khi request thất bại.
- Mọi nút tạo giao dịch phải có trạng thái đang xử lý và chống bấm lặp.

## 8. Quy tắc database và migration

- Không sửa database production trực tiếp.
- Không xóa bảng hoặc cột cũ khi chưa có kế hoạch chuyển dữ liệu.
- Không chỉnh sửa migration đã chạy trên môi trường khác; tạo migration mới.
- Migration phải có khả năng chạy trên database đang có dữ liệu.
- Trường mới nên có giá trị mặc định hoặc cho phép null trong giai đoạn chuyển đổi nếu cần.
- Phải có kế hoạch backfill cho dữ liệu cũ.
- Backfill cần chế độ `dry-run`, báo cáo dòng thành công, bỏ qua và xung đột.
- Không tự gán dữ liệu nếu có nhiều bản ghi khớp hoặc quan hệ không chắc chắn.
- Mọi Foreign Key, unique constraint và index mới phải được kiểm tra với dữ liệu hiện tại.
- Không dùng lệnh xóa database để giải quyết lỗi migration.
- Test phải sử dụng database riêng, không dùng database thật.

## 9. Quy tắc dữ liệu thuốc và tồn kho

- Admin quản lý dữ liệu thuốc gốc; kho quản lý tồn kho, lô và vị trí lưu trữ.
- Không tạo bản sao thuốc cho từng kho.
- Tồn kho phải liên kết bằng `product_id`/`sku_id`, `warehouse_id` và `batch_id`.
- Thuốc chưa có trong dữ liệu gốc không được tự động đưa vào bán.
- Thuốc mới từ file kho phải chuyển sang hàng chờ Admin duyệt.
- Không cho sửa tồn kho bằng cách cập nhật trực tiếp một con số mà không có chứng từ.
- Mọi thay đổi tồn phải tạo Inventory Movement và Audit Log.
- Không bán hoặc phân bổ lô hết hạn, bị cách ly hoặc bị thu hồi.
- Xuất kho phải tuân theo FEFO nếu nghiệp vụ yêu cầu.
- Hủy đơn phải giải phóng lượng hàng đã giữ đúng một lần.
- Nhập file lặp lại không được cộng tồn kho hai lần.
- Không sửa dữ liệu y tế gốc từ giao diện quản lý kho.

## 10. Quy tắc đơn hàng và phân quyền kho

- `Order` là đơn chung của khách hàng; `Fulfillment` là phần việc của một kho.
- Không đếm trùng Order khi một đơn có nhiều Fulfillment.
- Mỗi kho chỉ xem và xử lý Fulfillment thuộc kho mình.
- `warehouse_id` phải được xác định và kiểm tra tại backend.
- Quản lý kho không được xem hoặc sửa đơn của kho khác bằng cách đổi ID.
- Nhân viên kho chỉ xem công việc thuộc kho và phạm vi được giao.
- Mỗi mặt hàng giao cho khách phải truy được kho và lô đã xuất.
- Không được bỏ qua state machine của đơn hàng.
- Không chuyển đơn sang hoàn thành nếu chưa qua các bước nghiệp vụ bắt buộc.

## 11. Quy tắc đổi trả và hoàn tiền

- Hàng trả phải quay về kho thực tế đã giao sản phẩm, không tự chọn kho gần nhất.
- Nhân viên kho được tiếp nhận, kiểm hàng và tải bằng chứng.
- Nhân viên kho không được phê duyệt cuối cùng hoặc thực hiện hoàn tiền.
- Quản lý kho chỉ duyệt và hoàn tiền cho phần hàng thuộc kho mình.
- Số tiền hoàn phải do backend tính từ dữ liệu đơn gốc.
- Không cho frontend quyết định số tiền hoàn.
- Không hoàn vượt số tiền đã thanh toán.
- Không hoàn một Return Item hai lần.
- Thao tác hoàn tiền phải có idempotency, khóa đồng thời và Audit Log.
- Timeout từ cổng thanh toán không đồng nghĩa với thất bại; phải đối soát trước khi thử lại.
- Test hoàn tiền phải dùng mock hoặc sandbox, không giao dịch thật.

## 12. Quy tắc tài khoản và mật khẩu

- Không lưu hoặc hiển thị mật khẩu dạng văn bản thuần.
- Không tạo chức năng xem lại mật khẩu hiện tại.
- Admin hoặc quản lý kho chỉ được đặt lại mật khẩu theo phạm vi quyền hạn.
- Mật khẩu tạm thời chỉ hiển thị một lần và bắt buộc đổi ở lần đăng nhập tiếp theo.
- Không gửi `password_hash` về frontend.
- Reset mật khẩu phải thu hồi phiên đăng nhập cũ nếu hệ thống hỗ trợ.
- Quản lý kho chỉ quản lý tài khoản nhân viên thuộc kho mình.
- Không commit tài khoản, mật khẩu hoặc token thật vào repository.

## 13. Dịch vụ bên ngoài và bí mật

- Không gọi thật MoMo, PayOS, VNPay, VietQR, SMTP, Telegram, Google Maps hoặc website nhà thuốc trong test tự động.
- Chỉ dùng mock hoặc sandbox.
- Không tự tạo hoặc suy đoán API key.
- Không in biến môi trường bí mật ra terminal, log hoặc báo cáo.
- `.env` không được commit.
- `.env.example` chỉ chứa tên biến và giá trị mẫu không bí mật.
- Nếu credential bị lộ, phải thu hồi và tạo credential mới; chỉ xóa khỏi file là chưa đủ.
- Crawler không được vượt CAPTCHA, rate limit, robots.txt hoặc cơ chế chặn truy cập.

## 14. Cách viết code an toàn

- Ưu tiên thay đổi nhỏ, rõ ràng và có thể hoàn tác.
- Tái sử dụng service, schema và component hiện có nếu đúng chức năng.
- Không sao chép logic nghiệp vụ sang nhiều nơi.
- Không dùng ID giả hoặc fallback sang một sản phẩm thật để che dữ liệu thiếu.
- Không thêm `except Exception: pass`.
- Không trả dữ liệu mẫu khi API thật lỗi, trừ khi chế độ demo được bật rõ ràng.
- Không dùng comment để vô hiệu hóa test lỗi.
- Không giảm mức kiểm tra hoặc bỏ validation chỉ để luồng chạy qua.
- Không xóa test đang thất bại mà phải tìm nguyên nhân.
- Không thay đổi kỳ vọng test để hợp thức hóa hành vi sai.

## 15. Kiểm thử bắt buộc sau khi sửa

Tối thiểu phải chạy:

```text
Frontend build
Frontend unit test
Frontend lint hoặc type-check
Backend unit test liên quan
Backend integration test liên quan
Test phân quyền
Test hồi quy của lỗi vừa sửa
```

Nếu repository hỗ trợ các lệnh sau thì chạy:

```bash
npm run build
npm test
npm run lint
PYTHONPATH=apps/api pytest -q
```

Không được ghi “đã sửa xong” nếu:

- Build chưa chạy.
- Test liên quan chưa chạy.
- Test mới chưa được thêm.
- Còn lỗi `500` trong luồng vừa sửa.
- Chưa kiểm tra phân quyền.
- Chưa kiểm tra dữ liệu cũ.
- Chưa kiểm tra tác động tới các luồng đang chạy tốt.

Nếu toàn bộ test không thể chạy do lỗi môi trường, phải ghi rõ:

- Lệnh đã chạy.
- Lỗi môi trường.
- Phần nào đã kiểm tra được.
- Phần nào chưa thể xác nhận.

Không được tuyên bố “không còn lỗi” khi chưa chạy đầy đủ.

## 16. Ma trận kiểm tra ảnh hưởng

Sau mỗi thay đổi, đánh dấu các mục liên quan:

| Khu vực | Có ảnh hưởng? | Kiểm tra đã chạy | Kết quả |
|---|---:|---|---|
| Đăng nhập và token |  |  |  |
| Phân quyền Admin |  |  |  |
| Phân quyền quản lý kho |  |  |  |
| Phân quyền nhân viên kho |  |  |  |
| Storefront khách hàng |  |  |  |
| Sản phẩm/SKU |  |  |  |
| Kho và tồn kho |  |  |  |
| Lô và hạn sử dụng |  |  |  |
| Nhập kho/import file |  |  |  |
| Điều chuyển kho |  |  |  |
| Đơn hàng |  |  |  |
| Thanh toán |  |  |  |
| Đổi trả |  |  |  |
| Hoàn tiền |  |  |  |
| Email/thông báo |  |  |  |
| Audit Log |  |  |  |
| Database/migration |  |  |  |

Không cần chạy mọi test cho mọi thay đổi, nhưng phải giải thích vì sao khu vực nào không bị ảnh hưởng.

## 17. Quy tắc Git

- Tạo branch riêng cho mỗi nhiệm vụ.
- Không sửa trực tiếp `main`.
- Không dùng `git reset --hard` hoặc lệnh phá hủy thay đổi người dùng.
- Không force-push nếu chưa được cho phép.
- Mỗi commit chỉ nên chứa một nhóm thay đổi có liên quan.
- Không commit `.env`, database, ảnh tải về, file build, `node_modules` hoặc `.venv`.
- Kiểm tra `git diff` trước khi commit.
- Không đưa thay đổi format không liên quan vào commit.
- Commit message phải mô tả đúng nghiệp vụ được sửa.

## 18. Điều kiện bắt buộc phải dừng

Dừng sửa và hỏi người dùng khi:

- Phạm vi thực tế lớn hơn yêu cầu ban đầu.
- Cần xóa bảng, cột, file hoặc dữ liệu.
- Cần đổi cấu trúc phân quyền.
- Cần quyết định quy tắc tài chính hoặc y tế chưa được xác nhận.
- Cần credential mới.
- Cần gọi dịch vụ thật.
- Migration có nguy cơ làm mất dữ liệu.
- Có thay đổi chưa commit của người dùng trùng với file cần sửa.
- Không thể tái hiện lỗi nhưng thay đổi có rủi ro cao.
- Test phát hiện hành vi hiện tại mâu thuẫn với yêu cầu mới.

## 19. Báo cáo bắt buộc sau mỗi lần sửa

Sử dụng mẫu:

```markdown
## Kết quả

- Lỗi/yêu cầu đã xử lý:
- Nguyên nhân gốc:
- Trạng thái: Hoàn thành / Chưa hoàn thành / Bị chặn

## Phạm vi thay đổi

- File đã sửa:
- File đã thêm:
- Migration:
- API thay đổi:
- Giao diện thay đổi:

## Phần không thay đổi

- Các module được giữ nguyên:
- Lý do xác nhận không ảnh hưởng:

## Kiểm thử

- Lệnh:
- Kết quả:
- Test hồi quy mới:
- Test phân quyền:

## Dữ liệu

- Dữ liệu test đã tạo:
- Cách dọn dữ liệu test:
- Dữ liệu cũ được bảo toàn như thế nào:

## Rủi ro còn lại

- Phần chưa kiểm tra:
- Credential hoặc sandbox còn thiếu:
- Việc cần người dùng xác nhận:

## Git

- Branch:
- Commit:
- `git status` sau khi hoàn thành:
```

## 20. Mẫu giao nhiệm vụ sửa code

Mỗi prompt sửa code nên bắt đầu bằng:

```text
Đọc toàn bộ file QUY_TAC_AN_TOAN_KHI_SUA_CODE_H4CARE.md trước khi làm.

Nhiệm vụ:
[Mô tả duy nhất một lỗi hoặc một nhóm chức năng liên quan]

Phạm vi được phép sửa:
[Danh sách module/file nếu đã biết]

Không được thay đổi:
[Danh sách chức năng đang chạy tốt cần giữ nguyên]

Cách tái hiện:
[Các bước gây lỗi]

Kết quả hiện tại:
[Kết quả sai]

Kết quả mong đợi:
[Kết quả đúng]

Tiêu chí hoàn thành:
[Danh sách kiểm tra]

Nếu phát hiện cần mở rộng phạm vi, dừng và hỏi trước; không tự sửa thêm.
```

## 21. Định nghĩa hoàn thành

Một thay đổi chỉ được coi là hoàn thành khi:

1. Nguyên nhân gốc đã được xác định.
2. Thay đổi chỉ nằm trong phạm vi cho phép.
3. Có test hồi quy cho lỗi đã sửa.
4. Các test liên quan cũ vẫn đạt.
5. Build thành công.
6. Phân quyền được kiểm tra tại backend.
7. Không làm mất hoặc sửa sai dữ liệu cũ.
8. Không còn dữ liệu test trong database dùng thật.
9. `git diff` không chứa thay đổi ngoài nhiệm vụ.
10. Báo cáo cuối cùng nêu rõ phần đã và chưa kiểm tra.

---

**Quy tắc cuối cùng:** Ưu tiên bảo toàn hệ thống đang hoạt động. Một bản sửa nhỏ, được kiểm thử và có thể hoàn tác tốt hơn một thay đổi lớn không kiểm soát được tác động.
