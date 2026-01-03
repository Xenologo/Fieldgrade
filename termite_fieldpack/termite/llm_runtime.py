from __future__ import annotations

import json
import os
import signal
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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


def _now_ts() -> float:
    return time.time()


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
    # Prefer structured config; keep legacy keys for compatibility.
    try:
        base = (cfg.llm.base_url or "").strip()
        if base:
            return base
        return f"http://{cfg.llm.host}:{cfg.llm.port}"
    except Exception:
        llm = _read_cfg_llm(cfg.raw)
        host = str(llm.get("host") or "127.0.0.1")
        port = int(llm.get("port") or 8789)
        return str(llm.get("endpoint_base_url") or llm.get("base_url") or f"http://{host}:{port}")


def _effective_model(cfg: TermiteConfig) -> str:
    try:
        return str(cfg.llm.model or "")
    except Exception:
        llm = _read_cfg_llm(cfg.raw)
        return str(llm.get("model") or "")


def _effective_provider(cfg: TermiteConfig) -> str:
    try:
        return str(cfg.llm.provider or "endpoint_only")
    except Exception:
        llm = _read_cfg_llm(cfg.raw)
        return str(llm.get("provider") or "endpoint_only")


def _ping_path(cfg: TermiteConfig) -> str:
    # Laptop-mode standard: OpenAI-compatible readiness endpoint.
    # Allow override via config for edge cases.
    try:
        p = str(cfg.llm.ping_path or "/v1/models")
        return p
    except Exception:
        llm = _read_cfg_llm(cfg.raw)
        ping = llm.get("ping") or {}
        return str(ping.get("path") or "/v1/models")


def _ping_timeout(cfg: TermiteConfig) -> float:
    try:
        return float(cfg.llm.ping_timeout_s)
    except Exception:
        llm = _read_cfg_llm(cfg.raw)
        ping = llm.get("ping") or {}
        return float(ping.get("timeout_s") or 3.0)


def _launch_cfg(cfg: TermiteConfig) -> Dict[str, Any]:
    # Prefer structured config; keep legacy raw.
    llm = _read_cfg_llm(cfg.raw)
    return (llm.get("launch") or {})


def _startup_timeout(cfg: TermiteConfig) -> float:
    try:
        return float(cfg.llm.launch.startup_timeout_seconds)
    except Exception:
        lc = _launch_cfg(cfg)
        return float(lc.get("startup_timeout_seconds") or lc.get("startup_timeout_s") or 30.0)


def _stop_timeout(cfg: TermiteConfig) -> float:
    try:
        return float(cfg.llm.launch.kill_timeout_seconds)
    except Exception:
        lc = _launch_cfg(cfg)
        return float(lc.get("kill_timeout_seconds") or lc.get("stop_timeout_s") or 10.0)


def _compute_endpoint_id(toolchain_id: str, base_url: str, model: str, started_utc: str | None) -> str:
    return hash_str(f"{toolchain_id}|{base_url}|{model}|{started_utc or ''}")


def _proc_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _atomic_write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _tail_text_file(path: Path, *, max_bytes: int = 4096) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        b = path.read_bytes()
        if max_bytes > 0 and len(b) > max_bytes:
            b = b[-max_bytes:]
        return b.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _build_launch_cmd(cfg: TermiteConfig) -> List[str]:
    """Return argv list for launching an OpenAI-compatible server.

    Accepts either a list of strings or a shell-ish string.
    If no command is provided and provider is known, builds a template.
    """
    provider = _effective_provider(cfg)
    llm_cfg = cfg.llm
    cmd_raw: Union[str, List[str], None]
    try:
        cmd_raw = llm_cfg.launch.command
    except Exception:
        cmd_raw = None

    # Template command if not provided.
    if (cmd_raw is None or cmd_raw == "" or cmd_raw == []):
        host = getattr(llm_cfg, "host", "127.0.0.1")
        port = int(getattr(llm_cfg, "port", 8789))
        model = _effective_model(cfg)
        model_path = (getattr(llm_cfg, "model_path", None) or "").strip()

        if provider == "llama_cpp_server":
            # llama.cpp's OpenAI-compatible server binary is typically `llama-server`.
            # Users may override this in config.
            if not model_path:
                model_path = model
            return [
                "llama-server",
                "-m",
                model_path,
                "--host",
                host,
                "--port",
                str(port),
            ]

        if provider == "vllm":
            # vLLM OpenAI-compatible API server
            model_arg = model_path if model_path else model
            return [
                "python",
                "-m",
                "vllm.entrypoints.openai.api_server",
                "--host",
                host,
                "--port",
                str(port),
                "--model",
                model_arg,
            ]

        raise RuntimeError(
            "llm.launch.command is required (or set llm.provider to llama_cpp_server/vllm to enable templates)"
        )

    if isinstance(cmd_raw, list):
        if not all(isinstance(x, str) for x in cmd_raw):
            raise RuntimeError("llm.launch.command list must contain only strings")
        return list(cmd_raw)

    if isinstance(cmd_raw, str):
        # Best-effort split. Prefer list-form on Windows.
        return shlex.split(cmd_raw, posix=(os.name != "nt"))

    raise RuntimeError("llm.launch.command must be a string or a list")


