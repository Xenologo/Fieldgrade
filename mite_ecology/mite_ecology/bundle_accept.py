from __future__ import annotations

import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .accept import verify_termite_bundle
from .db import connect, init_db
from .delta import apply_delta_lines
from .kg import KnowledgeGraph
from .hashutil import canonical_json
from .kg_shacl_lite import load_shapes, validate_kg
from .specs import validate_studspec as _validate_studspec, validate_tubespec as _validate_tubespec
from .timeutil import utc_now_iso

# ---------------------------------------------------------------------------
# MEAP-aligned Ecology Acceptance
#
# - Termite verifies: signatures, hashes, allowlist, policy envelope
# - Ecology verifies: delta safety windows + KG SHACL-lite constraints
# - Auto-merge only if *both* sides pass (and KG remains valid after apply)
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _canonical_jsonl_payload(lines: Iterable[str]) -> str:
    out: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        out.append(s)
    return "\n".join(out) + ("\n" if out else "")


def _read_zip_text(z: zipfile.ZipFile, name: str) -> str:
    with z.open(name, "r") as f:
        return f.read().decode("utf-8")


def _read_zip_optional_text(z: zipfile.ZipFile, name: str) -> Optional[str]:
    try:
        return _read_zip_text(z, name)
    except KeyError:
        return None


def _hash_chain(prev_hash: Optional[str], *parts: str) -> str:
    blob = (prev_hash or "") + "|" + "|".join(parts)
    return sha256_bytes(blob.encode("utf-8"))


@dataclass(frozen=True)
class AcceptPolicy:
    # Additional ecology-side guards, independent of Termite MEAP.
    max_ops: int = 10_000
    max_new_nodes: int = 2_000
    max_new_edges: int = 10_000


def _get_last_hash(con: sqlite3.Connection, table: str, col: str) -> Optional[str]:
    row = con.execute(f"SELECT {col} FROM {table} ORDER BY id DESC LIMIT 1").fetchone()
    return str(row[col]) if row and row[col] is not None else None


def _count_new_entities(delta_ops: List[Dict]) -> Tuple[int, int]:
    new_nodes = 0
    new_edges = 0
    for op in delta_ops:
        k = str(op.get("op") or "")
        if k in ("ADD_NODE", "upsert_node"):
            new_nodes += 1
        elif k in ("ADD_EDGE", "upsert_edge"):
            new_edges += 1
    return new_nodes, new_edges


def _parse_delta_ops(delta_payload: str) -> List[Dict]:
    ops: List[Dict] = []
    for ln in delta_payload.splitlines():
        if not ln.strip():
            continue
        ops.append(json.loads(ln))
    return ops


def _simulate_apply_and_validate(con: sqlite3.Connection, delta_payload: str, shapes_path: Path) -> Dict[str, object]:
    """Apply delta to a temporary copy of the KG and run SHACL-lite validation."""
    tmp = sqlite3.connect(":memory:")
    tmp.row_factory = sqlite3.Row
    con.backup(tmp)
    try:
        kg = KnowledgeGraph(tmp)
        apply_delta_lines(kg, delta_payload.splitlines())
        shapes = load_shapes(shapes_path)
        rep = validate_kg(kg, shapes)
        return {
            "ok": bool(rep.ok),
            "nodes_seen": int(rep.nodes_seen),
            "edges_seen": int(rep.edges_seen),
            "issues": [i.__dict__ for i in rep.issues],
        }
    finally:
        tmp.close()


def _validate_optional_contracts(z: zipfile.ZipFile) -> Dict[str, object]:
    out: Dict[str, object] = {"studspec": None, "tubespec": None}
    s_txt = _read_zip_optional_text(z, "studspec.json")
    t_txt = _read_zip_optional_text(z, "tubespec.json")
    if s_txt:
        try:
            obj = json.loads(s_txt)
            issues = [i.__dict__ for i in _validate_studspec(obj)]
            out["studspec"] = {"ok": len(issues) == 0, "issues": issues}
        except Exception as e:
            out["studspec"] = {"ok": False, "issues": [{"path": "/", "message": f"parse_error:{e}", "severity": "error"}]}
    if t_txt:
        try:
            obj = json.loads(t_txt)
            issues = [i.__dict__ for i in _validate_tubespec(obj)]
            out["tubespec"] = {"ok": len(issues) == 0, "issues": issues}
        except Exception as e:
            out["tubespec"] = {"ok": False, "issues": [{"path": "/", "message": f"parse_error:{e}", "severity": "error"}]}
    return out


