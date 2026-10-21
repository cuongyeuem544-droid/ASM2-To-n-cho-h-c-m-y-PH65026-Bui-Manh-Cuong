import sys
import sqlite3
from pathlib import Path

repo_root = Path("C:/Users/admin/Desktop/TOAN HOC CHO MAY/du-an-website-ban-thuoc-")
sys.path.insert(0, str(repo_root))
from scripts.update_vietnam_provinces_2026 import PROVINCES_63

seed_path = repo_root / "apps/api/app/seed.py"
with open(seed_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '''ADMINISTRATIVE_UNITS = [
    # --- Tỉnh / Thành phố ---
    ("79", "Hồ Chí Minh", None, "PROVINCE", "Thành phố Hồ Chí Minh"),
    ("01", "Hà Nội", None, "PROVINCE", "Thành phố Hà Nội"),
    ("48", "Đà Nẵng", None, "PROVINCE", "Thành phố Đà Nẵng"),
    ("92", "Cần Thơ", None, "PROVINCE", "Thành phố Cần Thơ"),
    ("31", "Hải Phòng", None, "PROVINCE", "Thành phố Hải Phòng"),'''

lines = ['ADMINISTRATIVE_UNITS = [', '    # --- 63 Tỉnh / Thành phố trực thuộc Trung ương (Chuẩn Google Maps & TCTK) ---']
for p in PROVINCES_63:
    lines.append(f'    ("{p["code"]}", "{p["name"]}", None, "PROVINCE", "{p["fullName"]}"),')

replacement = '\n'.join(lines)
content_norm = content.replace('\r\n', '\n')
target_norm = target.replace('\r\n', '\n')
if target_norm in content_norm:
    new_content = content_norm.replace(target_norm, replacement)
    with open(seed_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Updated seed.py successfully with all 63 provinces.")
else:
    print("Target block already updated or not found.")

# Update database table administrative_units
db_path = repo_root / "pharmatrust.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
for p in PROVINCES_63:
    cur.execute("SELECT id FROM administrative_units WHERE code = ?", (p["code"],))
    row = cur.fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO administrative_units (code, name, parent_code, level, full_name)
            VALUES (?, ?, NULL, 'PROVINCE', ?)
            """,
            (p["code"], p["name"], p["fullName"]),
        )
conn.commit()
cur.execute("SELECT count(*) FROM administrative_units WHERE level = 'PROVINCE'")
print(f"Total PROVINCE units in pharmatrust.db: {cur.fetchone()[0]}")
conn.close()
