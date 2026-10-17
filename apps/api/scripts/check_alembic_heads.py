"""PharmaTrust - Check Alembic Single Head Revision.
Exits with 0 if exactly 1 head exists, or 1 otherwise.
"""
import sys
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

# apps/api/scripts/check_alembic_heads.py -> parents[1] is apps/api
ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
cfg = Config(str(ini_path))
s = ScriptDirectory.from_config(cfg)
heads = s.get_heads()
print(f"  - Heads count: {len(heads)} | Heads: {heads}")
sys.exit(0 if len(heads) == 1 else 1)
