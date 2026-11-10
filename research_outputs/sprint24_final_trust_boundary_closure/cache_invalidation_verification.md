# Cache Invalidation Verification
```json
{
  "cache_key_binding": [
    "artifact_digest (SHA-256)",
    "attestation_digest (SHA-256)",
    "key_id",
    "trust_policy_version",
    "is_revoked (boolean)"
  ],
  "invalidation_triggers": [
    "Source artifact modification on disk or metadata change",
    "Attestation claim modification or tampering",
    "Key revocation in SigningKeyRegistry",
    "Trust policy version increment"
  ],
  "test_verification": "test_cache_hit_and_invalidation_on_revocation PASSED",
  "status": "VERIFIED_HEALTHY"
}
```