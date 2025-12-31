from __future__ import annotations
import hashlib, json
from typing import Any

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_str(s: str) -> str:
    return sha256_hex(s.encode("utf-8"))

def stable_edge_key(src: str, dst: str, etype: str, attrs: Any) -> str:
    payload = {"src":src,"dst":dst,"type":etype,"attrs":attrs}
    return sha256_str(canonical_json(payload))
