# Cryptographic Verification Contract

```json
{
  "canonicalization": "RFC 8785 (standard library / audited rfc8785 package)",
  "signature_algorithm": "HMAC-SHA256",
  "signature_format": "hmac-sha256:<key_id>:<64_hex_digits>",
  "bound_claim_fields": [
    "completeness_assertion",
    "dataset_id",
    "expires_at_utc",
    "has_missing_data",
    "is_superseded",
    "issuer",
    "key_id",
    "missing_observations",
    "observation_count",
    "observation_end_utc",
    "observation_start_utc",
    "record_id",
    "schema_version",
    "source_artifact_sha256",
    "verification_method",
    "window_cadence"
  ],
  "verification_pipeline": [
    "1. Presence & dictionary format check",
    "2. Rejection of embedded keys or untrusted writable paths",
    "3. Cryptographic signature presence check & signature_digest calculation",
    "4. Schema version validation against supported list",
    "5. Issuer authority check against TRUSTED_ISSUERS",
    "6. Mandatory claims presence check (fail closed with MANDATORY_CLAIM_MISSING)",
    "7. Completeness assertion check & conflicting metadata audit (INCONSISTENT_COMPLETENESS_METADATA)",
    "8. Expiry check (ATTESTATION_EXPIRED) & Superseded check (ATTESTATION_SUPERSEDED)",
    "9. Key ID & revocation check via SigningKeyRegistry (REVOKED_SIGNING_KEY)",
    "10. Context binding check (record_id, dataset_id, boundaries, cadence, count, claimed sha)",
    "11. Fail-closed physical source artifact verification (path traversal, system dirs, symlinks, existence, size, disk SHA-256)",
    "12. RFC-8785 canonical claim hashing and HMAC signature evaluation",
    "13. Signature-bound cache query & storage bound to (artifact_sha, claims_sha, sig_digest, key_id, policy_ver, is_revoked)"
  ]
}
```
