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

python -m pip install -U pip
python -m pip install uv

$resolvedVenv = if ($env:VENV_DIR) { (Join-Path $ROOT $env:VENV_DIR) } else { (Join-Path $ROOT ".venv") }
$env:UV_PROJECT_ENVIRONMENT = $resolvedVenv
uv sync --frozen --group dev

Write-Host "[bootstrap_dev] OK" -ForegroundColor Green
Write-Host ("- venv: " + $resolvedVenv) -ForegroundColor DarkGray
Write-Host ("- python: " + (& (Join-Path $resolvedVenv "Scripts\python.exe") -c "import sys; print(sys.executable)")) -ForegroundColor DarkGray
