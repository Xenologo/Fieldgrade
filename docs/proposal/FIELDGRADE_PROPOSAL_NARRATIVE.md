# Fieldgrade Proposal Narrative

## Short description

Fieldgrade is a local-first evidence and provenance layer for frontier-AI research workflows. It helps teams convert research artifacts, datasets, benchmark slices, annotations, review decisions, and AI-generated outputs into auditable evidence bundles.

## Problem

Frontier-AI research and autonomous discovery workflows generate large volumes of intermediate artifacts. These artifacts are often difficult to trace, reproduce, verify, and reuse. This limits trust, slows review, weakens dataset governance, and makes funding or regulatory evidence harder to assemble.

## Solution

Fieldgrade provides a structured evidence workflow:

1. ingest source artifacts,
2. attach provenance metadata,
3. classify claim status,
4. record human and AI annotations,
5. preserve audit trails,
6. export evidence bundles, and
7. support proposal, benchmark, and review workflows.

## Innovation

Fieldgrade combines local-first evidence capture, admissibility classification, research-object provenance, and AI-agent review traces into a single proposal-ready substrate. Its differentiator is not an unreviewed AI decision loop; it is a human-reviewable evidence trail that helps teams explain how a research object moved from raw input to reviewed export.

## Target users

- AI research teams preparing benchmark or evaluation datasets.
- University consortia and RTOs coordinating cross-partner evidence.
- SMEs preparing Innovate UK or RFP submissions.
- Advanced-materials teams needing batch, QA, and review provenance.
- Autonomous research platform developers that need controlled evidence review.
- Organisations producing FAIR benchmark datasets.

## Technical approach

The existing repo is a Python monorepo with three main runtime areas: `termite_fieldpack/` for content-addressed evidence ingestion and bundle sealing, `mite_ecology/` for review and deterministic analysis flows, and `fieldgrade_ui/` for the governance UI/API shell. The proposal demonstrator adds synthetic evidence objects under `data/demo/` and validation scripts under `scripts/` without changing the core runtime architecture.

## Near-term demonstrator

The proposal-ready demonstrator shows a synthetic frontier-AI benchmark dataset moving through a Fieldgrade-style pipeline:

1. raw object registration,
2. metadata and provenance capture,
3. annotation,
4. claim classification,
5. review decision,
6. export manifest generation, and
7. proposal evidence pack output.

## Deliverables for a funded sprint

- Domain-specific benchmark governance pack.
- Partner-ready demo dataset and walkthrough.
- Evidence schema refinements for benchmark slices and AI-agent traces.
- Export templates for proposal evidence bundles.
- Human-review controls for admissibility and claim status.
- Validation scripts and lightweight readiness checks.
- Partner pilot report and evidence-pack example.

## Risks and ethics

Primary risks include overclaiming, treating synthetic examples as real data, AI hallucination, privacy leakage, benchmark contamination, unclear licensing, and insufficient human review. The risk and ethics register defines mitigations: synthetic notices, admissibility tiers, review states, placeholder checks, no hard-coded secrets, local-first operation, and explicit human-review boundaries.

## Commercialisation path

Near-term commercialisation should focus on founder-led setup, partner pilots, funded demonstrators, and paid proposal-support packs. Fieldgrade can then move toward domain packs for benchmark governance, GovAI records, FoodQA proof packs, and advanced-materials provenance once real partner data and validation are available.

## Fit to Frontier AI Benchmarking Datasets

Fieldgrade fits as a FAIR benchmark governance layer. It can help define how benchmark objects, source provenance, annotations, review decisions, admissibility tiers, and export manifests are recorded and checked before publication or partner handoff.

## Fit to Frontier AI Discovery

Fieldgrade fits as an evidence and audit layer for AI-assisted discovery workflows. It can record research-agent outputs, source references, human review decisions, risk flags, and exportable evidence bundles so discovery claims remain inspectable and controlled.

## Future extension route

Advanced-materials and HXMM-adjacent use cases should be presented as future controlled extensions. The current proposal pack includes only synthetic examples and should not be represented as real scientific validation.
