# Fieldgrade smoke-test evidence

## Evidence date

- Date: 2026-05-15
- Environment: GitHub Copilot task sandbox, repository at `/home/runner/work/Fieldgrade/Fieldgrade`
- Host runtime: Linux 6.17.0-1010-azure x86_64 GNU/Linux, Python 3.12.3
- Container runtime: Docker 28.0.4, Docker Compose v2.38.2

This note records commands actually attempted on 2026-05-15 to separate dated execution evidence from release-checklist checkboxes.

## Command evidence

| Validation type | Command | Expected result | Actual result | Status | Limitation / note |
| --- | --- | --- | --- | --- | --- |
| Proposal-pack validation | `python scripts/generate_demo_manifest.py` | Rebuild the synthetic demo export manifest without errors. | `Wrote data/demo/fieldgrade_demo_export_manifest.json with 3 objects` | Pass | Command ran from the repo root. |
| Proposal-pack validation | `python scripts/check_proposal_readiness.py` | Report a passing proposal-pack readiness check. | `Fieldgrade proposal readiness status: PASS` and `Readiness score: 100/100` | Pass | No missing files, invalid JSON, placeholders, or README findings were reported. |
| Proposal-pack validation | `python scripts/validate_fieldgrade_pack.py` | Pass by delegating to the readiness checker. | Reported the same `PASS` and `100/100` readiness result. | Pass | Compatibility wrapper behaved as expected. |
| Unit test validation | `python -m pytest -q` | Run the repository pytest suite. | `/usr/bin/python: No module named pytest` | Fail | Exact command was attempted with the sandbox system interpreter, which did not have `pytest` installed. |
| Unit test validation | `make test` | Create/update the repo virtualenv and run the canonical pytest suite. | Completed successfully and then ran `./.venv/bin/python -m pytest -q` with exit code 0. | Pass | This is the repository's documented test path in `Makefile`. |
| Unit test validation | `./.venv/bin/python -m pytest -q` | Re-run pytest from the repo-managed virtualenv. | Passed with exit code 0. | Pass | Used to confirm the suite after `make test` provisioned the environment. |
| Docker runtime validation | `FG_API_TOKEN=demo-local-token docker compose -f compose.yaml -f compose.dev.yaml up -d --build` | Build the local stack and start the `web` and `worker` services. | Completed with exit code 0 and brought the stack up. | Pass | This Docker smoke path was actually run on 2026-05-15. |
| Docker runtime validation | `curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/healthz` | Return a healthy local API response. | `HTTP/1.1 200 OK` with `{"ok":true}` | Pass | Ran after the compose stack started. |
| Docker runtime validation | `curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/readyz` | Return readiness once required runtime state exists. | Before init, returned `HTTP/1.1 503 Service Unavailable` with `missing:["mite_db:/app/mite_ecology/runtime/mite_ecology.sqlite"]`. | Expected pre-init state | This check was run before init to confirm the documented first-run behavior. |
| Docker runtime validation | `docker compose -f compose.yaml -f compose.dev.yaml exec -T web python -m fieldgrade_ui init` | Initialize the UI/runtime databases if `/readyz` is still `503`. | Returned `{"jobs_db":"/app/fieldgrade_ui/runtime/jobs.sqlite","mite_db":"/app/mite_ecology/runtime/mite_ecology.sqlite","ok":true}` | Pass | This step was necessary because `/readyz` was initially conservative on first run. |
| Docker runtime validation | `curl -H "X-API-Key: ${FG_API_TOKEN}" http://127.0.0.1:8787/readyz` | Return a ready response after init. | `HTTP/1.1 200 OK` with `{"ok":true}` | Pass | Confirms the local Docker runtime path after initialization. |
| Docker runtime validation | `docker compose -f compose.yaml -f compose.dev.yaml down` | Stop and remove the local smoke-test stack cleanly. | Completed with exit code 0. | Pass | Stack teardown was attempted and completed. |

## Environment limitations

- The exact `python -m pytest -q` command did not work in this sandbox because `/usr/bin/python` did not have `pytest`; the repo-managed `.venv` path did work after `make test`.
- The Docker smoke result above is fresh evidence from 2026-05-15 because the stack was actually started, checked, initialized, re-checked, and torn down in this environment.
- Use this note for dated command evidence. Treat release-checklist boxes as checklist state, not as a substitute for a dated execution log.
