from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict

from .db import connect, init_db
from .kg import KnowledgeGraph
from .delta import apply_delta_lines
from .hashutil import canonical_json


def sha256_str(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def snapshot_hash(con: sqlite3.Connection) -> str:
    """Stable snapshot of KG tables for deterministic replay verification."""
    nodes = [dict(r) for r in con.execute("SELECT * FROM nodes ORDER BY id").fetchall()]
    edges = [dict(r) for r in con.execute("SELECT * FROM edges ORDER BY id").fetchall()]
    payload = canonical_json({"nodes": nodes, "edges": edges})
    return sha256_str(payload)


def verify_hash_chains(con: sqlite3.Connection) -> Dict[str, object]:
    """Verify internal hash-chains for kg_deltas and ingested_bundles."""
    # kg_deltas chain
    ok_deltas = True
    prev = None
    rows = con.execute(
        "SELECT id, delta_hash, prev_hash, chain_hash FROM kg_deltas ORDER BY id"
    ).fetchall()
    for r in rows:
        if (r["prev_hash"] or None) != prev:
            ok_deltas = False
            break
        blob = (prev or "") + "|" + str(r["delta_hash"])
        expect = sha256_str(blob)
        if str(r["chain_hash"]) != expect:
            ok_deltas = False
            break
        prev = str(r["delta_hash"])

    # ingested_bundles chain
    ok_ing = True
    prev = None
    rows = con.execute(
        "SELECT id, bundle_sha256, kg_delta_hash, ingest_kind, policy_hash, allowlist_hash, prev_hash, ingest_hash "
        "FROM ingested_bundles ORDER BY id"
    ).fetchall()
    for r in rows:
        if (r["prev_hash"] or None) != prev:
            ok_ing = False
            break
        blob = (prev or "") + "|" + str(r["bundle_sha256"]) + "|" + str(r["kg_delta_hash"]) + "|" + str(r["ingest_kind"]) + "|" + str(r["policy_hash"]) + "|" + str(r["allowlist_hash"])
        expect = sha256_str(blob)
        if str(r["ingest_hash"]) != expect:
            ok_ing = False
            break
        prev = str(r["ingest_hash"])

    return {"kg_deltas_chain_ok": ok_deltas, "ingested_chain_ok": ok_ing}


def replay_verify(db_path: Path) -> Dict[str, object]:
    con = connect(db_path)
    current = snapshot_hash(con)

    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    init_db(mem, Path(__file__).resolve().parents[1] / "sql" / "schema.sql")

    kg = KnowledgeGraph(mem)
    deltas = [
        str(r["delta_payload"])
        for r in con.execute("SELECT delta_payload FROM kg_deltas ORDER BY id").fetchall()
    ]
    for payload in deltas:
        lines = [ln for ln in payload.splitlines() if ln.strip()]
        apply_delta_lines(kg, lines)

    replayed = snapshot_hash(mem)
    chains = verify_hash_chains(con)

    return {
        "current_snapshot_hash": current,
        "replayed_snapshot_hash": replayed,
        "match": current == replayed,
        **chains,
        "deltas_count": len(deltas),
    }
