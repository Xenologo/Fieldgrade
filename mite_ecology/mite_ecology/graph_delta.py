from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

from .hashutil import canonical_json, sha256_hex, sha256_str


def urn_mite(kind: str, value: Any) -> str:
    """Build a stable, content-addressed URN.

    - For dict/list/etc: sha256(canonical_json(value))
    - For str: sha256(value as utf-8)
    - For bytes: sha256(bytes)

    Output: urn:mite:<kind>:<sha256>
    """
    k = str(kind).strip().lower()
    if not k:
        raise ValueError("kind must be non-empty")

    if isinstance(value, (bytes, bytearray, memoryview)):
        h = sha256_hex(bytes(value))
    elif isinstance(value, str):
        h = sha256_str(value)
    else:
        h = sha256_str(canonical_json(value))

    return f"urn:mite:{k}:{h}"


def default_ledger_path_for_db(db_path: Path) -> Path:
    return db_path.resolve().parent / "graph_delta_ledger.jsonl"


def _canonical_jsonl(lines: Iterable[str]) -> str:
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # Ensure each line is canonical JSON.
        out.append(canonical_json(json.loads(s)))
    return "\n".join(out) + ("\n" if out else "")


def _read_last_nonempty_line(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    data = path.read_bytes()
    if not data:
        return None
    lines = data.decode("utf-8").splitlines()
    for ln in reversed(lines):
        if ln.strip():
            return ln
    return None


def latest_event_hash(path: Path) -> Optional[str]:
    ln = _read_last_nonempty_line(path)
    if not ln:
        return None
    obj = json.loads(ln)
    h = obj.get("event_hash")
    return str(h) if h else None


def _hash_event(prev_hash: Optional[str], event_body: Dict[str, Any]) -> str:
    # Hash is over prev_hash + canonical_json(event_body) to keep it deterministic.
    return sha256_str((prev_hash or "") + "|" + canonical_json(event_body))


@dataclass(frozen=True)
class AppendResult:
    prev_hash: Optional[str]
    event_hash: str


def append_graph_delta_event(
    ledger_path: Path,
    *,
    source: str,
    ops_lines: Iterable[str],
    context_node_id: Optional[str] = None,
    run_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> AppendResult:
    """Append one GraphDelta ledger event.

    This is intended to be called exactly once per *applied* KG mutation batch.
    """
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    ops_payload = _canonical_jsonl(ops_lines)
    ops_hash = sha256_str(ops_payload)

    # Always attach run context (may come from env vars or contextvars).
    from .run_context import current

    ctx = current(create=True)
    rid = str(run_id) if run_id is not None else ctx.run_id
    tid = str(trace_id) if trace_id is not None else ctx.trace_id

    prev = latest_event_hash(ledger_path)
    body = {
        "v": 1,
        "kind": "graph_delta",
        "prev_hash": prev,
        "payload": {
            "source": str(source),
            "context_node_id": (str(context_node_id) if context_node_id is not None else None),
            "run_id": rid,
            "trace_id": tid,
            "ops_kind": "kg_delta.jsonl",
            "ops_payload": ops_payload,
            "ops_hash": ops_hash,
            "meta": meta or None,
        },
    }

    ev_hash = _hash_event(prev, body)
    record = dict(body)
    record["event_hash"] = ev_hash

    with ledger_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(canonical_json(record) + "\n")

    return AppendResult(prev_hash=prev, event_hash=ev_hash)


def iter_ledger(ledger_path: Path) -> Iterator[Dict[str, Any]]:
    p = Path(ledger_path)
    if not p.exists():
        return
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        yield json.loads(ln)


def verify_ledger_chain(ledger_path: Path) -> Tuple[bool, int]:
    """Verify hash-chain integrity. Returns (ok, events_count)."""
    prev: Optional[str] = None
    n = 0
    for rec in iter_ledger(ledger_path):
        n += 1
        if rec.get("v") != 1 or rec.get("kind") != "graph_delta":
            return False, n
        if (rec.get("prev_hash") or None) != prev:
            return False, n

        ev_hash = rec.get("event_hash")
        body = dict(rec)
        body.pop("event_hash", None)

        expect = _hash_event(prev, body)
        if str(ev_hash) != expect:
            return False, n
        prev = str(ev_hash)

    return True, n


def ops_from_event(rec: Dict[str, Any]) -> str:
    payload = rec.get("payload") or {}
    return str(payload.get("ops_payload") or "")
