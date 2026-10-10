"""Cấu hình cơ sở dữ liệu kiểm thử cô lập (Isolated Test Database).
Ngăn chặn hoàn toàn việc kiểm thử tự động ghi đè hoặc sinh dữ liệu rác vào pharmatrust.db.
"""
import os
import shutil
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
APP_DB_PATH = os.path.join(BASE_DIR, "pharmatrust.db")
TEST_DB_PATH = os.path.join(BASE_DIR, "pharmatrust_test.db")
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def setup_isolated_test_db():
    """Khởi tạo database test riêng biệt được sao chép từ database hiện tại."""
    if os.path.exists(APP_DB_PATH):
        shutil.copy2(APP_DB_PATH, TEST_DB_PATH)
    else:
        Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestSessionLocal


def teardown_isolated_test_db():
    """Dọn dẹp sau khi kiểm thử kết thúc."""
    app.dependency_overrides.pop(get_db, None)
    test_engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
