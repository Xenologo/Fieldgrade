from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from mite_ecology.hashutil import canonical_json, sha256_str

from .jobs import ensure_db as ensure_jobs_db


EXECUTION_STATUSES = (
    "pending",
    "running",
    "passed",
    "failed",
    "paused",
    "paused_drift",
    "aborted",
)


@dataclass(frozen=True)
class ExecutionEvent:
    id: int
    execution_id: str
    plan_id: str
    step_index: int
    action_type: str
    status: str
    expected: Optional[Dict[str, Any]]
    observed: Optional[Dict[str, Any]]
    drift: Optional[Dict[str, Any]]
    actor_id: str
    justification: Optional[str]
    ts_ms: int
    prev_hash: Optional[str]
    event_hash: str


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    return con


def ensure_db(db_path: Path) -> None:
    """Ensure jobs DB + execution ledger tables exist.

    Reuses the existing jobs SQLite file so deployments keep a single runtime DB.
    """

    ensure_jobs_db(db_path)

    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA journal_mode=WAL;")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS executions (
                execution_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                base_snapshot_hash TEXT NOT NULL,
                owner_token_hash TEXT NOT NULL DEFAULT '',
                created_at_ms INTEGER NOT NULL
            )
            """
        )

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL,
                expected_json TEXT,
                observed_json TEXT,
                drift_json TEXT,
                actor_id TEXT NOT NULL,
                justification TEXT,
                ts_ms INTEGER NOT NULL,
                prev_hash TEXT,
                event_hash TEXT NOT NULL,
                FOREIGN KEY(execution_id) REFERENCES executions(execution_id)
            )
            """
        )

        con.execute("CREATE INDEX IF NOT EXISTS idx_exec_events_exec ON execution_events(execution_id, id);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_exec_events_hash ON execution_events(execution_id, event_hash);")

        # Make the event log append-only at the DB level.
        # (Operators can still manually edit SQLite; the hash-chain detects that.)
        con.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_execution_events_no_update
            BEFORE UPDATE ON execution_events
            BEGIN
                SELECT RAISE(FAIL, 'execution_events is append-only');
            END;
            """
        )
        con.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_execution_events_no_delete
            BEFORE DELETE ON execution_events
            BEGIN
                SELECT RAISE(FAIL, 'execution_events is append-only');
            END;
            """
        )

        con.commit()
    finally:
        con.close()


def create_execution(
    db_path: Path,
    *,
    plan_id: str,
    base_snapshot_hash: str,
    owner_token_hash: str = "",
    execution_id: Optional[str] = None,
) -> str:
    ensure_db(db_path)

    pid = str(plan_id).strip()
    if not pid:
        raise ValueError("plan_id must be non-empty")

    bsh = str(base_snapshot_hash).strip()
    if not bsh:
        raise ValueError("base_snapshot_hash must be non-empty")

    eid = (execution_id or "").strip() or uuid.uuid4().hex
    ts_ms = int(time.time() * 1000)

    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO executions(execution_id, plan_id, base_snapshot_hash, owner_token_hash, created_at_ms) VALUES (?, ?, ?, ?, ?)",
            (eid, pid, bsh, owner_token_hash or "", ts_ms),
        )
        return eid
    finally:
        con.close()


def _latest_event_hash(con: sqlite3.Connection, execution_id: str) -> Optional[str]:
    row = con.execute(
        "SELECT event_hash FROM execution_events WHERE execution_id=? ORDER BY id DESC LIMIT 1",
        (execution_id,),
    ).fetchone()
    if not row:
        return None
    h = row[0]
    return str(h) if h else None


def _hash_event(prev_hash: Optional[str], body: Dict[str, Any]) -> str:
    return sha256_str((prev_hash or "") + "|" + canonical_json(body))


