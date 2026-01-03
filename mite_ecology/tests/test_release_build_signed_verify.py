from __future__ import annotations

import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mite_ecology.release import build_release, verify_release_zip, release_zip_sha256


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_ed25519_keypair(priv_path: Path, pub_path: Path) -> None:
    # Deterministic test key: RFC8032-style private bytes.
    priv = Ed25519PrivateKey.from_private_bytes(b"\x11" * 32)
    pub = priv.public_key()

    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_bytes)
    pub_path.write_bytes(pub_bytes)


def test_release_build_signed_is_deterministic_and_verifiable(tmp_path: Path) -> None:
    comps = tmp_path / "components.yaml"
    vars_ = tmp_path / "variants.yaml"
    rems = tmp_path / "remotes.yaml"

    _write(
        comps,
        "\n".join(
            [
                "type: registry_components/1.0",
                "version: '1.0'",
                "components:",
                "  - component_id: demo_component",
            ]
        )
        + "\n",
    )

    _write(
        vars_,
        "\n".join(
            [
                "type: registry_variants/1.0",
                "version: '1.0'",
                "variants:",
                "  - variant_id: demo_variant",
            ]
        )
        + "\n",
    )

    _write(
        rems,
        "\n".join(
            [
                "type: registry_remotes/1.0",
                "version: '1.0'",
                "remotes: []",
            ]
        )
        + "\n",
    )

    keys_dir = tmp_path / "keys"
    priv = keys_dir / "ed25519_priv.pem"
    pub = keys_dir / "ed25519_pub.pem"
    _write_ed25519_keypair(priv, pub)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    r1 = build_release(
        out_dir=out1,
        components_path=comps,
        variants_path=vars_,
        remotes_path=rems,
        include_cyclonedx=True,
        include_dsse=True,
        signing_private_key_path=priv,
        signing_public_key_path=pub,
    )

    time.sleep(1.1)

    r2 = build_release(
        out_dir=out2,
        components_path=comps,
        variants_path=vars_,
        remotes_path=rems,
        include_cyclonedx=True,
        include_dsse=True,
        signing_private_key_path=priv,
        signing_public_key_path=pub,
    )

    assert r1.release_id == r2.release_id
    assert release_zip_sha256(r1.zip_path) == release_zip_sha256(r2.zip_path)

    rep = verify_release_zip(
        zip_path=r1.zip_path,
        signing_public_key_path=pub,
        require_dsse=True,
        require_cyclonedx=True,
    )
    assert rep["ok"] is True
    assert rep["dsse_ok"] is True
    assert rep["sbom_dsse_ok"] is True
