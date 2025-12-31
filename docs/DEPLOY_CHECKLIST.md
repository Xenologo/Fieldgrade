# Deploy checklist (single-host v0)

This checklist is the minimal “deploy parity” guardrail for bringing up Fieldgrade as a real single-host web service using Docker Compose + Caddy TLS termination.

## 1) Clean repo sanity

- Confirm you are on the latest `main`:
  - `git checkout main`
  - `git pull --ff-only origin main`

- Confirm you are deploying from a clean tree:
  - `git status --porcelain=v1` (should be empty)

## 2) Environment (no defaults)

Create `.env` next to `compose.yaml` (start from `.env.production.example`):

- `FG_API_TOKEN=<long-random>`
- `FIELDGRADE_DOMAIN=<your.domain>`
- `FG_PROXY_HEADERS=1`
- `FG_FORWARDED_ALLOW_IPS=<trusted proxy IPs/CIDRs>`

Recommended: set `FG_FORWARDED_ALLOW_IPS` to the Docker network subnet (CIDR) so only in-network traffic is trusted.

- Discover on host:
  - `docker network inspect fg_next_default --format '{{(index .IPAM.Config 0).Subnet}}'`

Note: the network exists after the stack is brought up at least once, and the name is usually `<compose-project>_default`.

Bootstrap note: for the first bring-up (before you know the CIDR), you can temporarily set `FG_FORWARDED_ALLOW_IPS=*`, bring the stack up once, inspect the CIDR, then switch to `FG_FORWARDED_ALLOW_IPS=<CIDR>` and redeploy.

Optional bundle/object storage:

- `FG_BUNDLE_STORE=local|s3`
- If `s3`: `FG_S3_BUCKET=...` (+ optional `FG_S3_PREFIX=...`)
- AWS env vars for `boto3`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (and optionally `AWS_SESSION_TOKEN`)
- S3-compatible endpoints (MinIO/etc): `AWS_ENDPOINT_URL=...`

## 3) Compose validation (must pass)

- Render base + production overlay:
  - `docker compose -f compose.yaml -f compose.production.yaml config`

- Build + start:
  - `docker compose -f compose.yaml -f compose.production.yaml up -d --build`

- Logs (first boot):
  - `docker compose logs -f --tail=200`

- Health:
  - `docker compose ps` should show `web` as `healthy`.

VPS smoke (on-host):

- `docker compose -f compose.yaml -f compose.production.yaml config`
- `docker compose -f compose.yaml -f compose.production.yaml up -d --build`
- `docker compose ps`

## 4) Live proof checks (external)

From a machine outside the VPS (your laptop):

- `https://$FIELDGRADE_DOMAIN/healthz`
- `https://$FIELDGRADE_DOMAIN/readyz`

If scheme/redirect behavior is correct (no `http://` confusion), proxy headers are configured correctly.

## 5) Minimum ops (v0 survivability)

- Backups: all state is in Docker named volumes (including the SQLite jobs DB).
- Restarts: `compose.production.yaml` sets `restart: always`.

## 6) Rollback

- Revert to a known-good commit:
  - `git checkout <sha>`
  - `docker compose -f compose.yaml -f compose.production.yaml up -d --build`

## Optional: GitHub Actions deploy (workflow_dispatch)

This repo includes a manual deploy workflow: `.github/workflows/deploy_vps.yml`.

Required GitHub secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_PRIVATE_KEY`
- `VPS_SSH_KNOWN_HOSTS` (recommended; output of `ssh-keyscan -H <host>`)
- `VPS_PORT` (optional; defaults to 22)

Run it from the GitHub UI and provide:

- `deploy_path` (path to `fg_next/` on the VPS)
- `compose_files` (defaults to `compose.yaml compose.production.yaml`)
- `readyz_url` (external URL to `/readyz`)
