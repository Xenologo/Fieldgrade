#!/usr/bin/env python3
"""Generate the synthetic Fieldgrade demo export manifest.

The script is intentionally dependency-free so proposal reviewers can run it in a
plain Python 3.10+ environment.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data" / "demo"
SOURCES = DEMO_DIR / "fieldgrade_demo_sources.json"
ANNOTATIONS = DEMO_DIR / "fieldgrade_demo_annotations.json"
AUDIT_TRAIL = DEMO_DIR / "fieldgrade_demo_audit_trail.json"
MANIFEST = DEMO_DIR / "fieldgrade_demo_export_manifest.json"
DEMO_FILES = [SOURCES, ANNOTATIONS, AUDIT_TRAIL]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    sources = load_json(SOURCES)
    annotations = load_json(ANNOTATIONS)
    audit_trail = load_json(AUDIT_TRAIL)

    annotations_by_object: dict[str, list[dict[str, Any]]] = {}
    for annotation in annotations:
        annotations_by_object.setdefault(annotation["object_id"], []).append(annotation)

    events_by_object: dict[str, list[dict[str, Any]]] = {}
    for event in audit_trail:
        events_by_object.setdefault(event["object_id"], []).append(event)

    objects: list[dict[str, Any]] = []
    for source in sources:
        object_id = source["object_id"]
        object_record = {
            "object_id": object_id,
            "title": source["title"],
            "source_type": source["source_type"],
            "provenance_note": source["provenance_note"],
            "ingestion_timestamp": source["ingestion_timestamp"],
            "claim_status": source["claim_status"],
            "admissibility_tier": source["admissibility_tier"],
            "review_state": source["review_state"],
            "evidence_status": source.get("evidence_status", "synthetic_demo"),
            "review_status": source.get("review_status", "unknown"),
            "annotation_count": len(annotations_by_object.get(object_id, [])),
            "audit_event_count": len(events_by_object.get(object_id, [])),
            "export_hash": canonical_hash(
                {
                    "source": source,
                    "annotations": annotations_by_object.get(object_id, []),
                    "audit_events": events_by_object.get(object_id, []),
                }
            ),
            "human_readable_explanation": source["human_readable_explanation"],
        }
        objects.append(object_record)

    manifest = {
        "manifest_id": "FG-DEMO-MANIFEST-2026-05-15",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "created_by": "scripts/generate_demo_manifest.py",
        "bundle_title": "Fieldgrade proposal-readiness synthetic evidence bundle",
        "bundle_scope": "Proposal-ready demonstrator for evidence-governed frontier-AI research workflows.",
        "synthetic_data_notice": (
            "All objects in this manifest are synthetic proposal-demo records and must not be represented "
            "as real benchmark, lab, or operational data."
        ),
        "objects": objects,
        "files": [
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in DEMO_FILES
        ],
    }

    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST.relative_to(ROOT)} with {len(objects)} objects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
