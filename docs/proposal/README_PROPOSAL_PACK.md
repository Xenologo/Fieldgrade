# Fieldgrade Proposal Pack

This folder contains the funder-facing Fieldgrade proposal-readiness pack. It frames Fieldgrade as a proposal-ready demonstrator for evidence-governed frontier-AI research workflows, while keeping claims grounded in the repository's existing local-first evidence, provenance, review, and export capabilities.

## Contents

- `FIELDGRADE_ONE_PAGE_SUMMARY.md` — concise funder summary.
- `FIELDGRADE_PROPOSAL_NARRATIVE.md` — problem, solution, innovation, users, delivery plan, and funding fit.
- `FIELDGRADE_TECHNICAL_ARCHITECTURE.md` — repository-grounded runtime and architecture overview.
- `FIELDGRADE_DEMO_SCRIPT.md` — walkthrough for the synthetic proposal demo.
- `FIELDGRADE_SUBMISSION_CHECKLIST.md` — submission-facing checklist for reviewers and partners.
- `FIELDGRADE_REVIEWER_WALKTHROUGH.md` — under-15-minute inspection path for a reviewer.
- `FIELDGRADE_SCREENSHOT_CAPTURE_PLAN.md` — concrete screenshot list for submission packets.
- `FIELDGRADE_FUNDING_FIT_MATRIX.md` — priority funding routes and evidence needed.
- `FIELDGRADE_RISK_ETHICS_REGISTER.md` — risks, controls, and mitigations.
- `FIELDGRADE_DATA_GOVERNANCE.md` — provenance, privacy, licensing, and review practices.
- `FIELDGRADE_12_WEEK_ROADMAP.md` — scoped delivery plan for a proposal sprint.
- `FIELDGRADE_PARTNER_BRIEF.md` — collaboration brief for universities, RTOs, SMEs, and demonstrator partners.
- `FIELDGRADE_READINESS_AUDIT.md` — current audit of repo state, commands, gaps, and readiness score.

## Demo and validation assets

Synthetic demo data lives under `data/demo/`. The output-pack landing file is `outputs/proposal_pack/README.md`.

## Reviewer pack sequence

For a fast partner or funder review, start with:

1. `FIELDGRADE_SUBMISSION_CHECKLIST.md`
2. `FIELDGRADE_REVIEWER_WALKTHROUGH.md`
3. `FIELDGRADE_SCREENSHOT_CAPTURE_PLAN.md`
4. `FIELDGRADE_DEMO_SCRIPT.md`
5. `FIELDGRADE_READINESS_AUDIT.md`

Run the proposal readiness check from the repository root:

```bash
python scripts/check_proposal_readiness.py
```

Refresh the demo export manifest after editing demo JSON:

```bash
python scripts/generate_demo_manifest.py
```

Re-run the compatibility validator if a reviewer wants the same PASS output through the wrapper script:

```bash
python scripts/validate_fieldgrade_pack.py
```
