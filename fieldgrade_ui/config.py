from __future__ import annotations

import os
from pathlib import Path

def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def jobs_db_path() -> Path:
    p = os.environ.get("FG_JOBS_DB", "")
    if p:
        return Path(p)
    return repo_root() / "fieldgrade_ui" / "runtime" / "jobs.sqlite"

def enable_embedded_worker() -> bool:
    # Safe default: enable embedded worker only when running a single server worker.
    if os.environ.get("FG_ENABLE_WORKER", ""):
        return os.environ.get("FG_ENABLE_WORKER", "0") == "1"
    try:
        workers = int(os.environ.get("FG_WORKERS") or os.environ.get("FIELDGRADE_UI_WORKERS", "1"))
    except Exception:
        workers = 1
    return workers == 1
