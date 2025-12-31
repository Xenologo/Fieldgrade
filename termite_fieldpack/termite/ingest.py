from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from .cas import CAS, sha256_bytes
from .chunking import chunk_text
from .extract import extract_text_best_effort, sniff_mime
from .provenance import Provenance, utc_now_iso, canonical_json, hash_str
from .db import insert_blob, insert_doc, insert_chunk, insert_kg_op

def sha256_text(s: str) -> str:
    h = hashlib.sha256()
    h.update(s.encode("utf-8"))
    return h.hexdigest()

@dataclass
class IngestResult:
    doc_id: int
    raw_sha256: str
    extract_sha256: Optional[str]
    mime: str
    chunks: int

def ingest_path(
    con,
    cas: CAS,
    prov: Provenance,
    path: Path,
    *,
    max_bytes: int,
    extract_text: bool,
    chunk_chars: int,
    overlap_chars: int,
    min_chunk_chars: int,
) -> IngestResult:
    path = path.resolve()
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError(f"File exceeds max_bytes: {len(raw)} > {max_bytes}")

    mime = sniff_mime(path)
    created = utc_now_iso()

    raw_sha = sha256_bytes(raw)
    cas.put(raw, kind="raw", sha256=raw_sha)
    insert_blob(con, raw_sha, "raw", len(raw), created, str(path))

    extract_sha = None
    extracted_text = None
    strategy = "none"
    if extract_text:
        extracted_text, strategy = extract_text_best_effort(path, raw)
        if extracted_text:
            ext_bytes = extracted_text.encode("utf-8")
            extract_sha = sha256_bytes(ext_bytes)
            cas.put(ext_bytes, kind="extract", sha256=extract_sha)
            insert_blob(con, extract_sha, "extract", len(ext_bytes), created, str(path))

    doc_id = insert_doc(con, str(path), mime, raw_sha, extract_sha, created)

    text_for_chunking = extracted_text if (extracted_text and extract_text) else None
    if text_for_chunking is None:
        try:
            text_for_chunking = raw.decode("utf-8")
        except Exception:
            text_for_chunking = ""

    chunks = chunk_text(text_for_chunking, chunk_chars, overlap_chars, min_chunk_chars)
    for c in chunks:
        insert_chunk(con, doc_id, c.index, c.start, c.end, c.text, sha256_text(c.text), created)
    con.commit()

    prov.append_event(
        con,
        "INGEST",
        {
            "path": str(path),
            "mime": mime,
            "raw_blob_sha256": raw_sha,
            "extract_blob_sha256": extract_sha,
            "extract_strategy": strategy,
            "chunks": len(chunks),
            "doc_id": doc_id,
        },
    )

    # Emit KG ops (delta-friendly JSON lines)
    doc_node = f"doc:{raw_sha}"
    raw_node = f"blob:raw:{raw_sha}"
    ops = []
    ops.append({"op":"ADD_NODE","id":doc_node,"type":"Document","attrs":{"path":str(path),"mime":mime,"doc_id":doc_id,"created_utc":created}})
    ops.append({"op":"ADD_NODE","id":raw_node,"type":"Blob","attrs":{"kind":"raw","sha256":raw_sha,"size_bytes":len(raw)}})
    ops.append({"op":"ADD_EDGE","src":doc_node,"dst":raw_node,"type":"HAS_BLOB","attrs":{"kind":"raw"}})

    if extract_sha:
        ext_node = f"blob:extract:{extract_sha}"
        ops.append({"op":"ADD_NODE","id":ext_node,"type":"Blob","attrs":{"kind":"extract","sha256":extract_sha,"size_bytes":len(ext_bytes)}})
        ops.append({"op":"ADD_EDGE","src":doc_node,"dst":ext_node,"type":"HAS_BLOB","attrs":{"kind":"extract"}})

    for c in chunks[: min(200, len(chunks))]:
        ch_id = f"chunk:{raw_sha}:{c.index}"
        ops.append({"op":"ADD_NODE","id":ch_id,"type":"Chunk","attrs":{"doc":doc_node,"index":c.index,"start":c.start,"end":c.end,"text_sha256":sha256_text(c.text)}})
        ops.append({"op":"ADD_EDGE","src":doc_node,"dst":ch_id,"type":"HAS_CHUNK","attrs":{}})

    for op in ops:
        j = canonical_json(op)
        insert_kg_op(con, created, j, hash_str(j))

    con.commit()

    return IngestResult(doc_id=doc_id, raw_sha256=raw_sha, extract_sha256=extract_sha, mime=mime, chunks=len(chunks))
