<#
.SYNOPSIS
  Bootstrap dev environment for Fieldgrade (Windows PowerShell)

.DESCRIPTION
  Creates/uses .venv, installs runtime + dev deps, and installs editable packages:
  - termite_fieldpack
  - mite_ecology
  - fieldgrade_ui

  Intended to be idempotent.
#>

$ErrorActionPreference = "Stop"

$ROOT = (Resolve-Path (Join-Path $PSScriptRoot ".."))
Set-Location $ROOT

$VENV_DIR = if ($env:VENV_DIR) { $env:VENV_DIR } else { ".venv" }
$ACT = Join-Path $VENV_DIR "Scripts\Activate.ps1"

if (-not (Test-Path $ACT)) {
  python -m venv $VENV_DIR
}

. $ACT

python -m pip install -U pip

python -m pip install -r (Join-Path $ROOT "requirements.txt")
python -m pip install -r (Join-Path $ROOT "requirements-dev.txt")

python -m pip install -e (Join-Path $ROOT "termite_fieldpack")
python -m pip install -e (Join-Path $ROOT "mite_ecology")
python -m pip install -e (Join-Path $ROOT "fieldgrade_ui")

Write-Host "[bootstrap_dev] OK" -ForegroundColor Green
Write-Host "- venv: $VENV_DIR" -ForegroundColor DarkGray
Write-Host ("- python: " + (python -c "import sys; print(sys.executable)")) -ForegroundColor DarkGray
