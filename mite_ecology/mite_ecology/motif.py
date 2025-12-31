from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .hashutil import canonical_json, sha256_str
from .timeutil import utc_now_iso
from .kg import KnowledgeGraph, Edge


@dataclass
class Motif:
    motif_id: str
    context_node_id: str
    motif: Dict[str, Any]
    score: float
    created_utc: str


def _motif_to_dict(m: Motif) -> Dict[str, Any]:
    return {
        "motif_id": m.motif_id,
        "context_node_id": m.context_node_id,
        "motif": m.motif,
        "score": float(m.score),
        "created_utc": m.created_utc,
    }


def mine_motif_from_attention(
    kg: KnowledgeGraph,
    context_node_id: str,
    *,
    top_edges: int = 32,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Mine a single motif from stored attention scores.

    Backwards-compatible: callers may pass `limit` (treated as `top_edges`).
    """
    if limit is not None:
        top_edges = int(limit)

    att = kg.list_attention(context_node_id, limit=top_edges)
    edge_ids = [eid for eid, _ in att]
    scores = [s for _, s in att]
    score = float(sum(scores))

    if not edge_ids:
        motif_obj = {"context": context_node_id, "nodes": [context_node_id], "edges": []}
    else:
        qmarks = ",".join(["?"] * len(edge_ids))
        rows = kg.con.execute(
            f"SELECT id, src, dst, type, attrs_json FROM edges WHERE id IN ({qmarks}) ORDER BY id ASC",
            tuple(edge_ids),
        ).fetchall()
        nodes = set([context_node_id])
        edges: List[int] = []
        for r in rows:
            nodes.add(str(r["src"]))
            nodes.add(str(r["dst"]))
            edges.append(int(r["id"]))
        motif_obj = {"context": context_node_id, "nodes": sorted(nodes), "edges": sorted(edges)}

    motif_id = sha256_str(canonical_json(motif_obj))
    created = utc_now_iso()
    kg.con.execute(
        "INSERT OR REPLACE INTO motifs(motif_id, context_node_id, motif_json, score, created_utc) VALUES(?,?,?,?,?)",
        (motif_id, context_node_id, canonical_json(motif_obj), score, created),
    )
    kg.con.commit()

    return _motif_to_dict(Motif(motif_id=motif_id, context_node_id=context_node_id, motif=motif_obj, score=score, created_utc=created))


def list_motifs(kg: KnowledgeGraph, context_node_id: Optional[str] = None, *, limit: int = 20) -> List[Dict[str, Any]]:
    """List motifs (optionally filtered by context_node_id) as JSON-serializable dicts."""
    if context_node_id:
        rows = kg.con.execute(
            "SELECT motif_id, context_node_id, motif_json, score, created_utc "
            "FROM motifs WHERE context_node_id=? ORDER BY score DESC, motif_id ASC LIMIT ?",
            (str(context_node_id), int(limit)),
        ).fetchall()
    else:
        rows = kg.con.execute(
            "SELECT motif_id, context_node_id, motif_json, score, created_utc "
            "FROM motifs ORDER BY score DESC, motif_id ASC LIMIT ?",
            (int(limit),),
        ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        obj = json.loads(r["motif_json"])
        out.append(
            _motif_to_dict(
                Motif(
                    motif_id=str(r["motif_id"]),
                    context_node_id=str(r["context_node_id"]),
                    motif=obj,
                    score=float(r["score"]),
                    created_utc=str(r["created_utc"]),
                )
            )
        )
    return out


def mine_motifs_from_attention(
    kg: KnowledgeGraph,
    context_node_id: str,
    *,
    limit: int = 24,
    top_edges: int = 64,
) -> List[Dict[str, Any]]:
    """Deterministically mine multiple motifs based on stored attention scores."""
    att = kg.list_attention(context_node_id, limit=top_edges)

    edges: List[Tuple[Edge, float]] = []
    for edge_id, score in att:
        e = kg.get_edge_by_id(edge_id)
        if e is None:
            continue
        edges.append((e, float(score)))

    motifs: List[Dict[str, Any]] = []
    seen = set()
    for e, s in edges:
        key = (e.src, e.dst, e.type)
        if key in seen:
            continue
        seen.add(key)
        m = {
            "context": context_node_id,
            "nodes": sorted(list({e.src, e.dst})),
            "edges": [{"src": e.src, "dst": e.dst, "type": e.type}],
        }
        motif_id = sha256_str(canonical_json(m))
        created = utc_now_iso()
        kg.upsert_motif(motif_id, context_node_id, m, float(s), created)
        motifs.append({"motif_id": motif_id, "context_node_id": context_node_id, "motif": m, "score": float(s), "created_utc": created})
        if len(motifs) >= int(limit):
            break

    return motifs