def stage_bundle(
    con: sqlite3.Connection,
    *,
    bundle_sha256: str,
    bundle_name: str,
    verified_ok: bool,
    verify_reason: str,
    policy_id: str,
    policy_hash: str,
    allowlist_hash: str,
    toolchain_id: str,
    bundle_map_hash: str,
    delta_payload: str,
    delta_hash: str,
    ops_count: int,
    status: str,
    policy_mode: str,
    contracts_report: Optional[Dict[str, object]] = None,
    kg_shacl_report: Optional[Dict[str, object]] = None,
    decision_actor: Optional[str] = None,
    decision_notes: Optional[str] = None,
) -> int:
    ts = utc_now_iso()
    prev_hash = _get_last_hash(con, "staged_bundles", "stage_hash")
    stage_hash = _hash_chain(prev_hash, bundle_sha256, delta_hash, status, policy_hash, allowlist_hash)
    cur = con.execute(
        """INSERT INTO staged_bundles
           (ts_utc, bundle_sha256, bundle_name, verified_ok, verify_reason, policy_id, policy_hash, allowlist_hash,
            toolchain_id, bundle_map_hash, ops_count, kg_delta_payload, kg_delta_hash, status, policy_mode,
            contracts_report_json, kg_shacl_report_json,
            decision_ts_utc, decision_actor, decision_notes, prev_hash, stage_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ts, bundle_sha256, bundle_name, int(bool(verified_ok)), verify_reason, policy_id, policy_hash, allowlist_hash,
            toolchain_id, bundle_map_hash, ops_count, delta_payload, delta_hash, status, policy_mode,
            json.dumps(contracts_report or None, sort_keys=True),
            json.dumps(kg_shacl_report or None, sort_keys=True),
            (ts if decision_actor else None), decision_actor, decision_notes, prev_hash, stage_hash,
        ),
    )
    return int(cur.lastrowid)


def _insert_ingested_bundle(
    con: sqlite3.Connection,
    *,
    bundle_sha256: str,
    bundle_name: str,
    verified_ok: bool,
    verify_reason: str,
    policy_id: str,
    policy_hash: str,
    allowlist_hash: str,
    toolchain_id: str,
    bundle_map_hash: str,
    ops_count: int,
    delta_hash: str,
    ingest_kind: str,
    notes: Optional[str] = None,
) -> int:
    ts = utc_now_iso()
    prev_hash = _get_last_hash(con, "ingested_bundles", "ingest_hash")
    ingest_hash = _hash_chain(prev_hash, bundle_sha256, delta_hash, ingest_kind, policy_hash, allowlist_hash)
    cur = con.execute(
        """INSERT INTO ingested_bundles
           (ts_utc, bundle_sha256, bundle_name, verified_ok, verify_reason, policy_id, policy_hash, allowlist_hash,
            toolchain_id, bundle_map_hash, ops_count, kg_delta_hash, ingest_kind, prev_hash, ingest_hash, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ts, bundle_sha256, bundle_name, int(bool(verified_ok)), verify_reason, policy_id, policy_hash, allowlist_hash,
            toolchain_id, bundle_map_hash, ops_count, delta_hash, ingest_kind, prev_hash, ingest_hash, notes
        ),
    )
    return int(cur.lastrowid)


