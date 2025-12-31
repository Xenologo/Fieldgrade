from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from .kg import KnowledgeGraph


@dataclass(frozen=True)
class KGIssue:
    code: str
    message: str
    severity: str = "error"  # error|warn|info
    subject: Optional[str] = None  # node_id or edge_key
    path: Optional[str] = None     # json-path-ish


@dataclass(frozen=True)
class KGReport:
    ok: bool
    issues: List[KGIssue]
    nodes_seen: int
    edges_seen: int


def load_shapes(path: str | Path) -> Dict[str, Any]:
    p = Path(path).resolve()
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _get_path(obj: Dict[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _type_ok(v: Any, typ: str) -> bool:
    if typ == "string":
        return isinstance(v, str)
    if typ == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if typ == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if typ == "boolean":
        return isinstance(v, bool)
    if typ == "object":
        return isinstance(v, dict)
    if typ == "array":
        return isinstance(v, list)
    return True  # unknown types are treated as "pass" in shacl-lite


def _shape_applies_node(shape: Dict[str, Any], node_type: str, attrs: Dict[str, Any]) -> bool:
    tgt = str(shape.get("target") or "ALL_NODES").upper()
    if tgt == "ALL_NODES":
        return True
    if tgt == "NODE_TYPE":
        want = str(shape.get("type") or "")
        return want.lower() == (node_type or "").lower()
    if tgt == "NODE_ATTR_PRESENT":
        want = str(shape.get("attr") or "")
        return want in (attrs or {})
    return False


def _shape_applies_edge(shape: Dict[str, Any], edge_type: str, attrs: Dict[str, Any]) -> bool:
    tgt = str(shape.get("target") or "ALL_EDGES").upper()
    if tgt == "ALL_EDGES":
        return True
    if tgt == "EDGE_TYPE":
        want = str(shape.get("type") or "")
        return want.lower() == (edge_type or "").lower()
    if tgt == "EDGE_ATTR_PRESENT":
        want = str(shape.get("attr") or "")
        return want in (attrs or {})
    return False


def validate_kg(kg: KnowledgeGraph, shapes: Dict[str, Any]) -> KGReport:
    issues: List[KGIssue] = []

    node_shapes = list(shapes.get("node_shapes") or [])
    edge_shapes = list(shapes.get("edge_shapes") or [])
    rules = dict(shapes.get("rules") or {})

    nodes = kg.nodes()
    edges = kg.edges()
    node_ids: Set[str] = set(n.id for n in nodes)

    def apply_required(subject_id: str, obj: Dict[str, Any], reqs: List[Dict[str, Any]], kind: str, default_sev: str) -> None:
        for r in reqs:
            path = str(r.get("path") or "")
            want_type = str(r.get("type") or "")
            min_len = r.get("min_len")
            const = r.get("const")
            sev = str(r.get("severity") or default_sev or "error")
            v = _get_path(obj, path) if path else None
            if v is None:
                issues.append(KGIssue(
                    code=f"{kind}_missing",
                    message=f"missing required field: {path}",
                    subject=subject_id,
                    path=path,
                    severity=sev,
                ))
                continue
            if want_type and not _type_ok(v, want_type):
                issues.append(KGIssue(
                    code=f"{kind}_bad_type",
                    message=f"field {path} expected {want_type}, got {type(v).__name__}",
                    subject=subject_id,
                    path=path,
                    severity=sev,
                ))
                continue
            if const is not None and v != const:
                issues.append(KGIssue(
                    code=f"{kind}_const",
                    message=f"field {path} expected const {const!r}, got {v!r}",
                    subject=subject_id,
                    path=path,
                    severity=sev,
                ))
            if isinstance(min_len, int) and isinstance(v, str) and len(v) < min_len:
                issues.append(KGIssue(
                    code=f"{kind}_min_len",
                    message=f"field {path} shorter than {min_len}",
                    subject=subject_id,
                    path=path,
                    severity=sev,
                ))

    # Nodes
    for n in nodes:
        obj = {"id": n.id, "type": n.type, "attrs": n.attrs}
        for sh in node_shapes:
            if not _shape_applies_node(sh, n.type, n.attrs or {}):
                continue
            reqs = list(sh.get("required") or [])
            default_sev = str(sh.get("severity") or "error")
            apply_required(n.id, obj, reqs, kind="node", default_sev=default_sev)

    # Edges
    for e in edges:
        obj = {"src": e.src, "dst": e.dst, "type": e.type, "attrs": e.attrs}
        for sh in edge_shapes:
            if not _shape_applies_edge(sh, e.type, e.attrs or {}):
                continue
            reqs = list(sh.get("required") or [])
            default_sev = str(sh.get("severity") or "error")
            apply_required(e.edge_key, obj, reqs, kind="edge", default_sev=default_sev)

        if rules.get("referential_integrity", {}).get("edges_must_reference_existing_nodes", False):
            if e.src not in node_ids:
                issues.append(KGIssue(
                    code="edge_dangling_src",
                    message=f"edge src does not exist as node: {e.src}",
                    subject=e.edge_key,
                    path="src",
                    severity="error",
                ))
            if e.dst not in node_ids:
                issues.append(KGIssue(
                    code="edge_dangling_dst",
                    message=f"edge dst does not exist as node: {e.dst}",
                    subject=e.edge_key,
                    path="dst",
                    severity="error",
                ))

        if rules.get("sanity", {}).get("no_self_edges", False) and e.src == e.dst:
            issues.append(KGIssue(
                code="edge_self_loop",
                message="self-loop edge (src == dst) is disallowed by policy",
                subject=e.edge_key,
                severity="warn",
            ))

    ok = not any(i.severity == "error" for i in issues)
    return KGReport(ok=ok, issues=issues, nodes_seen=len(nodes), edges_seen=len(edges))
