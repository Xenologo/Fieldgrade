from __future__ import annotations

"""SBOM helpers.

This repo ships a **minimal CycloneDX JSON** generator that requires *no*
third-party SBOM tooling at runtime. It is intentionally conservative and
captures the active Python environment's installed distributions.

Why CycloneDX?
  - It's widely used for software supply-chain inventory.
  - It's machine-readable and can be validated against the CycloneDX JSON schema.

We keep this generator small so Termite can run in constrained environments.
"""

import platform
from importlib import metadata
from typing import Any, Dict, List

from .provenance import utc_now_iso


def _installed_distributions() -> List[Dict[str, str]]:
    dists: List[Dict[str, str]] = []
    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "unknown").strip()
        ver = (dist.version or "unknown").strip()
        if not name:
            name = "unknown"
        if not ver:
            ver = "unknown"
        dists.append({"name": name, "version": ver})
    dists.sort(key=lambda x: (x["name"].lower(), x["version"]))
    return dists


def build_cyclonedx_bom(*, spec_version: str = "1.5") -> Dict[str, Any]:
    """Create a CycloneDX BOM (JSON) from installed Python distributions.

    This is not a complete SBOM for *source* inputs (it reflects the environment
    used to build/seal), but it's a practical minimum for fieldpacks.
    """
    dists = _installed_distributions()
    components = [
        {
            "type": "library",
            "name": p["name"],
            "version": p["version"],
            "purl": f"pkg:pypi/{p['name']}@{p['version']}",
        }
        for p in dists
    ]

    return {
        "bomFormat": "CycloneDX",
        "specVersion": str(spec_version),
        "version": 1,
        "metadata": {
            "timestamp": utc_now_iso(),
            "tools": [
                {
                    "vendor": "Termite",
                    "name": "termite_fieldpack",
                    "version": "0.1",
                }
            ],
            "properties": [
                {"name": "python.version", "value": platform.python_version()},
                {"name": "platform.system", "value": platform.system()},
                {"name": "platform.release", "value": platform.release()},
                {"name": "platform.machine", "value": platform.machine()},
            ],
        },
        "components": components,
    }
