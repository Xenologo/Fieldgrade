from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


# Make termite_fieldpack importable (monorepo-style test run)
sys.path.insert(0, str(_repo_root() / "termite_fieldpack"))


def _write_zip_variant(
    src_zip: Path,
    dst_zip: Path,
    *,
    replace: dict[str, bytes] | None = None,
    remove: set[str] | None = None,
) -> None:
    replace = replace or {}
    remove = remove or set()

    with zipfile.ZipFile(src_zip, "r") as zin:
        with zipfile.ZipFile(dst_zip, "w") as zout:
            for info in zin.infolist():
                name = info.filename
                if name in remove:
                    continue
                data = replace.get(name)
                if data is None:
                    data = zin.read(name)
                new_info = zipfile.ZipInfo(name)
                new_info.date_time = info.date_time
                new_info.compress_type = info.compress_type
                zout.writestr(new_info, data)


def _make_policy_and_allowlist(
    tmp_path: Path,
    *,
    require_dsse: bool,
    require_cdx: bool,
) -> tuple[Path, Path]:
    from termite.signing import load_or_create

    policy_path = tmp_path / "policy.yaml"
    allowlist_path = tmp_path / "allowlist.yaml"
    keys_dir = tmp_path / "keys"
    priv_path = keys_dir / "test_priv.pem"
    pub_path = keys_dir / "test_pub.pem"

    load_or_create(priv_path, pub_path)

    policy_obj = {
        "meap_v1": {
            "policy_id": "TEST_MEAP",
            "policy_version": 1,
            "mode": "AUTO_MERGE",
            "thresholds": {
                "max_bundle_mb": 25,
                "max_files_in_bundle": 200,
                "require_signature": True,
                "require_manifest_hashes": True,
                "require_deterministic_bundle_hash": True,
                "require_policy_hash_match": True,
                "require_allowlist_hash_match": True,
                "require_dsse_attestations": bool(require_dsse),
                "require_cyclonedx_sbom": bool(require_cdx),
            },
            "protected_paths": [],
        }
    }
    policy_path.write_text(yaml.safe_dump(policy_obj, sort_keys=True), encoding="utf-8")

    allowlist_obj = {
        "allowlist": {
            "toolchain_ids": [
                {
                    "id": "test_toolchain",
                    "pubkey_path": str(pub_path.relative_to(tmp_path)),
                }
            ]
        }
    }
    allowlist_path.write_text(yaml.safe_dump(allowlist_obj, sort_keys=True), encoding="utf-8")
    return policy_path, allowlist_path


def _build_minimal_signed_bundle(
    tmp_path: Path,
    *,
    require_dsse: bool,
    require_cdx: bool,
) -> tuple[Path, Path, Path]:
    from termite.cas import CAS
    from termite.db import connect as t_connect, init_db as t_init_db
    from termite.bundle import SealInputs, build_bundle
    from termite.policy import load_policy, canonical_hash_dict
    from termite.tools import load_allowlist
    from termite.provenance import utc_now_iso

    policy_path, allowlist_path = _make_policy_and_allowlist(
        tmp_path,
        require_dsse=require_dsse,
        require_cdx=require_cdx,
    )

    pol = load_policy(policy_path)
    allow = load_allowlist(allowlist_path)
    allow_for_hash = {k: v for k, v in allow.items() if k != "_base_dir"}

    keys_dir = tmp_path / "keys"
    priv_path = keys_dir / "test_priv.pem"
    pub_path = keys_dir / "test_pub.pem"

    t_dir = tmp_path / "termite"
    t_db = t_dir / "termite.sqlite"
    t_cas = CAS(t_dir / "cas")
    t_cas.init()

    t_con = t_connect(t_db)
    t_init_db(t_con, _repo_root() / "termite_fieldpack" / "sql" / "schema.sql")

    # Minimal delta: two nodes + one edge
    ops = [
        {"op": "ADD_NODE", "id": "task:1", "type": "Task", "attrs": {"title": "demo"}},
        {"op": "ADD_NODE", "id": "doc:1", "type": "Document", "attrs": {"name": "x"}},
        {"op": "ADD_EDGE", "src": "task:1", "dst": "doc:1", "rel": "REFERENCES", "attrs": {}},
    ]
    import hashlib

    for op in ops:
        op_json = json.dumps(op, separators=(",", ":"), sort_keys=True)
        op_hash = hashlib.sha256(op_json.encode("utf-8")).hexdigest()
        t_con.execute(
            "INSERT INTO kg_ops(ts_utc, op_json, op_hash) VALUES(?,?,?)",
            (utc_now_iso(), op_json, op_hash),
        )
    t_con.commit()

    inp = SealInputs(
        toolchain_id="test_toolchain",
        cas=t_cas,
        db_path=t_db,
        bundles_out=t_dir / "bundles",
        signing_priv=priv_path,
        signing_pub=pub_path,
        signing_enabled=True,
        deterministic_zip=True,
        policy_hash=pol.canonical_hash(),
        allowlist_hash=canonical_hash_dict(allow_for_hash),
    )
    bundle_path = build_bundle(inp, label="a4")
    return bundle_path, policy_path, allowlist_path


