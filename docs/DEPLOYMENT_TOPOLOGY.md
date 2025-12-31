# Deployment topology recommendation (Phase A / MVP)

This repo is already a usable **single-machine** platform (FastAPI + SQLite + subprocess orchestration). For a fast, low-risk “shippable MVP”, keep that shape and containerize it as a single deployable unit first.

## Recommendation: Two-container MVP (web + worker) + shared volumes

### Why this topology
- Preserves **strict determinism**: the core deterministic parts live in Python + SQLite + local filesystem; no distributed concurrency surprises.
- Preserves **bundle immutability**: sealed bundles are written once to a volume; the platform never rewrites bytes.
- Minimizes dependencies: no Redis, no external queue, no distributed filesystem in Phase A.
- Matches current architecture: `fieldgrade_ui` already has a separate worker process and a `jobs.sqlite` queue.

### Containers

1) **web** (FastAPI UI/API)
- Process: `python -m fieldgrade_ui serve`
- Needs:
  - The repo code (or built wheel)
  - Read/write access to shared volumes for:
    - `termite_fieldpack/runtime/` (uploads, CAS, keys, termite.sqlite)
    - `termite_fieldpack/artifacts/` (bundles_out)
    - `mite_ecology/runtime/` (mite_ecology.sqlite, reports)
    - `mite_ecology/artifacts/` (exports)
    - `fieldgrade_ui/runtime/` (jobs.sqlite)

2) **worker** (background job consumer)
- Process: `python -m fieldgrade_ui worker`
- Needs the same mounted volumes as web, because jobs point at uploaded paths and results are written to the same artifact dirs.

### Volumes (explicit)

- `fg_termite_runtime` → `termite_fieldpack/runtime/`
- `fg_termite_artifacts` → `termite_fieldpack/artifacts/`
- `fg_mite_runtime` → `mite_ecology/runtime/`
- `fg_mite_artifacts` → `mite_ecology/artifacts/`
- `fg_ui_runtime` → `fieldgrade_ui/runtime/`

### Environment variables (already supported)
- `FG_HOST`, `FG_PORT`
- `FG_API_TOKEN` (recommended for any non-loopback binding)
- `FG_UPLOADS_DIR` (optional override)
- `FG_MAX_UPLOAD_BYTES` (upload safety)
- `FG_CMD_TIMEOUT_S` (subprocess hard timeout)

## Alternative (even simpler): Single-container “all-in-one”

Run the embedded worker thread inside the web server:
- Configure the web container with embedded worker enabled (see `fieldgrade_ui/config.py`).

Tradeoffs:
- Simpler deploy, but **less isolation** (worker failures share process resources).
- Recommended only for local demos.

## Next step topology (Phase B/C readiness)

Once you add multi-tenancy + billing + audit logs, the topology should evolve:

- **web-api**: FastAPI app (no embedded worker)
- **worker**: background jobs
- **postgres**: multi-tenant data model (orgs/projects/bundles/runs/audit)
- **object storage**: S3-compatible (MinIO in dev, managed S3/Blob in prod)

Important: keep **sealed bundle bytes immutable** regardless of storage backend. Object storage should store:
- raw bundle ZIP bytes as uploaded/sealed
- content hash and expected digest in DB

## What is “the database” today?

- Termite uses SQLite for runtime ingest/provenance (`termite_fieldpack/runtime/termite.sqlite`).
- Mite uses SQLite for KG + staging review (`mite_ecology/runtime/mite_ecology.sqlite`).
- UI uses SQLite for jobs queue (`fieldgrade_ui/runtime/jobs.sqlite`).

This is acceptable for Phase A containerization, but not for multi-tenant SaaS.
