from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Set, Tuple

from .policy import MEAPPolicy


@dataclass(frozen=True)
class MEAPFinding:
    code: str
    message: str
    severity: str = "error"
    subject: Optional[str] = None


@dataclass(frozen=True)
class MEAPEval:
    ok: bool
    findings: List[MEAPFinding]
    artifact_types_seen: List[str]


_EXT_MAP = {
    # core
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".html": "code",
    ".css": "code",
    ".md": "report",
    ".txt": "report",
    ".json": "blob",
    ".yaml": "blob",
    ".yml": "blob",
    ".csv": "report",
    ".pdf": "report",
    ".docx": "report",
    # ML
    ".onnx": "onnx",
    ".pt": "weights",
    ".pth": "weights",
    ".bin": "weights",
    ".safetensors": "weights",
    # termite ecosystem meta
    ".jsonl": "kg_delta",
}


def _artifact_type_for_name(name: str) -> str:
    p = PurePosixPath(name)
    if p.name in ("manifest.json", "attestation.json", "attestation.sig", "attestation.dsse.json"):
        return "bundle"
    # SBOM: legacy and CycloneDX layout
    if p.name.endswith("sbom.json") or p.name == "sbom.json" or str(p).startswith("sbom/"):
        return "sbom"
    if p.name.startswith("provenance") and p.suffix == ".jsonl":
        return "provenance"
    # extension mapping (last suffix)
    suf = p.suffix.lower()
    return _EXT_MAP.get(suf, "blob")


def evaluate_bundle_manifest(policy: MEAPPolicy, files_map: Dict[str, str]) -> MEAPEval:
    """Evaluate MEAP accept rules against bundle manifest entries.

    This runs AFTER cryptographic verification and hash checks.
    """
    findings: List[MEAPFinding] = []

    ks = policy.kill_switch
    if bool(ks.get("enabled", False)) or bool(ks.get("kill", False)):
        findings.append(MEAPFinding("kill_switch_enabled", "MEAP kill-switch is enabled; refusing bundle."))

    allowed = set(policy.accept.get("allowed_artifact_types") or [])
    if not allowed:
        # if policy doesn't specify, treat as allow-all
        allowed = set()

    seen: Set[str] = set()
    for fname in files_map.keys():
        t = _artifact_type_for_name(str(fname))
        seen.add(t)
        if allowed and t not in allowed:
            findings.append(MEAPFinding(
                "artifact_type_denied",
                f"artifact type '{t}' is not in policy allow-list",
                subject=str(fname),
            ))

    ok = not any(f.severity == "error" for f in findings)
    return MEAPEval(ok=ok, findings=findings, artifact_types_seen=sorted(seen))
