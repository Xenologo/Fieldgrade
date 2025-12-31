from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    """Major-version compatibility for LDNA URIs (same media+name and major)."""
    ra = parse_ldna(a)
    rb = parse_ldna(b)
    if not ra or not rb:
        # non-LDNA -> cannot determine; treat as 'maybe'
        return True
    return (ra.media, ra.name, ra.major) == (rb.media, rb.name, rb.major)


@dataclass(frozen=True)
class ContractCheck:
    ok: bool
    issues: List[str]
    warnings: List[str]


def check_studspec_against_registry(studspec: Dict[str, Any], registry: Dict[str, Any], *, allow_unknown: bool = True) -> ContractCheck:
    issues: List[str] = []
    warnings: List[str] = []
    io = studspec.get("io") if isinstance(studspec.get("io"), dict) else {}
    for which in ("inputs","outputs"):
        ports = io.get(which) if isinstance(io, dict) else None
        if not isinstance(ports, list):
            continue
        for p in ports:
            if not isinstance(p, dict):
                continue
            sch = p.get("schema")
            if isinstance(sch, str) and sch.startswith("ldna://"):
                if not registry_has(registry, sch):
                    msg = f"unknown LDNA schema: {sch}"
                    if allow_unknown:
                        warnings.append(msg)
                    else:
                        issues.append(msg)
            elif isinstance(sch, str) and sch and not sch.startswith("ldna://"):
                warnings.append(f"non-LDNA schema id: {sch}")
    return ContractCheck(ok=len(issues)==0, issues=issues, warnings=warnings)
