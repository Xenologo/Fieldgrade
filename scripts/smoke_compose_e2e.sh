#!/usr/bin/env bash
set -euo pipefail

API_TOKEN="${FG_API_TOKEN:-}"
BASE_URL="${FG_BASE_URL:-http://localhost:8787}"
TIMEOUT_S="${FG_SMOKE_TIMEOUT_S:-300}"

if [[ -z "$API_TOKEN" ]]; then
  echo "FG_API_TOKEN is required (export it or set in .env)." >&2
  exit 2
fi

if [[ ! -f "compose.yaml" ]]; then
  echo "Run this from the fg_next folder (compose.yaml not found)." >&2
  exit 2
fi

# Prefer Docker Desktop Linux engine if present
(docker context use desktop-linux >/dev/null 2>&1) || true

echo "[smoke] Ensuring compose is up..."
docker compose up -d >/dev/null

# Wait for web readiness (token required)

deadline=$(( $(date +%s) + TIMEOUT_S ))
ready=0
while [[ $(date +%s) -lt $deadline ]]; do
  if curl -fsS -H "X-API-Key: $API_TOKEN" "$BASE_URL/api/state" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [[ $ready -ne 1 ]]; then
  echo "[smoke] web did not become ready in time" >&2
  docker compose ps || true
  docker compose logs --tail 200 web || true
  exit 1
fi

echo "[smoke] Initializing Termite runtime (idempotent)..."
docker compose exec -T web sh -lc "cd /app/termite_fieldpack; python -m termite.cli init" >/dev/null

label="smoke_$(date +%Y%m%dT%H%M%S)"
upload_path="/app/termite_fieldpack/runtime/uploads/${label}.txt"

echo "[smoke] Creating a tiny upload file..."
docker compose exec -T web sh -lc "mkdir -p /app/termite_fieldpack/runtime/uploads; echo 'fieldgrade smoke test' > '$upload_path'" >/dev/null

echo "[smoke] Enqueuing pipeline job via API..."
job_id=$(curl -fsS \
  -H "X-API-Key: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"upload_path\":\"$upload_path\",\"label\":\"$label\"}" \
  "$BASE_URL/api/jobs/pipeline" | python -c "import sys, json; print(json.load(sys.stdin)['job_id'])")

echo "[smoke] job_id=$job_id"

echo "[smoke] Waiting for job to complete (timeout ${TIMEOUT_S}s)..."
status=""
while [[ $(date +%s) -lt $deadline ]]; do
  status=$(curl -fsS -H "X-API-Key: $API_TOKEN" "$BASE_URL/api/jobs/$job_id" | python -c "import sys, json; print(json.load(sys.stdin)['job']['status'])")
  echo "[smoke] status=$status"
  if [[ "$status" == "succeeded" || "$status" == "failed" || "$status" == "canceled" ]]; then
    break
  fi
  sleep 2
done

logs=$(curl -fsS -H "X-API-Key: $API_TOKEN" "$BASE_URL/api/jobs/$job_id/logs?limit=500" || true)

if [[ "$status" != "succeeded" ]]; then
  echo "[smoke] FAILED status=$status" >&2
  echo "$logs" >&2
  docker compose logs --tail 200 worker || true
  exit 1
fi

echo "[smoke] OK (succeeded)"
echo "$logs"
