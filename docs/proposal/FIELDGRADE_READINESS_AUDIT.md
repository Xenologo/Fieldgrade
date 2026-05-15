# Fieldgrade Readiness Audit

## Audit date

2026-05-15.

## Current repo state

Fieldgrade is a Python monorepo with existing documentation, deployment guides, schemas, tests, a FastAPI UI/API package, Termite Fieldpack evidence tooling, mite_ecology review and analysis tooling, sample exports, and shell/PowerShell demo scripts.

## Actual runtime stack

- Python 3.10+.
- Root workspace managed by `pyproject.toml` and `uv`.
- `fieldgrade_ui/` uses FastAPI and uvicorn.
- `termite_fieldpack/` provides evidence ingestion, content-addressed storage, provenance, bundle sealing, verification, and replay.
- `mite_ecology/` provides deterministic review/analysis pipeline behavior and review modes.
- Root `Makefile` defines `make test` as the canonical test command.

## Existing entry points inspected

- `README.md` documents bootstrap, test, CLI, UI, Docker Compose, and end-to-end demo paths.
- `site/landing.html`, `site/setup/index.html`, `site/contact/index.html`, `site/pricing/index.html`, and `site/products/*.html` form the static buyer-facing conversion path for FoodQA-first ProofOps packaging.
- `run_demo.sh` runs a local Termite plus mite_ecology demonstration in `.demo_runtime`.
- `run_demo.ps1` provides the Windows demo route.
- `fieldgrade_ui/__main__.py` exposes UI/API commands through `python -m fieldgrade_ui` and the installed console script.
- `scripts/bootstrap_dev.sh` and `scripts/bootstrap_dev.ps1` provide development setup.

## Proposal-readiness assets added

- Proposal pack under `docs/proposal/`.
- Funding-mode routing notes under `docs/proposal/FIELDGRADE_SUBMISSION_MODES.md`.
- Pilot data replacement controls under `docs/proposal/FIELDGRADE_PILOT_DATA_REPLACEMENT_PROTOCOL.md`.
- Synthetic demo evidence records under `data/demo/`.
- Controlled public pilot-sample staging under `data/pilot_samples/`.
- Proposal output landing file under `outputs/proposal_pack/`.
- Validation scripts under `scripts/`.
- Root `AGENTS.md` with durable proposal-readiness instructions.
- A small synthetic JSONL resource used by `run_demo.sh` as an ingestible demo artifact.

## Readiness rubric

| Area | Pass condition | Status | Score |
| --- | --- | --- | --- |
| Runtime | Local demo or documented run path exists | Pass | 2 |
| README | Clear setup path exists | Pass | 2 |
| Demo data | Synthetic evidence set exists | Pass | 3 |
| Governance | Risk register exists | Pass | 3 |
| Proposal | One-page summary exists | Pass | 3 |
| Validation | Readiness script runs | Pass | 3 |
| Funding | Fit matrix exists | Pass | 3 |
| Evidence | Export manifest exists | Pass | 3 |

Scoring scale: 0 = absent, 1 = present but weak, 2 = usable, 3 = proposal-ready.

## Current readiness score

22 out of 24. Fieldgrade is honestly describable as a proposal-ready demonstrator for evidence-governed frontier-AI research workflows.

## Integrity check versus maturity rubric

The `scripts/check_proposal_readiness.py` score and this audit score answer different reviewer questions.

- **100/100 readiness script score** means the required submission pack exists, parses correctly, contains the expected demo-object fields, avoids placeholder text, and includes a recognizable README local setup path.
- **22/24 audit score** means the repository maturity rubric still rates the runtime and README as **usable (2/3)** rather than **fully polished (3/3)**.

These results are therefore not inconsistent. The repository is submission-ready and reviewer-verifiable as a partner-facing proposal and pilot pack, while the underlying runtime is still most accurately described as a proposal-ready demonstrator rather than a fully hardened production deployment.

## Commands identified

- `bash scripts/bootstrap_dev.sh` — development setup.
- `make test` — install workspace with `uv`, sync dev dependencies, and run pytest.
- `python -m pytest -q` — test suite after dependencies are available.
- `site/*.html` — open directly in a browser for the static public-site and conversion-path review.
- `./run_demo.sh` — local end-to-end CLI demo.
- `python -m fieldgrade_ui init` — initialise UI runtime.
- `python -m fieldgrade_ui serve` — serve local UI/API.
- `python scripts/generate_demo_manifest.py` — refresh synthetic export manifest.
- `python scripts/check_proposal_readiness.py` — validate the full post-tranche submission pack.
- `python scripts/validate_fieldgrade_pack.py` — compatibility wrapper around the readiness checker.

## Fresh smoke-test evidence

See [`docs/proposal/FIELDGRADE_SMOKE_TEST_EVIDENCE.md`](FIELDGRADE_SMOKE_TEST_EVIDENCE.md) for the dated command log captured on 2026-05-15, including proposal-pack checks, unit-test attempts, Docker runtime verification, and sandbox limitations.
That note is the per-run evidence source; the release checklist remains a release-management checklist rather than a PR-by-PR execution log.

## Validator coverage status

`scripts/check_proposal_readiness.py` now enforces the reviewer and submission artifacts added in the latest tranche, including the submission checklist, reviewer walkthrough, screenshot capture plan, smoke evidence note, release publication plan, and pilot data replacement protocol.
This closes the earlier validator-drift gap between `README_PROPOSAL_PACK.md` and the automated readiness check, while leaving screenshot capture and release publication themselves as separate operational tasks.

## Known gaps

- The proposal demo is synthetic and should be replaced or extended with partner-approved non-sensitive records for real submissions, using the documented pilot data replacement protocol.
- Submission-mode routing is now documented, but each mode still needs a real partner case before Fieldgrade should be framed as deployment-ready for that route.
- Production hardening, access-control review, actual screenshot asset capture, and partner user testing remain future work.
- GitHub release publication and screenshot capture are still incomplete even though the validator now checks the supporting documents for those workflows.
- Advanced-materials use cases are controlled extensions only until real lab validation exists.
- The proposal pack does not claim regulatory certification or production assurance.

## Stop condition status

The required proposal documents, demo data, validation scripts, and audit materials are present. The readiness script checks files, JSON parsing, required object fields, placeholder text, and README local setup coverage.
Read together with the rubric above, that means reviewers can verify pack integrity with the script while using this audit to understand the remaining runtime and README polish gap.
