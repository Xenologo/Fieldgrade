from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_a5_inprocess_pipeline_runner_smoke(tmp_path: Path):
    """A5 boundary hardening: run the UI pipeline in-process (no subprocess).

    Uses temporary configs + runtime dirs so the test is hermetic.
    """

    # Ensure termite_fieldpack is importable (monorepo-style)
    sys.path.insert(0, str(_repo_root() / "termite_fieldpack"))

    from fieldgrade_ui.internal_pipeline import run_termite_to_ecology_pipeline_library

    from termite.cas import CAS
    from termite.db import connect as t_connect, init_db as t_init_db
    from termite.signing import load_or_create

    repo = _repo_root()

    # ------------------------
    # Build hermetic termite runtime + config
    # ------------------------
    t_root = tmp_path / "termite"
    t_runtime = t_root / "runtime"
    t_cas_root = t_runtime / "cas"
    t_db = t_runtime / "termite.sqlite"
    t_bundles_out = t_root / "artifacts" / "bundles_out"
    t_keys = t_runtime / "keys"
    priv = t_keys / "toolchain_ed25519.pem"
    pub = t_keys / "toolchain_ed25519.pub"

    t_keys.mkdir(parents=True, exist_ok=True)
    load_or_create(priv, pub)

    # termite schema
    cas = CAS(t_cas_root)
    cas.init()
    con = t_connect(t_db)
    t_init_db(con, repo / "termite_fieldpack" / "sql" / "schema.sql")
    con.close()

    # policy + allowlist
    policy_path = t_root / "meap.yaml"
    allowlist_path = t_root / "allowlist.yaml"
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
                "require_dsse_attestations": True,
                "require_cyclonedx_sbom": True,
            },
            "protected_paths": [],
        }
    }
    policy_path.write_text(yaml.safe_dump(policy_obj, sort_keys=True), encoding="utf-8")

    allowlist_obj = {
        "allowlist": {
            "toolchain_ids": [
                {
                    "id": "TEST_TOOLCHAIN",
                    "pubkey_path": str(pub),
                }
            ]
        }
    }
    allowlist_path.write_text(yaml.safe_dump(allowlist_obj, sort_keys=True), encoding="utf-8")

    termite_cfg_path = t_root / "termite.yaml"
    termite_cfg = {
        "termite": {
            "runtime_root": str(t_runtime),
            "cas_root": str(t_cas_root),
            "db_path": str(t_db),
            "bundles_out": str(t_bundles_out),
            "policy_path": str(policy_path),
            "allowlist_path": str(allowlist_path),
            "offline_mode": True,
            "network_policy": "deny_by_default",
        },
        "toolchain": {
            "toolchain_id": "TEST_TOOLCHAIN",
            "signing": {
                "enabled": True,
                "algorithm": "ed25519",
                "private_key_path": str(priv),
                "public_key_path": str(pub),
            },
        },
        "ingest": {
            "max_bytes": 5_000_000,
            "extract_text": True,
            "chunking": {"chunk_chars": 200, "overlap_chars": 20, "min_chunk_chars": 50},
        },
        "seal": {
            "include_raw_blobs": True,
            "include_extracted_blobs": True,
            "include_aux": True,
            "include_provenance": True,
            "include_sbom": True,
            "include_kg_delta": True,
            "deterministic_zip": True,
        },
    }
    termite_cfg_path.write_text(yaml.safe_dump(termite_cfg, sort_keys=True), encoding="utf-8")

    # A tiny upload
    upload = tmp_path / "upload.txt"
    upload.write_text("hello world\n", encoding="utf-8")

    # ------------------------
    # Build hermetic ecology runtime + config
    # ------------------------
    e_root = tmp_path / "ecology"
    e_root.mkdir(parents=True, exist_ok=True)
    e_runtime = e_root / "runtime"
    e_db = e_runtime / "mite_ecology.sqlite"
    e_imports = e_runtime / "imports"
    e_exports = e_root / "artifacts" / "export"

    ecology_cfg_path = e_root / "ecology.yaml"
    ecology_cfg = {
        "mite_ecology": {
            "runtime_root": str(e_runtime),
            "db_path": str(e_db),
            "imports_root": str(e_imports),
            "exports_root": str(e_exports),
            "policy_path": str(policy_path),
            "allowlist_path": str(allowlist_path),
            "schemas_dir": str(repo / "schemas"),
            "max_bundle_ops": 200_000,
        },
        "embedding": {"hops": 2, "feature_dim": 16, "normalize": True},
        "gat": {"alpha": 0.2, "top_edges": 16},
        "memoga": {"population": 12, "generations": 6, "elite_k": 3, "mutation_rate": 0.3, "crossover_rate": 0.5, "max_nodes_per_genome": 24, "max_edges_per_genome": 40},
        "accept": {"max_new_nodes": 2000, "max_new_edges": 10000},
    }
    ecology_cfg_path.write_text(yaml.safe_dump(ecology_cfg, sort_keys=True), encoding="utf-8")

    res = run_termite_to_ecology_pipeline_library(
        repo,
        upload_path=upload,
        label="a5",
        termite_config_path=termite_cfg_path,
        ecology_config_path=ecology_cfg_path,
    )

    assert res["verify"]["ok"] is True
    assert res["replay_verify"]["match"] is True
    assert Path(res["bundle_path"]).exists()
