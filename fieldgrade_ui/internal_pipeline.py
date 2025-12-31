from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

import yaml


def _safe_resolve(p: Path) -> Path:
    p = Path(p).expanduser()
    try:
        return p.resolve(strict=False)
    except Exception:
        try:
            return p.resolve()
        except Exception:
            return p


def _expand(s: str) -> str:
    return os.path.expandvars(os.path.expanduser(str(s)))


def _resolve_config_path_value(base_dir: Path, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    raw = _expand(value)
    p = Path(raw)
    if not p.is_absolute():
        p = base_dir / p
    return str(_safe_resolve(p))


def _set_path(raw: dict[str, Any], key_path: list[str], base_dir: Path) -> None:
    d: Any = raw
    for k in key_path[:-1]:
        if not isinstance(d, dict) or k not in d:
            return
        d = d[k]
    if not isinstance(d, dict):
        return
    last = key_path[-1]
    if last not in d:
        return
    d[last] = _resolve_config_path_value(base_dir, d[last])


def _load_termite_config(config_path: Path):
    from termite.config import TermiteConfig

    p = _safe_resolve(Path(config_path))
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "termite" not in raw:
        raise ValueError("invalid_config: missing top-level 'termite' key")
    base_dir = p.parent

    for kp in [
        ["termite", "runtime_root"],
        ["termite", "cas_root"],
        ["termite", "db_path"],
        ["termite", "bundles_out"],
        ["termite", "policy_path"],
        ["termite", "allowlist_path"],
        ["toolchain", "signing", "private_key_path"],
        ["toolchain", "signing", "public_key_path"],
    ]:
        _set_path(raw, kp, base_dir)

    return TermiteConfig(raw)


def _load_ecology_config(config_path: Path):
    from mite_ecology.config import EcologyConfig

    p = _safe_resolve(Path(config_path))
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if "mite_ecology" not in raw:
        raise ValueError("invalid_config: missing top-level 'mite_ecology' key")
    base_dir = p.parent

    for kp in [
        ["mite_ecology", "runtime_root"],
        ["mite_ecology", "db_path"],
        ["mite_ecology", "imports_root"],
        ["mite_ecology", "exports_root"],
        ["mite_ecology", "policy_path"],
        ["mite_ecology", "allowlist_path"],
        ["mite_ecology", "schemas_dir"],
    ]:
        _set_path(raw, kp, base_dir)

    return EcologyConfig(raw)


def _default_context_node(con) -> str:
    row = con.execute("SELECT id FROM nodes WHERE type='Task' LIMIT 1").fetchone()
    if row:
        return str(row["id"])
    row = con.execute("SELECT id FROM nodes LIMIT 1").fetchone()
    if not row:
        raise RuntimeError("KG is empty. Import a bundle or ingest nodes first.")
    return str(row["id"])


def run_termite_to_ecology_pipeline_library(
    repo_root: Path,
    *,
    upload_path: Path,
    label: str,
    policy_path: Optional[Path] = None,
    allowlist_path: Optional[Path] = None,
    termite_config_path: Optional[Path] = None,
    ecology_config_path: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """Run the termite->ecology pipeline in-process (no subprocess).

    This is intended as a Phase A5 boundary-hardening step. It preserves existing
    semantics by reusing the same underlying library calls as the CLIs.
    """

    repo_root = _safe_resolve(repo_root)
    upload_path = _safe_resolve(upload_path)
    if not upload_path.exists():
        raise FileNotFoundError(str(upload_path))

    # Resolve config paths
    if termite_config_path is None:
        termite_config_path = repo_root / "termite_fieldpack" / "config" / "termite.yaml"
    if ecology_config_path is None:
        ecology_config_path = repo_root / "mite_ecology" / "configs" / "ecology.yaml"

    t_cfg = _load_termite_config(termite_config_path)
    e_cfg = _load_ecology_config(ecology_config_path)

    # termite imports
    from termite.cas import CAS
    from termite.db import connect as t_connect
    from termite.ingest import ingest_path
    from termite.provenance import Provenance
    from termite.bundle import SealInputs, build_bundle
    from termite.policy import load_policy, canonical_hash_dict
    from termite.verify import verify_bundle
    from termite.replay import replay_bundle

    # mite_ecology imports
    from mite_ecology.db import connect as e_connect, init_db as e_init_db
    from mite_ecology.bundle_accept import accept_termite_bundle, AcceptPolicy
    from mite_ecology.replay import replay_verify
    from mite_ecology.kg import KnowledgeGraph
    from mite_ecology.auto import autorun, AutoRunConfig
    from mite_ecology.hashutil import sha256_str, canonical_json

    # ------------------------
    # 1) termite ingest
    # ------------------------
    if log:
        log(f"pipeline(lib): upload_path={upload_path}")
        log(f"pipeline(lib): label={label}")

    cas = CAS(t_cfg.cas_root)
    cas.init()
    t_con = t_connect(t_cfg.db_path)
    prov = Provenance(t_cfg.toolchain_id)
    ingest_res = ingest_path(
        t_con,
        cas,
        prov,
        upload_path,
        max_bytes=t_cfg.max_bytes,
        extract_text=t_cfg.extract_text,
        chunk_chars=t_cfg.chunk_chars,
        overlap_chars=t_cfg.overlap_chars,
        min_chunk_chars=t_cfg.min_chunk_chars,
    )

    # ------------------------
    # 2) termite seal
    # ------------------------
    pol_path = _safe_resolve(policy_path) if policy_path is not None else t_cfg.policy_path
    allow_path = _safe_resolve(allowlist_path) if allowlist_path is not None else t_cfg.allowlist_path

    pol = load_policy(pol_path)
    allow = yaml.safe_load(allow_path.read_text(encoding="utf-8")) or {}
    allow["_base_dir"] = str(allow_path.resolve().parent)
    allow_for_hash = {k: v for k, v in allow.items() if k != "_base_dir"}

    inp = SealInputs(
        toolchain_id=t_cfg.toolchain_id,
        cas=cas,
        db_path=t_cfg.db_path,
        bundles_out=t_cfg.bundles_out,
        signing_priv=t_cfg.signing_private_key_path,
        signing_pub=t_cfg.signing_public_key_path,
        signing_enabled=t_cfg.signing_enabled,
        include_raw=t_cfg.include_raw,
        include_extract=t_cfg.include_extract,
        include_aux=t_cfg.include_aux,
        include_provenance=t_cfg.include_provenance,
        include_sbom=t_cfg.include_sbom,
        include_kg_delta=t_cfg.include_kg_delta,
        deterministic_zip=t_cfg.deterministic_zip,
        policy_hash=pol.canonical_hash(),
        allowlist_hash=canonical_hash_dict(allow_for_hash),
    )
    bundle_path = build_bundle(inp, label=label)

    # ------------------------
    # 3) termite verify + replay
    # ------------------------
    vr = verify_bundle(bundle_path, policy=pol, allowlist=allow)
    if not vr.ok:
        raise RuntimeError(f"termite verify not ok: {vr.__dict__}")

    rs = replay_bundle(bundle_path, policy=pol, allowlist=allow)
    if not rs.ok:
        raise RuntimeError(f"termite replay not ok: {rs.__dict__}")

    # ------------------------
    # 4) mite_ecology init (schema)
    # ------------------------
    e_cfg.runtime_root.mkdir(parents=True, exist_ok=True)
    e_cfg.imports_root.mkdir(parents=True, exist_ok=True)
    e_cfg.exports_root.mkdir(parents=True, exist_ok=True)
    e_con = e_connect(e_cfg.db_path)
    e_schema = repo_root / "mite_ecology" / "sql" / "schema.sql"
    e_init_db(e_con, e_schema)
    e_con.close()

    # ------------------------
    # 5) import bundle (idempotent)
    # ------------------------
    accept_termite_bundle(
        e_cfg.db_path,
        bundle_path,
        policy_path=e_cfg.policy_path,
        allowlist_path=e_cfg.allowlist_path,
        accept_policy=AcceptPolicy(
            max_ops=e_cfg.max_bundle_ops,
            max_new_nodes=getattr(e_cfg, "max_bundle_new_nodes", 2000),
            max_new_edges=getattr(e_cfg, "max_bundle_new_edges", 10000),
        ),
        override_mode=None,
        actor=None,
        notes=None,
        idempotent=True,
    )

    # ------------------------
    # 6) auto-run (same defaults as CLI)
    # ------------------------
    e_con = e_connect(e_cfg.db_path)
    kg = KnowledgeGraph(e_con)
    context = _default_context_node(e_con)
    ar = AutoRunConfig(
        cycles=5,
        hops=e_cfg.hops,
        feature_dim=e_cfg.feature_dim,
        top_attention_edges=64,
        motif_limit=24,
        population=32,
        generations=12,
        llm_mode="off",
        notes="",
    )
    rep = autorun(kg, context_node_id=context, cfg=ar)
    out = e_cfg.runtime_root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    rp = out / f"autorun_{sha256_str(canonical_json(rep))[:16]}.json"
    rp.write_text(canonical_json(rep), encoding="utf-8")
    e_con.close()

    # ------------------------
    # 7) replay-verify
    # ------------------------
    replay_json = replay_verify(e_cfg.db_path)
    if not replay_json.get("match"):
        raise RuntimeError(f"mite_ecology replay-verify mismatch: {replay_json}")
    if not replay_json.get("kg_deltas_chain_ok") or not replay_json.get("ingested_chain_ok"):
        raise RuntimeError(f"mite_ecology replay-verify chain failed: {replay_json}")

    return {
        "ingest": asdict(ingest_res),
        "bundle_path": str(bundle_path),
        "verify": vr.__dict__,
        "replay_verify": replay_json,
    }
