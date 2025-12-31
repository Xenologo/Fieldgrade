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

    @property
    def toolchain_id(self) -> str:
        return str(self.raw["toolchain"]["toolchain_id"])

    @property
    def signing_enabled(self) -> bool:
        return bool(self.raw["toolchain"]["signing"]["enabled"])

    @property
    def signing_private_key_path(self) -> Path:
        return Path(_expand(self.raw["toolchain"]["signing"]["private_key_path"])).resolve()

    @property
    def signing_public_key_path(self) -> Path:
        return Path(_expand(self.raw["toolchain"]["signing"]["public_key_path"])).resolve()

    @property
    def max_bytes(self) -> int:
        return int(self.raw["ingest"]["max_bytes"])

    @property
    def extract_text(self) -> bool:
        return bool(self.raw["ingest"]["extract_text"])

    @property
    def chunk_chars(self) -> int:
        return int(self.raw["ingest"]["chunking"]["chunk_chars"])

    @property
    def overlap_chars(self) -> int:
        return int(self.raw["ingest"]["chunking"]["overlap_chars"])

    @property
    def min_chunk_chars(self) -> int:
        return int(self.raw["ingest"]["chunking"]["min_chunk_chars"])

    @property
    def deterministic_zip(self) -> bool:
        return bool(self.raw["seal"]["deterministic_zip"])

    @property
    def include_kg_delta(self) -> bool:
        return bool(self.raw["seal"].get("include_kg_delta", True))

    @property
    def include_raw_blobs(self) -> bool:
        return bool(self.raw["seal"].get("include_raw_blobs", True))

    @property
    def include_extracted_blobs(self) -> bool:
        return bool(self.raw["seal"].get("include_extracted_blobs", True))
@property
def include_aux(self) -> bool:
    return bool(self.raw.get("seal", {}).get("include_aux", True))


    @property
    def include_provenance(self) -> bool:
        return bool(self.raw["seal"].get("include_provenance", True))

    @property
    def include_sbom(self) -> bool:
        return bool(self.raw["seal"].get("include_sbom", True))


def db_con(self):
    from .db import connect
    return connect(self.db_path)
def load_config(path: str | Path) -> TermiteConfig:
    p = Path(path).resolve()
    return TermiteConfig(yaml.safe_load(p.read_text(encoding="utf-8")))

def default_config_path() -> Path:
    cwd = Path.cwd()
    for cand in [cwd/"config"/"termite.yaml", cwd/"termite.yaml"]:
        if cand.exists():
            return cand.resolve()
    return Path("config/termite.yaml").resolve()
