# Fieldgrade Proposal Narrative

## Short description

Fieldgrade is a local-first evidence and provenance workbench for proposal readiness, audit readiness, research traceability, AI governance support, and technical due diligence. It helps teams convert scattered project artefacts into defensible evidence packs.

## Problem

Small R&D, AI, grant-funded, and regulated innovation teams often have real work but weak evidence structure. Their notes, screenshots, datasets, code references, decisions, and AI-assisted outputs are spread across folders and tools. That makes funding bids, investor diligence, reproducibility review, and audit preparation harder than they need to be.

## Solution

Fieldgrade provides a structured evidence workflow:

1. ingest source artefacts,
2. attach provenance metadata,
3. record claim status and admissibility,
4. preserve human and AI-use annotations,
5. maintain review and audit trails,
6. assemble project registers, and
7. export a reviewable evidence dossier.

## Innovation

Fieldgrade combines local-first evidence capture, claim-to-evidence linking, admissibility classification, and human-reviewable audit trails into a single proposal-ready substrate. Its differentiator is not unreviewed automation; it is a provenance-preserving workflow that helps teams explain how messy project material became a reviewed export.

## Target users

- Founders and small teams preparing Innovate UK, UKRI, accelerator, or investor submissions.
- R&amp;D consultants and grant writers packaging client evidence into coherent appendices.
- AI teams that need structured evidence for governance, audit, or compliance review.
- Research and prototype teams that need provenance and reproducibility support without replacing existing tools.
- University spinouts, SMEs, and partner consortia assembling defensible technical due-diligence material.

## Technical approach

The existing repo is a Python monorepo with three main runtime areas: `termite_fieldpack/` for content-addressed evidence ingestion and bundle sealing, `mite_ecology/` for review and deterministic analysis flows, and `fieldgrade_ui/` for the governance UI/API shell. The proposal demonstrator adds synthetic evidence objects under `data/demo/` and validation scripts under `scripts/` without changing the core runtime architecture.

## Near-term demonstrator

The proposal-ready demonstrator shows a synthetic evidence-pack workflow moving through a Fieldgrade-style pipeline:

1. raw object registration,
2. provenance and metadata capture,
3. annotation,
4. claim classification,
5. reviewer decision,
6. register assembly, and
7. export manifest plus proposal pack output.

## Buyer-visible outputs

The first commercial workflow should produce:

- project evidence ledger,
- claim-to-evidence matrix,
- milestone register,
- risk and assumption register,
- data-management mini-plan,
- exportable dossier bundle, and
- missing-evidence checklist.

## Deliverables for a funded sprint

- Domain-specific proposal or diligence evidence pack.
- Partner-ready synthetic or public-safe demo dataset and walkthrough.
- Evidence schema refinements for claims, annotations, and reviewer traces.
- Export templates for proposal, audit, and diligence bundles.
- Human-review controls for admissibility and claim status.
- Validation scripts and lightweight readiness checks.
- Pilot report and evidence-pack example.

## Risks and ethics

Primary risks include overclaiming, treating synthetic examples as real evidence, AI hallucination, privacy leakage, unclear licensing, weak review discipline, and unsupported compliance claims. The risk and ethics register defines mitigations: synthetic notices, admissibility tiers, review states, placeholder checks, no hard-coded secrets, local-first operation, and explicit human-review boundaries.

## Commercialisation path

Near-term commercialisation should focus on a service-led proposal-readiness sprint, founder-led setup, partner pilots, and paid evidence-pack assembly. Fieldgrade can then expand into AI governance packs, research witness packs, sector packs, and broader diligence-room workflows once real partner data and validation are available.

## Fit to Frontier AI Benchmarking Datasets

Fieldgrade fits as a FAIR benchmark and dataset-governance substrate. It can help define how benchmark objects, source provenance, annotations, review decisions, admissibility tiers, and export manifests are recorded and checked before publication or partner handoff.

## Fit to Frontier AI Discovery

Fieldgrade fits as an evidence and audit layer for AI-assisted discovery workflows. It can record research-agent outputs, source references, human review decisions, risk flags, and exportable evidence bundles so discovery claims remain inspectable and controlled.

## Future extension route

AI governance, research-lab traceability, and advanced-materials use cases should be presented as controlled extensions. The current proposal pack includes only synthetic examples and should not be represented as real scientific validation or legal compliance assurance.
