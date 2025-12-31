from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import hashlib


def hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

_SPEC_START = re.compile(r"^\s*COMPONENT_SPEC\s*:\s*$", re.IGNORECASE)
_FIELD = re.compile(r"^\s*-\s*([A-Za-z0-9_ /]+?)\s*:\s*(.*)\s*$")

def sha256_text(text: str) -> str:
    return hash_bytes(text.encode("utf-8"))

def parse_component_spec(prompt_text: str) -> Dict[str, str]:
    lines = prompt_text.splitlines()
    # find COMPONENT_SPEC:
    start = None
    for i, ln in enumerate(lines):
        if _SPEC_START.match(ln):
            start = i + 1
            break
    if start is None:
        return {}
    spec: Dict[str, str] = {}
    for ln in lines[start:]:
        if ln.strip() == "":
            # stop at first blank line after spec section begins
            if spec:
                break
            continue
        m = _FIELD.match(ln)
        if not m:
            # stop when leaving bullet section
            if spec:
                break
            continue
        k = m.group(1).strip()
        v = m.group(2).strip()
        spec[k] = v
    return spec

def build_manifest_from_prompt_cache(prompts_dir: Path) -> List[Dict[str, object]]:
    prompts_dir = Path(prompts_dir).resolve()
    out: List[Dict[str, object]] = []
    for p in sorted(prompts_dir.glob("*.prompt.txt")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        ph = sha256_text(txt)
        spec = parse_component_spec(txt)
        out.append({
            "prompt_file": p.name,
            "prompt_hash": ph,
            "component_spec": spec,
        })
    return out

def write_manifest_jsonl(manifest: List[Dict[str, object]], out_path: Path) -> None:
    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for row in manifest:
        import json
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
