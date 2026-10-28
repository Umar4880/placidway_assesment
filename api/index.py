import os
import sys
from pathlib import Path

# Add project root directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Handle Vercel serverless read-only filesystem
if os.environ.get("VERCEL"):
    data_dir = root_dir / "data"
    tmp_data = Path("/tmp/data")
    if not tmp_data.exists() and data_dir.exists():
        import shutil
        try:
            shutil.copytree(data_dir, tmp_data, dirs_exist_ok=True)
        except Exception:
            pass

from src.api.app import app
