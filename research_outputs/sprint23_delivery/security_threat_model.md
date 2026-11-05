# Sprint 23 Security Threat Model
## STRIDE Threat Analysis & Defensive Architecture

### 1. Scope & Trust Boundaries

The Coin Behavior Engine research platform operates across three distinct trust boundaries:
1. **Public/Untrusted Client Space:** Browser user agent, client JavaScript, external HTTP callers.
2. **Server Execution Boundary:** Python Web Server (`coin_behavior_engine.web.server`), API service layer, session manager, resource governor.
3. **Persistent Storage Boundary:** Host filesystem, Docker persistent volume mounts (`/app/data/prospective`), lock directory (`/tmp/cbe_locks`).

---

### 2. STRIDE Threat Assessment & Mitigations

| STRIDE Category | Specific Threat | Likelihood | Impact | Implemented Mitigation | Residual Risk |
|---|---|---|---|---|---|
| **Spoofing** | Attacker impersonates operator via stolen token | Low | High | HttpOnly, SameSite=Strict cookies; constant-time comparison; token rotation & revocation registry. | Minimal |
| **Tampering** | Modification of saved reports or evidence bundles | Medium | Critical | Deterministic SHA-256 package checksum; HMAC-SHA256 signature verification; atomic writes with advisory locking. | Zero |
| **Repudiation** | Operator denies generating or publishing research reports | Low | Medium | Structured audit logging with correlation IDs; signed evidence bundles linked to active key IDs. | Zero |
| **Information Disclosure** | Credentials leaked in logs, error traces, or client storage | High | High | Regex secret redaction filter; zero tokens stored in localStorage/sessionStorage; masked UI tokens. | Zero |
| **Denial of Service** | Resource exhaustion via concurrent heavy calculations or huge payloads | High | High | Concurrency semaphores (research=2, pdf=2); 2MB payload ceiling; 5,000 candle budget; memory RSS monitor. | Controlled |
| **Elevation of Privilege** | Unauthenticated callers accessing administrative diagnostics | Medium | Medium | Strict role separation (`X-Admin-Token` vs `X-Operator-Token`); unprivileged access rejected with HTTP 401. | Zero |

---

### 3. Conclusion
The implemented security controls neutralize identified attack vectors without impacting retrospective historical research capabilities.
