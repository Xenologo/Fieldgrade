# Migration plan B — Multi-tenant core (Postgres + RBAC + API keys)

## Current status (as of 2025-12-31)

Phase B is **not implemented** yet.

- There are no Postgres-backed migrations/models for organisations, projects, memberships, datasets, or runs.
- There is no RBAC guard layer, API-key system, or audit logging.
- State remains local (SQLite job queue + runtime/artifact directories), so tenant isolation is not available.

## Scope and non-goals

In scope:
- Introduce a multi-tenant data model suitable for a hosted web platform.
- Enforce tenant isolation end-to-end at the API and data access layers.

Out of scope (for Phase B):
- Billing/Stripe/entitlements (Phase D)
- Full platformisation of pipelines/object storage (Phase C)

## Goals

- Postgres-backed persistence for tenant-scoped entities.
- Strong tenant isolation (cross-org access prevention).
- RBAC and API keys for programmatic access.
- Audit logging for security-relevant actions.

## Planned work items (placeholders)

- Data model + migrations
  - [ ] Organisations
  - [ ] Projects
  - [ ] Memberships / roles
  - [ ] Datasets
  - [ ] Runs
- AuthN/AuthZ
  - [ ] RBAC policy model (roles, permissions)
  - [ ] API-key issuance + rotation
  - [ ] Request-scoped tenant context
- Guardrails + observability
  - [ ] Audit log schema + writer
  - [ ] Admin-only endpoints (if needed)
- Kill-tests / acceptance gates
  - [ ] Tenant isolation kill-test (cross-org access must fail)
  - [ ] Deterministic/immutability invariants remain enforced

## Exit criteria

- All tenant-scoped requests require an org/project context and are authorization-checked.
- Postgres migrations run cleanly; CI includes migration/app boot checks.
- Tenant isolation kill-test is enabled and passing.

## Risks / notes

- Preserve Phase A invariants: bundle bytes remain immutable evidence artifacts; DSSE/CDX semantics unchanged.
- Ensure queries are deterministic where determinism matters (explicit `ORDER BY`).
