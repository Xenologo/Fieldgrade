from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


def _expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


@dataclass(frozen=True)
class EcologyConfig:
    """Configuration wrapper for mite_ecology.

    The config file is expected to have top-level keys:
      - mite_ecology: paths + import/bundle governance
      - embedding: embedding params
      - gat: attention params
      - memoga: GA params
    """

    raw: Dict[str, Any]

    # -------------------------
    # Core paths
    # -------------------------
    @property
    def runtime_root(self) -> Path:
        return Path(_expand(self.raw["mite_ecology"]["runtime_root"])).resolve()

    @property
    def db_path(self) -> Path:
        return Path(_expand(self.raw["mite_ecology"]["db_path"])).resolve()

    @property
    def imports_root(self) -> Path:
        return Path(_expand(self.raw["mite_ecology"]["imports_root"])).resolve()

    @property
    def exports_root(self) -> Path:
        return Path(_expand(self.raw["mite_ecology"]["exports_root"])).resolve()

    @property
    def policy_path(self) -> Path:
        p = self.raw.get("mite_ecology", {}).get("policy_path", "../termite_fieldpack/config/meap_v1.yaml")
        return Path(_expand(str(p))).resolve()

    @property
    def allowlist_path(self) -> Path:
        p = self.raw.get("mite_ecology", {}).get("allowlist_path", "../termite_fieldpack/config/tool_allowlist.yaml")
        return Path(_expand(str(p))).resolve()

    @property
    def schemas_dir(self) -> Path:
        p = self.raw.get("mite_ecology", {}).get("schemas_dir", "../schemas")
        return Path(_expand(str(p))).resolve()

    # -------------------------
    # Bundle accept limits
    # -------------------------
    @property
    def max_bundle_ops(self) -> int:
        return int(self.raw.get("mite_ecology", {}).get("max_bundle_ops", 200_000))

    @property
    def max_bundle_new_nodes(self) -> int:
        return int(self.raw.get("accept", {}).get("max_new_nodes", 2000))

    @property
    def max_bundle_new_edges(self) -> int:
        return int(self.raw.get("accept", {}).get("max_new_edges", 10_000))

    # -------------------------
    # Embedding params
    # -------------------------
    @property
    def feature_dim(self) -> int:
        return int(self.raw.get("embedding", {}).get("feature_dim", 32))

    @property
    def hops(self) -> int:
        return int(self.raw.get("embedding", {}).get("hops", 2))

    # -------------------------
    # GAT params
    # -------------------------
    @property
    def gat_alpha(self) -> float:
        return float(self.raw.get("gat", {}).get("alpha", 0.2))

    @property
    def gat_top_edges(self) -> int:
        return int(self.raw.get("gat", {}).get("top_edges", 16))

    # -------------------------
    # GA params
    # -------------------------
    @property
    def ga_population(self) -> int:
        return int(self.raw.get("memoga", {}).get("population", 32))

    @property
    def ga_generations(self) -> int:
        return int(self.raw.get("memoga", {}).get("generations", 12))

    @property
    def ga_elite_k(self) -> int:
        return int(self.raw.get("memoga", {}).get("elite_k", 4))

    @property
    def ga_mutation_rate(self) -> float:
        return float(self.raw.get("memoga", {}).get("mutation_rate", 0.3))

    @property
    def ga_crossover_rate(self) -> float:
        return float(self.raw.get("memoga", {}).get("crossover_rate", 0.5))

    @property
    def ga_max_nodes(self) -> int:
        return int(self.raw.get("memoga", {}).get("max_nodes_per_genome", 64))

    @property
    def ga_max_edges(self) -> int:
        return int(self.raw.get("memoga", {}).get("max_edges_per_genome", 64))


def load_config(path: str | Path) -> EcologyConfig:
    p = Path(path).resolve()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "mite_ecology" not in raw:
        raise ValueError("invalid_config: missing top-level 'mite_ecology' key")
    return EcologyConfig(raw)


def default_config_path() -> Path:
    # Prefer project-local configs/ecology.yaml (renamed from config/ to avoid namespace collision)
    cwd = Path.cwd()
    for cand in [cwd / "configs" / "ecology.yaml", cwd / "config" / "ecology.yaml", cwd / "ecology.yaml"]:
        if cand.exists():
            return cand.resolve()
    # Fallback to bundled config in package layout
    return (Path(__file__).resolve().parents[1] / "configs" / "ecology.yaml").resolve()
