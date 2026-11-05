# Authentication & Authorization Architecture Review
## Sprint 23 Enterprise Security Verification

### 1. Authentication Layers

The platform implements a multi-tier defense-in-depth authentication framework:

1. **Server-Managed Session Layer (`SessionManager`):**
   - Sessions are initiated via `POST /api/v1/product/session/login` by presenting a valid operator token.
   - The server issues a cryptographically secure 256-bit random session identifier (`cbe_session_id`).
   - Session identifiers are transmitted in `Set-Cookie` headers with `HttpOnly; SameSite=Strict; Max-Age=3600`.
   - Browser client scripts cannot read, modify, or leak `cbe_session_id` via JavaScript (`document.cookie` is protected).

2. **CSRF Mitigation:**
   - Every authenticated session generates a unique CSRF token (`cbe_csrf_token`).
   - All state-mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`) must supply this token in the `X-CSRF-Token` header.
   - Cross-origin requests (`Sec-Fetch-Site: cross-site`) or mismatched CSRF tokens are rejected with `HTTP 403 Forbidden`.

3. **Role & Credential Separation (`CredentialManager`):**
   - `CBE_OPERATOR_TOKEN`: Used strictly for operator session authentication.
   - `CBE_EVIDENCE_SIGNING_KEY`: Used strictly for HMAC-SHA256 evidence bundle signatures.
   - `CBE_ADMIN_DIAGNOSTICS_TOKEN`: Required for privileged operational diagnostics (`/diagnostics`).
   - `CBE_TEST_OPERATOR_TOKEN`: Permitted only in local test environments; explicitly rejected in staging/production.

---

### 2. Revocation Verification

- Tokens and signing keys can be revoked immediately via SHA-256 fingerprint registration.
- Revoked keys return explicit verdicts: `REVOKED_SIGNING_KEY` during evidence verification and `TOKEN_REVOKED` during authentication.
