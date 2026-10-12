import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from app.db.session import SessionLocal
from app.services.warehouse_seeder import seed_warehouses_and_managers, seed_distributed_inventory

def main():
    db = SessionLocal()
    try:
        wh_map = seed_warehouses_and_managers(db)
        print(f"Successfully seeded {len(wh_map)} warehouses nationwide:")
        for code, wid in wh_map.items():
            print(f" - {code} (ID: {wid})")
        seed_distributed_inventory(db)
        print("Successfully seeded distributed inventory batches with FEFO compliance.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
