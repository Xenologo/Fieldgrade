# Fieldgrade Submission Checklist

## Purpose

Use this checklist when packaging Fieldgrade for a funder, partner, or pilot reviewer. It is designed for a submission-ready proposal demonstrator, not a production-certified deployment.

## Core submission status

- [ ] Confirm the repository snapshot is the intended review version.
- [ ] Confirm `docs/proposal/` contains the proposal narrative, architecture, demo, governance, roadmap, partner brief, readiness audit, and reviewer-pack documents.
- [ ] Confirm `data/demo/` contains only synthetic demo records.
- [ ] Confirm `outputs/proposal_pack/README.md` is present for exported-pack orientation.
- [ ] Confirm no document claims regulatory certification, autonomous approval, or production hardening that the repo does not evidence.

## Reviewer materials to hand over

- [ ] `docs/proposal/README_PROPOSAL_PACK.md`
- [ ] `docs/proposal/FIELDGRADE_REVIEWER_WALKTHROUGH.md`
- [ ] `docs/proposal/FIELDGRADE_SCREENSHOT_CAPTURE_PLAN.md`
- [ ] `docs/proposal/FIELDGRADE_DEMO_SCRIPT.md`
- [ ] `docs/proposal/FIELDGRADE_READINESS_AUDIT.md`
- [ ] `data/demo/fieldgrade_demo_export_manifest.json`

## Commands to run from the repository root

```bash
python scripts/generate_demo_manifest.py
python scripts/check_proposal_readiness.py
python scripts/validate_fieldgrade_pack.py
```

If dependencies are already available, an additional confidence check is:

```bash
python -m pytest -q
```

## Expected PASS signals

- `python scripts/generate_demo_manifest.py` writes `data/demo/fieldgrade_demo_export_manifest.json` with synthetic object hashes and file checksums.
- `python scripts/check_proposal_readiness.py` reports `Fieldgrade proposal readiness status: PASS` and `Readiness score: 100/100`.
- `python scripts/validate_fieldgrade_pack.py` exits cleanly after re-running the readiness check.
- `python -m pytest -q` is optional for this reviewer pack and should only be presented if the environment already has test dependencies.

## Synthetic-data boundary

- [ ] State explicitly that `data/demo/` is synthetic proposal-demo content.
- [ ] State explicitly that the demo does not prove real benchmark, lab, supplier, or operational evidence quality.
- [ ] State explicitly that Fieldgrade is submission-ready as a proposal demonstrator and reviewer-verifiable pack, not production-certified.
- [ ] State explicitly that partner-approved non-sensitive records are a later pilot step.

## Reviewer claims discipline

### What the demo proves

- [ ] Fieldgrade can present evidence objects, annotations, audit events, and export metadata in a human-reviewable structure.
- [ ] The repo contains a reproducible proposal-pack integrity check.
- [ ] The product framing, architecture, and governance story align with the shipped repository materials.

### What the demo does not prove

- [ ] Production security assurance
- [ ] Regulatory certification
- [ ] Real partner-data validation
- [ ] Fully autonomous scientific or compliance decisions

## Next funded sprint handoff

- [ ] Identify the intended submission mode or pilot lane.
- [ ] Identify which partner-approved records would replace or extend the synthetic demo.
- [ ] Identify screenshot assets to capture using `FIELDGRADE_SCREENSHOT_CAPTURE_PLAN.md`.
- [ ] Identify runtime smoke, packaging, and user-testing work that remains outside this submission reviewer pack.
