from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.middleware import RateLimitMiddleware


from app.services.scheduler import scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.raw_storage.mkdir(parents=True, exist_ok=True)
    settings.upload_storage.mkdir(parents=True, exist_ok=True)
    # Khởi động Scheduler cào tự động 24/7
    if settings.auto_crawl_enabled:
        scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    version="1.1.1",
    description="Nền tảng đánh giá độ tin cậy hồ sơ dữ liệu thuốc. Không phải công cụ chẩn đoán hoặc tư vấn điều trị.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Order-Token", "X-Idempotency-Key"],
)
app.add_middleware(RateLimitMiddleware)
app.include_router(api_router)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

FIELD_NAMES_VI = {
    "customer_name": "Họ và tên người nhận",
    "customer_phone": "Số điện thoại nhận hàng",
    "shipping_address": "Địa chỉ nhận hàng",
    "shipping_city": "Tỉnh/Thành phố",
    "payment_method": "Phương thức thanh toán",
    "items": "Danh sách sản phẩm",
    "product_id": "Mã sản phẩm",
    "quantity": "Số lượng",
    "price": "Đơn giá",
}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    msgs = []
    for err in exc.errors():
        loc = err.get("loc", [])
        field = str(loc[-1]) if loc else "Trường dữ liệu"
        field_vi = FIELD_NAMES_VI.get(field, field)
        raw_msg = err.get("msg", "không hợp lệ")
        if "at least" in raw_msg:
            min_l = err.get("ctx", {}).get("min_length", "")
            msg = f"yêu cầu tối thiểu {min_l} ký tự" if min_l else "quá ngắn"
        elif "Field required" in raw_msg or err.get("type") == "missing":
            msg = "bắt buộc phải nhập"
        else:
            msg = raw_msg
        msgs.append(f"{field_vi}: {msg}")
    detail_str = "; ".join(msgs) if msgs else "Thông tin gửi lên không đúng định dạng."
    return JSONResponse(status_code=422, content={"detail": detail_str, "errors": exc.errors()})


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

web_dist_dir = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
assets_dir = web_dist_dir / "assets"
index_html = web_dist_dir / "index.html"

# Mount static files cho storage nội bộ (ảnh sản phẩm, tài liệu gốc)
storage_dir = settings.storage_root.resolve()
storage_dir.mkdir(parents=True, exist_ok=True)
(storage_dir / "products").mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(storage_dir)), name="storage")

if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/")
def serve_root():
    if index_html.exists():
        return FileResponse(str(index_html))
    return {"name": settings.app_name, "docs": "/docs", "warning": "Chỉ đánh giá hồ sơ dữ liệu, không xác nhận an toàn y khoa."}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path == "api" or full_path.startswith("storage/") or full_path == "storage":
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    target_file = web_dist_dir / full_path
    if target_file.is_file():
        return FileResponse(str(target_file))
    if index_html.exists():
        return FileResponse(str(index_html))
    return JSONResponse(status_code=404, content={"detail": "Not found"})
