<#
.SYNOPSIS
  Launch the local Fieldgrade UI server (Windows PowerShell)

.DESCRIPTION
  Installs optional UI dependencies from requirements-dev.txt and starts the FastAPI server.

  Then open:
    http://127.0.0.1:8787/
#>

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

$VENV = Join-Path $ROOT ".venv"
$ACT = Join-Path $VENV "Scripts\Activate.ps1"

if (-not (Test-Path $ACT)) {
  python -m venv $VENV
}

. $ACT

# Install runtime deps and editable packages (safe to re-run)
pip install -q -r (Join-Path $ROOT "requirements.txt")
pip install -q -r (Join-Path $ROOT "requirements-dev.txt")

pip install -q -e (Join-Path $ROOT "termite_fieldpack")
pip install -q -e (Join-Path $ROOT "mite_ecology")
pip install -q -e (Join-Path $ROOT "fieldgrade_ui")

python -m fieldgrade_ui serve
