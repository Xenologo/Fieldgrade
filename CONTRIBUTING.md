# Contributing (strict determinism + provenance)

This repo is operated under **strict determinism and evidence integrity** constraints.
If a change risks altering bundle bytes, hash binding, DSSE semantics, CycloneDX semantics, or replay outcomes, it must be treated as a breaking change and gated by kill-tests.

## Non-negotiable invariants

- **Sealed bundle immutability**: after `termite seal`, bundle ZIP bytes are immutable evidence artifacts.
- **Hash binding / canonicalization**: anything hashed must use canonical/stable serialization and stable ordering.
- **DSSE semantics**: do not change envelope structure, key identity binding, or verification expectations without explicit policy + tests.
- **CycloneDX semantics**: do not weaken SBOM validation; if policy requires CycloneDX, missing/invalid BOM must fail verification.
- **Replay equivalence**: replay must continue to validate and reproduce deterministic artifacts (as defined by tests).

## One PR per step (A1…D3)

- Each step must be a standalone, mergeable PR.
- Do not mix unrelated refactors or “drive-by” fixes.
- Keep diffs minimal and scoped to the step.

PR description must include:
- Goal and scope (what is in/out)
- Risk assessment (determinism + security)
- Evidence: test command(s) run and results

## Required checks before opening a PR

- Run unit tests: `pytest -q`
- If Docker/compose changes are involved: bring up the stack and run the smoke test scripts under `scripts/`.

## Security expectations

- Do not log secrets.
- Preserve API auth expectations (`FG_API_TOKEN` gating / X-API-Key/Bearer usage).
- Treat uploads as untrusted input; preserve sandboxing constraints.

## Git requirement for PR workflow

This workspace must be a Git working tree connected to a remote in order to follow the “one PR per step” workflow.

If you extracted from a zip and there is no `.git/` directory:

- Preferred: re-clone from the authoritative remote and re-apply local changes.
- If you cannot re-clone: `git init` + add the correct remote + create a baseline commit (note: this loses history).

(Ask for the repository URL before proceeding with PR-per-step work.)
