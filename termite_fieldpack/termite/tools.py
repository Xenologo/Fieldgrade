from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .cas import CAS
from .config import TermiteConfig
from .provenance import canonical_json, hash_str, utc_now_iso

def _hash_chain(prev_hash: Optional[str], payload: str) -> str:
    return hash_str((prev_hash or "") + "|" + payload)

def _latest_run_hash(con) -> Optional[str]:
    row = con.execute("SELECT run_hash FROM tool_runs ORDER BY id DESC LIMIT 1").fetchone()
    return None if row is None else str(row["run_hash"])

def load_allowlist(path: Path) -> Dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw["_base_dir"] = str(path.resolve().parent)
    return raw

def run_tool(cfg: TermiteConfig, tool_id: str, argv: List[str], allowlist_path: Path) -> Dict[str, Any]:
    """Run a whitelisted tool (no shell) and store stdout/stderr as CAS aux blobs, with provenance."""
    allow = load_allowlist(allowlist_path)
    tools = allow.get("tools") or {}
    if tool_id not in tools:
        raise RuntimeError(f"Tool not allowed: {tool_id}")
    spec = tools[tool_id]
    cmd = spec.get("cmd")
    if not isinstance(cmd, list) or not cmd:
        raise RuntimeError(f"Invalid allowlist cmd for tool {tool_id}")

    # Optional argument regex constraints
    arg_re = spec.get("arg_regex")
    if arg_re:
        import re
        rx = re.compile(str(arg_re))
        for a in argv:
            if not rx.match(a):
                raise RuntimeError(f"Arg rejected by allowlist regex: {a}")

    full = [str(x) for x in cmd] + [str(a) for a in argv]
    cwd = spec.get("cwd")
    if cwd:
        cwd = str(Path(allow["_base_dir"]) / str(cwd))

    ts = utc_now_iso()
    timeout_s_raw = (os.environ.get("TERMITE_TOOL_TIMEOUT_S") or os.environ.get("FG_CMD_TIMEOUT_S") or "600").strip()
    try:
        timeout_s = float(timeout_s_raw)
    except Exception:
        timeout_s = 600.0
    if timeout_s <= 0:
        timeout_s = None
    try:
        p = subprocess.run(full, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        class _P:
            returncode = 124
            stdout = e.stdout if isinstance(e.stdout, str) else ((e.stdout or b"").decode("utf-8", "replace"))
            stderr = e.stderr if isinstance(e.stderr, str) else ((e.stderr or b"").decode("utf-8", "replace"))
        p = _P()
        p.stderr = (p.stderr or "") + f"\n[timeout] command exceeded {timeout_s_raw}s"

    cas = CAS(cfg.cas_root); cas.init()
    con = cfg.db_con()

    stdout_sha = cas.put_aux((p.stdout or "").encode("utf-8")) if p.stdout is not None else None
    stderr_sha = cas.put_aux((p.stderr or "").encode("utf-8")) if p.stderr is not None else None

    prev = _latest_run_hash(con)
    payload = canonical_json({
        "ts_utc": ts,
        "tool_id": tool_id,
        "argv": full,
        "exit_code": int(p.returncode),
        "stdout_aux_sha256": stdout_sha,
        "stderr_aux_sha256": stderr_sha,
        "prev_hash": prev,
    })
    run_hash = _hash_chain(prev, payload)

    con.execute(
        "INSERT INTO tool_runs(ts_utc,tool_id,argv_json,exit_code,stdout_aux_sha256,stderr_aux_sha256,prev_hash,run_hash) VALUES(?,?,?,?,?,?,?,?)",
        (ts, tool_id, canonical_json(full), int(p.returncode), stdout_sha, stderr_sha, prev, run_hash),
    )
    # provenance event
    from .provenance import Provenance
    prov = Provenance(cfg.toolchain_id)
    prov.emit(con, "TOOL_RUN", {
        "tool_id": tool_id,
        "argv": full,
        "exit_code": int(p.returncode),
        "stdout_aux_sha256": stdout_sha,
        "stderr_aux_sha256": stderr_sha,
        "run_hash": run_hash,
    })
    con.commit()
    return {
        "tool_id": tool_id,
        "argv": full,
        "exit_code": int(p.returncode),
        "stdout_aux_sha256": stdout_sha,
        "stderr_aux_sha256": stderr_sha,
        "run_hash": run_hash,
    }