def _spawn_process(cfg: TermiteConfig, argv: List[str], *, cwd: Path, env: Dict[str, str]) -> subprocess.Popen:
    logf = _log_path(cfg)
    logf.parent.mkdir(parents=True, exist_ok=True)

    # Basic hardening: argv must be an explicit list of non-empty strings.
    # This function never uses shell=True.
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        raise RuntimeError("llm.launch.command resolved to invalid argv")
    if any((not a) or ("\x00" in a) for a in argv):
        raise RuntimeError("llm.launch.command contains empty/NUL argv entries")

    # Ensure repo-local Python modules can be imported even when the child
    # process runs with cwd under runtime_root (common in laptop mode and CI).
    try:
        repo_root = Path(__file__).resolve().parents[2]
        pp = str(env.get("PYTHONPATH") or "").strip()
        repo_root_s = str(repo_root)
        if pp:
            parts = pp.split(os.pathsep)
            if repo_root_s not in parts:
                env["PYTHONPATH"] = repo_root_s + os.pathsep + pp
        else:
            env["PYTHONPATH"] = repo_root_s
    except Exception:
        pass

    popen_kwargs: Dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": False,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    # Stream stdout/stderr to a single log file.
    out = logf.open("ab")
    popen_kwargs["stdout"] = out
    # Termite intentionally launches a local OpenAI-compatible server. The argv
    # comes from operator-controlled config (or a fixed template), and we
    # explicitly avoid shell=True.
    p = subprocess.Popen(argv, **popen_kwargs)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
    return p


def read_status(cfg: TermiteConfig) -> LLMRuntimeStatus:
    sp = _state_path(cfg)
    base_url = _effective_base_url(cfg)
    model = _effective_model(cfg)
    provider = _effective_provider(cfg)
    pid = None
    managed = False
    started_utc = None
    running = False
    last_error: Optional[str] = None

    if sp.exists():
        try:
            st = json.loads(sp.read_text(encoding="utf-8"))
            base_url = str(st.get("base_url") or base_url)
            model = str(st.get("model") or model)
            provider = str(st.get("provider") or provider)
            pid = int(st["pid"]) if st.get("pid") is not None else None
            managed = bool(st.get("managed", False))
            started_utc = str(st.get("started_at") or st.get("started_utc")) if (st.get("started_at") or st.get("started_utc")) else None
            running = bool(st.get("running", False))
            last_error = str(st.get("last_error")) if st.get("last_error") else None
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


