from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from mite_ecology.db import init_db
from mite_ecology.delta import apply_delta_lines
from mite_ecology.graph_delta import (
    append_graph_delta_event,
    iter_ledger,
    ops_from_event,
    urn_mite,
    verify_ledger_chain,
)
from mite_ecology.kg import KnowledgeGraph
from mite_ecology.replay import snapshot_hash


def _schema_path() -> Path:
    return (Path(__file__).resolve().parents[1] / "sql" / "schema.sql").resolve()


def test_urn_mite_stable() -> None:
    obj = {"a": 1, "b": [2, 3]}
    u1 = urn_mite("artifact", obj)
    u2 = urn_mite("artifact", {"b": [2, 3], "a": 1})
    assert u1 == u2
    assert u1.startswith("urn:mite:artifact:")


def test_ledger_chain_ok(tmp_path: Path) -> None:
    lp = tmp_path / "graph_delta_ledger.jsonl"

    ops1 = [json.dumps({"op": "ADD_NODE", "id": "n1", "type": "Thing", "attrs": {"x": 1}})]
    ops2 = [json.dumps({"op": "ADD_NODE", "id": "n2", "type": "Thing", "attrs": {"x": 2}})]

    r1 = append_graph_delta_event(lp, source="TEST", ops_lines=ops1)
    r2 = append_graph_delta_event(lp, source="TEST", ops_lines=ops2)

    assert r1.event_hash != r2.event_hash

    ok, n = verify_ledger_chain(lp)
    assert ok is True
    assert n == 2


def test_replay_equivalence(tmp_path: Path) -> None:
    schema = _schema_path()

    # Build a ledger for two ops
    lp = tmp_path / "graph_delta_ledger.jsonl"
    ops = [
        json.dumps({"op": "ADD_NODE", "id": "n1", "type": "Thing", "attrs": {"x": 1}}),
        json.dumps({"op": "ADD_EDGE", "src": "n1", "dst": "n1", "type": "SELF", "attrs": {}}),
    ]
    append_graph_delta_event(lp, source="TEST", ops_lines=ops)

    # Apply directly
    con1 = sqlite3.connect(":memory:")
    con1.row_factory = sqlite3.Row
    init_db(con1, schema)
    kg1 = KnowledgeGraph(con1)
    apply_delta_lines(kg1, ops)
    h1 = snapshot_hash(con1)

    # Replay from ledger
    con2 = sqlite3.connect(":memory:")
    con2.row_factory = sqlite3.Row
    init_db(con2, schema)
    kg2 = KnowledgeGraph(con2)
    for rec in iter_ledger(lp):
        op_payload = ops_from_event(rec)
        apply_delta_lines(kg2, op_payload.splitlines())
    h2 = snapshot_hash(con2)

    assert h1 == h2


def test_event_has_run_context(tmp_path: Path) -> None:
    lp = tmp_path / "graph_delta_ledger.jsonl"
    ops = [json.dumps({"op": "ADD_NODE", "id": "n1", "type": "Thing", "attrs": {"x": 1}})]
    append_graph_delta_event(lp, source="TEST", ops_lines=ops)

    recs = list(iter_ledger(lp))
    assert len(recs) == 1
    payload = recs[0].get("payload") or {}
    assert isinstance(payload.get("run_id"), str)
    assert payload.get("run_id")
    assert isinstance(payload.get("trace_id"), str)
    assert payload.get("trace_id")
