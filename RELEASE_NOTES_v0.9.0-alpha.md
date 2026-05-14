# Fieldgrade v0.9.0-alpha release notes

## Release page summary

Fieldgrade v0.9.0-alpha is suitable for private evaluation, founder-led setup, and pilot deployments. It is not yet a self-serve commercial SaaS or certified compliance product.

## Summary

Fieldgrade v0.9.0-alpha now ships as a founder-led pilot release packet with reproducible install materials, downloadable sample packs, pilot intake paths, proof-pack PDFs, and public alpha launch collateral.

## Included in this alpha

- buyer-facing product, demo, setup, contact, docs, and pricing pages
- reproducible dependency lockfiles: `uv.lock` and `requirements.lock`
- release packet materials under `releases/v0.9.0-alpha/`
- downloadable ProofOps, GovAI, and FoodQA sample pack ZIPs
- sample proof-pack PDFs for ProofOps, GovAI, and FoodQA
- pilot intake, ProofOps setup offer, GovAI/FoodQA pilot templates, and pilot trust packet docs
- launch post, LinkedIn announcement, buyer email, and founder demo script

## Attached deliverables

- `fieldgrade-v0.9.0-alpha-source.zip`
- `fieldgrade-proofops-demo-pack.zip`
- `fieldgrade-foodqa-sample-pack.zip`
- `fieldgrade-govai-sample-pack.zip`
- `SHA256SUMS.txt`
- `RELEASE_MANIFEST.json`

## Intended use

- private alpha evaluations
- founder-led pilot deployments
- internal stakeholder demos
- pilot proof-pack walkthroughs

## Installation paths verified

- Linux lockfile path: `python3 -m pip install -U uv && uv sync --frozen`
- Windows lockfile path: `python -m pip install -U uv && uv sync --frozen`
- Dev bootstrap path: `bash scripts/bootstrap_dev.sh`
- Docker runtime path: `docker compose -f compose.yaml -f compose.dev.yaml up -d --build`

## Docker Compose smoke test

Validated on 2026-05-14 with the development overlay.

- `/healthz` returned `200 OK` after the stack started
- `/readyz` returned `200 OK` after initialising the first-run `mite_ecology` runtime DB using the documented `INSTALL.md` snippet
- the stack was brought down cleanly after verification

## Operator notes

- use `INSTALL.md` for pilot release install mode versus development mode
- use `docs/PILOT_SECURITY_BRIEF.md`, `docs/PILOT_DATA_BOUNDARIES.md`, and `docs/AI_USE_DISCLAIMER.md` when briefing pilot users
- use `releases/v0.9.0-alpha/RELEASE_BODY.md` as the GitHub Release page copy
- use `releases/v0.9.0-alpha/SHA256SUMS.txt` and `releases/v0.9.0-alpha/RELEASE_MANIFEST.json` when attaching deliverables

## Not yet included

- automated GitHub Release publishing
- self-serve payment and fulfilment automation
- production-scale multi-tenant SaaS features
