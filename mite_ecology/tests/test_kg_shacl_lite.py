from __future__ import annotations

from pathlib import Path

from mite_ecology.db import connect, init_db
from mite_ecology.kg import KnowledgeGraph
from mite_ecology.kg_shacl_lite import load_shapes, validate_kg


def test_kg_validator_detects_dangling_edge(tmp_path: Path):
    dbp = tmp_path / "kg.sqlite"
    con = connect(dbp)

    # schema lives at <repo>/mite_ecology/mite_ecology/sql/schema.sql
    schema_sql = Path(__file__).resolve().parents[2] / "mite_ecology" / "sql" / "schema.sql"
    init_db(con, schema_sql)

    kg = KnowledgeGraph(con)
    kg.upsert_node("n1", "Memite", {"a": 1})
    # dangling dst n2
    kg.upsert_edge("n1", "n2", "calls", {})

    # shapes live at <repo>/schemas/kg_shapes_lite.yaml
    shapes_path = Path(__file__).resolve().parents[2] / "schemas" / "kg_shapes_lite.yaml"
    shapes = load_shapes(shapes_path)

    rep = validate_kg(kg, shapes)
    assert rep.ok is False
    assert any(i.code in ("edge_dangling_dst", "edge_dangling_src") for i in rep.issues)
