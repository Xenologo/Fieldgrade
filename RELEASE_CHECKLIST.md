# Fieldgrade release checklist

Use this checklist before publishing a pilot or alpha release.

## Repository and documentation

- [x] Update `CHANGELOG.md`
- [x] Update release notes for the target version
- [x] Confirm `LICENSE`, `SECURITY.md`, `INSTALL.md`, and `DATA_HANDLING.md` are still accurate
- [x] Confirm README badges and quick links still resolve correctly

## Validation

- [x] Review the dated command log in `docs/proposal/FIELDGRADE_SMOKE_TEST_EVIDENCE.md` for per-run validation evidence
- [x] `bash scripts/bootstrap_dev.sh`
- [x] `./.venv/bin/python -m pytest -q`
- [x] `FG_API_TOKEN=ci_dummy_token docker compose -f compose.yaml config`
- [x] `FG_API_TOKEN=ci_dummy_token docker compose -f compose.yaml -f compose.dev.yaml config`
- [x] `FG_API_TOKEN=ci_dummy_token FIELDGRADE_DOMAIN=ci.example.invalid FG_FORWARDED_ALLOW_IPS=127.0.0.1 docker compose -f compose.yaml -f compose.production.yaml config`
- [x] `uv lock --check`
- [x] `uv export --frozen --no-dev --no-hashes --no-emit-workspace`
- [x] `docker build -t fieldgrade:ci .`

## Docker smoke test

- [x] See `docs/proposal/FIELDGRADE_SMOKE_TEST_EVIDENCE.md` for the dated 2026-05-15 smoke-test run; the checkboxes below are release-checklist state, not standalone dated evidence
- [x] `export FG_API_TOKEN=demo-local-token`
- [x] `docker compose -f compose.yaml -f compose.dev.yaml up -d --build`
- [x] `curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/healthz`
- [x] `docker compose -f compose.yaml -f compose.dev.yaml exec -T web python -m fieldgrade_ui init` if `/readyz` is still `503`
- [x] `curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/readyz`
- [x] `docker compose -f compose.yaml -f compose.dev.yaml down`

## Release packaging

- [x] Draft GitHub Release copy prepared in `releases/v0.9.0-alpha/RELEASE_BODY.md`
- [ ] Publish the GitHub Release object for `v0.9.0-alpha` and attach the release packet assets
- [x] Source archive attached
- [x] Demo/sample packs attached
- [x] Checksums and release manifest attached

## Commercial packaging

- [x] Pricing/setup page reviewed
- [x] Contact / setup request CTA reviewed
- [x] Public disclaimers reviewed for regulated and AI-assisted use cases
- [x] Setup offer, pilot intake, and launch packet added