def _write_state(
    cfg: TermiteConfig,
    *,
    pid: Optional[int],
    managed: bool,
    running: bool,
    started_at: Optional[str],
    launch_cmd: Optional[List[str]] = None,
    last_error: Optional[str] = None,
) -> None:
    d = _llm_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)

    base_url = _effective_base_url(cfg)
    model = _effective_model(cfg)
    provider = _effective_provider(cfg)
    endpoint_id = _compute_endpoint_id(cfg.toolchain_id, base_url, model, started_at)

    st = {
        "toolchain_id": cfg.toolchain_id,
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "pid": pid,
        "managed": bool(managed),
        "running": bool(running),
        "started_at": started_at,
        "endpoint_id": endpoint_id,
        "state_version": "2.0",
    }
    if launch_cmd is not None:
        st["launch_cmd"] = list(launch_cmd)
    if last_error:
        st["last_error"] = str(last_error)

    _atomic_write_json(_state_path(cfg), st)
    if pid is not None:
        try:
            _pid_path(cfg).write_text(str(pid), encoding="utf-8")
        except Exception:
            pass


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

    llm_cfg = cfg.llm
    enabled = bool(getattr(llm_cfg.launch, "enabled", False))
    started_at = utc_now_iso()

    pid: Optional[int] = None
    managed = False

    model = _effective_model(cfg).strip()
    if enabled and not model:
        raise RuntimeError("llm.model is required when llm.launch.enabled=true")

    model_path = (getattr(llm_cfg, "model_path", None) or "").strip()
    if enabled and model_path:
        mp = Path(model_path)
        if not mp.exists():
            raise RuntimeError(f"llm.model_path does not exist: {mp} (download weights or update config)")

    launch_cmd: Optional[List[str]] = None

    p: Optional[subprocess.Popen] = None

    if enabled:
        managed = True
        launch_cmd = _build_launch_cmd(cfg)

        # merge env
        proc_env = dict(os.environ)
        for k, v in dict(getattr(llm_cfg.launch, "env", {}) or {}).items():
            proc_env[str(k)] = str(v)

        # cwd: allow relative to runtime_root
        cwd_raw = getattr(llm_cfg.launch, "cwd", None)
        if cwd_raw:
            cwd_path = (cfg.runtime_root / str(cwd_raw)).resolve()
        else:
            cwd_path = d

        p = _spawn_process(cfg, launch_cmd, cwd=cwd_path, env=proc_env)
        pid = int(p.pid)
        _write_state(cfg, pid=pid, managed=True, running=True, started_at=started_at, launch_cmd=launch_cmd)
    else:
        # endpoint-only: do not spawn, but record the endpoint as "active" if it responds
        ok, _msg = ping(cfg)
        if not ok:
            raise RuntimeError("Endpoint-only mode: ping failed; refuse to mark active (configure llm.launch or start server manually)")
        _write_state(cfg, pid=None, managed=False, running=True, started_at=started_at)

    # wait for readiness (ping)
    deadline = time.time() + _startup_timeout(cfg)
    last_err = ""
    while time.time() < deadline:
        # If we launched a managed subprocess and it already exited, surface its log.
        if managed and pid is not None and not _proc_running(pid):
            tail = _tail_text_file(_log_path(cfg))
            if tail:
                last_err = f"process_exited_early (pid={pid})\n--- server.log (tail) ---\n{tail}"
            else:
                last_err = f"process_exited_early (pid={pid})"
            break
        ok, _ = ping(cfg)
        if ok:
            break
        time.sleep(0.6)

    ok, msg = ping(cfg)
    if not ok:
        last_err = last_err or msg
        if not last_err:
            last_err = "unready"

        if managed:
            tail = _tail_text_file(_log_path(cfg))
            if tail and tail not in last_err:
                last_err = f"{last_err}\n--- server.log (tail) ---\n{tail}"
        # ensure we do not leave a stale pid/state behind
        try:
            stop(cfg, force_kill=True)
        except Exception:
            pass
        _write_state(cfg, pid=None, managed=False, running=False, started_at=started_at, launch_cmd=launch_cmd, last_error=last_err)
        raise RuntimeError(f"llm_start_failed: {last_err}")

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
            "started_at": started_at,
            "launch_cmd": launch_cmd,
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
        # Try graceful termination first.
        try:
            if os.name == "nt":
                # Best-effort: SIGTERM may map to TerminateProcess; still try.
                os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

        deadline = time.time() + _stop_timeout(cfg)
        while time.time() < deadline and _proc_running(pid):
            time.sleep(0.2)

        if _proc_running(pid):
            if os.name == "nt":
                # Fallback: ensure the process tree is terminated.
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                except Exception:
                    pass
            elif force_kill:
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass

    # mark inactive
    _write_state(cfg, pid=None, managed=False, running=False, started_at=st.started_utc or stopped_utc)
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


