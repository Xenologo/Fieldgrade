# Fieldgrade Reviewer Walkthrough

## Purpose

This walkthrough lets a funder, partner, or technical reviewer inspect Fieldgrade in under 15 minutes. It is a reviewer-verifiable submission pack for a proposal demonstrator, not a claim of production certification.

## What this demo proves

- Fieldgrade can organise evidence-like records, annotations, audit events, and export metadata into a human-reviewable structure.
- The repository exposes a clear local-first architecture across the documented runtime directories `termite_fieldpack/`, `mite_ecology/`, and `fieldgrade_ui/`.
- The proposal pack can be checked with simple local Python commands.

## What this demo does not prove

- Real partner, benchmark, laboratory, or operational evidence quality
- Production hardening or security certification
- Regulator-approved workflows
- Autonomous approval without human review

## Synthetic-data boundary

All files under `data/demo/` are synthetic proposal-demo records. They exist to show structure, provenance handling, review boundaries, and export packaging. They must not be presented as real customer, supplier, benchmark, or scientific data.

## 15-minute review path

### 1. Understand the repository surface (2 minutes)

Inspect:

- `README.md`
- `docs/proposal/README_PROPOSAL_PACK.md`
- `docs/proposal/FIELDGRADE_READINESS_AUDIT.md`

Look for:

- local-first ProofOps framing
- the three main runtime areas
- the distinction between submission readiness and production maturity

### 2. Inspect the synthetic evidence bundle (3 minutes)

Open:

- `data/demo/fieldgrade_demo_sources.json`
- `data/demo/fieldgrade_demo_annotations.json`
- `data/demo/fieldgrade_demo_audit_trail.json`
- `data/demo/fieldgrade_demo_export_manifest.json`

Look for:

- object IDs and titles
- provenance notes
- admissibility tiers
- review states
- export hashes and file checksums

### 3. Run the reviewer commands (4 minutes)

From the repository root:

```bash
python scripts/generate_demo_manifest.py
python scripts/check_proposal_readiness.py
python scripts/validate_fieldgrade_pack.py
```

Expected PASS output:

- manifest generation reports that `data/demo/fieldgrade_demo_export_manifest.json` was written
- readiness check reports `Fieldgrade proposal readiness status: PASS`
- readiness check reports `Readiness score: 100/100`
- wrapper validation exits cleanly with the same PASS result

If dependencies are already available, an optional extra check is:

```bash
python -m pytest -q
```

Do not treat skipped pytest execution as a proposal-pack failure when the environment has not been bootstrapped.

### 4. Inspect the proposal narrative layer (3 minutes)

Open:

- `docs/proposal/FIELDGRADE_ONE_PAGE_SUMMARY.md`
- `docs/proposal/FIELDGRADE_PROPOSAL_NARRATIVE.md`
- `docs/proposal/FIELDGRADE_TECHNICAL_ARCHITECTURE.md`
- `docs/proposal/FIELDGRADE_DATA_GOVERNANCE.md`

Confirm:

- claims remain cautious
- governance language is evidence-governed and human-reviewable
- the architecture described matches the repository

### 5. Inspect the demo limitations and next step (3 minutes)

Open:

- `docs/proposal/FIELDGRADE_RISK_ETHICS_REGISTER.md`
- `docs/proposal/FIELDGRADE_12_WEEK_ROADMAP.md`
- `docs/proposal/FIELDGRADE_PARTNER_BRIEF.md`

Confirm:

- the pack does not overclaim production readiness
- the next funded sprint includes partner-approved evidence replacement, runtime hardening, and reviewer capture work
- the expected partner contribution is explicit

## Recommended files to inspect first

1. `docs/proposal/FIELDGRADE_SUBMISSION_CHECKLIST.md`
2. `docs/proposal/FIELDGRADE_REVIEWER_WALKTHROUGH.md`
3. `docs/proposal/FIELDGRADE_DEMO_SCRIPT.md`
4. `docs/proposal/FIELDGRADE_READINESS_AUDIT.md`
5. `data/demo/fieldgrade_demo_export_manifest.json`

## Next funded sprint deliverables

The next funded sprint should replace or extend the synthetic demo with partner-approved non-sensitive records, add fresh smoke-test evidence, tighten submission-mode routing, and close release-publication tasks. Those follow-on items are outside the claims made by this reviewer pack.
