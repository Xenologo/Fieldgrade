# Fieldgrade installation guide

This guide separates **pilot release install mode** from **development mode**.

## Install modes

- **Pilot release install mode** uses pinned lockfiles for deterministic evaluation and pilot deployment.
- **Development mode** uses the bootstrap scripts to install the editable workspace plus dev tooling.

## Option A — Try the static demo

Use the public site materials first if you only need the buyer-facing narrative and sample outputs.

- Open `/site/landing.html`
- Review `/site/demo/index.html`
- Inspect sample deliverables under `/exports`
- Review release assets under `/releases/v0.9.0-alpha`

## Option B — Run locally with Docker (pilot release mode)

Recommended for pilot evaluation on a developer workstation or single host.

The Docker image installs pinned runtime dependencies from `requirements.lock`.

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
   docker compose -f compose.yaml -f compose.dev.yaml exec -T web python -m fieldgrade_ui init
   curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/readyz
   ```

6. Stop the stack when finished:

   ```bash
   docker compose -f compose.yaml -f compose.dev.yaml down
   ```

## Option C — Run locally with the lockfile (pilot release mode)

Recommended when evaluating the Python install path directly.

### Linux / WSL

```bash
cd /path/to/Fieldgrade
python3 -m pip install -U uv
uv sync --frozen
./.venv/bin/python -m pytest -q
```

### Windows PowerShell

```powershell
cd C:\path\to\Fieldgrade
python -m pip install -U uv
uv sync --frozen
.\.venv\Scripts\python -m pytest -q
```

## Option D — Development mode

Use this when you want editable installs plus developer tooling.

### Linux / WSL

```bash
cd /path/to/Fieldgrade
bash scripts/bootstrap_dev.sh
./.venv/bin/python -m pytest -q
```

### Windows PowerShell

```powershell
cd C:\path\to\Fieldgrade
.\scripts\bootstrap_dev.ps1
.\.venv\Scripts\python -m pytest -q
```

## Option E — VPS deployment

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

- **`uv sync --frozen` fails:** refresh or regenerate the lockfiles only when intentionally updating dependencies, then re-run the command
- **Port 8787 already in use:** stop the conflicting process or change the local bind in `compose.dev.yaml`
- **401/403 responses:** verify that `FG_API_TOKEN` is set and that requests include `X-API-Key`
- **Compose config fails:** confirm required environment variables are present before running `docker compose`
- **`/readyz` returns `503`:** run `python -m fieldgrade_ui init` (or `fieldgrade-ui init-runtime`) inside the app environment, then retry
- **Tests fail during bootstrap:** remove `.venv` and run the install step again

## Uninstall

### Docker deployment

```bash
docker compose -f compose.yaml -f compose.dev.yaml down -v
```

### Python environment

Remove `.venv` and any local runtime or artifact directories you no longer need.

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
- Review `DATA_HANDLING.md`, `docs/PILOT_SECURITY_BRIEF.md`, and the deployment docs for retention expectations
