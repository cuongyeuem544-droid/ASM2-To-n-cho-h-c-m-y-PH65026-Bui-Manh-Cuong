import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from app.main import app

print(f"FastAPI loaded successfully! Total routes registered: {len(app.routes)}")
for r in app.routes:
    if "warehouse" in getattr(r, "path", ""):
        print(f"  Route: {r.path} [{','.join(getattr(r, 'methods', []))}]")
