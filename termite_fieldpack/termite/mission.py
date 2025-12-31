from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .config import TermiteConfig, load_config
from .ingest import ingest_path
from .cas import CAS
from .db import connect
from .provenance import Provenance

from .llm_runtime import start as llm_start, stop as llm_stop, ping as llm_ping
from .llm_chat import chat as llm_chat
from .bundle import SealInputs, build_bundle
from .verify import verify_bundle
from .replay import replay_bundle
from .policy import load_policy, canonical_hash_dict
from .tools import run_tool, load_allowlist

def run_mission(mission_yaml: Path, *, config_path: Optional[Path] = None) -> Dict[str, Any]:
    obj = yaml.safe_load(mission_yaml.read_text(encoding="utf-8")) or {}
    cfg_path = config_path or Path(obj.get("config") or "config/termite.yaml")
    cfg = load_config(cfg_path)

    cas = CAS(cfg.cas_root); cas.init()
    con = connect(cfg.db_path)
    prov = Provenance(cfg.toolchain_id)

    steps = obj.get("steps") or []
    results = {"mission": str(mission_yaml), "steps": []}

    for step in steps:
        kind = step.get("kind")
        if kind == "ingest":
            path = Path(step["path"])
            res = ingest_path(con, cas, prov, path, max_bytes=cfg.max_bytes, extract_text=cfg.extract_text, chunk_chars=cfg.chunk_chars)
            results["steps"].append({"kind": "ingest", "path": str(path), "result": res})
        elif kind == "llm_start":
            r = llm_start(cfg, force=bool(step.get("force", False)))
            results["steps"].append({"kind": "llm_start", "result": r})
        elif kind == "llm_ping":
            r = llm_ping(cfg)
            results["steps"].append({"kind": "llm_ping", "result": r})
        elif kind == "llm_stop":
            r = llm_stop(cfg)
            results["steps"].append({"kind": "llm_stop", "result": r})
        elif kind == "llm_chat":
            prompt = str(step.get("prompt") or "")
            r = llm_chat(cfg, prompt, temperature=step.get("temperature"), max_tokens=step.get("max_tokens"), store=True)
            results["steps"].append({"kind": "llm_chat", "result": {"prompt_hash": r.get("prompt_hash"), "call_hash": r.get("call_hash")}})
        elif kind == "tool_run":
            tool_id = str(step["tool_id"])
            argv = [str(a) for a in (step.get("argv") or [])]
            allowlist = Path(step.get("allowlist") or "config/tool_allowlist.yaml")
            r = run_tool(cfg, tool_id, argv, allowlist)
            results["steps"].append({"kind": "tool_run", "result": r})
        elif kind == "seal":
            label = str(step.get("label") or "mission")
            # Bind seal to the same policy+allowlist in force for verification.
            # This lets downstream verifiers optionally require hash matches.
            pol_path = Path(step.get("policy") or cfg.policy_path)
            allow_path = Path(step.get("allowlist") or cfg.allowlist_path)
            pol = load_policy(pol_path)
            allow = load_allowlist(allow_path)
            allow_for_hash = {k: v for k, v in allow.items() if k != "_base_dir"}
            inp = SealInputs(
                toolchain_id=cfg.toolchain_id,
                cas=cas,
                db_path=cfg.db_path,
                bundles_out=cfg.bundles_out,
                include_raw=cfg.include_raw,
                include_extract=cfg.include_extract,
                include_aux=bool(getattr(cfg, "include_aux", True)),
                include_provenance=cfg.include_provenance,
                include_sbom=cfg.include_sbom,
                include_kg_delta=cfg.include_kg_delta,
                deterministic_zip=cfg.deterministic_zip,
                policy_hash=pol.canonical_hash(),
                allowlist_hash=canonical_hash_dict(allow_for_hash),
                signing_enabled=cfg.signing_enabled,
                signing_algorithm=cfg.signing_algorithm,
                signing_priv=cfg.signing_private_key_path,
                signing_pub=cfg.signing_public_key_path,
            )
            out = build_bundle(inp, label=label)
            results["steps"].append({"kind": "seal", "bundle": str(out)})
        elif kind == "verify":
            pol = load_policy(Path(step.get("policy") or "config/meap_v1.yaml"))
            allow = load_allowlist(Path(step.get("allowlist") or "config/tool_allowlist.yaml"))
            bundle = Path(step["bundle"])
            vr = verify_bundle(bundle, policy=pol, allowlist=allow)
            results["steps"].append({"kind": "verify", "ok": vr.ok, "reason": vr.reason})
        elif kind == "replay":
            pol = load_policy(Path(step.get("policy") or "config/meap_v1.yaml"))
            allow = load_allowlist(Path(step.get("allowlist") or "config/tool_allowlist.yaml"))
            bundle = Path(step["bundle"])
            rr = replay_bundle(bundle, policy=pol, allowlist=allow)
            results["steps"].append({"kind": "replay", "ok": rr.ok, "reason": rr.reason, "summary": rr.summary})
        else:
            raise RuntimeError(f"Unknown mission step kind: {kind}")

    return results
