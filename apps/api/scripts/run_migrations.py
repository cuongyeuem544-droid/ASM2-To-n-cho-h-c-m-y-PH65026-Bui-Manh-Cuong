"""PharmaTrust - Robust, Self-Healing Database Migration Runner.
Executes Alembic migrations to head with automatic detection and recovery from:
1. Obsolete / abandoned revision IDs from old branches in local DB.
2. Missing alembic_version table on existing databases.
3. Database locking detection with helpful guidance.
4. Single-head integrity verification.
"""
import os
import sys
import sqlite3
from pathlib import Path

# Add apps/api to sys.path
API_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = API_DIR.parent.parent
sys.path.insert(0, str(API_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_migrations() -> bool:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic import command
        from app.core.config import settings
    except ImportError as e:
        print(f"[LOI THIEU THU VIEN] Khong the nap Alembic hoac dependencies backend: {e}")
        print("Vui long chay: pip install -r apps/api/requirements.txt")
        return False

    ini_path = API_DIR / "alembic.ini"
    if not ini_path.exists():
        print(f"[LOI] Khong tim thay tep cau hinh alembic.ini tai {ini_path}")
        return False

    cfg = Config(str(ini_path))
    script = ScriptDirectory.from_config(cfg)
    known_revisions = set(script.walk_revisions())
    known_rev_ids = {rev.revision for rev in known_revisions}
    known_rev_ids.add("head")
    known_rev_ids.add("heads")

    # Detect SQLite DB path
    db_url = settings.database_url
    sqlite_prefix = "sqlite:///"
    if db_url.startswith(sqlite_prefix):
        raw_db_path = db_url[len(sqlite_prefix):]
        # Resolve path
        if raw_db_path.startswith("./"):
            db_file_path = ROOT_DIR / raw_db_path[2:]
        else:
            p = Path(raw_db_path)
            db_file_path = p if p.is_absolute() else (ROOT_DIR / p)

        if db_file_path.exists():
            # Check for stale / obsolete revision ID in alembic_version
            try:
                conn = sqlite3.connect(str(db_file_path), timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
                has_ver_table = cursor.fetchone() is not None
                if has_ver_table:
                    cursor.execute("SELECT version_num FROM alembic_version")
                    rows = cursor.fetchall()
                    for (v_num,) in rows:
                        if v_num not in known_rev_ids:
                            print(f"  - [CANH BAO] Phat hien revision cu khong hop le trong CSDL: '{v_num}' (tu nhanh cu hoac merge truoc do).")
                            print("  - [TU DONG SUA] Dang xoa revision cu khoi alembic_version de tai dong bo chuan...")
                            cursor.execute("DELETE FROM alembic_version WHERE version_num = ?", (v_num,))
                            conn.commit()
                conn.close()
            except sqlite3.OperationalError as e:
                err_msg = str(e).lower()
                if "locked" in err_msg or "busy" in err_msg:
                    print("\n" + "=" * 70)
                    print("[LOI KHOA CO SO DU LIEU] Tep pharmatrust.db dang bi tien trinh khac khoa!")
                    print("Nguyen nhan: Co tien trinh Backend hoac cong cu xem SQLite cu chua duoc dong.")
                    print("GIAI PHAP: Vui long chay 'stop-all.bat' hoac dong cac cua so chay truoc do, sau do thu lai.")
                    print("=" * 70 + "\n")
                    return False

    # Execute Alembic upgrade head
    print(f"  - Dang chay Alembic upgrade head (CSDL: {db_url})...")
    try:
        command.upgrade(cfg, "head")
    except Exception as e:
        err_str = str(e)
        print(f"  - [LOI KHI UPGRADE] {err_str}")
        if "Can't locate revision identified by" in err_str:
            print("  - [TU DONG SUA] Thu don dep alembic_version va stamp head...")
            try:
                if 'db_file_path' in locals() and db_file_path.exists():
                    c = sqlite3.connect(str(db_file_path))
                    c.execute("DROP TABLE IF EXISTS alembic_version")
                    c.commit()
                    c.close()
                command.upgrade(cfg, "head")
                print("  - [OK] Da tu dong khac phuc va upgrade thanh cong!")
            except Exception as e2:
                print(f"  - [LOI] Khong the tu dong khac phuc: {e2}")
                return False
        else:
            return False

    # Verify single head
    heads = script.get_heads()
    if len(heads) != 1:
        print(f"  - [LOI] Co nhieu hon 1 Alembic head revision: {heads}")
        return False

    print(f"  - [OK] Alembic database migrations hoan tat thanh cong! Revision hien tai: {heads[0]}")
    return True


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
