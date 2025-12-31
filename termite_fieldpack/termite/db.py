from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con

def init_db(con: sqlite3.Connection, schema_sql_path: Path) -> None:
    con.executescript(schema_sql_path.read_text(encoding="utf-8"))
    con.commit()

def sqlite_has_fts5(con: sqlite3.Connection) -> bool:
    try:
        rows = con.execute("PRAGMA compile_options;").fetchall()
        opts = {r[0] for r in rows}
        return any("FTS5" in o for o in opts)
    except Exception:
        return False

def latest_event_hash(con: sqlite3.Connection) -> Optional[str]:
    row = con.execute("SELECT event_hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
    return None if row is None else str(row["event_hash"])

def insert_blob(con, sha256: str, kind: str, size_bytes: int, created_utc: str, source_path: str | None):
    con.execute(
        "INSERT OR IGNORE INTO blobs(sha256, kind, size_bytes, created_utc, source_path) VALUES(?,?,?,?,?)",
        (sha256, kind, size_bytes, created_utc, source_path),
    )

def insert_doc(con, path: str, mime: str | None, raw_blob_sha256: str, extract_blob_sha256: str | None, created_utc: str) -> int:
    cur = con.execute(
        "INSERT INTO docs(path, mime, raw_blob_sha256, extract_blob_sha256, created_utc) VALUES(?,?,?,?,?)",
        (path, mime, raw_blob_sha256, extract_blob_sha256, created_utc),
    )
    return int(cur.lastrowid)

def insert_chunk(con, doc_id: int, chunk_index: int, start_char: int, end_char: int, text: str, text_sha256: str, created_utc: str):
    con.execute(
        "INSERT INTO chunks(doc_id, chunk_index, start_char, end_char, text, text_sha256, created_utc) VALUES(?,?,?,?,?,?,?)",
        (doc_id, chunk_index, start_char, end_char, text, text_sha256, created_utc),
    )

def insert_kg_op(con, ts_utc: str, op_json: str, op_hash: str):
    con.execute("INSERT INTO kg_ops(ts_utc, op_json, op_hash) VALUES(?,?,?)", (ts_utc, op_json, op_hash))

def export_kg_ops_jsonl(con) -> str:
    rows = con.execute("SELECT op_json FROM kg_ops ORDER BY id ASC").fetchall()
    if not rows:
        return ""
    return "\n".join([str(r["op_json"]) for r in rows]) + "\n"

def export_provenance_jsonl(con) -> str:
    rows = con.execute("SELECT ts_utc, event_type, payload_json, prev_hash, event_hash FROM events ORDER BY id ASC").fetchall()
    if not rows:
        return ""
    return "\n".join([
        '{"ts_utc":' + json_escape(r["ts_utc"]) + ',"event_type":' + json_escape(r["event_type"]) +
        ',"payload":' + (r["payload_json"] or "{}") +
        ',"prev_hash":' + (json_escape(r["prev_hash"]) if r["prev_hash"] is not None else "null") +
        ',"event_hash":' + json_escape(r["event_hash"]) + '}'
        for r in rows
    ]) + "\n"

def json_escape(s: str) -> str:
    import json
    return json.dumps(str(s), ensure_ascii=False)
