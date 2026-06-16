# COIL / HITT / FIELDGRADE Stack Sandbox v0.3

This directory seeds a local-first implementation track for **COIL/HITT/FIELDGRADE** inside the existing Fieldgrade repository.

The stack demonstrates a protected-participation architecture for youth online safety:

- **COIL** — Child Online Interaction Layer / Licence: a privacy-preserving age-and-capability credential.
- **HITT** — High-Integrity Trust Token: a non-transferable, non-assumable, revocable proof object.
- **FIELDGRADE** — compliance witnessing: a tamper-evident audit/provenance layer for platform corridor enforcement.

The central design rule is:

> Protect the corridor; do not sever the child from the culture.

## Boundary

This sandbox is demonstration-only. It must not be used as legal age assurance and must not be used with real child data, real biometric data, genetic data, or production platform decisions.

Biometrics, if used in a future production design, should only unlock a local device-held credential. They must not become network-visible identifiers. Genetic identification is inadmissible for this use case.

## Current v0.3 scope

- Local synthetic credential issuance.
- HITT-style proof presentation.
- Corridor verification and routing.
- Fieldgrade hash-chained audit events.
- Audit summary and audit-bundle export.
- Synthetic misuse simulations: wrong corridor, revoked replay, forged holder signature, over-identification, and tampered Fieldgrade chain.

## Run the monolithic seed

```bash
cd experiments/coil_stack_sandbox
python coil_stack_v0_3.py selftest
python coil_stack_v0_3.py issue --age-band 13-15 --alias demo-child
python coil_stack_v0_3.py list
python coil_stack_v0_3.py present --corridor COIL-C1 --out latest_hitt.json
python coil_stack_v0_3.py verify --presentation latest_hitt.json
python coil_stack_v0_3.py fieldgrade verify
python coil_stack_v0_3.py audit export --out fieldgrade_audit_bundle.json
python coil_stack_v0_3.py simulate revoked-replay --isolated
```

## Deployment track

This directory is intentionally a seed. The next refactor should split the monolithic file into:

```text
packages/coil_core/
packages/hitt_wallet/
packages/hitt_verifier/
packages/fieldgrade_ledger/
packages/coil_router/
apps/coil_console/
apps/coil_cli/
```

## Product positioning

COIL/HITT/FIELDGRADE should be presented as a standards-aligned trust, routing, and audit stack rather than a blanket-ban bypass. A platform receiving a valid minor credential should be required to instantiate the relevant child-safe interaction corridor and produce audit-grade evidence that it did so.
