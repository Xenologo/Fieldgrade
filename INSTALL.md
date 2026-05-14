# Fieldgrade installation guide

This guide is intentionally practical. Start with the option that matches how much of Fieldgrade you need to evaluate.

## Option A — Try the static demo

Use the public site materials first if you only need the buyer-facing narrative and sample outputs.

- Open `/site/landing.html`
- Review `/site/demo/index.html`
- Inspect sample deliverables under `/exports`

## Option B — Run locally with Docker

Recommended for pilot evaluation on a developer workstation or single host.

1. Install Docker Engine and the Docker Compose plugin.
2. From the repository root:

   ```bash
   export FG_API_TOKEN=demo-local-token
   docker compose -f compose.yaml -f compose.dev.yaml up -d --build
   ```

3. Open `http://127.0.0.1:8787`
4. Use the same token in the `X-API-Key` header for API requests.
5. Confirm health:

   ```bash
   curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/healthz
   curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/readyz
   ```

6. Stop the stack when finished:

   ```bash
   docker compose -f compose.yaml -f compose.dev.yaml down
   ```

## Option C — Run locally with Python

Recommended for development, CLI usage, or test execution.

### Linux / WSL

```bash
cd /home/runner/work/Fieldgrade/Fieldgrade
bash scripts/bootstrap_dev.sh
./.venv/bin/python -m pytest -q
```

### Windows PowerShell

```powershell
cd C:\path\to\Fieldgrade
.\scripts\bootstrap_dev.ps1
.\.venv\Scripts\python -m pytest -q
```

## Option D — VPS deployment

Recommended for founder-led pilot installs, not anonymous self-serve production.

1. Review `docs/DEPLOY_PROD_SINGLEHOST.md`
2. Review `docs/DEPLOY_CHECKLIST.md`
3. Set:
   - `FG_API_TOKEN`
   - `FIELDGRADE_DOMAIN`
   - `FG_FORWARDED_ALLOW_IPS`
4. Launch:

   ```bash
   docker compose -f compose.yaml -f compose.production.yaml up -d --build
   ```

5. Validate `/healthz` and `/readyz` through the deployed endpoint
6. Verify backups before onboarding real customer evidence

## Troubleshooting

- **Port 8787 already in use:** stop the conflicting process or change the local bind in `compose.dev.yaml`
- **401/403 responses:** verify that `FG_API_TOKEN` is set and that requests include `X-API-Key`
- **Compose config fails:** confirm required environment variables are present before running `docker compose`
- **Tests fail during bootstrap:** recreate `.venv` and run `bash scripts/bootstrap_dev.sh` again

## Uninstall

### Docker deployment

```bash
docker compose -f compose.yaml -f compose.dev.yaml down -v
```

### Python environment

Remove the virtual environment and any local runtime/artifact directories you no longer need.

## Where data is stored

- `termite_fieldpack/runtime`
- `termite_fieldpack/artifacts`
- `mite_ecology/runtime`
- `mite_ecology/artifacts`
- `fieldgrade_ui/runtime`

Docker deployments persist the same paths through named volumes.

## Backup basics

- Back up runtime and artifact volumes before upgrades
- Test restore procedures before storing important evidence
- Keep backups encrypted and access-controlled
- Review `DATA_HANDLING.md` and the deployment docs for retention expectations
