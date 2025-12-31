from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple, Optional
from .hashutil import canonical_json, stable_edge_key
from .timeutil import utc_now_iso

@dataclass
class Node:
    id: str
    type: str
    attrs: Dict[str, Any]

@dataclass
class Edge:
    id: int
    edge_key: str
    src: str
    dst: str
    type: str
    attrs: Dict[str, Any]

class KnowledgeGraph:
    def __init__(self, con):
        self.con = con

    def upsert_node(self, node_id: str, node_type: str, attrs: Dict[str, Any]) -> None:
        self.con.execute(
            "INSERT INTO nodes(id,type,attrs_json) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET type=excluded.type, attrs_json=excluded.attrs_json",
            (node_id, node_type, canonical_json(attrs)),
        )
        self.con.commit()

    def upsert_edge(self, src: str, dst: str, etype: str, attrs: Dict[str, Any]) -> int:
        ek = stable_edge_key(src, dst, etype, attrs)
        self.con.execute(
            "INSERT OR IGNORE INTO edges(edge_key,src,dst,type,attrs_json) VALUES(?,?,?,?,?)",
            (ek, src, dst, etype, canonical_json(attrs)),
        )
        row = self.con.execute("SELECT id FROM edges WHERE edge_key=?", (ek,)).fetchone()
        self.con.commit()
        return int(row["id"])

    def remove_node(self, node_id: str) -> None:
        self.con.execute("DELETE FROM edges WHERE src=? OR dst=?", (node_id, node_id))
        self.con.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        self.con.commit()

    def remove_edge_by_key(self, edge_key: str) -> None:
        self.con.execute("DELETE FROM edges WHERE edge_key=?", (edge_key,))
        self.con.commit()

    def nodes(self) -> List[Node]:
        rows = self.con.execute("SELECT id,type,attrs_json FROM nodes").fetchall()
        out=[]
        for r in rows:
            out.append(Node(id=str(r["id"]), type=str(r["type"]), attrs=json.loads(r["attrs_json"])))
        return out

    def edges(self) -> List[Edge]:
        rows = self.con.execute("SELECT id,edge_key,src,dst,type,attrs_json FROM edges").fetchall()
        out=[]
        for r in rows:
            out.append(Edge(
                id=int(r["id"]),
                edge_key=str(r["edge_key"]),
                src=str(r["src"]),
                dst=str(r["dst"]),
                type=str(r["type"]),
                attrs=json.loads(r["attrs_json"]),
            ))
        return out

    def neighborhood(self, center_id: str, hops: int = 2, max_nodes: int = 500) -> Tuple[List[Node], List[Edge]]:
        # BFS across undirected view for sampling
        seen = {center_id}
        frontier = {center_id}
        for _ in range(hops):
            nxt=set()
            for nid in list(frontier):
                rows = self.con.execute(
                    "SELECT src,dst FROM edges WHERE src=? OR dst=? LIMIT 1000",
                    (nid, nid),
                ).fetchall()
                for r in rows:
                    for x in (str(r["src"]), str(r["dst"])):
                        if x not in seen and len(seen) < max_nodes:
                            seen.add(x); nxt.add(x)
            frontier = nxt
            if not frontier:
                break
        # fetch nodes/edges induced
        qmarks = ",".join(["?"]*len(seen))
        nrows = self.con.execute(f"SELECT id,type,attrs_json FROM nodes WHERE id IN ({qmarks})", tuple(seen)).fetchall()
        nodes=[Node(id=str(r["id"]), type=str(r["type"]), attrs=json.loads(r["attrs_json"])) for r in nrows]
        erows = self.con.execute(
            f"SELECT id,edge_key,src,dst,type,attrs_json FROM edges WHERE src IN ({qmarks}) AND dst IN ({qmarks})",
            tuple(seen)+tuple(seen),
        ).fetchall()
        edges=[Edge(id=int(r["id"]), edge_key=str(r["edge_key"]), src=str(r["src"]), dst=str(r["dst"]),
                    type=str(r["type"]), attrs=json.loads(r["attrs_json"])) for r in erows]
        return nodes, edges

    def upsert_node_embedding(self, node_id: str, vec: List[float]) -> None:
        self.con.execute(
            "INSERT INTO node_embeddings(node_id,dim,vec_json,updated_utc) VALUES(?,?,?,?) "
            "ON CONFLICT(node_id) DO UPDATE SET dim=excluded.dim, vec_json=excluded.vec_json, updated_utc=excluded.updated_utc",
            (node_id, len(vec), json.dumps(vec, separators=(",", ":"), ensure_ascii=False), utc_now_iso()),
        )
        self.con.commit()

    def get_node_embedding(self, node_id: str) -> List[float] | None:
        row = self.con.execute("SELECT vec_json FROM node_embeddings WHERE node_id=?", (node_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["vec_json"])

    def set_edge_attention(self, edge_id: int, score: float, context_node_id: str) -> None:
        self.con.execute(
            "INSERT INTO edge_attention(edge_id,score,context_node_id,updated_utc) VALUES(?,?,?,?) "
            "ON CONFLICT(edge_id) DO UPDATE SET score=excluded.score, context_node_id=excluded.context_node_id, updated_utc=excluded.updated_utc",
            (edge_id, float(score), context_node_id, utc_now_iso()),
        )
        self.con.commit()

    def list_attention(self, context_node_id: str, limit: int = 50) -> List[Tuple[int,float]]:
        rows = self.con.execute(
            "SELECT edge_id, score FROM edge_attention WHERE context_node_id=? ORDER BY score DESC, edge_id ASC LIMIT ?",
            (context_node_id, limit),
        ).fetchall()
        return [(int(r["edge_id"]), float(r["score"])) for r in rows]

    def get_edge_by_id(self, edge_id: int) -> Optional[Edge]:
        """Fetch an Edge by numeric id.

        The DB schema defines edges columns: (id, edge_key, src, dst, type, attrs_json).
        """
        r = self.con.execute(
            "SELECT id, edge_key, src, dst, type, attrs_json FROM edges WHERE id=?",
            (int(edge_id),),
        ).fetchone()
        if not r:
            return None
        return Edge(
            id=int(r["id"]),
            edge_key=str(r["edge_key"]),
            src=str(r["src"]),
            dst=str(r["dst"]),
            type=str(r["type"]),
            attrs=json.loads(r["attrs_json"]),
        )

    def upsert_motif(
        self,
        motif_id: str,
        context_node_id: str,
        motif_obj: Dict[str, Any],
        score: float,
        created_utc: Optional[str] = None,
    ) -> None:
        """Insert or update a motif record.

        This matches the schema in sql/schema.sql:
          motifs(motif_id, context_node_id, motif_json, score, created_utc)
        """
        created = created_utc or utc_now_iso()
        self.con.execute(
            "INSERT OR REPLACE INTO motifs(motif_id, context_node_id, motif_json, score, created_utc) VALUES(?,?,?,?,?)",
            (motif_id, context_node_id, canonical_json(motif_obj), float(score), created),
        )
        self.con.commit()
