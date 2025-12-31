from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from .db import latest_event_hash

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def hash_event(prev_hash: Optional[str], event_type: str, payload: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update((prev_hash or "").encode("utf-8"))
    h.update(b"|")
    h.update(event_type.encode("utf-8"))
    h.update(b"|")
    h.update(canonical_json(payload).encode("utf-8"))
    return h.hexdigest()

def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def hash_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

@dataclass
class Provenance:
    toolchain_id: str

    def append_event(self, con, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        prev = latest_event_hash(con)
        ts = utc_now_iso()
        payload2 = dict(payload)
        payload2.setdefault("toolchain_id", self.toolchain_id)
        payload2.setdefault("ts_utc", ts)
        ev_hash = hash_event(prev, event_type, payload2)
        con.execute(
            "INSERT INTO events(ts_utc, event_type, payload_json, prev_hash, event_hash) VALUES(?,?,?,?,?)",
            (ts, event_type, canonical_json(payload2), prev, ev_hash),
        )
        con.commit()
        return {"ts_utc": ts, "event_type": event_type, "prev_hash": prev, "event_hash": ev_hash, "payload": payload2}

def verify_chain(con) -> bool:
    rows = con.execute("SELECT id, event_type, payload_json, prev_hash, event_hash FROM events ORDER BY id ASC").fetchall()
    prev = None
    import json as _json
    for r in rows:
        payload = _json.loads(r["payload_json"])
        expected = hash_event(prev, r["event_type"], payload)
        if expected != r["event_hash"]:
            return False
        prev = r["event_hash"]
    return True
