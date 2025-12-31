from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from .kg import KnowledgeGraph

SUPPORTED_OPS = {"ADD_NODE","ADD_EDGE","REMOVE_NODE","REMOVE_EDGE"}

def apply_delta_lines(kg: KnowledgeGraph, lines: Iterable[str]) -> int:
    n = 0
    for line in lines:
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        op = obj.get("op")
        if op not in SUPPORTED_OPS:
            continue
        if op == "ADD_NODE":
            kg.upsert_node(str(obj["id"]), str(obj.get("type","Thing")), dict(obj.get("attrs") or {}))
            n += 1
        elif op == "ADD_EDGE":
            kg.upsert_edge(str(obj["src"]), str(obj["dst"]), str(obj.get("type","RELATED")), dict(obj.get("attrs") or {}))
            n += 1
        elif op == "REMOVE_NODE":
            kg.remove_node(str(obj["id"]))
            n += 1
        elif op == "REMOVE_EDGE":
            # expect edge_key if provided else recompute from src/dst/type/attrs
            ek = obj.get("edge_key")
            if ek:
                kg.remove_edge_by_key(str(ek))
                n += 1
    return n

def apply_delta_file(kg: KnowledgeGraph, path: Path) -> int:
    return apply_delta_lines(kg, path.read_text(encoding="utf-8").splitlines())
