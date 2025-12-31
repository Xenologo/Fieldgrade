#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  echo "ERROR: .venv not found. Run: bash scripts/termux_setup.sh" >&2
  exit 1
fi

source .venv/bin/activate

export FG_WORKER_POLL="${FG_WORKER_POLL:-1.0}"

echo "[Fieldgrade] starting background worker (poll=$FG_WORKER_POLL)"
python -m fieldgrade_ui worker
