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

function Test-PortInUse {
  param(
    [Parameter(Mandatory=$true)][int]$Port
  )
  try {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
    return $null -ne $conn
  } catch {
    return $false
  }
}

# If the caller didn't specify FG_PORT, prefer 8787 but fall back to 8788 when 8787 is occupied
# (common on Windows when WSL/Docker port-forwarding is holding 8787).
if (-not $env:FG_PORT -or $env:FG_PORT.Trim() -eq "") {
  $preferred = 8787
  if (Test-PortInUse -Port $preferred) {
    $env:FG_PORT = "8788"
  } else {
    $env:FG_PORT = "$preferred"
  }
}

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

Write-Host "Fieldgrade UI: http://127.0.0.1:$($env:FG_PORT)/" -ForegroundColor Green

python -m fieldgrade_ui serve
