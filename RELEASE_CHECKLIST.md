# Fieldgrade release checklist

Use this checklist before publishing a pilot or alpha release.

## Repository and documentation

- [ ] Update `CHANGELOG.md`
- [ ] Update release notes for the target version
- [ ] Confirm `LICENSE`, `SECURITY.md`, `INSTALL.md`, and `DATA_HANDLING.md` are still accurate
- [ ] Confirm README badges and quick links still resolve correctly

## Validation

- [ ] `bash scripts/bootstrap_dev.sh`
- [ ] `./.venv/bin/python -m pytest -q`
- [ ] `FG_API_TOKEN=ci_dummy_token docker compose -f compose.yaml config`
- [ ] `FG_API_TOKEN=ci_dummy_token docker compose -f compose.yaml -f compose.dev.yaml config`

## Docker smoke test

- [ ] `export FG_API_TOKEN=demo-local-token`
- [ ] `docker compose -f compose.yaml -f compose.dev.yaml up -d --build`
- [ ] `curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/healthz`
- [ ] `docker compose -f compose.yaml -f compose.dev.yaml exec -T web python -c "from pathlib import Path; from mite_ecology.db import connect, init_db; db_path = Path('/app/mite_ecology/runtime/mite_ecology.sqlite'); db_path.parent.mkdir(parents=True, exist_ok=True); con = connect(db_path); init_db(con, Path('/app/mite_ecology/sql/schema.sql'))"`
- [ ] `curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/readyz`
- [ ] `docker compose -f compose.yaml -f compose.dev.yaml down`

## Release packaging

- [ ] Draft GitHub Release created
- [ ] Source archive attached
- [ ] Demo/sample packs attached if applicable
- [ ] Checksums or manifest attached if applicable

## Commercial packaging

- [ ] Pricing/setup page reviewed
- [ ] Contact / setup request CTA reviewed
- [ ] Public disclaimers reviewed for regulated and AI-assisted use cases
