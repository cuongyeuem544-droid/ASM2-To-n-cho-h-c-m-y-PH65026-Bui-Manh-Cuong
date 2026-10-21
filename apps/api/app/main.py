from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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

cors_kwargs = {
    "allow_origins": settings.cors_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["*"],
}
if settings.cors_origin_regex:
    cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex

app.add_middleware(CORSMiddleware, **cors_kwargs)
app.add_middleware(RateLimitMiddleware)
app.include_router(api_router)


@app.get("/health", tags=["Hệ thống"])
def root_health():
    """Endpoint kiểm tra trạng thái hoạt động của máy chủ (Root Health Check cho Render)."""
    return {"status": "ok", "service": "H4CARE API"}


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
    detail_str = "; ".join(msgs) if msgs else "Dữ liệu không hợp lệ"
    return JSONResponse(status_code=422, content={"detail": detail_str, "errors": jsonable_encoder(exc.errors())})


from app.core.config import _REPO_ROOT
web_dist_dir = (
    _REPO_ROOT / "apps" / "web" / "dist"
    if (_REPO_ROOT / "apps" / "web" / "dist").exists()
    else _REPO_ROOT / "web" / "dist"
)
assets_dir = web_dist_dir / "assets"
index_html = web_dist_dir / "index.html"

# Mount static files an toàn: Chỉ cho phép thư mục ảnh sản phẩm công khai (/storage/products).
# Tuyệt đối KHÔNG mount tĩnh thư mục storage/returns chứa tài liệu và hình ảnh đổi/trả nhạy cảm.
storage_dir = settings.storage_root.resolve()
storage_dir.mkdir(parents=True, exist_ok=True)
products_dir = storage_dir / "products"
products_dir.mkdir(parents=True, exist_ok=True)
app.mount("/storage/products", StaticFiles(directory=str(products_dir)), name="storage_products")

if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


@app.get("/")
def serve_root():
    if index_html.exists():
        return FileResponse(str(index_html))
    return {"name": settings.app_name, "docs": "/docs", "warning": "Chỉ đánh giá hồ sơ dữ liệu, không xác nhận an toàn y khoa."}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("storage/returns") or full_path == "storage/returns":
        return JSONResponse(status_code=403, content={"detail": "Truy cập tài liệu đổi/trả qua static URL bị từ chối vì lý do bảo mật. Vui lòng sử dụng API bảo mật có xác thực."})
    if full_path.startswith("api/") or full_path == "api" or full_path.startswith("storage/") or full_path == "storage":
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    target_file = web_dist_dir / full_path
    if target_file.is_file():
        return FileResponse(str(target_file))
    if index_html.exists():
        return FileResponse(str(index_html))
    return JSONResponse(status_code=404, content={"detail": "Not found"})
