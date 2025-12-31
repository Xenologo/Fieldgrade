from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con

def init_db(con: sqlite3.Connection, schema_sql_path: Path) -> None:
    # Base schema (idempotent)
    con.executescript(schema_sql_path.read_text(encoding="utf-8"))
    con.commit()
    # Lightweight migrations (safe ALTERs) for existing installs
    migrate_db(con)

def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None

def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}

def _add_cols(con: sqlite3.Connection, table: str, cols_sql: Sequence[str]) -> None:
    existing = _cols(con, table)
    for col_sql in cols_sql:
        col_name = col_sql.split()[0]
        if col_name not in existing:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col_sql}")

def migrate_db(con: sqlite3.Connection) -> None:
    """Apply lightweight, idempotent migrations for existing installs.

    NOTE: The canonical schema lives in sql/schema.sql, but we keep a small set of
    safe ALTER-based migrations here so older DBs can be upgraded in-place.
    """

    # ingested_bundles extended fields
    if _table_exists(con, "ingested_bundles"):
        _add_cols(
            con,
            "ingested_bundles",
            [
                "verify_reason TEXT",
                "policy_id TEXT",
                "toolchain_id TEXT",
                "bundle_map_hash TEXT",
                "ingest_kind TEXT NOT NULL DEFAULT 'MERGED'",
            ],
        )

    # staged_bundles table for REVIEW_ONLY / QUARANTINE mode
    if not _table_exists(con, "staged_bundles"):
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS staged_bundles (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts_utc TEXT NOT NULL,
              bundle_sha256 TEXT NOT NULL,
              bundle_name TEXT NOT NULL,
              verified_ok INTEGER NOT NULL,
              verify_reason TEXT,
              policy_id TEXT,
              policy_hash TEXT,
              allowlist_hash TEXT,
              toolchain_id TEXT,
              bundle_map_hash TEXT,
              ops_count INTEGER NOT NULL,
              kg_delta_payload TEXT NOT NULL,
              kg_delta_hash TEXT NOT NULL,
              status TEXT NOT NULL,
                            policy_mode TEXT NOT NULL,
              contracts_report_json TEXT,
              kg_shacl_report_json TEXT,
              decision_ts_utc TEXT,
              decision_actor TEXT,
              decision_notes TEXT,
              prev_hash TEXT,
              stage_hash TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uidx_staged_bundles_sha ON staged_bundles(bundle_sha256);
            CREATE INDEX IF NOT EXISTS idx_staged_bundles_status ON staged_bundles(status);
            CREATE INDEX IF NOT EXISTS idx_staged_bundles_ts ON staged_bundles(ts_utc);
            """
        )

    # Ensure staged_bundles analytics/report fields exist for older installs
    if _table_exists(con, "staged_bundles"):
        _add_cols(
            con,
            "staged_bundles",
            [
                "policy_mode TEXT NOT NULL DEFAULT 'REVIEW_ONLY'",
                "contracts_report_json TEXT",
                "kg_shacl_report_json TEXT",
                "decision_ts_utc TEXT",
                "decision_actor TEXT",
                "decision_notes TEXT",
                "prev_hash TEXT",
                "stage_hash TEXT",
            ],
        )

    # kg_deltas: unify schema across accept/replay/llm flows
    if _table_exists(con, "kg_deltas"):
        # Older installs may have a reduced kg_deltas table (no source/delta_kind/chain_hash).
        _add_cols(
            con,
            "kg_deltas",
            [
                "source TEXT NOT NULL DEFAULT 'UNKNOWN'",
                "context_node_id TEXT",
                "delta_kind TEXT NOT NULL DEFAULT 'KG_DELTA'",
                "delta_payload TEXT NOT NULL DEFAULT ''",
                "prev_hash TEXT",
                "chain_hash TEXT",
            ],
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_kg_deltas_context ON kg_deltas(context_node_id)")

        # Backfill prev_hash + chain_hash deterministically (id order) if possible.
        cols = _cols(con, "kg_deltas")
        if {"id", "delta_hash", "prev_hash", "chain_hash"}.issubset(cols):
            import hashlib

            def _sha(s: str) -> str:
                return hashlib.sha256(s.encode("utf-8")).hexdigest()

            rows = con.execute(
                "SELECT id, delta_hash, prev_hash, chain_hash FROM kg_deltas ORDER BY id ASC"
            ).fetchall()
            prev: str | None = None
            needs = False
            for r in rows:
                if (r["prev_hash"] or None) != prev or (r["chain_hash"] is None):
                    needs = True
                    break
                prev = str(r["delta_hash"])

            if needs:
                prev = None
                for r in rows:
                    dh = str(r["delta_hash"])
                    ch = _sha((prev or "") + "|" + dh)
                    con.execute(
                        "UPDATE kg_deltas SET prev_hash=?, chain_hash=? WHERE id=?",
                        (prev, ch, int(r["id"])),
                    )
                    prev = dh

    con.commit()
