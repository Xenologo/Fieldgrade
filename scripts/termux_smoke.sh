#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

source .venv/bin/activate

echo "[Smoke] Python:"
python -V

echo "[Smoke] Import checks:"
python - <<'PY'
import mite_ecology, termite_fieldpack, fieldgrade_ui
print("mite_ecology:", mite_ecology.__version__ if hasattr(mite_ecology,"__version__") else "ok")
print("termite_fieldpack:", termite_fieldpack.__version__ if hasattr(termite_fieldpack,"__version__") else "ok")
print("fieldgrade_ui:", fieldgrade_ui.__version__ if hasattr(fieldgrade_ui,"__version__") else "ok")
PY

echo "[Smoke] Init mite_ecology DB (safe no-op if exists):"
python -m mite_ecology init || true

echo "[Smoke] Status:"
python -m mite_ecology status || true
python -m termite_fieldpack status || true

echo "[Smoke] OK"
