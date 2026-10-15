import asyncio
import logging
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AdminAlert, CrawlLock, CrawlRun, DataSource, FailedCrawlItem
from app.models.enums import RunStatus, SourceType

logger = logging.getLogger("pharmatrust.scheduler")


def utcnow() -> datetime:
    return datetime.now(UTC)


class DistributedLockService:
    """
    Quản lý Distributed Lock dựa trên CSDL cho từng nguồn dữ liệu.
    Bảo đảm chỉ duy nhất 1 job của mỗi nguồn được thực thi tại một thời điểm,
    ngay cả khi máy chủ chạy nhiều uvicorn workers hoặc nhiều tiến trình.
    """

    @staticmethod
    def init_locks(db: Session):
        for code in ["PHARMACITY", "LONG_CHAU", "LEADER_SCHEDULER"]:
            existing = db.get(CrawlLock, code)
            if not existing:
                db.add(CrawlLock(
                    source_code=code,
                    is_locked=False,
                    lease_timeout_seconds=settings.job_lease_timeout_seconds,
                ))
        db.commit()

    @staticmethod
    def acquire_lock(db: Session, source_code: str, run_id: int | None = None, host_pid: str | None = None) -> tuple[bool, str]:
        lock = db.get(CrawlLock, source_code)
        if not lock:
            lock = CrawlLock(
                source_code=source_code,
                is_locked=False,
                lease_timeout_seconds=settings.job_lease_timeout_seconds,
            )
            db.add(lock)
            db.flush()

        now = utcnow()
        host_pid = host_pid or f"{os.getpid()}"

        # Kiểm tra nếu khóa đang được giữ
        if lock.is_locked:
            # Kiểm tra xem khóa có bị quá hạn (Stale Lock do tiến trình chết đột ngột) hay không
            if lock.locked_at:
                locked_at_utc = lock.locked_at.replace(tzinfo=lock.locked_at.tzinfo or UTC)
                time_elapsed = (now - locked_at_utc).total_seconds()
                if time_elapsed < lock.lease_timeout_seconds:
                    # Khóa đang hợp lệ do job trước đang chạy -> SKIPPED_OVERLAP
                    lock.overlap_count = (lock.overlap_count or 0) + 1
                    lock.last_skipped_at = now
                    db.commit()
                    return False, f"SKIPPED_OVERLAP: Nguồn {source_code} đang có tác vụ chạy (PID: {lock.locked_by}). Bỏ qua để chống chạy chồng."

            # Khóa đã quá hạn (Stale Lock) -> Thu hồi và cấp quyền cho tiến trình mới
            logger.warning(f"Thu hồi khóa quá hạn (Stale Lock) cho nguồn {source_code}")

        # Giành quyền khóa thành công
        lock.is_locked = True
        lock.locked_at = now
        lock.locked_by = host_pid
        lock.current_run_id = run_id
        db.commit()
        return True, "ACQUIRED"

    @staticmethod
    def release_lock(db: Session, source_code: str):
        lock = db.get(CrawlLock, source_code)
        if lock:
            lock.is_locked = False
            lock.current_run_id = None
            db.commit()