def append_event(
    db_path: Path,
    *,
    execution_id: str,
    plan_id: str,
    step_index: int,
    action_type: str,
    status: str,
    expected: Optional[Dict[str, Any]] = None,
    observed: Optional[Dict[str, Any]] = None,
    drift: Optional[Dict[str, Any]] = None,
    actor_id: str = "",
    justification: Optional[str] = None,
    ts_ms: Optional[int] = None,
) -> str:
    """Append one execution event and return its event_hash."""

    ensure_db(db_path)

    eid = str(execution_id).strip()
    pid = str(plan_id).strip()
    if not eid:
        raise ValueError("execution_id must be non-empty")
    if not pid:
        raise ValueError("plan_id must be non-empty")

    if not isinstance(step_index, int) or step_index < 0:
        raise ValueError("step_index must be a non-negative int")

    act = str(action_type).strip()
    if not act:
        raise ValueError("action_type must be non-empty")

    st = str(status).strip().lower()
    if st not in EXECUTION_STATUSES:
        raise ValueError(f"invalid status={status!r}")

    actor = str(actor_id).strip() or "system"
    now_ms = int(time.time() * 1000) if ts_ms is None else int(ts_ms)

    con = _connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE;")

        prev = _latest_event_hash(con, eid)
        body = {
            "v": 1,
            "kind": "execution_event",
            "prev_hash": prev,
            "payload": {
                "execution_id": eid,
                "plan_id": pid,
                "step_index": int(step_index),
                "action_type": act,
                "status": st,
                "expected": expected or None,
                "observed": observed or None,
                "drift": drift or None,
                "actor_id": actor,
                "justification": (str(justification) if justification is not None else None),
                "ts_ms": now_ms,
            },
        }
        ev_hash = _hash_event(prev, body)

        def _dump_or_none(obj: Optional[Dict[str, Any]]) -> Optional[str]:
            if obj is None:
                return None
            return canonical_json(obj)

        con.execute(
            """
            INSERT INTO execution_events(
                execution_id, plan_id, step_index, action_type, status,
                expected_json, observed_json, drift_json,
                actor_id, justification, ts_ms,
                prev_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eid,
                pid,
                int(step_index),
                act,
                st,
                _dump_or_none(expected),
                _dump_or_none(observed),
                _dump_or_none(drift),
                actor,
                (str(justification) if justification is not None else None),
                now_ms,
                prev,
                ev_hash,
            ),
        )

        con.execute("COMMIT;")
        return ev_hash
    except Exception:
        try:
            con.execute("ROLLBACK;")
        except Exception:
            pass
        raise
    finally:
        con.close()


def iter_events(db_path: Path, execution_id: str) -> Iterator[ExecutionEvent]:
    ensure_db(db_path)

    eid = str(execution_id).strip()
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM execution_events WHERE execution_id=? ORDER BY id ASC",
            (eid,),
        ).fetchall()
        for r in rows:
            expected = json.loads(r["expected_json"]) if r["expected_json"] else None
            observed = json.loads(r["observed_json"]) if r["observed_json"] else None
            drift = json.loads(r["drift_json"]) if r["drift_json"] else None
            yield ExecutionEvent(
                id=int(r["id"]),
                execution_id=str(r["execution_id"]),
                plan_id=str(r["plan_id"]),
                step_index=int(r["step_index"]),
                action_type=str(r["action_type"]),
                status=str(r["status"]),
                expected=expected,
                observed=observed,
                drift=drift,
                actor_id=str(r["actor_id"]),
                justification=(str(r["justification"]) if r["justification"] is not None else None),
                ts_ms=int(r["ts_ms"]),
                prev_hash=(str(r["prev_hash"]) if r["prev_hash"] else None),
                event_hash=str(r["event_hash"]),
            )
    finally:
        con.close()


def verify_chain(db_path: Path, execution_id: str) -> Tuple[bool, int]:
    """Verify hash-chain integrity for one execution.

    Returns (ok, events_count).
    """

    prev: Optional[str] = None
    n = 0
    for ev in iter_events(db_path, execution_id):
        n += 1
        if ev.prev_hash != prev:
            return False, n

        body = {
            "v": 1,
            "kind": "execution_event",
            "prev_hash": prev,
            "payload": {
                "execution_id": ev.execution_id,
                "plan_id": ev.plan_id,
                "step_index": int(ev.step_index),
                "action_type": ev.action_type,
                "status": ev.status,
                "expected": ev.expected or None,
                "observed": ev.observed or None,
                "drift": ev.drift or None,
                "actor_id": ev.actor_id,
                "justification": ev.justification,
                "ts_ms": int(ev.ts_ms),
            },
        }
        expected_hash = _hash_event(prev, body)
        if ev.event_hash != expected_hash:
            return False, n

        prev = ev.event_hash

    return True, n
