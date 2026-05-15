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
    monkeypatch.setenv("FG_MITE_DB", str(tmp_path / "mite.sqlite"))
    monkeypatch.setenv("FG_TERMITE_ARTIFACTS_DIR", str(tmp_path / "termite_artifacts"))
    monkeypatch.setenv("FG_TENANTS_ROOT", str(tmp_path / "tenants"))
    monkeypatch.setenv("FG_UI_RUNTIME_DIR", str(tmp_path / "ui_runtime"))

    import fieldgrade_ui.app as app_mod

    importlib.reload(app_mod)
    return TestClient(app_mod.app)  # type: ignore[attr-defined]


def test_architecture_overview_endpoint_exposes_layer_and_status_contracts(client: TestClient) -> None:
    r = client.get("/api/architecture/overview", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema_version"] == "fieldgrade.architecture_overview.v1"
    assert [layer["layer_id"] for layer in body["layers"]] == [
        "termite_fieldpack",
        "mite_ecology",
        "fieldgrade_ui",
    ]
    assert "captured" in body["status_vocabulary"]["evidence"]
    assert "approved" in body["status_vocabulary"]["review_decision"]
    assert body["planes"]["control_plane"]["plane"] == "control_plane"
    assert body["planes"]["data_plane"]["plane"] == "data_plane"
    assert "schemas/fieldgrade_evidence_packet_v1.json" in body["bridge_contracts"]["schemas"]

