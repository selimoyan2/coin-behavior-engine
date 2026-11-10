# Cryptographic Verification Contract
```json
{
  "canonicalization": "RFC 8785 (audited standard library package)",
  "signature_algorithm": "HMAC-SHA256",
  "signature_format": "hmac-sha256:<key_id>:<64_hex_digits>",
  "bound_claim_fields": [
    "completeness_assertion",
    "dataset_id",
    "issuer",
    "key_id",
    "observation_count",
    "observation_end_utc",
    "observation_start_utc",
    "record_id",
    "schema_version",
    "source_artifact_sha256",
    "verification_method",
    "window_cadence"
  ],
  "verification_steps": [
    "1. Presence & dictionary format check",
    "2. Rejection of embedded keys or untrusted writable paths",
    "3. Cryptographic signature presence check",
    "4. Schema version validation against supported list",
    "5. Issuer authority check against TRUSTED_ISSUERS",
    "6. Completeness assertion check and missing observation audit",
    "7. Key revocation check via SigningKeyRegistry",
    "8. Context binding check (record_id, dataset_id, sha256, boundaries, cadence, count)",
    "9. Disk artifact hash check if source file exists on disk",
    "10. RFC-8785 canonical claim hashing and HMAC constant-time digest comparison",
    "11. Dynamic cache evaluation bound to (artifact_sha, attestation_sha, key_id, policy_ver, is_revoked)"
  ]
}
```