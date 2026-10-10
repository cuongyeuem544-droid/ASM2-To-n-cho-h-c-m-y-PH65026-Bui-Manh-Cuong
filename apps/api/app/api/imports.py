from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import DataSource, User
from app.models.enums import SourceType, UserRole
from app.services.audit import write_audit
from app.services.importer import (
    ImportValidationError,
    generate_excel_template,
    import_rows,
    preview_import_rows,
)

router = APIRouter(prefix="/imports", tags=["Nhập dữ liệu thuốc & Lô kho"])

ALLOWED_MIME_TYPES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/octet-stream",
}


@router.get("/template")
def download_import_template(
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
):
    """
    Tải về tệp Excel mẫu chuẩn (.xlsx) để nhập danh mục thuốc, số lô và hạn dùng.
    """
    content = generate_excel_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="Mau_Nhap_Don_Thuoc_Pharmatrust.xlsx"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/preview")
async def preview_file(
    file: UploadFile = File(...),
    warehouse_id: Optional[int] = Form(None),
    batch_number: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    initial_quantity: Optional[int] = Form(100),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """
    Quét xem trước (Preview Scan) tệp Excel trước khi nhập kho chính thức.
    Thống kê tổng số thuốc, kiểm tra tính hợp lệ, nhận diện số lô và hạn dùng.
    """
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"MIME type '{file.content_type}' chưa được hỗ trợ")

    content = await file.read()
    try:
        preview_data = preview_import_rows(
            db=db,
            filename=file.filename or "upload.xlsx",
            content=content,
            warehouse_id=warehouse_id,
            default_batch_number=batch_number,
            default_expiry_date=expiry_date,
            default_quantity=initial_quantity,
        )
        return preview_data
    except (ImportValidationError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/file", status_code=201)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    warehouse_id: Optional[int] = Form(None),
    batch_number: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    initial_quantity: Optional[int] = Form(100),
    source_id: Optional[int] = Form(None),
    is_demo: bool = Form(False),
    force_update: bool = Form(True),
    auto_approve: bool = Form(True),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.DATA_REVIEWER)),
    db: Session = Depends(get_db),
):
    """
    Thực hiện nhập và lưu trữ thuốc, thiết lập số lô, hạn sử dụng và phân bổ tồn kho.
    """
    # Tự động gán DataSource nhập file thủ công nếu không truyền
    if source_id:
        source = db.get(DataSource, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Không tìm thấy nguồn dữ liệu")
    else:
        source = db.scalar(
            select(DataSource).where(
                DataSource.source_type.in_([SourceType.MANUAL_UPLOAD, SourceType.DEMO])
            )
        )
        if not source:
            source = DataSource(
                name="Tải lên tệp Excel đơn thuốc",
                code="EXCEL_IMPORT",
                source_type=SourceType.MANUAL_UPLOAD,
                is_active=True,
            )
            db.add(source)
            db.flush()

    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"MIME type '{file.content_type}' chưa được hỗ trợ")

    content = await file.read()
    try:
        result = import_rows(
            db=db,
            source_id=source.id,
            filename=file.filename or "upload.bin",
            content=content,
            is_demo=is_demo,
            force_update=force_update,
            auto_approve=auto_approve,
            warehouse_id=warehouse_id,
            default_batch_number=batch_number,
            default_expiry_date=expiry_date,
            default_quantity=initial_quantity,
        )
    except (ImportValidationError, UnicodeDecodeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    write_audit(
        db,
        "IMPORT_EXCEL_FILE",
        "DataSource",
        source.id,
        user,
        request,
        after={
            "filename": file.filename,
            "created": result.get("created"),
            "updated": result.get("updated"),
            "skipped": result.get("skipped"),
            "total_rows": result.get("total_rows"),
            "total_quantity": result.get("total_quantity"),
            "warehouse_id": warehouse_id,
            "batch_number": batch_number,
            "expiry_date": expiry_date,
            "is_demo": is_demo,
            "force_update": force_update,
            "auto_approve": auto_approve,
        },
    )
    db.commit()
    return {"message": "Đã nhập tệp và nhận diện thuốc vào kho thành công", **result}