# ---------------------------------------------------------------------------
# Laptop-mode friendly APIs (requested names)
# ---------------------------------------------------------------------------


def start_llm(cfg: TermiteConfig, *, force: bool = False) -> Dict[str, Any]:
    st = start(cfg, force=force)
    return status_llm(cfg)


def stop_llm(cfg: TermiteConfig, *, force_kill: bool = False) -> Dict[str, Any]:
    stop(cfg, force_kill=force_kill)
    return status_llm(cfg)


def ping_llm(cfg: TermiteConfig) -> Dict[str, Any]:
    ok, msg = ping(cfg)
    return {"ok": bool(ok), "msg": msg}


def status_llm(cfg: TermiteConfig) -> Dict[str, Any]:
    sp = _state_path(cfg)
    base_url = _effective_base_url(cfg)
    model = _effective_model(cfg)
    provider = _effective_provider(cfg)
    launch_enabled = bool(getattr(cfg.llm.launch, "enabled", False))

    pid: Optional[int] = None
    managed = False
    started_at: Optional[str] = None
    endpoint_id: Optional[str] = None
    last_error: Optional[str] = None
    launch_cmd: Optional[List[str]] = None

    if sp.exists():
        try:
            st = json.loads(sp.read_text(encoding="utf-8"))
            base_url = str(st.get("base_url") or base_url)
            model = str(st.get("model") or model)
            provider = str(st.get("provider") or provider)
            pid = int(st["pid"]) if st.get("pid") is not None else None
            managed = bool(st.get("managed", False))
            started_at = str(st.get("started_at") or st.get("started_utc")) if (st.get("started_at") or st.get("started_utc")) else None
            endpoint_id = str(st.get("endpoint_id")) if st.get("endpoint_id") else None
            last_error = str(st.get("last_error")) if st.get("last_error") else None
            if isinstance(st.get("launch_cmd"), list) and all(isinstance(x, str) for x in st.get("launch_cmd")):
                launch_cmd = list(st.get("launch_cmd"))
        except Exception:
            pass

    if endpoint_id is None:
        endpoint_id = _compute_endpoint_id(cfg.toolchain_id, base_url, model, started_at)

    stale_pid = False
    alive = True
    if pid is not None:
        alive = _proc_running(pid)

    ready = False
    ping_msg = ""
    if alive:
        ok, ping_msg = ping(cfg)
        ready = bool(ok)
        if not ready and not last_error:
            last_error = ping_msg

    # Spec: if PID exists but process is dead OR ping fails => stale_pid=true.
    if pid is not None and (not alive or not ready):
        stale_pid = True

    running = bool(alive and ready)

    # If we had a pid but it is dead or server is unready, ensure state doesn't claim running.
    if sp.exists():
        try:
            current = json.loads(sp.read_text(encoding="utf-8"))
            if bool(current.get("running", False)) and not running:
                current["running"] = False
                # Keep PID as recorded so stale_pid remains diagnosable.
                # Only an explicit stop should clear the PID and pid file.
                if current.get("pid") is None:
                    current["pid"] = pid
                if last_error:
                    current["last_error"] = last_error
                _atomic_write_json(sp, current)
        except Exception:
            pass

    return {
        "running": running,
        "ready": ready,
        "stale_pid": stale_pid,
        "launch_enabled": launch_enabled,
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "endpoint_id": endpoint_id,
        "toolchain_id": cfg.toolchain_id,
        "started_at": started_at,
        "pid": pid if alive else None,
        "managed": bool(managed),
        "launch_cmd": launch_cmd,
        "last_error": last_error,
        "state_path": str(sp),
        "ping_msg": ping_msg,
    }


def resolve_active_endpoint(cfg: TermiteConfig) -> Optional[Dict[str, Any]]:
    """Return active endpoint info if the runtime is running and ready."""
    st = status_llm(cfg)
    if st.get("running"):
        return {
            "base_url": str(st.get("base_url") or ""),
            "model": str(st.get("model") or ""),
            "endpoint_id": str(st.get("endpoint_id") or ""),
            "toolchain_id": str(st.get("toolchain_id") or ""),
            "provider": str(st.get("provider") or ""),
            "started_at": st.get("started_at"),
            "pid": st.get("pid"),
        }
    return None


