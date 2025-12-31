# Local deploy (Docker Compose)

This runs the existing local architecture in containers:
- **web**: FastAPI UI/API (`python -m fieldgrade_ui serve`)
- **worker**: background job worker (`python -m fieldgrade_ui worker`)

State is persisted via Docker named volumes (SQLite DBs + artifacts).

## Prereqs

- Docker Desktop (or Docker Engine + Compose)

## 1) Configure env

Copy the example env and set a token:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set `FG_API_TOKEN` to a long random value.

Why: the server refuses to bind to `0.0.0.0` without `FG_API_TOKEN`.
Compose is configured to fail fast if `FG_API_TOKEN` is missing.

## 2) Build + run

```bash
docker compose up --build
```

## Smoke test (one command)

After the stack is up (or even if it isn't), you can run an end-to-end pipeline smoke test:

```powershell
./scripts/smoke_compose_e2e.ps1
```

This enqueues a pipeline job via the API and waits until it finishes.

Open:
- http://localhost:8787

In the UI header, paste your `FG_API_TOKEN` into **API token** and click **Set**.
(Static `/` loads without auth; API calls require the token.)

## 3) Persistent data locations

Compose mounts named volumes into these in-container paths:
- `/app/termite_fieldpack/runtime` (uploads, keys, CAS, termite.sqlite)
- `/app/termite_fieldpack/artifacts` (bundles_out)
- `/app/mite_ecology/runtime` (mite_ecology.sqlite, reports)
- `/app/mite_ecology/artifacts` (exports)
- `/app/fieldgrade_ui/runtime` (jobs.sqlite)

## 4) Reset / clean slate

To stop:

```bash
docker compose down
```

To delete persisted data too:

```bash
docker compose down -v
```

## Notes

- For safety and determinism, the platform treats sealed bundle ZIPs as immutable evidence artifacts.
- If you change `FG_CMD_TIMEOUT_S`, it affects the subprocess timeouts for Termite/Mite calls.
