from __future__ import annotations
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .policy import MEAPPolicy
from .verify import verify_bundle

@dataclass
class ReplaySummary:
    ok: bool
    reason: str
    toolchain_id: str | None = None
    events: int = 0
    kg_ops: int = 0

def replay_bundle(bundle_path: Path, *, policy: MEAPPolicy, allowlist: Dict[str, Any]) -> ReplaySummary:
    vr = verify_bundle(bundle_path, policy=policy, allowlist=allowlist)
    if not vr.ok:
        return ReplaySummary(False, f"verify_failed:{vr.reason}", toolchain_id=vr.toolchain_id)

    # Conservative replay: structural checks only.
    p = Path(bundle_path).resolve()
    with zipfile.ZipFile(p, "r") as z:
        events = 0
        kg_ops = 0
        if "provenance.jsonl" in z.namelist():
            events = sum(1 for ln in z.read("provenance.jsonl").decode("utf-8").splitlines() if ln.strip())
        if "kg_delta.jsonl" in z.namelist():
            kg_ops = sum(1 for ln in z.read("kg_delta.jsonl").decode("utf-8").splitlines() if ln.strip())
        # No tool re-exec allowed unless policy says so (we do not implement re-exec in fieldpack)
        if not bool(policy.replay.get("allow_reexecute_tools", False)):
            return ReplaySummary(True, "ok_structural_only", toolchain_id=vr.toolchain_id, events=events, kg_ops=kg_ops)
        return ReplaySummary(True, "ok_reexec_disabled_in_impl", toolchain_id=vr.toolchain_id, events=events, kg_ops=kg_ops)


def _count_optional_tables(con):
    out = {}
    for t in ["llm_calls", "tool_runs"]:
        try:
            r = con.execute(f"SELECT COUNT(1) AS n FROM {t}").fetchone()
            out[t] = int(r["n"]) if r else 0
        except Exception:
            pass
    return out
