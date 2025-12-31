#!/usr/bin/env bash
set -euo pipefail

# Production-ish server launcher (pre-fork model).
# Works on Linux/macOS; and also tends to work fine on Termux,
# but keep WORKERS modest to avoid memory pressure.

# Accept multiple env var conventions:
#  - FIELDGRADE_UI_HOST/PORT/WORKERS (preferred)
#  - FG_HOST/FG_PORT/FG_WORKERS (common)
#  - HOST/PORT/WORKERS (legacy)

: "${HOST:=${FIELDGRADE_UI_HOST:-${FG_HOST:-0.0.0.0}}}"
: "${PORT:=${FIELDGRADE_UI_PORT:-${FG_PORT:-8787}}}"
: "${WORKERS:=${FIELDGRADE_UI_WORKERS:-${FG_WORKERS:-2}}}"

# Avoid installing at runtime if already available.
python - <<'PY'
import importlib.util, sys
missing = []
for pkg in ("gunicorn", "uvicorn"):
    if importlib.util.find_spec(pkg) is None:
        missing.append(pkg)
if missing:
    print("Missing packages:", ", ".join(missing), file=sys.stderr)
    print("Install them with: pip install gunicorn uvicorn", file=sys.stderr)
    sys.exit(2)
PY

exec gunicorn -w "${WORKERS}" -k uvicorn.workers.UvicornWorker -b "${HOST}:${PORT}" fieldgrade_ui.app:app
