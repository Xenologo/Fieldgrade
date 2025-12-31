from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json

import jsonschema

import re
# Additional lint (beyond JSON Schema)
_LDNA_RE = re.compile(r"^ldna://([a-z0-9+._-]+)/([a-zA-Z0-9._-]+)@([0-9]+\.[0-9]+\.[0-9]+)$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/\-]{3,256}$")

def _lint_ldna(schema_str: str) -> str | None:
    if not schema_str:
        return "schema must be non-empty"
    if schema_str.startswith("ldna://"):
        if not _LDNA_RE.match(schema_str):
            return "invalid LDNA URI; expected ldna://<media>/<name>@<X.Y.Z>"
        return None
    return "non-LDNA schema id; prefer ldna:// URIs"



# ---------------------------------------------------------------------------
# StudSpec / TubeSpec
# ---------------------------------------------------------------------------
# These are the "stud-and-tube" compatibility contracts for Memites.
# They are intentionally small, versioned, and validator-friendly.
#
# NOTE: We embed the JSON Schemas here to keep the validators self-contained,
# while also shipping copies under repo-root /schemas/ for tooling/editor use.
# ---------------------------------------------------------------------------

STUDSPEC_V1_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mite-ecology.local/schemas/studspec_v1.json",
    "title": "StudSpec v1",
    "type": "object",
    "required": ["studspec", "memite_id", "kind", "io", "constraints"],
    "properties": {
        "studspec": {"type": "string", "const": "1.0"},
        "memite_id": {"type": "string", "minLength": 3},
        "kind": {
            "type": "string",
            "enum": ["frontend", "backend", "db", "filler", "evaluator", "tool", "pipeline"],
        },
        "io": {
            "type": "object",
            "required": ["inputs", "outputs"],
            "properties": {
                "inputs": {"type": "array", "items": {"$ref": "#/$defs/ioPort"}},
                "outputs": {"type": "array", "items": {"$ref": "#/$defs/ioPort"}},
            },
            "additionalProperties": True,
        },
        "constraints": {
            "type": "object",
            "required": ["determinism"],
            "properties": {
                "determinism": {"type": "string", "enum": ["strict", "bounded", "best_effort"]},
                "max_ram_mb": {"type": "integer", "minimum": 0},
                "max_latency_ms": {"type": "integer", "minimum": 0},
                "side_effects": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": True,
        },
        "deps": {"type": "array", "items": {"type": "string"}},
        "provenance": {"type": "object"},
        "attestation": {"type": "object"},
    },
    "$defs": {
        "ioPort": {
            "type": "object",
            "required": ["name", "schema"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "schema": {"type": "string", "minLength": 1},
                "optional": {"type": "boolean"},
            },
            "additionalProperties": True,
        }
    },
    "additionalProperties": True,
}

TUBESPEC_V1_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://mite-ecology.local/schemas/tubespec_v1.json",
    "title": "TubeSpec v1",
    "type": "object",
    "required": ["tubespec", "runtime", "deps"],
    "properties": {
        "tubespec": {"type": "string", "const": "1.0"},
        "runtime": {
            "type": "object",
            "required": ["python"],
            "properties": {
                "python": {"type": "string"},
                "os": {"type": "string"},
                "arch": {"type": "string"},
                "device": {"type": "string"},
                "accelerators": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": True,
        },
        "deps": {"type": "array", "items": {"type": "string"}},
        "assets": {"type": "array", "items": {"type": "string"}},
        "limits": {"type": "object"},
        "compat": {"type": "object"},
        "notes": {"type": "string"},
    },
    "additionalProperties": True,
}


@dataclass(frozen=True)
class SpecIssue:
    path: str
    message: str
    validator: str = "jsonschema"
    severity: str = "error"


def _collect_issues(schema: Dict[str, Any], instance: Dict[str, Any]) -> List[SpecIssue]:
    v = jsonschema.Draft202012Validator(schema)
    issues: List[SpecIssue] = []
    for e in sorted(v.iter_errors(instance), key=lambda x: x.path):
        p = "/" + "/".join(map(str, e.absolute_path)) if e.absolute_path else "/"
        issues.append(SpecIssue(path=p, message=e.message))
    return issues


def validate_studspec(obj: Dict[str, Any]) -> List[SpecIssue]:
    return _collect_issues(STUDSPEC_V1_SCHEMA, obj)


def validate_tubespec(obj: Dict[str, Any]) -> List[SpecIssue]:
    return _collect_issues(TUBESPEC_V1_SCHEMA, obj)


def load_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path).resolve()
    return json.loads(p.read_text(encoding="utf-8"))


def validate_spec_file(kind: str, path: str | Path) -> Tuple[bool, List[SpecIssue]]:
    obj = load_json(path)
    kind = kind.lower().strip()
    if kind in ("stud", "studspec"):
        issues = validate_studspec(obj)
    elif kind in ("tube", "tubespec"):
        issues = validate_tubespec(obj)
    else:
        raise ValueError(f"unknown_spec_kind:{kind}")
    return (len(issues) == 0), issues
