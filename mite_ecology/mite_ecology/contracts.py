from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_LDNA_RE = re.compile(r"^ldna://([a-z0-9+._-]+)/([a-zA-Z0-9._-]+)@([0-9]+)\.([0-9]+)\.([0-9]+)$")


@dataclass(frozen=True)
class LDNARef:
    media: str
    name: str
    major: int
    minor: int
    patch: int
    uri: str


def parse_ldna(uri: str) -> Optional[LDNARef]:
    if not isinstance(uri, str) or not uri.startswith("ldna://"):
        return None
    m = _LDNA_RE.match(uri)
    if not m:
        return None
    return LDNARef(
        media=m.group(1),
        name=m.group(2),
        major=int(m.group(3)),
        minor=int(m.group(4)),
        patch=int(m.group(5)),
        uri=uri,
    )


def load_ldna_registry(path: str | Path) -> Dict[str, Any]:
    p = Path(path).resolve()
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def registry_has(reg: Dict[str, Any], uri: str) -> bool:
    schemas = reg.get("schemas") or []
    return any(isinstance(s, dict) and s.get("uri") == uri for s in schemas)


def compatible(a: str, b: str) -> bool:
    ra = parse_ldna(a)
    rb = parse_ldna(b)
    if not ra or not rb:
        return True
    return (ra.media, ra.name, ra.major) == (rb.media, rb.name, rb.major)
