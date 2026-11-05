# Structured Logging Security & Secret Redaction Review
## Sprint 23 Security Engineering Audit

### 1. Secret Redaction Architecture

All application loggers attach `SecretRedactingFilter` to prevent accidental credential leakage in container logs:

- **Redacted Tokens:**
  - `CBE_OPERATOR_TOKEN` -> `***REDACTED_OPERATOR_TOKEN***`
  - `CBE_EVIDENCE_SIGNING_KEY` -> `***REDACTED_SIGNING_KEY***`
  - `CBE_ADMIN_DIAGNOSTICS_TOKEN` -> `***REDACTED_ADMIN_TOKEN***`
  - Pattern matches for Bearer tokens, passwords, secrets, private keys.

### 2. In-Memory Ring Buffer

- Maintains the last 200 non-sensitive operational events in memory for `GET /api/v1/product/diagnostics`.
- Ring buffer entries are strictly stripped of query parameters, authorization headers, and cookie data.
- Verified in Scenario 32 of Playwright Acceptance: 0 leaked secrets across all browser console logs.
