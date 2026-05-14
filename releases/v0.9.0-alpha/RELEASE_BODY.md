# Fieldgrade v0.9.0-alpha

Fieldgrade v0.9.0-alpha is suitable for private evaluation, founder-led setup, and pilot deployments. It is not yet a self-serve commercial SaaS or certified compliance product.

> Capture evidence. Seal provenance. Review decisions. Export audit-ready proof.

This alpha release is designed for one clear pilot path: install Fieldgrade, open the sample workflow, review evidence, export a proof pack, and request a paid setup.

Attached deliverables:

- fieldgrade-v0.9.0-alpha-source.zip
- fieldgrade-proofops-demo-pack.zip
- fieldgrade-foodqa-sample-pack.zip
- fieldgrade-govai-sample-pack.zip
- SHA256SUMS.txt
- RELEASE_MANIFEST.json

Public proof included in the repository:

- walkthrough GIF: `site/demo/fieldgrade-proofops-walkthrough.gif`
- screenshot gallery: `site/screenshots/`
- proof-pack PDFs: `exports/sample_audit_pack/`
- install guide: `INSTALL.md`
- release notes: `RELEASE_NOTES_v0.9.0-alpha.md`

First-run Docker note:

- if `/readyz` is still `503`, run `docker compose -f compose.yaml -f compose.dev.yaml exec -T web python -m fieldgrade_ui init`
