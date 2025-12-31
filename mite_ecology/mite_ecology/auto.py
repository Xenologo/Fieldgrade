from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .kg import KnowledgeGraph
from .gnn import message_passing_embeddings
from .gat import compute_edge_attention
from .motif import mine_motifs_from_attention
from .memoga import run_memoga
from .hashutil import sha256_str
from .timeutil import utc_now_iso

@dataclass(frozen=True)
class AutoRunConfig:
    cycles: int = 5
    hops: int = 2
    feature_dim: int = 32
    top_attention_edges: int = 64
    motif_limit: int = 24
    population: int = 32
    generations: int = 12
    llm_mode: str = "off"  # off | cache_only | live (live is discouraged in strict mode)
    notes: str = ""

def autorun(
    kg: KnowledgeGraph,
    *,
    context_node_id: str,
    cfg: AutoRunConfig,
) -> Dict[str, Any]:
    # Strict determinism: no global randomness; all RNG derived from stable hashes inside memoga.
    report: Dict[str, Any] = {
        # Deterministic run identifier (stable across independent runs)
        "run_id": sha256_str(f"{context_node_id}|{cfg}")[:16],
        # Do not inject wall-clock time into determinism-critical reports
        "ts_utc": "1970-01-01T00:00:00+00:00",
        "context": context_node_id,
        "cycles": cfg.cycles,
        "cycles_report": [],
        "notes": cfg.notes,
    }

    for c in range(cfg.cycles):
        # Neighborhood is deterministic by node id ordering in SQL + fixed hops/max
        nodes, edges = kg.neighborhood(context_node_id, hops=cfg.hops, max_nodes=1200)

        # GNN embeddings (deterministic)
        emb = message_passing_embeddings(nodes, edges, feature_dim=cfg.feature_dim, hops=cfg.hops)
        for nid, vec in emb.items():
            kg.upsert_node_embedding(nid, vec)

        # GAT-style attention (deterministic; store per edge)
        scores = compute_edge_attention(nodes, edges, emb, context_node_id, alpha=0.2)
        for e in edges:
            kg.set_edge_attention(e.id, float(scores.get(e.id, 0.0)), context_node_id)

        # Mine motifs from attention
        motifs = mine_motifs_from_attention(kg, context_node_id, limit=cfg.motif_limit, top_edges=cfg.top_attention_edges)

        # Memo-GA: evolve genomes from motifs (deterministic seed per cycle)
        cycle_seed = sha256_str(f"{context_node_id}|cycle={c}")
        ga_res = run_memoga(
            kg,
            context_node_id=context_node_id,
            motifs=motifs,
            population=cfg.population,
            generations=cfg.generations,
            seed_hex=cycle_seed,
        )

        report["cycles_report"].append({
            "cycle": c,
            "nodes": len(nodes),
            "edges": len(edges),
            "motifs": len(motifs),
            "best_genome_id": ga_res.get("best_genome_id"),
            "best_fitness": ga_res.get("best_fitness"),
        })

    # pick final best genome across cycles (deterministic by fitness then genome_id)
    best = None
    for cr in report["cycles_report"]:
        if cr.get("best_genome_id") is None:
            continue
        cand = (float(cr.get("best_fitness", -1e18)), str(cr.get("best_genome_id")))
        if best is None or cand > best:
            best = cand
    report["final_best"] = {"fitness": best[0], "genome_id": best[1]} if best else None
    return report
