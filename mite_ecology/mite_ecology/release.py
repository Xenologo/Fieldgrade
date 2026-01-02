from __future__ import annotations

import json
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .hashutil import canonical_json, sha256_hex, sha256_str
from .registry import RegistryLoadResult, load_components_registry, load_remotes_registry, load_variants_registry


@dataclass(frozen=True)
class ReleaseBuildResult:
    release_id: str
    created_utc: str
    manifest_sha256: str
    out_dir: str
    manifest_path: str
    zip_path: str
    registries: Dict[str, Dict[str, Any]]


def _utc_iso(ts: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts or time.time()))


def _deterministic_zip_write(zip_path: Path, files: Dict[str, bytes]) -> None:
    """Write a deterministic zip (stable ordering + fixed timestamps)."""

    zip_path.parent.mkdir(parents=True, exist_ok=True)

    # Fixed earliest DOS timestamp to keep bytes stable.
    fixed_dt = (1980, 1, 1, 0, 0, 0)

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(files.keys()):
            data = files[name]
            zi = zipfile.ZipInfo(filename=name, date_time=fixed_dt)
            zi.compress_type = zipfile.ZIP_DEFLATED
            # Force consistent file mode bits.
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data)


def _registry_record(r: RegistryLoadResult) -> Dict[str, Any]:
    return {
        "path": r.path,
        "canonical_sha256": r.canonical_sha256,
    }


def build_release(
    *,
    out_dir: str | Path,
    components_path: str | Path | None = None,
    variants_path: str | Path | None = None,
    remotes_path: str | Path | None = None,
) -> ReleaseBuildResult:
    """Build a deterministic release artifact.

    Produces:
      - {out_dir}/{release_id}/manifest.json
      - {out_dir}/{release_id}/registries/{components,variants,remotes}.json
      - {out_dir}/{release_id}.zip (deterministic zip)

    The release_id is derived from the sha256 of the canonical manifest JSON.
    """

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    comp = load_components_registry(components_path)
    var = load_variants_registry(variants_path)
    rem = load_remotes_registry(remotes_path)

    created = _utc_iso()

    manifest_obj: Dict[str, Any] = {
        "type": "fieldgrade_release/1.0",
        "version": "1.0",
        "created_utc": created,
        "registries": {
            "components": _registry_record(comp),
            "variants": _registry_record(var),
            "remotes": _registry_record(rem),
        },
    }

    manifest_canon = canonical_json(manifest_obj)
    manifest_sha = sha256_str(manifest_canon)
    release_id = manifest_sha[:16]

    # Write directory layout
    rel_dir = out_root / release_id
    reg_dir = rel_dir / "registries"
    reg_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = rel_dir / "manifest.json"
    manifest_path.write_text(manifest_canon, encoding="utf-8")

    (reg_dir / "components.json").write_text(comp.canonical_json, encoding="utf-8")
    (reg_dir / "variants.json").write_text(var.canonical_json, encoding="utf-8")
    (reg_dir / "remotes.json").write_text(rem.canonical_json, encoding="utf-8")

    # Deterministic zip content
    zip_path = out_root / f"{release_id}.zip"
    zip_files = {
        "manifest.json": manifest_canon.encode("utf-8"),
        "registries/components.json": comp.canonical_json.encode("utf-8"),
        "registries/variants.json": var.canonical_json.encode("utf-8"),
        "registries/remotes.json": rem.canonical_json.encode("utf-8"),
    }
    _deterministic_zip_write(zip_path, zip_files)

    return ReleaseBuildResult(
        release_id=release_id,
        created_utc=created,
        manifest_sha256=manifest_sha,
        out_dir=str(out_root),
        manifest_path=str(manifest_path),
        zip_path=str(zip_path),
        registries={
            "components": _registry_record(comp),
            "variants": _registry_record(var),
            "remotes": _registry_record(rem),
        },
    )


def load_release_manifest(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def release_zip_sha256(path: str | Path) -> str:
    p = Path(path)
    return sha256_hex(p.read_bytes())
