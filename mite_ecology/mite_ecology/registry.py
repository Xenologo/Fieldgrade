from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml
from jsonschema import Draft202012Validator

from .hashutil import canonical_json, sha256_str


@dataclass(frozen=True)
class RegistryLoadResult:
    path: str
    data: Dict[str, Any]
    canonical_json: str
    canonical_sha256: str


def _repo_root() -> Path:
    # .../fg_next/mite_ecology/mite_ecology/registry.py -> parents[2] == .../fg_next
    return Path(__file__).resolve().parents[2]


def _schemas_dir() -> Path:
    return _repo_root() / "schemas"


def _registry_dir() -> Path:
    return _repo_root() / "mite_ecology" / "registry"


def _load_yaml(path: Path) -> Dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    if obj is None:
        return {}
    if not isinstance(obj, dict):
        raise ValueError(f"registry YAML must be a mapping: {path}")
    return obj


def _load_schema_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _err_path_str(err_path: Iterable[Any]) -> str:
    # jsonschema gives a deque/list of path components
    parts: List[str] = []
    for p in err_path:
        if isinstance(p, int):
            parts.append(f"[{p}]")
        else:
            parts.append("/" + str(p))
    return "".join(parts) or "/"


def _validate_or_raise(data: Dict[str, Any], *, schema_path: Path, what: str) -> None:
    v = _load_schema_validator(schema_path)
    errors = sorted(v.iter_errors(data), key=lambda e: (list(e.path), e.message))
    if not errors:
        return
    e0 = errors[0]
    raise ValueError(
        f"{what} failed schema validation at {_err_path_str(e0.path)}: {e0.message} (schema={schema_path.name})"
    )


def _sorted_by_id(items: List[Any], *, id_key: str) -> List[Any]:
    def key_fn(item: Any) -> Tuple[str, str]:
        if isinstance(item, dict):
            raw = item.get(id_key)
            k = str(raw) if raw is not None else ""
        else:
            k = ""
        # tie-breaker prevents nondeterminism when ids are missing/duplicated
        return (k, canonical_json(item))

    return sorted(items, key=key_fn)


def _canonicalize_registry(data: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(data)

    if isinstance(out.get("components"), list):
        out["components"] = _sorted_by_id(list(out["components"]), id_key="component_id")
    if isinstance(out.get("variants"), list):
        out["variants"] = _sorted_by_id(list(out["variants"]), id_key="variant_id")
    if isinstance(out.get("remotes"), list):
        out["remotes"] = _sorted_by_id(list(out["remotes"]), id_key="remote_id")

    return out


def _load_registry(*, yaml_path: Path, schema_path: Path, what: str) -> RegistryLoadResult:
    data = _load_yaml(yaml_path)
    _validate_or_raise(data, schema_path=schema_path, what=what)
    canon_obj = _canonicalize_registry(data)
    canon = canonical_json(canon_obj)
    return RegistryLoadResult(
        path=str(yaml_path),
        data=canon_obj,
        canonical_json=canon,
        canonical_sha256=sha256_str(canon),
    )


def load_components_registry(path: str | Path | None = None) -> RegistryLoadResult:
    if path is not None:
        p = Path(path)
    else:
        p_new = _registry_dir() / "components.yaml"
        p = p_new if p_new.exists() else (_registry_dir() / "components_v1.yaml")
    s = _schemas_dir() / "registry_components_v1.json"
    return _load_registry(yaml_path=p, schema_path=s, what="components_registry")


def load_variants_registry(path: str | Path | None = None) -> RegistryLoadResult:
    if path is not None:
        p = Path(path)
    else:
        p_new = _registry_dir() / "variants.yaml"
        p = p_new if p_new.exists() else (_registry_dir() / "variants_v1.yaml")
    s = _schemas_dir() / "registry_variants_v1.json"
    return _load_registry(yaml_path=p, schema_path=s, what="variants_registry")


def load_remotes_registry(path: str | Path | None = None) -> RegistryLoadResult:
    p = Path(path) if path is not None else (_registry_dir() / "remotes_v1.yaml")
    s = _schemas_dir() / "registry_remotes_v1.json"
    return _load_registry(yaml_path=p, schema_path=s, what="remotes_registry")
