from __future__ import annotations

import base64
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional

from .policy import MEAPPolicy, canonical_hash_dict
from .meap_eval import evaluate_bundle_manifest
from .specs import validate_studspec, validate_tubespec
from .provenance import canonical_json, hash_bytes
from .signing import load_public_key
from .dsse import verify_dsse

def sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()

@dataclass
class VerifyResult:
    ok: bool
    reason: str
    toolchain_id: Optional[str] = None
    bundle_map_hash: Optional[str] = None
    policy_hash_expected: Optional[str] = None
    policy_hash_seen: Optional[str] = None
    allowlist_hash_expected: Optional[str] = None
    allowlist_hash_seen: Optional[str] = None
    meap_findings: Optional[list] = None
    artifact_types_seen: Optional[list] = None
    studspec_issues: Optional[list] = None
    tubespec_issues: Optional[list] = None


def _is_safe_member_name(name: str) -> bool:
    """Strict zip member name validation.

    - No absolute paths
    - No backslashes
    - No '.' or '..' path segments
    - No Windows drive prefixes (e.g. C:...)
    """
    if not isinstance(name, str) or not name:
        return False
    if "\\" in name:
        return False
    # Normalize by stripping a trailing slash (zip directory entries)
    is_dir = name.endswith("/")
    nn = name[:-1] if is_dir else name
    if not nn:
        return False
    if nn.startswith("/"):
        return False
    p = PurePosixPath(nn)
    # Reject Windows drive prefixes like "C:..."
    if p.parts and ":" in p.parts[0]:
        return False
    # Reject dot segments and traversal
    for part in p.parts:
        if part in (".", "..", ""):
            return False
    # Reject weird normalizations (e.g. repeated slashes)
    if str(p) != nn:
        return False
    return True

def _read_zip_bytes(z: zipfile.ZipFile, name: str) -> bytes:
    with z.open(name, "r") as f:
        return f.read()

