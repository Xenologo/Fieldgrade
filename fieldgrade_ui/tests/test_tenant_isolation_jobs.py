from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_and_upload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Two distinct principals (tenants) for BOLA-style isolation tests.
    monkeypatch.setenv("FG_API_TOKENS", "token_a,token_b")

    # Isolated DB per test.
    monkeypatch.setenv("FG_JOBS_DB", str(tmp_path / "jobs.sqlite"))

    # Allow the test upload path via sandbox extra roots.
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    upload_path = uploads / "demo.txt"
    upload_path.write_text("hello", encoding="utf-8")
    monkeypatch.setenv("FG_API_EXTRA_ROOTS", str(uploads))

    import fieldgrade_ui.app as app_mod

    # app.py reads env at import time; ensure a clean reload after env is set.
    importlib.reload(app_mod)

    return TestClient(app_mod.app), upload_path


def _h(token: str) -> dict[str, str]:
    return {"X-API-Key": token}


def test_jobs_are_scoped_by_api_token(client_and_upload):
    client, upload_path = client_and_upload

    # Tenant A creates a job.
    r = client.post(
        "/api/jobs/pipeline",
        headers=_h("token_a"),
        json={"upload_path": str(upload_path), "label": "a"},
    )
    assert r.status_code == 200, r.text
    job_id = int(r.json()["job_id"])

    # Tenant A can see it.
    r = client.get(f"/api/jobs/{job_id}", headers=_h("token_a"))
    assert r.status_code == 200, r.text

    # Tenant B cannot see it (404 to avoid existence oracle).
    r = client.get(f"/api/jobs/{job_id}", headers=_h("token_b"))
    assert r.status_code == 404, r.text

    # Tenant B cannot access logs.
    r = client.get(f"/api/jobs/{job_id}/logs", headers=_h("token_b"))
    assert r.status_code == 404, r.text

    # Tenant B cannot cancel it.
    r = client.post(f"/api/jobs/{job_id}/cancel", headers=_h("token_b"))
    assert r.status_code == 404, r.text

    # Lists are scoped too.
    r = client.get("/api/jobs", headers=_h("token_b"))
    assert r.status_code == 200, r.text
    assert r.json()["jobs"] == []


def test_invalid_token_is_rejected(client_and_upload):
    client, upload_path = client_and_upload

    r = client.post(
        "/api/jobs/pipeline",
        headers=_h("wrong"),
        json={"upload_path": str(upload_path), "label": "x"},
    )
    assert r.status_code == 401
