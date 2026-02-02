from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fieldgrade_ui.execution_ledger import append_event, create_execution, ensure_db, iter_events, verify_chain


def test_execution_ledger_hash_chain_is_valid(tmp_path: Path):
    dbp = tmp_path / "jobs.sqlite"
    ensure_db(dbp)

    eid = create_execution(dbp, plan_id="plan-demo", base_snapshot_hash="snap0")

    h1 = append_event(
        dbp,
        execution_id=eid,
        plan_id="plan-demo",
        step_index=0,
        action_type="step.start",
        status="running",
        expected={"pre": "ok"},
        actor_id="system",
        ts_ms=1000,
    )
    h2 = append_event(
        dbp,
        execution_id=eid,
        plan_id="plan-demo",
        step_index=0,
        action_type="step.finish",
        status="passed",
        observed={"post": "ok"},
        actor_id="system",
        ts_ms=1001,
    )

    events = list(iter_events(dbp, eid))
    assert [e.event_hash for e in events] == [h1, h2]

    ok, n = verify_chain(dbp, eid)
    assert ok is True
    assert n == 2


def test_execution_ledger_is_append_only_at_db_level(tmp_path: Path):
    dbp = tmp_path / "jobs.sqlite"
    ensure_db(dbp)
    eid = create_execution(dbp, plan_id="p", base_snapshot_hash="s")

    append_event(
        dbp,
        execution_id=eid,
        plan_id="p",
        step_index=0,
        action_type="x",
        status="running",
        actor_id="system",
        ts_ms=1000,
    )

    con = sqlite3.connect(str(dbp))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE execution_events SET status='failed' WHERE execution_id=?", (eid,))

        with pytest.raises(sqlite3.IntegrityError):
            con.execute("DELETE FROM execution_events WHERE execution_id=?", (eid,))
    finally:
        con.close()
