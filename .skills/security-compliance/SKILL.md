---
name: security-compliance
description: "Security and compliance workflow for designing defense-in-depth controls, performing threat modeling and risk assessments, and mapping mitigations to frameworks (SOC2/ISO27001/GDPR/HIPAA). Use when reviewing security posture, shipping sensitive features, preparing compliance evidence, or running a lightweight secrets scan."
---

# Security & Compliance

Build real security, not checkbox security.

## Quick Start
1) Scope the system and data:
   - What data types exist (PII/PHI/payment/secrets)? Where is it stored and transmitted?
   - Trust boundaries (browser ↔ edge ↔ API ↔ DB ↔ 3rd parties)
2) Threat model (lightweight): list top 5 abuse cases + mitigations.
3) Controls: pick practical controls (authN/authZ, encryption, logging, rate limits, backups, key mgmt).
4) Evidence: document decisions and “how we know it works” (configs, screenshots, logs, tests).

## Output artifacts (default)
- 5-item threat model table (abuse case → impact → mitigation).
- Control checklist mapped to the system’s trust boundaries.
- Evidence list: concrete proofs (configs, logs, tests) with where to find them.

## Secret scan (safe by default)

The bundled scanner never exposes credentials:

- `keys/`, `.git/`, `.env` and `.env.*` are always excluded (no opt-out for `keys/`).
- Findings report only file, line and rule id — never the matched value.
  This applies to both stdout and JSON output.
- An explicit `keys/` or `keys/<file>` target is refused (exit code 2)
  before any file is opened.
- Detects possible `mongodb://` / `mongodb+srv://` URIs by rule
  (`mongodb-uri`), reporting only their existence, never the URI.

```bash
python .skills/security-compliance/scripts/secret_scan.py <scoped-path> --json
```

Run it only on scoped paths relevant to the change under review, never on
`keys/`. Verify the safe behavior with:

```bash
python .skills/security-compliance/scripts/test_secret_scan.py
```

## References
- Threat model template: `references/threat-model.md`
- Control checklist: `references/control-checklist.md`
