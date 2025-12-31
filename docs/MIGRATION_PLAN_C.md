# Migration plan C — Pipeline platformisation (object storage + verify as a service)

## Current status (as of 2025-12-31)

Phase C is **not implemented** yet.

- Bundles and artifacts are stored on the local filesystem.
- Verification is invoked via CLI; there is no server-side “verify as a service” API.
- There is no review queue UI and no deterministic server-side “Run” abstraction for analytics.

## Scope and non-goals

In scope:
- Move artifact/bundle storage from local disk to an object store (S3-compatible).
- Expose verification via web/API services.
- Introduce a durable “Run” concept for repeatable analytics.

Out of scope (for Phase C):
- Billing/Stripe/entitlements (Phase D)

## Goals

- Object storage for bundles/artifacts with hash-addressed immutability guarantees.
- Server-side verification workflows (API/service) with strict DSSE/CycloneDX checks.
- A stable “Run” abstraction that supports deterministic replay and auditing.

## Planned work items (placeholders)

- Storage
  - [ ] Bundle store interface (local dev, S3 prod)
  - [ ] Artifact store interface (local dev, S3 prod)
  - [ ] Store raw bytes + content hash; never mutate bytes after upload
- Verification as a service
  - [ ] API endpoint(s) for submit/verify
  - [ ] Background job integration (queue + worker)
  - [ ] Verification result persistence (status, logs, hashes)
- Review / workflow
  - [ ] Review queue model
  - [ ] Minimal UI surface (placeholder)
- Determinism guardrails
  - [ ] Ensure download→hash validation on every read
  - [ ] Ensure canonical JSON rules are enforced where hashed/signed

## Exit criteria

- Bundles/artifacts can be stored and retrieved via object storage without changing bytes.
- Verification can be run as a service and yields the same results as CLI.
- Deterministic replay remains valid; immutability and strict verification tests remain passing.

## Risks / notes

- Treat object storage as untrusted: validate hashes and enforce immutability semantics at read/write boundaries.
- Keep Phase A invariants intact: DSSE envelope and CycloneDX expectations must not change.
