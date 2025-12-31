from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlparse
from pathlib import Path
from typing import Iterable, Optional

"""Fieldgrade UI configuration helpers.

This module is the single source of truth for environment variables used by
`fieldgrade_ui`.

**Server / API**
- `FG_HOST` (fallback `FIELDGRADE_UI_HOST`, default `127.0.0.1`): bind host
- `FG_PORT` (fallback `FIELDGRADE_UI_PORT`, default `8787`): bind port
- `FG_WORKERS` (fallback `FIELDGRADE_UI_WORKERS`, default `1`): uvicorn workers
- `FG_LOG_LEVEL` (default `info`): uvicorn log level
- `FG_RELOAD` (default `0`): set to `1` to enable auto-reload (dev)
- `FG_API_TOKEN` (fallback `FIELDGRADE_UI_API_TOKEN`, default empty): API auth

**Worker / jobs**
- `FG_JOBS_DB` (default `{repo}/fieldgrade_ui/runtime/jobs.sqlite`): jobs DB path
- `FG_ENABLE_WORKER` (default empty): if set, `1` enables embedded worker
- `FG_WORKER_POLL` (default `1.0`): worker poll interval in seconds

**Database (Phase B prep)**
- `DATABASE_URL` or `FG_DATABASE_URL`: database URL.
    - Today only `sqlite://...` is supported; Postgres is a Phase B change.

**Timeouts**
- `FG_CMD_TIMEOUT_S` (default `600`): subprocess timeout seconds; `0` disables

**Filesystem sandboxes**
- `FG_UPLOADS_DIR` (fallback `FIELDGRADE_UPLOADS_DIR`): uploads directory override
- `FG_API_EXTRA_ROOTS`: additional allowed roots for path-bearing endpoints
    - separated by platform `os.pathsep`; also accepts `:` if unambiguous on Windows

**Upload watcher**
- `FG_WATCH_STATE` (default `{repo}/fieldgrade_ui/runtime/upload_watch.json`)
- `FG_WATCH_UPLOADS` (default `0`): set to `1` to enable background upload watcher
- `FG_WATCH_POLL` (default `2.0`): watcher scan interval
- `FG_WATCH_LABEL` (default `watch`): label for watcher-enqueued jobs

**Pipeline boundary**
- `FG_PIPELINE_RUNNER` (default `subprocess`): `subprocess` or `library`

**Reverse proxy / TLS termination**
- `FG_PROXY_HEADERS` (default `0`): set to `1` when running behind a reverse proxy (Caddy/Nginx)
- `FG_FORWARDED_ALLOW_IPS` (default `127.0.0.1`): uvicorn forwarded-allow-ips setting
"""

def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_resolve_path(p: Path) -> Path:
    p = Path(p).expanduser()
    try:
        return p.resolve(strict=False)
    except Exception:
        try:
            return p.resolve()
        except Exception:
            return p


def env_str(*names: str, default: str = "") -> str:
    for n in names:
        v = os.environ.get(n)
        if v is not None and str(v) != "":
            return str(v)
    return default


def env_bool(*names: str, default: bool = False) -> bool:
    v = env_str(*names, default="")
    if v == "":
        return bool(default)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def env_int(*names: str, default: int) -> int:
    v = env_str(*names, default="")
    if v == "":
        return int(default)
    try:
        return int(str(v).strip())
    except Exception:
        return int(default)


def env_float(*names: str, default: float) -> float:
    v = env_str(*names, default="")
    if v == "":
        return float(default)
    try:
        return float(str(v).strip())
    except Exception:
        return float(default)


def split_env_path_list(raw: str) -> list[str]:
    """Split a list of paths from an env var.

    Uses platform `os.pathsep`. For compatibility with older configs, also accepts
    ':' on platforms where `os.pathsep` is not ':' (e.g. Windows) *only* when the
    string doesn't look like a drive-letter path list.
    """
    s = (raw or "").strip()
    if not s:
        return []

    parts = [p.strip() for p in s.split(os.pathsep) if p.strip()]
    if os.pathsep != ":" and len(parts) == 1 and ":" in s and not re.search(r"[A-Za-z]:[\\/]", s):
        parts = [p.strip() for p in s.split(":") if p.strip()]
    return parts


def cmd_timeout_s() -> Optional[float]:
    raw = (os.environ.get("FG_CMD_TIMEOUT_S", "600") or "600").strip()
    try:
        v = float(raw)
    except Exception:
        v = 600.0
    if v <= 0:
        return None
    return v


def ui_host() -> str:
    return env_str("FG_HOST", "FIELDGRADE_UI_HOST", default="127.0.0.1")


