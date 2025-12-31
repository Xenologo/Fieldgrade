from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_termite_to_ecology_acceptance_path(tmp_path: Path):
    """End-to-end smoke: build a signed Termite bundle -> verify + accept into mite_ecology.

    This exercises:
      - Termite bundle creation (deterministic, signed)
      - Termite verification hardening paths
      - mite_ecology acceptance + kg_deltas chain hash recording
      - deterministic replay verification
    """

    # Make termite_fieldpack importable (monorepo-style test run)
    sys.path.insert(0, str(_repo_root() / "termite_fieldpack"))

    # termite imports
    from termite.cas import CAS
    from termite.db import connect as t_connect, init_db as t_init_db
    from termite.bundle import SealInputs, build_bundle
    from termite.policy import load_policy, canonical_hash_dict
    from termite.tools import load_allowlist
    from termite.provenance import utc_now_iso
    from termite.signing import load_or_create

    # mite_ecology imports
    from mite_ecology.db import connect as e_connect, init_db as e_init_db
    from mite_ecology.bundle_accept import accept_termite_bundle, AcceptPolicy
    from mite_ecology.replay import replay_verify

    # ------------------------
    # Create test policy + allowlist
    # ------------------------
    policy_path = tmp_path / "policy.yaml"
    allowlist_path = tmp_path / "allowlist.yaml"
    keys_dir = tmp_path / "keys"
    priv_path = keys_dir / "test_priv.pem"
    pub_path = keys_dir / "test_pub.pem"

    # Ensure keys exist for allowlist
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

    pol = load_policy(policy_path)
    allow = load_allowlist(allowlist_path)
    allow_for_hash = {k: v for k, v in allow.items() if k != "_base_dir"}

    # ------------------------
    # Build a minimal termite bundle
    # ------------------------
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
    for op in ops:
        op_json = json.dumps(op, separators=(",", ":"), sort_keys=True)
        # Termite op_hash isn't re-verified by mite_ecology; it's used for internal provenance.
        # Keep deterministic hashing anyway.
        import hashlib

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
    bundle_path = build_bundle(inp, label="it")

    # ------------------------
    # Accept into mite_ecology
    # ------------------------
    e_dir = tmp_path / "ecology"
    e_db = e_dir / "ecology.sqlite"
    e_con = e_connect(e_db)
    e_init_db(e_con, _repo_root() / "mite_ecology" / "sql" / "schema.sql")
    e_con.close()

    res = accept_termite_bundle(
        e_db,
        bundle_path,
        policy_path,
        allowlist_path,
        accept_policy=AcceptPolicy(),
        override_mode="AUTO_MERGE",
        actor="test",
    )
    assert res["policy_mode"] == "AUTO_MERGE"
    assert res["status"] == "MERGED"
    assert int(res["ops_count"]) == len(ops)

    # KG and deltas exist and replay is consistent
    rv = replay_verify(e_db)
    assert rv["kg_deltas_chain_ok"] is True
    assert rv["ingested_chain_ok"] is True
    assert rv["match"] is True
    assert int(rv["deltas_count"]) >= 1
