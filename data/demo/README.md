# Fieldgrade demo data

This directory contains synthetic records used for the public Fieldgrade proposal demonstrator.

## Status

- All records here are synthetic.
- They exist to show provenance, annotation, audit-trail, and export-pack structure.
- They must not be presented as real partner, benchmark, laboratory, supplier, customer, or governance evidence.

## Files

- `fieldgrade_demo_sources.json` — synthetic source objects.
- `fieldgrade_demo_annotations.json` — synthetic annotations and review notes.
- `fieldgrade_demo_audit_trail.json` — synthetic audit events.
- `fieldgrade_demo_export_manifest.json` — generated export manifest with object hashes and checksums.

## Regeneration

From the repository root:

```bash
python scripts/generate_demo_manifest.py
python scripts/check_proposal_readiness.py
python scripts/validate_fieldgrade_pack.py
```

## Replacement path

If the proposal demonstrator later needs partner-approved non-sensitive pilot records, do not overwrite this directory with live data. Follow `docs/proposal/FIELDGRADE_PILOT_DATA_REPLACEMENT_PROTOCOL.md` and use `data/pilot_samples/` only when the sample is explicitly cleared for public repository use.
