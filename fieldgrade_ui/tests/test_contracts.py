from __future__ import annotations

import json
import zipfile
from pathlib import Path

from fieldgrade_ui.contracts import build_pipeline_contracts


def test_build_pipeline_contracts_emits_review_bound_bridge_objects(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bundle.zip"
    provenance = b'{"event":"one"}\n{"event":"two"}\n'
    kg_delta = b'{"op":"ADD_NODE","id":"n1"}\n'
    manifest = {
        "bundle_map_hash": "abc123",
        "kg_delta_hash": "f" * 64,
        "provenance_hash": "e" * 64,
    }
    with zipfile.ZipFile(bundle_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        zf.writestr("provenance.jsonl", provenance)
        zf.writestr("kg_delta.jsonl", kg_delta)
        zf.writestr("attestation.json", "{}")

    export_root = tmp_path / "exports"
    export_root.mkdir(parents=True, exist_ok=True)
    (export_root / "report.json").write_text("{}", encoding="utf-8")

    contracts = build_pipeline_contracts(
        repo_root=tmp_path,
        bundle_path=bundle_path,
        verify_result={"ok": True},
        replay_verify_result={"match": True, "kg_deltas_chain_ok": True, "ingested_chain_ok": True},
        run_id="run-123",
        export_root=export_root,
        bundle_store_info={"bundle_store": "local"},
    )

    assert contracts["bundle_acceptance"]["status"] == "exported"
    assert contracts["review_decision"]["status"] == "approved"
    assert contracts["runtime_hardening_report"]["invariant_status"] == "ok"
    assert contracts["fieldgrade_bridge"]["review_required"] is True
    assert contracts["cao_candidate"]["canonical_status"] == "not_canonical"
