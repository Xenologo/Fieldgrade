# Fieldgrade in the CFX Stack

**Canonical object:** `CAO-STACK-CFX-001/FIELDGRADE-001`  
**Parent architecture:** `CAO-STACK-CFX-001` — CFX Stack: Continuity–Fieldgrade–Xenoclaw Operating Architecture  
**System identity:** Fieldgrade as the evidentiary substrate of the Continuity Operating System  
**Role phrase:** Fieldgrade witnesses.  
**Motto:** Seal the evidence.

## 1. Position in CFX

CFX is the Continuity Operating System:

```text
Fieldgrade + Xenoclaw + CAO = CFX
Provenance + Runtime + Canonisation = Continuity Operating System
```

Fieldgrade is the provenance and deterministic validation layer. It is not the whole CFX system, and it is not merely a utility package. It is the evidentiary floor beneath Xenoclaw runtime action and CAO canonisation.

```text
Fieldgrade witnesses.
Xenoclaw acts.
CAO judges.
```

## 2. Boundary of authority

Fieldgrade may assert:

- this object was ingested;
- this object was sealed;
- this manifest binds these files;
- this hash matches;
- this provenance chain is inspectable;
- this replay or structural verification succeeded;
- this graph delta was recorded;
- this evidence packet is suitable for downstream review.

Fieldgrade may not assert:

- this object is canonical;
- this generated object is true;
- this claim belongs in CAO;
- this runtime output is doctrine;
- this speculative object is admissible without review.

That authority belongs to CAO after registry and admissibility review.

## 3. CFX lifecycle mapping

```text
RAW INPUT
  ↓
FIELDGRADE INGESTION
  file, note, graph, archive object, bundle, dataset
  ↓
TERMITE SEALING
  CAS, hash chain, manifest, SBOM, provenance, kg_delta
  ↓
MITE ECOLOGY ANALYSIS
  embeddings, attention, motifs, deterministic GA, neuroarch export
  ↓
XENOCLAW RUNTIME IMPORT
  graph/autopilot workspace, ledger, delta, ontology runtime
  ↓
MORPHOGENESIS / CODEGEN
  motifs, genomes, phenotypes, components, Mite/Memite/MetaMite actions
  ↓
FIELDGRADE HARDENING
  replay, verification, deterministic checks, provenance review
  ↓
CAO REGISTRY CANDIDATE
  object ID, claim level, parent architecture, dependencies
  ↓
CAO ADMISSIBILITY REVIEW
  canonical, lab-active, quarantined, rejected, archived
  ↓
ATLAS / MONOGRAPH / REGISTRY PUBLICATION
```

Compressed process:

```text
Ingest → Seal → Mutate → Evaluate → Verify → Register → Canonise
```

## 4. Repository development direction

The existing repository already contains the core Fieldgrade/Termite/mite_ecology spine:

- `termite_fieldpack/` for ingestion, CAS, provenance, sealing, verification, replay, and local LLM runtime ownership;
- `mite_ecology/` for deterministic graph import, GNN/GAT-style analysis, motif mining, deterministic GA, and neuroarch export;
- UI, Docker, bootstrap, review, quarantine, and replay workflows.

The next development direction is therefore not replacement. It is CFX alignment:

1. make Fieldgrade outputs explicitly consumable by Xenoclaw;
2. make hardened evidence packets explicitly consumable by CAO;
3. preserve strict determinism and evidence integrity;
4. add schemas, docs, and endpoints only where they clarify provenance-runtime-canonisation boundaries.

## 5. Required CFX artefact classes

Fieldgrade should progressively expose the following artefact classes:

```text
fieldpack
manifest
provenance_event
kg_delta
replay_report
verification_report
evidence_packet
runtime_hardening_report
cao_registry_candidate
```

Only the first six are pure Fieldgrade artefacts. The final two are bridge artefacts: they prepare downstream handoff without claiming canonisation.

## 6. Bridge contract to Xenoclaw

Fieldgrade should export evidence and graph material in a form that Xenoclaw can import without losing traceability.

Minimum bridge fields:

```yaml
fieldgrade_bridge:
  bundle_id: string
  manifest_sha256: string
  fieldpack_path: string
  kg_delta_path: string
  provenance_chain_head: string
  replay_status: passed | failed | not_run
  verification_status: passed | failed | not_run
  admissibility_hint: evidence_only
```

The `admissibility_hint` is deliberately constrained. Fieldgrade may mark an object as evidence-bearing; it may not mark it as canonical.

## 7. Bridge contract to CAO

Fieldgrade may prepare CAO registry candidates, but CAO must perform the review.

Minimum CAO candidate fields:

```yaml
cao_candidate:
  candidate_id: string
  source_bundle_id: string
  source_manifest_sha256: string
  proposed_title: string | null
  proposed_domain: CFX | mite_ecology | HXMM | QFIM-Triad | unknown
  proposed_object_type: string | null
  evidence_packet: string
  runtime_trace: string | null
  claim_level_recommendation: evidence-supported | lab-active | speculative | unknown
  review_required: true
```

`review_required` must remain true for every candidate emitted by Fieldgrade.

## 8. Non-negotiable invariants

Fieldgrade development must preserve:

- sealed bundle immutability;
- canonical JSON serialization for hashed data;
- hash-chain integrity;
- DSSE/key identity semantics where used;
- CycloneDX/SBOM validation semantics where required;
- deterministic replay assumptions;
- quarantine and review separation;
- no silent promotion from evidence to canon.

## 9. Development phases

### FG-CFX-01 — Architecture and schema alignment

- install CFX doctrine documentation;
- add bridge schemas for Xenoclaw and CAO handoff;
- document object status vocabulary;
- add tests that validate bridge objects without affecting bundle bytes.

### FG-CFX-02 — Evidence packet formalisation

- define `evidence_packet.schema.json`;
- add CLI/API export command if not already present;
- ensure packet hashes are deterministic;
- include provenance and replay status.

### FG-CFX-03 — Runtime hardening reports

- define a report emitted when Xenoclaw output is returned to Fieldgrade;
- bind runtime deltas back to source evidence;
- verify that mutation did not sever provenance.

### FG-CFX-04 — CAO candidate handoff

- define candidate export format;
- preserve `review_required: true`;
- add status mapping into `canonical`, `lab-active`, `quarantined`, `rejected`, `archived` as CAO-owned outcomes only.

### FG-CFX-05 — Dashboard integration

- expose CFX status in UI/API;
- display sealed evidence, runtime handoff readiness, and CAO candidate queue separately;
- never display generated runtime material as canonical unless CAO status is present.

## 10. Final rule

Dynamic Xenoclaw output may inform CAO. It may not silently become CAO.

Fieldgrade's task is to make that rule technically enforceable by ensuring that every object has a trace, every transformation has a delta, every bundle has a manifest, and every downstream canonical candidate remains review-bound.
