from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _h(token: str) -> dict[str, str]:
    return {"X-API-Key": token}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FG_API_TOKENS", "token_a,token_b")
    monkeypatch.setenv("FG_JOBS_DB", str(tmp_path / "jobs.sqlite"))
    monkeypatch.setenv("FG_TERMITE_ARTIFACTS_DIR", str(tmp_path / "termite_artifacts"))
    monkeypatch.setenv("FG_TENANTS_ROOT", str(tmp_path / "tenants"))

    import fieldgrade_ui.app as app_mod

    importlib.reload(app_mod)
    return TestClient(app_mod.app)  # type: ignore[attr-defined]


def test_governance_govai_register_flow(client: TestClient) -> None:
    r = client.post(
        "/api/governance/organizations",
        headers=_h("token_a"),
        json={"name": "Example Borough Council", "sector": "UK public sector"},
    )
    assert r.status_code == 200, r.text
    org = r.json()["organization"]
    assert org["organization_id"].startswith("FG-ORG-")

    r = client.post(
        "/api/governance/systems",
        headers=_h("token_a"),
        json={
            "organization_id": org["organization_id"],
            "title": "Housing Arrears Prioritisation Tool",
            "status": "Under Review",
            "risk_tier": "High",
            "next_review_due": "2099-06-30",
        },
    )
    assert r.status_code == 200, r.text
    record = r.json()["record"]
    record_id = record["record_id"]
    assert record_id.startswith("FG-GOVAI-")
    assert record["audit"]["chain_ok"] is True

    r = client.get(f"/api/governance/systems/{record_id}/advisory", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    advisory = r.json()
    assert advisory["readiness_status"] == "attention_required"
    assert advisory["crosswalk"]["gap_count"] > 0
    assert any(action["action_id"] == "close-gap-atrs-ownership" for action in advisory["prioritized_actions"])

    r = client.put(
        f"/api/governance/systems/{record_id}",
        headers=_h("token_a"),
        json={
            "owners": {
                "senior_responsible_owner": "SRO Name",
                "data_owner": "Data Owner",
                "technical_owner": "Tech Owner",
                "supplier_owner": "Supplier Lead",
            },
            "purpose": {
                "plain_english_summary": "The tool helps prioritise cases for human review by housing officers.",
                "decision_context": "Operational prioritisation, not final decision-making.",
                "affected_groups": ["Council tenants", "Housing officers"],
            },
            "data": {
                "development_data_sources": [],
                "operational_data_sources": ["Housing arrears case data"],
                "lawful_basis": ["Public task"],
                "retention_period": "6 years",
                "data_quality_notes": "Source data quality reviewed monthly.",
            },
            "supplier": {
                "supplier_name": "Example Supplier Ltd",
                "model_documentation_status": "Model card and DPIA received",
                "hosting_location": "UK",
                "change_policy": "Supplier must disclose material model changes before deployment.",
                "contract_notes": "Responsible AI clauses included.",
            },
            "system": {
                "supplier": "Example Supplier Ltd",
                "model_type": "Machine learning classifier",
                "automation_level": "Decision support",
                "human_final_decision": True,
            },
            "human_oversight": {
                "oversight_model": "Housing officers review prioritised cases before action.",
                "human_reviewers": ["Housing officer"],
                "appeal_route": "Residents can challenge decisions through the housing complaints route.",
                "escalation_path": "Escalate to the service manager and DPO.",
            },
        },
    )
    assert r.status_code == 200, r.text

    for path, payload in (
        (f"/api/governance/systems/{record_id}/risks", {"title": "Bias against protected groups", "severity": "High", "likelihood": "Medium", "mitigations": ["Monthly fairness review"]}),
        (f"/api/governance/systems/{record_id}/controls", {"title": "Monthly human review sampling", "owner": "SRO Name"}),
        (f"/api/governance/systems/{record_id}/review_gates", {"stage": "assessed", "status": "approved", "owner": "SRO Name", "due_date": "2026-06-30"}),
        (f"/api/governance/systems/{record_id}/evidence", {"title": "Supplier model card", "summary": "Evidence from supplier due diligence.", "source_type": "primary", "stored_path": "/tmp/model-card.pdf"}),
    ):
        r = client.post(path, headers=_h("token_a"), json=payload)
        assert r.status_code == 200, r.text

    r = client.get(f"/api/governance/systems/{record_id}/crosswalk", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    crosswalk = r.json()
    assert crosswalk["gap_count"] == 0

    r = client.get(f"/api/governance/systems/{record_id}/advisory", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    advisory = r.json()
    assert advisory["readiness_status"] == "review_ready"
    assert advisory["crosswalk"]["gap_count"] == 0
    assert any(action["action_id"] == "generate-exports" for action in advisory["prioritized_actions"])

    r = client.post(f"/api/governance/systems/{record_id}/exports/generate", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["exports"]) == 4
    assert {x["kind"] for x in body["exports"]} == {
        "internal_governance_record",
        "atrs_draft",
        "public_summary",
        "evidence_gap_report",
    }

    r = client.get("/api/governance/dashboard", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    dash = r.json()
    assert dash["counts"]["organizations"] == 1
    assert dash["counts"]["systems"] == 1
    assert dash["counts"]["by_readiness"]["export_ready"] == 1
    assert dash["counts"]["by_review_state"]["scheduled"] == 1
    assert dash["attention_queue"] == []

    r = client.get(f"/api/governance/systems/{record_id}", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    fetched = r.json()
    assert fetched["record"]["export_status"]["public_summary"] is True
    assert fetched["record"]["audit"]["chain_ok"] is True
    assert len(fetched["audit_events"]) >= 6


def test_governance_dashboard_attention_queue_surfaces_overdue_work(client: TestClient) -> None:
    r = client.post(
        "/api/governance/organizations",
        headers=_h("token_a"),
        json={"name": "Example Food QA", "sector": "Food QA"},
    )
    assert r.status_code == 200, r.text
    org_id = r.json()["organization"]["organization_id"]

    r = client.post(
        "/api/governance/systems",
        headers=_h("token_a"),
        json={
            "organization_id": org_id,
            "title": "Batch release classifier",
            "status": "Under Review",
            "risk_tier": "High",
            "next_review_due": "2000-01-01",
        },
    )
    assert r.status_code == 200, r.text
    record_id = r.json()["record"]["record_id"]

    r = client.get(f"/api/governance/systems/{record_id}/advisory", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    advisory = r.json()
    assert advisory["review"]["state"] == "overdue"
    assert any(action["action_id"] == "renew-review" for action in advisory["prioritized_actions"])

    r = client.get("/api/governance/dashboard", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    dash = r.json()
    assert dash["counts"]["by_review_state"]["overdue"] == 1
    assert dash["attention_queue"][0]["record_id"] == record_id
