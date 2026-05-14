from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from mite_ecology.db import connect as connect_mite_db
from mite_ecology.db import init_db as init_mite_db

from .config import jobs_db_path, repo_root
from .execution_ledger import ensure_db as ensure_jobs_and_ledger_db


def _safe_resolve_path(p: Path) -> Path:
    p = Path(p).expanduser()
    try:
        return p.resolve(strict=False)
    except Exception:
        try:
            return p.resolve()
        except Exception:
            return p


def mite_db_path() -> Path:
    override = os.getenv("FG_MITE_DB") or os.getenv("MITE_ECOLOGY_DB")
    if override:
        return _safe_resolve_path(Path(override))

    root = repo_root()
    candidates = [
        root / "mite_ecology" / "runtime" / "mite_ecology.sqlite",
        root / "mite_ecology" / "runtime" / "mite_ecology.db",
        root / "mite_ecology" / "mite_ecology.sqlite",
        root / "mite_ecology.sqlite",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def init_runtime() -> dict[str, Any]:
    jobs_db = jobs_db_path()
    ensure_jobs_and_ledger_db(jobs_db)

    mite_db = mite_db_path()
    con = connect_mite_db(mite_db)
    try:
        init_mite_db(con, repo_root() / "mite_ecology" / "sql" / "schema.sql")
    finally:
        con.close()

    return {
        "ok": True,
        "jobs_db": str(jobs_db),
        "mite_db": str(mite_db),
    }


def main() -> None:
    json.dump(init_runtime(), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
