from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import yaml

from .config import load_config, default_config_path
from .cas import CAS
from .db import connect, init_db, export_kg_ops_jsonl
from .ingest import ingest_path
from .provenance import Provenance, verify_chain
from .search import search
from .bundle import SealInputs, build_bundle
from .policy import load_policy
from .verify import verify_bundle
from .replay import replay_bundle
from .llm_runtime import start as llm_start, stop as llm_stop, ping as llm_ping, read_status as llm_status
from .llm_chat import chat as llm_chat
from .tools import run_tool
from .mission import run_mission


def cmd_init(args) -> int:
    cfg = load_config(args.config)
    cfg.runtime_root.mkdir(parents=True, exist_ok=True)
    (cfg.runtime_root / "llm").mkdir(parents=True, exist_ok=True)
    cfg.bundles_out.mkdir(parents=True, exist_ok=True)

    cas = CAS(cfg.cas_root)
    cas.init()

    con = connect(cfg.db_path)
    schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
    init_db(con, schema_path)

    if cfg.signing_enabled:
        from .signing import load_or_create
        load_or_create(cfg.signing_private_key_path, cfg.signing_public_key_path)

    print(f"Initialized Termite runtime at {cfg.runtime_root}")
    return 0


def cmd_ingest(args) -> int:
    cfg = load_config(args.config)
    cas = CAS(cfg.cas_root); cas.init()
    con = connect(cfg.db_path)
    prov = Provenance(cfg.toolchain_id)
    res = ingest_path(
        con, cas, prov, Path(args.path),
        max_bytes=cfg.max_bytes,
        extract_text=cfg.extract_text,
        chunk_chars=cfg.chunk_chars,
    )
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


def cmd_search(args) -> int:
    cfg = load_config(args.config)
    con = connect(cfg.db_path)
    rows = search(con, args.query, limit=args.limit)
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


def cmd_seal(args) -> int:
    cfg = load_config(args.config)
    cas = CAS(cfg.cas_root); cas.init()

    inp = SealInputs(
        toolchain_id=cfg.toolchain_id,
        cas=cas,
        db_path=cfg.db_path,
        bundles_out=cfg.bundles_out,
        include_extract=cfg.include_extract,
        include_aux=cfg.include_aux,
    )
    out = build_bundle(inp, label=args.label)
    print(str(out))
    return 0


def cmd_verify(args) -> int:
    pol = load_policy(Path(args.policy))
    allow = yaml.safe_load(Path(args.allowlist).read_text(encoding="utf-8")) or {}
    allow["_base_dir"] = str(Path(args.allowlist).resolve().parent)
    vr = verify_bundle(Path(args.bundle), policy=pol, allowlist=allow)
    print(json.dumps(vr.__dict__, indent=2, sort_keys=True))
    return 0 if vr.ok else 2


def cmd_replay(args) -> int:
    pol = load_policy(Path(args.policy))
    allow = yaml.safe_load(Path(args.allowlist).read_text(encoding="utf-8")) or {}
    allow["_base_dir"] = str(Path(args.allowlist).resolve().parent)
    rs = replay_bundle(Path(args.bundle), policy=pol, allowlist=allow)
    print(json.dumps(rs.__dict__, indent=2, sort_keys=True))
    return 0 if rs.ok else 2


def cmd_llm_start(args) -> int:
    cfg = load_config(args.config)
    st = llm_start(cfg, force=args.force)
    print(json.dumps(st.__dict__, indent=2, sort_keys=True))
    return 0


def cmd_llm_stop(args) -> int:
    cfg = load_config(args.config)
    st = llm_stop(cfg, force_kill=args.force_kill)
    print(json.dumps(st.__dict__, indent=2, sort_keys=True))
    return 0


def cmd_llm_ping(args) -> int:
    cfg = load_config(args.config)
    ok, msg = llm_ping(cfg)
    print(json.dumps({"ok": bool(ok), "msg": msg}, indent=2, sort_keys=True))
    return 0 if ok else 2


def cmd_llm_status(args) -> int:
    cfg = load_config(args.config)
    st = llm_status(cfg)
    if args.json:
        print(json.dumps(st, indent=2, sort_keys=True))
    else:
        print(f"{st.get('provider')} {st.get('model')} {st.get('base_url')} running={st.get('running')}")
    return 0


def cmd_llm_chat(args) -> int:
    cfg = load_config(args.config)
    prompt = args.prompt or ""
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    r = llm_chat(cfg, prompt, temperature=args.temperature, max_tokens=args.max_tokens, store=not args.no_store)
    if args.json:
        print(json.dumps(r, indent=2, sort_keys=True))
    else:
        print(r.get("content", ""))
    return 0


def cmd_tool_run(args) -> int:
    cfg = load_config(args.config)
    r = run_tool(cfg, args.tool_id, args.argv, Path(args.allowlist))
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0 if int(r.get("exit_code", 1)) == 0 else 2


def cmd_mission_run(args) -> int:
    cfg_path = Path(args.config).resolve() if args.config else None
    r = run_mission(Path(args.mission).resolve(), config_path=cfg_path)
    print(json.dumps(r, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="termite", description="Termite fieldpack CLI")
    p.add_argument("--config", default=str(default_config_path()))

    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("ingest")
    s.add_argument("path")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("seal")
    s.add_argument("--label", default="bundle")
    s.set_defaults(func=cmd_seal)

    s = sub.add_parser("verify")
    s.add_argument("bundle")
    s.add_argument("--policy", default="config/meap_v1.yaml")
    s.add_argument("--allowlist", default="config/tool_allowlist.yaml")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("replay")
    s.add_argument("bundle")
    s.add_argument("--policy", default="config/meap_v1.yaml")
    s.add_argument("--allowlist", default="config/tool_allowlist.yaml")
    s.set_defaults(func=cmd_replay)

    # LLM runtime control
    llm = sub.add_parser("llm")
    llm_sub = llm.add_subparsers(dest="llm_cmd", required=True)

    s = llm_sub.add_parser("start")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_llm_start)

    s = llm_sub.add_parser("stop")
    s.add_argument("--force-kill", action="store_true")
    s.set_defaults(func=cmd_llm_stop)

    s = llm_sub.add_parser("ping")
    s.set_defaults(func=cmd_llm_ping)

    s = llm_sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_llm_status)

    s = llm_sub.add_parser("chat")
    s.add_argument("--prompt", default="")
    s.add_argument("--prompt-file", default=None)
    s.add_argument("--temperature", type=float, default=None)
    s.add_argument("--max-tokens", type=int, default=None)
    s.add_argument("--no-store", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_llm_chat)

    # tool runner
    tool = sub.add_parser("tool")
    tool_sub = tool.add_subparsers(dest="tool_cmd", required=True)
    s = tool_sub.add_parser("run")
    s.add_argument("tool_id")
    s.add_argument("--allowlist", default="config/tool_allowlist.yaml")
    s.add_argument("argv", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_tool_run)

    # mission runner
    ms = sub.add_parser("mission")
    ms_sub = ms.add_subparsers(dest="mission_cmd", required=True)
    s = ms_sub.add_parser("run")
    s.add_argument("mission")
    s.add_argument("--config", default=None)
    s.set_defaults(func=cmd_mission_run)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
