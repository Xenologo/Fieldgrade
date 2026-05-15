# Fieldgrade Data Governance

## Governance principle

Fieldgrade should preserve evidence provenance without pretending that capture alone proves truth. Source material, metadata, annotations, AI-use records, review decisions, and export manifests should remain distinct so reviewers can inspect how a claim was assembled.

## Data categories

- Synthetic proposal-demo records under `data/demo/`.
- Local runtime evidence ingested through Termite Fieldpack.
- Review and analysis records processed through mite_ecology.
- Fieldgrade UI/API records for jobs, governance, registries, and readiness surfaces.
- Export bundles, manifests, reports, and audit-pack outputs.

## Provenance controls

Every proposal-demo object includes object ID, title, source type, provenance note, ingestion timestamp, claim status, admissibility tier, review state, evidence status, review status, risk flags, and human-readable explanation. Generated manifests add object-level export hashes and file-level SHA-256 checksums.

## Human review controls

AI-assisted outputs and speculative extensions should remain in `audit_only`, `controlled_extension`, or `speculative_projective_extension` tiers until a human reviewer verifies sources, limitations, and intended use. Review decisions should identify the actor, timestamp, decision, and reason.

## Privacy and sensitivity

The proposal demo uses synthetic data only. Real deployments should define data-classification rules before ingestion, keep sensitive data local where possible, avoid unnecessary external transfer, and document retention and deletion rules.
Any partner-approved public pilot sample should follow `docs/proposal/FIELDGRADE_PILOT_DATA_REPLACEMENT_PROTOCOL.md` before it is committed.

## Licensing and dataset reuse

Proposal and benchmark datasets should record license, source permission, transformation history, and reuse constraints. Public or partner datasets should not be mixed into benchmark artifacts unless their license and provenance support the intended use.

## Benchmark contamination controls

Benchmark-oriented proposals should separate training, evaluation, validation, and demonstration artifacts. AI-generated summaries should be labelled, cached where possible, and reviewed so benchmark records do not silently absorb unverified model output.

## Export controls

Export manifests should include file checksums, object export hashes, synthetic-data notices where applicable, and a clear statement of admissibility status. Exports should distinguish proposal examples from operational evidence.
