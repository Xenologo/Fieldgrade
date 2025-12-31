from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import yaml

@dataclass(frozen=True)
class MEAPPolicy:
    raw: Dict[str, Any]

    @property
    def policy_id(self) -> str:
        return str(self.raw["meap_v1"]["policy_id"])

    @property
    def mode(self) -> str:
        return str(self.raw["meap_v1"]["mode"])

    @property
    def thresholds(self) -> Dict[str, Any]:
        return dict(self.raw["meap_v1"]["thresholds"])

    @property
    def replay(self) -> Dict[str, Any]:
        return dict(self.raw["meap_v1"]["replay"])

    @property
    def accept(self) -> Dict[str, Any]:
        return dict(self.raw["meap_v1"]["accept"])

def load_policy(path: str | Path) -> MEAPPolicy:
    p = Path(path).resolve()
    return MEAPPolicy(yaml.safe_load(p.read_text(encoding="utf-8")))
