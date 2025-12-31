from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .config import jobs_db_path, repo_root
from .jobs import append_log, claim_next_job, fail_job, succeed_job
from .pipeline import run_termite_to_ecology_pipeline

def _safe_resolve(p: Path) -> Path:
    p = Path(p).expanduser()
    try:
        return p.resolve(strict=False)
    except Exception:
        try:
            return p.resolve()
        except Exception:
            return p


def _uploads_dir() -> Path:
    override = os.environ.get("FG_UPLOADS_DIR") or os.environ.get("FIELDGRADE_UPLOADS_DIR")
    if override:
        return _safe_resolve(Path(override))
    # default: termite_fieldpack/runtime/uploads
    return _safe_resolve(repo_root() / "termite_fieldpack" / "runtime" / "uploads")


def _is_under(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except Exception:
        return False


def _extra_roots() -> list[Path]:
    raw = (os.environ.get("FG_API_EXTRA_ROOTS") or "").strip()
    if not raw:
        return []
    out: list[Path] = []

    def _split_env_path_list(s: str) -> list[str]:
        """Split a list of paths from an environment variable.

        Uses the platform separator (os.pathsep). For compatibility with older
        configs, also accepts ':' on platforms where os.pathsep is not ':'
        (e.g. Windows) *only* when it does not look like a drive-letter path list.
        """
        s = (s or "").strip()
        if not s:
            return []
        parts = [p.strip() for p in s.split(os.pathsep) if p.strip()]
        if os.pathsep != ":" and len(parts) == 1 and ":" in s and not re.search(r"[A-Za-z]:[\\/]", s):
            parts = [p.strip() for p in s.split(":") if p.strip()]
        return parts

    for part in _split_env_path_list(raw):
        out.append(_safe_resolve(Path(part)))
    return out


def _sandbox_upload_path(p: Path) -> Path:
    rp = _safe_resolve(p)
    roots = [_uploads_dir()] + _extra_roots()
    if not any(_is_under(rp, r) for r in roots):
        raise RuntimeError(f"upload_path not allowed: {rp}")
    if not rp.exists() or not rp.is_file():
        raise RuntimeError(f"upload_path missing or not a file: {rp}")
    return rp


def run_once() -> bool:
    db_path = jobs_db_path()
    claimed = claim_next_job(db_path, kinds=["pipeline"])
    if not claimed:
        return False

    job_id, kind, params = claimed

    def log(msg: str) -> None:
        append_log(db_path, job_id, "info", msg)

    try:
        if kind == "pipeline":
            upload_path = _sandbox_upload_path(Path(params["upload_path"]))
            label = str(params.get("label", "run"))
            log("starting pipeline job")
            result = run_termite_to_ecology_pipeline(repo_root(), upload_path=upload_path, label=label, log=log)
            succeed_job(db_path, job_id, result)
        else:
            raise RuntimeError(f"unknown job kind={kind}")
    except Exception as e:
        fail_job(db_path, job_id, f"{type(e).__name__}: {e}")
    return True

def main() -> None:
    poll = float(os.environ.get("FG_WORKER_POLL", "1.0"))
    print(f"[fieldgrade_ui.worker] jobs_db={jobs_db_path()} poll={poll}s", flush=True)
    while True:
        worked = run_once()
        if not worked:
            time.sleep(poll)

if __name__ == "__main__":
    main()
