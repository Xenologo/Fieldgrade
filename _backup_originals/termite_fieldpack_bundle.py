from __future__ import annotations
import base64
import hashlib
import io
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .cas import CAS
from .provenance import canonical_json, hash_bytes, hash_str, utc_now_iso
from .sbom import build_min_sbom
from .signing import load_or_create

FIXED_ZIP_DT = (1980, 1, 1, 0, 0, 0)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

@dataclass
class SealInputs:
    toolchain_id: str
    cas: CAS
    db_path: Path
    bundles_out: Path
    signing_priv: Path
    signing_pub: Path
    include_raw: bool
    include_extract: bool
    include_provenance: bool
    include_sbom: bool
    include_kg_delta: bool
    deterministic_zip: bool

def _zip_write_bytes(z: zipfile.ZipFile, arcname: str, data: bytes, *, deterministic: bool) -> None:
    zi = zipfile.ZipInfo(arcname)
    if deterministic:
        zi.date_time = FIXED_ZIP_DT
    zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, data)

def _zip_write_file(z: zipfile.ZipFile, arcname: str, path: Path, *, deterministic: bool) -> None:
    data = path.read_bytes()
    _zip_write_bytes(z, arcname, data, deterministic=deterministic)

def build_bundle(
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

    # Build files in-memory first for manifest consistency
    files: List[Tuple[str, bytes]] = []
    # core metadata
    sbom = build_min_sbom() if inp.include_sbom else None
    sbom_bytes = (canonical_json(sbom).encode("utf-8") + b"\n") if sbom is not None else b""
    prov_bytes = provenance_jsonl.encode("utf-8") if inp.include_provenance else b""
    kg_bytes = kg_delta_jsonl.encode("utf-8") if inp.include_kg_delta else b""

    if sbom is not None:
        files.append(("sbom.json", sbom_bytes))
    if inp.include_provenance:
        files.append(("provenance.jsonl", prov_bytes))
    if inp.include_kg_delta:
        files.append(("kg_delta.jsonl", kg_bytes))

    # include blobs referenced by docs table
    raw_blobs = set()
    ext_blobs = set()
    for r in con.execute("SELECT raw_blob_sha256, extract_blob_sha256 FROM docs").fetchall():
        raw_blobs.add(str(r["raw_blob_sha256"]))
        if r["extract_blob_sha256"]:
            ext_blobs.add(str(r["extract_blob_sha256"]))

    if inp.include_raw:
        for sha in sorted(raw_blobs):
            p = inp.cas.blobs_dir / sha
            if p.exists():
                files.append((f"blobs/sha256/{sha}", p.read_bytes()))
    if inp.include_extract:
        for sha in sorted(ext_blobs):
            p = inp.cas.extracts_dir / sha
            if p.exists():
                files.append((f"extracts/sha256/{sha}", p.read_bytes()))
    if inp.include_aux:
        for sha in sorted(aux_blobs):
            p = inp.cas.aux_dir / sha
            if p.exists():
                files.append((f"aux/sha256/{sha}", p.read_bytes()))

    # manifest
    manifest: Dict[str, str] = {name: sha256_bytes(data) for name, data in files}
    manifest_obj = {
        "manifest_version":"1",
        "toolchain_id": inp.toolchain_id,
        "label": label,
        "generated_utc": utc_now_iso(),
        "files": manifest,
    }
    manifest_bytes = canonical_json(manifest_obj).encode("utf-8") + b"\n"
    files.append(("manifest.json", manifest_bytes))

    # deterministic bundle hash is hash of (sorted filename + filehash)
    bundle_map = [(k, manifest[k]) for k in sorted(manifest.keys())]
    bundle_hash = sha256_bytes(canonical_json(bundle_map).encode("utf-8"))

    sbom_hash = sha256_bytes(sbom_bytes) if sbom is not None else None
    provenance_hash = sha256_bytes(prov_bytes) if inp.include_provenance else None

    attestation = {
        "attestation_version":"1",
        "toolchain_id": inp.toolchain_id,
        "label": label,
        "bundle_map_hash": bundle_hash,
        "sbom_hash": sbom_hash,
        "provenance_hash": provenance_hash,
        "manifest_hash": sha256_bytes(manifest_bytes),
        "created_utc": utc_now_iso(),
        "algo": "ed25519",
    }
    att_bytes = canonical_json(attestation).encode("utf-8") + b"\n"
    files.append(("attestation.json", att_bytes))

    # sign the concatenation of key hashes
    kp = load_or_create(inp.signing_priv, inp.signing_pub)
    sign_msg = (attestation["bundle_map_hash"] + "|" + (sbom_hash or "") + "|" + (provenance_hash or "")).encode("utf-8")
    sig = kp.sign(sign_msg)
    files.append(("attestation.sig", base64.b64encode(sig) + b"\n"))

    # write zip deterministically (sorted by arcname)
    with zipfile.ZipFile(out_path, "w") as z:
        for name, data in sorted(files, key=lambda x: x[0]):
            _zip_write_bytes(z, name, data, deterministic=inp.deterministic_zip)

    return out_path
