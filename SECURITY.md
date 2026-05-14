# Security Policy

## Supported versions

Fieldgrade is currently distributed as a pilot/alpha product line.

| Version line | Status |
| --- | --- |
| `0.9.x` | Supported for pilot deployments and security fixes |
| `< 0.9.0` | Unsupported |

## Reporting a vulnerability

Please do **not** open public GitHub issues for suspected vulnerabilities.

- Open a private security report through GitHub Security Advisories if available for this repository.
- If that path is unavailable, open a minimal public issue requesting a secure contact path, but do **not** include exploit details, secrets, or customer data in the issue body.
- Include affected version, deployment shape, reproduction steps, impact, and any logs or screenshots needed to reproduce safely.

## Response targets

- Initial acknowledgement: within **3 business days**
- Triage decision: within **7 business days**
- Status update cadence for accepted reports: at least every **7 business days**

These are targets for a small pilot-stage team, not contractual SLAs.

## Coordinated disclosure

- Please avoid public disclosure until a fix or mitigation is available.
- We will coordinate release notes and remediation guidance once a fix is ready.
- Reports made in good faith and without data exfiltration or destructive testing are treated as responsible disclosure.

## Secrets and credentials

- Never commit `.env` files, API tokens, private keys, or customer evidence to the repository.
- Rotate any exposed token immediately and assume compromise until proven otherwise.
- Treat demo tokens as disposable and distinct from production credentials.

## Deployment hardening summary

- Set `FG_API_TOKEN` for all non-trivial deployments.
- Do not expose port `8787` directly on the public internet for production use.
- Use `compose.production.yaml` with TLS termination in front of the app.
- Restrict `FG_FORWARDED_ALLOW_IPS` to trusted proxy/network ranges rather than `*`.
- Persist runtime and artifact volumes, and test backup/restore before onboarding pilot data.
- Keep host OS, Docker, Python, and dependency updates current as part of release hygiene.

## Responsible AI-use and compliance caveats

- Fieldgrade supports evidence governance, review, and audit preparation.
- Fieldgrade is **not** certified compliance software and does not itself certify legal or regulatory compliance.
- Fieldgrade does **not** replace qualified auditors, QA managers, regulators, or responsible persons.
- AI-assisted outputs must remain reviewable, attributable, and subject to explicit human approval.

## Data handling and retention caveat

- Fieldgrade is designed for local-first or customer-controlled deployment.
- Operators remain responsible for retention periods, deletion policy, backup handling, and any third-party AI endpoint usage they configure.
- Review [`DATA_HANDLING.md`](DATA_HANDLING.md) before sharing customer or regulated evidence.