class AutoCrawlScheduler:
    """
    Scheduler chạy liên tục 24/7, lặp lại sau mỗi 6 giờ cho Pharmacity và Long Châu.
    """

    def __init__(self):
        self.is_running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.interval_hours = settings.auto_crawl_interval_hours
        self.auto_enabled = settings.auto_crawl_enabled
        self.pharmacity_enabled = settings.pharmacity_crawl_enabled
        self.long_chau_enabled = settings.long_chau_crawl_enabled
        self.publish_mode = settings.default_publish_mode
        self.next_run_at: dict[str, datetime] = {}
        self._last_evidence_expire_check: datetime | None = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="PharmaTrust-AutoCrawler-6H")
        self._thread.start()
        logger.info("Scheduler tự động cào dữ liệu 24/7 đã khởi động.")

    def stop(self):
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        logger.info("Scheduler đã dừng an toàn.")

    def _run_loop(self):
        # 1. Khởi tạo khóa CSDL và xử lý phục hồi sau khởi động lại máy chủ
        db = SessionLocal()
        try:
            DistributedLockService.init_locks(db)
            self._handle_server_restart(db)
        finally:
            db.close()

        # 2. Vòng lặp kiểm tra định kỳ mỗi 30 giây
        while not self._stop_event.is_set():
            try:
                if self.auto_enabled:
                    self._check_and_trigger_sources()
                self._check_and_expire_evidence()
            except Exception as exc:
                logger.error(f"Lỗi vòng lặp Scheduler: {exc}")

            # Chờ 30 giây trước khi kiểm tra lại
            self._stop_event.wait(timeout=30)

    def _check_and_expire_evidence(self):
        """
        Quét các yêu cầu bổ sung hình ảnh đổi trả đã quá hạn 3 ngày (chu kỳ 15 phút).
        """
        now = utcnow()
        if self._last_evidence_expire_check and (now - self._last_evidence_expire_check).total_seconds() < 900:
            return

        self._last_evidence_expire_check = now
        try:
            with SessionLocal() as db:
                from app.services.warehouse_return_service import WarehouseReturnService
                WarehouseReturnService.check_and_expire_evidence_requests(db)
        except Exception as e:
            logger.error(f"Lỗi khi quét quá hạn bằng chứng đổi trả: {e}")

    def _handle_server_restart(self, db: Session):
        """
        Xử lý khi máy chủ khởi động lại:
        - Xóa sạch các khóa bị treo (Stale Locks) và đánh dấu CrawlRun dở dang là INTERRUPTED.
        - Kiểm tra nếu đã quá 6 giờ kể từ lần cào gần nhất thì chạy bù ĐÚNG 1 LẦN.
        """
        now = utcnow()
        logger.info("Đang kiểm tra phục hồi hệ thống sau khi máy chủ khởi động...")

        # Dọn dẹp CrawlRun bị treo trạng thái RUNNING
        stuck_runs = db.scalars(
            select(CrawlRun).where(CrawlRun.status == RunStatus.RUNNING)
        ).all()
        for r in stuck_runs:
            r.status = RunStatus.FAILED
            r.error_message = "Tiến trình bị gián đoạn do máy chủ khởi động lại (INTERRUPTED)."
            r.finished_at = now
        db.commit()

        # Dọn dẹp khóa chết
        db.execute(update(CrawlLock).values(is_locked=False, current_run_id=None))
        db.commit()

        # Kiểm tra chạy bù nếu quá hạn 6 giờ
        sources_to_check = [
            ("PHARMACITY", self.pharmacity_enabled),
            ("LONG_CHAU", self.long_chau_enabled),
        ]
        for code, enabled in sources_to_check:
            if not enabled:
                continue
            src = db.scalar(select(DataSource).where(DataSource.code == code))
            if src:
                last_run = src.last_success_at or src.last_failure_at
                should_catch_up = False
                if not last_run:
                    should_catch_up = True
                else:
                    last_run_utc = last_run.replace(tzinfo=last_run.tzinfo or UTC)
                    if (now - last_run_utc) >= timedelta(hours=self.interval_hours):
                        should_catch_up = True

                if should_catch_up:
                    logger.info(f"[CHẠY BÙ] Nguồn {code} đã quá {self.interval_hours} giờ chưa chạy. Kích hoạt chạy bù 1 lần.")
                    self.trigger_source_crawl(code, is_manual=False, is_catchup=True)
                else:
                    # Lên lịch lần chạy tiếp theo
                    last_run_utc = last_run.replace(tzinfo=last_run.tzinfo or UTC)
                    self.next_run_at[code] = last_run_utc + timedelta(hours=self.interval_hours)

    def _check_and_trigger_sources(self):
        now = utcnow()
        for code, enabled in [("PHARMACITY", self.pharmacity_enabled), ("LONG_CHAU", self.long_chau_enabled)]:
            if not enabled:
                continue

            target_time = self.next_run_at.get(code)
            if not target_time or now >= target_time:
                # Kích hoạt cào theo lịch 6 giờ
                self.trigger_source_crawl(code, is_manual=False)
                self.next_run_at[code] = now + timedelta(hours=self.interval_hours)

    def trigger_source_crawl(self, source_code: str, is_manual: bool = False, is_catchup: bool = False) -> dict[str, Any]:
        """
        Kích hoạt tác vụ cào dữ liệu cho một nguồn cụ thể (tái sử dụng 100% giữa scheduler và nút thủ công).
        """
        from app.services.crawler_pipeline import execute_crawl_pipeline

        # Chạy trong luồng riêng để không chặn Scheduler
        worker_thread = threading.Thread(
            target=execute_crawl_pipeline,
            args=(source_code,),
            kwargs={"is_manual": is_manual, "is_catchup": is_catchup, "publish_mode": self.publish_mode},
            daemon=True,
            name=f"Crawl-{source_code}",
        )
        worker_thread.start()
        return {"status": "TRIGGERED", "source": source_code, "is_manual": is_manual}

    def get_status(self, db: Session) -> dict[str, Any]:
        locks = db.scalars(select(CrawlLock)).all()
        lock_map = {l.source_code: {
            "is_locked": l.is_locked,
            "locked_at": l.locked_at.isoformat() if l.locked_at else None,
            "overlap_count": l.overlap_count,
            "last_skipped_at": l.last_skipped_at.isoformat() if l.last_skipped_at else None,
        } for l in locks}

        alerts = db.scalars(
            select(AdminAlert).order_by(AdminAlert.id.desc()).limit(10)
        ).all()

        recent_runs = db.scalars(
            select(CrawlRun).order_by(CrawlRun.id.desc()).limit(10)
        ).all()

        return {
            "auto_crawl_enabled": self.auto_enabled,
            "interval_hours": self.interval_hours,
            "pharmacity_enabled": self.pharmacity_enabled,
            "long_chau_enabled": self.long_chau_enabled,
            "publish_mode": self.publish_mode,
            "next_run_at": {k: v.isoformat() for k, v in self.next_run_at.items()},
            "locks": lock_map,
            "alerts": [
                {
                    "id": a.id,
                    "source": a.source_code,
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in alerts
            ],
            "recent_runs": [
                {
                    "id": r.id,
                    "source_id": r.source_id,
                    "status": r.status.value,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    "pages_success": r.pages_success,
                    "pages_failed": r.pages_failed,
                    "products_discovered": r.products_discovered,
                    "error_message": r.error_message,
                }
                for r in recent_runs
            ],
        }


# Singleton Scheduler
scheduler = AutoCrawlScheduler()
