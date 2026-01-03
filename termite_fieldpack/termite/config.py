from __future__ import annotations

import os
from dataclasses import dataclass, field
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

import yaml

def _expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


@dataclass(frozen=True)
class LLMLaunchConfig:
    enabled: bool = False
    # Accept either a string (shell-ish) or a list of argv tokens.
    command: Union[str, List[str], None] = None
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    startup_timeout_seconds: float = 30.0
    kill_timeout_seconds: float = 10.0


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "endpoint_only"

    # OpenAI-compatible base URL (preferred). If absent, it will be derived from host/port.
    base_url: str = ""

    # Model identifier (required for laptop launch mode).
    model: str = ""

    # Optional local model path (recommended in laptop mode when the server requires weights).
    model_path: Optional[str] = None

    host: str = "127.0.0.1"
    port: int = 8789

    offline_loopback_only: bool = True

    ping_path: str = "/v1/models"
    ping_timeout_s: float = 3.0

    launch: LLMLaunchConfig = field(default_factory=LLMLaunchConfig)


@dataclass(frozen=True)
class TermiteConfig:
    raw: Dict[str, Any]

    # -------------------------
    # Structured LLM config (backward compatible)
    # -------------------------
    @property
    def llm(self) -> LLMConfig:
        llm_raw = dict(self.raw.get("llm", {}) or {})

        provider = str(llm_raw.get("provider") or "endpoint_only")
        model = str(llm_raw.get("model") or "")
        model_path = llm_raw.get("model_path")
        model_path_s = str(model_path) if model_path is not None and str(model_path).strip() else None

        host = str(llm_raw.get("host") or "127.0.0.1")
        try:
            port = int(llm_raw.get("port") or 8789)
        except Exception:
            port = 8789

        # Backward compatibility: endpoint_base_url was the original name.
        base_url = str(llm_raw.get("endpoint_base_url") or llm_raw.get("base_url") or "").strip()
        if not base_url:
            base_url = f"http://{host}:{port}"

        offline_loopback_only = bool(llm_raw.get("offline_loopback_only", True))
        ping_raw = dict(llm_raw.get("ping", {}) or {})
        ping_path = str(ping_raw.get("path") or "/v1/models")
        try:
            ping_timeout_s = float(ping_raw.get("timeout_s") or 3.0)
        except Exception:
            ping_timeout_s = 3.0

        launch_raw = dict(llm_raw.get("launch", {}) or {})
        enabled = bool(launch_raw.get("enabled", False))

        command: Union[str, List[str], None]
        cmd_raw = launch_raw.get("command")
        if cmd_raw is None:
            command = None
        elif isinstance(cmd_raw, str):
            command = cmd_raw
        elif isinstance(cmd_raw, list) and all(isinstance(x, str) for x in cmd_raw):
            command = list(cmd_raw)
        else:
            # Preserve backwards-compatibility by treating invalid command types as absent.
            command = None

        env_raw = launch_raw.get("env") or {}
        env: Dict[str, str] = {}
        if isinstance(env_raw, Mapping):
            for k, v in env_raw.items():
                env[str(k)] = str(v)

        cwd = launch_raw.get("cwd")
        cwd_s = str(cwd) if cwd is not None and str(cwd).strip() else None

        # Backward compatibility: older configs used *_timeout_s.
        st_raw = launch_raw.get("startup_timeout_seconds", launch_raw.get("startup_timeout_s", 30))
        kt_raw = launch_raw.get("kill_timeout_seconds", launch_raw.get("stop_timeout_s", 10))
        try:
            startup_timeout_seconds = float(st_raw)
        except Exception:
            startup_timeout_seconds = 30.0
        try:
            kill_timeout_seconds = float(kt_raw)
        except Exception:
            kill_timeout_seconds = 10.0

        return LLMConfig(
            provider=provider,
            base_url=base_url,
            model=model,
            model_path=model_path_s,
            host=host,
            port=port,
            offline_loopback_only=offline_loopback_only,
            ping_path=ping_path,
            ping_timeout_s=ping_timeout_s,
            launch=LLMLaunchConfig(
                enabled=enabled,
                command=command,
                env=env,
                cwd=cwd_s,
                startup_timeout_seconds=startup_timeout_seconds,
                kill_timeout_seconds=kill_timeout_seconds,
            ),
        )

    # -------------------------
    # Core paths
    # -------------------------
    @property
    def runtime_root(self) -> Path:
        return Path(_expand(self.raw["termite"]["runtime_root"])).resolve()

    @property
    def cas_root(self) -> Path:
        return Path(_expand(self.raw["termite"]["cas_root"])).resolve()

    @property
    def db_path(self) -> Path:
        return Path(_expand(self.raw["termite"]["db_path"])).resolve()

    @property
    def bundles_out(self) -> Path:
        return Path(_expand(self.raw["termite"]["bundles_out"])).resolve()

    # Paths to governance policy + allowlist (used for sealing audit fields)
    @property
    def policy_path(self) -> Path:
        p = self.raw.get("termite", {}).get("policy_path", "./config/meap_v1.yaml")
        return Path(_expand(str(p))).resolve()

    @property
    def allowlist_path(self) -> Path:
        p = self.raw.get("termite", {}).get("allowlist_path", "./config/tool_allowlist.yaml")
        return Path(_expand(str(p))).resolve()

    # -------------------------
    # Runtime controls
    # -------------------------
    @property
    def offline_mode(self) -> bool:
        return bool(self.raw["termite"].get("offline_mode", True))

    @property
    def network_policy(self) -> str:
        return str(self.raw["termite"].get("network_policy", "deny_by_default"))

    # -------------------------
    # Toolchain identity + signing
    # -------------------------
    @property
    def toolchain_id(self) -> str:
        return str(self.raw["toolchain"]["toolchain_id"])

    @property
    def signing_enabled(self) -> bool:
        return bool(self.raw.get("toolchain", {}).get("signing", {}).get("enabled", True))

    @property
    def signing_private_key_path(self) -> Path:
        return Path(_expand(self.raw["toolchain"]["signing"]["private_key_path"])).resolve()

    @property
    def signing_public_key_path(self) -> Path:
        return Path(_expand(self.raw["toolchain"]["signing"]["public_key_path"])).resolve()

    # -------------------------
    # Ingest settings
    # -------------------------
    @property
    def max_bytes(self) -> int:
        return int(self.raw.get("ingest", {}).get("max_bytes", 25_000_000))

    @property
    def extract_text(self) -> bool:
        return bool(self.raw.get("ingest", {}).get("extract_text", True))

    @property
    def chunk_chars(self) -> int:
        return int(self.raw.get("ingest", {}).get("chunking", {}).get("chunk_chars", 2000))

    @property
    def overlap_chars(self) -> int:
        return int(self.raw.get("ingest", {}).get("chunking", {}).get("overlap_chars", 200))

    @property
    def min_chunk_chars(self) -> int:
        return int(self.raw.get("ingest", {}).get("chunking", {}).get("min_chunk_chars", 300))

    # -------------------------
    # Seal/export settings
    # -------------------------
    @property
    def include_raw(self) -> bool:
        return bool(self.raw.get("seal", {}).get("include_raw_blobs", True))

    @property
    def include_extract(self) -> bool:
        return bool(self.raw.get("seal", {}).get("include_extracted_blobs", True))

    @property
    def include_aux(self) -> bool:
        return bool(self.raw.get("seal", {}).get("include_aux", True))

    @property
    def include_provenance(self) -> bool:
        return bool(self.raw.get("seal", {}).get("include_provenance", True))

    @property
    def include_sbom(self) -> bool:
        return bool(self.raw.get("seal", {}).get("include_sbom", True))

    @property
    def include_kg_delta(self) -> bool:
        return bool(self.raw.get("seal", {}).get("include_kg_delta", True))

    @property
    def deterministic_zip(self) -> bool:
        return bool(self.raw.get("seal", {}).get("deterministic_zip", True))

    # -------------------------
    # LLM settings (offline endpoint + optional launcher)
    # -------------------------
    @property
    def llm_provider(self) -> str:
        return self.llm.provider

    @property
    def llm_endpoint_base_url(self) -> str:
        # Keep legacy name for compatibility (endpoint_base_url).
        return str((self.raw.get("llm", {}) or {}).get("endpoint_base_url") or "")

    @property
    def llm_base_url(self) -> str:
        return self.llm.base_url

    @property
    def llm_host(self) -> str:
        return self.llm.host

    @property
    def llm_port(self) -> int:
        return int(self.llm.port)

    @property
    def llm_model_path(self) -> str:
        return str(self.llm.model_path or "")

    @property
    def llm_model(self) -> str:
        return self.llm.model

    @property
    def llm_offline_loopback_only(self) -> bool:
        return bool(self.llm.offline_loopback_only)

    @property
    def llm_ping_path(self) -> str:
        return self.llm.ping_path

    @property
    def llm_ping_timeout_s(self) -> int:
        return int(self.llm.ping_timeout_s)

    @property
    def llm_launch_enabled(self) -> bool:
        return bool(self.llm.launch.enabled)

    @property
    def llm_launch_command(self) -> list[str]:
        cmd = self.llm.launch.command
        return list(cmd) if isinstance(cmd, list) else []

    @property
    def llm_launch_cwd(self) -> Path:
        cwd = self.llm.launch.cwd or str(self.runtime_root / "llm")
        return Path(_expand(str(cwd))).resolve()

    @property
    def llm_launch_env(self) -> Dict[str, str]:
        return dict(self.llm.launch.env)

    @property
    def llm_startup_timeout_s(self) -> int:
        return int(self.llm.launch.startup_timeout_seconds)

    @property
    def llm_stop_timeout_s(self) -> int:
        return int(self.llm.launch.kill_timeout_seconds)


def default_config_path() -> Path:
    return (Path(__file__).resolve().parents[1] / "config" / "termite.yaml").resolve()

def load_config(path: str | Path) -> TermiteConfig:
    p = Path(path).resolve()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "termite" not in raw:
        raise ValueError("invalid_config: missing top-level 'termite' key")
    return TermiteConfig(raw)
