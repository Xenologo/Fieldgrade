# Fieldgrade Fullstack (STRICT DSSE + CycloneDX) — Architecture Map

This repo is a **deterministic, provenance-first ingestion + verification** stack composed of three primary Python packages.

## 1) Runtime components (today)

### A. `termite_fieldpack/` — offline “field toolchain”
**Role:** ingest local files into a content-addressed store, maintain append-only provenance, emit sealed bundles, verify/replay bundles.

**Primary interfaces**
- CLI: `termite` → implemented in `termite_fieldpack/termite/cli.py`.

**Local state / storage**
- SQLite DB (runtime): `termite_fieldpack/runtime/termite.sqlite` (path is configurable via `termite_fieldpack/config/termite.yaml`).
- CAS (content-addressed blobs): `termite_fieldpack/runtime/cas/` (configurable).
- Provenance (hash-chained events): stored in SQLite tables and exported as bundle artifacts.

**Artifacts produced**
- Bundles: `termite_fieldpack/artifacts/bundles_out/*.zip`
- Bundle contents (high level):
  - `manifest.json` (canonical JSON; stable ordering/serialization)
  - `attestation.json` + `attestation.sig` (legacy, ed25519)
  - `attestation.dsse.json` (DSSE envelope binding manifest digest)
  - `sbom/bom.cdx.json` (CycloneDX BOM JSON; current implementation defaults `spec_version="1.5"`)
  - `sbom/bom.dsse.json` (DSSE envelope binding the BOM digest)
  - `provenance/*` (hash-chained provenance material)
  - `kg_delta.jsonl` (KG delta operations)
  - `blobs/*` (CAS material as referenced by manifest)

**Verification semantics**
- Verification is done by `termite_fieldpack/termite/verify.py`:
  - Policy gates: MEAP policy (`termite_fieldpack/config/meap_v1.yaml`)
  - Tool allowlist: `termite_fieldpack/config/tool_allowlist.yaml`
  - Strict checks can require DSSE attestations and CycloneDX SBOM (`require_dsse_attestations`, `require_cyclonedx_sbom`).

### B. `mite_ecology/` — design-time deterministic KG pipeline
**Role:** accept verified termite bundles, stage/approve/reject KG deltas, apply deltas to a local KG, run deterministic analytics, export artifacts.

**Primary interfaces**
- CLI: `mite-ecology` → implemented in `mite_ecology/mite_ecology/cli.py`.

**Local state / storage**
- SQLite KG DB: `mite_ecology/runtime/mite_ecology.sqlite` (configurable via `mite_ecology/configs/*.yaml`).
- Staging/review tables: staged bundle imports + decisions live in the same DB.
- Hash-chain verification/replay: `mite_ecology/mite_ecology/replay.py`.

**Key flows**
- `import-bundle` → `accept_termite_bundle(...)`:
  - Re-verifies policy/signature as part of acceptance
  - Validates KG ops against `schemas/kg_delta.json` and local constraints
  - Supports review queue and idempotent import semantics

**Deterministic compute**
- GNN embeddings: NumPy message passing (`mite_ecology/mite_ecology/gnn.py`)
- GAT-style attention: deterministic scoring (`mite_ecology/mite_ecology/gat.py`)
- Motif mining: `mite_ecology/mite_ecology/motif.py`
- Deterministic GA: memoized RNG seeded from stable hashes (`mite_ecology/mite_ecology/memoga.py`)

**Artifacts produced**
- Exports: `mite_ecology/artifacts/export/*`
- Reports (e.g. autorun): `mite_ecology/runtime/reports/*.json`

### C. `fieldgrade_ui/` — local UI/API + background worker
**Role:** provide a local web UI and API that orchestrate the termite→verify→mite pipeline.

**Primary interfaces**
- FastAPI app: `fieldgrade_ui/app.py`
- Entry: `python -m fieldgrade_ui serve` (or `fieldgrade-ui` script)
- Worker: `python -m fieldgrade_ui worker`

**Operational model (today)**
- Runs **local subprocesses** for Termite and Mite:
  - `python -m termite.cli ...` with `cwd=termite_fieldpack/`
  - `python -m mite_ecology.cli ...` with `cwd=mite_ecology/`
- Uploads are written to local disk and sandboxed:
  - default uploads dir: `termite_fieldpack/runtime/uploads/`
  - sandbox enforced in UI API to avoid “file oracle” behavior

**Local state / storage**
- Jobs DB: `fieldgrade_ui/runtime/jobs.sqlite` (SQLite + WAL).

**Notable endpoints (selected)**
- UI shell: `GET /` (static HTML)
- State: `GET /api/state`
- Upload: `POST /api/pipeline/upload_run` (requires `python-multipart`)
- Job queue: `GET /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/pipeline`
- Termite orchestration: `/api/termite/ingest|seal|verify|replay|spec_validate`
- Ecology orchestration: `/api/ecology/init|import|full_pipeline|review_*|replay_verify`
- Lightweight metrics: `GET /api/metrics` (JSON)

**Current access control**
- By default refuses to bind to non-loopback unless `FG_API_TOKEN` is set.
- If `FG_API_TOKEN` is set: middleware requires `X-API-Key` (or `Authorization: Bearer`).

## 2) Top-level glue / scripts

- Monorepo install/test:
  - `requirements.txt` includes the three package requirement files.
  - `Makefile` provides `make install` and `make test` (pytest).
- Windows helpers:
  - `run_ui.ps1`, `run_worker.ps1`, `run_demo.ps1`

## 3) Dataflow (happy path)

1. User provides input file (CLI ingest or UI upload).
2. Termite ingests to CAS + sqlite + provenance.
3. Termite seals a deterministic bundle ZIP.
4. Termite verifies bundle against MEAP policy + allowlist; strict mode can require DSSE + CycloneDX.
5. Mite imports bundle: validates, stages or merges KG delta ops (review workflow supported).
6. Mite runs deterministic pipeline (gnn → gat → motifs → ga → export).

## 4) Determinism + provenance invariants (non-negotiables)

- Canonical JSON serialization for hash binding.
- Hash-chained logs for provenance and for ingest/replay verification.
- Bundles treated as immutable bytes once sealed.
- DSSE verification binds payload digests to key identity (`keyid`) and policy thresholds.
- Any live LLM calls are exogenous unless cached and replayed.
