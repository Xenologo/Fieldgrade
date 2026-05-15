from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from mite_ecology.hashutil import canonical_json, sha256_str

from .contracts import (
    governance_state_views,
    normalize_control_status,
    normalize_review_gate_status,
    normalize_risk_status,
)
from .execution_ledger import append_event, create_execution, ensure_db, iter_events, verify_chain


CORE_SCHEMA_NAME = "fieldgrade_core_objects_v1.json"
GOVAI_SCHEMA_NAME = "fieldgrade_govai_system_record_v1.json"
CROSSWALK_RESOURCE = "fieldgrade_govai_crosswalks_v1.json"
EXPORT_KINDS = (
    "internal_governance_record",
    "atrs_draft",
    "public_summary",
    "evidence_gap_report",
)


class GovernanceLedger:
    def __init__(self, *, repo_root: Path, runtime_root: Path, jobs_db_path: Path):
        self.repo_root = Path(repo_root)
        self.root = Path(runtime_root)
        self.jobs_db_path = Path(jobs_db_path)
        self.root.mkdir(parents=True, exist_ok=True)
        ensure_db(self.jobs_db_path)
        self._organizations_path = self.root / "organizations.json"
        self._records_dir = self.root / "records"
        self._exports_dir = self.root / "exports"
        self._counters_path = self.root / "_counters.json"
        self._records_dir.mkdir(parents=True, exist_ok=True)
        self._exports_dir.mkdir(parents=True, exist_ok=True)
        self._govai_validator = self._load_validator(self.repo_root / "schemas" / GOVAI_SCHEMA_NAME)
        self._crosswalk_templates = self._load_json(self.repo_root / "resources" / CROSSWALK_RESOURCE, default={})

    @staticmethod
    def _load_json(path: Path, *, default: Any) -> Any:
        if not path.exists():
            return deepcopy(default)
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return deepcopy(default)
        return json.loads(raw)

    @staticmethod
    def _write_json(path: Path, obj: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(canonical_json(obj) + "\n", encoding="utf-8")

    @staticmethod
    def _load_validator(path: Path) -> Draft202012Validator:
        schema = json.loads(path.read_text(encoding="utf-8"))
        core_path = path.parent / CORE_SCHEMA_NAME
        core_schema = json.loads(core_path.read_text(encoding="utf-8"))
        registry = (
            Registry()
            .with_resource(core_schema.get("$id") or CORE_SCHEMA_NAME, Resource.from_contents(core_schema))
            .with_resource(CORE_SCHEMA_NAME, Resource.from_contents(core_schema))
            .with_resource(schema.get("$id") or path.name, Resource.from_contents(schema))
            .with_resource(path.name, Resource.from_contents(schema))
        )
        return Draft202012Validator(schema, registry=registry)

    def _next_id(self, prefix: str) -> str:
        counters = self._load_json(self._counters_path, default={})
        current = int(counters.get(prefix, 0)) + 1
        counters[prefix] = current
        self._write_json(self._counters_path, counters)
        return f"{prefix}{current:06d}"

    def _organizations(self) -> List[Dict[str, Any]]:
        data = self._load_json(self._organizations_path, default={"organizations": []})
        orgs = data.get("organizations") if isinstance(data, dict) else []
        return orgs if isinstance(orgs, list) else []

    def list_organizations(self) -> List[Dict[str, Any]]:
        return sorted(self._organizations(), key=lambda x: str(x.get("organization_id") or ""))

    def create_organization(self, body: Dict[str, Any], *, actor_id: str) -> Dict[str, Any]:
        orgs = self._organizations()
        org_id = self._next_id("FG-ORG-")
        now_ms = int(time.time() * 1000)
        org = {
            "organization_id": org_id,
            "name": str(body.get("name") or "Untitled organization").strip(),
            "sector": str(body.get("sector") or "Public sector").strip(),
            "deployment_model": str(body.get("deployment_model") or "Local-first / private cloud").strip(),
            "created_at_ms": now_ms,
            "created_by": actor_id,
            "notes": str(body.get("notes") or "").strip(),
        }
        orgs.append(org)
        self._write_json(self._organizations_path, {"organizations": sorted(orgs, key=lambda x: x["organization_id"])})
        return org

    def _record_path(self, record_id: str) -> Path:
        return self._records_dir / f"{record_id}.json"

    def _get_record(self, record_id: str) -> Dict[str, Any]:
        path = self._record_path(record_id)
        if not path.exists():
            raise KeyError(record_id)
        data = self._load_json(path, default={})
        if not isinstance(data, dict):
            raise KeyError(record_id)
        return data

    def _validate_record(self, record: Dict[str, Any]) -> None:
        errors = sorted(self._govai_validator.iter_errors(record), key=lambda e: list(e.path))
        if errors:
            e0 = errors[0]
            path = "/" + "/".join(str(p) for p in e0.path)
            raise ValueError(f"record validation failed at {path or '/'}: {e0.message}")

    @staticmethod
    def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = GovernanceLedger._deep_merge(out[key], value)
            else:
                out[key] = deepcopy(value)
        return out

    @staticmethod
    def _non_empty(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ""
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) > 0
        return True

    @staticmethod
    def _get_path_values(obj: Any, path: str) -> List[Any]:
        parts = [p for p in str(path).split(".") if p]
        values = [obj]
        for part in parts:
            next_values: List[Any] = []
            for value in values:
                if isinstance(value, list):
                    next_values.extend(item for item in value if item is not None)
                    continue
                if isinstance(value, dict) and part in value:
                    next_values.append(value.get(part))
            values = next_values
        flattened: List[Any] = []
        for value in values:
            if isinstance(value, list):
                flattened.extend(value)
            else:
                flattened.append(value)
        return flattened

    def _compute_crosswalks(self, record: Dict[str, Any]) -> Dict[str, Any]:
        templates = self._crosswalk_templates.get("templates") if isinstance(self._crosswalk_templates, dict) else []
        evaluations: List[Dict[str, Any]] = []
        gaps: List[Dict[str, Any]] = []
        for template in templates if isinstance(templates, list) else []:
            frameworks = template.get("frameworks") if isinstance(template, dict) else []
            fw_rows: List[Dict[str, Any]] = []
            for fw in frameworks if isinstance(frameworks, list) else []:
                obligations = fw.get("obligations") if isinstance(fw, dict) else []
                ob_rows: List[Dict[str, Any]] = []
                for obligation in obligations if isinstance(obligations, list) else []:
                    required_paths = obligation.get("required_paths") if isinstance(obligation, dict) else []
                    required_paths = required_paths if isinstance(required_paths, list) else []
                    missing_paths = []
                    for rp in required_paths:
                        values = self._get_path_values(record, str(rp))
                        if not any(self._non_empty(v) for v in values):
                            missing_paths.append(str(rp))
                    satisfied = len(missing_paths) == 0
                    row = {
                        "obligation_id": obligation.get("obligation_id"),
                        "title": obligation.get("title"),
                        "required_paths": required_paths,
                        "missing_paths": missing_paths,
                        "status": "satisfied" if satisfied else "gap",
                    }
                    if not satisfied:
                        gaps.append(
                            {
                                "framework": fw.get("framework_id"),
                                "obligation_id": obligation.get("obligation_id"),
                                "title": obligation.get("title"),
                                "missing_paths": missing_paths,
                            }
                        )
                    ob_rows.append(row)
                fw_rows.append(
                    {
                        "framework_id": fw.get("framework_id"),
                        "title": fw.get("title"),
                        "obligations": ob_rows,
                    }
                )
            evaluations.append(
                {
                    "template_id": template.get("template_id"),
                    "title": template.get("title"),
                    "frameworks": fw_rows,
                }
            )
        return {"templates": evaluations, "gaps": gaps, "gap_count": len(gaps)}

    @staticmethod
    def _crosswalk_stats(crosswalk: Dict[str, Any]) -> Dict[str, int]:
        total = 0
        satisfied = 0
        templates = crosswalk.get("templates") if isinstance(crosswalk, dict) else []
        for template in templates if isinstance(templates, list) else []:
            frameworks = template.get("frameworks") if isinstance(template, dict) else []
            for framework in frameworks if isinstance(frameworks, list) else []:
                obligations = framework.get("obligations") if isinstance(framework, dict) else []
                for obligation in obligations if isinstance(obligations, list) else []:
                    total += 1
                    if obligation.get("status") == "satisfied":
                        satisfied += 1
        return {"total_obligations": total, "satisfied_obligations": satisfied}

    @staticmethod
    def _parse_due_date(value: Any) -> Optional[date]:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None

    def _review_posture(self, record: Dict[str, Any]) -> Dict[str, Any]:
        due_date = self._parse_due_date(record.get("next_review_due"))
        if due_date is None:
            return {
                "state": "unscheduled",
                "days_until_due": None,
                "due_date": str(record.get("next_review_due") or ""),
            }
        delta = (due_date - date.today()).days
        if delta < 0:
            state = "overdue"
        elif delta <= 14:
            state = "due_soon"
        else:
            state = "scheduled"
        return {"state": state, "days_until_due": delta, "due_date": due_date.isoformat()}

    @staticmethod
    def _priority_rank(priority: str) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(str(priority or "").lower(), 3)

    def _advisory(self, record: Dict[str, Any], crosswalk: Dict[str, Any]) -> Dict[str, Any]:
        stats = self._crosswalk_stats(crosswalk)
        review = self._review_posture(record)
        gap_count = int(crosswalk.get("gap_count") or 0)
        export_status = record.get("export_status") if isinstance(record.get("export_status"), dict) else {}
        export_total = len(EXPORT_KINDS)
        exports_ready = sum(1 for value in export_status.values() if value)
        all_exports_ready = export_total > 0 and exports_ready == export_total
        controls = record.get("controls") if isinstance(record.get("controls"), list) else []
        risks = record.get("risks") if isinstance(record.get("risks"), list) else []
        review_gates = record.get("review_gates") if isinstance(record.get("review_gates"), list) else []
        approved_gates = sum(1 for gate in review_gates if normalize_review_gate_status(gate.get("status")) == "approved")
        open_risks = sum(
            1 for risk in risks if normalize_risk_status(risk.get("review_status")) == "open"
        )

        actions: List[Dict[str, Any]] = []
        for gap in crosswalk.get("gaps", []) if isinstance(crosswalk.get("gaps"), list) else []:
            framework = str(gap.get("framework") or "").strip() or "FRAMEWORK"
            obligation_id = str(gap.get("obligation_id") or framework).strip().lower().replace("_", "-")
            priority = "high" if framework != "FIELDGRADE_INTERNAL_CONTROLS" else "medium"
            actions.append(
                {
                    "action_id": f"close-gap-{obligation_id}",
                    "priority": priority,
                    "title": str(gap.get("title") or "Close governance evidence gap"),
                    "reason": f"Missing record fields: {', '.join(gap.get('missing_paths') or []) or 'not recorded'}",
                    "framework": framework,
                    "missing_paths": list(gap.get("missing_paths") or []),
                    "recommended_endpoint": f"/api/governance/systems/{record['record_id']}",
                }
            )

        if review["state"] == "overdue":
            actions.append(
                {
                    "action_id": "renew-review",
                    "priority": "high",
                    "title": "Renew the overdue governance review",
                    "reason": f"Review date {review['due_date']} has passed.",
                    "recommended_endpoint": f"/api/governance/systems/{record['record_id']}/review_gates",
                }
            )
        elif review["state"] == "due_soon":
            actions.append(
                {
                    "action_id": "prepare-review",
                    "priority": "medium",
                    "title": "Prepare the upcoming governance review",
                    "reason": f"Review is due in {review['days_until_due']} day(s).",
                    "recommended_endpoint": f"/api/governance/systems/{record['record_id']}/review_gates",
                }
            )
        elif review["state"] == "unscheduled":
            actions.append(
                {
                    "action_id": "schedule-review",
                    "priority": "medium",
                    "title": "Set a governance review date",
                    "reason": "The system record does not yet define next_review_due.",
                    "recommended_endpoint": f"/api/governance/systems/{record['record_id']}",
                }
            )

        if open_risks > 0 and not controls:
            actions.append(
                {
                    "action_id": "stabilize-open-risks",
                    "priority": "high",
                    "title": "Add controls for open risks",
                    "reason": f"{open_risks} open risk(s) are recorded without any control objects.",
                    "recommended_endpoint": f"/api/governance/systems/{record['record_id']}/controls",
                }
            )

        if review_gates and approved_gates == 0:
            actions.append(
                {
                    "action_id": "approve-review-gates",
                    "priority": "medium",
                    "title": "Complete at least one review gate approval",
                    "reason": "Review gates exist, but none are marked approved or completed.",
                    "recommended_endpoint": f"/api/governance/systems/{record['record_id']}/review_gates",
                }
            )

        if gap_count == 0 and not all_exports_ready:
            actions.append(
                {
                    "action_id": "generate-exports",
                    "priority": "medium",
                    "title": "Generate the governance export pack",
                    "reason": "The record is complete enough to produce its audit artifacts.",
                    "recommended_endpoint": f"/api/governance/systems/{record['record_id']}/exports/generate",
                }
            )

        actions.sort(key=lambda item: (self._priority_rank(str(item.get("priority") or "")), str(item.get("title") or "")))

        completeness_score = 0.0
        if stats["total_obligations"] > 0:
            completeness_score = stats["satisfied_obligations"] / stats["total_obligations"]
        review_score = {"scheduled": 1.0, "due_soon": 0.6, "overdue": 0.0, "unscheduled": 0.25}.get(
            str(review.get("state") or ""),
            0.0,
        )
        score = int(round((completeness_score * 70.0) + ((exports_ready / export_total) * 20.0) + (review_score * 10.0)))

        readiness_status = "attention_required"
        if gap_count == 0 and all_exports_ready and review["state"] in {"scheduled", "due_soon"}:
            readiness_status = "export_ready"
        elif gap_count == 0:
            readiness_status = "review_ready"

        return {
            "readiness_score": max(0, min(score, 100)),
            "readiness_status": readiness_status,
            "review": review,
            "crosswalk": {
                "gap_count": gap_count,
                "total_obligations": stats["total_obligations"],
                "satisfied_obligations": stats["satisfied_obligations"],
            },
            "exports": {
                "ready": exports_ready,
                "total": export_total,
                "all_ready": all_exports_ready,
            },
            "operations": {
                "open_risks": open_risks,
                "controls": len(controls),
                "review_gates": len(review_gates),
                "approved_review_gates": approved_gates,
            },
            "prioritized_actions": actions,
        }

    def _atrs_draft(self, record: Dict[str, Any], crosswalk: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "fieldgrade_export_pack/1.0",
            "export_kind": "ATRS_DRAFT",
            "record_id": record["record_id"],
            "title": record.get("title"),
            "ownership": {
                "senior_responsible_owner": record.get("owners", {}).get("senior_responsible_owner"),
                "data_owner": record.get("owners", {}).get("data_owner"),
                "technical_owner": record.get("owners", {}).get("technical_owner"),
                "supplier_owner": record.get("owners", {}).get("supplier_owner"),
            },
            "summary": record.get("purpose", {}).get("plain_english_summary"),
            "decision_context": record.get("purpose", {}).get("decision_context"),
            "affected_groups": record.get("purpose", {}).get("affected_groups"),
            "supplier": record.get("supplier", {}).get("supplier_name"),
            "model": {
                "model_type": record.get("system", {}).get("model_type"),
                "automation_level": record.get("system", {}).get("automation_level"),
                "human_final_decision": record.get("system", {}).get("human_final_decision"),
            },
            "data": record.get("data", {}),
            "risks": record.get("risks", []),
            "controls": record.get("controls", []),
            "human_oversight": record.get("human_oversight", {}),
            "evidence_gap_count": crosswalk.get("gap_count", 0),
        }

    def _public_summary(self, record: Dict[str, Any], crosswalk: Dict[str, Any]) -> str:
        purpose = record.get("purpose", {})
        system = record.get("system", {})
        supplier = record.get("supplier", {})
        oversight = record.get("human_oversight", {})
        risks = record.get("risks", [])
        controls = record.get("controls", [])
        affected = purpose.get("affected_groups") or []
        affected_lines = [f"- {str(x)}" for x in affected] if affected else ["Not yet recorded"]
        return "\n".join(
            [
                f"# {record.get('title', 'Untitled GovAI record')}",
                "",
                "## Plain-English summary",
                str(purpose.get("plain_english_summary") or "Summary not yet recorded."),
                "",
                "## Decision context",
                str(purpose.get("decision_context") or "Decision context not yet recorded."),
                "",
                "## Supplier and model",
                f"- Supplier: {supplier.get('supplier_name') or 'Not yet recorded'}",
                f"- Model type: {system.get('model_type') or 'Not yet recorded'}",
                f"- Automation level: {system.get('automation_level') or 'Not yet recorded'}",
                f"- Human final decision: {'Yes' if system.get('human_final_decision') else 'No / not recorded'}",
                "",
                "## Who may be affected",
                *affected_lines,
                "",
                "## Human oversight and appeal",
                f"- Oversight model: {oversight.get('oversight_model') or 'Not yet recorded'}",
                f"- Appeal route: {oversight.get('appeal_route') or 'Not yet recorded'}",
                "",
                "## Risks and controls",
                f"- Risks recorded: {len(risks)}",
                f"- Controls recorded: {len(controls)}",
                f"- Evidence gaps still open: {crosswalk.get('gap_count', 0)}",
            ]
        ) + "\n"

    def _export_bytes(self, content: Any) -> bytes:
        if isinstance(content, (dict, list)):
            return (canonical_json(content) + "\n").encode("utf-8")
        return str(content).encode("utf-8")

    def _write_export(self, record_id: str, kind: str, content: Any) -> Dict[str, Any]:
        suffix = ".md" if kind == "public_summary" else ".json"
        path = self._exports_dir / record_id / f"{kind}{suffix}"
        payload = self._export_bytes(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {
            "kind": kind,
            "path": str(path),
            "sha256": sha256_str(payload.decode("utf-8")),
            "bytes": len(payload),
        }

    def list_systems(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for path in sorted(self._records_dir.glob("FG-GOVAI-*.json")):
            data = self._load_json(path, default={})
            if not isinstance(data, dict):
                continue
            advisory = self._advisory(data, self._compute_crosswalks(data))
            views = governance_state_views(data, advisory, self._compute_crosswalks(data))
            items.append(
                {
                    "record_id": data.get("record_id"),
                    "organization_id": data.get("organization_id"),
                    "title": data.get("title"),
                    "status": data.get("status"),
                    "risk_tier": data.get("risk_tier"),
                    "next_review_due": data.get("next_review_due"),
                    "updated_at_ms": data.get("updated_at_ms"),
                    "export_status": data.get("export_status", {}),
                    "advisory": {
                        "readiness_score": advisory.get("readiness_score"),
                        "readiness_status": advisory.get("readiness_status"),
                        "review": advisory.get("review"),
                        "prioritized_actions": advisory.get("prioritized_actions", [])[:3],
                    },
                    "architecture_views": views,
                }
            )
        return items

    def create_system(self, body: Dict[str, Any], *, actor_id: str) -> Dict[str, Any]:
        record_id = self._next_id("FG-GOVAI-")
        now_ms = int(time.time() * 1000)
        base_record: Dict[str, Any] = {
            "type": "fieldgrade_govai_system_record/1.0",
            "fieldgrade_object_type": "AI_SYSTEM_RECORD",
            "record_id": record_id,
            "title": str(body.get("title") or "Untitled GovAI system").strip(),
            "sector_variant": "GovAI",
            "variant_pack": {
                "variant_id": "fieldgrade.govai.register@0.1.0",
                "title": "Fieldgrade Governance & Evidence Ledger / GovAI",
            },
            "organization_id": str(body.get("organization_id") or "").strip(),
            "status": str(body.get("status") or "Proposed").strip(),
            "risk_tier": str(body.get("risk_tier") or "Medium").strip(),
            "owners": {
                "senior_responsible_owner": "",
                "data_owner": "",
                "technical_owner": "",
                "supplier_owner": "",
            },
            "purpose": {
                "plain_english_summary": "",
                "decision_context": "",
                "affected_groups": [],
            },
            "system": {
                "supplier": "",
                "model_type": "",
                "automation_level": "Decision support",
                "human_final_decision": True,
            },
            "data": {
                "development_data_sources": [],
                "operational_data_sources": [],
                "lawful_basis": [],
                "retention_period": "",
                "data_quality_notes": "",
            },
            "supplier": {
                "supplier_name": "",
                "model_documentation_status": "",
                "hosting_location": "",
                "change_policy": "",
                "contract_notes": "",
            },
            "human_oversight": {
                "oversight_model": "",
                "human_reviewers": [],
                "appeal_route": "",
                "escalation_path": "",
            },
            "actors": [],
            "risks": [],
            "controls": [],
            "evidence": [],
            "decisions": [],
            "review_gates": [],
            "crosswalks": [],
            "export_status": {
                "internal_governance_record": False,
                "atrs_draft": False,
                "public_summary": False,
                "evidence_gap_report": False,
            },
            "created_at_ms": now_ms,
            "updated_at_ms": now_ms,
            "created_by": actor_id,
            "next_review_due": str(body.get("next_review_due") or "").strip(),
            "notes": str(body.get("notes") or "").strip(),
            "audit": {},
        }
        record = self._deep_merge(base_record, body or {})
        execution_id = create_execution(
            self.jobs_db_path,
            plan_id=f"govai_record:{record_id}",
            base_snapshot_hash=sha256_str(record_id),
        )
        record["audit"] = {"execution_id": execution_id}
        self._validate_record(record)
        event_hash = append_event(
            self.jobs_db_path,
            execution_id=execution_id,
            plan_id=f"govai_record:{record_id}",
            step_index=0,
            action_type="record.create",
            status="passed",
            observed={"record_id": record_id, "title": record.get("title")},
            actor_id=actor_id,
            justification="GovAI system record created",
        )
        ok, n = verify_chain(self.jobs_db_path, execution_id)
        record["audit"].update({"last_event_hash": event_hash, "chain_ok": ok, "events": n})
        self._write_json(self._record_path(record_id), record)
        return record

    def get_system(self, record_id: str) -> Dict[str, Any]:
        record = self._get_record(record_id)
        execution_id = record.get("audit", {}).get("execution_id")
        if execution_id:
            ok, n = verify_chain(self.jobs_db_path, str(execution_id))
            record.setdefault("audit", {})["chain_ok"] = ok
            record["audit"]["events"] = n
        return record

    def update_system(self, record_id: str, patch: Dict[str, Any], *, actor_id: str) -> Dict[str, Any]:
        record = self._get_record(record_id)
        merged = self._deep_merge(record, patch or {})
        merged["record_id"] = record_id
        merged["type"] = "fieldgrade_govai_system_record/1.0"
        merged["fieldgrade_object_type"] = "AI_SYSTEM_RECORD"
        merged["sector_variant"] = "GovAI"
        merged["updated_at_ms"] = int(time.time() * 1000)
        self._validate_record(merged)
        execution_id = merged.get("audit", {}).get("execution_id")
        if not execution_id:
            execution_id = create_execution(
                self.jobs_db_path,
                plan_id=f"govai_record:{record_id}",
                base_snapshot_hash=sha256_str(record_id),
            )
            merged.setdefault("audit", {})["execution_id"] = execution_id
        event_hash = append_event(
            self.jobs_db_path,
            execution_id=str(execution_id),
            plan_id=f"govai_record:{record_id}",
            step_index=max(int(merged.get("audit", {}).get("events") or 0), 0),
            action_type="record.update",
            status="passed",
            expected={"record_sha256": sha256_str(canonical_json(record))},
            observed={"record_sha256": sha256_str(canonical_json(merged))},
            actor_id=actor_id,
            justification="GovAI system record updated",
        )
        ok, n = verify_chain(self.jobs_db_path, str(execution_id))
        merged.setdefault("audit", {}).update({"last_event_hash": event_hash, "chain_ok": ok, "events": n})
        self._write_json(self._record_path(record_id), merged)
        return merged

    def add_evidence(self, record_id: str, body: Dict[str, Any], *, actor_id: str) -> Dict[str, Any]:
        record = self._get_record(record_id)
        evidence_id = self._next_id("FG-EVID-")
        now_ms = int(time.time() * 1000)
        evidence = {
            "type": "fieldgrade_evidence_object/1.0",
            "evidence_id": evidence_id,
            "title": str(body.get("title") or "Untitled evidence").strip(),
            "summary": str(body.get("summary") or "").strip(),
            "evidence_kind": str(body.get("evidence_kind") or "document").strip(),
            "stored_path": str(body.get("stored_path") or "").strip(),
            "url": str(body.get("url") or "").strip(),
            "claim_ids": body.get("claim_ids") if isinstance(body.get("claim_ids"), list) else [],
            "source": {
                "type": "fieldgrade_source_object/1.0",
                "source_id": self._next_id("FG-SRC-"),
                "source_type": str(body.get("source_type") or "primary").strip(),
                "supplied_by": str(body.get("supplied_by") or actor_id).strip(),
                "captured_at_ms": now_ms,
                "confidence": str(body.get("confidence") or "high").strip(),
            },
            "captured_at_ms": now_ms,
            "captured_by": actor_id,
        }
        items = record.get("evidence") if isinstance(record.get("evidence"), list) else []
        items.append(evidence)
        record["evidence"] = items
        return self.update_system(record_id, {"evidence": items}, actor_id=actor_id)

    def add_risk(self, record_id: str, body: Dict[str, Any], *, actor_id: str) -> Dict[str, Any]:
        record = self._get_record(record_id)
        risks = record.get("risks") if isinstance(record.get("risks"), list) else []
        risks.append(
            {
                "type": "fieldgrade_risk_object/1.0",
                "risk_id": self._next_id("FG-RISK-"),
                "title": str(body.get("title") or "Untitled risk").strip(),
                "severity": str(body.get("severity") or "Medium").strip(),
                "likelihood": str(body.get("likelihood") or "Medium").strip(),
                "affected_groups": body.get("affected_groups") if isinstance(body.get("affected_groups"), list) else [],
                "mitigations": body.get("mitigations") if isinstance(body.get("mitigations"), list) else [],
                "residual_risk": str(body.get("residual_risk") or "").strip(),
                "review_status": normalize_risk_status(body.get("review_status")),
            }
        )
        return self.update_system(record_id, {"risks": risks}, actor_id=actor_id)

    def add_control(self, record_id: str, body: Dict[str, Any], *, actor_id: str) -> Dict[str, Any]:
        record = self._get_record(record_id)
        controls = record.get("controls") if isinstance(record.get("controls"), list) else []
        controls.append(
            {
                "type": "fieldgrade_control_object/1.0",
                "control_id": self._next_id("FG-CTRL-"),
                "title": str(body.get("title") or "Untitled control").strip(),
                "control_kind": str(body.get("control_kind") or "governance").strip(),
                "status": normalize_control_status(body.get("status")),
                "owner": str(body.get("owner") or "").strip(),
            }
        )
        return self.update_system(record_id, {"controls": controls}, actor_id=actor_id)

    def add_review_gate(self, record_id: str, body: Dict[str, Any], *, actor_id: str) -> Dict[str, Any]:
        record = self._get_record(record_id)
        review_gates = record.get("review_gates") if isinstance(record.get("review_gates"), list) else []
        review_gates.append(
            {
                "type": "fieldgrade_review_gate/1.0",
                "review_gate_id": self._next_id("FG-GATE-"),
                "stage": str(body.get("stage") or "proposed").strip(),
                "status": normalize_review_gate_status(body.get("status")),
                "owner": str(body.get("owner") or "").strip(),
                "due_date": str(body.get("due_date") or "").strip(),
            }
        )
        return self.update_system(record_id, {"review_gates": review_gates}, actor_id=actor_id)

    def record_crosswalk(self, record_id: str) -> Dict[str, Any]:
        record = self.get_system(record_id)
        crosswalk = self._compute_crosswalks(record)
        record["crosswalks"] = crosswalk.get("templates", [])
        self._write_json(self._record_path(record_id), record)
        return crosswalk

    def generate_exports(self, record_id: str, *, actor_id: str) -> Dict[str, Any]:
        record = self.get_system(record_id)
        crosswalk = self._compute_crosswalks(record)
        record["crosswalks"] = crosswalk.get("templates", [])
        internal = record
        atrs = self._atrs_draft(record, crosswalk)
        public_summary = self._public_summary(record, crosswalk)
        gaps = {
            "type": "fieldgrade_export_pack/1.0",
            "export_kind": "EVIDENCE_GAP_REPORT",
            "record_id": record_id,
            "generated_at_ms": int(time.time() * 1000),
            "gap_count": crosswalk.get("gap_count", 0),
            "gaps": crosswalk.get("gaps", []),
        }
        exports = [
            self._write_export(record_id, EXPORT_KINDS[0], internal),
            self._write_export(record_id, EXPORT_KINDS[1], atrs),
            self._write_export(record_id, EXPORT_KINDS[2], public_summary),
            self._write_export(record_id, EXPORT_KINDS[3], gaps),
        ]
        record["export_status"] = {x["kind"]: True for x in exports}
        record["crosswalks"] = crosswalk.get("templates", [])
        execution_id = record.get("audit", {}).get("execution_id")
        if execution_id:
            event_hash = append_event(
                self.jobs_db_path,
                execution_id=str(execution_id),
                plan_id=f"govai_record:{record_id}",
                step_index=max(int(record.get("audit", {}).get("events") or 0), 0),
                action_type="export.generate",
                status="passed",
                observed={"exports": exports, "gap_count": crosswalk.get("gap_count", 0)},
                actor_id=actor_id,
                justification="GovAI export pack generated",
            )
            ok, n = verify_chain(self.jobs_db_path, str(execution_id))
            record.setdefault("audit", {}).update({"last_event_hash": event_hash, "chain_ok": ok, "events": n})
        self._write_json(self._record_path(record_id), record)
        return {"record": record, "exports": exports, "crosswalk": crosswalk}

    def system_advisory(self, record_id: str) -> Dict[str, Any]:
        record = self.get_system(record_id)
        crosswalk = self._compute_crosswalks(record)
        advisory = self._advisory(record, crosswalk)
        advisory["architecture_views"] = governance_state_views(record, advisory, crosswalk)
        return advisory

    def dashboard(self) -> Dict[str, Any]:
        systems = self.list_systems()
        by_status: Dict[str, int] = {}
        by_risk: Dict[str, int] = {}
        by_readiness: Dict[str, int] = {}
        by_review: Dict[str, int] = {}
        views = {
            "evidence": {},
            "review": {},
            "runtime_handoff": {},
            "export": {},
        }
        attention_queue: List[Dict[str, Any]] = []
        for item in systems:
            by_status[item.get("status") or "Unknown"] = by_status.get(item.get("status") or "Unknown", 0) + 1
            by_risk[item.get("risk_tier") or "Unknown"] = by_risk.get(item.get("risk_tier") or "Unknown", 0) + 1
            advisory = item.get("advisory") if isinstance(item.get("advisory"), dict) else {}
            readiness = str(advisory.get("readiness_status") or "attention_required")
            review = advisory.get("review") if isinstance(advisory.get("review"), dict) else {}
            review_state = str(review.get("state") or "unscheduled")
            by_readiness[readiness] = by_readiness.get(readiness, 0) + 1
            by_review[review_state] = by_review.get(review_state, 0) + 1
            item_views = item.get("architecture_views") if isinstance(item.get("architecture_views"), dict) else {}
            for view_name in views:
                state = str(item_views.get(view_name) or "unknown")
                bucket = views[view_name]
                bucket[state] = int(bucket.get(state) or 0) + 1
            if readiness != "export_ready":
                attention_queue.append(
                    {
                        "record_id": item.get("record_id"),
                        "title": item.get("title"),
                        "readiness_score": advisory.get("readiness_score"),
                        "readiness_status": readiness,
                        "review_state": review_state,
                        "architecture_views": item_views,
                        "actions": advisory.get("prioritized_actions", [])[:2],
                    }
                )
        attention_queue.sort(
            key=lambda entry: (
                self._priority_rank(str(((entry.get("actions") or [{}])[0]).get("priority") or "low")),
                int(entry.get("readiness_score") or 0),
                str(entry.get("title") or ""),
            )
        )
        return {
            "organizations": self.list_organizations(),
            "systems": systems,
            "counts": {
                "organizations": len(self.list_organizations()),
                "systems": len(systems),
                "by_status": by_status,
                "by_risk_tier": by_risk,
                "by_readiness": by_readiness,
                "by_review_state": by_review,
            },
            "views": {name: {"by_state": bucket} for name, bucket in views.items()},
            "attention_queue": attention_queue,
        }

    def audit_events(self, record_id: str) -> List[Dict[str, Any]]:
        record = self._get_record(record_id)
        execution_id = record.get("audit", {}).get("execution_id")
        if not execution_id:
            return []
        return [
            {
                "id": ev.id,
                "action_type": ev.action_type,
                "status": ev.status,
                "actor_id": ev.actor_id,
                "ts_ms": ev.ts_ms,
                "event_hash": ev.event_hash,
                "prev_hash": ev.prev_hash,
                "justification": ev.justification,
            }
            for ev in iter_events(self.jobs_db_path, str(execution_id))
        ]
