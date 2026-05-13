# Fieldgrade Phase 2 — Sector Variant Productisation Plan

**Status:** provisioned next-phase architecture note  
**Branch:** `phase-2-sector-variants`  
**Primary product:** Fieldgrade Governance & Evidence Ledger  
**Primary audiences:** UK public-sector digital teams, regulated SMEs, governance leads, procurement/commercial teams, and AI assurance consultants.

## 1. Phase 2 thesis

Fieldgrade should now be treated as a reusable evidence-governance base class rather than as a single-purpose application.

The current repository already contains the technical substrate required for this direction:

- `termite_fieldpack/` provides offline-first ingestion, content-addressed storage, signed deterministic bundles, provenance material, policy verification, and conservative replay.
- `mite_ecology/` provides deterministic knowledge-graph import, review modes, embeddings, attention, motif mining, memo-GA export, and replay verification.
- `fieldgrade_ui/` provides the FastAPI UI/API shell, registry endpoints, pipeline orchestration, job handling, governance workspace primitives, token authentication, and tenant-aware runtime roots.
- `schemas/` and `resources/` already carry versioned JSON schemas and crosswalk resources.

Phase 2 should therefore avoid a ground-up rewrite. The right move is to add a sector-pack layer above Fieldgrade Core.

## 2. Product architecture

```text
Fieldgrade Core
  EvidenceObject
  SourceObject
  ClaimObject
  DecisionObject
  RiskObject
  ControlObject
  ActorObject
  ReviewGate
  AuditEvent
  PolicyCrosswalk
  ExportPack
  RegistryRecord

Sector Packs
  GovAI
  SME-AI
  Procurement
  DataEthics
  FoodQA
  ResearchIntegrity
  XenoVisorCapture
```

Fieldgrade Core should remain deliberately abstract. It should know how to handle evidence, sources, claims, decisions, risk, controls, actors, gates, audit events, crosswalks, exports, and registry records. It should not directly encode all domain knowledge for AI, food safety, procurement, education, health, or research.

Sector packs should define:

1. record schema;
2. required fields;
3. crosswalk templates;
4. workflow states;
5. export pack definitions;
6. default review gates;
7. recommended risks and controls;
8. UI labels and form sections;
9. buyer-specific reports.

## 3. Phase 2 milestones

### P2.1 — Sector-pack manifest runtime

Introduce a manifest schema and catalog so sector packs can be discovered, validated, and surfaced by the UI.

Deliverables:

- `schemas/fieldgrade_sector_pack_manifest_v1.json`;
- `resources/fieldgrade_sector_packs_v1.json`;
- `/api/registry/sector-packs` endpoint;
- UI selector for creating records from a sector pack;
- tests proving all bundled sector packs resolve to valid schemas and resources.

### P2.2 — GovAI hardening

The GovAI ledger MVP should be tightened into a public-sector-ready pilot product.

Deliverables:

- richer ATRS and Data/AI Ethics crosswalks;
- evidence-gap severity levels;
- claim-to-evidence map;
- supplier assurance tab;
- human oversight and challenge-route tab;
- export history with export hashes;
- governance dashboard: systems by status, risk tier, review date, gap count, and unresolved controls.

### P2.3 — SME-AI and Procurement variant pilots

Ship two adjacent variants that reuse GovAI and Core primitives.

Deliverables:

- `schemas/fieldgrade_sme_ai_system_record_v1.json`;
- `schemas/fieldgrade_procurement_assurance_record_v1.json`;
- SME-AI crosswalk starter pack;
- procurement/supplier evidence checklist;
- board-report export pack;
- supplier due-diligence export pack.

### P2.4 — Productisation and deployment hardening

Make the tool easy to pilot in real organisations.

Deliverables:

- README quickstart screenshots/GIFs;
- sample public-sector demo data;
- one-command demo seed;
- backup/restore docs;
- key-management and token-handling docs;
- release notes template;
- Docker production smoke test retained as CI gate;
- tenant-isolation regression tests.

## 4. Recommended variant order

1. **GovAI** — flagship public-sector and algorithmic transparency variant.
2. **SME-AI** — lightweight AI inventory and risk register for regulated SMEs.
3. **Procurement** — supplier assurance, model documentation, contract evidence, and due-diligence file.
4. **DataEthics** — non-AI data projects, data sharing, public benefit, ethics review.
5. **FoodQA** — batch, deviation, CAPA, supplier approval, cleaning verification, and audit preparation.
6. **ResearchIntegrity** — research evidence, claim ladder, provenance, reproducibility, and exportable registry objects.
7. **XenoVisorCapture** — headset/mobile real-world inspection capture that writes Fieldgrade EvidenceObjects.

## 5. Fieldgrade GovAI pilot offer

A concrete pilot package should be expressed in product terms, not only in repository terms:

**Fieldgrade 30-Day AI Governance Ledger Pilot**

For up to ten AI, automation, data, or algorithmic systems:

1. create system inventory;
2. assign ownership and accountability;
3. document purpose and affected groups;
4. record data provenance and lawful-basis notes;
5. capture supplier/model evidence;
6. map human oversight and challenge routes;
7. create risk/control records;
8. generate evidence-gap report;
9. generate ATRS-style draft;
10. generate plain-English public summary;
11. export internal governance record.

## 6. Design invariants

Fieldgrade should retain these invariants through Phase 2:

- Evidence before assertion.
- Claim-to-evidence mapping before publication.
- Human ownership before deployment.
- Review gates before export.
- Deterministic serialization for hashes.
- Append-only audit trails for governance actions.
- Sector packs may extend Core, but must not mutate Core semantics silently.
- LLM output remains exogenous unless cached, hashed, and recorded.

## 7. Near-term implementation sequence

```text
1. Add sector-pack manifest schema.
2. Add sector-pack catalog resource.
3. Add SME-AI and Procurement schemas.
4. Add endpoint to list sector packs.
5. Refactor GovernanceLedger into variant-aware record services.
6. Add claim-to-evidence mapping to Core schema and UI.
7. Expand crosswalk engine from required_paths only to severity, guidance, evidence_kind, and recommended_controls.
8. Add export-history object with content hash, actor, timestamp, and source record hash.
9. Add seeded demo records for GovAI, SME-AI, and Procurement.
10. Add acceptance tests covering create/update/export/crosswalk for each variant.
```

## 8. Strategic note

The decisive commercial edge is not that Fieldgrade can run deterministic KG analytics. The edge is that it can transform source material, organisational decisions, policy obligations, and audit events into a living, reviewable, exportable evidence ledger.

That makes Fieldgrade sellable as:

> A system of record for accountable AI, data, algorithmic, and regulated decision systems.
