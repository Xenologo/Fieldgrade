from __future__ import annotations

import importlib.util
import sys
from dataclasses import fields
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_readiness_score_uses_result_categories() -> None:
    module = _load_script_module("check_proposal_readiness", "scripts/check_proposal_readiness.py")

    result = module.Result(missing_files=["docs/proposal/FIELDGRADE_READINESS_AUDIT.md"])
    total_categories = len(fields(module.Result))
    expected = round(((total_categories - 1) / total_categories) * 100)

    assert result.categories() == tuple(field.name for field in fields(module.Result))
    assert module.readiness_score(result) == expected


def test_local_setup_regex_requires_specific_headings() -> None:
    module = _load_script_module("check_proposal_readiness", "scripts/check_proposal_readiness.py")

    assert module.LOCAL_SETUP_RE.search("## Canonical dev setup (recommended)")
    assert module.LOCAL_SETUP_RE.search("### Pilot release install mode")
    assert module.LOCAL_SETUP_RE.search("### Development mode")
    assert module.LOCAL_SETUP_RE.search("We offer setup support during onboarding.") is None


def test_required_proposal_files_include_post_tranche_submission_pack() -> None:
    module = _load_script_module("check_proposal_readiness", "scripts/check_proposal_readiness.py")

    assert {
        "docs/proposal/FIELDGRADE_SUBMISSION_CHECKLIST.md",
        "docs/proposal/FIELDGRADE_REVIEWER_WALKTHROUGH.md",
        "docs/proposal/FIELDGRADE_SCREENSHOT_CAPTURE_PLAN.md",
        "docs/proposal/FIELDGRADE_SMOKE_TEST_EVIDENCE.md",
        "docs/proposal/FIELDGRADE_RELEASE_PUBLICATION_PLAN.md",
        "docs/proposal/FIELDGRADE_PILOT_DATA_REPLACEMENT_PROTOCOL.md",
    }.issubset(set(module.REQUIRED_PROPOSAL_FILES))


def test_check_files_flags_missing_post_tranche_doc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_script_module("check_proposal_readiness", "scripts/check_proposal_readiness.py")
    target = "docs/proposal/FIELDGRADE_REVIEWER_WALKTHROUGH.md"

    for rel in module.REQUIRED_PROPOSAL_FILES + module.REQUIRED_DEMO_FILES:
        if rel == target:
            continue
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]\n" if path.suffix == ".json" else "placeholder-free content\n", encoding="utf-8")

    monkeypatch.setattr(module, "ROOT", tmp_path)
    result = module.Result()
    module.check_files(result)

    assert result.missing_files == [target]


def test_validate_wrapper_uses_checked_subprocess(monkeypatch) -> None:
    module = _load_script_module("validate_fieldgrade_pack", "scripts/validate_fieldgrade_pack.py")
    recorded: dict[str, object] = {}

    def fake_run(command, cwd, check):
        recorded["command"] = command
        recorded["cwd"] = cwd
        recorded["check"] = check

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main() == 0
    assert recorded["command"] == [module.sys.executable, str(module.ROOT / "scripts" / "check_proposal_readiness.py")]
    assert recorded["cwd"] == module.ROOT
    assert recorded["check"] is True
