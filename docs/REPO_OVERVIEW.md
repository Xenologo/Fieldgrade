# Fieldgrade repo overview

This repository is a small, reproducible full-stack system that combines:

- Offline-first ingestion into a content-addressed store (CAS)
- Deterministic, replayable “delta” application into a lightweight knowledge graph (KG)
- Deterministic CPU/NumPy analysis (embeddings, attention, motifs, GA)
- A minimal FastAPI UI/API for running and observing the pipeline

It is designed to be run on Linux/WSL, Windows PowerShell, and Termux.

---

## High-level structure

### termite_fieldpack/

A fieldable toolchain that can:

- Ingest files into a CAS + SQLite (+ FTS5 when available)
- Emit hash-chained provenance events
- Produce a signed, deterministic bundle (manifest + SBOM + provenance + `kg_delta.jsonl` + blobs)
- Verify bundles against MEAP policy + tool allowlist
- Replay bundles conservatively (structural checks; no tool re-execution)

### mite_ecology/

Consumes verified Termite bundles and runs a deterministic pipeline:

- Applies `kg_delta.jsonl` to the KG
- Computes deterministic message-passing embeddings (CPU + NumPy)
- Computes deterministic “GAT-style” attention over edges
- Mines motifs from top-attention edges
- Runs a memoized deterministic GA and exports artifacts

Ingestion acceptance supports explicit modes (policy or override):

- `AUTO_MERGE`: apply immediately if KG remains valid
- `REVIEW_ONLY`: stage delta for review
- `QUARANTINE`: stage delta in quarantine
- `KILL`: refuse

### fieldgrade_ui/

A FastAPI UI/API with:

- Registry endpoints (components/variants/remotes)
- Lightweight graph query endpoints (`/api/graph/*`)
- Job/worker endpoints for running heavier tasks asynchronously
- Optional embedded worker/watch threads

A generated OpenAPI document exists at:

- `openapi/fieldgrade_ui.openapi.json`

### schemas/ and resources/

- `schemas/` contains versioned JSON schemas (registries, deltas, shapes, etc.)
- `resources/` contains demo resources, prompt caches, and other inputs used by scripts

---

## Development environment

### Bootstrapping

Canonical setup scripts:

- Linux/WSL: `scripts/bootstrap_dev.sh`
- Windows: `scripts/bootstrap_dev.ps1`

### Tests

- `make test` on Linux/WSL (see `Makefile`)
- `python -m pytest -q` on Windows

Warnings policy:

- `DeprecationWarning` and `PendingDeprecationWarning` are treated as errors (CI gate)

### CI

GitHub Actions CI runs on Linux and Windows and includes hygiene checks and docker config/build validation:

- `.github/workflows/ci.yml`

---

## Pipeline and deterministic execution

The repo is structured so that the same inputs yield the same on-disk artifacts (hashes, deltas, reports), assuming the same environment and no new non-deterministic external signals.

Key mechanisms:

- Canonical JSON serialization wherever hashes are computed
- Hash-chained logs across multiple “ledger” tables/files
- Deterministic CPU/NumPy computations (no torch)
- Conservative bundle verification and schema validation before application

LLM notes:

- LLM output is treated as exogenous unless cached
- Termite can “own” a local OpenAI-compatible endpoint identity and expose it to the rest of the stack

---

## Cross-platform support

- Windows laptop guide: `WINDOWS.md`
- Termux guide: `TERMUX.md`

The UI typically binds on `http://127.0.0.1:8787` in dev flows.

---

## Strengths

- Deterministic and auditable design (hash-chains, canonicalization, conservative replay)
- Governance-oriented acceptance modes (`AUTO_MERGE`, `REVIEW_ONLY`, `QUARANTINE`, `KILL`)
- Cross-platform scripts and docs (Linux/WSL, Windows, Termux)
- CI already in place with hygiene + test matrix + docker config validation

---

## Areas to improve (repo-accurate)

- Make CI results more visible in docs (README badges, how to interpret CI jobs)
- Expand docs around key management/secrets handling for signing and API tokens
- Consider tightening dependency pinning across submodules to reduce mismatch risk
- Improve UI discoverability (screenshots/GIFs, “what to click” quickstart)

---

## Pointers

- Architecture overview: `ARCH_MAP.md` and `docs/ARCH_MAP.md`
- Deployment topology: `DEPLOYMENT_TOPOLOGY.md` and `docs/DEPLOYMENT_TOPOLOGY.md`
- Local LLM runtime: `docs/LLM_RUNTIME.md`
- Demo scripts: `run_demo.sh`, `run_demo.ps1`, and `scripts/smoke_compose_e2e.*`
