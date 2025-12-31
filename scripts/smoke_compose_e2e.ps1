param(
    [string]$ApiToken = $env:FG_API_TOKEN,
    [string]$BaseUrl = "http://localhost:8787",
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = 'Stop'

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

Require-Command "docker"

if (-not $ApiToken -or $ApiToken.Trim() -eq "") {
    throw "FG_API_TOKEN is required. Set it in .env or pass -ApiToken."
}

# Ensure we're running from repo root (where compose.yaml lives)
$here = Get-Location
if (-not (Test-Path (Join-Path $here "compose.yaml"))) {
    throw "Run this from the fg_next folder (compose.yaml not found in $here)."
}

# Use Docker Desktop Linux engine if available
try { docker context use desktop-linux | Out-Null } catch { }

Write-Host "[smoke] Ensuring compose is up..."
docker compose up -d | Out-Null

# Wait until API is reachable (auth required for /api/state)
$headers = @{ "X-API-Key" = $ApiToken }
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-RestMethod -Uri "$BaseUrl/api/state" -Headers $headers -Method Get | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $ready) {
    Write-Host "[smoke] web did not become ready in time" -ForegroundColor Red
    docker compose ps
    docker compose logs --tail 200 web
    throw "web not ready"
}

Write-Host "[smoke] Initializing Termite runtime (idempotent)..."
docker compose exec -T web sh -lc "cd /app/termite_fieldpack; python -m termite.cli init" | Out-Null

Write-Host "[smoke] Creating a tiny upload file inside the shared uploads volume..."
$label = "smoke_" + (Get-Date -Format "yyyyMMddTHHmmss")
$uploadPath = "/app/termite_fieldpack/runtime/uploads/$label.txt"
docker compose exec -T web sh -lc "mkdir -p /app/termite_fieldpack/runtime/uploads; echo 'fieldgrade smoke test' > '$uploadPath'" | Out-Null

Write-Host "[smoke] Enqueuing pipeline job via API..."
$body = @{ upload_path = $uploadPath; label = $label } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri "$BaseUrl/api/jobs/pipeline" -Method Post -Headers $headers -ContentType "application/json" -Body $body
$jobId = [int]$resp.job_id
Write-Host "[smoke] job_id=$jobId"

Write-Host "[smoke] Waiting for job to complete (timeout ${TimeoutSeconds}s)..."
$final = $null
while ((Get-Date) -lt $deadline) {
    $j = Invoke-RestMethod -Uri "$BaseUrl/api/jobs/$jobId" -Headers $headers -Method Get
    $status = $j.job.status
    Write-Host "[smoke] status=$status"
    if ($status -in @('succeeded', 'failed', 'canceled')) {
        $final = $j
        break
    }
    Start-Sleep -Seconds 2
}

if (-not $final) {
    Write-Host "[smoke] job did not reach terminal status in time" -ForegroundColor Red
    docker compose logs --tail 200 worker
    throw "job timeout"
}

$logs = Invoke-RestMethod -Uri "$BaseUrl/api/jobs/$jobId/logs?limit=500" -Headers $headers -Method Get

if ($final.job.status -ne 'succeeded') {
    Write-Host "[smoke] FAILED job status=$($final.job.status)" -ForegroundColor Red
    $final | ConvertTo-Json -Depth 30
    $logs | ConvertTo-Json -Depth 30
    docker compose logs --tail 200 worker
    exit 1
}

Write-Host "[smoke] OK (succeeded)" -ForegroundColor Green
$logs | ConvertTo-Json -Depth 10
exit 0
