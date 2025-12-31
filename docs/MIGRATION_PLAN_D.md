# Migration plan D — Billing and entitlements (subscriptions + usage metering)

## Current status (as of 2025-12-31)

Phase D is **not implemented** yet.

- There is no pricing/billing code.
- There is no Stripe integration.
- There is no usage metering, subscription provisioning, or entitlement enforcement.

## Scope and non-goals

In scope:
- Subscription lifecycle management.
- Usage metering and plan entitlements.
- Enforcing entitlements at API/workflow boundaries.

Out of scope (for Phase D):
- Major product/UI redesign (keep changes minimal)

## Goals

- A clear plan/entitlement model (free vs paid tiers).
- Automated subscription provisioning and renewal handling.
- Usage metering that is auditable and ties back to tenant context.

## Planned work items (placeholders)

- Pricing + plans
  - [ ] Define plans and entitlements (limits/quotas)
  - [ ] Persist entitlements per org
- Billing integration
  - [ ] Stripe customer + subscription wiring
  - [ ] Webhook handling (idempotent)
  - [ ] Billing portal/customer management (placeholder)
- Usage metering
  - [ ] Define billable events
  - [ ] Record usage with tenant attribution
  - [ ] Aggregation/reporting (placeholder)
- Enforcement
  - [ ] Gate operations by entitlement (API + worker)
  - [ ] Soft/hard limits behavior (placeholder)

## Exit criteria

- Subscriptions can be created/updated/canceled and reflected in entitlements.
- Usage is metered and can be audited per org.
- Entitlements are enforced consistently across API and worker workflows.

## Risks / notes

- Avoid introducing nondeterminism into bundle sealing/verification; billing must not affect evidence artifact bytes.
- Ensure webhook handlers are idempotent and resilient.
