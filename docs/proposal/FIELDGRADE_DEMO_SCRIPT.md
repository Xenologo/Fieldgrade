# Fieldgrade Proposal Demo Script

## Demo objective

Show that Fieldgrade can organise synthetic frontier-AI and research-governance artifacts into a human-reviewable evidence bundle with provenance, admissibility, annotations, audit decisions, and an export manifest.

## Preparation

From the repository root:

```bash
python scripts/generate_demo_manifest.py
python scripts/check_proposal_readiness.py
```

Optional runtime demonstration:

```bash
./run_demo.sh
```

For the local UI/API, install the workspace and run:

```bash
python -m fieldgrade_ui init
python -m fieldgrade_ui serve
```

## Walkthrough

### 1. Open the synthetic source objects

Open `data/demo/fieldgrade_demo_sources.json`. Explain that every record is synthetic and includes object ID, source type, provenance note, claim status, admissibility tier, review state, and risk flags.

### 2. Show annotations

Open `data/demo/fieldgrade_demo_annotations.json`. Explain that Fieldgrade separates source records from review annotations so AI-assisted or speculative claims can remain controlled until reviewed.

### 3. Show audit trail

Open `data/demo/fieldgrade_demo_audit_trail.json`. Highlight event ID, actor, timestamp, decision, review state, and admissibility tier.

### 4. Generate export manifest

Run `python scripts/generate_demo_manifest.py`. Open `data/demo/fieldgrade_demo_export_manifest.json` and show object-level export hashes and file checksums.

### 5. Run readiness validation

Run `python scripts/check_proposal_readiness.py`. Use the PASS output as the proposal-readiness check for required files, JSON parsing, object fields, placeholder scanning, and README local setup coverage.

### 6. Describe runtime path honestly

Explain that the existing repo also includes Termite, mite_ecology, and Fieldgrade UI/API runtime paths. The synthetic proposal demo is designed for funder review and does not claim that synthetic records are real benchmark, lab, or operational evidence.

## Screenshot instructions

Capture screenshots of:

1. repository root with `docs/proposal/`, `data/demo/`, and `scripts/` visible;
2. the generated export manifest showing object hashes;
3. terminal output from `python scripts/check_proposal_readiness.py`;
4. optional local UI at `http://127.0.0.1:8787` after running the UI serve command.

Store screenshots under `docs/screenshots/` if they are added to a proposal submission.
