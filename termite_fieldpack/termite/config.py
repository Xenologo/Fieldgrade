from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

def _expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))

@dataclass(frozen=True)
class TermiteConfig:
    raw: Dict[str, Any]

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
        return str(self.raw.get("llm", {}).get("provider", "endpoint_only"))

    @property
    def llm_endpoint_base_url(self) -> str:
        return str(self.raw.get("llm", {}).get("endpoint_base_url", ""))

    @property
    def llm_model(self) -> str:
        return str(self.raw.get("llm", {}).get("model", ""))

    @property
    def llm_offline_loopback_only(self) -> bool:
        return bool(self.raw.get("llm", {}).get("offline_loopback_only", True))

    @property
    def llm_ping_path(self) -> str:
        return str(self.raw.get("llm", {}).get("ping", {}).get("path", "/v1/models"))

    @property
    def llm_ping_timeout_s(self) -> int:
        return int(self.raw.get("llm", {}).get("ping", {}).get("timeout_s", 3))

    @property
    def llm_launch_enabled(self) -> bool:
        return bool(self.raw.get("llm", {}).get("launch", {}).get("enabled", False))

    @property
    def llm_launch_command(self) -> list[str]:
        return list(self.raw.get("llm", {}).get("launch", {}).get("command", []))

    @property
    def llm_launch_cwd(self) -> Path:
        return Path(_expand(self.raw.get("llm", {}).get("launch", {}).get("cwd", str(self.runtime_root / "llm")))).resolve()

    @property
    def llm_launch_env(self) -> Dict[str, str]:
        return dict(self.raw.get("llm", {}).get("launch", {}).get("env", {}))

    @property
    def llm_startup_timeout_s(self) -> int:
        return int(self.raw.get("llm", {}).get("launch", {}).get("startup_timeout_s", 30))

    @property
    def llm_stop_timeout_s(self) -> int:
        return int(self.raw.get("llm", {}).get("launch", {}).get("stop_timeout_s", 10))


def default_config_path() -> Path:
    return (Path(__file__).resolve().parents[1] / "config" / "termite.yaml").resolve()

def load_config(path: str | Path) -> TermiteConfig:
    p = Path(path).resolve()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "termite" not in raw:
        raise ValueError("invalid_config: missing top-level 'termite' key")
    return TermiteConfig(raw)
