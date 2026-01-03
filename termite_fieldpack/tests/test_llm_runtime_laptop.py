from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from termite.config import TermiteConfig
from termite.llm_runtime import ping_llm, start_llm, status_llm, stop_llm


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return int(s.getsockname()[1])


def _mk_cfg(tmp_path: Path, port: int) -> TermiteConfig:
    runtime_root = tmp_path / "runtime"
    raw = {
        "termite": {
            "runtime_root": str(runtime_root),
            "cas_root": str(runtime_root / "cas"),
            "db_path": str(runtime_root / "termite.sqlite"),
            "bundles_out": str(tmp_path / "bundles_out"),
            "offline_mode": True,
            "network_policy": "deny_by_default",
        },
        "toolchain": {"toolchain_id": "TEST_TOOLCHAIN"},
        "llm": {
            "provider": "endpoint_only",
            "host": "127.0.0.1",
            "port": int(port),
            "model": "fake-model",
            "offline_loopback_only": True,
            "ping": {"path": "/v1/models", "timeout_s": 2},
            "launch": {
                "enabled": True,
                "command": [
                    sys.executable,
                    "-m",
                    "termite_fieldpack.tests.support.fake_openai_server",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--model",
                    "fake-model",
                ],
                "env": {},
                "cwd": None,
                "startup_timeout_seconds": 10,
                "kill_timeout_seconds": 5,
            },
        },
    }
    return TermiteConfig(raw)


def test_llm_runtime_start_ping_stop_status(tmp_path: Path) -> None:
    port = _free_port()
    cfg = _mk_cfg(tmp_path, port)

    st = start_llm(cfg)
    assert st["running"] is True
    assert st.get("ready") is True
    assert st.get("stale_pid") is False
    assert st.get("base_url", "").endswith(f":{port}")
    assert st.get("model") == "fake-model"
    assert st.get("endpoint_id")

    ping = ping_llm(cfg)
    assert ping["ok"] is True

    stopped = stop_llm(cfg, force_kill=False)
    assert stopped["running"] is False

    # Active endpoint file should contain the required keys.
    state_path = Path(stopped["state_path"])
    obj = json.loads(state_path.read_text(encoding="utf-8"))
    for k in ["running", "base_url", "model", "endpoint_id", "toolchain_id", "started_at", "provider", "pid"]:
        assert k in obj


def test_llm_runtime_status_stale_pid_when_process_dies(tmp_path: Path) -> None:
    port = _free_port()
    cfg = _mk_cfg(tmp_path, port)

    st = start_llm(cfg)
    pid = int(st["pid"])

    # Kill the child process externally.
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    # Give it a moment to exit and for /v1/models to fail.
    deadline = time.time() + 5
    while time.time() < deadline:
        s2 = status_llm(cfg)
        if s2.get("stale_pid") or not s2.get("running"):
            break
        time.sleep(0.1)

    s2 = status_llm(cfg)
    assert s2.get("running") is False
    assert s2.get("stale_pid") is True

    # Cleanup is idempotent.
    stop_llm(cfg, force_kill=True)
