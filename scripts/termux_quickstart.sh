#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  echo "[Fieldgrade] .venv missing; running setup..."
  bash scripts/termux_setup.sh
fi

echo "[Fieldgrade] doctor..."
source .venv/bin/activate
python -m fieldgrade_ui doctor || true

echo "[Fieldgrade] starting UI server..."
bash scripts/termux_run_ui.sh
