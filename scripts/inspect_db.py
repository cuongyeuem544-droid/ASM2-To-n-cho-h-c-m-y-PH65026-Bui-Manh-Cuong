import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("pharmatrust.db")
cur = conn.cursor()
cur.execute("SELECT id, code, name, province, address, lat, lng FROM warehouses")
for r in cur.fetchall():
    print(r)
conn.close()
