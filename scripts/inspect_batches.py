import sqlite3

conn = sqlite3.connect("pharmatrust.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(inventory_batches)")
print("inventory_batches columns:", [c[1] for c in cur.fetchall()])
cur.execute("PRAGMA table_info(warehouse_batch_stock)")
print("warehouse_batch_stock columns:", [c[1] for c in cur.fetchall()])
conn.close()
