from __future__ import annotations

"""DSSE (Dead Simple Signing Envelope) helpers.

We use DSSE to sign in-toto Statement payloads for:
  - SBOM attestations (CycloneDX JSON)
  - Bundle/build attestations (binding manifest hash + governance hashes)

This module intentionally does *not* depend on external DSSE libraries.
"""

import base64
import hashlib
import json
from typing import Any, Dict, Optional


DSSE_V1 = b"DSSEv1"


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("utf-8"))


def pae(payload_type: str, payload: bytes) -> bytes:
    """Pre-Authentication Encoding (PAE) for DSSEv1.

    Format:
      "DSSEv1" SP LEN(payloadType) SP payloadType SP LEN(payload) SP payload
    where LEN are ASCII decimal lengths.
    """
    pt = payload_type.encode("utf-8")
    return b"".join(
        [
            DSSE_V1,
            b" ",
            str(len(pt)).encode("utf-8"),
            b" ",
            pt,
            b" ",
            str(len(payload)).encode("utf-8"),
            b" ",
            payload,
        ]
    )


def keyid_for_pubkey_pem(pub_pem: bytes) -> str:
    """Stable key id derived from the PEM bytes (sha256 hex)."""
    return hashlib.sha256(pub_pem).hexdigest()


def envelope(
    *,
    payload_type: str,
    payload_bytes: bytes,
    sig_bytes: bytes,
    keyid: str,
) -> Dict[str, Any]:
    return {
        "payloadType": payload_type,
        "payload": _b64e(payload_bytes),
        "signatures": [{"keyid": str(keyid), "sig": _b64e(sig_bytes)}],
    }


def sign_dsse(
    *,
    payload_type: str,
    payload_obj: Dict[str, Any],
    signer,  # Ed25519PrivateKey-like .sign(bytes)->bytes
    keyid: str,
) -> Dict[str, Any]:
    payload_bytes = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = signer.sign(pae(payload_type, payload_bytes))
    return envelope(payload_type=payload_type, payload_bytes=payload_bytes, sig_bytes=sig, keyid=keyid)


def verify_dsse(
    env: Dict[str, Any],
    *,
    verifier,  # Ed25519PublicKey-like .verify(sig, msg)->None
    expected_keyid: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify DSSE envelope and return decoded payload object.

    Raises ValueError on failure.
    """
    if not isinstance(env, dict):
        raise ValueError("dsse_not_dict")
    payload_type = env.get("payloadType")
    payload_b64 = env.get("payload")
    sigs = env.get("signatures")
    if not isinstance(payload_type, str) or not payload_type:
        raise ValueError("dsse_missing_payloadType")
    if not isinstance(payload_b64, str) or not payload_b64:
        raise ValueError("dsse_missing_payload")
    if not isinstance(sigs, list) or not sigs:
        raise ValueError("dsse_missing_signatures")

    payload_bytes = _b64d(payload_b64)
    msg = pae(payload_type, payload_bytes)

    # Accept first signature that verifies.
    last_err = None
    for s in sigs:
        try:
            keyid = str(s.get("keyid") or "")
            if expected_keyid and keyid != expected_keyid:
                raise ValueError("dsse_keyid_mismatch")
            sig = _b64d(str(s.get("sig") or ""))
            verifier.verify(sig, msg)
            # Verified; return payload
            return json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            last_err = e
            continue

    raise ValueError(f"dsse_bad_signature:{last_err}")


def make_intoto_statement(
    *,
    subjects: list[dict[str, Any]],
    predicate_type: str,
    predicate: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": str(predicate_type),
        "predicate": dict(predicate),
    }
