from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


EVIDENCE_STATES = ("captured", "sealed", "verified", "quarantined", "exported")
REVIEW_DECISION_STATES = ("unreviewed", "staged", "approved", "rejected", "quarantined")
REVIEW_SCHEDULE_STATES = ("unscheduled", "scheduled", "due_soon", "overdue")
EXPORT_STATES = ("pending", "ready", "exported")
VERIFICATION_STATES = ("passed", "failed", "not_run")
RUNTIME_HANDOFF_STATES = ("review_required", "ready_for_bridge", "blocked")
JOB_LIFECYCLE_STATES = ("queued", "running", "succeeded", "failed", "canceled")
VERIFICATION_MATERIAL_FILES = {
    "manifest.json",
    "attestation.json",
    "attestation.sig",
    "attestation.dsse.json",
    "sbom/bom.cdx.json",
    "sbom/bom.dsse.json",
}

_RISK_STATUS_MAP = {
    "open": "open",
    "active": "open",
    "pending": "open",
    "in_review": "open",
    "under review": "open",
    "resolved": "closed",
    "closed": "closed",
    "mitigated": "closed",
    "controlled": "closed",
    "quarantine": "quarantined",
    "quarantined": "quarantined",
    "blocked": "quarantined",
}
_CONTROL_STATUS_MAP = {
    "planned": "planned",
    "draft": "planned",
    "pending": "planned",
    "active": "active",
    "implemented": "active",
    "enforced": "active",
    "live": "active",
    "retired": "retired",
    "archived": "retired",
    "quarantine": "quarantined",
    "quarantined": "quarantined",
}
_REVIEW_GATE_STATUS_MAP = {
    "planned": "staged",
    "pending": "staged",
    "scheduled": "staged",
    "in_review": "staged",
    "under review": "staged",
    "staged": "staged",
    "approved": "approved",
    "complete": "approved",
    "completed": "approved",
    "passed": "approved",
    "rejected": "rejected",
    "denied": "rejected",
    "failed": "rejected",
    "exception": "quarantined",
    "blocked": "quarantined",
    "quarantine": "quarantined",
    "quarantined": "quarantined",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _jsonl_chain_head(text: str) -> str:
    last = ""
    for line in text.splitlines():
        s = line.strip()
        if s:
            last = s
    return _sha256_bytes(last.encode("utf-8")) if last else ""


def _zip_member_uri(bundle_path: Path, name: str) -> str:
    return f"zip:{bundle_path}!/{name}"


def _contract_seed(meta: Dict[str, Any]) -> str:
    return str(meta.get("manifest_sha256") or meta.get("bundle_sha256") or "unknown")[:12]


def _contract_id(prefix: str, meta: Dict[str, Any]) -> str:
    return f"{prefix}{_contract_seed(meta)}"


def _normalize(raw: Any, mapping: Dict[str, str], *, default: str) -> str:
    key = str(raw or "").strip().lower()
    return mapping.get(key, default)


def normalize_risk_status(raw: Any) -> str:
    return _normalize(raw, _RISK_STATUS_MAP, default="open")


def normalize_control_status(raw: Any) -> str:
    return _normalize(raw, _CONTROL_STATUS_MAP, default="planned")


def normalize_review_gate_status(raw: Any) -> str:
    return _normalize(raw, _REVIEW_GATE_STATUS_MAP, default="staged")


def normalize_contract_review_state(raw: Any) -> str:
    normalized = normalize_review_gate_status(raw)
    if normalized in {"approved", "quarantined", "staged"}:
        return normalized
    return "staged"


def status_vocabulary() -> Dict[str, Any]:
    return {
        "evidence": list(EVIDENCE_STATES),
        "review_decision": list(REVIEW_DECISION_STATES),
        "review_schedule": list(REVIEW_SCHEDULE_STATES),
        "export": list(EXPORT_STATES),
        "verification": list(VERIFICATION_STATES),
        "runtime_handoff": list(RUNTIME_HANDOFF_STATES),
        "job_lifecycle": list(JOB_LIFECYCLE_STATES),
        "bridge": {
            "admissibility_hint": ["evidence_only"],
            "canonical_status": ["not_canonical"],
            "review_required": [True],
        },
    }


def architecture_layers() -> list[Dict[str, Any]]:
    return [
        {
            "layer_id": "termite_fieldpack",
            "title": "Ingestion and sealing",
            "plane": "data_plane",
            "owns": [
                "uploaded bytes",
                "content-addressed storage",
                "bundle manifests",
                "provenance chains",
                "sealed bundle bytes",
                "bundle verification material",
            ],
        },
        {
            "layer_id": "mite_ecology",
            "title": "Review and deterministic analysis",
            "plane": "data_plane",
            "owns": [
                "kg deltas",
                "bundle acceptance outcomes",
                "review and quarantine state",
                "deterministic replay reports",
                "analysis exports",
            ],
        },
        {
            "layer_id": "fieldgrade_ui",
            "title": "Governance and orchestration",
            "plane": "control_plane",
            "owns": [
                "job scheduling",
                "worker lifecycle",
                "tenant-scoped runtime roots",
                "dashboard projections",
                "governance records",
                "API surface contracts",
            ],
        },
    ]


def data_plane_contract() -> Dict[str, Any]:
    return {
        "plane": "data_plane",
        "concerns": [
            "immutable evidence artifacts",
            "manifest-bound hashes",
            "provenance continuity",
            "kg delta application",
            "deterministic replay and export outputs",
        ],
    }


def control_plane_contract() -> Dict[str, Any]:
    return {
        "plane": "control_plane",
        "concerns": [
            "job submission and retries",
            "worker heartbeat and readiness",
            "tenant isolation",
            "dashboard summaries",
            "review queues",
            "contract publication",
        ],
    }


def build_architecture_overview(
    *,
    repo_root: Path,
    jobs_db: Path,
    mite_db: Path,
    tenants_root: Path,
    ui_runtime_dir: Path,
    worker_status: Dict[str, Any],
) -> Dict[str, Any]:
    from .storage import bundle_store_backend

    jobs_path = Path(jobs_db)
    mite_path = Path(mite_db)
    return {
        "schema_version": "fieldgrade.architecture_overview.v1",
        "generated_at": _utc_now_iso(),
        "layers": architecture_layers(),
        "planes": {
            "data_plane": data_plane_contract(),
            "control_plane": control_plane_contract(),
        },
        "status_vocabulary": status_vocabulary(),
        "storage_boundary": {
            "bundle_store_backend": bundle_store_backend(),
            "jobs_db": str(jobs_path),
            "jobs_db_exists": jobs_path.exists(),
            "mite_db": str(mite_path),
            "mite_db_exists": mite_path.exists(),
            "tenants_root": str(tenants_root),
            "ui_runtime_dir": str(ui_runtime_dir),
        },
        "runtime": {
            "worker": worker_status,
            "readyz_contract": {
                "service_ready": jobs_path.exists() and mite_path.exists(),
                "required_paths": [str(jobs_path), str(mite_path)],
            },
        },
        "bridge_contracts": {
            "schemas": [
                "schemas/fieldgrade_evidence_packet_v1.json",
                "schemas/fieldgrade_runtime_hardening_report_v1.json",
                "schemas/cfx_fieldgrade_bridge_v1.json",
                "schemas/cfx_cao_candidate_v1.json",
            ],
            "review_bound": True,
        },
        "repo_root": str(repo_root),
    }


def _bundle_metadata(bundle_path: Path) -> Dict[str, Any]:
    bundle_path = Path(bundle_path)
    manifest: Dict[str, Any] = {}
    manifest_bytes = b""
    names: set[str] = set()
    provenance_text = ""
    has_kg_delta = False
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = set(zf.namelist())
        if "manifest.json" in names:
            manifest_bytes = zf.read("manifest.json")
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        if "provenance.jsonl" in names:
            provenance_text = zf.read("provenance.jsonl").decode("utf-8")
        has_kg_delta = "kg_delta.jsonl" in names
    return {
        "bundle_id": bundle_path.stem,
        "bundle_path": str(bundle_path),
        "bundle_sha256": _sha256_file(bundle_path),
        "manifest_sha256": _sha256_bytes(manifest_bytes) if manifest_bytes else "",
        "bundle_map_hash": str(manifest.get("bundle_map_hash") or ""),
        "kg_delta_sha256": str(manifest.get("kg_delta_hash") or ""),
        "provenance_sha256": str(manifest.get("provenance_hash") or ""),
        "fieldpack_path": str(bundle_path),
        "kg_delta_path": _zip_member_uri(bundle_path, "kg_delta.jsonl") if has_kg_delta else "",
        "provenance_chain_head": _jsonl_chain_head(provenance_text),
        "verification_materials": sorted(
            name
            for name in names
            if name in VERIFICATION_MATERIAL_FILES
        ),
    }


def _bridge_provenance(meta: Dict[str, Any]) -> tuple[str, str]:
    head = str(meta.get("provenance_chain_head") or "").strip()
    if head:
        return head, "provenance_chain_head"
    provenance_sha = str(meta.get("provenance_sha256") or "").strip()
    if provenance_sha:
        return provenance_sha, "provenance_sha256_fallback"
    return str(meta.get("bundle_sha256") or "").strip(), "bundle_sha256_fallback"


def _list_export_files(export_root: Path) -> list[str]:
    if not export_root.exists():
        return []
    return [str(p) for p in sorted(export_root.rglob("*")) if p.is_file()]


def build_pipeline_contracts(
    *,
    repo_root: Path,
    bundle_path: Path,
    verify_result: Dict[str, Any],
    replay_verify_result: Dict[str, Any],
    run_id: str,
    export_root: Path,
    bundle_store_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = _bundle_metadata(bundle_path)
    verify_ok = bool(verify_result.get("ok"))
    replay_ok = bool(replay_verify_result.get("ok", replay_verify_result.get("match")))
    provenance_ok = bool(replay_verify_result.get("kg_deltas_chain_ok", replay_ok))
    review_chain_ok = bool(replay_verify_result.get("ingested_chain_ok", replay_ok))
    export_files = _list_export_files(export_root)

    export_state = "exported" if export_files else ("ready" if verify_ok and replay_ok else "pending")
    evidence_state = "quarantined" if not verify_ok else ("exported" if export_state == "exported" else "verified")
    review_state = "approved" if verify_ok and replay_ok and provenance_ok and review_chain_ok else "quarantined"
    runtime_handoff_state = "ready_for_bridge" if review_state == "approved" else "blocked"
    verification_status = "passed" if verify_ok else "failed"
    replay_status = "passed" if replay_ok else "failed"

    normalized_review_state = normalize_contract_review_state(review_state)
    bridge_provenance_head, bridge_provenance_source = _bridge_provenance(meta)

    evidence_packet = {
        "schema_version": "fieldgrade.evidence_packet.v1",
        "packet_id": _contract_id("FG-PACKET-", meta),
        "bundle_id": meta["bundle_id"],
        "bundle_path": meta["bundle_path"],
        "manifest_sha256": meta["manifest_sha256"],
        "provenance_chain_head": bridge_provenance_head,
        "evidence_state": evidence_state,
        "review_state": normalized_review_state,
        "review_required": True,
        "canonical_status": "not_canonical",
        "created_at": _utc_now_iso(),
    }

    runtime_hardening_report = {
        "schema_version": "fieldgrade.runtime_hardening_report.v1",
        "report_id": f"FG-RUNTIME-{str(run_id)[:12]}",
        "run_id": run_id,
        "bundle_id": meta["bundle_id"],
        "verification_status": verification_status,
        "replay_status": replay_status,
        "determinism_ok": bool(replay_ok),
        "provenance_continuity_ok": bool(provenance_ok and review_chain_ok),
        "invariant_status": "ok" if verify_ok and replay_ok and provenance_ok and review_chain_ok else "attention_required",
        "created_at": _utc_now_iso(),
    }

    fieldgrade_bridge = {
        "schema_version": "cfx.fieldgrade_bridge.v1",
        "bridge_id": _contract_id("FG-BRIDGE-", meta),
        "bundle_id": meta["bundle_id"],
        "manifest_sha256": meta["manifest_sha256"],
        "fieldpack_path": meta["fieldpack_path"],
        "kg_delta_path": meta["kg_delta_path"],
        "provenance_chain_head": bridge_provenance_head,
        "replay_status": replay_status,
        "verification_status": verification_status,
        "admissibility_hint": "evidence_only",
        "review_required": True,
        "created_at": _utc_now_iso(),
        "notes": f"Bridge artifact is review-bound and evidence-only. provenance_source={bridge_provenance_source}",
    }

    cao_candidate = {
        "schema_version": "cfx.cao_candidate.v1",
        "candidate_id": _contract_id("CAO-CANDIDATE-", meta),
        "source_bundle_id": meta["bundle_id"],
        "source_manifest_sha256": meta["manifest_sha256"],
        "proposed_title": f"Fieldgrade bundle {meta['bundle_id']}",
        "proposed_domain": "CFX",
        "proposed_object_type": "fieldgrade_bundle",
        "evidence_packet": evidence_packet["packet_id"],
        "runtime_trace": runtime_hardening_report["report_id"],
        "claim_level_recommendation": "evidence-supported" if verify_ok and replay_ok else "unknown",
        "review_required": True,
        "canonical_status": "not_canonical",
        "created_at": _utc_now_iso(),
        "notes": "Prepared for downstream review only.",
    }

    return {
        "schema_version": "fieldgrade.pipeline_contracts.v1",
        "run_id": run_id,
        "layers": architecture_layers(),
        "status_vocabulary": status_vocabulary(),
        "bundle_acceptance": {
            "contract_type": "fieldgrade_bundle_acceptance_contract/1.0",
            "bundle_id": meta["bundle_id"],
            "bundle_path": meta["bundle_path"],
            "bundle_sha256": meta["bundle_sha256"],
            "manifest_sha256": meta["manifest_sha256"],
            "kg_delta_path": meta["kg_delta_path"],
            "status": evidence_state,
            "accepted_into_review": bool(verify_ok),
        },
        "verification_result": {
            "contract_type": "fieldgrade_verification_result/1.0",
            "bundle_id": meta["bundle_id"],
            "status": verification_status,
            "checks": {
                "bundle_map_hash": meta["bundle_map_hash"],
                "verification_materials": meta["verification_materials"],
            },
            "raw": verify_result,
        },
        "review_decision": {
            "contract_type": "fieldgrade_review_decision/1.0",
            "bundle_id": meta["bundle_id"],
            "status": review_state,
            "decision_basis": {
                "replay_ok": replay_ok,
                "kg_deltas_chain_ok": provenance_ok,
                "ingested_chain_ok": review_chain_ok,
            },
        },
        "export_package": {
            "contract_type": "fieldgrade_export_package/1.0",
            "status": export_state,
            "export_root": str(export_root),
            "files": export_files,
        },
        "runtime_hardening_report": runtime_hardening_report,
        "evidence_packet": evidence_packet,
        "fieldgrade_bridge": fieldgrade_bridge,
        "cao_candidate": cao_candidate,
        "runtime_handoff": {
            "state": runtime_handoff_state,
            "review_required": True,
        },
        "bundle_store": bundle_store_info or {},
        "repo_root": str(repo_root),
    }


def governance_state_views(record: Dict[str, Any], advisory: Dict[str, Any], crosswalk: Dict[str, Any]) -> Dict[str, str]:
    record_status = str(record.get("status") or "").strip().lower()
    if "quarantine" in record_status:
        review_state = "quarantined"
    else:
        gate_statuses = [
            normalize_review_gate_status(item.get("status"))
            for item in (record.get("review_gates") if isinstance(record.get("review_gates"), list) else [])
        ]
        if "approved" in gate_statuses:
            review_state = "approved"
        elif "rejected" in gate_statuses:
            review_state = "rejected"
        elif gate_statuses:
            review_state = "staged"
        else:
            review_state = "unreviewed"

    export_status = record.get("export_status") if isinstance(record.get("export_status"), dict) else {}
    all_exports_ready = bool(export_status) and all(bool(v) for v in export_status.values())
    evidence_items = record.get("evidence") if isinstance(record.get("evidence"), list) else []
    gap_count = int(crosswalk.get("gap_count") or 0)

    if "quarantine" in record_status:
        evidence_state = "quarantined"
    elif all_exports_ready:
        evidence_state = "exported"
    elif gap_count == 0 and evidence_items:
        evidence_state = "verified"
    elif evidence_items:
        evidence_state = "sealed"
    else:
        evidence_state = "captured"

    if all_exports_ready:
        export_state = "exported"
    elif gap_count == 0:
        export_state = "ready"
    else:
        export_state = "pending"

    readiness_status = str(advisory.get("readiness_status") or "")
    if review_state == "quarantined":
        runtime_handoff_state = "blocked"
    elif readiness_status in {"review_ready", "export_ready"} and review_state == "approved":
        runtime_handoff_state = "ready_for_bridge"
    else:
        runtime_handoff_state = "review_required"

    return {
        "evidence": evidence_state,
        "review": review_state,
        "runtime_handoff": runtime_handoff_state,
        "export": export_state,
    }
