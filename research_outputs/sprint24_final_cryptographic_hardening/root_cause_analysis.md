# CBE SPRINT 24 FINAL CRYPTOGRAPHIC HARDENING — ROOT CAUSE ANALYSIS

## 1. Vulnerability Description
Independent source code review identified three interrelated cryptographic and trust-boundary defects in `ObservationCompletenessAttestationVerifier`:
1. **Verification Cache Identity Not Bound to Signature:**
   The cache key previously used `(artifact_digest, attestation_digest, key_id, trust_policy_version, is_revoked)`. Because the attestation digest computed the hash over the parsed claims dictionary without including the signature string itself, an attestation copy with an invalid or forged signature could hit a cache entry populated by a valid signature with matching claims.
2. **Source Artifact Integrity Check Skipped on Missing Disk Files:**
   Physical file hash checking was performed only if the source file already existed on disk (`if p.exists()`). If an attacker specified a nonexistent path or if the source artifact was deleted, the physical integrity gate was skipped without failing closed.
3. **Acceptance-Affecting Claims Omitted from Canonical RFC 8785 Digest:**
   Fields such as `missing_observations`, `has_missing_data`, `expires_at_utc`, and `is_superseded` were not all included in the canonical claim dictionary hashed for HMAC-SHA256 signature verification. Consequently, modifying these security-relevant flags after signing did not break the signature.

## 2. Root Cause Classification
- **CWE-345:** Insufficient Verification of Data Authenticity.
- **CWE-347:** Improper Verification of Cryptographic Signature.
- **CWE-524:** Information Exposure Through Caching / Cross-Signature Cache Poisoning.
- **CWE-22:** Path Traversal / Untrusted Source Path Reference.

## 3. Remediation Architecture
1. **Signature-Bound Thread-Safe Cache:**
   - Cache key is strictly bound to `(artifact_digest, claims_sha256, signature_digest, key_id, trust_policy_version, is_revoked)`.
   - Modifying the signature immediately causes a cache miss and undergoes full signature verification.
   - Cache reads re-verify physical source file presence, size, and modification timestamp (`st_mtime_ns`), immediately evicting if tampered or deleted.
   - Concurrency is protected via `threading.Lock()`.
2. **Fail-Closed Physical Source Artifact Integrity:**
   - Enforces strict path traversal rejection (`..`), disallowed system root blocking (`/etc`, `/bin`, `C:\Windows`), symlink escape checks, directory rejection, and resource-bounded reads (50 MB limit).
   - Missing or unreadable files fail closed with `SOURCE_ARTIFACT_MISSING` or `SOURCE_ARTIFACT_UNREADABLE`.
   - Actual disk SHA-256 is strictly verified against both record metadata and attestation claim (`SOURCE_ARTIFACT_HASH_MISMATCH`).
3. **Signed Security Claims:**
   - All 16 security claims (`missing_observations`, `has_missing_data`, `expires_at_utc`, `is_superseded`, `completeness_assertion`, `dataset_id`, `record_id`, `observation_count`, `observation_start_utc`, `observation_end_utc`, `window_cadence`, `schema_version`, `source_artifact_sha256`, `verification_method`, `issuer`, `key_id`) are signed into RFC 8785 canonical bytes.
   - Conflicting metadata triggers `INCONSISTENT_COMPLETENESS_METADATA`.
   - Expired attestations trigger `ATTESTATION_EXPIRED`.
   - Superseded attestations trigger `ATTESTATION_SUPERSEDED`.
