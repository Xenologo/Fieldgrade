from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


@dataclass
class CAS:
    """Content-addressable store (CAS) for field-grade deterministic bundles.

    Layout:
      root/
        blobs/sha256/<hash>      ... raw uploaded bytes
        extracts/sha256/<hash>   ... derived/extracted artifacts
        aux/sha256/<hash>        ... auxiliary I/O (LLM transcripts, reports, stdout/stderr)
    """

    root: Path

    @property
    def blobs_dir(self) -> Path:
        return self.root / "blobs" / "sha256"

    @property
    def extracts_dir(self) -> Path:
        return self.root / "extracts" / "sha256"

    @property
    def aux_dir(self) -> Path:
        return self.root / "aux" / "sha256"

    def init(self) -> None:
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.extracts_dir.mkdir(parents=True, exist_ok=True)
        self.aux_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, sha256: str, kind: str) -> Path:
        if kind in ("raw", "blob", "blobs"):
            base = self.blobs_dir
        elif kind in ("extract", "extracts"):
            base = self.extracts_dir
        elif kind in ("aux", "auxiliary"):
            base = self.aux_dir
        else:
            raise ValueError(f"unknown CAS kind: {kind}")
        return base / sha256

    def put(self, data: bytes, kind: str, sha256: Optional[str] = None) -> str:
        if sha256 is None:
            sha256 = sha256_bytes(data)
        p = self._path_for(sha256, kind)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return sha256

    def get(self, sha256: str, kind: str) -> bytes:
        return self._path_for(sha256, kind).read_bytes()

    # Convenience helpers
    def put_aux(self, data: bytes) -> str:
        return self.put(data, kind="aux")

    def get_aux_path(self, sha256: str) -> Path:
        return self._path_for(sha256, kind="aux")