def test_a4_bundle_zip_immutable_through_verify_and_replay(tmp_path: Path):
    from termite.verify import verify_bundle
    from termite.replay import replay_bundle
    from termite.policy import load_policy
    from termite.tools import load_allowlist

    bundle_path, policy_path, allowlist_path = _build_minimal_signed_bundle(
        tmp_path,
        require_dsse=True,
        require_cdx=True,
    )
    policy = load_policy(policy_path)
    allowlist = load_allowlist(allowlist_path)

    before = bundle_path.read_bytes()

    vr = verify_bundle(bundle_path, policy=policy, allowlist=allowlist)
    assert vr.ok is True

    rr = replay_bundle(bundle_path, policy=policy, allowlist=allowlist)
    assert rr.ok is True

    after = bundle_path.read_bytes()
    assert before == after


def test_a4_strict_verification_fails_on_corrupted_signature(tmp_path: Path):
    from termite.verify import verify_bundle
    from termite.policy import load_policy
    from termite.tools import load_allowlist

    bundle_path, policy_path, allowlist_path = _build_minimal_signed_bundle(
        tmp_path,
        require_dsse=True,
        require_cdx=True,
    )
    policy = load_policy(policy_path)
    allowlist = load_allowlist(allowlist_path)

    bad_bundle = tmp_path / "bad_sig.zip"
    _write_zip_variant(
        bundle_path,
        bad_bundle,
        replace={"attestation.sig": b"NOT_BASE64\n"},
    )

    vr = verify_bundle(bad_bundle, policy=policy, allowlist=allowlist)
    assert vr.ok is False
    assert vr.reason == "bad_signature"


def test_a4_strict_verification_fails_on_tampered_dsse(tmp_path: Path):
    from termite.verify import verify_bundle
    from termite.policy import load_policy
    from termite.tools import load_allowlist

    bundle_path, policy_path, allowlist_path = _build_minimal_signed_bundle(
        tmp_path,
        require_dsse=True,
        require_cdx=False,
    )
    policy = load_policy(policy_path)
    allowlist = load_allowlist(allowlist_path)

    bad_bundle = tmp_path / "bad_dsse.zip"
    _write_zip_variant(
        bundle_path,
        bad_bundle,
        replace={"attestation.dsse.json": b"{not valid json\n"},
    )

    vr = verify_bundle(bad_bundle, policy=policy, allowlist=allowlist)
    assert vr.ok is False
    assert vr.reason.startswith("dsse_attestation_invalid:")


def test_a4_strict_verification_fails_when_cdx_required_but_missing(tmp_path: Path):
    from termite.verify import verify_bundle
    from termite.policy import load_policy
    from termite.tools import load_allowlist

    bundle_path, policy_path, allowlist_path = _build_minimal_signed_bundle(
        tmp_path,
        require_dsse=False,
        require_cdx=True,
    )
    policy = load_policy(policy_path)
    allowlist = load_allowlist(allowlist_path)

    bad_bundle = tmp_path / "missing_cdx.zip"
    _write_zip_variant(
        bundle_path,
        bad_bundle,
        remove={"sbom/bom.cdx.json"},
    )

    vr = verify_bundle(bad_bundle, policy=policy, allowlist=allowlist)
    assert vr.ok is False
    assert vr.reason == "missing_cyclonedx_sbom"
