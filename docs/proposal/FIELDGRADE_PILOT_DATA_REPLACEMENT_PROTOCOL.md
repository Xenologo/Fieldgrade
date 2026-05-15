# Fieldgrade Pilot Data Replacement Protocol

## Purpose

This protocol defines how the synthetic proposal-demo records under `data/demo/` may later be replaced or extended with partner-approved pilot records. It exists to keep Fieldgrade proposal-ready, provenance-preserving, and safe for public-repository use.

## Scope

- `data/demo/` remains synthetic by default.
- `data/pilot_samples/` is the controlled staging area for partner-approved, non-sensitive pilot samples that are explicitly cleared for this public repository.
- Real operational, customer, supplier, patient, employee, or confidential research data must not be committed to this repository unless it satisfies every control below and is genuinely approved for public distribution.

## Synthetic versus partner-approved pilot records

### Synthetic demo records

Synthetic demo records:

- are created for walkthroughs, proposal validation, and reviewer verification,
- must be labelled as synthetic or proposal-demo content,
- must not be presented as real benchmark, lab, customer, supplier, or governance evidence, and
- may be regenerated, simplified, or redacted freely because they are not live partner records.

### Partner-approved pilot records

Partner-approved pilot records:

- originate from a real partner workflow or a partner-controlled transformation of one,
- require explicit permission before they are committed,
- must preserve provenance and review metadata without exposing restricted content, and
- should be the minimum viable sample needed to prove the pilot pathway.

## Required metadata before any pilot record is committed

Every committed pilot record must have a companion note or manifest entry that states:

- data owner,
- source organisation or originating workflow,
- licence or reuse permission,
- sensitivity class,
- consent or permission basis,
- redaction status,
- synthetic versus real label,
- export permission,
- reviewer sign-off,
- provenance note,
- ingestion timestamp,
- admissibility tier, and
- review state.

If any of these fields is unknown, the record must stay out of the public repository until the gap is resolved.

## Minimum approval workflow

1. Identify the partner record class proposed for inclusion.
2. Confirm the data owner and the person authorised to approve publication.
3. Record the licence or written permission that allows repository publication.
4. Classify the record for sensitivity, confidentiality, and exportability.
5. Redact direct and indirect identifiers, secrets, credentials, and commercially sensitive details.
6. Label the record clearly as `synthetic` or `partner_approved_pilot`.
7. Confirm whether export outside the repository is allowed, restricted, or prohibited.
8. Obtain reviewer sign-off from both the repository side and the partner side where applicable.
9. Store only the minimum public sample necessary in `data/pilot_samples/`.

## Privacy, redaction, and public-repo controls

Before committing pilot records:

- remove personal data unless there is explicit public-release permission and a compelling reason to include it,
- remove API keys, credentials, access tokens, secrets, internal URLs, and private infrastructure details,
- remove commercially sensitive pricing, supplier terms, and unreleased product details unless cleared for publication,
- remove unpublished scientific results or restricted benchmark content unless the partner has approved public disclosure,
- prefer excerpts, summaries, placeholders, hashed identifiers, and structural examples over raw source dumps, and
- document what was redacted and why.

## Export permission rules

Each pilot sample must state one of:

- `public_repo_and_export_allowed`
- `public_repo_allowed_export_restricted`
- `public_repo_metadata_only`
- `not_permitted_for_public_repo`

Only the first three states are eligible for inclusion here. If export is restricted, the record should be limited to the minimum public-safe representation needed for review.

## Reviewer sign-off requirement

No partner-approved pilot record should be committed without reviewer sign-off that confirms:

- provenance is understood,
- the public-repo licence or permission is documented,
- privacy and redaction checks are complete,
- the synthetic-versus-real label is correct,
- export permission is recorded, and
- the sample does not overstate what Fieldgrade has proven.

## Prohibited data types for this public repository

Do not commit:

- unredacted personal data,
- health records,
- payroll, HR, or student records,
- private contracts or non-public legal correspondence,
- confidential customer or supplier files,
- secrets, tokens, credentials, or internal security materials,
- export-controlled or restricted research data, or
- regulated or safety-critical evidence that a partner has not approved for public release.

## Repository usage note

Use `data/demo/` for proposal-review materials and `data/pilot_samples/` only for the rare case where a partner-approved, non-sensitive, public sample is genuinely needed. If a pilot record is useful for validation but not safe for publication, keep it out of this repository and describe the pathway in proposal materials instead.
