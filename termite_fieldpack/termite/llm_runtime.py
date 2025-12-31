from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .config import TermiteConfig
from .db import connect
from .provenance import Provenance, utc_now_iso, hash_str


@dataclass(frozen=True)
class LLMRuntimeStatus:
    toolchain_id: str
    provider: str
    base_url: str
    model: str
    pid: Optional[int]
    managed: bool
    running: bool
    started_utc: Optional[str]
    state_path: str
    endpoint_id: str


def _llm_dir(cfg: TermiteConfig) -> Path:
    return (cfg.runtime_root / "llm").resolve()


def _state_path(cfg: TermiteConfig) -> Path:
    return _llm_dir(cfg) / "active_endpoint.json"


def _pid_path(cfg: TermiteConfig) -> Path:
    return _llm_dir(cfg) / "server.pid"


def _log_path(cfg: TermiteConfig) -> Path:
    return _llm_dir(cfg) / "server.log"


def _is_loopback(base_url: str) -> bool:
    u = base_url.strip().lower()
    # allow common loopback names
    return ("127.0.0.1" in u) or ("localhost" in u) or ("[::1]" in u)


def _read_cfg_llm(raw: Dict[str, Any]) -> Dict[str, Any]:
    return (raw.get("llm") or {})


def _effective_base_url(cfg: TermiteConfig) -> str:
    llm = _read_cfg_llm(cfg.raw)
    return str(llm.get("endpoint_base_url") or llm.get("base_url") or "http://127.0.0.1:8000")


def _effective_model(cfg: TermiteConfig) -> str:
    llm = _read_cfg_llm(cfg.raw)
    return str(llm.get("model") or "qwen2.5-coder-0.5b-instruct")


def _effective_provider(cfg: TermiteConfig) -> str:
    llm = _read_cfg_llm(cfg.raw)
    return str(llm.get("provider") or "endpoint_only")


def _ping_path(cfg: TermiteConfig) -> str:
    llm = _read_cfg_llm(cfg.raw)
    ping = llm.get("ping") or {}
    return str(ping.get("path") or "/v1/models")


def _ping_timeout(cfg: TermiteConfig) -> float:
    llm = _read_cfg_llm(cfg.raw)
    ping = llm.get("ping") or {}
    return float(ping.get("timeout_s") or 3.0)


def _launch_cfg(cfg: TermiteConfig) -> Dict[str, Any]:
    llm = _read_cfg_llm(cfg.raw)
    return (llm.get("launch") or {})


def _startup_timeout(cfg: TermiteConfig) -> float:
    lc = _launch_cfg(cfg)
    return float(lc.get("startup_timeout_s") or 30.0)


def _stop_timeout(cfg: TermiteConfig) -> float:
    lc = _launch_cfg(cfg)
    return float(lc.get("stop_timeout_s") or 10.0)


def _compute_endpoint_id(toolchain_id: str, base_url: str, model: str, started_utc: str | None) -> str:
    return hash_str(f"{toolchain_id}|{base_url}|{model}|{started_utc or ''}")


def _proc_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def read_status(cfg: TermiteConfig) -> LLMRuntimeStatus:
    sp = _state_path(cfg)
    base_url = _effective_base_url(cfg)
    model = _effective_model(cfg)
    provider = _effective_provider(cfg)
    pid = None
    managed = False
    started_utc = None
    running = False

    if sp.exists():
        try:
            st = json.loads(sp.read_text(encoding="utf-8"))
            base_url = str(st.get("base_url") or base_url)
            model = str(st.get("model") or model)
            provider = str(st.get("provider") or provider)
            pid = int(st["pid"]) if st.get("pid") is not None else None
            managed = bool(st.get("managed", False))
            started_utc = str(st.get("started_utc")) if st.get("started_utc") else None
            running = bool(st.get("running", False))
        except Exception:
            # fall back to config-only view
            pass

    # reconcile with actual process state
    if pid is not None:
        alive = _proc_running(pid)
        running = running and alive

    endpoint_id = _compute_endpoint_id(cfg.toolchain_id, base_url, model, started_utc)
    return LLMRuntimeStatus(
        toolchain_id=cfg.toolchain_id,
        provider=provider,
        base_url=base_url,
        model=model,
        pid=pid,
        managed=managed,
        running=running,
        started_utc=started_utc,
        state_path=str(sp),
        endpoint_id=endpoint_id,
    )


def ping(cfg: TermiteConfig) -> Tuple[bool, str]:
    st = read_status(cfg)
    url = st.base_url.rstrip("/") + _ping_path(cfg)
    try:
        r = requests.get(url, timeout=_ping_timeout(cfg))
        if r.status_code >= 200 and r.status_code < 300:
            return True, f"OK {r.status_code} {url}"
        return False, f"BAD {r.status_code} {url}"
    except Exception as e:
        return False, f"FAIL {url} :: {e}"


