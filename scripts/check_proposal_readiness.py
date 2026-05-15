#!/usr/bin/env python3
"""Check Fieldgrade proposal-readiness artifacts."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PROPOSAL_FILES = [
    "docs/proposal/FIELDGRADE_READINESS_AUDIT.md",
    "docs/proposal/FIELDGRADE_PROPOSAL_NARRATIVE.md",
    "docs/proposal/FIELDGRADE_TECHNICAL_ARCHITECTURE.md",
    "docs/proposal/FIELDGRADE_DEMO_SCRIPT.md",
    "docs/proposal/FIELDGRADE_FUNDING_FIT_MATRIX.md",
    "docs/proposal/FIELDGRADE_SUBMISSION_MODES.md",
    "docs/proposal/FIELDGRADE_RISK_ETHICS_REGISTER.md",
    "docs/proposal/FIELDGRADE_DATA_GOVERNANCE.md",
    "docs/proposal/FIELDGRADE_12_WEEK_ROADMAP.md",
    "docs/proposal/FIELDGRADE_PARTNER_BRIEF.md",
    "docs/proposal/FIELDGRADE_ONE_PAGE_SUMMARY.md",
    "docs/proposal/README_PROPOSAL_PACK.md",
]
REQUIRED_DEMO_FILES = [
    "data/demo/fieldgrade_demo_sources.json",
    "data/demo/fieldgrade_demo_annotations.json",
    "data/demo/fieldgrade_demo_audit_trail.json",
    "data/demo/fieldgrade_demo_export_manifest.json",
    "outputs/proposal_pack/README.md",
]
JSON_DEMO_FILES = [path for path in REQUIRED_DEMO_FILES if path.endswith(".json")]
REQUIRED_OBJECT_FIELDS = {
    "object_id",
    "title",
    "source_type",
    "provenance_note",
    "ingestion_timestamp",
    "claim_status",
    "admissibility_tier",
    "review_state",
}
PLACEHOLDER_RE = re.compile(r"\b(TODO|FIXME|TBD)\b|lorem ipsum|\[insert\]", re.IGNORECASE)
LOCAL_SETUP_RE = re.compile(
    r"^#{2,}\s+.*(?:local setup|local demo|local run|local ui|development mode|canonical dev setup|pilot release install mode)\b",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class Result:
    missing_files: list[str] = field(default_factory=list)
    invalid_json_files: list[str] = field(default_factory=list)
    missing_object_fields: list[str] = field(default_factory=list)
    placeholder_findings: list[str] = field(default_factory=list)
    readme_findings: list[str] = field(default_factory=list)

    @classmethod
    def categories(cls) -> tuple[str, ...]:
        return tuple(item.name for item in fields(cls))

    def findings(self) -> dict[str, list[str]]:
        return {name: getattr(self, name) for name in self.categories()}

    @property
    def ok(self) -> bool:
        return not any(self.findings().values())


def load_json(path: Path, result: Result) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - produce reviewer-friendly diagnostics
        result.invalid_json_files.append(f"{path.relative_to(ROOT)}: {exc}")
        return None


def iter_manifest_objects(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        objects = payload.get("objects", [])
        if isinstance(objects, list):
            return [item for item in objects if isinstance(item, dict)]
    return []


def check_files(result: Result) -> None:
    for rel in REQUIRED_PROPOSAL_FILES + REQUIRED_DEMO_FILES:
        if not (ROOT / rel).is_file():
            result.missing_files.append(rel)


def check_json(result: Result) -> None:
    for rel in JSON_DEMO_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        payload = load_json(path, result)
        if payload is None:
            continue
        if rel.endswith("fieldgrade_demo_sources.json"):
            if not isinstance(payload, list):
                result.invalid_json_files.append(f"{rel}: expected a list of source objects")
                continue
            for index, item in enumerate(payload):
                if not isinstance(item, dict):
                    result.missing_object_fields.append(f"{rel}[{index}]: expected object")
                    continue
                missing = sorted(REQUIRED_OBJECT_FIELDS - set(item))
                if missing:
                    result.missing_object_fields.append(f"{rel}[{index}] {item.get('object_id', '<unknown>')}: {', '.join(missing)}")
        if rel.endswith("fieldgrade_demo_export_manifest.json"):
            for index, item in enumerate(iter_manifest_objects(payload)):
                missing = sorted(REQUIRED_OBJECT_FIELDS - set(item))
                if missing:
                    result.missing_object_fields.append(
                        f"{rel}.objects[{index}] {item.get('object_id', '<unknown>')}: {', '.join(missing)}"
                    )


def check_placeholders(result: Result) -> None:
    scan_files = [ROOT / rel for rel in REQUIRED_PROPOSAL_FILES]
    scan_files += [ROOT / rel for rel in REQUIRED_DEMO_FILES if rel.endswith((".md", ".json"))]
    for path in scan_files:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PLACEHOLDER_RE.search(line):
                result.placeholder_findings.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")


def check_readme(result: Result) -> None:
    readme = ROOT / "README.md"
    if not readme.exists():
        result.readme_findings.append("README.md is missing")
        return
    text = readme.read_text(encoding="utf-8")
    if not LOCAL_SETUP_RE.search(text):
        result.readme_findings.append("README.md does not contain a recognizable local setup/run section")


def readiness_score(result: Result) -> int:
    findings = result.findings()
    total_checks = len(findings)
    passed = total_checks - sum(bool(category) for category in findings.values())
    return round((passed / total_checks) * 100)


def print_list(title: str, values: list[str]) -> None:
    print(f"{title}:")
    if not values:
        print("  none")
    else:
        for value in values:
            print(f"  - {value}")


def main() -> int:
    result = Result()
    check_files(result)
    check_json(result)
    check_placeholders(result)
    check_readme(result)

    status = "PASS" if result.ok else "FAIL"
    print(f"Fieldgrade proposal readiness status: {status}")
    print(f"Readiness score: {readiness_score(result)}/100")
    print_list("Missing files", result.missing_files)
    print_list("Invalid JSON files", result.invalid_json_files)
    print_list("Missing demo object fields", result.missing_object_fields)
    print_list("Placeholder findings", result.placeholder_findings)
    print_list("README findings", result.readme_findings)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
