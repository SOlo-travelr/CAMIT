# Threat model

Scope: single-site pilot with RTSP cameras, an API service, a worker, and
object/metadata storage.

## Assets

- Camera streams and credentials.
- Incident evidence (clips/snapshots) — sensitive personal data.
- Policies and thresholds (safety-critical configuration).
- Operator accounts.

## Trust boundaries

1. Camera → worker (RTSP). Assume network is semi-trusted; use VLAN isolation.
2. Operator → API (REST/WS). Authenticated, authorised, audited.
3. LLM provider (optional, egress). Untrusted output.

## Key risks & mitigations

| Risk | Mitigation |
| --- | --- |
| **Prompt injection** via NL policy text | LLM output is *only* JSON, always run through `validate_policy`; no generated code is executed; unknown cameras/zones/classes are rejected. |
| Malicious/oversized policy | Strict Pydantic schema; enumerated conditions/events; non-negative constraints. |
| RTSP credential leakage | Store camera URIs as secrets; never log full URIs. |
| Evidence tampering | Write-once object keys per incident id; integrity via storage checksums. |
| DoS via camera flood | Frame sampling + bounded ring buffer + per-camera watchdog. |
| Silent failure hiding incidents | No blanket exception swallowing; camera health surfaced via watchdog + `/health`; failures logged. |
| Supply chain | Pinned dependency ranges; heavy/optional ML deps isolated behind extras. |

## Explicit non-goals (reduce blast radius)

No autonomous emergency dispatch, no online model retraining, no biometric
identity. Metric-distance rules are disabled until calibration is validated,
preventing unsafe collision alerts from uncalibrated cameras.
