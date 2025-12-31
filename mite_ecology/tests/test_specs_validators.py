from __future__ import annotations

from mite_ecology.specs import validate_studspec, validate_tubespec


def test_valid_studspec():
    obj = {
        "studspec": "1.0",
        "memite_id": "NLP_TextSummarization::Summarizer::V1",
        "kind": "backend",
        "io": {"inputs": [{"name": "text", "schema": "ldna://text/plain@1.0"}], "outputs": [{"name": "summary", "schema": "ldna://text/plain@1.0"}]},
        "constraints": {"determinism": "bounded", "max_ram_mb": 512, "max_latency_ms": 1000},
        "deps": ["pypi:transformers@>=4.0.0"],
    }
    issues = validate_studspec(obj)
    assert issues == []


def test_invalid_studspec_missing_fields():
    obj = {"studspec": "1.0"}
    issues = validate_studspec(obj)
    assert len(issues) > 0


def test_valid_tubespec():
    obj = {"tubespec": "1.0", "runtime": {"python": ">=3.10", "os": "linux"}, "deps": ["PyYAML>=6.0"]}
    issues = validate_tubespec(obj)
    assert issues == []
