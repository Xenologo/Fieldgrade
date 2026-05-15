# Fieldgrade Risk and Ethics Register

| Risk | Impact | Control | Residual status |
|---|---|---|---|
| Synthetic records presented as real evidence | Misleading funders or partners | Synthetic-data notices in source objects, manifest, demo script, and proposal documents | Controlled for proposal demo |
| AI hallucination treated as evidence | Unsupported claims enter datasets or proposals | AI-assisted outputs remain review-bound and can be marked `audit_only` | Requires partner operating procedure |
| Overclaiming production readiness | Loss of trust or unsuitable deployment | Use “proposal-ready demonstrator” unless production evidence exists | Controlled in proposal pack |
| Privacy leakage during ingestion | Sensitive data exposure | Local-first framing, no new network calls, recommend data classification before real ingestion | Requires deployment controls |
| Dataset licensing ambiguity | Reuse or publication risk | Require license and provenance notes for real datasets | Requires partner review |
| Benchmark contamination | Invalid evaluation results | Separate demo, training, validation, and benchmark artifacts; record transformation history | Requires benchmark-specific protocol |
| Weak human review | Unchecked claims exported | Review states, admissibility tiers, actor/timestamp audit events | Requires reviewer training |
| Misuse for papering over poor evidence | False confidence in weak artifacts | Risk flags, rejected/audit-only tiers, explicit limitation notes | Requires governance enforcement |
| Security or access-control gaps | Unauthorised evidence access | Keep proposal demo synthetic; scope access-control hardening in roadmap | Open engineering item |
| Materials-science overextension | Synthetic materials records misread as validation | Mark advanced-materials examples as future controlled extensions only | Controlled in proposal demo |

## Ethics position

Fieldgrade should make evidence easier to inspect, not harder. It should preserve disagreement, uncertainty, and review boundaries. It should not convert AI-generated text, speculative technical ideas, or synthetic examples into approved facts without domain review.

## Required operating controls for real pilots

1. Define data owners and reviewers.
2. Set admissibility-tier policy before ingestion.
3. Label AI-assisted content.
4. Keep sensitive records local unless a partner approves transfer.
5. Record source licenses and reuse constraints.
6. Export limitations alongside proof packs.
7. Review security and privacy controls before using real operational or research data.
