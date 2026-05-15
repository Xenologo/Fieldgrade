# Fieldgrade Proposal Pack Output

This directory is the landing area for proposal-pack outputs such as screenshots, generated evidence bundles, reviewer notes, or exported proposal appendices.

Current proposal-readiness assets are stored in source-controlled locations:

- proposal documents: `docs/proposal/`,
- synthetic demo data: `data/demo/`,
- validation scripts: `scripts/`,
- generated demo manifest: `data/demo/fieldgrade_demo_export_manifest.json`.

To refresh and validate the current pack:

```bash
python scripts/generate_demo_manifest.py
python scripts/check_proposal_readiness.py
```

All current demo records are synthetic and must not be represented as real benchmark, lab, or operational data.
