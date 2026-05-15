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
- `run_demo.sh` runs a local Termite plus mite_ecology demonstration in `.demo_runtime`.
- `run_demo.ps1` provides the Windows demo route.
- `fieldgrade_ui/__main__.py` exposes UI/API commands through `python -m fieldgrade_ui` and the installed console script.
- `scripts/bootstrap_dev.sh` and `scripts/bootstrap_dev.ps1` provide development setup.

## Proposal-readiness assets added

- Proposal pack under `docs/proposal/`.
- Synthetic demo evidence records under `data/demo/`.
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

## Commands identified

- `bash scripts/bootstrap_dev.sh` — development setup.
- `make test` — install workspace with `uv` and run pytest.
- `python -m pytest -q` — test suite after dependencies are available.
- `./run_demo.sh` — local end-to-end CLI demo.
- `python -m fieldgrade_ui init` — initialise UI runtime.
- `python -m fieldgrade_ui serve` — serve local UI/API.
- `python scripts/generate_demo_manifest.py` — refresh synthetic export manifest.
- `python scripts/check_proposal_readiness.py` — validate proposal pack.

## Known gaps

- The proposal demo is synthetic and should be replaced or extended with partner-approved non-sensitive records for real submissions.
- Production hardening, access-control review, screenshot capture, and partner user testing remain future work.
- Advanced-materials use cases are controlled extensions only until real lab validation exists.
- The proposal pack does not claim regulatory certification or production assurance.

## Stop condition status

The required proposal documents, demo data, validation scripts, and audit materials are present. The readiness script checks files, JSON parsing, required object fields, placeholder text, and README local setup coverage.
