from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

from .config import load_config, default_config_path
from .db import connect, init_db
from .kg import KnowledgeGraph
from .bundle_accept import accept_termite_bundle, AcceptPolicy, list_staged, approve_staged, reject_staged
from .replay import replay_verify
from .components import build_manifest_from_prompt_cache, write_manifest_jsonl
from .auto import autorun, AutoRunConfig
from .gnn import message_passing_embeddings
from .gat import compute_edge_attention
from .motif import mine_motif_from_attention, list_motifs
from .memoga import run_memoga
from .export import export_best_genome
from .llm_sync import llm_sync as _llm_sync, llm_propose_motif as _llm_propose_motif, llm_propose_delta as _llm_propose_delta
from .hashutil import sha256_str, canonical_json
from .kg_shacl_lite import load_shapes, validate_kg


def _default_context_node(kg: KnowledgeGraph) -> str:
    # Prefer any node with type 'Task', else first node
    row = kg.con.execute("SELECT id FROM nodes WHERE type='Task' LIMIT 1").fetchone()
    if row:
        return str(row["id"])
    row = kg.con.execute("SELECT id FROM nodes LIMIT 1").fetchone()
    if not row:
        raise RuntimeError("KG is empty. Import a bundle or ingest nodes first.")
    return str(row["id"])


def cmd_init(args) -> int:
    cfg = load_config(args.config)
    cfg.runtime_root.mkdir(parents=True, exist_ok=True)
    cfg.imports_root.mkdir(parents=True, exist_ok=True)
    cfg.exports_root.mkdir(parents=True, exist_ok=True)
    con = connect(cfg.db_path)
    schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
    init_db(con, schema_path)
    print(f"Initialized mite_ecology DB at {cfg.db_path}")
    return 0


