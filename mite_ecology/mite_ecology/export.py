from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict
from .hashutil import canonical_json
from .kg import KnowledgeGraph
from .timeutil import utc_now_iso

def export_best_genome(kg: KnowledgeGraph, exports_root: Path) -> Path:
    exports_root.mkdir(parents=True, exist_ok=True)
    row = kg.con.execute(
        "SELECT g.genome_id, g.context_node_id, g.genome_json, e.fitness, e.eval_json "
        "FROM genomes g LEFT JOIN genome_eval e ON e.genome_id=g.genome_id "
        "ORDER BY (e.fitness) DESC NULLS LAST LIMIT 1"
    ).fetchone()
    if not row:
        raise RuntimeError("No genomes found. Run motifs + ga first.")
    genome = json.loads(row["genome_json"])
    out = {
        "neuroarch_dsl_version":"0.1",
        "exported_utc": utc_now_iso(),
        "genome_id": row["genome_id"],
        "context_node_id": row["context_node_id"],
        "fitness": float(row["fitness"]) if row["fitness"] is not None else None,
        "eval": json.loads(row["eval_json"]) if row["eval_json"] else None,
        "dsl": {
            "nodes": genome["nodes"],
            "edges": genome["edges"],
            "params": genome["params"],
            "notes": "This is a minimal DSL emitted from motif-derived genome; expand into full PyG/ONNX as needed.",
        },
    }
    out_path = exports_root / f"neuroarch_{row['genome_id']}.json"
    out_path.write_text(canonical_json(out) + "\n", encoding="utf-8")
    # also emit a tiny torch-like skeleton (no dependency)
    py_path = exports_root / f"neuroarch_{row['genome_id']}_skeleton.py"
    py_path.write_text(
        """# Auto-emitted skeleton (no runtime deps)

class NeuroArchModel:
    def __init__(self, params):
        self.params = params

    def forward(self, x):
        # TODO: map genome nodes/edges into real layers
        return x
""" ,
        encoding="utf-8",
    )
    return out_path
