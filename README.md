# PharmaTrust / H4CARE - Unified Healthcare & Medicine Data Ecosystem

Hệ sinh thái công nghệ y tế và dữ liệu thuốc tích hợp **PharmaTrust & H4CARE**, bao gồm sàn thương mại dược phẩm, cổng xử lý đơn thuốc điện tử (OCR + AI), hệ thống chuẩn hóa & đối soát dữ liệu thuốc quốc gia, và cổng quản trị vận hành chuyên sâu.

---

## 🏛️ Kiến trúc hệ thống & Phân bổ Cổng (Ports)

Hệ thống được tổ chức theo kiến trúc Monorepo phân tán với 3 dịch vụ chính:

| Dịch vụ | Thư mục | Công nghệ | Cổng / URL | Mô tả chức năng |
|---|---|---|---|---|
| **Storefront (Khách hàng)** | `apps/storefront` | Next.js 14 (App Router), Tailwind CSS, Framer Motion | [http://localhost:3000](http://localhost:3000) | Giao diện khách hàng: mua sắm thuốc, danh mục OTC/Rx, giỏ hàng, gửi đơn thuốc (OCR), thanh toán MoMo/COD, trang xác thực bảo mật H4CARE. |
| **Admin Data Hub** | `apps/web` | React 18, Vite, TypeScript | [http://localhost:5173](http://localhost:5173) | Cổng quản trị dữ liệu: đối soát ứng viên thuốc, chấm điểm tin cậy (Trust Score), quản lý nguồn thu thập (DAV, MFR, Retail), kiểm toán audit logs. |
| **Backend API** | `apps/api` | FastAPI, Python 3.11, SQLAlchemy, Alembic, Celery | [http://localhost:8000](http://localhost:8000) | Lõi API nghiệp vụ: Public API, tính điểm thuốc, xác thực JWT, thanh toán MoMo Sandbox, gửi email thông báo SMTP. |
| **Swagger / OpenAPI** | `apps/api` | FastAPI OpenAPI UI | [http://localhost:8000/docs](http://localhost:8000/docs) | Tài liệu kiểm thử API tương tác trực tiếp. |
| **Health Check API** | `apps/api` | REST Endpoint | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) | Giám sát trạng thái hoạt động của máy chủ backend. |

---

## 🚀 Khởi động nhanh (1-Click Startup trên Windows)

Các script tự động hóa được đặt sẵn tại thư mục gốc của dự án:

### 1. Khởi động toàn bộ hệ sinh thái (Khuyên dùng)
Nhấp đúp chuột vào:
```cmd
start.bat
```
*(Hoặc `run-local.bat` / `run-all.ps1` - tất cả đều đồng bộ chung một quy trình chuẩn hóa)*
- Tự động kiểm tra phiên bản Python 3.11/3.12 và Node.js 20+.
- Tự động tạo và kích hoạt môi trường ảo `.venv` nếu chưa có.
- Tự động cài đặt dependencies cho Backend (`apps/api`), Storefront (`apps/storefront`) và Admin Web (`apps/web`).
- Tự động khởi tạo file `.env` từ `.env.example` (bảo toàn cấu hình nếu `.env` đã có).
- Tự động thực thi Alembic database migration (`upgrade head`) và kiểm tra tính toàn vẹn single head.
- Tự động đồng bộ schema SQLite và nạp dữ liệu mẫu demo idempotent (kho hàng, tài khoản, danh mục thuốc).
- Khởi động đồng thời 3 dịch vụ với 3 cửa sổ log độc lập:
  1. **Backend FastAPI**: [http://localhost:8000](http://localhost:8000) (kèm Health Check tự động)
  2. **Storefront Next.js**: [http://localhost:3000](http://localhost:3000)
  3. **Admin Web Portal**: [http://localhost:5173](http://localhost:5173)
- Tự động mở trình duyệt sau khi Backend Health Check phản hồi HTTP 200 OK.

### 2. Khởi động riêng lẻ từng dịch vụ
- **Chỉ chạy Backend API (:8000)**: Chạy `run-backend.bat`
- **Chỉ chạy Frontend (:3000 & :5173)**: Chạy `run-frontend.bat`

### 3. Dừng toàn bộ hệ thống
Nhấp đúp chuột vào:
```cmd
stop-all.bat
```
Script sẽ tự động tìm và đóng toàn bộ các tiến trình đang lắng nghe trên các cổng `8000`, `3000` và `5173`.

---

## 🛠️ Cài đặt & Khởi động thủ công (Manual Setup)

### Yêu cầu tiên quyết
- **Node.js**: Phiên bản 20.x trở lên
- **Python**: Phiên bản 3.11 hoặc 3.12

### 1. Cấu hình Môi trường (Environment Variables)
Sao chép file `.env.example` thành `.env` tại thư mục gốc:
```bash
cp .env.example .env
```

Cấu trúc các file môi trường trong dự án:
- `/.env`: Biến môi trường dùng chung cho hệ sinh thái và Backend API.
- `/apps/api/.env.example`: Tài liệu biến môi trường chi tiết của Backend API.
- `/apps/storefront/.env.example`: Biến môi trường cho module xử lý đơn thuốc và Prisma của Storefront.
- `/apps/web/.env.example`: Cấu hình API URL cho Admin Hub.

### 2. Thiết lập Backend API
```bash
# Tạo môi trường ảo Python
python -m venv .venv

# Kích hoạt môi trường ảo
# Trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
source .venv/bin/activate

# Cài đặt thư viện phụ thuộc
pip install -r apps/api/requirements-dev.txt

# Khởi tạo dữ liệu mẫu ban đầu (SQLite)
python -m app.seed

# Khởi động Backend API
uvicorn app.main:app --app-dir apps/api --reload --host 0.0.0.0 --port 8000
```

### 3. Thiết lập Storefront (Next.js)
```bash
cd apps/storefront
npm install
npx prisma generate
npx prisma db push
npm run dev -- -p 3000
```

### 4. Thiết lập Admin Data Hub (Vite + React)
```bash
cd apps/web
npm install
npm run dev
```

---

## 🔐 Danh sách Tài khoản Demo Chuẩn hóa

| Cổng truy cập | Vai trò (Role) | Email đăng nhập | Mật khẩu demo | Quyền hạn chính |
|---|---|---|---|---|
| **Admin Portal (:5173)** | Quản trị toàn quyền (`ADMIN`) | `admin@pharmatrust.vn` | `Admin@123456` | Toàn quyền cấu hình, đối soát dữ liệu, quản trị hệ thống đa kho. |
| **Admin Portal (:5173)** | Quản lý kho HCM (`WAREHOUSE_MANAGER`) | `manager.hcm@pharmatrust.vn` | `Warehouse@2026` | Điều phối đơn hàng, tồn kho, ca đổi trả thuộc Kho HCM. |
| **Admin Portal (:5173)** | Nhân viên kho HCM (`WAREHOUSE_STAFF`) | `staff.hcm@pharmatrust.vn` | `Staff@2026` | Thực hiện soạn hàng, đóng gói, bàn giao vận chuyển tại Kho HCM. |
| **Admin Portal (:5173)** | Quản lý kho Hà Nội (`WAREHOUSE_MANAGER`) | `manager.hn@pharmatrust.vn` | `Warehouse@2026` | Điều phối đơn hàng, tồn kho, ca đổi trả thuộc Kho Hà Nội. |
| **Admin Portal (:5173)** | Nhân viên kho Hà Nội (`WAREHOUSE_STAFF`) | `staff.hn@pharmatrust.vn` | `Staff@2026` | Thực hiện soạn hàng, đóng gói, bàn giao vận chuyển tại Kho Hà Nội. |
| **Storefront (:3000)** | Khách hàng mua sắm (`CUSTOMER`) | `buyer@pharmatrust.vn` | `Buyer@123456` | Đặt hàng thuốc OTC/Rx, tra cứu đơn hàng, gửi yêu cầu trả hàng. |

---

## 🗄️ Cấu trúc Cơ sở dữ liệu

- **PharmaTrust Core Database**: Tệp SQLite `pharmatrust.db` tại thư mục gốc (hoặc PostgreSQL khi chạy qua Docker/Production). Quản lý danh mục thuốc chuẩn hóa, nguồn dữ liệu (DAV, MFR, Retail), điểm tin cậy, quy tắc hard-rules và audit logs.
- **Storefront Local Storage**: Tệp SQLite `apps/storefront/dev.db` phục vụ lưu trữ tiến trình tải lên, OCR và trích xuất AI của module đơn thuốc.

---

## 🧪 Kiểm thử & Đảm bảo Chất lượng (Quality Assurance)

### Kiểm tra Backend API (Pytest)
```bash
# Chạy toàn bộ 75+ test suites của backend
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
```

### Kiểm tra kiểu dữ liệu Frontend (TypeScript)
```bash
# Kiểm tra Next.js Storefront
cd apps/storefront && npx tsc --noEmit

# Kiểm tra Vite Admin Hub
cd apps/web && npx tsc --noEmit
```

---

## 🔒 Quy ước Bảo vệ Mã nguồn (Protected Scopes)
Phần giao diện và logic Xác thực (Authentication) của H4CARE đã được hoàn thiện và khóa cố định (`LOCKED`):
- `/login`, `/register`, `/forgot-password`, `/reset-password`
- Bộ component không gian `components/auth/*`
- Không tự ý sửa đổi hoặc refactor các route và component trên khi chưa có yêu cầu riêng biệt.
