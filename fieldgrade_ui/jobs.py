from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

STATUSES = ("queued", "running", "succeeded", "failed", "canceled")

@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    status: str
    owner_token_hash: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: float
    started_at: Optional[float]
    finished_at: Optional[float]

def _now() -> float:
    return time.time()

def ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                owner_token_hash TEXT NOT NULL DEFAULT '',
                params_json TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL
            )
            """
        )

        # Lightweight migration: older DBs won't have owner_token_hash.
        cols = [r[1] for r in con.execute("PRAGMA table_info(jobs)").fetchall()]
        if "owner_token_hash" not in cols:
            con.execute("ALTER TABLE jobs ADD COLUMN owner_token_hash TEXT NOT NULL DEFAULT '';")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                ts REAL NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_owner_id ON jobs(owner_token_hash, id);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_job ON job_logs(job_id, ts);")
        con.commit()
    finally:
        con.close()

def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    return con

def create_job(db_path: Path, kind: str, params: Dict[str, Any], *, owner_token_hash: str = "") -> int:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO jobs(kind, status, owner_token_hash, params_json, created_at) VALUES (?, 'queued', ?, ?, ?)",
            (kind, owner_token_hash or "", json.dumps(params, ensure_ascii=False), _now()),
        )
        job_id = int(cur.lastrowid)
        con.execute(
            "INSERT INTO job_logs(job_id, ts, level, message) VALUES (?, ?, ?, ?)",
            (job_id, _now(), "info", f"enqueued kind={kind}"),
        )
        return job_id
    finally:
        con.close()

def list_jobs(
    db_path: Path,
    *,
    owner_token_hash: Optional[str] = None,
    limit: int = 50,
    status: Optional[str] = None,
) -> List[Job]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        # Use fixed SQL strings (no string interpolation) to keep query
        # construction obviously safe for scanners and reviewers.
        if owner_token_hash is None and not status:
            sql = "SELECT * FROM jobs ORDER BY id DESC LIMIT ?"
            params = (limit,)
        elif owner_token_hash is not None and not status:
            sql = "SELECT * FROM jobs WHERE owner_token_hash=? ORDER BY id DESC LIMIT ?"
            params = (owner_token_hash, limit)
        elif owner_token_hash is None and status:
            sql = "SELECT * FROM jobs WHERE status=? ORDER BY id DESC LIMIT ?"
            params = (status, limit)
        else:
            sql = "SELECT * FROM jobs WHERE owner_token_hash=? AND status=? ORDER BY id DESC LIMIT ?"
            params = (owner_token_hash, status, limit)

        rows = con.execute(sql, params).fetchall()
        return [_row_to_job(r) for r in rows]
    finally:
        con.close()

def get_job(db_path: Path, job_id: int, *, owner_token_hash: Optional[str] = None) -> Optional[Job]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if owner_token_hash is None:
            r = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        else:
            r = con.execute("SELECT * FROM jobs WHERE id=? AND owner_token_hash=?", (job_id, owner_token_hash)).fetchone()
        return _row_to_job(r) if r else None
    finally:
        con.close()

def get_job_logs(
    db_path: Path,
    job_id: int,
    *,
    owner_token_hash: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if owner_token_hash is None:
            rows = con.execute(
                "SELECT ts, level, message FROM job_logs WHERE job_id=? ORDER BY id ASC LIMIT ?",
                (job_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT l.ts, l.level, l.message
                FROM job_logs l
                JOIN jobs j ON j.id = l.job_id
                WHERE l.job_id=? AND j.owner_token_hash=?
                ORDER BY l.id ASC
                LIMIT ?
                """,
                (job_id, owner_token_hash, limit),
            ).fetchall()
        return [{"ts": float(r["ts"]), "level": str(r["level"]), "message": str(r["message"])} for r in rows]
    finally:
        con.close()

def append_log(db_path: Path, job_id: int, level: str, message: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO job_logs(job_id, ts, level, message) VALUES (?, ?, ?, ?)",
            (job_id, _now(), level, message),
        )
    finally:
        con.close()

def cancel_job(db_path: Path, job_id: int, *, owner_token_hash: Optional[str] = None) -> bool:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        if owner_token_hash is None:
            cur = con.execute(
                "UPDATE jobs SET status='canceled', finished_at=? WHERE id=? AND status IN ('queued')",
                (_now(), job_id),
            )
        else:
            cur = con.execute(
                "UPDATE jobs SET status='canceled', finished_at=? WHERE id=? AND owner_token_hash=? AND status IN ('queued')",
                (_now(), job_id, owner_token_hash),
            )
        ok = cur.rowcount > 0
        if ok:
            append_log(db_path, job_id, "warn", "canceled by user")
        return ok
    finally:
        con.close()

def claim_next_job(db_path: Path, kinds: Optional[Iterable[str]] = None) -> Optional[Tuple[int, str, Dict[str, Any]]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE;")
        if kinds:
            kinds = list(kinds)
            placeholders = ",".join("?" for _ in kinds)
            row = con.execute(
                f"SELECT id, kind, params_json FROM jobs WHERE status='queued' AND kind IN ({placeholders}) ORDER BY id ASC LIMIT 1",
                tuple(kinds),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT id, kind, params_json FROM jobs WHERE status='queued' ORDER BY id ASC LIMIT 1"
            ).fetchone()

        if not row:
            con.execute("COMMIT;")
            return None

        job_id = int(row["id"])
        con.execute(
            "UPDATE jobs SET status='running', started_at=? WHERE id=? AND status='queued'",
            (_now(), job_id),
        )
        con.execute("INSERT INTO job_logs(job_id, ts, level, message) VALUES (?, ?, ?, ?)",
                    (job_id, _now(), "info", "claimed by worker"))
        con.execute("COMMIT;")

        params = json.loads(row["params_json"])
        return job_id, str(row["kind"]), params
    except Exception:
        try:
            con.execute("ROLLBACK;")
        except Exception:
            pass
        raise
    finally:
        con.close()

def succeed_job(db_path: Path, job_id: int, result: Dict[str, Any]) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE jobs SET status='succeeded', result_json=?, finished_at=? WHERE id=?",
            (json.dumps(result, ensure_ascii=False), _now(), job_id),
        )
        con.execute(
            "INSERT INTO job_logs(job_id, ts, level, message) VALUES (?, ?, ?, ?)",
            (job_id, _now(), "info", "succeeded"),
        )
    finally:
        con.close()

def fail_job(db_path: Path, job_id: int, error: str) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE jobs SET status='failed', error=?, finished_at=? WHERE id=?",
            (error, _now(), job_id),
        )
        con.execute(
            "INSERT INTO job_logs(job_id, ts, level, message) VALUES (?, ?, ?, ?)",
            (job_id, _now(), "error", error),
        )
    finally:
        con.close()

def _row_to_job(r: Any) -> Job:
    params = json.loads(r["params_json"]) if r["params_json"] else {}
    result = json.loads(r["result_json"]) if r["result_json"] else None
    return Job(
        id=int(r["id"]),
        kind=str(r["kind"]),
        status=str(r["status"]),
        owner_token_hash=str(r["owner_token_hash"] or ""),
        params=params,
        result=result,
        error=str(r["error"]) if r["error"] else None,
        created_at=float(r["created_at"]),
        started_at=float(r["started_at"]) if r["started_at"] is not None else None,
        finished_at=float(r["finished_at"]) if r["finished_at"] is not None else None,
    )
