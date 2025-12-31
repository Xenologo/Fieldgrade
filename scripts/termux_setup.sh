#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

echo "[Termux] Updating packages..."
pkg update -y
pkg upgrade -y

echo "[Termux] Installing core dependencies..."
# sqlite is typically bundled, but keep explicit for clarity.
pkg install -y python git openssl libffi sqlite

echo "[Termux] Installing compiled Python deps via Termux packages (avoids pip builds)..."
# These names exist on most Termux repos; if any fail, just remove and rely on pip.
pkg install -y python-numpy python-cryptography || true

echo "[Termux] Creating venv (with system site packages enabled)..."
python -m venv .venv --system-site-packages
source .venv/bin/activate

echo "[Termux] Installing UI deps..."
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt

echo "[Termux] Installing local packages (no dependency resolution)..."
# We use --no-deps to prevent pip from attempting to build numpy/cryptography from source.
python -m pip install -e mite_ecology --no-deps
python -m pip install -e termite_fieldpack --no-deps
python -m pip install -e fieldgrade_ui --no-deps

echo
echo "[Termux] Done."
echo "Next:"
echo "  source .venv/bin/activate"
echo "  bash scripts/termux_run_ui.sh"
