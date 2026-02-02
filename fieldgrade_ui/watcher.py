from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from .config import jobs_db_path, watch_state_path
from .jobs import create_job

def load_state() -> Dict[str, dict]:
    sp = watch_state_path()
    if sp.exists():
        try:
            return json.loads(sp.read_text())
        except Exception:
            return {}
    return {}

def save_state(state: Dict[str, dict]) -> None:
    sp = watch_state_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(state, indent=2))

def scan_and_enqueue(uploads_dir: Path, label: str = "watch") -> int:
    """Scan uploads_dir, enqueue pipeline jobs for new files. Returns number enqueued."""
    state = load_state()
    enq = 0
    for p in sorted(uploads_dir.glob("*")):
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except Exception:
            continue
        key = str(p.resolve())
        sig = {"size": st.st_size, "mtime": st.st_mtime}
        if key in state and state[key] == sig:
            continue
        # update state first to prevent duplicate enqueues on crash loops
        state[key] = sig
        save_state(state)
        run_id = uuid.uuid4().hex
        create_job(
            jobs_db_path(),
            "pipeline",
            {"upload_path": key, "label": label, "run_id": run_id},
        )
        enq += 1
    return enq

def loop(uploads_dir: Path, stop_evt, poll_s: float = 2.0, label: str = "watch") -> None:
    while not stop_evt.is_set():
        try:
            scan_and_enqueue(uploads_dir, label=label)
        except Exception:
            pass
        time.sleep(poll_s)
