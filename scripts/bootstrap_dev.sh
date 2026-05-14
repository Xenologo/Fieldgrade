#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_BIN="${PYTHON:-}"
if [[ -z "$PY_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
  else
    PY_BIN="python"
  fi
fi

"$PY_BIN" -m pip install -U pip uv
command -v uv >/dev/null 2>&1 || { echo "uv installation failed" >&2; exit 1; }
UV_PROJECT_ENVIRONMENT="${VENV_DIR:-$ROOT_DIR/.venv}" uv sync --frozen --group dev
VENV_PYTHON="${VENV_DIR:-$ROOT_DIR/.venv}/bin/python"

echo "[bootstrap_dev] OK"
echo "- venv: ${VENV_DIR:-.venv}"
echo "- python: $("${VENV_PYTHON}" -c 'import sys; print(sys.executable)')"
