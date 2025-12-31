from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# StudSpec / TubeSpec validators (v1)
#
# This is intentionally "jsonschema-lite" so Termite can validate on-device
# without heavyweight deps. The ecology can enforce stricter JSON Schema
# validation as part of acceptance.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SpecIssue:
    path: str
    message: str
    severity: str = "error"  # error|warn|info


_KIND_ENUM = {"frontend","backend","db","filler","evaluator","tool","pipeline"}
_DET_ENUM = {"strict","bounded","best_effort"}

# ldna://<media>/<name>@<semver>
_LDNA_RE = re.compile(r"^ldna://([a-z0-9+._-]+)/([a-zA-Z0-9._-]+)@([0-9]+\.[0-9]+\.[0-9]+)$")

# conservative: block whitespace + path separators in ids
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/\-]{3,256}$")


def parse_ldna_uri(s: str) -> Tuple[bool, Optional[Tuple[str,str,str]], Optional[str]]:
    if not isinstance(s, str) or not s:
        return False, None, "schema must be a non-empty string"
    if s.startswith("ldna://"):
        m = _LDNA_RE.match(s)
        if not m:
            return False, None, "invalid LDNA URI; expected ldna://<media>/<name>@<X.Y.Z>"
        return True, (m.group(1), m.group(2), m.group(3)), None
    # allow non-LDNA schema identifiers, but nudge toward LDNA
    return True, None, None


def _is_pos_int(x: Any) -> bool:
    return isinstance(x, int) and x >= 0


def validate_studspec(obj: Dict[str, Any]) -> List[SpecIssue]:
    issues: List[SpecIssue] = []
    if str(obj.get("studspec","")) != "1.0":
        issues.append(SpecIssue("/", "studspec must be '1.0'"))

    memite_id = obj.get("memite_id")
    if not isinstance(memite_id, str) or not memite_id or len(memite_id) < 3:
        issues.append(SpecIssue("/memite_id", "memite_id must be a non-empty string (len>=3)"))
    elif not _SAFE_ID_RE.match(memite_id) or (".." in memite_id) or ("//" in memite_id):
        issues.append(SpecIssue("/memite_id", "memite_id contains unsafe characters"))

    kind = obj.get("kind")
    if kind not in _KIND_ENUM:
        issues.append(SpecIssue("/kind", f"kind must be one of {sorted(_KIND_ENUM)}"))

    io = obj.get("io")
    if not isinstance(io, dict):
        issues.append(SpecIssue("/io", "io must be an object"))
    else:
        for port_list_name in ("inputs","outputs"):
            arr = io.get(port_list_name)
            if not isinstance(arr, list):
                issues.append(SpecIssue(f"/io/{port_list_name}", "must be an array"))
                continue
            if len(arr) == 0 and port_list_name == "outputs":
                issues.append(SpecIssue(f"/io/{port_list_name}", "outputs should not be empty", severity="warn"))
            for i, it in enumerate(arr):
                if not isinstance(it, dict):
                    issues.append(SpecIssue(f"/io/{port_list_name}/{i}", "port must be an object"))
                    continue
                if not isinstance(it.get("name"), str) or not it["name"]:
                    issues.append(SpecIssue(f"/io/{port_list_name}/{i}/name", "missing/empty"))
                sch = it.get("schema")
                ok, _, emsg = parse_ldna_uri(str(sch) if sch is not None else "")
                if not ok:
                    issues.append(SpecIssue(f"/io/{port_list_name}/{i}/schema", emsg or "invalid schema"))
                elif isinstance(sch, str) and sch and not sch.startswith("ldna://"):
                    issues.append(SpecIssue(f"/io/{port_list_name}/{i}/schema", "non-LDNA schema id; prefer ldna:// URIs", severity="warn"))

    cons = obj.get("constraints")
    if not isinstance(cons, dict):
        issues.append(SpecIssue("/constraints", "constraints must be an object"))
    else:
        det = cons.get("determinism")
        if det not in _DET_ENUM:
            issues.append(SpecIssue("/constraints/determinism", f"determinism must be one of {sorted(_DET_ENUM)}"))
        # envelope checks (optional)
        for k in ("max_ram_mb","max_disk_mb","max_latency_ms"):
            if k in cons and not _is_pos_int(cons.get(k)):
                issues.append(SpecIssue(f"/constraints/{k}", f"{k} must be a non-negative integer"))
        if "network" in cons and not isinstance(cons.get("network"), str):
            issues.append(SpecIssue("/constraints/network", "network must be a string (e.g., offline|lan|wan)"))

    return issues


def validate_tubespec(obj: Dict[str, Any]) -> List[SpecIssue]:
    issues: List[SpecIssue] = []
    if str(obj.get("tubespec","")) != "1.0":
        issues.append(SpecIssue("/", "tubespec must be '1.0'"))

    runtime = obj.get("runtime")
    if not isinstance(runtime, dict):
        issues.append(SpecIssue("/runtime", "runtime must be an object"))
    else:
        py = runtime.get("python")
        if not isinstance(py, str) or not py:
            issues.append(SpecIssue("/runtime/python", "runtime.python must be a non-empty string"))
        plat = runtime.get("platform")
        if plat is not None and not isinstance(plat, str):
            issues.append(SpecIssue("/runtime/platform", "runtime.platform must be a string"))
        # optional: cpu_arch, os, accelerator
        for k in ("cpu_arch","os","accelerator"):
            if k in runtime and runtime.get(k) is not None and not isinstance(runtime.get(k), str):
                issues.append(SpecIssue(f"/runtime/{k}", f"runtime.{k} must be a string"))

    deps = obj.get("deps")
    if deps is None:
        # allow empty deps
        pass
    elif not isinstance(deps, list):
        issues.append(SpecIssue("/deps", "deps must be an array"))
    else:
        for i, d in enumerate(deps):
            if not isinstance(d, str) or not d:
                issues.append(SpecIssue(f"/deps/{i}", "dep must be a non-empty string"))
            elif any(ch.isspace() for ch in d):
                issues.append(SpecIssue(f"/deps/{i}", "dep contains whitespace", severity="warn"))

    tools = obj.get("tools")
    if tools is not None and not isinstance(tools, list):
        issues.append(SpecIssue("/tools", "tools must be an array"))
    elif isinstance(tools, list):
        for i, t in enumerate(tools):
            if not isinstance(t, dict):
                issues.append(SpecIssue(f"/tools/{i}", "tool must be an object"))
                continue
            if not isinstance(t.get("id"), str) or not t["id"]:
                issues.append(SpecIssue(f"/tools/{i}/id", "missing/empty"))
            if "allowlist_key" in t and not isinstance(t.get("allowlist_key"), str):
                issues.append(SpecIssue(f"/tools/{i}/allowlist_key", "must be a string"))

    return issues
