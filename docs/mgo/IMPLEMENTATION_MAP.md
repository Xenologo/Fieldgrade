# MGO v0.2 — Implementation Map

This doc is a living map of where MGO touches the repo, organized by PR phase.

## Current architecture anchors

- `termite_fieldpack/`: untrusted inputs → verified sealed bundles (includes `kg_delta.jsonl`)
- `mite_ecology/`: design-time KG + deterministic analytics, with an existing `kg_deltas` hash-chain (SQLite)
- `fieldgrade_ui/`: operator UX + lightweight graph explorer

## PR-01 — Canonical GraphDelta Ledger + Stable IDs

**Goal**

- Introduce an append-only, hash-chained `GraphDelta` ledger as the canonical representation of KG mutations.
- Provide canonical JSON serialization and stable URN helpers.
- Provide deterministic replay from ledger → KG serialization.

**Planned changes (additive, minimal risk)**

- New schema:
  - `schemas/graph_delta_event_v1.json`
- Schema registry update (if required by repo conventions):
  - `schemas/ldna_registry.yaml` (add a `ldna://json/graph_delta_event@1.0.0` entry)
- New module (proposed):
  - `mite_ecology/mite_ecology/graph_delta.py` (canonical JSON + event hashing + append/verify)
- KG mutation hook (minimal touch):
  - `mite_ecology/mite_ecology/kg.py` (ensure mutations go through a single emission point)
- Replay utility:
  - `scripts/ledger_replay.py` (verify chain + apply events deterministically + emit canonical KG JSON)
- Tests:
  - `mite_ecology/tests/test_graph_delta_ledger.py`

**Compatibility notes**

- Do not change existing CLI entrypoints.
- Do not change existing on-disk formats inside sealed bundles.
- Keep the existing `kg_deltas` SQLite chain intact; PR-01 can initially dual-write (SQLite + ledger file) to avoid breaking workflows.

**Risks**

- Performance: one event per op can be large. Mitigation: keep payload minimal, stable ordering, and allow chunked replay.
- Semantics: existing KG ops include domain-specific op names (e.g., `ADD_NODE`). PR-01 should encode them without renaming.

## PR-02 — RunContext Everywhere

Primary touchpoints:

- Termite seal/ingest outputs: run context artifact emission
- Ecology import + delta emission: attach run_id/trace_id everywhere
- UI APIs: runs + deltas listing endpoints

## PR-03 — PROV overlay + cycle detection

Primary touchpoints:

- Add Prov nodes/edges (Entity/Activity/Agent)
- Add API `GET /api/prov/path`

## PR-04 — ArchitectureSpec + structural diff

Primary touchpoints:

- Add ArchitectureSpec nodes
- Deterministic diff artifact generation + UI viewer

## PR-05 — Doc coverage + staleness

Primary touchpoints:

- Doc nodes + staleness evaluation from hashes
- UI quality lens

## PR-06 — Metrics + quality gates bound to runs

Primary touchpoints:

- Metric/GateResult nodes
- Promotion gating alignment with existing review modes

## PR-07 — Attestations + SBOM/AIBOM linkage

Primary touchpoints:

- Attestation nodes
- BOM generation at seal time + UI badge

## PR-08 — Lifecycle controller + actuation boundary

Primary touchpoints:

- Actuation artifacts (WillCommit, AbyssCertificate)
- API plan/certify/execute + UI panel
- Hard gate effectful ops
