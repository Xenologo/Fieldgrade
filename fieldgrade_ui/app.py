from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
import re
import sqlite3
import subprocess
import sys
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, HTTPException, UploadFile, Request, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import threading
import time

# FastAPI requires the optional dependency "python-multipart" for endpoints
# that accept UploadFile/File form-data. We allow the server to start even if
# it's missing (common in minimal / offline installs) and degrade upload
# endpoints gracefully.
try:
    import python_multipart  # noqa: F401
    _MULTIPART_OK = True
except Exception:
    _MULTIPART_OK = False

from .config import (
    api_extra_roots,
    api_token,
    api_tokens,
    cmd_timeout_s,
    enable_embedded_worker,
    env_bool,
    env_float,
    env_str,
    jobs_db_path,
    uploads_dir,
)
from .jobs import create_job, list_jobs as jobs_list, get_job as jobs_get, get_job_logs as jobs_logs, cancel_job as jobs_cancel, ensure_db as ensure_jobs_db
from .worker import run_once as worker_run_once
from .watcher import loop as watcher_loop


REPO_ROOT = Path(__file__).resolve().parents[1]
TERMITE_DIR = REPO_ROOT / "termite_fieldpack"
ECOLOGY_DIR = REPO_ROOT / "mite_ecology"


def _tenants_root() -> Path:
    override = (os.environ.get("FG_TENANTS_ROOT") or "").strip()
    if override:
        return _safe_resolve_path(Path(override))
    return REPO_ROOT / "fieldgrade_ui" / "runtime" / "tenants"


