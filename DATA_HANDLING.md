# Data handling guide

Fieldgrade is designed to support local-first evidence governance. Operators remain responsible for how they deploy it and what external services they attach to it.

## What Fieldgrade stores

Fieldgrade may store:

- uploaded evidence files and their content-addressed copies
- runtime metadata and review state
- manifests, provenance logs, and export bundles
- optional AI-call records, prompts, and outputs when those workflows are enabled

## Default storage locations

- `termite_fieldpack/runtime`
- `termite_fieldpack/artifacts`
- `mite_ecology/runtime`
- `mite_ecology/artifacts`
- `fieldgrade_ui/runtime`

In Docker deployments these paths are backed by named volumes.

## What leaves the machine

By default, the repository is positioned for local or customer-controlled use.

- Static pages can be viewed without sending repository data anywhere
- Local CLI and UI workflows can run without a hosted SaaS dependency
- If you configure an external AI endpoint, prompts and related context may leave the machine and will be governed by that endpoint's operator

## Telemetry and logging

- This repository does not advertise mandatory product telemetry
- Operators should assume routine application, HTTP, and process logs may still exist on the host or container runtime
- Avoid placing secrets, customer personal data, or regulated evidence in logs

## Retention and deletion

- Define retention periods before onboarding customer or regulated evidence
- Delete data by removing the relevant runtime/artifact files or Docker volumes
- Confirm that backups, exports, and copied proof packs are deleted separately when required

## Backups

- Back up runtime and artifact stores before upgrades or infrastructure changes
- Encrypt backups and restrict access
- Test restore drills before relying on backups for customer evidence

## AI endpoint usage

- Only connect AI endpoints you are permitted to use for the relevant evidence class
- Redact or minimize sensitive material before external AI submission
- Keep human review mandatory for AI-assisted outputs

## Sharing and redaction

- Share the minimum evidence needed for review
- Redact personal, contractual, health, or security-sensitive information before sending demo packs externally
- Use sample datasets for demos whenever possible instead of customer records

## Compliance caveat

Fieldgrade supports evidence governance and audit preparation. It does not itself certify compliance, provide legal advice, or replace qualified professional review.
