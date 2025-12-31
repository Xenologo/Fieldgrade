# Migration plan A — “Make it shippable” (preserve determinism + DSSE/CDX semantics)

## Current status (as of 2025-12-31)

The repo has progressed through the Phase A scope below. Multi-tenant SaaS features described in later phases (B–D) are not implemented yet.

Evidence of Phase A work completed:

- **A1 — Repo hygiene and reproducible setup.** Bootstrap + CI were added so `make install` and `make test` can run from a clean environment. CI runs Linux and Windows matrix builds and verifies tests pass.
- **A2 — Containerization.** `compose.yaml` defines a two-service deployment (`web` FastAPI UI + `worker` job worker) with named volumes for termite and mite runtime/artifact directories. The Dockerfile builds a single Python image containing `termite_fieldpack`, `mite_ecology`, and `fieldgrade_ui`, exposing the API on port 8787.
- **A3/A4 — Operational endpoints and CI kill-tests.** CI includes a dedicated Docker validation job (installs docker-compose plugin if needed and runs `docker compose config`). Regression tests assert bundle verification fails for corrupted/tampered DSSE and missing CycloneDX SBOMs, and that replay does not mutate bundle ZIP bytes. The DSSE attestation decoder fails when the signature cannot be base64-decoded.

Gaps / remaining work:

- **Phase B — Multi-tenant core.** No Postgres-backed org/project/membership/dataset/run model, migrations, RBAC, API keys, or audit logging; state is still local SQLite job queue + runtime directories. Tenant isolation is not implemented, so the Phase A4 “tenant isolation kill-test” remains not applicable.
- **Phase C — Pipeline platformisation.** Artifacts remain on local filesystem, verification is still CLI-invoked (no “verify as a service” API), and there is no review queue UI or deterministic server-side “Run” abstraction.
- **Phase D — Billing and entitlements.** No pricing, Stripe integration, usage metering, or subscription provisioning.

This plan is explicitly constrained by:
- **Do not break deterministic behavior** for sealing/verification/replay.
- **Do not change DSSE envelope semantics** or CycloneDX verification expectations.
- **Do not rewrite bundle bytes** after seal; bundles are immutable evidence artifacts.

## Phase A0 — Baseline definition (no behavior change)

1) Declare invariants (docs + tests)
- Bundle immutability: sealed ZIP bytes never change.
- Verification strictness: invalid DSSE → fail; missing/invalid CycloneDX when required → fail.
- Determinism: stable hashes for canonical JSON and repeatable pipeline outputs.

2) Identify current “boundaries”
- `termite_fieldpack` and `mite_ecology` are already separately testable Python packages.
- `fieldgrade_ui` orchestrates them via subprocess calls, plus SQLite job queue.

Deliverables (no code changes required to start):
- Architecture map: `docs/ARCH_MAP.md`
- Deployment topo: `docs/DEPLOYMENT_TOPOLOGY.md`

## Phase A1 — Repo hygiene and reproducible local setup

Goals:
- One canonical setup path for Windows + Linux
- `make install` and `make test` succeed from a clean venv

Work items (minimal / safe)
- Add a single bootstrap script (`scripts/bootstrap_dev.ps1` and/or `.sh`) that:
  - creates `.venv`
  - installs `requirements.txt` and `requirements-dev.txt`
  - installs editable packages: `termite_fieldpack`, `mite_ecology`, `fieldgrade_ui`
- Update README to point to the bootstrap as canonical.

Determinism risk notes
- Dependency drift can affect SBOM content if SBOM reflects installed distributions.
- Pinning or locking dependencies should be done carefully:
  - pin versions for CI determinism
  - document that runtime SBOM reflects the environment at seal time

## Phase A2 — Containerize the *existing* architecture (no platform refactor)

Goals:
- A local prod-like environment with:
  - web UI/API
  - worker
  - persistent volumes

Work items
- Add Dockerfile(s) that build a single Python image containing all 3 packages.
- Add `compose.yaml` that runs:
  - `web`: `python -m fieldgrade_ui serve`
  - `worker`: `python -m fieldgrade_ui worker`
- Mount volumes for runtimes/artifacts:
  - termite runtime + artifacts
  - mite runtime + artifacts
  - UI jobs runtime

Determinism risk notes
- Do not introduce non-deterministic file ordering when building bundles.
- Ensure time-dependent metadata is either:
  - excluded from hash binding, or
  - canonicalized and stable.

## Phase A3 — Operational endpoints + minimal metrics

Goal:
- Add `/healthz` and `/readyz` endpoints to `fieldgrade_ui`.

Notes
- There is already `GET /api/metrics` in the UI.
- `/readyz` should fail when required SQLite DBs are missing/unmigrated (and later, Postgres).

## Phase A4 — CI “kill-tests” (platform acceptance gates)

Add/verify tests in CI that ensure:

1) Tenant isolation kill-test
- Not applicable until Phase B multi-tenancy exists.

2) Bundle immutability kill-test
- Seal a bundle, compute hash of the bundle ZIP bytes, verify it, replay it, re-hash; hashes must match.

3) Strict verification kill-test
- Corrupt `attestation.dsse.json` or signature and assert verify fails.
- Remove `sbom/bom.cdx.json` and assert verify fails when policy requires it.

4) Deterministic run kill-test
- Run `mite-ecology auto-run` twice from the same DB snapshot and assert stable output hashes for artifacts intended to be deterministic.

## Phase A5 — Platform boundary hardening (prep for SaaS)

These are structural changes that make Phase B/C simpler without changing semantics:

- Introduce an internal Python API boundary:
  - Prefer importing `termite_fieldpack` and `mite_ecology` as libraries from `fieldgrade_ui` rather than shelling out, but only after you have deterministic equivalence tests.
- Centralize config:
  - consolidate env var names and document them.
- Introduce a stable artifact registry abstraction:
  - file path today → S3 pointer later
  - always store hashes alongside pointers

## What not to do in Phase A

- Do not introduce distributed queues or multiple DB backends yet.
- Do not move bundles to object storage yet unless you also implement hash validation + byte-for-byte immutability guarantees.
- Do not change DSSE envelope format or CycloneDX BOM semantics.

## Exit criteria for Phase A

- Local setup is reproducible.
- Tests pass from a clean environment.
- Docker compose brings up web + worker.
- A sample pipeline job completes end-to-end.
- Determinism/immutability/strict verification kill-tests are in CI.
