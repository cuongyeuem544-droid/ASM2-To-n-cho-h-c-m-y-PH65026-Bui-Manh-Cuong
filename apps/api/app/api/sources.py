from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import CrawlRun, DataSource, User
from app.models.enums import RunStatus, SourceType, UserRole
from app.schemas.data import CrawlRunOut, DataSourceCreate, DataSourceOut, DataSourceUpdate
from app.services.audit import write_audit
from app.tasks.jobs import crawl_source_task, execute_crawl


router = APIRouter(tags=["Nguồn dữ liệu"])


@router.get("/sources", response_model=list[DataSourceOut])
def list_sources(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(DataSource).order_by(DataSource.authority_level.desc(), DataSource.name)).all()


@router.post("/sources", response_model=DataSourceOut, status_code=201)
def create_source(
    payload: DataSourceCreate,
    request: Request,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    if db.scalar(select(DataSource.id).where(DataSource.code == payload.code)):
        raise HTTPException(status_code=409, detail="Mã nguồn đã tồn tại")
    source = DataSource(**payload.model_dump(mode="json"))
    db.add(source)
    db.flush()
    write_audit(db, "CREATE", "DataSource", source.id, admin, request, after=payload.model_dump(mode="json"))
    db.commit()
    db.refresh(source)
    return source


@router.patch("/sources/{source_id}", response_model=DataSourceOut)
def update_source(
    source_id: int,
    payload: DataSourceUpdate,
    request: Request,
    admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    source = db.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Không tìm thấy nguồn dữ liệu")
    before = {key: getattr(source, key) for key in payload.model_dump(exclude_unset=True)}
    for key, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(source, key, value)
    write_audit(db, "UPDATE", "DataSource", source.id, admin, request, before=before, after=payload.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    db.refresh(source)
    return source


@router.get("/crawl-runs", response_model=list[CrawlRunOut])
def list_runs(_: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 100):
    return db.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(min(limit, 200))).all()


@router.post("/sources/{source_id}/run", response_model=CrawlRunOut, status_code=202)
def run_source(
    source_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    source = db.get(DataSource, source_id)
    if not source or not source.enabled:
        raise HTTPException(status_code=404, detail="Nguồn không tồn tại hoặc đang bị khóa")
    run = CrawlRun(
        source_id=source.id,
        status=RunStatus.QUEUED,
        configuration_snapshot={"rate_limit": source.rate_limit, "base_url": source.base_url, "source_type": source.source_type.value},
    )
    db.add(run)
    db.flush()
    write_audit(db, "QUEUE_CRAWL", "CrawlRun", run.id, user, request, after={"source_id": source.id})
    db.commit()
    db.refresh(run)
    if source.source_type in {SourceType.MANUAL_UPLOAD, SourceType.DEMO} or not source.base_url:
        run.status = RunStatus.SUCCESS
        run.started_at = datetime.now(UTC)
        run.finished_at = run.started_at
        run.error_message = "Nguồn này sử dụng chức năng nhập tệp; không cần crawler."
        db.commit()
        db.refresh(run)
    else:
        try:
            crawl_source_task.delay(run.id)
        except Exception:
            # Chạy trực tiếp trong nền qua FastAPI BackgroundTasks nếu không có Redis/Celery (môi trường Windows local)
            background_tasks.add_task(execute_crawl, run.id)
            run.error_message = "Đang chạy nền cục bộ (FastAPI BackgroundTasks)."
            db.commit()
            db.refresh(run)
    return run
