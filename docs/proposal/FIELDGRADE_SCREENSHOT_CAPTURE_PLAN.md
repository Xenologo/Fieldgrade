# Fieldgrade Screenshot Capture Plan

## Purpose

Capture a small, concrete screenshot set that helps a reviewer verify the submission pack quickly. Screenshots are supporting evidence for a proposal demonstrator and should not imply production certification.

## Capture rules

- Capture from a clean local working tree.
- Prefer readable terminal width and visible file paths.
- Keep any runtime screenshot local-first and non-sensitive.
- Do not capture secrets, tokens, or unrelated local data.
- If screenshots are added to the repo, store them under `docs/screenshots/`.

## Required screenshot set

| ID | Screenshot | Source | What must be visible | Suggested filename |
| --- | --- | --- | --- | --- |
| 1 | Proposal-pack repository view | File browser or terminal | repo root with `docs/proposal/`, `data/demo/`, `scripts/`, `outputs/proposal_pack/` | `01-repo-root-proposal-pack.png` |
| 2 | Synthetic source objects | `data/demo/fieldgrade_demo_sources.json` | synthetic notice context, object IDs, provenance-oriented fields | `02-demo-sources.png` |
| 3 | Demo export manifest | `data/demo/fieldgrade_demo_export_manifest.json` | object export hashes and file checksum section | `03-demo-export-manifest.png` |
| 4 | Readiness PASS output | terminal after `python scripts/check_proposal_readiness.py` | `PASS`, `100/100`, and empty findings lists | `04-readiness-pass.png` |
| 5 | Validation wrapper PASS output | terminal after `python scripts/validate_fieldgrade_pack.py` | wrapper-triggered PASS output | `05-validate-pack-pass.png` |

## Optional screenshot set

| ID | Screenshot | Source | What must be visible | Suggested filename |
| --- | --- | --- | --- | --- |
| 6 | Demo script | `docs/proposal/FIELDGRADE_DEMO_SCRIPT.md` | walkthrough headings and screenshot instructions | `06-demo-script.png` |
| 7 | Readiness audit | `docs/proposal/FIELDGRADE_READINESS_AUDIT.md` | score distinction section and limitations | `07-readiness-audit.png` |
| 8 | Local UI/API | `http://127.0.0.1:8787` after local setup | only if the local UI is actually running and non-sensitive | `08-local-ui.png` |

## Capture order

1. Run `python scripts/generate_demo_manifest.py`.
2. Capture the synthetic source objects.
3. Capture the refreshed export manifest.
4. Run `python scripts/check_proposal_readiness.py` and capture the PASS output.
5. Run `python scripts/validate_fieldgrade_pack.py` and capture the wrapper PASS output.
6. Capture optional audit or UI evidence only if it is genuinely available.

## Reviewer note to accompany screenshots

Use a short note such as: “Screenshots were captured from the local Fieldgrade proposal demonstrator. Demo records are synthetic and included only to show provenance, review, and export structure.”