def _path_mite_db() -> Path:
    """Return the resolved path to the mite_ecology SQLite DB.

    Termux / zip extractions can end up in different places, and users may also
    choose to keep the DB elsewhere. This helper makes DB discovery resilient.

    Override knobs:
      - FG_MITE_DB: explicit path to the sqlite DB file
      - MITE_ECOLOGY_DB: alternate name (compatible with CLI)

    Default layout:
      - {repo}/mite_ecology/runtime/mite_ecology.sqlite
    """

    override = os.getenv("FG_MITE_DB") or os.getenv("MITE_ECOLOGY_DB")
    if override:
        p = Path(override).expanduser()
        try:
            return p.resolve()
        except Exception:
            return p

    candidates = [
        ECOLOGY_DIR / "runtime" / "mite_ecology.sqlite",
        ECOLOGY_DIR / "runtime" / "mite_ecology.db",
        ECOLOGY_DIR / "mite_ecology.sqlite",
        REPO_ROOT / "mite_ecology.sqlite",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Return the default even if it doesn't exist yet; callers can handle that.
    return candidates[0]


def _path_uploads() -> Path:
    """Return uploads directory (overrideable)."""
    return uploads_dir(UPLOADS_DIR)


def _path_termite_artifacts() -> Path:
    """Return Termite artifacts dir (overrideable)."""
    override = os.getenv("FG_TERMITE_ARTIFACTS_DIR") or os.getenv("FIELDGRADE_TERMITE_ARTIFACTS_DIR")
    if override:
        p = Path(override).expanduser()
        try:
            return p.resolve()
        except Exception:
            return p
    return TERMITE_DIR / "artifacts"


DEFAULT_POLICY = TERMITE_DIR / "config" / "meap_v1.yaml"
DEFAULT_ALLOWLIST = TERMITE_DIR / "config" / "tool_allowlist.yaml"

BUNDLES_DIR = TERMITE_DIR / "artifacts" / "bundles_out"
EXPORTS_DIR = ECOLOGY_DIR / "artifacts" / "export"

UPLOADS_DIR = TERMITE_DIR / "runtime" / "uploads"


@dataclass
class CmdResult:
    ok: bool
    cmd: List[str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    parsed: Optional[Any] = None


def _run_cmd(cmd: List[str], cwd: Path) -> CmdResult:
    """Run a subprocess with stdout/stderr capture and a configurable timeout.

    Timeout is controlled by FG_CMD_TIMEOUT_S (default 600). Set to 0/empty to disable.
    """
    timeout_s_raw = (os.environ.get("FG_CMD_TIMEOUT_S", "600") or "600").strip()
    timeout_s = cmd_timeout_s()

    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        stdout = p.stdout or ""
        stderr = p.stderr or ""
        code = int(p.returncode)
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        stderr = (e.stderr or "") if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
        stderr = (stderr or "") + f"\n[timeout] command exceeded {timeout_s_raw}s"
        code = 124

    parsed: Optional[Any] = None
    s = (stdout or "").strip()
    if s:
        try:
            parsed = json.loads(s)
        except Exception:
            parsed = None

    return CmdResult(
        ok=(code == 0),
        cmd=cmd,
        cwd=str(cwd),
        exit_code=code,
        stdout=stdout,
        stderr=stderr,
        parsed=parsed,
    )


def _require_exists(p: Path, what: str) -> None:
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"{what}_not_found: {p}")


def _safe_resolve_path(p: Path) -> Path:
    """Resolve a path without requiring it to exist."""
    p = Path(p).expanduser()
    try:
        return p.resolve(strict=False)
    except Exception:
        try:
            return p.resolve()
        except Exception:
            return p


def _is_under_root(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except Exception:
        return False


def _extra_sandbox_roots() -> list[Path]:
    return api_extra_roots()


def _sandbox_path(raw: str, *, roots: list[Path], what: str, must_exist: bool = True, must_be_file: bool = False) -> Path:
    """Restrict user-supplied filesystem paths to a small set of allowed roots.

    This prevents the API from being used as a general-purpose file oracle.
    """
    if not raw or not str(raw).strip():
        raise HTTPException(status_code=400, detail=f"missing_{what}")
    pth = _safe_resolve_path(Path(str(raw)))
    allowed = [_safe_resolve_path(r) for r in roots] + _extra_sandbox_roots()
    if not any(_is_under_root(pth, r) for r in allowed):
        raise HTTPException(status_code=403, detail=f"path_not_allowed:{what}:{pth}")
    if must_exist and not pth.exists():
        raise HTTPException(status_code=404, detail=f"{what}_not_found:{pth}")
    if must_be_file and pth.exists() and not pth.is_file():
        raise HTTPException(status_code=400, detail=f"{what}_not_a_file:{pth}")
    return pth


def _connect_sqlite(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def _table_payload_col(con: sqlite3.Connection, table: str) -> Optional[str]:
    """Return the JSON payload column name for a given table.

    Supports schema drift across versions (e.g. `attrs_json` vs legacy `json`).
    Returns None if no known payload column exists.
    """
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        cols = []
        for r in rows:
            if isinstance(r, sqlite3.Row):
                cols.append(r["name"])
            else:
                cols.append(r[1])
    except Exception:
        return None

    for cand in ("attrs_json", "json", "payload_json"):
        if cand in cols:
            return cand
    return None


def _safe_json_loads(s: Optional[str]) -> Optional[Any]:
    if s is None:
        return None
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None
    try:
        return json.loads(t)
    except Exception:
        return None

safe_json_loads = _safe_json_loads

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _worker_stop_evt, _worker_thread, _watcher_stop_evt, _watcher_thread

    if enable_embedded_worker():
        _worker_stop_evt = threading.Event()
        _worker_thread = threading.Thread(target=_bg_worker_loop, args=(_worker_stop_evt,), daemon=True)
        _worker_thread.start()

    # Optional: autonomic uploads watcher (drop files into uploads dir).
    if env_bool("FG_WATCH_UPLOADS", default=False):
        _watcher_stop_evt = threading.Event()
        poll_s = env_float("FG_WATCH_POLL", default=2.0)
        label = env_str("FG_WATCH_LABEL", default="watch")
        _watcher_thread = threading.Thread(
            target=watcher_loop,
            args=(_path_uploads(), _watcher_stop_evt, poll_s, label),
            daemon=True,
        )
        _watcher_thread.start()

    try:
        yield
    finally:
        if _worker_stop_evt is not None:
            _worker_stop_evt.set()
        if _watcher_stop_evt is not None:
            _watcher_stop_evt.set()


app = FastAPI(title="Fieldgrade UI", version="0.1", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/readyz")
def readyz() -> JSONResponse:
    """Readiness probe.

    Conservative: do not create or migrate DBs here; only confirm required state
    exists on disk.
    """
    jobs_db = jobs_db_path()
    mite_db = _path_mite_db()

    missing: list[str] = []
    if not jobs_db.exists():
        missing.append(f"jobs_db:{jobs_db}")
    if not mite_db.exists():
        missing.append(f"mite_db:{mite_db}")

    if missing:
        return JSONResponse({"ok": False, "missing": missing}, status_code=503)

    return JSONResponse({"ok": True}, status_code=200)


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8", "replace")).hexdigest()


API_TOKENS = set(api_tokens())


def _multi_tenant_enabled() -> bool:
    # Enable per-token scoping when multiple principals exist.
    return len(API_TOKENS) > 1


def _path_bundles_dir() -> Path:
    # Allow overriding artifacts root for tests / alternate runtime layouts.
    artifacts = _path_termite_artifacts()
    return artifacts / "bundles_out"


def _tenant_dir(request: Request) -> Optional[Path]:
    owner = _owner_hash(request)
    if not owner:
        return None
    return _tenants_root() / owner


def _tenant_ecology_config_path(request: Request) -> Optional[Path]:
    if not _multi_tenant_enabled():
        return None
    td = _tenant_dir(request)
    if td is None:
        return None

    cfg_path = td / "ecology.yaml"
    if cfg_path.exists():
        return cfg_path

    runtime_root = td / "runtime"
    db_path = runtime_root / "mite_ecology.sqlite"
    imports_root = td / "imports"
    exports_root = td / "exports"
    for p in (runtime_root, imports_root, exports_root):
        p.mkdir(parents=True, exist_ok=True)

    # Minimal config (yaml) for mite_ecology CLI.
    cfg_text = "\n".join(
        [
            "mite_ecology:",
            f"  runtime_root: {runtime_root.as_posix()}",
            f"  db_path: {db_path.as_posix()}",
            f"  imports_root: {imports_root.as_posix()}",
            f"  exports_root: {exports_root.as_posix()}",
            "",
        ]
    )
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(cfg_text, encoding="utf-8")
    return cfg_path


def _tenant_mite_db_path(request: Request) -> Path:
    if not _multi_tenant_enabled():
        return _path_mite_db()
    td = _tenant_dir(request)
    if td is None:
        return _path_mite_db()
    return td / "runtime" / "mite_ecology.sqlite"


def _tenant_exports_root(request: Request) -> Path:
    if not _multi_tenant_enabled():
        return EXPORTS_DIR
    td = _tenant_dir(request)
    if td is None:
        return EXPORTS_DIR
    return td / "exports"


def _tenant_remotes_cache_root(request: Request) -> Path:
    """Return tenant-scoped cache root for verified remote catalogs."""
    if not _multi_tenant_enabled():
        root = REPO_ROOT / "fieldgrade_ui" / "runtime" / "remotes_cache"
        root.mkdir(parents=True, exist_ok=True)
        return root

    td = _tenant_dir(request)
    if td is None:
        root = REPO_ROOT / "fieldgrade_ui" / "runtime" / "remotes_cache"
        root.mkdir(parents=True, exist_ok=True)
        return root

    root = td / "remotes_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _tenant_releases_root(request: Request) -> Path:
    """Return tenant-scoped root for release artifacts."""
    if not _multi_tenant_enabled():
        root = REPO_ROOT / "mite_ecology" / "artifacts" / "releases"
        root.mkdir(parents=True, exist_ok=True)
        return root

    td = _tenant_dir(request)
    if td is None:
        root = REPO_ROOT / "mite_ecology" / "artifacts" / "releases"
        root.mkdir(parents=True, exist_ok=True)
        return root

    root = td / "releases"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _visible_bundle_paths_for_owner(request: Request) -> list[Path]:
    """Return bundle paths visible to this principal.

    In multi-tenant mode, the bundle list is derived from succeeded jobs owned
    by this principal (e.g. pipeline runs or termite seal calls).
    """
    bundles_dir = _path_bundles_dir()
    bundles_dir.mkdir(parents=True, exist_ok=True)
    if not _multi_tenant_enabled():
        items = sorted(bundles_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [p for p in items if p.is_file()]

    owner = _owner_hash(request)
    if not owner:
        return []

    dbp = jobs_db_path()
    items = jobs_list(dbp, owner_token_hash=owner, limit=2000, status="succeeded")
    seen: set[str] = set()
    out: list[Path] = []
    for j in items:
        r = j.result or {}
        if not isinstance(r, dict):
            continue
        bp = r.get("bundle_path")
        if not bp:
            continue
        try:
            p = _safe_resolve_path(Path(str(bp)))
        except Exception:
            continue
        if not _is_under_root(p, bundles_dir):
            continue
        if not p.exists() or not p.is_file():
            continue
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        out.append(p)
    return out


def _require_visible_bundle(request: Request, bundle_path: Path) -> None:
    if not _multi_tenant_enabled():
        return
    allowed = {str(p) for p in _visible_bundle_paths_for_owner(request)}
    if str(bundle_path) not in allowed:
        raise HTTPException(status_code=404, detail="bundle_not_found")

if API_TOKENS:
    @app.middleware("http")
    async def _api_token_auth(request, call_next):
        # Keep the UI shell accessible without auth; protect all API actions.
        p = request.url.path or ""
        if p == "/" or p.startswith("/static/"):
            return await call_next(request)

        token = (request.headers.get("x-api-key") or "").strip()
        auth = (request.headers.get("authorization") or "").strip()
        if not token and auth.lower().startswith("bearer "):
            token = auth[7:].strip()

        if token not in API_TOKENS:
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        request.state.api_token = token
        request.state.owner_token_hash = _token_hash(token)

        return await call_next(request)


def _owner_hash(request: Request) -> Optional[str]:
    return getattr(request.state, "owner_token_hash", None)

def _bg_worker_loop(stop_evt: threading.Event) -> None:
    """Embedded background worker (only safe with FG_WORKERS=1)."""
    dbp = jobs_db_path()
    ensure_jobs_db(dbp)
    poll_s = env_float("FG_WORKER_POLL", default=1.0)
    while not stop_evt.is_set():
        try:
            worked = worker_run_once()
        except Exception as e:
            time.sleep(max(0.05, poll_s))
            continue

        if not worked:
            time.sleep(max(0.05, poll_s))

_worker_stop_evt: threading.Event | None = None
_worker_thread: threading.Thread | None = None

_watcher_stop_evt: threading.Event | None = None
_watcher_thread: threading.Thread | None = None

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(static_dir / "index.html"))


@app.get("/api/state")
def state() -> Dict[str, Any]:
    return {
        "repo_root": str(REPO_ROOT),
        "termite_dir": str(TERMITE_DIR),
        "ecology_dir": str(ECOLOGY_DIR),
        "default_policy": str(DEFAULT_POLICY),
        "default_allowlist": str(DEFAULT_ALLOWLIST),
        "bundles_dir": str(_path_bundles_dir()),
        "exports_dir": str(EXPORTS_DIR),
        "tenants_root": str(_tenants_root()),
        "multi_tenant": _multi_tenant_enabled(),
        "uploads_dir": str(UPLOADS_DIR),
        "python": sys.executable,
    }


if _MULTIPART_OK:
    @app.post("/api/ingest/upload")
    async def ingest_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

        # Basic filename hygiene
        filename = (file.filename or "upload.bin").replace("\\", "_").replace("/", "_")

        # Avoid collisions
        base = filename
        candidate = UPLOADS_DIR / base
        i = 1
        while candidate.exists():
            stem, ext = os.path.splitext(filename)
            base = f"{stem}_{i}{ext}"
            candidate = UPLOADS_DIR / base
            i += 1

        max_bytes = int(os.environ.get("FG_MAX_UPLOAD_BYTES", "0") or "0")
        total = 0
        with candidate.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if max_bytes and total > max_bytes:
                    try:
                        candidate.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail=f"upload_too_large: {total} > {max_bytes}")
                f.write(chunk)

        return {
            "ok": True,
            "saved_path": str(candidate),
            "bytes": total,
            "filename": filename,
        }
else:
    @app.post("/api/ingest/upload")
    async def ingest_upload_disabled() -> Dict[str, Any]:
        raise HTTPException(
            status_code=503,
            detail="upload_endpoint_disabled: install 'python-multipart' to enable file uploads",
        )


@app.get("/api/metrics")
def api_metrics(request: Request):
    """Lightweight operational metrics (JSON)."""
    dbp = jobs_db_path()
    ensure_jobs_db(dbp)

    con = sqlite3.connect(str(dbp))
    try:
        owner = _owner_hash(request)
        if owner is None:
            rows = con.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
        else:
            rows = con.execute(
                "SELECT status, COUNT(*) AS n FROM jobs WHERE owner_token_hash=? GROUP BY status",
                (owner,),
            ).fetchall()
        jobs_by_status = {r[0]: int(r[1]) for r in rows}
    finally:
        con.close()

    def bytes_of(p: Path):
        try:
            if p.is_dir():
                total = 0
                for fp in p.rglob("*"):
                    if fp.is_file():
                        try:
                            total += fp.stat().st_size
                        except Exception:
                            pass
                return total
            return p.stat().st_size
        except Exception:
            return None

    mite_db = _path_mite_db()
    termite_artifacts = _path_termite_artifacts()
    uploads_dir = _path_uploads()

    return {
        "jobs_db": str(dbp),
        "jobs_db_bytes": bytes_of(dbp),
        "jobs_by_status": jobs_by_status,
        "mite_db": str(mite_db),
        "mite_db_bytes": bytes_of(mite_db),
        "termite_artifacts_dir": str(termite_artifacts),
        "termite_artifacts_bytes": bytes_of(termite_artifacts),
        "uploads_dir": str(uploads_dir),
        "uploads_bytes": bytes_of(uploads_dir) if uploads_dir.exists() else 0,
    }


@app.get("/api/jobs")
def api_jobs(request: Request, limit: int = 50, status: str | None = None):
    dbp = jobs_db_path()
    items = jobs_list(dbp, owner_token_hash=_owner_hash(request), limit=limit, status=status)
    return {"jobs": [j.__dict__ for j in items]}

@app.get("/api/jobs/{job_id}")
def api_job(request: Request, job_id: int):
    dbp = jobs_db_path()
    j = jobs_get(dbp, job_id, owner_token_hash=_owner_hash(request))
    if not j:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"job": j.__dict__}

@app.get("/api/jobs/{job_id}/logs")
def api_job_logs(request: Request, job_id: int, limit: int = 500):
    dbp = jobs_db_path()
    j = jobs_get(dbp, job_id, owner_token_hash=_owner_hash(request))
    if not j:
        return JSONResponse({"error": "not found"}, status_code=404)
    logs = jobs_logs(dbp, job_id, owner_token_hash=_owner_hash(request), limit=limit)
    return {"job_id": job_id, "logs": logs}

@app.post("/api/jobs/{job_id}/cancel")
def api_job_cancel(request: Request, job_id: int):
    dbp = jobs_db_path()
    j = jobs_get(dbp, job_id, owner_token_hash=_owner_hash(request))
    if not j:
        return JSONResponse({"error": "not found"}, status_code=404)
    ok = jobs_cancel(dbp, job_id, owner_token_hash=_owner_hash(request))
    return {"ok": ok}

@app.post("/api/jobs/pipeline")
def api_jobs_pipeline(request: Request, payload: dict):
    """Enqueue a full termite→mite_ecology pipeline job.

    payload: {upload_path: str, label?: str}
    """
    upload_path = _sandbox_path(str(payload.get("upload_path") or ""), roots=[UPLOADS_DIR], what="upload_path", must_exist=True, must_be_file=True)
    label = str(payload.get("label", "run") or "run")
    job_id = create_job(
        jobs_db_path(),
        "pipeline",
        {"upload_path": str(upload_path), "label": label},
        owner_token_hash=_owner_hash(request) or "",
    )
    return {"ok": True, "job_id": job_id, "upload_path": str(upload_path), "label": label}

if _MULTIPART_OK:
    @app.post("/api/pipeline/upload_run")
    async def api_pipeline_upload_run(request: Request, file: UploadFile = File(...), label: str = "run"):
        """Upload a file and enqueue the pipeline as a background job."""
        upload_dir = _path_uploads()
        upload_dir.mkdir(parents=True, exist_ok=True)

        raw_name = (file.filename or "upload.bin")
        safe_name = os.path.basename(raw_name).replace("\\", "_").replace("/", "_").replace("\x00", "")
        if safe_name.strip() == "":
            safe_name = "upload.bin"

        dest = upload_dir / safe_name
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            i = 1
            while True:
                cand = upload_dir / f"{stem}_{i}{suffix}"
                if not cand.exists():
                    dest = cand
                    break
                i += 1

        max_bytes = int(os.environ.get("FG_MAX_UPLOAD_BYTES", "0") or "0")
        total = 0
        with dest.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if max_bytes and total > max_bytes:
                    try:
                        dest.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail=f"upload_too_large: {total} > {max_bytes}")
                f.write(chunk)

        job_id = create_job(
            jobs_db_path(),
            "pipeline",
            {"upload_path": str(dest), "label": label},
            owner_token_hash=_owner_hash(request) or "",
        )
        return {"ok": True, "job_id": job_id, "upload_path": str(dest), "bytes": total}
else:
    @app.post("/api/pipeline/upload_run")
    async def api_pipeline_upload_run_disabled() -> Dict[str, Any]:
        raise HTTPException(
            status_code=503,
            detail="upload_endpoint_disabled: install 'python-multipart' to enable file uploads",
        )

@app.post("/api/termite/ingest")
def termite_ingest(body: Dict[str, Any]) -> Dict[str, Any]:
    # Only allow ingesting files from the uploads directory (or extra sandbox roots).
    path = _sandbox_path(str(body.get("path") or ""), roots=[UPLOADS_DIR], what="upload", must_exist=True, must_be_file=True)

    cmd = [sys.executable, "-m", "termite.cli", "ingest", str(path)]
    res = _run_cmd(cmd, cwd=TERMITE_DIR)
    return asdict(res)


@app.post("/api/termite/seal")
def termite_seal(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    label = str(body.get("label", "demo") or "demo")
    cmd = [sys.executable, "-m", "termite.cli", "seal", "--label", label]
    res = _run_cmd(cmd, cwd=TERMITE_DIR)

    # In multi-tenant mode, register created bundles so /api/bundles can be scoped.
    if _multi_tenant_enabled() and res.ok:
        try:
            bp = Path((res.stdout or "").strip())
            if bp:
                job_id = create_job(
                    jobs_db_path(),
                    "termite_seal",
                    {"label": label},
                    owner_token_hash=_owner_hash(request) or "",
                )
                from .jobs import succeed_job

                succeed_job(jobs_db_path(), job_id, {"bundle_path": str(bp)})
        except Exception:
            pass
    return asdict(res)


@app.get("/api/bundles")
def list_bundles(request: Request) -> Dict[str, Any]:
    items = _visible_bundle_paths_for_owner(request)
    return {
        "ok": True,
        "bundles": [str(p) for p in items],
    }


def _policy_allowlist_from_body(body: Dict[str, Any]) -> Tuple[Path, Path]:
    policy = _sandbox_path(str(body.get("policy") or DEFAULT_POLICY), roots=[TERMITE_DIR], what="policy", must_exist=True, must_be_file=True)
    allowlist = _sandbox_path(str(body.get("allowlist") or DEFAULT_ALLOWLIST), roots=[TERMITE_DIR], what="allowlist", must_exist=True, must_be_file=True)
    return policy, allowlist


@app.post("/api/termite/verify")
def termite_verify(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    bundle = _sandbox_path(str(body.get("bundle_path", "") or ""), roots=[_path_bundles_dir()], what="bundle", must_exist=True, must_be_file=True)
    _require_visible_bundle(request, bundle)
    policy, allowlist = _policy_allowlist_from_body(body)

    cmd = [
        sys.executable,
        "-m",
        "termite.cli",
        "verify",
        str(bundle),
        "--policy",
        str(policy),
        "--allowlist",
        str(allowlist),
    ]
    res = _run_cmd(cmd, cwd=TERMITE_DIR)
    return asdict(res)


@app.post("/api/termite/replay")
def termite_replay(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    bundle = _sandbox_path(str(body.get("bundle_path", "") or ""), roots=[_path_bundles_dir()], what="bundle", must_exist=True, must_be_file=True)
    _require_visible_bundle(request, bundle)
    policy, allowlist = _policy_allowlist_from_body(body)

    cmd = [
        sys.executable,
        "-m",
        "termite.cli",
        "replay",
        str(bundle),
        "--policy",
        str(policy),
        "--allowlist",
        str(allowlist),
    ]
    res = _run_cmd(cmd, cwd=TERMITE_DIR)
    return asdict(res)


@app.post("/api/ecology/init")
def ecology_init(request: Request) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "mite_ecology.cli", "init"]
    cfg = _tenant_ecology_config_path(request)
    if cfg is not None:
        cmd += ["--config", str(cfg)]
    res = _run_cmd(cmd, cwd=ECOLOGY_DIR)
    return asdict(res)


@app.post("/api/ecology/import")
def ecology_import(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    bundle = _sandbox_path(str(body.get("bundle_path", "") or ""), roots=[_path_bundles_dir()], what="bundle", must_exist=True, must_be_file=True)
    _require_visible_bundle(request, bundle)
    # Default import mode to AUTO_MERGE for the UI so repeat runs work without manual review.
    mode = body.get("mode") or "AUTO_MERGE"

    cmd = [sys.executable, "-m", "mite_ecology.cli", "import-bundle", str(bundle), "--idempotent"]
    cfg = _tenant_ecology_config_path(request)
    if cfg is not None:
        cmd += ["--config", str(cfg)]
    if mode:
        cmd += ["--mode", str(mode)]
    res = _run_cmd(cmd, cwd=ECOLOGY_DIR)

    if not res.ok:
        stderr = (res.stderr or "")
        if "sqlite3.IntegrityError" in stderr and "UNIQUE constraint failed: ingested_bundles.bundle_sha256" in stderr:
            # Idempotent behavior: bundle already ingested.
            res.ok = True
            res.exit_code = 0
            res.stderr = stderr + "\n[ui] Ignored duplicate bundle import (already ingested)."

    return asdict(res)

@app.get("/api/ecology/kg_validate")
def ecology_kg_validate(request: Request) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "mite_ecology.cli", "kg-validate"]
    cfg = _tenant_ecology_config_path(request)
    if cfg is not None:
        cmd += ["--config", str(cfg)]
    res = _run_cmd(cmd, cwd=ECOLOGY_DIR)
    return asdict(res)


@app.post("/api/ecology/review_list")
def ecology_review_list(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    status = body.get("status")
    cmd = [sys.executable, "-m", "mite_ecology.cli", "review-list", "--json"]
    cfg = _tenant_ecology_config_path(request)
    if cfg is not None:
        cmd += ["--config", str(cfg)]
    if status:
        cmd += ["--status", str(status)]
    res = _run_cmd(cmd, cwd=ECOLOGY_DIR)
    return asdict(res)


@app.post("/api/ecology/review_approve")
def ecology_review_approve(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    sid = int(body.get("id", 0))
    actor = str(body.get("actor") or "ui")
    notes = body.get("notes")
    if sid <= 0:
        raise HTTPException(status_code=400, detail="missing id")
    cmd = [sys.executable, "-m", "mite_ecology.cli", "review-approve", str(sid), "--actor", actor]
    cfg = _tenant_ecology_config_path(request)
    if cfg is not None:
        cmd += ["--config", str(cfg)]
    if notes:
        cmd += ["--notes", str(notes)]
    res = _run_cmd(cmd, cwd=ECOLOGY_DIR)
    return asdict(res)


@app.post("/api/ecology/review_reject")
def ecology_review_reject(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    sid = int(body.get("id", 0))
    actor = str(body.get("actor") or "ui")
    notes = body.get("notes")
    if sid <= 0:
        raise HTTPException(status_code=400, detail="missing id")
    cmd = [sys.executable, "-m", "mite_ecology.cli", "review-reject", str(sid), "--actor", actor]
    cfg = _tenant_ecology_config_path(request)
    if cfg is not None:
        cmd += ["--config", str(cfg)]
    if notes:
        cmd += ["--notes", str(notes)]
    res = _run_cmd(cmd, cwd=ECOLOGY_DIR)
    return asdict(res)


@app.post("/api/termite/spec_validate")
def termite_spec_validate(body: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(body.get("kind") or "")
    file_path = _sandbox_path(str(body.get("file_path") or ""), roots=[UPLOADS_DIR], what="file_path", must_exist=True, must_be_file=True)
    cmd = [sys.executable, "-m", "termite.cli", "validate-spec", kind, str(file_path)]
    res = _run_cmd(cmd, cwd=TERMITE_DIR)
    return asdict(res)




@app.post("/api/ecology/full_pipeline")
def ecology_full_pipeline(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    bundle = _sandbox_path(str(body.get("bundle_path", "") or ""), roots=[_path_bundles_dir()], what="bundle", must_exist=True, must_be_file=True)
    _require_visible_bundle(request, bundle)

    # If the ecology config defaults to review-only, a bundle can be staged (exit 0)
    # and the KG remains empty, causing downstream GNN/GAT to fail. For the "full pipeline"
    # UX we default to AUTO_MERGE unless the caller overrides it.
    mode = str(body.get("mode") or "AUTO_MERGE")

    steps: List[Dict[str, Any]] = []

    def step(cmd: List[str]) -> None:
        r = _run_cmd(cmd, cwd=ECOLOGY_DIR)
        steps.append(asdict(r))
        if not r.ok:
            # Make the pipeline idempotent for repeated clicks: importing the same bundle twice
            # can hit a UNIQUE constraint (ingested_bundles.bundle_sha256). That is safe to ignore
            # here since the DB already contains the import.
            stderr = (r.stderr or "")
            if (
                cmd[:4] == [sys.executable, "-m", "mite_ecology.cli", "import-bundle"]
                and "sqlite3.IntegrityError" in stderr
                and "UNIQUE constraint failed: ingested_bundles.bundle_sha256" in stderr
            ):
                steps[-1]["ok"] = True
                steps[-1]["exit_code"] = 0
                steps[-1]["stderr"] = stderr + "\n[ui] Ignored duplicate bundle import (already ingested)."
                return

            raise HTTPException(status_code=400, detail={"failed_step": cmd, "result": asdict(r)})

    cfg = _tenant_ecology_config_path(request)
    cfg_args: List[str] = ["--config", str(cfg)] if cfg is not None else []

    step([sys.executable, "-m", "mite_ecology.cli", "init", *cfg_args])
    step([sys.executable, "-m", "mite_ecology.cli", "import-bundle", str(bundle), "--idempotent", "--mode", mode, *cfg_args])

    # Fail fast with a clearer error if the import did not populate the KG.
    db_path = _tenant_mite_db_path(request)
    try:
        con = _connect_sqlite(db_path)
        try:
            row = con.execute("SELECT COUNT(*) AS n FROM nodes").fetchone()
            n_nodes = int(row["n"] if row else 0)
        finally:
            con.close()
    except Exception:
        n_nodes = -1

    if n_nodes == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "import_produced_no_nodes",
                "hint": "Bundle may have been staged for review; try /api/ecology/import with mode=AUTO_MERGE or approve via mite_ecology review-* commands.",
                "mode": mode,
            },
        )
    step([sys.executable, "-m", "mite_ecology.cli", "gnn", *cfg_args])
    step([sys.executable, "-m", "mite_ecology.cli", "gat", *cfg_args])
    step([sys.executable, "-m", "mite_ecology.cli", "motifs", *cfg_args])
    step([sys.executable, "-m", "mite_ecology.cli", "ga", *cfg_args])
    step([sys.executable, "-m", "mite_ecology.cli", "export", *cfg_args])

    return {"ok": True, "steps": steps}


@app.post("/api/ecology/replay_verify")
def ecology_replay_verify(request: Request) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "mite_ecology.cli", "replay-verify"]
    cfg = _tenant_ecology_config_path(request)
    if cfg is not None:
        cmd += ["--config", str(cfg)]
    res = _run_cmd(cmd, cwd=ECOLOGY_DIR)
    return asdict(res)


@app.get("/api/exports")
def list_exports(request: Request) -> Dict[str, Any]:
    root = _tenant_exports_root(request)
    root.mkdir(parents=True, exist_ok=True)
    items = sorted(root.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "ok": True,
        "exports": [str(p) for p in items if p.is_file()],
    }


def _import_mite_ecology_module(name: str):
    """Import mite_ecology modules in both installed and workspace layouts.

    In this repo layout, the top-level folder `mite_ecology/` contains both:
      - a Python package at `mite_ecology/mite_ecology/*.py`
      - data at `mite_ecology/registry/*.yaml`

    When running from the workspace without installing the package, Python can
    treat `mite_ecology/` as a namespace package and resolve `mite_ecology.registry`
    to the data folder, not the code module.
    """
    from importlib import import_module

    errors = []
    for mod_name in (f"mite_ecology.{name}", f"mite_ecology.mite_ecology.{name}"):
        try:
            return import_module(mod_name)
        except Exception as e:
            errors.append(f"{mod_name}: {e}")

    raise ImportError("; ".join(errors) or f"unable to import mite_ecology.{name}")


def _load_registry_or_500(loader_name: str) -> Dict[str, Any]:
    """Load a local registry via mite_ecology.registry with consistent error shaping."""
    try:
        from importlib import import_module

        # Prefer the normal installed-module path, but fall back to the
        # workspace layout if `mite_ecology.registry` resolves to the YAML
        # directory (namespace package) rather than the code module.
        registry_mod = import_module("mite_ecology.registry")
        if not hasattr(registry_mod, loader_name):
            registry_mod = import_module("mite_ecology.mite_ecology.registry")
        loader = getattr(registry_mod, loader_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"registry_loader_unavailable: {e}")

    try:
        r = loader()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"registry_load_failed: {e}")

    return {
        "ok": True,
        "canonical_sha256": r.canonical_sha256,
        "registry": r.data,
    }


@app.get("/api/registry/components")
def registry_components(_: Request) -> Dict[str, Any]:
    return _load_registry_or_500("load_components_registry")


@app.get("/api/registry/variants")
def registry_variants(_: Request) -> Dict[str, Any]:
    return _load_registry_or_500("load_variants_registry")


@app.get("/api/registry/remotes")
def registry_remotes(_: Request) -> Dict[str, Any]:
    return _load_registry_or_500("load_remotes_registry")


@app.get("/api/remotes/status")
def remotes_status(request: Request) -> Dict[str, Any]:
    try:
        sync_mod = _import_mite_ecology_module("remote_sync")
        load_status = getattr(sync_mod, "load_status")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"remote_sync_unavailable: {e}")

    rr = _load_registry_or_500("load_remotes_registry")["registry"]
    remotes = rr.get("remotes") if isinstance(rr, dict) else []
    cache_root = _tenant_remotes_cache_root(request)

    out = []
    if isinstance(remotes, list):
        for r in remotes:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("remote_id") or "")
            out.append(
                {
                    "remote_id": rid,
                    "enabled": (r.get("enabled") is not False),
                    "tuf_base": r.get("tuf_base"),
                    "status": load_status(cache_root, rid),
                }
            )

    return {"ok": True, "remotes": out}


@app.post("/api/remotes/sync")
def remotes_sync(request: Request, remote_id: str = "") -> Dict[str, Any]:
    try:
        sync_mod = _import_mite_ecology_module("remote_sync")
        sync_all_remotes = getattr(sync_mod, "sync_all_remotes")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"remote_sync_unavailable: {e}")

    rr = _load_registry_or_500("load_remotes_registry")["registry"]
    remotes = rr.get("remotes") if isinstance(rr, dict) else []
    if not isinstance(remotes, list):
        remotes = []

    cache_root = _tenant_remotes_cache_root(request)
    results = sync_all_remotes(remotes, cache_root=cache_root, only_remote_id=(remote_id or "").strip() or None)

    return {
        "ok": True,
        "results": [asdict(r) for r in results],
    }


@app.get("/api/releases")
def releases_list(request: Request) -> Dict[str, Any]:
    root = _tenant_releases_root(request)
    root.mkdir(parents=True, exist_ok=True)

    items = sorted(root.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in items:
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except Exception:
            continue
        rid = p.stem
        out.append(
            {
                "release_id": rid,
                "zip_path": str(p),
                "bytes": int(st.st_size),
                "mtime": float(st.st_mtime),
            }
        )

    return {"ok": True, "releases": out}


@app.post("/api/releases/build")
def releases_build(request: Request, body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    try:
        rel_mod = _import_mite_ecology_module("release")
        build_release = getattr(rel_mod, "build_release")
        release_zip_sha256 = getattr(rel_mod, "release_zip_sha256")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"release_builder_unavailable: {e}")

    out_dir = _tenant_releases_root(request)
    try:
        include_dsse = bool(body.get("include_dsse"))
        include_cyclonedx = bool(body.get("include_cyclonedx"))

        signing_public_key_path = body.get("signing_public_key_path")
        signing_private_key_path = body.get("signing_private_key_path")

        pub_path: Optional[Path] = None
        priv_path: Optional[Path] = None

        if signing_public_key_path:
            pub_path = _sandbox_path(
                str(signing_public_key_path),
                roots=[TERMITE_DIR],
                what="signing_public_key_path",
                must_exist=True,
                must_be_file=True,
            )
        if signing_private_key_path:
            priv_path = _sandbox_path(
                str(signing_private_key_path),
                roots=[TERMITE_DIR],
                what="signing_private_key_path",
                must_exist=True,
                must_be_file=True,
            )

        if include_dsse and (pub_path is None or priv_path is None):
            raise HTTPException(status_code=400, detail="missing_signing_key_paths")

        res = build_release(
            out_dir=out_dir,
            include_dsse=include_dsse,
            include_cyclonedx=include_cyclonedx,
            signing_public_key_path=str(pub_path) if pub_path else None,
            signing_private_key_path=str(priv_path) if priv_path else None,
        )
        # enrich with zip sha for easy pinning
        out = {"ok": True, **res.__dict__}
        out["zip_sha256"] = release_zip_sha256(res.zip_path)
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"release_build_failed: {e}")


@app.post("/api/releases/verify")
def releases_verify(request: Request, body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    try:
        rel_mod = _import_mite_ecology_module("release")
        verify_release_zip = getattr(rel_mod, "verify_release_zip")
        release_zip_sha256 = getattr(rel_mod, "release_zip_sha256")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"release_verifier_unavailable: {e}")

    zip_root = _tenant_releases_root(request)
    zip_path = _sandbox_path(
        str(body.get("zip_path") or ""),
        roots=[zip_root],
        what="zip_path",
        must_exist=True,
        must_be_file=True,
    )

    require_dsse = bool(body.get("require_dsse"))
    require_cyclonedx = bool(body.get("require_cyclonedx"))

    signing_public_key_path = body.get("signing_public_key_path")
    pub_path: Optional[Path] = None
    if signing_public_key_path:
        pub_path = _sandbox_path(
            str(signing_public_key_path),
            roots=[TERMITE_DIR],
            what="signing_public_key_path",
            must_exist=True,
            must_be_file=True,
        )

    try:
        report = verify_release_zip(
            zip_path=str(zip_path),
            signing_public_key_path=str(pub_path) if pub_path else None,
            require_dsse=require_dsse,
            require_cyclonedx=require_cyclonedx,
        )
        return {
            "ok": True,
            "zip_path": str(zip_path),
            "zip_sha256": release_zip_sha256(zip_path),
            "report": report,
        }
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"release_verify_failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"release_verify_error: {e}")


@app.get("/api/graph/nodes")
def graph_nodes(request: Request, filter: str = "", limit: int = 200) -> Dict[str, Any]:
    """
    Lightweight graph browser: returns a slice of nodes plus a suggested center node.

    This endpoint is intentionally schema-tolerant: it supports both the current
    `attrs_json` payload column and older `json` payload column variants.
    """
    db_path = _tenant_mite_db_path(request)
    if not os.path.exists(db_path):
        raise HTTPException(
            404,
            "mite_ecology DB not initialized. In the UI: Ecology → Init DB (or run `python -m mite_ecology init`).",
        )

    # Bound limits to keep the UI responsive on mobile devices.
    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 200
    limit_i = max(1, min(limit_i, 2000))

    flt = (filter or "").strip()

    con = _connect_sqlite(db_path)
    try:
        payload_col = _table_payload_col(con, "nodes")
        if not payload_col:
            payload_col = "attrs_json"  # best-effort default

        if flt:
            like = f"%{flt}%"
            sql = f"""
                SELECT id, type, {payload_col} AS payload_json
                FROM nodes
                WHERE id LIKE ? OR type LIKE ?
                ORDER BY id
                LIMIT ?
            """
            rows = con.execute(sql, (like, like, limit_i)).fetchall()
        else:
            sql = f"SELECT id, type, {payload_col} AS payload_json FROM nodes ORDER BY id LIMIT ?"
            rows = con.execute(sql, (limit_i,)).fetchall()

        nodes: List[Dict[str, Any]] = []
        for r in rows:
            attrs = safe_json_loads(r["payload_json"])
            nodes.append({"id": r["id"], "type": r["type"], "attrs": attrs})

        # Choose a "center" node: if filter yields results, use the first result;
        # otherwise fall back to the first node in the DB.
        center: Optional[Dict[str, Any]] = None
        if nodes:
            center = nodes[0]
        else:
            row = con.execute(
                f"SELECT id, type, {payload_col} AS payload_json FROM nodes ORDER BY id LIMIT 1"
            ).fetchone()
            if row:
                center = {
                    "id": row["id"],
                    "type": row["type"],
                    "attrs": safe_json_loads(row["payload_json"]),
                }

        return {
            "db_path": db_path,
            "payload_col": payload_col,
            "nodes": nodes,
            "center": center,
        }
    finally:
        con.close()

@app.get("/api/graph/neighborhood")
def graph_neighborhood(request: Request, node_id: str, limit_edges: int = 2000) -> Dict[str, Any]:
    """
    Returns a 1-hop neighborhood subgraph for a node.

    `limit_edges` caps the number of edge rows returned to keep the UI responsive.
    """
    db_path = _tenant_mite_db_path(request)
    if not os.path.exists(db_path):
        raise HTTPException(
            404,
            "mite_ecology DB not initialized. In the UI: Ecology → Init DB (or run `python -m mite_ecology init`).",
        )

    try:
        limit_edges_i = int(limit_edges)
    except Exception:
        limit_edges_i = 2000
    limit_edges_i = max(1, min(limit_edges_i, 20000))

    con = _connect_sqlite(db_path)
    try:
        ncol = _table_payload_col(con, "nodes") or "attrs_json"
        ecol = _table_payload_col(con, "edges") or "attrs_json"

        center_row = con.execute(
            f"SELECT id, type, {ncol} AS payload_json FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if not center_row:
            raise HTTPException(404, f"node not found: {node_id}")

        center = {
            "id": center_row["id"],
            "type": center_row["type"],
            "attrs": safe_json_loads(center_row["payload_json"]),
        }

        # Fetch incident edges (both directions). Keep the query simple and fast.
        e_rows = con.execute(
            f"""
            SELECT id, src, dst, type, {ecol} AS payload_json
            FROM edges
            WHERE src = ? OR dst = ?
            ORDER BY id
            LIMIT ?
            """,
            (node_id, node_id, limit_edges_i),
        ).fetchall()

        neighbor_ids = set([node_id])
        edges: List[Dict[str, Any]] = []
        for e in e_rows:
            neighbor_ids.add(e["src"])
            neighbor_ids.add(e["dst"])
            edges.append(
                {
                    "id": e["id"],
                    "src": e["src"],
                    "dst": e["dst"],
                    "type": e["type"],
                    "attrs": safe_json_loads(e["payload_json"]),
                }
            )

        # Cap node count for mobile sanity; keep center always.
        neighbor_list = list(neighbor_ids)
        if len(neighbor_list) > 2500:
            neighbor_list = [node_id] + [x for x in neighbor_list if x != node_id][:2499]

        ph = ",".join(["?"] * len(neighbor_list))
        n_rows = con.execute(
            f"SELECT id, type, {ncol} AS payload_json FROM nodes WHERE id IN ({ph})",
            tuple(neighbor_list),
        ).fetchall()

        nodes: List[Dict[str, Any]] = []
        for r in n_rows:
            nodes.append(
                {
                    "id": r["id"],
                    "type": r["type"],
                    "attrs": safe_json_loads(r["payload_json"]),
                }
            )

        return {
            "db_path": db_path,
            "payload_col_nodes": ncol,
            "payload_col_edges": ecol,
            "center": center,
            "nodes": nodes,
            "edges": edges,
        }
    finally:
        con.close()