def accept_termite_bundle(
    db_path: Path,
    bundle_path: Path,
    policy_path: Path,
    allowlist_path: Path,
    *,
    accept_policy: AcceptPolicy,
    override_mode: Optional[str] = None,
    actor: Optional[str] = None,
    notes: Optional[str] = None,
    idempotent: bool = False,
) -> Dict[str, object]:
    """Verify + accept a Termite bundle.

    Modes (from policy or override_mode):
      - AUTO_MERGE: apply delta immediately if KG remains valid
      - REVIEW_ONLY: stage delta (PENDING)
      - QUARANTINE: stage delta (QUARANTINED)
      - KILL: refuse
    """
    bundle_path = Path(bundle_path).resolve()
    bundle_sha = sha256_bytes(bundle_path.read_bytes())

    vr, pol, allow = verify_termite_bundle(bundle_path, policy_path, allowlist_path)
    if not vr.ok:
        raise RuntimeError(f"bundle_verify_failed: {vr.reason}")

    policy_id = pol.policy_id
    policy_hash = pol.canonical_hash()
    allow_for_hash = {k: v for k, v in allow.items() if k != "_base_dir"}
    allowlist_hash = sha256_bytes(canonical_json(allow_for_hash).encode("utf-8"))

    mode = (override_mode or pol.mode or "REVIEW_ONLY").upper().strip()
    if mode == "KILL":
        raise RuntimeError("policy_mode_kill")

    bundle_name = bundle_path.name
    toolchain_id = vr.toolchain_id or ""
    bundle_map_hash = vr.bundle_map_hash or ""

    shapes_path = Path(__file__).resolve().parents[2] / "schemas" / "kg_shapes_lite.yaml"

    # Load delta + optional contracts from bundle
    with zipfile.ZipFile(bundle_path, "r") as z:
        if "kg_delta.jsonl" not in z.namelist():
            raise RuntimeError("missing_kg_delta")
        delta_raw = _read_zip_text(z, "kg_delta.jsonl")
        contracts_report = _validate_optional_contracts(z)

    delta_payload = _canonical_jsonl_payload(delta_raw.splitlines())
    delta_hash = sha256_bytes(delta_payload.encode("utf-8"))
    ops_count = 0 if not delta_payload.strip() else len(delta_payload.splitlines())

    if ops_count > accept_policy.max_ops:
        raise RuntimeError("delta_too_large_ops")

    delta_ops = _parse_delta_ops(delta_payload)
    new_nodes, new_edges = _count_new_entities(delta_ops)
    if new_nodes > accept_policy.max_new_nodes:
        raise RuntimeError("delta_too_many_new_nodes")
    if new_edges > accept_policy.max_new_edges:
        raise RuntimeError("delta_too_many_new_edges")

    con = connect(db_path)
    schema_sql_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
    init_db(con, schema_sql_path)

    if idempotent:
        # If this exact bundle was already ingested, treat as success (no-op).
        row = con.execute(
            "SELECT id, ingest_kind, kg_delta_hash, ts_utc FROM ingested_bundles WHERE bundle_sha256 = ?",
            (bundle_sha,),
        ).fetchone()
        if row:
            return {
                "status": "ALREADY_INGESTED",
                "bundle_sha256": bundle_sha,
                "bundle_name": bundle_name,
                "policy_mode": mode,
                "ops_count": ops_count,
                "delta_hash": delta_hash,
                "ingested_id": int(row["id"]),
                "ingest_kind": str(row["ingest_kind"]),
                "ingested_ts_utc": str(row["ts_utc"]),
                "contracts_ok": bool((contracts_report.get("studspec") or {}).get("ok", True) and (contracts_report.get("tubespec") or {}).get("ok", True)),
            }

        # If it's already staged, also treat as success (no-op) and point to staged_id.
        srow = con.execute(
            "SELECT id, status, policy_mode, ts_utc FROM staged_bundles WHERE bundle_sha256 = ? ORDER BY id DESC LIMIT 1",
            (bundle_sha,),
        ).fetchone()
        if srow:
            return {
                "status": "ALREADY_STAGED",
                "bundle_sha256": bundle_sha,
                "bundle_name": bundle_name,
                "policy_mode": str(srow["policy_mode"] or mode),
                "ops_count": ops_count,
                "delta_hash": delta_hash,
                "staged_id": int(srow["id"]),
                "staged_status": str(srow["status"]),
                "staged_ts_utc": str(srow["ts_utc"]),
                "contracts_ok": bool((contracts_report.get("studspec") or {}).get("ok", True) and (contracts_report.get("tubespec") or {}).get("ok", True)),
            }

    # Pre-flight SHACL-lite check against a temp copy
    kg_shacl_report = _simulate_apply_and_validate(con, delta_payload, shapes_path)

    if mode == "AUTO_MERGE":
        # Apply to live KG, then validate *after apply* before committing.
        rep_after: Optional[Dict[str, object]] = None
        try:
            with con:
                kg = KnowledgeGraph(con)
                apply_delta_lines(kg, delta_payload.splitlines())
                shapes = load_shapes(shapes_path)
                rep = validate_kg(kg, shapes)
                rep_after = {
                    "ok": bool(rep.ok),
                    "nodes_seen": int(rep.nodes_seen),
                    "edges_seen": int(rep.edges_seen),
                    "issues": [i.__dict__ for i in rep.issues],
                }
                if not rep.ok:
                    raise RuntimeError("kg_shacl_failed_after_apply")

                prev_delta_hash = _get_last_hash(con, "kg_deltas", "delta_hash")
                chain_hash = _hash_chain(prev_delta_hash, delta_hash)
                con.execute(
                    """INSERT INTO kg_deltas (ts_utc, source, context_node_id, delta_kind, delta_payload, prev_hash, delta_hash, chain_hash)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (utc_now_iso(), "TERMITE", None, "BUNDLE_IMPORT", delta_payload, prev_delta_hash, delta_hash, chain_hash),
                )
                ing_id = _insert_ingested_bundle(
                    con,
                    bundle_sha256=bundle_sha,
                    bundle_name=bundle_name,
                    verified_ok=True,
                    verify_reason=vr.reason,
                    policy_id=policy_id,
                    policy_hash=policy_hash,
                    allowlist_hash=allowlist_hash,
                    toolchain_id=toolchain_id,
                    bundle_map_hash=bundle_map_hash,
                    ops_count=ops_count,
                    delta_hash=delta_hash,
                    ingest_kind="MERGED",
                    notes=notes,
                )
            from .graph_delta import append_graph_delta_event, default_ledger_path_for_db
            append_graph_delta_event(
                default_ledger_path_for_db(db_path),
                source="TERMITE",
                ops_lines=delta_payload.splitlines(),
                context_node_id=None,
                run_id=None,
                trace_id=None,
                meta={
                    "bundle_sha256": bundle_sha,
                    "bundle_name": bundle_name,
                    "delta_hash": delta_hash,
                    "ingested_id": ing_id,
                    "policy_id": policy_id,
                    "policy_hash": policy_hash,
                    "allowlist_hash": allowlist_hash,
                    "toolchain_id": toolchain_id,
                    "bundle_map_hash": bundle_map_hash,
                },
            )
            return {
                "status": "MERGED",
                "bundle_sha256": bundle_sha,
                "bundle_name": bundle_name,
                "policy_mode": mode,
                "ops_count": ops_count,
                "delta_hash": delta_hash,
                "ingested_id": ing_id,
                "contracts_ok": bool((contracts_report.get("studspec") or {}).get("ok", True) and (contracts_report.get("tubespec") or {}).get("ok", True)),
            }
        except RuntimeError as e:
            # Safety: if KG becomes invalid, quarantine the bundle for review.
            if str(e) != "kg_shacl_failed_after_apply":
                raise
            with con:
                stg_id = stage_bundle(
                    con,
                    bundle_sha256=bundle_sha,
                    bundle_name=bundle_name,
                    verified_ok=True,
                    verify_reason=f"{vr.reason}; ecology:kg_invalid",
                    policy_id=policy_id,
                    policy_hash=policy_hash,
                    allowlist_hash=allowlist_hash,
                    toolchain_id=toolchain_id,
                    bundle_map_hash=bundle_map_hash,
                    delta_payload=delta_payload,
                    delta_hash=delta_hash,
                    ops_count=ops_count,
                    status="QUARANTINED",
                    policy_mode=mode,
                    contracts_report=contracts_report,
                    kg_shacl_report=(rep_after or kg_shacl_report),
                    decision_actor=actor,
                    decision_notes=notes,
                )
            return {
                "status": "QUARANTINED",
                "reason": "kg_shacl_failed_after_apply",
                "bundle_sha256": bundle_sha,
                "bundle_name": bundle_name,
                "policy_mode": mode,
                "ops_count": ops_count,
                "delta_hash": delta_hash,
                "staged_id": stg_id,
            }

    # REVIEW_ONLY / QUARANTINE -> stage
    status = "PENDING" if mode == "REVIEW_ONLY" else "QUARANTINED"
    with con:
        stg_id = stage_bundle(
            con,
            bundle_sha256=bundle_sha,
            bundle_name=bundle_name,
            verified_ok=True,
            verify_reason=vr.reason,
            policy_id=policy_id,
            policy_hash=policy_hash,
            allowlist_hash=allowlist_hash,
            toolchain_id=toolchain_id,
            bundle_map_hash=bundle_map_hash,
            delta_payload=delta_payload,
            delta_hash=delta_hash,
            ops_count=ops_count,
            status=status,
            policy_mode=mode,
            contracts_report=contracts_report,
            kg_shacl_report=kg_shacl_report,
            decision_actor=(actor if status != "PENDING" else None),
            decision_notes=(notes if status != "PENDING" else None),
        )

    return {
        "status": status,
        "bundle_sha256": bundle_sha,
        "bundle_name": bundle_name,
        "policy_mode": mode,
        "ops_count": ops_count,
        "delta_hash": delta_hash,
        "staged_id": stg_id,
        "kg_shacl_ok": bool(kg_shacl_report.get("ok", False)),
    }


def list_staged(con: sqlite3.Connection, status: Optional[str] = None) -> List[Dict[str, object]]:
    q = "SELECT * FROM staged_bundles"
    params: Tuple = ()
    if status:
        q += " WHERE status=?"
        params = (status,)
    q += " ORDER BY id DESC"
    rows = con.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def approve_staged(con: sqlite3.Connection, staged_id: int, *, actor: str, notes: Optional[str] = None) -> Dict[str, object]:
    row = con.execute("SELECT * FROM staged_bundles WHERE id=?", (staged_id,)).fetchone()
    if not row:
        raise RuntimeError("staged_not_found")
    if row["status"] not in ("PENDING", "QUARANTINED"):
        raise RuntimeError("staged_not_pending")

    shapes_path = Path(__file__).resolve().parents[2] / "schemas" / "kg_shapes_lite.yaml"
    delta_payload = str(row["kg_delta_payload"])
    delta_hash = str(row["kg_delta_hash"])
    ops_count = int(row["ops_count"])
    bundle_sha = str(row["bundle_sha256"])
    bundle_name = str(row["bundle_name"])

    # Pre-flight again (KG may have changed since staging)
    rep_pre = _simulate_apply_and_validate(con, delta_payload, shapes_path)
    if not rep_pre.get("ok", False):
        raise RuntimeError("cannot_approve:kg_shacl_failed")

    with con:
        kg = KnowledgeGraph(con)
        apply_delta_lines(kg, delta_payload.splitlines())
        shapes = load_shapes(shapes_path)
        rep = validate_kg(kg, shapes)
        if not rep.ok:
            raise RuntimeError("kg_shacl_failed_after_apply")

        prev_delta_hash = _get_last_hash(con, "kg_deltas", "delta_hash")
        chain_hash = _hash_chain(prev_delta_hash, delta_hash)
        con.execute(
            "INSERT INTO kg_deltas (ts_utc, source, context_node_id, delta_kind, delta_payload, prev_hash, delta_hash, chain_hash) VALUES (?,?,?,?,?,?,?,?)",
            (utc_now_iso(), "TERMITE", None, "BUNDLE_APPROVE", delta_payload, prev_delta_hash, delta_hash, chain_hash),
        )
        ing_id = _insert_ingested_bundle(
            con,
            bundle_sha256=bundle_sha,
            bundle_name=bundle_name,
            verified_ok=bool(row["verified_ok"]),
            verify_reason=str(row["verify_reason"] or ""),
            policy_id=str(row["policy_id"] or ""),
            policy_hash=str(row["policy_hash"] or ""),
            allowlist_hash=str(row["allowlist_hash"] or ""),
            toolchain_id=str(row["toolchain_id"] or ""),
            bundle_map_hash=str(row["bundle_map_hash"] or ""),
            ops_count=ops_count,
            delta_hash=delta_hash,
            ingest_kind="MERGED",
            notes=notes,
        )
        con.execute(
            "UPDATE staged_bundles SET status=?, decision_ts_utc=?, decision_actor=?, decision_notes=? WHERE id=?",
            ("APPROVED", utc_now_iso(), actor, notes, staged_id),
        )

    return {"status": "APPROVED", "staged_id": staged_id, "ingested_id": ing_id, "delta_hash": delta_hash, "ops_count": ops_count}


def reject_staged(con: sqlite3.Connection, staged_id: int, *, actor: str, notes: Optional[str] = None) -> Dict[str, object]:
    row = con.execute("SELECT * FROM staged_bundles WHERE id=?", (staged_id,)).fetchone()
    if not row:
        raise RuntimeError("staged_not_found")
    if row["status"] not in ("PENDING", "QUARANTINED"):
        raise RuntimeError("staged_not_pending")
    with con:
        con.execute(
            "UPDATE staged_bundles SET status=?, decision_ts_utc=?, decision_actor=?, decision_notes=? WHERE id=?",
            ("REJECTED", utc_now_iso(), actor, notes, staged_id),
        )
    return {"status": "REJECTED", "staged_id": staged_id}
