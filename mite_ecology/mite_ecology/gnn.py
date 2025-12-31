from __future__ import annotations
import math
from typing import Dict, List, Tuple
import numpy as np

from .kg import Node, Edge

def _node_type_vocab(nodes: List[Node]) -> Dict[str, int]:
    types = sorted({n.type for n in nodes})
    return {t:i for i,t in enumerate(types)}

def _hash_feat(s: str, dim: int) -> np.ndarray:
    # simple deterministic hashed bag of chars -> dim
    v = np.zeros((dim,), dtype=np.float64)
    if not s:
        return v
    for ch in s:
        idx = (ord(ch) * 1315423911) % dim
        v[idx] += 1.0
    # L2 normalize
    norm = np.linalg.norm(v)
    if norm > 0:
        v /= norm
    return v

def build_initial_features(nodes: List[Node], feature_dim: int) -> np.ndarray:
    # features = [onehot(type_vocab) || hash(text)] but keep within feature_dim
    vocab = _node_type_vocab(nodes)
    tdim = min(len(vocab), max(4, feature_dim // 2))
    hdim = feature_dim - tdim
    X = np.zeros((len(nodes), feature_dim), dtype=np.float64)
    for i,n in enumerate(nodes):
        ti = vocab.get(n.type, 0) % tdim
        X[i, ti] = 1.0
        text = (n.attrs.get("path") or n.attrs.get("mime") or n.attrs.get("name") or n.id)
        X[i, tdim:] = _hash_feat(str(text), hdim)
    return X

def message_passing_embeddings(nodes: List[Node], edges: List[Edge], feature_dim: int, hops: int = 2) -> Dict[str, List[float]]:
    # Simple deterministic GCN-like: H_{k+1} = D^-1 (A+I) H_k
    if not nodes:
        return {}
    idx = {n.id:i for i,n in enumerate(nodes)}
    n = len(nodes)
    A = np.zeros((n,n), dtype=np.float64)
    for e in edges:
        if e.src in idx and e.dst in idx:
            i,j = idx[e.src], idx[e.dst]
            A[i,j] = 1.0
            A[j,i] = 1.0
    A = A + np.eye(n, dtype=np.float64)
    deg = A.sum(axis=1)
    Dinv = np.diag(1.0 / np.maximum(deg, 1.0))
    M = Dinv @ A
    H = build_initial_features(nodes, feature_dim)
    for _ in range(max(1, hops)):
        H = M @ H
        # row normalize for stability
        norms = np.linalg.norm(H, axis=1)
        norms[norms == 0] = 1.0
        H = H / norms[:,None]
    return {nodes[i].id: H[i].astype(float).tolist() for i in range(n)}
