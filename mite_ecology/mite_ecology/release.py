from __future__ import annotations

import json
import time
import zipfile
import hashlib
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


DETERMINISTIC_CREATED_UTC = "1970-01-01T00:00:00Z"


def _utc_iso(ts: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts or time.time()))


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _build_release_cyclonedx_bom(*, release_id: str, manifest_sha256: str, registries: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Build a minimal, deterministic CycloneDX BOM describing the release payload.

    This intentionally avoids environment-derived data (installed packages, timestamps).
    """
    components = []
    for k in sorted(registries.keys()):
        r = registries[k]
        components.append(
            {
                "type": "file",
                "name": f"registries/{k}.json",
                "hashes": [{"alg": "SHA-256", "content": str(r.get("canonical_sha256") or "")}],
            }
        )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "tools": [
                {
                    "vendor": "Fieldgrade",
                    "name": "mite_ecology",
                    "version": "0.1",
                }
            ],
            "properties": [
                {"name": "fieldgrade.release_id", "value": str(release_id)},
                {"name": "fieldgrade.manifest_sha256", "value": str(manifest_sha256)},
            ],
        },
        "components": components,
    }


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
    signing_public_key_path: str | Path | None = None,
    signing_private_key_path: str | Path | None = None,
    include_dsse: bool = False,
    include_cyclonedx: bool = False,
    created_utc: str | None = None,
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

    # Determinism: release artifacts must be byte-stable for identical inputs.
    # Default to a fixed timestamp unless the caller explicitly overrides it.
    created = str(created_utc) if created_utc is not None else DETERMINISTIC_CREATED_UTC

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

    # Optional signed attestations (DSSE) + optional deterministic CycloneDX BOM
    zip_files: Dict[str, bytes] = {
        "manifest.json": manifest_canon.encode("utf-8"),
        "registries/components.json": comp.canonical_json.encode("utf-8"),
        "registries/variants.json": var.canonical_json.encode("utf-8"),
        "registries/remotes.json": rem.canonical_json.encode("utf-8"),
    }

    if include_cyclonedx:
        bom_obj = _build_release_cyclonedx_bom(
            release_id=release_id,
            manifest_sha256=manifest_sha,
            registries={
                "components": _registry_record(comp),
                "variants": _registry_record(var),
                "remotes": _registry_record(rem),
            },
        )
        bom_bytes = canonical_json(bom_obj).encode("utf-8")
        zip_files["sbom/bom.cdx.json"] = bom_bytes

    if include_dsse:
        # Keep DSSE deterministic by requiring an existing signing keypair.
        if not signing_public_key_path or not signing_private_key_path:
            raise ValueError("missing_signing_key_paths")
        pub_path = Path(signing_public_key_path)
        priv_path = Path(signing_private_key_path)
        if not pub_path.exists() or not priv_path.exists():
            raise ValueError("signing_key_paths_must_exist")

        from termite.signing import load_private_key
        from termite.dsse import keyid_for_pubkey_pem, make_intoto_statement, sign_dsse

        pub_pem = pub_path.read_bytes()
        kid = keyid_for_pubkey_pem(pub_pem)
        signer = load_private_key(priv_path)

        # Build DSSE: bind manifest digest
        man_sha = _sha256_bytes(zip_files["manifest.json"])
        build_stmt = make_intoto_statement(
            subjects=[{"name": "manifest.json", "digest": {"sha256": man_sha}}],
            predicate_type="https://mite.ecology/fieldgrade/release/v1",
            predicate={
                "release_id": release_id,
                "manifest_sha256": manifest_sha,
                "created_utc": created,
            },
        )
        build_env = sign_dsse(
            payload_type="application/vnd.in-toto+json",
            payload_obj=build_stmt,
            signer=signer,
            keyid=kid,
        )
        zip_files["attestation.dsse.json"] = (canonical_json(build_env) + "\n").encode("utf-8")

        # SBOM DSSE: bind CycloneDX digest if present
        if "sbom/bom.cdx.json" in zip_files:
            sbom_sha = _sha256_bytes(zip_files["sbom/bom.cdx.json"])
            sbom_stmt = make_intoto_statement(
                subjects=[{"name": "sbom/bom.cdx.json", "digest": {"sha256": sbom_sha}}],
                predicate_type="https://mite.ecology/fieldgrade/release-sbom/v1",
                predicate={
                    "release_id": release_id,
                    "created_utc": created,
                    "sbom_format": "CycloneDX",
                    "sbom_spec_version": "1.5",
                },
            )
            sbom_env = sign_dsse(
                payload_type="application/vnd.in-toto+json",
                payload_obj=sbom_stmt,
                signer=signer,
                keyid=kid,
            )
            zip_files["sbom/bom.dsse.json"] = (canonical_json(sbom_env) + "\n").encode("utf-8")

    zip_path = out_root / f"{release_id}.zip"
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


def verify_release_zip(
    *,
    zip_path: str | Path,
    signing_public_key_path: str | Path | None = None,
    require_dsse: bool = False,
    require_cyclonedx: bool = False,
) -> Dict[str, Any]:
    """Verify structural and cryptographic invariants of a release zip.

    - Always validates manifest sha and release_id relationship.
    - Optionally validates CycloneDX + DSSE attestations if present/required.
    """
    zp = Path(zip_path)
    if not zp.exists() or not zp.is_file():
        raise FileNotFoundError(str(zp))

    with zipfile.ZipFile(zp, mode="r") as zf:
        names = set(zf.namelist())
        required = {
            "manifest.json",
            "registries/components.json",
            "registries/variants.json",
            "registries/remotes.json",
        }
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"missing_files:{','.join(missing)}")

        manifest_bytes = zf.read("manifest.json")
        manifest_obj = json.loads(manifest_bytes.decode("utf-8"))
        manifest_sha = sha256_str(canonical_json(manifest_obj))
        release_id = manifest_sha[:16]
        if zp.stem != release_id:
            raise ValueError("release_id_mismatch")

        # CycloneDX (optional)
        has_cdx = "sbom/bom.cdx.json" in names
        if require_cyclonedx and not has_cdx:
            raise ValueError("missing_cyclonedx")

        # DSSE (optional)
        has_dsse = "attestation.dsse.json" in names
        if require_dsse and not has_dsse:
            raise ValueError("missing_dsse")

        dsse_ok = False
        sbom_dsse_ok = False
        keyid = None

        if has_dsse or ("sbom/bom.dsse.json" in names):
            if not signing_public_key_path:
                raise ValueError("missing_signing_public_key_path")
            pub_path = Path(signing_public_key_path)
            if not pub_path.exists():
                raise ValueError("signing_public_key_not_found")

            from termite.dsse import verify_dsse
            from termite.signing import load_public_key

            pub = load_public_key(pub_path)
            keyid = _sha256_bytes(pub_path.read_bytes())

            if has_dsse:
                env = json.loads(zf.read("attestation.dsse.json").decode("utf-8"))
                payload = verify_dsse(env, verifier=pub, expected_keyid=keyid)
                subj = (payload.get("subject") or [])
                if not isinstance(subj, list) or not subj:
                    raise ValueError("dsse_payload_malformed")
                man_digest = str(subj[0].get("digest", {}).get("sha256") or "")
                if man_digest != _sha256_bytes(manifest_bytes):
                    raise ValueError("dsse_manifest_digest_mismatch")
                dsse_ok = True

            if "sbom/bom.dsse.json" in names:
                if "sbom/bom.cdx.json" not in names:
                    raise ValueError("sbom_dsse_without_bom")
                bom_bytes = zf.read("sbom/bom.cdx.json")
                env = json.loads(zf.read("sbom/bom.dsse.json").decode("utf-8"))
                payload = verify_dsse(env, verifier=pub, expected_keyid=keyid)
                subj = (payload.get("subject") or [])
                if not isinstance(subj, list) or not subj:
                    raise ValueError("dsse_sbom_payload_malformed")
                bom_digest = str(subj[0].get("digest", {}).get("sha256") or "")
                if bom_digest != _sha256_bytes(bom_bytes):
                    raise ValueError("dsse_sbom_digest_mismatch")
                sbom_dsse_ok = True

        return {
            "ok": True,
            "release_id": release_id,
            "manifest_sha256": manifest_sha,
            "zip_sha256": sha256_hex(zp.read_bytes()),
            "has_cyclonedx": bool(has_cdx),
            "dsse_ok": bool(dsse_ok),
            "sbom_dsse_ok": bool(sbom_dsse_ok),
            "keyid": keyid,
        }
