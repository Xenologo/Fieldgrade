<#
.SYNOPSIS
  Launch the Fieldgrade background worker (Windows PowerShell)

.DESCRIPTION
  Ensures a local venv exists, installs requirements, installs editable packages,
  then runs the SQLite-backed job worker.

  Use alongside run_ui.ps1 for "volume" mode:
    Terminal 1: .\run_ui.ps1
    Terminal 2: .\run_worker.ps1
#>

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

$VENV = Join-Path $ROOT ".venv"
$ACT = Join-Path $VENV "Scripts\Activate.ps1"

if (-not (Test-Path $ACT)) {
  python -m venv $VENV
}

. $ACT

pip install -q -r (Join-Path $ROOT "requirements.txt")
pip install -q -e (Join-Path $ROOT "termite_fieldpack")
pip install -q -e (Join-Path $ROOT "mite_ecology")
pip install -q -e (Join-Path $ROOT "fieldgrade_ui")

python -m fieldgrade_ui worker
