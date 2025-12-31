from __future__ import annotations
import math
from typing import Dict, List, Tuple
import numpy as np

from .kg import Node, Edge

def _leaky_relu(x: float, alpha: float) -> float:
    return x if x >= 0 else alpha * x

def _softmax(scores: List[float]) -> List[float]:
    if not scores:
        return []
    m = max(scores)
    ex = [math.exp(s - m) for s in scores]
    s = sum(ex) or 1.0
    return [e / s for e in ex]

def compute_edge_attention(
    nodes: List[Node],
    edges: List[Edge],
    embeddings: Dict[str, List[float]],
    context_node_id: str,
    alpha: float = 0.2,
) -> Dict[int, float]:
    # Deterministic single-head attention:
    # score(e: u->v) = softmax_u( leaky( dot(h_u, h_v) + dot(h_ctx, h_v) ) )
    idx = {n.id:i for i,n in enumerate(nodes)}
    hctx = np.array(embeddings.get(context_node_id) or [0.0]*len(next(iter(embeddings.values()))) , dtype=np.float64) if embeddings else np.zeros((1,),dtype=np.float64)

    # group outgoing edges by src
    out_by_src: Dict[str, List[Edge]] = {}
    for e in edges:
        out_by_src.setdefault(e.src, []).append(e)

    edge_scores: Dict[int, float] = {}
    for src, elist in out_by_src.items():
        hs = embeddings.get(src)
        if hs is None:
            continue
        hsrc = np.array(hs, dtype=np.float64)
        raw_scores=[]
        valid_edges=[]
        for e in elist:
            hv = embeddings.get(e.dst)
            if hv is None:
                continue
            hv = np.array(hv, dtype=np.float64)
            s = float(np.dot(hsrc, hv) + np.dot(hctx, hv))
            raw_scores.append(_leaky_relu(s, alpha))
            valid_edges.append(e)
        probs = _softmax(raw_scores)
        for e,p in zip(valid_edges, probs):
            edge_scores[e.id] = float(p)
    return edge_scores
