from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .contracts import compatible


@dataclass(frozen=True)
class ClutchScore:
    score_0_100: int
    reasons: List[str]
    details: Dict[str, Any]


def _score_schema_compat(stud_a: Dict[str, Any], stud_b: Dict[str, Any]) -> Tuple[float, List[str], Dict[str, Any]]:
    reasons: List[str] = []
    details: Dict[str, Any] = {}
    a_out = (stud_a.get("io") or {}).get("outputs") or []
    b_in = (stud_b.get("io") or {}).get("inputs") or []
    compat_pairs = 0
    total_pairs = 0
    for ao in a_out:
        if not isinstance(ao, dict):
            continue
        for bi in b_in:
            if not isinstance(bi, dict):
                continue
            total_pairs += 1
            sa = str(ao.get("schema") or "")
            sb = str(bi.get("schema") or "")
            if sa and sb and compatible(sa, sb):
                compat_pairs += 1
    if total_pairs == 0:
        return 0.5, ["no ports to compare (defaulting)"], {"pairs": 0, "compatible": 0}
    frac = compat_pairs / total_pairs
    reasons.append(f"{compat_pairs}/{total_pairs} port pairs are LDNA-major-compatible")
    details["pairs"] = total_pairs
    details["compatible"] = compat_pairs
    return frac, reasons, details


def _score_envelope(stud_a: Dict[str, Any], stud_b: Dict[str, Any], host: Optional[Dict[str, Any]]) -> Tuple[float, List[str], Dict[str, Any]]:
    reasons: List[str] = []
    details: Dict[str, Any] = {}
    host = host or {}
    host_ram = int(host.get("ram_mb") or 0)
    host_disk = int(host.get("disk_mb") or 0)

    def env(s: Dict[str, Any], key: str) -> int:
        c = s.get("constraints") or {}
        v = c.get(key)
        return int(v) if isinstance(v, int) else 0

    ram_need = max(env(stud_a, "max_ram_mb"), env(stud_b, "max_ram_mb"))
    disk_need = max(env(stud_a, "max_disk_mb"), env(stud_b, "max_disk_mb"))

    if host_ram and ram_need and ram_need > host_ram:
        reasons.append(f"RAM envelope exceeded: need {ram_need}MB > host {host_ram}MB")
        return 0.0, reasons, {"ram_need": ram_need, "host_ram": host_ram, "disk_need": disk_need, "host_disk": host_disk}
    if host_disk and disk_need and disk_need > host_disk:
        reasons.append(f"Disk envelope exceeded: need {disk_need}MB > host {host_disk}MB")
        return 0.0, reasons, {"ram_need": ram_need, "host_ram": host_ram, "disk_need": disk_need, "host_disk": host_disk}

    if host_ram == 0 and host_disk == 0:
        reasons.append("host caps unknown (neutral envelope score)")
        return 0.6, reasons, {"ram_need": ram_need, "disk_need": disk_need}

    reasons.append("resource envelope satisfied")
    return 1.0, reasons, {"ram_need": ram_need, "host_ram": host_ram, "disk_need": disk_need, "host_disk": host_disk}


def _score_determinism(stud_a: Dict[str, Any], stud_b: Dict[str, Any]) -> Tuple[float, List[str]]:
    det_a = str((stud_a.get("constraints") or {}).get("determinism") or "")
    det_b = str((stud_b.get("constraints") or {}).get("determinism") or "")
    order = {"strict": 3, "bounded": 2, "best_effort": 1}
    va = order.get(det_a, 1)
    vb = order.get(det_b, 1)
    v = min(va, vb) / 3.0
    return v, [f"determinism min({det_a},{det_b})"]


def compute_clutchscore(stud_a: Dict[str, Any], tube_a: Dict[str, Any], stud_b: Dict[str, Any], tube_b: Dict[str, Any], host_caps: Optional[Dict[str, Any]] = None) -> ClutchScore:
    reasons: List[str] = []
    details: Dict[str, Any] = {}

    s_schema, r_schema, d_schema = _score_schema_compat(stud_a, stud_b)
    reasons += r_schema
    details["schema"] = d_schema

    s_env, r_env, d_env = _score_envelope(stud_a, stud_b, host_caps)
    reasons += r_env
    details["envelope"] = d_env

    s_det, r_det = _score_determinism(stud_a, stud_b)
    reasons += r_det
    details["determinism"] = {"score": s_det}

    py_a = str((tube_a.get("runtime") or {}).get("python") or "")
    py_b = str((tube_b.get("runtime") or {}).get("python") or "")
    if py_a and py_b and py_a != py_b:
        reasons.append(f"python runtime constraints differ: {py_a} vs {py_b}")
        s_py = 0.7
    else:
        s_py = 1.0
        reasons.append("python runtime constraints compatible/unknown")
    details["runtime"] = {"python_a": py_a, "python_b": py_b}

    score = (0.45 * s_schema) + (0.25 * s_env) + (0.15 * s_det) + (0.15 * s_py)
    score_0_100 = max(0, min(100, int(round(score * 100))))
    return ClutchScore(score_0_100=score_0_100, reasons=reasons, details=details)
