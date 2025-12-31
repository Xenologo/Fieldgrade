from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from .provenance import canonical_json, hash_str

# ---------------------------------------------------------------------------
# MEAP_v1 policy (machine-enforceable governance envelope)
# ---------------------------------------------------------------------------
#
# This package supports the "meap_v1" schema (preferred) and a legacy "policy"
# schema used by early fieldpacks. Both are normalized to an internal dict.
#
# NOTE: We intentionally hash the *canonicalized parsed object* rather than
# raw YAML bytes to avoid whitespace/line-ending drift across environments.
# ---------------------------------------------------------------------------

def _normalize_policy(raw: Dict[str, Any]) -> Dict[str, Any]:
    if "meap_v1" in raw:
        return raw
    # legacy -> normalize
    if "policy" in raw:
        # Map legacy keys into meap_v1-compatible structure.
        pol = raw.get("policy") or {}
        meap = {
            "policy_id": str(pol.get("name") or "MEAP_V1_LEGACY"),
            "policy_version": int(pol.get("version") or 1),
            "mode": str(pol.get("mode") or "REVIEW_ONLY"),
            "thresholds": raw.get("thresholds") or {
                "max_bundle_mb": int(raw.get("limits", {}).get("max_bundle_mb", 250)),
                "max_files_in_bundle": int(raw.get("limits", {}).get("max_files_in_bundle", 20000)),
                "require_signature": True,
                "require_provenance_chain_intact": bool(raw.get("replay", {}).get("require_provenance_chain", True)),
                "require_manifest_hashes": True,
                "require_deterministic_bundle_hash": True,
                "require_policy_hash_match": bool(raw.get("replay", {}).get("require_provenance_chain", True)),
                "require_allowlist_hash_match": True,
            },
            "protected_paths": list(raw.get("protected_paths") or []),
            "accept": {
                "allowed_artifact_types": list((raw.get("accept") or {}).get("allowed_artifact_types", [
                    "code","dsl","onnx","weights","report","bundle","blob","provenance","sbom","kg_delta"
                ])),
                "deny_network_by_default": True,
            },
            "replay": {
                "allow_reexecute_tools": False
            },
            "kill_switch": raw.get("kill_switch") or {},
        }
        return {"meap_v1": meap}
    return {"meap_v1": {
        "policy_id":"MEAP_V1_DEFAULT",
        "policy_version":1,
        "mode":"REVIEW_ONLY",
        "thresholds":{},
        "protected_paths":[],
        "accept":{},
        "replay":{},
    }}

@dataclass(frozen=True)
class MEAPPolicy:
    raw: Dict[str, Any]

    @property
    def meap(self) -> Dict[str, Any]:
        return dict(self.raw["meap_v1"])

    @property
    def policy_id(self) -> str:
        return str(self.meap.get("policy_id", "MEAP_V1"))

    @property
    def policy_version(self) -> int:
        return int(self.meap.get("policy_version", 1))

    @property
    def mode(self) -> str:
        return str(self.meap.get("mode", "REVIEW_ONLY"))

    @property
    def thresholds(self) -> Dict[str, Any]:
        return dict(self.meap.get("thresholds", {}))

    @property
    def protected_paths(self) -> list[str]:
        return list(self.meap.get("protected_paths", []))

    @property
    def accept(self) -> Dict[str, Any]:
        return dict(self.meap.get("accept", {}))

    @property
    def replay(self) -> Dict[str, Any]:
        return dict(self.meap.get("replay", {}))

    @property
    def kill_switch(self) -> Dict[str, Any]:
        return dict(self.meap.get("kill_switch", {}))

    def canonical_hash(self) -> str:
        # Hash the normalized meap_v1 object for stability.
        return hash_str(canonical_json(self.raw.get("meap_v1", self.raw)))

def load_policy(path: str | Path) -> MEAPPolicy:
    p = Path(path).resolve()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    norm = _normalize_policy(raw)
    return MEAPPolicy(norm)

def canonical_hash_dict(obj: Mapping[str, Any]) -> str:
    return hash_str(canonical_json(obj))
