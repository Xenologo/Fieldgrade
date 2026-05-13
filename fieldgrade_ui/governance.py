from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from mite_ecology.hashutil import canonical_json, sha256_str

from .execution_ledger import append_event, create_execution, ensure_db, iter_events, verify_chain


CORE_SCHEMA_NAME = "fieldgrade_core_objects_v1.json"
GOVAI_SCHEMA_NAME = "fieldgrade_govai_system_record_v1.json"
CROSSWALK_RESOURCE = "fieldgrade_govai_crosswalks_v1.json"


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
                "review_status": str(body.get("review_status") or "Open").strip(),
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
                "status": str(body.get("status") or "Planned").strip(),
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
                "status": str(body.get("status") or "pending").strip(),
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
            self._write_export(record_id, "internal_governance_record", internal),
            self._write_export(record_id, "atrs_draft", atrs),
            self._write_export(record_id, "public_summary", public_summary),
            self._write_export(record_id, "evidence_gap_report", gaps),
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

    def dashboard(self) -> Dict[str, Any]:
        systems = self.list_systems()
        by_status: Dict[str, int] = {}
        by_risk: Dict[str, int] = {}
        for item in systems:
            by_status[item.get("status") or "Unknown"] = by_status.get(item.get("status") or "Unknown", 0) + 1
            by_risk[item.get("risk_tier") or "Unknown"] = by_risk.get(item.get("risk_tier") or "Unknown", 0) + 1
        return {
            "organizations": self.list_organizations(),
            "systems": systems,
            "counts": {
                "organizations": len(self.list_organizations()),
                "systems": len(systems),
                "by_status": by_status,
                "by_risk_tier": by_risk,
            },
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
