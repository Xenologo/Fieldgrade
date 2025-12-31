from __future__ import annotations

from pathlib import Path

from mite_ecology.db import connect, init_db
from mite_ecology.kg import KnowledgeGraph
from mite_ecology.auto import autorun, AutoRunConfig
from mite_ecology.hashutil import canonical_json, sha256_str


def _init_kg(tmp_path: Path) -> KnowledgeGraph:
    dbp = tmp_path / "kg.sqlite"
    con = connect(dbp)
    schema = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
    init_db(con, schema)
    kg = KnowledgeGraph(con)

    # Deterministic toy graph
    kg.upsert_node("task:1", "Task", {"title": "demo"})
    kg.upsert_node("doc:1", "Document", {"name": "field_ops.md"})
    kg.upsert_node("blob:1", "Blob", {"sha256": "00"*32})
    kg.upsert_edge("task:1", "doc:1", "REFERENCES", {})
    kg.upsert_edge("doc:1", "blob:1", "HAS_BLOB", {})
    return kg


def test_autorun_is_deterministic(tmp_path: Path):
    kg1 = _init_kg(tmp_path / "run1")
    kg2 = _init_kg(tmp_path / "run2")

    cfg = AutoRunConfig(cycles=3, hops=2, feature_dim=16, top_attention_edges=16, motif_limit=10, population=12, generations=6)

    r1 = autorun(kg1, context_node_id="task:1", cfg=cfg)
    r2 = autorun(kg2, context_node_id="task:1", cfg=cfg)

    h1 = sha256_str(canonical_json(r1))
    h2 = sha256_str(canonical_json(r2))

    assert h1 == h2
    assert r1["final_best"] == r2["final_best"]
