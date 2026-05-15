# Fieldgrade Technical Architecture

## Repository-grounded architecture

Fieldgrade is a Python monorepo with three primary implementation areas:

- `termite_fieldpack/` — evidence ingestion, content-addressed storage, provenance events, deterministic bundle sealing, verification, and replay.
- `mite_ecology/` — review and analysis workflows, deterministic graph operations, import modes, review queue actions, and export support.
- `fieldgrade_ui/` — FastAPI-based governance workspace and API shell for jobs, registries, governance records, runtime readiness, architecture views, and local UI operation.

The root `pyproject.toml` defines a workspace that depends on the three local packages. The root `Makefile` exposes `make test`, which installs the workspace with `uv` and runs `pytest`.

## Runtime entry points

- Root demo: `./run_demo.sh` on Linux or WSL and `./run_demo.ps1` on Windows.
- UI/API: `python -m fieldgrade_ui` or the `fieldgrade-ui` console script after installation.
- Termite CLI: `./termite_fieldpack/bin/termite` or installed `termite` entry point.
- mite_ecology CLI: `./mite_ecology/bin/mite-ecology` or installed `mite-ecology` entry point.
- Proposal validation: `python scripts/check_proposal_readiness.py`.

## Data flow

1. Source artifacts are ingested into local evidence storage.
2. Provenance and content hashes are recorded.
3. Bundles can be sealed and verified.
4. Review modes distinguish automatic merge, review-only, quarantine, and refusal paths in the underlying workflow.
5. Fieldgrade UI/API exposes governance and readiness surfaces.
6. Proposal demo assets model sources, annotations, audit events, and export manifests as synthetic JSON.

## Local-first boundary

The proposal pack does not add network calls, credentials, external services, or hosted dependencies. The synthetic demo data can be reviewed offline. The existing codebase supports optional local or OpenAI-compatible LLM runtime ownership, but proposal documents treat live LLM output as exogenous unless cached and reviewed.

## Evidence model used in the proposal demo

Each demo object carries:

- object ID,
- title,
- source type,
- provenance note,
- ingestion timestamp,
- claim status,
- admissibility tier,
- review state,
- evidence status,
- review status,
- risk flags,
- human-readable explanation, and
- export hash in the generated manifest.

## Current technical limitation

This proposal pack is documentation, synthetic data, validation tooling, and controlled pilot-data protocol documentation layered on top of the existing repo. It does not turn Fieldgrade into a production-certified platform. Partner-specific data schemas, access controls, actual screenshot asset capture, packaging polish, and user acceptance testing remain next-step work.
