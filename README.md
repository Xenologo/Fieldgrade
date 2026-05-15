# Fieldgrade

[![CI](https://github.com/Xenologo/Fieldgrade/actions/workflows/ci.yml/badge.svg)](https://github.com/Xenologo/Fieldgrade/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/Xenologo/Fieldgrade?display_name=tag)](https://github.com/Xenologo/Fieldgrade/releases)
[![License](https://img.shields.io/github/license/Xenologo/Fieldgrade)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

**Turn project chaos into funder-ready evidence.** Fieldgrade is a local-first evidence infrastructure workspace for founders, researchers, AI teams, and technical consultants who need to prove what happened, when it happened, who touched it, what files or models were involved, and why the resulting claim is credible.

> **Capture evidence. Witness provenance. Review claims. Export defensible dossiers.**

## Fieldgrade public doctrine

> **Show the proof layer. Occlude the complexity layer.**

Fieldgrade should publicly appear as a calm, practical evidence workbench. Buyers should first see proposal readiness, audit readiness, research traceability, AI governance support, technical due diligence, and local control. Internal kernels, graph analysis, and advanced architecture stay available, but they belong in advanced documentation rather than the first-touch product surface.

## Fieldgrade Phase 2 — Proposal-readiness and evidence-pack commercialisation

> Convert Fieldgrade from an alpha-grade evidence-governance repo into a founder-led evidence-pack product with reproducible installation, a working local demo, a proposal-ready document set, and a service-led route to paid proof-pack delivery.

This phase is about making one person able to install Fieldgrade, understand the value, load a sample workflow, export a structured evidence pack, and request a proposal-readiness sprint.

## Public product family

Fieldgrade is structured as a family of evidence-pack products:

- **Fieldgrade Proposal** — convert scattered project artefacts into claim-linked proposal evidence packs
- **Fieldgrade AI Governance** — prepare structured evidence for AI governance, audit, and compliance review
- **Fieldgrade Lab** — package experimental records, provenance, and reproducibility evidence without replacing an ELN
- **Fieldgrade Diligence Room** — assemble investor, partner, and technical due-diligence dossiers
- **Fieldgrade Core** — the evidence and provenance engine beneath the product family
- **Fieldgrade Sector Packs** — domain packs such as FoodQA or advanced-materials evidence workflows when a buyer needs a vertical template

## Public-facing materials in this repository

- Landing page: [`/site/landing.html`](site/landing.html)
- Product pages: [`/site/products/`](site/products/)
- Demo page: [`/site/demo/index.html`](site/demo/index.html)
- Public docs page: [`/site/docs/index.html`](site/docs/index.html)
- Security and responsible AI-use page: [`/site/security/index.html`](site/security/index.html)
- Pilot setup page: [`/site/setup/index.html`](site/setup/index.html)
- Contact and pilot request page: [`/site/contact/index.html`](site/contact/index.html)
- Pricing and setup page: [`/site/pricing/index.html`](site/pricing/index.html)
- Sample deliverables: [`/exports`](exports)
- Proposal pack: [`/docs/proposal`](docs/proposal)
- Release packet: [`/releases/v0.9.0-alpha`](releases/v0.9.0-alpha)

## Release-hardening documents

- [`LICENSE`](LICENSE)
- [`SECURITY.md`](SECURITY.md)
- [`INSTALL.md`](INSTALL.md)
- [`CHANGELOG.md`](CHANGELOG.md)
- [`DATA_HANDLING.md`](DATA_HANDLING.md)
- [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)
- [`RELEASE_NOTES_v0.9.0-alpha.md`](RELEASE_NOTES_v0.9.0-alpha.md)
- [`docs/FIELDGRADE_PHASE2_PILOT_RELEASE.md`](docs/FIELDGRADE_PHASE2_PILOT_RELEASE.md)

## What buyers should see first

Fieldgrade publicly emphasizes:

- proposal readiness
- audit readiness
- claim-to-evidence traceability
- exportable evidence dossiers
- AI accountability
- local-first governance

Fieldgrade publicly avoids over-claiming:

- it is **not** a generic notes app
- it is **not** a full enterprise GRC platform
- it is **not** just a document manager
- it is **not** merely blockchain provenance
- it does **not** ask buyers to trust AI automatically
- it does **not** claim legally binding or regulator-approved decisions by default

## Initial commercial ladder

Fieldgrade should lead with a service-led evidence-pack offer, then add subscription tiers later:

- **Free** — local capture, one project, basic export
- **Solo** — suggested range £19–£39/month for founders or independent inventors
- **Team** — suggested range £99–£199/month for small R&D teams
- **Proposal Readiness Sprint** — suggested range £750–£2,500 for founder-led setup and dossier assembly
- **Diligence Room Build** — suggested range £2,500–£10,000 for investor, funder, or compliance evidence-room delivery

## Public trust notes

- Fieldgrade separates capture, analysis, review, and approval.
- Evidence may be ingested automatically, but authority remains explicit.
- Sensitive evidence should not need to leave your machine just to become organised.
- AI outputs are not decisions until reviewed.
- Fieldgrade supports evidence governance and audit preparation; it does not itself certify compliance or replace qualified auditors, QA managers, regulators, or responsible persons.
- Fieldgrade does not provide legal advice, and AI-assisted outputs require human review before operational or compliance decisions.

## Pilot setup and contact path

- Founder-led setup page: [`site/setup/index.html`](site/setup/index.html)
- Contact and pilot request page: [`site/contact/index.html`](site/contact/index.html)
- Structured intake form: [GitHub Issue template](https://github.com/Xenologo/Fieldgrade/issues/new?template=fieldgrade_pilot_request.yml)
- Starting commercial package: **Fieldgrade Proposal Readiness Sprint — £750–£2,500 suggested range**
- Suggested scope: local install, project evidence ledger, claim-to-evidence matrix, risk and assumption register, data-management mini-plan, export-ready evidence pack, and guided review walkthrough

## Release install mode vs development mode

### Pilot release install mode

Use pinned artifacts when you are evaluating or deploying the alpha:

- `uv lock`
- `uv.lock`
- `requirements.lock`
- `releases/v0.9.0-alpha/`

Recommended commands:

**Linux / WSL**

```bash
python3 -m pip install -U uv
uv sync --frozen
```

**Windows PowerShell**

```powershell
python -m pip install -U uv
uv sync --frozen
```

### Development mode

Use the bootstrap scripts when you want the editable workspace plus dev tools:

- `bash scripts/bootstrap_dev.sh`
- `.\scripts\bootstrap_dev.ps1`

## Repository architecture and advanced internals

This monorepo still carries the deeper substrate behind the public product surface:

- `termite_fieldpack/` is the evidence and provenance kernel
- `mite_ecology/` is the review and analysis kernel
- `fieldgrade_ui/` is the governance workspace and application shell

If you want the implementation depth, use the repository docs under `/docs`, especially architecture and deployment materials. The public site should not require buyers to understand those internals before they see value.

## Why this repository is technically credible

This monorepo already implements the audit substrate behind the public positioning:

- file ingestion into **content-addressed storage**
- **SQLite + FTS5** search
- **hash-chained provenance** events
- deterministic signed bundles
- replay verification
- local UI
- local/OpenAI-compatible LLM runtime ownership
- strict deterministic mode

# Technical overview

This monorepo provides:

## Fieldgrade UI: API quick reference

**Registry catalogs (current naming)**

- The versioned JSON Schemas live under `schemas/`:
   - `registry_components_v1.json`, `registry_variants_v1.json`, `registry_remotes_v1.json`
- The UI/API refers to these as **registries** (not `component_catalog_v1`).
- HTTP endpoints (return the registry payload + a deterministic `canonical_sha256`):
   - `GET /api/registry/components`
   - `GET /api/registry/variants`
   - `GET /api/registry/remotes`

**Knowledge graph query surface (current)**

- Today, the supported HTTP query surface is the lightweight `/api/graph/*` endpoints:
   - `GET /api/graph/nodes?filter=<substring>&limit=<n>`
   - `GET /api/graph/neighborhood?node_id=<id>&limit_edges=<n>`
- There is intentionally no general-purpose `/api/kg/*` surface yet.

**Governance autonomy advisory surface**

- GovAI records now expose a deterministic readiness and action-planning layer for operator triage:
    - `GET /api/governance/systems/{record_id}/advisory`
    - `GET /api/governance/dashboard`
- The advisory surface summarizes readiness score, review urgency, export readiness, and prioritized next actions without auto-approving decisions.
- The dashboard now also separates evidence state, review decision state, runtime handoff readiness, and export state into explicit architecture views.

**Architecture and contract surface**

- `GET /api/architecture/overview` returns the current layer ownership model, control-plane/data-plane split, status vocabulary, storage boundary, and readiness contract.
- `GET /api/jobs/{job_id}/contracts` returns the explicit handoff contracts emitted by the termite→mite→Fieldgrade pipeline:
   - evidence packet
   - verification result
   - review decision
   - export package
   - runtime hardening report
   - review-bound CFX bridge and CAO candidate artifacts
- Supporting schemas live under `schemas/`:
   - `fieldgrade_evidence_packet_v1.json`
   - `fieldgrade_runtime_hardening_report_v1.json`
   - `cfx_fieldgrade_bridge_v1.json`
   - `cfx_cao_candidate_v1.json`

## Canonical dev setup (recommended)

Use the bootstrap scripts to get to a known-good environment (runtime + dev deps + editable installs).

**Linux / WSL (bash):**

```bash
bash scripts/bootstrap_dev.sh
make test
```

**Windows (PowerShell):**

```powershell
.\scripts\bootstrap_dev.ps1
python -m pytest -q
```

After bootstrapping, you can run the CLIs (`termite`, `mite-ecology`, `fieldgrade-ui`) or follow the fast-start flows below.

### Warnings policy

Pytest is configured to treat `DeprecationWarning` and `PendingDeprecationWarning` as errors (CI gate).
If a new dependency or change introduces these warnings, fix or isolate it before merging.

## 1) `termite_fieldpack/` (Termux/field/offline)
A fieldable toolchain that can:

- **Ingest** files into a **CAS** (content-addressed blobs) + **SQLite** + **FTS5** (when available)
- Emit **hash-chained provenance** events (append-only)
- Store KG delta ops (`kg_delta.jsonl`) describing observed nodes/edges