def _calc_bundle_map_hash(files_map: Dict[str, str]) -> str:
    import hashlib
    h = hashlib.sha256()
    for name in sorted(files_map.keys()):
        h.update(name.encode("utf-8"))
        h.update(b"=")
        h.update(str(files_map[name]).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()

def verify_bundle(zip_path: Path, *, policy: MEAPPolicy, allowlist: Dict[str, Any]) -> VerifyResult:
    zip_path = Path(zip_path).resolve()
    if not zip_path.exists():
        return VerifyResult(False, "missing_bundle")

    thr = policy.thresholds
    max_mb = int(thr.get("max_bundle_mb", 250))
    max_files = int(thr.get("max_files_in_bundle", 20000))
    require_sig = bool(thr.get("require_signature", True))
    require_manifest_hashes = bool(thr.get("require_manifest_hashes", True))
    require_det = bool(thr.get("require_deterministic_bundle_hash", True))
    require_policy_hash_match = bool(thr.get("require_policy_hash_match", False))
    require_allowlist_hash_match = bool(thr.get("require_allowlist_hash_match", False))
    require_dsse = bool(thr.get("require_dsse_attestations", False))
    require_cdx = bool(thr.get("require_cyclonedx_sbom", False))

    # normalize allowlist (strip helper keys)
    allow_for_hash = {k:v for k,v in allowlist.items() if k != "_base_dir"}
    allow_hash_expected = canonical_hash_dict(allow_for_hash)

    pol_hash_expected = policy.canonical_hash()

    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()

        # Harden: reject unsafe paths and duplicate file members.
        file_names = [n for n in names if isinstance(n, str) and n and not n.endswith("/")]
        if len(set(file_names)) != len(file_names):
            return VerifyResult(False, "duplicate_zip_members")
        for n in names:
            if not _is_safe_member_name(str(n)):
                return VerifyResult(False, f"unsafe_zip_member:{n}")

        # basic limits
        total_bytes = sum([z.getinfo(n).file_size for n in names])
        if total_bytes > max_mb * 1024 * 1024:
            return VerifyResult(False, "bundle_too_large")
        if len(names) > max_files:
            return VerifyResult(False, "too_many_files")

        # protected paths (defensive)
        prot = policy.protected_paths
        for n in names:
            for p in prot:
                if n.startswith(p.rstrip("/") + "/") or n == p.rstrip("/"):
                    return VerifyResult(False, f"protected_path:{p}")

        # presence
        if "manifest.json" not in names:
            return VerifyResult(False, "missing_manifest")
        if "attestation.json" not in names:
            return VerifyResult(False, "missing_attestation")
        if require_sig and "attestation.sig" not in names:
            return VerifyResult(False, "missing_signature")

        # Strict mandatory (DSSE + CycloneDX)
        if require_cdx:
            if "sbom/bom.cdx.json" not in names:
                return VerifyResult(False, "missing_cyclonedx_sbom")
            if "sbom/bom.dsse.json" not in names:
                return VerifyResult(False, "missing_cyclonedx_dsse")
        if require_dsse and "attestation.dsse.json" not in names:
            return VerifyResult(False, "missing_dsse_attestation")

        manifest_bytes = _read_zip_bytes(z, "manifest.json")
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except Exception:
            return VerifyResult(False, "manifest_parse_error")

        files_map = manifest.get("files") or {}
        toolchain_id = manifest.get("toolchain_id")

        if not isinstance(files_map, dict):
            return VerifyResult(False, "manifest_files_not_dict", toolchain_id=toolchain_id)

        # Harden: ensure manifest file names are safe and present, and reject any
        # zip members not explicitly covered by the manifest (or meta).
        for fname in files_map.keys():
            if not _is_safe_member_name(str(fname)) or str(fname).endswith("/"):
                return VerifyResult(False, f"unsafe_manifest_name:{fname}", toolchain_id=toolchain_id)
        # Bundle meta files are allowed to exist outside the manifest's files map.
        # (Including them in the manifest would create circular hashing dependencies.)
        allowed_meta = {
            "manifest.json",
            "attestation.json",
            "attestation.sig",
            "attestation.dsse.json",
            "sbom/bom.dsse.json",
        }
        allowed_files = set(map(str, files_map.keys())) | allowed_meta
        for n in file_names:
            if n not in allowed_files:
                return VerifyResult(False, f"unexpected_zip_member:{n}", toolchain_id=toolchain_id)

        # validate file hashes per manifest
        if require_manifest_hashes:
            for fname, expected in files_map.items():
                if fname not in names:
                    return VerifyResult(False, f"manifest_file_missing:{fname}", toolchain_id=toolchain_id)
                got = sha256_bytes(_read_zip_bytes(z, fname))
                if got != expected:
                    return VerifyResult(False, f"hash_mismatch:{fname}", toolchain_id=toolchain_id)

        # deterministic bundle map hash
        bundle_map_hash = _calc_bundle_map_hash(files_map)
        if require_det:
            if str(manifest.get("bundle_map_hash") or "") != bundle_map_hash:
                return VerifyResult(False, "bundle_map_hash_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # attestation checks (bind manifest + hashes)
        att_bytes = _read_zip_bytes(z, "attestation.json")
        try:
            att = json.loads(att_bytes.decode("utf-8"))
        except Exception:
            return VerifyResult(False, "attestation_parse_error", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # verify bundle_map_hash matches
        if require_det and str(att.get("bundle_map_hash") or "") != bundle_map_hash:
            return VerifyResult(False, "attestation_bundle_map_hash_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # manifest hash binding
        manifest_hash = sha256_bytes(manifest_bytes)
        if str(att.get("manifest_hash") or "") != manifest_hash:
            return VerifyResult(False, "attestation_manifest_hash_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # policy/allowlist hash binding
        pol_seen = att.get("policy_hash")
        allow_seen = att.get("allowlist_hash")
        if require_policy_hash_match and pol_seen and (str(pol_seen) != pol_hash_expected):
            return VerifyResult(False, "policy_hash_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash,
                                policy_hash_expected=pol_hash_expected, policy_hash_seen=str(pol_seen))
        if require_allowlist_hash_match and allow_seen and (str(allow_seen) != allow_hash_expected):
            return VerifyResult(False, "allowlist_hash_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash,
                                allowlist_hash_expected=allow_hash_expected, allowlist_hash_seen=str(allow_seen))

        # allowlist lookup
        allowed = {x["id"]: x for x in (allowlist.get("allowlist") or {}).get("toolchain_ids", [])}
        if toolchain_id not in allowed:
            return VerifyResult(False, "toolchain_not_allowed", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # verify signature
        if require_sig:
            try:
                sig = base64.b64decode(_read_zip_bytes(z, "attestation.sig").strip())
            except Exception:
                return VerifyResult(False, "bad_signature", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)
            base_dir = Path(allowlist.get("_base_dir") or ".").resolve()
            pub_rel = Path(allowed[toolchain_id]["pubkey_path"])
            pub_path = pub_rel if pub_rel.is_absolute() else (base_dir / pub_rel).resolve()
            pub = load_public_key(pub_path)

            # attestation v2 signs canonical JSON bytes of attestation.json
            ver = str(att.get("attestation_version") or "1")
            try:
                if ver == "2":
                    pub.verify(sig, att_bytes)
                else:
                    # legacy: bundle_map_hash|sbom_hash|provenance_hash
                    sign_msg = (
                        str(att.get("bundle_map_hash") or "") + "|" +
                        str(att.get("sbom_hash") or "") + "|" +
                        str(att.get("provenance_hash") or "")
                    ).encode("utf-8")
                    pub.verify(sig, sign_msg)
            except Exception:
                return VerifyResult(False, "bad_signature", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        # DSSE attestation verification (strict mode)
        if require_dsse or require_cdx:
            base_dir = Path(allowlist.get("_base_dir") or ".").resolve()
            pub_rel = Path(allowed[toolchain_id]["pubkey_path"])
            pub_path = pub_rel if pub_rel.is_absolute() else (base_dir / pub_rel).resolve()
            pub = load_public_key(pub_path)
            expected_kid = sha256_bytes(pub_path.read_bytes())

            # verify build attestation dsse binds manifest
            if require_dsse:
                try:
                    env = json.loads(_read_zip_bytes(z, "attestation.dsse.json").decode("utf-8"))
                    payload = verify_dsse(env, verifier=pub, expected_keyid=expected_kid)
                except Exception as e:
                    return VerifyResult(False, f"dsse_attestation_invalid:{e}", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

                # validate subject manifest digest
                try:
                    subs = payload.get("subject") or []
                    ok_sub = any(
                        (s.get("name") == "manifest.json") and (s.get("digest", {}).get("sha256") == manifest_hash)
                        for s in subs
                    )
                    if not ok_sub:
                        return VerifyResult(False, "dsse_manifest_digest_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)
                except Exception:
                    return VerifyResult(False, "dsse_payload_malformed", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

            # verify sbom dsse binds CycloneDX BOM
            if require_cdx:
                sbom_bytes = _read_zip_bytes(z, "sbom/bom.cdx.json")
                sbom_sha = sha256_bytes(sbom_bytes)
                try:
                    env = json.loads(_read_zip_bytes(z, "sbom/bom.dsse.json").decode("utf-8"))
                    payload = verify_dsse(env, verifier=pub, expected_keyid=expected_kid)
                except Exception as e:
                    return VerifyResult(False, f"dsse_sbom_invalid:{e}", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

                try:
                    subs = payload.get("subject") or []
                    ok_sub = any(
                        (s.get("name") == "sbom/bom.cdx.json") and (s.get("digest", {}).get("sha256") == sbom_sha)
                        for s in subs
                    )
                    if not ok_sub:
                        return VerifyResult(False, "dsse_sbom_digest_mismatch", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)
                except Exception:
                    return VerifyResult(False, "dsse_sbom_payload_malformed", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)


        # MEAP evaluator (artifact-type allowlist, kill-switch)
        ev = evaluate_bundle_manifest(policy, {str(k): str(v) for k, v in files_map.items()})
        if not ev.ok:
            return VerifyResult(
                False,
                "meap_eval_failed",
                toolchain_id=toolchain_id,
                bundle_map_hash=bundle_map_hash,
                policy_hash_expected=pol_hash_expected,
                policy_hash_seen=(str(pol_seen) if pol_seen else None),
                allowlist_hash_expected=allow_hash_expected,
                allowlist_hash_seen=(str(allow_seen) if allow_seen else None),
                meap_findings=[f.__dict__ for f in ev.findings],
                artifact_types_seen=list(ev.artifact_types_seen),
            )

        # Optional: validate embedded StudSpec/TubeSpec if present
        if "studspec.json" in names:
            try:
                stud_obj = json.loads(_read_zip_bytes(z, "studspec.json").decode("utf-8"))
                iss = validate_studspec(stud_obj)
                if iss:
                    return VerifyResult(False, "invalid_studspec", toolchain_id=toolchain_id,
                                        bundle_map_hash=bundle_map_hash, studspec_issues=[i.__dict__ for i in iss])
            except Exception:
                return VerifyResult(False, "invalid_studspec", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        if "tubespec.json" in names:
            try:
                tube_obj = json.loads(_read_zip_bytes(z, "tubespec.json").decode("utf-8"))
                iss = validate_tubespec(tube_obj)
                if iss:
                    return VerifyResult(False, "invalid_tubespec", toolchain_id=toolchain_id,
                                        bundle_map_hash=bundle_map_hash, tubespec_issues=[i.__dict__ for i in iss])
            except Exception:
                return VerifyResult(False, "invalid_tubespec", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash)

        return VerifyResult(True, "ok", toolchain_id=toolchain_id, bundle_map_hash=bundle_map_hash,
                            policy_hash_expected=pol_hash_expected, policy_hash_seen=(str(pol_seen) if pol_seen else None),
                            allowlist_hash_expected=allow_hash_expected, allowlist_hash_seen=(str(allow_seen) if allow_seen else None))
