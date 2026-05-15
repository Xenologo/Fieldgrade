# AGENTS.md — Fieldgrade Proposal-Readiness Instructions

## Project Identity

Fieldgrade is a local-first evidence, provenance, and proposal-readiness substrate within the wider CFX Stack.

Its function is to witness, seal, classify, export, and review evidence-bearing research objects.

Fieldgrade is not a generic notes app.
Fieldgrade is not merely a document viewer.
Fieldgrade is not the whole CFX Stack.
Fieldgrade is the evidence/provenance layer that makes research artifacts auditable, admissible, and proposal-ready.

## Current Sprint Objective

Finalise Fieldgrade for proposal readiness.

The repository must become suitable for:
- Innovate UK Frontier AI Benchmarking Datasets
- Innovate UK Frontier AI Discovery
- Evidence-governance, provenance, research-infrastructure, and AI-audit proposals
- Later HXMM / advanced-materials demonstrator proposals

## Product Thesis

Fieldgrade enables frontier-AI and research teams to create trustworthy datasets and benchmark artifacts by preserving:
- source provenance
- ingestion metadata
- human/AI annotations
- audit decisions
- claim status
- admissibility tier
- exportable evidence bundles
- review trails
- reproducible demo datasets

## Proposal-Ready Definition

The sprint is complete only when the repo contains:

1. A working local demo
2. A demo dataset
3. A clear README
4. A proposal narrative
5. A technical architecture document
6. A risk and ethics register
7. A funding-fit matrix
8. A demo script
9. Screenshots or screenshot instructions
10. A validation script
11. A readiness audit
12. A final changelog

## Required Proposal Pack

Create or update the following files:

- `docs/proposal/FIELDGRADE_READINESS_AUDIT.md`
- `docs/proposal/FIELDGRADE_PROPOSAL_NARRATIVE.md`
- `docs/proposal/FIELDGRADE_TECHNICAL_ARCHITECTURE.md`
- `docs/proposal/FIELDGRADE_DEMO_SCRIPT.md`
- `docs/proposal/FIELDGRADE_FUNDING_FIT_MATRIX.md`
- `docs/proposal/FIELDGRADE_RISK_ETHICS_REGISTER.md`
- `docs/proposal/FIELDGRADE_DATA_GOVERNANCE.md`
- `docs/proposal/FIELDGRADE_12_WEEK_ROADMAP.md`
- `docs/proposal/FIELDGRADE_PARTNER_BRIEF.md`
- `docs/proposal/FIELDGRADE_ONE_PAGE_SUMMARY.md`
- `docs/proposal/README_PROPOSAL_PACK.md`

Create or update these demo assets:

- `data/demo/fieldgrade_demo_sources.json`
- `data/demo/fieldgrade_demo_annotations.json`
- `data/demo/fieldgrade_demo_audit_trail.json`
- `data/demo/fieldgrade_demo_export_manifest.json`
- `outputs/proposal_pack/README.md`

Create or update validation tools:

- `scripts/validate_fieldgrade_pack.py`
- `scripts/generate_demo_manifest.py`
- `scripts/check_proposal_readiness.py`

## Engineering Rules

Before changing code:
1. Inspect the repo structure.
2. Identify the actual runtime entry points.
3. Identify existing build, test, lint, and run commands.
4. Record findings in `docs/proposal/FIELDGRADE_READINESS_AUDIT.md`.
5. Do not invent commands if the repo already defines them.

When changing code:
1. Prefer small, reviewable changes.
2. Preserve existing architecture unless broken.
3. Avoid adding large dependencies without justification.
4. Keep Fieldgrade local-first.
5. Do not hard-code private API keys.
6. Do not add live network calls unless the project already supports them.
7. Make demo data synthetic or clearly public-domain/sample data.
8. Keep proposal artifacts separate from runtime code.

## Evidence and Governance Rules

Every demo artifact should include:
- object ID
- title
- source type
- provenance note
- ingestion timestamp
- evidence status
- review status
- admissibility tier
- export hash or checksum where feasible
- human-readable explanation

Use these admissibility tiers:
- canonical
- controlled_extension
- speculative_projective_extension
- rejected
- audit_only
- unknown

Use these review states:
- raw
- ingested
- annotated
- reviewed
- exported
- superseded

## Funding-Framing Rules

For Frontier AI Benchmarking Datasets:
Frame Fieldgrade as a FAIR benchmark and dataset-governance substrate for evaluating frontier-AI research agents.

For Frontier AI Discovery:
Frame Fieldgrade as the evidence and audit layer for autonomous scientific discovery workflows.

For advanced-materials proposals:
Frame Fieldgrade as the provenance layer for experiment batches, microscopy, sensor traces, laminate recipes, QA data, and end-user review.

## Documentation Style

Use precise, proposal-ready language.

Avoid overclaiming.

Do not present speculative CAO, HXMM, QFIM-Triad, or CFX concepts as proven scientific facts.

Use cautious phrases:
- "evidence-governed"
- "audit-ready"
- "local-first"
- "human-reviewable"
- "provenance-preserving"
- "benchmark-oriented"
- "proposal-ready demonstrator"
- "controlled speculative extension"

Avoid unsupported phrases:
- "AGI"
- "consciousness transfer"
- "quantum proof"
- "metamaterial breakthrough"
- "fully autonomous science"
- "guaranteed trust"

## Verification Rules

Before declaring completion:
1. Run the available tests.
2. Run lint/type checks if available.
3. Run the local demo if possible.
4. Run `scripts/check_proposal_readiness.py`.
5. Confirm all required files exist.
6. Confirm proposal documents cross-reference actual repo behavior.
7. Confirm no fake features are described as implemented.
8. Produce a final summary with:
   - files changed
   - commands run
   - passing checks
   - known gaps
   - next recommended action
