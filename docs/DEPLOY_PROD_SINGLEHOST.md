# Single-host production deployment (Docker Compose + Caddy)

This is the fastest path to a “real web” deployment while keeping Fieldgrade’s strict invariants (bundle bytes are immutable; DSSE/CycloneDX semantics unchanged).

## Prereqs

- A Linux VM or bare-metal host with Docker installed.
- Ports 80/443 reachable from the internet (for automatic HTTPS).
- A DNS `A`/`AAAA` record pointing your domain at the host.

## Files

- `compose.yaml` (base)
- `compose.dev.yaml` (dev-only override; exposes `8787` on the host)
- `compose.production.yaml` (production overlay)
- `Caddyfile` (HTTPS reverse proxy)

## Configure

Create a `.env` file next to `compose.yaml`:

Tip: start from `.env.production.example` and edit.

- `FG_API_TOKEN` (required): token required by the API (`X-API-Key` header)
- `FIELDGRADE_DOMAIN` (required): your public hostname (e.g. `fieldgrade.example.com`)

Behind Caddy (TLS termination), configure proxy header trust explicitly:

- `FG_PROXY_HEADERS=1`
- `FG_FORWARDED_ALLOW_IPS` (required): trusted IPs/CIDRs for forwarded headers
  - Recommended: set this to your Docker network subnet (CIDR) so only in-network traffic is trusted.
  - After the stack has been brought up at least once (so the network exists), find the subnet with:
    - `docker network inspect fg_next_default --format '{{(index .IPAM.Config 0).Subnet}}'`
  - If your compose project name differs, the network will be `<project>_default`. To discover it:
    - `docker network ls | grep _default`

Bootstrap note (CIDR chicken-and-egg):

- First boot requires *some* `FG_FORWARDED_ALLOW_IPS` value. For the initial bring-up, you can temporarily set:
  - `FG_FORWARDED_ALLOW_IPS=*`
- Bring the stack up once, inspect the CIDR, then set `FG_FORWARDED_ALLOW_IPS=<CIDR>` and redeploy.

Optional (future-facing knobs):

- `DATABASE_URL`: today must be SQLite (e.g. `sqlite:////app/fieldgrade_ui/runtime/jobs.sqlite`). Postgres is a Phase B change.
- `FG_BUNDLE_STORE`: `local` (default) or `s3`
- `FG_S3_BUCKET` (required when `FG_BUNDLE_STORE=s3`): bucket name
- `FG_S3_PREFIX` (optional): key prefix within the bucket

When `FG_BUNDLE_STORE=s3`, the container uses `boto3` and the standard AWS env vars:

- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (required for most setups)
- `AWS_SESSION_TOKEN` (optional; required for some temporary credentials)
- `AWS_REGION` or `AWS_DEFAULT_REGION` (recommended)

For S3-compatible endpoints (e.g. MinIO), also set:

- `AWS_ENDPOINT_URL` (e.g. `http://minio:9000` inside a Docker network, or a full URL)

## Deploy

From the `fg_next/` directory on the host:

- Build and start:
  - `docker compose -f compose.yaml -f compose.production.yaml up -d --build`

For local dev (direct host port, no Caddy):

- `docker compose -f compose.yaml -f compose.dev.yaml up -d --build`

- Tail logs:
  - `docker compose logs -f --tail=200`

- Health:
  - `docker compose ps` should show `web` as `healthy` (the container healthcheck hits `/healthz`).

## Verify

- HTTPS:
  - Visit `https://$FIELDGRADE_DOMAIN/` (Caddy provisions a TLS cert automatically once DNS and ports are correct).

- API:
  - `curl -H "X-API-Key: $FG_API_TOKEN" https://$FIELDGRADE_DOMAIN/healthz`

## Notes

- Single-host mode keeps runtime state on the host (named volumes). Back up Docker volumes regularly.
- For multi-host / “platform” mode, move state to Postgres and bundles/artifacts to object storage (Phases B/C).
