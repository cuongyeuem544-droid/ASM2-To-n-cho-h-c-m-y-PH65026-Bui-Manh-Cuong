import hashlib
import io
import logging
from pathlib import Path
from typing import Tuple

import httpx
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_product_storage_dir() -> Path:
    """Trả về thư mục lưu trữ ảnh sản phẩm cục bộ."""
    dir_path = settings.storage_root.resolve() / "products"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def download_and_optimize_image(remote_url: str, product_id: int) -> Tuple[str | None, str | None]:
    """
    Tải ảnh từ URL bên ngoài, tối ưu hóa định dạng WebP và tạo thumbnail.
    
    Returns:
        tuple (local_image_url, local_thumbnail_url) hoặc (None, None) nếu thất bại.
    """
    if not remote_url:
        return None, None

    # Nếu URL đã là ảnh nội bộ thì không cần tải lại
    if remote_url.startswith(("/storage/", "http://127.0.0.1:8000/storage", "http://localhost:8000/storage")):
        return remote_url, None

    if not remote_url.startswith(("http://", "https://")):
        return None, None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            resp = client.get(remote_url, headers=headers)
            if resp.status_code != 200 or not resp.content:
                logger.warning(f"Không thể tải ảnh sản phẩm {product_id} từ {remote_url} (HTTP {resp.status_code})")
                return None, None

            content_type = resp.headers.get("content-type", "").lower()
            content = resp.content

            # Tạo hash định danh duy nhất cho nội dung ảnh
            content_hash = hashlib.sha256(content).hexdigest()[:10]
            storage_dir = get_product_storage_dir()

            # Tên file cho bản chính (max 800x800 WebP) và thumbnail (max 250x250 WebP)
            main_filename = f"prod_{product_id}_{content_hash}.webp"
            thumb_filename = f"prod_{product_id}_{content_hash}_thumb.webp"

            main_path = storage_dir / main_filename
            thumb_path = storage_dir / thumb_filename

            # Nếu cả 2 file đã tồn tại trên đĩa thì tái sử dụng
            if main_path.exists() and thumb_path.exists():
                return f"/storage/products/{main_filename}", f"/storage/products/{thumb_filename}"

            try:
                img = Image.open(io.BytesIO(content))
                
                # Chuyển đổi định dạng phù hợp cho WebP
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    # Giữ kênh Alpha
                    img = img.convert("RGBA")
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                # 1. Tối ưu ảnh chính (kích thước tối đa 800x800)
                main_img = img.copy()
                main_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                main_img.save(main_path, "WEBP", quality=85, optimize=True)

                # 2. Tạo thumbnail nhỏ (kích thước tối đa 250x250)
                thumb_img = img.copy()
                thumb_img.thumbnail((250, 250), Image.Resampling.LANCZOS)
                thumb_img.save(thumb_path, "WEBP", quality=80, optimize=True)

                logger.info(f"Đã lưu và tối ưu ảnh sản phẩm {product_id} thành WebP: {main_filename}")
                return f"/storage/products/{main_filename}", f"/storage/products/{thumb_filename}"

            except Exception as img_err:
                logger.warning(f"Lỗi khi xử lý nén WebP bằng Pillow cho {remote_url}: {img_err}. Lưu ảnh thô.")
                # Fallback lưu dữ liệu thô nếu Pillow không phân tích được
                ext = ".jpg" if "jpeg" in content_type else (".png" if "png" in content_type else ".bin")
                raw_filename = f"prod_{product_id}_{content_hash}{ext}"
                raw_path = storage_dir / raw_filename
                raw_path.write_bytes(content)
                return f"/storage/products/{raw_filename}", None

    except Exception as e:
        logger.warning(f"Ngoại lệ khi tải ảnh từ {remote_url}: {e}")
        return None, None


def backfill_product_images(db: Session, max_items: int = 50) -> dict:
    """
    Quét và tải ảnh nội bộ cho các thuốc chưa có local_image_url.
    """
    from app.models import CanonicalProduct

    products = (
        db.query(CanonicalProduct)
        .filter(
            CanonicalProduct.image_url.isnot(None),
            CanonicalProduct.local_image_url.is_(None),
            CanonicalProduct.image_url.like("http%"),
        )
        .limit(max_items)
        .all()
    )

    succeeded = 0
    failed = 0

    for prod in products:
        main_url, thumb_url = download_and_optimize_image(prod.image_url, prod.id)
        if main_url:
            prod.local_image_url = main_url
            prod.local_thumbnail_url = thumb_url
            succeeded += 1
        else:
            failed += 1

    if succeeded > 0:
        db.commit()

    return {
        "total_scanned": len(products),
        "succeeded": succeeded,
        "failed": failed,
    }

def validate_image_magic_bytes(content: bytes) -> str:
    """
    Xác minh chữ ký nhị phân (magic bytes) để đảm bảo tệp thực sự là ảnh hợp lệ.
    Trả về định dạng ("JPEG", "PNG", "WEBP", "AVIF", "GIF") hoặc ném ValueError.
    """
    if len(content) < 12:
        raise ValueError("Tệp tin quá nhỏ hoặc rỗng, không phải ảnh hợp lệ.")

    if content.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "WEBP"
    if b"ftyp" in content[:16] and (b"avif" in content[:32] or b"avis" in content[:32]):
        return "AVIF"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "GIF"

    raise ValueError("Định dạng tệp không được hỗ trợ hoặc không phải hình ảnh hợp lệ (chỉ chấp nhận JPEG, PNG, WebP, AVIF).")


def save_and_optimize_uploaded_image(
    content: bytes,
    product_id: int,
    original_filename: str = "",
) -> Tuple[str, str]:
    """
    Lưu và tối ưu ảnh tải lên từ Admin thành 2 bản:
    1. Ảnh chính: WebP tối đa 800x800, quality 85
    2. Thumbnail: WebP tối đa 250x250, quality 80
    """
    validate_image_magic_bytes(content)

    content_hash = hashlib.sha256(content).hexdigest()[:10]
    storage_dir = get_product_storage_dir()

    main_filename = f"prod_{product_id}_{content_hash}.webp"
    thumb_filename = f"prod_{product_id}_{content_hash}_thumb.webp"

    main_path = storage_dir / main_filename
    thumb_path = storage_dir / thumb_filename

    # Decode và xử lý bằng Pillow
    img = Image.open(io.BytesIO(content))

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # 1. Ảnh chính
    main_img = img.copy()
    main_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    main_img.save(main_path, "WEBP", quality=85, optimize=True)

    # 2. Thumbnail
    thumb_img = img.copy()
    thumb_img.thumbnail((250, 250), Image.Resampling.LANCZOS)
    thumb_img.save(thumb_path, "WEBP", quality=80, optimize=True)

    return f"/storage/products/{main_filename}", f"/storage/products/{thumb_filename}"

