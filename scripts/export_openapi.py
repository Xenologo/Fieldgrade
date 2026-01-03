from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    # fg_next/scripts/export_openapi.py -> fg_next
    return Path(__file__).resolve().parents[1]


def main() -> int:
    repo = _repo_root()
    sys.path.insert(0, str(repo))

    from fieldgrade_ui.app import app  # noqa: WPS433

    schema = app.openapi()
    out_dir = repo / "openapi"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fieldgrade_ui.openapi.json"

    out_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
