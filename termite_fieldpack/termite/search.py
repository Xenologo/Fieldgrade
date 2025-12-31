from __future__ import annotations
from dataclasses import dataclass
from typing import List
from .db import sqlite_has_fts5

@dataclass
class SearchHit:
    path: str
    chunk_id: int
    snippet: str

def search(con, query: str, limit: int = 20) -> List[SearchHit]:
    q = query.strip()
    if not q:
        return []
    if sqlite_has_fts5(con):
        rows = con.execute(
            """
            SELECT path, chunk_id, snippet(chunks_fts, 0, '[', ']', '…', 12) AS snip
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            LIMIT ?
            """,
            (q, limit),
        ).fetchall()
        return [SearchHit(path=r["path"], chunk_id=int(r["chunk_id"]), snippet=str(r["snip"])) for r in rows]

    rows = con.execute(
        """
        SELECT d.path AS path, c.id AS chunk_id, c.text AS text
        FROM chunks c
        JOIN docs d ON d.id = c.doc_id
        WHERE c.text LIKE ?
        LIMIT ?
        """,
        (f"%{q}%", limit),
    ).fetchall()
    hits: List[SearchHit] = []
    for r in rows:
        text = str(r["text"])
        hits.append(SearchHit(path=str(r["path"]), chunk_id=int(r["chunk_id"]), snippet=text[:240] + ("…" if len(text) > 240 else "")))
    return hits
