from __future__ import annotations

import hashlib
import importlib
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _h(token: str) -> dict[str, str]:
    return {"X-API-Key": token}


def _owner_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FG_API_TOKENS", "token_a,token_b")

    # Isolated jobs DB per test.
    monkeypatch.setenv("FG_JOBS_DB", str(tmp_path / "jobs.sqlite"))

    # Keep termite artifacts out of the repo tree for tests.
    monkeypatch.setenv("FG_TERMITE_ARTIFACTS_DIR", str(tmp_path / "termite_artifacts"))

    # Tenant runtime root (mite_ecology DB + exports) isolated per test.
    monkeypatch.setenv("FG_TENANTS_ROOT", str(tmp_path / "tenants"))

    import fieldgrade_ui.app as app_mod

    importlib.reload(app_mod)
    return TestClient(app_mod.app)  # type: ignore[attr-defined]


def _ensure_graph_db(db_path: Path, *, node_id: str) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, type TEXT, attrs_json TEXT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS edges (id INTEGER PRIMARY KEY AUTOINCREMENT, src TEXT, dst TEXT, type TEXT, attrs_json TEXT)"
        )
        con.execute(
            "INSERT OR REPLACE INTO nodes(id, type, attrs_json) VALUES (?, ?, ?)",
            (node_id, "Task", "{}"),
        )
        con.commit()
    finally:
        con.close()


def test_exports_are_scoped_by_token(client: TestClient, tmp_path: Path) -> None:
    tenants = tmp_path / "tenants"

    a_owner = _owner_hash("token_a")
    b_owner = _owner_hash("token_b")

    a_exports = tenants / a_owner / "exports"
    b_exports = tenants / b_owner / "exports"
    a_exports.mkdir(parents=True, exist_ok=True)
    b_exports.mkdir(parents=True, exist_ok=True)

    (a_exports / "a.json").write_text("{}", encoding="utf-8")
    (b_exports / "b.json").write_text("{}", encoding="utf-8")

    r = client.get("/api/exports", headers=_h("token_a"))
    assert r.status_code == 200
    exports = r.json()["exports"]
    assert any(p.endswith("a.json") for p in exports)
    assert not any(p.endswith("b.json") for p in exports)

    r = client.get("/api/exports", headers=_h("token_b"))
    assert r.status_code == 200
    exports = r.json()["exports"]
    assert any(p.endswith("b.json") for p in exports)
    assert not any(p.endswith("a.json") for p in exports)


def test_graph_endpoints_use_token_scoped_db(client: TestClient, tmp_path: Path) -> None:
    tenants = tmp_path / "tenants"

    a_owner = _owner_hash("token_a")
    b_owner = _owner_hash("token_b")

    a_db = tenants / a_owner / "runtime" / "mite_ecology.sqlite"
    b_db = tenants / b_owner / "runtime" / "mite_ecology.sqlite"

    _ensure_graph_db(a_db, node_id="a1")
    _ensure_graph_db(b_db, node_id="b1")

    r = client.get("/api/graph/nodes", headers=_h("token_a"))
    assert r.status_code == 200
    ids = [n["id"] for n in r.json()["nodes"]]
    assert "a1" in ids
    assert "b1" not in ids

    r = client.get("/api/graph/nodes", headers=_h("token_b"))
    assert r.status_code == 200
    ids = [n["id"] for n in r.json()["nodes"]]
    assert "b1" in ids
    assert "a1" not in ids

    # Neighborhood lookup should not cross tenants.
    r = client.get("/api/graph/neighborhood", params={"node_id": "a1"}, headers=_h("token_b"))
    assert r.status_code == 404


def test_bundles_are_scoped_by_token_via_job_results(client: TestClient, tmp_path: Path) -> None:
    # Seed a fake bundle file under the test artifacts root, and register it via a succeeded job.
    bundles_dir = tmp_path / "termite_artifacts" / "bundles_out"
    bundles_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundles_dir / "demo.zip"
    bundle_path.write_bytes(b"PK\x03\x04")  # minimal zip signature prefix

    # Register bundle for token_a via jobs DB.
    from fieldgrade_ui.jobs import create_job, succeed_job

    owner = _owner_hash("token_a")
    job_id = create_job(
        tmp_path / "jobs.sqlite",
        "pipeline",
        {"label": "x"},
        owner_token_hash=owner,
    )
    succeed_job(tmp_path / "jobs.sqlite", job_id, {"bundle_path": str(bundle_path)})

    r = client.get("/api/bundles", headers=_h("token_a"))
    assert r.status_code == 200
    bundles = r.json()["bundles"]
    assert any(p.endswith("demo.zip") for p in bundles)

    r = client.get("/api/bundles", headers=_h("token_b"))
    assert r.status_code == 200
    bundles = r.json()["bundles"]
    assert not any(p.endswith("demo.zip") for p in bundles)
