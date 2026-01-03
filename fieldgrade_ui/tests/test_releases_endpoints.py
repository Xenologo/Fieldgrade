from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from termite.signing import generate_keypair, save_keypair


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

    import fieldgrade_ui.app as app_mod

    importlib.reload(app_mod)
    return TestClient(app_mod.app)  # type: ignore[attr-defined]


def test_release_build_and_list(client: TestClient) -> None:
    r = client.post("/api/releases/build", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["release_id"]
    assert body["zip_path"].endswith(body["release_id"] + ".zip")
    assert body["zip_sha256"]

    r = client.get("/api/releases", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    items = r.json()["releases"]
    assert any(x["release_id"] == body["release_id"] for x in items)


def test_release_verify_default_ok(client: TestClient) -> None:
    r = client.post("/api/releases/build", headers=_h("token_a"))
    assert r.status_code == 200, r.text
    built = r.json()

    r = client.post(
        "/api/releases/verify",
        headers=_h("token_a"),
        json={"zip_path": built["zip_path"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["zip_sha256"]


def test_release_build_cyclonedx_and_verify_required(client: TestClient) -> None:
    r = client.post(
        "/api/releases/build",
        headers=_h("token_a"),
        json={"include_cyclonedx": True},
    )
    assert r.status_code == 200, r.text
    built = r.json()

    r = client.post(
        "/api/releases/verify",
        headers=_h("token_a"),
        json={"zip_path": built["zip_path"], "require_cyclonedx": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_release_build_dsse_and_verify_required(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Allow test-owned key material to be passed through the API sandbox.
    monkeypatch.setenv("FG_API_EXTRA_ROOTS", str(tmp_path))

    pub = tmp_path / "keys" / "test.pub.pem"
    priv = tmp_path / "keys" / "test.priv.pem"
    kp = generate_keypair()
    save_keypair(kp, priv_path=priv, pub_path=pub)

    r = client.post(
        "/api/releases/build",
        headers=_h("token_a"),
        json={
            "include_dsse": True,
            "include_cyclonedx": True,
            "signing_public_key_path": str(pub),
            "signing_private_key_path": str(priv),
        },
    )
    assert r.status_code == 200, r.text
    built = r.json()

    # Verifying a DSSE-signed release requires the public key.
    r = client.post(
        "/api/releases/verify",
        headers=_h("token_a"),
        json={
            "zip_path": built["zip_path"],
            "require_dsse": True,
            "require_cyclonedx": True,
            "signing_public_key_path": str(pub),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_release_verify_requires_pubkey_when_dsse_present(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FG_API_EXTRA_ROOTS", str(tmp_path))

    pub = tmp_path / "keys" / "test.pub.pem"
    priv = tmp_path / "keys" / "test.priv.pem"
    kp = generate_keypair()
    save_keypair(kp, priv_path=priv, pub_path=pub)

    r = client.post(
        "/api/releases/build",
        headers=_h("token_a"),
        json={
            "include_dsse": True,
            "signing_public_key_path": str(pub),
            "signing_private_key_path": str(priv),
        },
    )
    assert r.status_code == 200, r.text
    built = r.json()

    r = client.post(
        "/api/releases/verify",
        headers=_h("token_a"),
        json={"zip_path": built["zip_path"], "require_dsse": True},
    )
    assert r.status_code == 400, r.text