def _write_state(cfg: TermiteConfig, *, pid: Optional[int], managed: bool, running: bool, started_utc: Optional[str]) -> None:
    d = _llm_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    st = {
        "toolchain_id": cfg.toolchain_id,
        "provider": _effective_provider(cfg),
        "base_url": _effective_base_url(cfg),
        "model": _effective_model(cfg),
        "pid": pid,
        "managed": bool(managed),
        "running": bool(running),
        "started_utc": started_utc,
        "state_version": "1.0",
    }
    (_state_path(cfg)).write_text(json.dumps(st, indent=2, sort_keys=True), encoding="utf-8")
    if pid is not None:
        _pid_path(cfg).write_text(str(pid), encoding="utf-8")


def start(cfg: TermiteConfig, *, force: bool = False) -> LLMRuntimeStatus:
    # enforce offline safety: loopback only unless explicitly configured otherwise
    llm = _read_cfg_llm(cfg.raw)
    offline_loopback_only = bool(llm.get("offline_loopback_only", True))
    if offline_loopback_only and not _is_loopback(_effective_base_url(cfg)):
        raise RuntimeError("Refusing to use non-loopback base_url in offline_loopback_only mode")

    # if already running and not force: just return status
    st = read_status(cfg)
    if st.running and not force:
        return st

    d = _llm_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    logf = _log_path(cfg)
    logf.parent.mkdir(parents=True, exist_ok=True)

    lc = _launch_cfg(cfg)
    cmd = lc.get("command")
    enabled = bool(lc.get("enabled", False))
    cwd = lc.get("cwd")
    env = lc.get("env") or {}

    started_utc = utc_now_iso()

    pid: Optional[int] = None
    managed = False

    if enabled and cmd:
        if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
            raise RuntimeError("llm.launch.command must be a YAML list of strings")
        managed = True
        # merge env
        proc_env = dict(os.environ)
        for k, v in env.items():
            proc_env[str(k)] = str(v)
        # note: stdout/stderr to a single log file
        with logf.open("ab") as out:
            p = subprocess.Popen(
                cmd,
                cwd=str((cfg.runtime_root / str(cwd)).resolve()) if cwd else str(d),
                env=proc_env,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # so Termux can detach reliably
            )
        pid = int(p.pid)
        _write_state(cfg, pid=pid, managed=True, running=True, started_utc=started_utc)
    else:
        # endpoint-only: do not spawn, but record the endpoint as "active" if it responds
        ok, _msg = ping(cfg)
        if not ok:
            raise RuntimeError("Endpoint-only mode: ping failed; refuse to mark active (configure llm.launch or start server manually)")
        _write_state(cfg, pid=None, managed=False, running=True, started_utc=started_utc)

    # wait for readiness (ping)
    deadline = time.time() + _startup_timeout(cfg)
    while time.time() < deadline:
        ok, _ = ping(cfg)
        if ok:
            break
        time.sleep(0.6)

    # write provenance (best-effort; requires termite init)
    try:
        con = connect(cfg.db_path)
        prov = Provenance(cfg.toolchain_id)
        prov.append_event(con, "LLM_START", {
            "base_url": _effective_base_url(cfg),
            "model": _effective_model(cfg),
            "provider": _effective_provider(cfg),
            "managed": managed,
            "pid": pid,
            "started_utc": started_utc,
        })
        con.close()
    except Exception:
        pass

    return read_status(cfg)


def stop(cfg: TermiteConfig, *, force_kill: bool = False) -> LLMRuntimeStatus:
    st = read_status(cfg)
    pid = st.pid
    stopped_utc = utc_now_iso()

    if pid is not None and st.managed and _proc_running(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

        deadline = time.time() + _stop_timeout(cfg)
        while time.time() < deadline and _proc_running(pid):
            time.sleep(0.2)

        if _proc_running(pid) and force_kill:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

    # mark inactive
    _write_state(cfg, pid=None, managed=False, running=False, started_utc=st.started_utc or stopped_utc)
    try:
        _pid_path(cfg).unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass

    # provenance (best-effort)
    try:
        con = connect(cfg.db_path)
        prov = Provenance(cfg.toolchain_id)
        prov.append_event(con, "LLM_STOP", {
            "base_url": st.base_url,
            "model": st.model,
            "provider": st.provider,
            "pid": pid,
            "managed": st.managed,
            "stopped_utc": stopped_utc,
            "force_kill": bool(force_kill),
        })
        con.close()
    except Exception:
        pass

    return read_status(cfg)

