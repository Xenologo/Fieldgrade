from __future__ import annotations
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class Chunk:
    index: int
    start: int
    end: int
    text: str

def chunk_text(text: str, chunk_chars: int, overlap_chars: int, min_chunk_chars: int) -> List[Chunk]:
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be > 0")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be >= 0")
    if min_chunk_chars <= 0:
        min_chunk_chars = 1

    n = len(text)
    chunks: List[Chunk] = []
    i = 0
    idx = 0
    while i < n:
        end = min(n, i + chunk_chars)
        piece = text[i:end].strip()
        if len(piece) >= min_chunk_chars:
            chunks.append(Chunk(index=idx, start=i, end=end, text=piece))
            idx += 1
        if end == n:
            break
        i = max(0, end - overlap_chars)
    return chunks
