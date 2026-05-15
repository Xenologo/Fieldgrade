# Fieldgrade Proposal Pack

This folder contains the funder-facing Fieldgrade proposal-readiness pack. It frames Fieldgrade as a proposal-ready demonstrator for evidence-governed frontier-AI research workflows, while keeping claims grounded in the repository's existing local-first evidence, provenance, review, and export capabilities.

## Contents

- `FIELDGRADE_ONE_PAGE_SUMMARY.md` — concise funder summary.
- `FIELDGRADE_PROPOSAL_NARRATIVE.md` — problem, solution, innovation, users, delivery plan, and funding fit.
- `FIELDGRADE_TECHNICAL_ARCHITECTURE.md` — repository-grounded runtime and architecture overview.
- `FIELDGRADE_DEMO_SCRIPT.md` — walkthrough for the synthetic proposal demo.
- `FIELDGRADE_FUNDING_FIT_MATRIX.md` — priority funding routes and evidence needed.
- `FIELDGRADE_RISK_ETHICS_REGISTER.md` — risks, controls, and mitigations.
- `FIELDGRADE_DATA_GOVERNANCE.md` — provenance, privacy, licensing, and review practices.
- `FIELDGRADE_12_WEEK_ROADMAP.md` — scoped delivery plan for a proposal sprint.
- `FIELDGRADE_PARTNER_BRIEF.md` — collaboration brief for universities, RTOs, SMEs, and demonstrator partners.
- `FIELDGRADE_READINESS_AUDIT.md` — current audit of repo state, commands, gaps, and readiness score.

## Demo and validation assets

Synthetic demo data lives under `data/demo/`. The output-pack landing file is `outputs/proposal_pack/README.md`.

Run the proposal readiness check from the repository root:

```bash
python scripts/check_proposal_readiness.py
```

Refresh the demo export manifest after editing demo JSON:

```bash
python scripts/generate_demo_manifest.py
```
