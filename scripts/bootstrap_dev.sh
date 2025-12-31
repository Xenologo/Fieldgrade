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

VENV_DIR="${VENV_DIR:-.venv}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PY_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install -U pip

# Install base + dev deps
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt

# Editable installs (ensures CLI entrypoints + imports work)
python -m pip install -e termite_fieldpack
python -m pip install -e mite_ecology
python -m pip install -e fieldgrade_ui

echo "[bootstrap_dev] OK"
echo "- venv: $VENV_DIR"
echo "- python: $(python -c 'import sys; print(sys.executable)')"