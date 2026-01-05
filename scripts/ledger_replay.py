from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _repo_root() -> Path:
    # fg_next/scripts/ledger_replay.py -> fg_next
    return Path(__file__).resolve().parents[1]


def main() -> int:
    repo = _repo_root()
    sys.path.insert(0, str(repo))

    from mite_ecology.mite_ecology.db import init_db  # noqa: WPS433
    from mite_ecology.mite_ecology.delta import apply_delta_lines  # noqa: WPS433
    from mite_ecology.mite_ecology.graph_delta import iter_ledger, ops_from_event, verify_ledger_chain  # noqa: WPS433
    from mite_ecology.mite_ecology.kg import KnowledgeGraph  # noqa: WPS433
    from mite_ecology.mite_ecology.replay import snapshot_hash  # noqa: WPS433

    ap = argparse.ArgumentParser(description="Replay a GraphDelta ledger into an empty KG and report snapshot hash.")
    ap.add_argument("ledger", type=Path, help="Path to graph_delta_ledger.jsonl")
    ap.add_argument("--schema", type=Path, default=None, help="Path to mite_ecology/sql/schema.sql")
    ap.add_argument("--out", type=Path, default=None, help="Optional: write replay report JSON")
    args = ap.parse_args()

    ok, n = verify_ledger_chain(args.ledger)
    if not ok:
        rep = {"ok": False, "error": "ledger_chain_invalid", "events_seen": n}
        if args.out:
            args.out.write_text(json.dumps(rep, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        else:
            print(json.dumps(rep, sort_keys=True))
        return 2

    schema_path = args.schema
    if schema_path is None:
        schema_path = (repo / "mite_ecology" / "sql" / "schema.sql").resolve()

    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    init_db(mem, schema_path)

    kg = KnowledgeGraph(mem)
    total_ops = 0
    for rec in iter_ledger(args.ledger):
        ops_payload = ops_from_event(rec)
        lines = [ln for ln in ops_payload.splitlines() if ln.strip()]
        total_ops += apply_delta_lines(kg, lines)

    rep = {
        "ok": True,
        "events": n,
        "ops_applied": total_ops,
        "snapshot_hash": snapshot_hash(mem),
    }

    if args.out:
        args.out.write_text(json.dumps(rep, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(rep, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
