from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .cas import CAS
from .db import connect, export_kg_ops_jsonl, export_provenance_jsonl
from .provenance import canonical_json, hash_bytes, hash_str, utc_now_iso
from .sbom import build_cyclonedx_bom
from .signing import load_or_create
from .dsse import (
    keyid_for_pubkey_pem,
    make_intoto_statement,
    sign_dsse,
)

# Deterministic ZIP timestamp (1980-01-01 00:00:00) per ZIP epoch
FIXED_ZIP_DT: Tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)

def _zip_write_bytes(z: zipfile.ZipFile, arcname: str, data: bytes, *, deterministic: bool) -> None:
    zi = zipfile.ZipInfo(arcname)
    if deterministic:
        zi.date_time = FIXED_ZIP_DT
    zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, data)

def _zip_write_file(z: zipfile.ZipFile, arcname: str, path: Path, *, deterministic: bool) -> None:
    data = path.read_bytes()
    _zip_write_bytes(z, arcname, data, deterministic=deterministic)

def _calc_bundle_map_hash(files_map: dict) -> str:
    """Hash of the bundle file-map: sha256 over sorted name=hash lines."""
    h = hashlib.sha256()
    for name in sorted(files_map.keys()):
        h.update(name.encode("utf-8"))
        h.update(b"=")
        h.update(str(files_map[name]).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()

@dataclass
class SealInputs:
    toolchain_id: str
    cas: CAS
    db_path: Path
    bundles_out: Path

    # signing material
    signing_priv: Path
    signing_pub: Path
    signing_enabled: bool = True

    # inclusion flags
    include_raw: bool = True
    include_extract: bool = True
    include_aux: bool = True
    include_provenance: bool = True
    include_sbom: bool = True
    include_kg_delta: bool = True
    deterministic_zip: bool = True

    # audit binding
    policy_hash: Optional[str] = None
    allowlist_hash: Optional[str] = None

SPECIAL_AUX_TO_ROOT = {"studspec.json", "tubespec.json", "brick_passport.json"}


def build_bundle(
    inp: SealInputs,
    *,
    label: str,
) -> Path:
    """Convenience wrapper: exports provenance + kg_delta from the Termite DB and seals a deterministic bundle."""
    con = connect(inp.db_path)
    prov_jsonl = export_provenance_jsonl(con) if inp.include_provenance else ""
    kg_delta_jsonl = export_kg_ops_jsonl(con) if inp.include_kg_delta else ""
    return build_bundle_from_parts(con, inp, label=label, provenance_jsonl=prov_jsonl, kg_delta_jsonl=kg_delta_jsonl)

def build_bundle_from_parts(
    con,
    inp: SealInputs,
    *,
    label: str,
    provenance_jsonl: str,
    kg_delta_jsonl: str,
) -> Path:
    inp.bundles_out.mkdir(parents=True, exist_ok=True)
    bundle_name = f"termite_bundle_{label}_{utc_now_iso().replace(':','').replace('-','')}.zip"
    out_path = (inp.bundles_out / bundle_name).resolve()

    files: List[Tuple[str, bytes]] = []

    # -------------------------
    # Include CAS content
    # -------------------------
    if inp.include_raw and inp.cas.blobs_dir.exists():
        for p in sorted(inp.cas.blobs_dir.glob("*")):
            if p.is_file():
                files.append((f"cas/raw/{p.name}", p.read_bytes()))
    if inp.include_extract and inp.cas.extracts_dir.exists():
        for p in sorted(inp.cas.extracts_dir.glob("*")):
            if p.is_file():
                files.append((f"cas/extract/{p.name}", p.read_bytes()))
    if inp.include_aux and inp.cas.aux_dir.exists():
        for p in sorted(inp.cas.aux_dir.glob("*")):
            if p.is_file():
                files.append((f"cas/aux/{p.name}", p.read_bytes()))

    # -------------------------
    # Include provenance + kg_delta (JSONL)
    # -------------------------
    provenance_hash: Optional[str] = None
    if inp.include_provenance:
        prov_bytes = provenance_jsonl.encode("utf-8")
        provenance_hash = hash_bytes(prov_bytes)
        files.append(("provenance.jsonl", prov_bytes + (b"\n" if not prov_bytes.endswith(b"\n") and prov_bytes else b"")))

    kg_delta_hash: Optional[str] = None
    if inp.include_kg_delta:
        delta_bytes = kg_delta_jsonl.encode("utf-8")
        kg_delta_hash = hash_bytes(delta_bytes)
        files.append(("kg_delta.jsonl", delta_bytes + (b"\n" if not delta_bytes.endswith(b"\n") and delta_bytes else b"")))

    # -------------------------
    # Include SBOM (CycloneDX JSON) + DSSE attestation
    # -------------------------
    sbom_hash: Optional[str] = None
    if inp.include_sbom:
        sbom_obj = build_cyclonedx_bom()
        sbom_bytes = (canonical_json(sbom_obj) + "\n").encode("utf-8")
        sbom_hash = hash_bytes(sbom_bytes)
        files.append(("sbom/bom.cdx.json", sbom_bytes))

    # -------------------------
    # Build manifest (hashes of included files)
    # -------------------------
    files_map = {name: hash_bytes(data) for (name, data) in files}
    manifest_obj = {
        "manifest_version": "2",
        "toolchain_id": inp.toolchain_id,
        "created_utc": utc_now_iso(),
        "files": files_map,
        "bundle_map_hash": _calc_bundle_map_hash(files_map),
        "policy_hash": inp.policy_hash,
        "allowlist_hash": inp.allowlist_hash,
        "sbom_hash": sbom_hash,
        "provenance_hash": provenance_hash,
        "kg_delta_hash": kg_delta_hash,
    }
    manifest_bytes = (canonical_json(manifest_obj) + "\n").encode("utf-8")
    manifest_hash = hash_bytes(manifest_bytes)
    files.append(("manifest.json", manifest_bytes))

    # -------------------------
    # Attestation (legacy JSON + signature)
    # -------------------------
    attestation = {
        "attestation_version": "2",
        "toolchain_id": inp.toolchain_id,
        "label": label,
        "bundle_map_hash": manifest_obj["bundle_map_hash"],
        "manifest_hash": manifest_hash,
        "policy_hash": inp.policy_hash,
        "allowlist_hash": inp.allowlist_hash,
        "sbom_hash": sbom_hash,
        "provenance_hash": provenance_hash,
        "kg_delta_hash": kg_delta_hash,
        "created_utc": utc_now_iso(),
        "algo": "ed25519",
        "signing_schema": "ed25519_canonical_attestation_v2",
    }
    att_bytes = (canonical_json(attestation) + "\n").encode("utf-8")
    files.append(("attestation.json", att_bytes))

    if inp.signing_enabled:
        kp = load_or_create(inp.signing_priv, inp.signing_pub)
        sig = kp.sign(att_bytes)
        files.append(("attestation.sig", base64.b64encode(sig) + b"\n"))

    # -------------------------
    # DSSE attestations (strict mode consumers rely on these)
    # -------------------------
    if inp.signing_enabled:
        kp = load_or_create(inp.signing_priv, inp.signing_pub)
        pub_pem = inp.signing_pub.read_bytes()
        kid = keyid_for_pubkey_pem(pub_pem)

        # SBOM DSSE (bind the CycloneDX JSON)
        if inp.include_sbom and sbom_hash:
            sbom_stmt = make_intoto_statement(
                subjects=[{"name": "sbom/bom.cdx.json", "digest": {"sha256": sbom_hash}}],
                predicate_type="https://mite.ecology/termite/sbom/v1",
                predicate={
                    "toolchain_id": inp.toolchain_id,
                    "created_utc": utc_now_iso(),
                    "sbom_format": "CycloneDX",
                    "sbom_spec_version": str(sbom_obj.get("specVersion") or ""),
                },
            )
            sbom_env = sign_dsse(
                payload_type="application/vnd.in-toto+json",
                payload_obj=sbom_stmt,
                signer=kp.private_key,
                keyid=kid,
            )
            files.append(("sbom/bom.dsse.json", (canonical_json(sbom_env) + "\n").encode("utf-8")))

        # Build DSSE (bind manifest + governance hashes)
        build_stmt = make_intoto_statement(
            subjects=[{"name": "manifest.json", "digest": {"sha256": manifest_hash}}],
            predicate_type="https://mite.ecology/termite/attestation/v1",
            predicate={
                "toolchain_id": inp.toolchain_id,
                "label": label,
                "created_utc": utc_now_iso(),
                "bundle_map_hash": manifest_obj["bundle_map_hash"],
                "policy_hash": inp.policy_hash,
                "allowlist_hash": inp.allowlist_hash,
                "sbom_sha256": sbom_hash,
                "provenance_sha256": provenance_hash,
                "kg_delta_sha256": kg_delta_hash,
            },
        )
        build_env = sign_dsse(
            payload_type="application/vnd.in-toto+json",
            payload_obj=build_stmt,
            signer=kp.private_key,
            keyid=kid,
        )
        files.append(("attestation.dsse.json", (canonical_json(build_env) + "\n").encode("utf-8")))

    # -------------------------
    # Write zip deterministically (sorted by arcname)
    # -------------------------
    with zipfile.ZipFile(out_path, "w") as z:
        for name, data in sorted(files, key=lambda x: x[0]):
            _zip_write_bytes(z, name, data, deterministic=inp.deterministic_zip)

    return out_path
