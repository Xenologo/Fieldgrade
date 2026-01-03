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

    # Isolated jobs DB per test.
    monkeypatch.setenv("FG_JOBS_DB", str(tmp_path / "jobs.sqlite"))

    # Keep termite artifacts out of the repo tree for tests.
    monkeypatch.setenv("FG_TERMITE_ARTIFACTS_DIR", str(tmp_path / "termite_artifacts"))

    # Tenant runtime root isolated per test.
    monkeypatch.setenv("FG_TENANTS_ROOT", str(tmp_path / "tenants"))

    # UI runtime isolated per test (used by worker heartbeat path).
    monkeypatch.setenv("FG_UI_RUNTIME_DIR", str(tmp_path / "ui_runtime"))

    import fieldgrade_ui.app as app_mod

    importlib.reload(app_mod)
    return TestClient(app_mod.app)  # type: ignore[attr-defined]


def test_worker_status_endpoint_ok_shape(client: TestClient) -> None:
    r = client.get("/api/worker/status", headers=_h("token_a"))
    assert r.status_code == 200
    data = r.json()

    assert "ok" in data
    assert "reason" in data
    assert "heartbeat_path" in data
    assert "max_age_s" in data