def cmd_import_bundle(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    # Ensure schema + migrations
    init_db(con, Path(__file__).resolve().parents[1] / "sql" / "schema.sql")

    bundle = Path(args.bundle).resolve()
    res = accept_termite_bundle(
        cfg.db_path,
        bundle,
        policy_path=cfg.policy_path,
        allowlist_path=cfg.allowlist_path,
        accept_policy=AcceptPolicy(
            max_ops=cfg.max_bundle_ops,
            max_new_nodes=getattr(cfg, "max_bundle_new_nodes", 2000),
            max_new_edges=getattr(cfg, "max_bundle_new_edges", 10000),
        ),
        override_mode=args.mode,
        actor=args.actor or None,
        notes=args.notes or None,
        idempotent=bool(getattr(args, "idempotent", False)),
    )
    st = str(res.get("status"))
    if st == "MERGED":
        print(f"Imported {res.get('ops_count')} KG ops from bundle {bundle.name} (merged)")
    elif st == "ALREADY_INGESTED":
        print(f"Bundle {bundle.name} already ingested (id={res.get('ingested_id')})")
    elif st == "ALREADY_STAGED":
        print(f"Bundle {bundle.name} already staged (staged_id={res.get('staged_id')}, status={res.get('staged_status')})")
    else:
        print(f"Bundle {bundle.name} staged: status={st} ops={res.get('ops_count')} staged_id={res.get('staged_id')}")
    return 0


def cmd_gnn(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    context = args.context or _default_context_node(kg)
    nodes, edges = kg.neighborhood(context, hops=cfg.hops, max_nodes=800)
    emb = message_passing_embeddings(nodes, edges, feature_dim=cfg.feature_dim, hops=cfg.hops)
    for nid, vec in emb.items():
        kg.upsert_node_embedding(nid, vec)
    print(f"Computed embeddings for {len(emb)} nodes (context={context})")
    return 0


def cmd_gat(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    context = args.context or _default_context_node(kg)
    nodes, edges = kg.neighborhood(context, hops=cfg.hops, max_nodes=800)
    emb = {n.id: kg.get_node_embedding(n.id) for n in nodes}
    scores = compute_edge_attention(nodes, edges, emb, context, alpha=cfg.gat_alpha)
    for e in edges:
        kg.set_edge_attention(e.id, float(scores.get(e.id, 0.0)), context)
    print(f"Computed attention for {len(edges)} edges (context={context})")
    return 0


def cmd_motifs(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    context = args.context or _default_context_node(kg)
    if args.mine:
        mined = mine_motif_from_attention(kg, context, limit=args.limit)
        print(json.dumps(mined, indent=2, sort_keys=True))
    else:
        ms = list_motifs(kg, context, limit=args.limit)
        print(json.dumps(ms, indent=2, sort_keys=True))
    return 0


def cmd_ga(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    context = args.context or _default_context_node(kg)
    # Pull motifs from DB
    motifs = list_motifs(kg, context, limit=cfg.gat_top_edges)
    seed_hex = sha256_str(f"{context}|ga_seed")
    res = run_memoga(
        kg,
        context_node_id=context,
        motifs=motifs,
        population=cfg.ga_population,
        generations=cfg.ga_generations,
        seed_hex=seed_hex,
    )
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


def cmd_export(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    out = export_best_genome(kg, cfg.exports_root)
    print(str(out))
    return 0


def cmd_auto_run(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    context = args.context or _default_context_node(kg)
    ar = AutoRunConfig(
        cycles=int(args.cycles),
        hops=cfg.hops,
        feature_dim=cfg.feature_dim,
        top_attention_edges=int(args.top_attention_edges),
        motif_limit=int(args.motif_limit),
        population=int(args.population),
        generations=int(args.generations),
        llm_mode="off",
        notes=str(args.notes or ""),
    )
    rep = autorun(kg, context_node_id=context, cfg=ar)
    out = cfg.runtime_root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    rp = out / f"autorun_{sha256_str(canonical_json(rep))[:16]}.json"
    rp.write_text(canonical_json(rep), encoding="utf-8")
    print(f"Auto-run complete. Report: {rp}")
    return 0


def cmd_llm_sync(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    res = _llm_sync(kg, cfg.raw, task_node_id=args.task)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


def cmd_llm_propose_motif(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    res = _llm_propose_motif(kg, cfg.raw, task_node_id=args.task)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


def cmd_llm_propose_delta(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    kg = KnowledgeGraph(con)
    res = _llm_propose_delta(kg, cfg.raw, scope_rule=args.scope)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mite-ecology", description="mite_ecology CLI (strict deterministic mode)")
    p.add_argument("--config", default=str(default_config_path()))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("import-bundle")
    s.add_argument("bundle")
    s.add_argument("--mode", default=None, choices=["AUTO_MERGE","REVIEW_ONLY","QUARANTINE","KILL"])
    s.add_argument("--idempotent", action="store_true", help="Treat an already-ingested or already-staged bundle as a successful no-op.")
    s.add_argument("--actor", default="")
    s.add_argument("--notes", default="")
    s.set_defaults(func=cmd_import_bundle)

    s = sub.add_parser("review-list")
    s.add_argument("--status", default="ALL", choices=["ALL","PENDING","QUARANTINED","APPROVED","REJECTED"])
    s.add_argument("--json", action="store_true", help="Emit JSON rows")
    s.set_defaults(func=cmd_review_list)

    s = sub.add_parser("review-approve")
    s.add_argument("staged_id", type=int)
    s.add_argument("--actor", required=True)
    s.add_argument("--notes", default="")
    s.set_defaults(func=cmd_review_approve)

    s = sub.add_parser("review-reject")
    s.add_argument("staged_id", type=int)
    s.add_argument("--actor", required=True)
    s.add_argument("--notes", default="")
    s.set_defaults(func=cmd_review_reject)

    s = sub.add_parser("replay-verify")
    s.set_defaults(func=cmd_replay_verify)

    s = sub.add_parser("components-manifest")
    s.add_argument("--prompt-cache", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_components_manifest)

    s = sub.add_parser("gnn")
    s.add_argument("--context", default=None)
    s.set_defaults(func=cmd_gnn)

    s = sub.add_parser("gat")
    s.add_argument("--context", default=None)
    s.set_defaults(func=cmd_gat)

    s = sub.add_parser("motifs")
    s.add_argument("--context", default=None)
    s.add_argument("--limit", type=int, default=24)
    s.add_argument("--mine", action="store_true", help="Mine motifs from attention and persist")
    s.set_defaults(func=cmd_motifs)

    s = sub.add_parser("ga")
    s.add_argument("--context", default=None)
    s.set_defaults(func=cmd_ga)

    s = sub.add_parser("export")
    s.add_argument("--context", default=None)
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("auto-run")
    s.add_argument("--context", default=None)
    s.add_argument("--cycles", type=int, default=5)
    s.add_argument("--top-attention-edges", type=int, default=64)
    s.add_argument("--motif-limit", type=int, default=24)
    s.add_argument("--population", type=int, default=32)
    s.add_argument("--generations", type=int, default=12)
    s.add_argument("--notes", default="")
    s.set_defaults(func=cmd_auto_run)

    # LLM sync family (still deterministic in hashing/audit, but model outputs are exogenous)
    s = sub.add_parser("llm-sync")
    s.add_argument("--task", required=True)
    s.set_defaults(func=cmd_llm_sync)

    s = sub.add_parser("llm-propose-motif")
    s.add_argument("--task", required=True)
    s.set_defaults(func=cmd_llm_propose_motif)

    s = sub.add_parser("llm-propose-delta")
    s.add_argument("--scope", required=True)
    s.set_defaults(func=cmd_llm_propose_delta)


    s = sub.add_parser("spec-validate")
    s.add_argument("kind", help="stud|tube")
    s.add_argument("file")
    s.set_defaults(func=cmd_spec_validate)

    s = sub.add_parser("kg-validate")
    s.set_defaults(func=cmd_kg_validate)

    s = sub.add_parser("clutchscore")
    s.add_argument("--a-stud", required=True)
    s.add_argument("--a-tube", required=True)
    s.add_argument("--b-stud", required=True)
    s.add_argument("--b-tube", required=True)
    s.add_argument("--host-ram-mb", default=0, type=int)
    s.add_argument("--host-disk-mb", default=0, type=int)
    s.set_defaults(func=cmd_clutchscore)


    return p




def cmd_review_list(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    init_db(con, Path(__file__).resolve().parents[1] / "sql" / "schema.sql")
    status = None if args.status == "ALL" else args.status
    rows = list_staged(con, status=status)
    if getattr(args, "json", False):
        print(json.dumps({"rows": rows}, indent=2, sort_keys=True))
        return 0
    if not rows:
        print("No staged bundles.")
        return 0
    for r in rows:
        print(f"[{r['id']}] status={r['status']} ts={r['ts_utc']} bundle={r['bundle_name']} ops={r['ops_count']} delta={r['kg_delta_hash']}")
    return 0

def cmd_review_approve(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    init_db(con, Path(__file__).resolve().parents[1] / "sql" / "schema.sql")
    res = approve_staged(con, int(args.staged_id), actor=str(args.actor), notes=str(args.notes or ""))
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0

def cmd_review_reject(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    init_db(con, Path(__file__).resolve().parents[1] / "sql" / "schema.sql")
    res = reject_staged(con, int(args.staged_id), actor=str(args.actor), notes=str(args.notes or ""))
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0

def cmd_replay_verify(args) -> int:
    cfg = load_config(args.config)
    res = replay_verify(cfg.db_path)
    print(json.dumps(res, indent=2, sort_keys=True))
    if not res.get("match"):
        return 2
    if not res.get("kg_deltas_chain_ok") or not res.get("ingested_chain_ok"):
        return 2
    return 0

def cmd_components_manifest(args) -> int:
    manifest = build_manifest_from_prompt_cache(Path(args.prompt_cache))
    write_manifest_jsonl(manifest, Path(args.out))
    print(f"Wrote {len(manifest)} rows to {args.out}")
    return 0


def cmd_spec_validate(args) -> int:
    obj = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if args.kind.lower() in ("stud","studspec"):
        issues = [i.__dict__ for i in validate_studspec(obj)]
    elif args.kind.lower() in ("tube","tubespec"):
        issues = [i.__dict__ for i in validate_tubespec(obj)]
    else:
        raise SystemExit("unknown kind")
    out = {"ok": len([i for i in issues if i.get("severity","error")=="error"]) == 0, "issues": issues}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["ok"] else 2


def cmd_kg_validate(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    init_db(con, Path(__file__).resolve().parents[1] / "sql" / "schema.sql")
    kg = KnowledgeGraph(con)
    shapes_path = Path(__file__).resolve().parents[2] / "schemas" / "kg_shapes_lite.yaml"
    rep = validate_kg(kg, load_shapes(shapes_path))
    out = {"ok": rep.ok, "nodes_seen": rep.nodes_seen, "edges_seen": rep.edges_seen, "issues": [i.__dict__ for i in rep.issues]}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if rep.ok else 2


def cmd_clutchscore(args) -> int:
    a_stud = json.loads(Path(args.a_stud).read_text(encoding="utf-8"))
    a_tube = json.loads(Path(args.a_tube).read_text(encoding="utf-8"))
    b_stud = json.loads(Path(args.b_stud).read_text(encoding="utf-8"))
    b_tube = json.loads(Path(args.b_tube).read_text(encoding="utf-8"))
    host = None
    if args.host_ram_mb or args.host_disk_mb:
        host = {"ram_mb": int(args.host_ram_mb or 0), "disk_mb": int(args.host_disk_mb or 0)}
    cs = compute_clutchscore(a_stud, a_tube, b_stud, b_tube, host_caps=host)
    out = {"score_0_100": cs.score_0_100, "reasons": cs.reasons, "details": cs.details}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
