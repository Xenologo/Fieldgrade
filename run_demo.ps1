<#
.SYNOPSIS
    End-to-end demo for mite_ecology_fullstack (Windows PowerShell)

.DESCRIPTION
    This script:
    1. Creates/activates a Python venv if needed
    2. Installs both termite_fieldpack and mite_ecology in editable mode
    3. Runs the full Termite → seal → verify → replay pipeline
    4. Imports the bundle into mite_ecology
    5. Runs gnn → gat → motifs → ga → export
    6. Prints output paths

.NOTES
    Run from the monorepo root:
        .\run_demo.ps1
#>

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " mite_ecology_fullstack - Windows Demo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Venv setup ---
$VENV = Join-Path $ROOT ".venv"
$VENV_ACTIVATE = Join-Path $VENV "Scripts\Activate.ps1"

if (-not (Test-Path $VENV_ACTIVATE)) {
    Write-Host "[1/7] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $VENV
} else {
    Write-Host "[1/7] Virtual environment exists" -ForegroundColor Green
}

Write-Host "[1/7] Activating venv..." -ForegroundColor Yellow
. $VENV_ACTIVATE

# --- 2. Install packages ---
Write-Host "[2/7] Installing packages (editable)..." -ForegroundColor Yellow
pip install -q -r (Join-Path $ROOT "termite_fieldpack\requirements.txt")
pip install -q -r (Join-Path $ROOT "mite_ecology\requirements.txt")
pip install -q -e (Join-Path $ROOT "termite_fieldpack")
pip install -q -e (Join-Path $ROOT "mite_ecology")

# --- 3. Termite init + ingest ---
Write-Host "[3/7] Termite: init + ingest README.md..." -ForegroundColor Yellow
Push-Location (Join-Path $ROOT "termite_fieldpack")

python -m termite.cli init
$ingestResult = python -m termite.cli ingest (Join-Path $ROOT "README.md")
Write-Host "  Ingest result: $ingestResult" -ForegroundColor DarkGray

# --- 4. Seal bundle ---
Write-Host "[4/7] Termite: seal bundle..." -ForegroundColor Yellow
$BUNDLE = (python -m termite.cli seal --label demo).Trim()
Write-Host "  Bundle: $BUNDLE" -ForegroundColor DarkGray

# --- 5. Verify + Replay ---
Write-Host "[5/7] Termite: verify + replay..." -ForegroundColor Yellow
$verifyResult = python -m termite.cli verify $BUNDLE | ConvertFrom-Json
if ($verifyResult.ok) {
    Write-Host "  Verify: OK" -ForegroundColor Green
} else {
    Write-Host "  Verify: FAILED - $($verifyResult.reason)" -ForegroundColor Red
    exit 1
}

$replayResult = python -m termite.cli replay $BUNDLE | ConvertFrom-Json
if ($replayResult.ok) {
    Write-Host "  Replay: OK ($($replayResult.events) events, $($replayResult.kg_ops) kg_ops)" -ForegroundColor Green
} else {
    Write-Host "  Replay: FAILED - $($replayResult.reason)" -ForegroundColor Red
    exit 1
}

Pop-Location

# --- 6. mite_ecology pipeline ---
Write-Host "[6/7] Ecology: init + import + gnn/gat/motifs/ga..." -ForegroundColor Yellow
Push-Location (Join-Path $ROOT "mite_ecology")

python -m mite_ecology.cli init
python -m mite_ecology.cli import-bundle $BUNDLE

Write-Host "  Running GNN embeddings..." -ForegroundColor DarkGray
python -m mite_ecology.cli gnn

Write-Host "  Running GAT attention..." -ForegroundColor DarkGray
python -m mite_ecology.cli gat

Write-Host "  Mining motifs..." -ForegroundColor DarkGray
python -m mite_ecology.cli motifs

Write-Host "  Running GA..." -ForegroundColor DarkGray
$gaResult = python -m mite_ecology.cli ga | ConvertFrom-Json
Write-Host "  Best fitness: $($gaResult.best_fitness)" -ForegroundColor Green

# --- 7. Export ---
Write-Host "[7/7] Ecology: export..." -ForegroundColor Yellow
$exportPath = (python -m mite_ecology.cli export).Trim()

Pop-Location

# --- Summary ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Demo Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  Bundle:  $BUNDLE"
Write-Host "  Export:  $exportPath"
Write-Host ""
Write-Host "Artifacts directories:" -ForegroundColor Green
Write-Host "  Bundles: $ROOT\termite_fieldpack\artifacts\bundles_out\"
Write-Host "  Exports: $ROOT\mite_ecology\artifacts\export\"
