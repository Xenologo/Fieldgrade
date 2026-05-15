#!/usr/bin/env python3
"""Compatibility wrapper for proposal-pack validation."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "check_proposal_readiness.py")], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
