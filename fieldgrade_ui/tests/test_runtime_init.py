from __future__ import annotations

import importlib
import io
import json
import sqlite3
import sys
from pathlib import Path


def _tables(db_path: Path) -> set[str]:
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row[0]) for row in rows}
    finally:
        con.close()


def test_init_runtime_creates_required_databases(tmp_path: Path, monkeypatch) -> None:
    jobs_db = tmp_path / "ui" / "jobs.sqlite"
    mite_db = tmp_path / "ecology" / "mite.sqlite"

    monkeypatch.setenv("FG_JOBS_DB", str(jobs_db))
    monkeypatch.setenv("FG_MITE_DB", str(mite_db))

    import fieldgrade_ui.runtime_init as runtime_init

    importlib.reload(runtime_init)
    result = runtime_init.init_runtime()

    assert result["ok"] is True
    assert jobs_db.exists()
    assert mite_db.exists()
    assert {"jobs", "job_logs", "executions", "execution_events"} <= _tables(jobs_db)
    assert {"nodes", "edges", "ingested_bundles"} <= _tables(mite_db)


def test_cli_init_alias_prints_json(tmp_path: Path, monkeypatch) -> None:
    jobs_db = tmp_path / "jobs.sqlite"
    mite_db = tmp_path / "mite.sqlite"

    monkeypatch.setenv("FG_JOBS_DB", str(jobs_db))
    monkeypatch.setenv("FG_MITE_DB", str(mite_db))

    import fieldgrade_ui.__main__ as cli

    importlib.reload(cli)

    stdout = io.StringIO()
    monkeypatch.setattr(sys, "argv", ["fieldgrade-ui", "init"])
    monkeypatch.setattr(sys, "stdout", stdout)

    cli.main()

    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["jobs_db"] == str(jobs_db)
    assert payload["mite_db"] == str(mite_db)
