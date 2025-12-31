#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

source .venv/bin/activate

# Back-compat aliases (most people will try FG_HOST/FG_PORT/FG_WORKERS)
export FIELDGRADE_UI_HOST="${FIELDGRADE_UI_HOST:-${FG_HOST:-127.0.0.1}}"
export FIELDGRADE_UI_PORT="${FIELDGRADE_UI_PORT:-${FG_PORT:-8787}}"
# Termux default: single worker; override explicitly if you know what you're doing.
export FIELDGRADE_UI_WORKERS="${FIELDGRADE_UI_WORKERS:-${FG_WORKERS:-1}}"
export FIELDGRADE_UI_LOG_LEVEL="${FIELDGRADE_UI_LOG_LEVEL:-info}"
export FIELDGRADE_UI_ACCESS_LOG="${FIELDGRADE_UI_ACCESS_LOG:-0}"

echo "[Termux] Starting Fieldgrade UI at http://${FIELDGRADE_UI_HOST}:${FIELDGRADE_UI_PORT}"
python -m fieldgrade_ui