def ui_port() -> int:
    return env_int("FG_PORT", "FIELDGRADE_UI_PORT", default=8787)


def ui_workers() -> int:
    return env_int("FG_WORKERS", "FIELDGRADE_UI_WORKERS", default=1)


def ui_log_level() -> str:
    return env_str("FG_LOG_LEVEL", default="info")


def ui_reload() -> bool:
    return env_bool("FG_RELOAD", default=False)


def api_token() -> str:
    return env_str("FG_API_TOKEN", "FIELDGRADE_UI_API_TOKEN", default="").strip()


def api_tokens() -> list[str]:
    """Return configured API tokens.

    Back-compat:
        - If FG_API_TOKENS is unset/empty, falls back to FG_API_TOKEN.

    New:
        - FG_API_TOKENS: comma-separated list of tokens (whitespace trimmed).
    """
    raw = env_str("FG_API_TOKENS", default="").strip()
    if raw:
        toks = [t.strip() for t in raw.split(",")]
        return [t for t in toks if t]
    t = api_token()
    return [t] if t else []


def database_url() -> str:
    """Return configured DB URL.

    If DATABASE_URL/FG_DATABASE_URL is not set, this returns a sqlite URL derived
    from the existing FG_JOBS_DB / default jobs DB path.
    """
    raw = env_str("DATABASE_URL", "FG_DATABASE_URL", default="").strip()
    if raw:
        return raw

    # Back-compat: derive sqlite URL from legacy path config.
    p = jobs_db_path()
    # sqlite:///C:/path/to/file.sqlite on Windows; sqlite:////abs/path on Linux.
    posix = p.as_posix()
    if re.match(r"^[A-Za-z]:/", posix):
        return f"sqlite:///{posix}"
    return f"sqlite:////{posix.lstrip('/')}"


def _sqlite_path_from_url(url: str) -> Optional[Path]:
    """Parse a sqlite URL into a filesystem path.

    Supported forms:
    - sqlite:////abs/path/to.db
    - sqlite:///C:/path/to.db
    - sqlite:///relative/path.db (treated as relative)
    """
    u = (url or "").strip()
    if not u:
        return None
    parsed = urlparse(u)
    if (parsed.scheme or "").lower() != "sqlite":
        return None

    # urlparse puts the filesystem path in `path`; decode percent-escapes.
    raw_path = unquote(parsed.path or "")

    # Handle Windows drive-letter form sqlite:///C:/...
    if re.match(r"^/[A-Za-z]:/", raw_path):
        raw_path = raw_path.lstrip("/")

    if not raw_path:
        return None
    return _safe_resolve_path(Path(raw_path))


def jobs_db_path() -> Path:
    db_url = env_str("DATABASE_URL", "FG_DATABASE_URL", default="").strip()
    if db_url:
        p = _sqlite_path_from_url(db_url)
        if p is None:
            raise RuntimeError(
                "Non-sqlite DATABASE_URL is not supported yet. "
                "Use sqlite (DATABASE_URL=sqlite://...) for now; Postgres is a Phase B change."
            )
        return p

    p = os.environ.get("FG_JOBS_DB", "")
    if p:
        return _safe_resolve_path(Path(p))
    return repo_root() / "fieldgrade_ui" / "runtime" / "jobs.sqlite"


def proxy_headers_enabled() -> bool:
    return env_bool("FG_PROXY_HEADERS", default=False)


def forwarded_allow_ips() -> str:
    return env_str("FG_FORWARDED_ALLOW_IPS", default="127.0.0.1")


def uploads_dir(default: Path) -> Path:
    override = os.environ.get("FG_UPLOADS_DIR") or os.environ.get("FIELDGRADE_UPLOADS_DIR")
    if override:
        return _safe_resolve_path(Path(override))
    return _safe_resolve_path(default)


def api_extra_roots() -> list[Path]:
    raw = (os.environ.get("FG_API_EXTRA_ROOTS") or "").strip()
    return [_safe_resolve_path(Path(p)) for p in split_env_path_list(raw)]


def watch_state_path() -> Path:
    p = os.environ.get("FG_WATCH_STATE", "")
    if p:
        return _safe_resolve_path(Path(p))
    return repo_root() / "fieldgrade_ui" / "runtime" / "upload_watch.json"

def enable_embedded_worker() -> bool:
    # Safe default: enable embedded worker only when running a single server worker.
    if os.environ.get("FG_ENABLE_WORKER", ""):
        return os.environ.get("FG_ENABLE_WORKER", "0") == "1"
    try:
        workers = ui_workers()
    except Exception:
        workers = 1
    return workers == 1
