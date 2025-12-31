from __future__ import annotations

import base64
import json
import hashlib
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from termite.policy import MEAPPolicy, canonical_hash_dict
from termite.verify import verify_bundle, _calc_bundle_map_hash


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon_json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def make_bundle(tmp: Path, *, allowed_types, payload_name="payload/foo.py"):
    # keypair
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (tmp / "priv.pem").write_bytes(priv_pem)
    (tmp / "pub.pem").write_bytes(pub_pem)

    # policy + allowlist
    policy = MEAPPolicy({
        "meap_v1": {
            "version": "meap/1.0",
            "mode": "AUTO_MERGE",
            "limits": {"max_bytes": 5_000_000, "max_files": 50, "max_uncompressed_bytes": 5_000_000},
            "accept": {"protected_paths": [], "allowed_artifact_types": allowed_types},
            "replay": {},
            "kill_switch": {"enabled": False},
        }
    })
    allowlist = {
        "_base_dir": str(tmp),
        "allowlist": {
            "toolchain_ids": [
                {"id": "testtool", "pubkey_path": "pub.pem"},
            ]
        },
    }

    policy_hash = policy.canonical_hash()
    allow_hash = canonical_hash_dict(allowlist["allowlist"])

    payload_bytes = b"print('hi')\n"
    files_map = {payload_name: _sha256(payload_bytes)}

    # compute bundle_map_hash as in termite.verify
    bundle_map_hash = _calc_bundle_map_hash(files_map)

    manifest = {
        "bundle_version": "1.0",
        "created_utc": "2025-01-01T00:00:00Z",
        "policy_hash": policy_hash,
        "allowlist_hash": allow_hash,
        "toolchain_id": "testtool",
        "root": "payload",
        "files": files_map,
        "bundle_map_hash": bundle_map_hash,
    }
    manifest_bytes = _canon_json_bytes(manifest)
    manifest_hash = _sha256(manifest_bytes)

    att = {
        "attestation_version": "2",
        "toolchain_id": "testtool",
        "label": "test",
        "bundle_map_hash": bundle_map_hash,
        "manifest_hash": manifest_hash,
        "policy_hash": policy_hash,
        "allowlist_hash": allow_hash,
        "sbom_hash": None,
        "provenance_hash": None,
        "kg_delta_hash": None,
        "created_utc": "2025-01-01T00:00:00Z",
        "algo": "ed25519",
    }
    att_bytes = _canon_json_bytes(att)
    sig = priv.sign(att_bytes)

    bundle = tmp / "bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(payload_name, payload_bytes)
        z.writestr("manifest.json", manifest_bytes)
        z.writestr("attestation.json", att_bytes)
        z.writestr("attestation.sig", base64.b64encode(sig))
    return bundle, policy, allowlist


def test_meap_eval_denies_disallowed_artifact_type(tmp_path: Path):
    bundle, policy, allowlist = make_bundle(tmp_path, allowed_types=["bundle", "report"])
    res = verify_bundle(bundle, policy=policy, allowlist=allowlist)
    assert res.ok is False
    assert res.reason == "meap_eval_failed"


def test_meap_eval_allows_when_configured(tmp_path: Path):
    bundle, policy, allowlist = make_bundle(tmp_path, allowed_types=["bundle", "report", "code", "blob", "kg_delta", "sbom", "provenance", "onnx", "weights"])
    res = verify_bundle(bundle, policy=policy, allowlist=allowlist)
    assert res.ok is True
