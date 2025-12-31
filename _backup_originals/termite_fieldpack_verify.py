from __future__ import annotations
import base64
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Tuple

from .policy import MEAPPolicy
from .provenance import hash_str

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

@dataclass
class VerifyResult:
    ok: bool
    reason: str
    toolchain_id: str | None = None
    bundle_map_hash: str | None = None

def _read_zip_bytes(z: zipfile.ZipFile, name: str) -> bytes:
    with z.open(name, "r") as f:
        return f.read()

def _calc_bundle_map_hash(manifest_files: Dict[str, str]) -> str:
    bundle_map = [(k, manifest_files[k]) for k in sorted(manifest_files.keys())]
    return sha256_bytes(json.dumps(bundle_map, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))

def verify_bundle(bundle_path: Path, *, policy: MEAPPolicy, allowlist: Dict[str, Any]) -> VerifyResult:
    p = Path(bundle_path).resolve()
    if not p.exists():
        return VerifyResult(False, "bundle_not_found")

    # size thresholds
    mb = p.stat().st_size / (1024 * 1024)
    if mb > float(policy.thresholds["max_bundle_mb"]):
        return VerifyResult(False, f"bundle_too_large_mb:{mb:.2f}")

    with zipfile.ZipFile(p, "r") as z:
        names = z.namelist()
        if len(names) > int(policy.thresholds["max_files_in_bundle"]):
            return VerifyResult(False, f"too_many_files:{len(names)}")

        if "manifest.json" not in names:
            return VerifyResult(False, "missing_manifest")
        if "attestation.json" not in names:
            return VerifyResult(False, "missing_attestation")
        if "attestation.sig" not in names and bool(policy.thresholds["require_signature"]):
            return VerifyResult(False, "missing_signature")

        manifest = json.loads(_read_zip_bytes(z, "manifest.json").decode("utf-8"))
        files = manifest.get("files", {})
        toolchain_id = manifest.get("toolchain_id")

        # validate manifest hashes
        if bool(policy.thresholds["require_manifest_hashes"]):
            for fname, expected in files.items():
                if fname not in names:
                    return VerifyResult(False, f"manifest_file_missing:{fname}", toolchain_id=toolchain_id)
                data = _read_zip_bytes(z, fname)
                got = sha256_bytes(data)
                if got != expected:
                    return VerifyResult(False, f"hash_mismatch:{fname}", toolchain_id=toolchain_id)

        # deterministic bundle map hash
        bundle_map_hash = _calc_bundle_map_hash(files)
        att = json.loads(_read_zip_bytes(z, "attestation.json").decode("utf-8"))
        if bool(policy.thresholds.get("require_deterministic_bundle_hash", True)):
            if att.get("bundle_map_hash") != bundle_map_hash:
                return VerifyResult(False, "bundle_map_hash_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # allowlist lookup
        allowed = {x["id"]: x for x in allowlist.get("allowlist", {}).get("toolchain_ids", [])}
        if toolchain_id not in allowed:
            return VerifyResult(False, "toolchain_not_allowed", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # verify signature
        if bool(policy.thresholds["require_signature"]):
            sig_b64 = _read_zip_bytes(z, "attestation.sig").strip()
            sig = base64.b64decode(sig_b64)
            # sign_msg structure mirrors seal
            sign_msg = (att["bundle_map_hash"] + "|" + (att.get("sbom_hash") or "") + "|" + (att.get("provenance_hash") or "")).encode("utf-8")
            base_dir = Path(allowlist.get('_base_dir') or '.').resolve()
            pub_rel = Path(allowed[toolchain_id]["pubkey_path"])
            pub_path = pub_rel if pub_rel.is_absolute() else (base_dir / pub_rel).resolve()
            from .signing import load_public_key
            pub = load_public_key(pub_path)
            try:
                pub.verify(sig, sign_msg)
            except Exception:
                return VerifyResult(False, "signature_invalid", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # provenance chain check: lightweight (hash-chain recompute)
        if bool(policy.thresholds["require_provenance_chain_intact"]) and "provenance.jsonl" in names:
            prev = None
            for line in _read_zip_bytes(z, "provenance.jsonl").decode("utf-8").splitlines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                payload = obj["payload"]
                # recompute
                import hashlib
                h = hashlib.sha256()
                h.update((prev or "").encode("utf-8"))
                h.update(b"|")
                h.update(obj["event_type"].encode("utf-8"))
                h.update(b"|")
                h.update(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
                expected = h.hexdigest()
                if expected != obj["event_hash"]:
                    return VerifyResult(False, "provenance_chain_broken", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)
                prev = obj["event_hash"]

    return VerifyResult(True, "ok", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)
