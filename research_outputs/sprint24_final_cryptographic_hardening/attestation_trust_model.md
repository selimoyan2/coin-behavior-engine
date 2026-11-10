# Attestation Trust Model

```json
{
  "trust_boundary_version": "2026.2",
  "threat_model": {
    "threats_mitigated": [
      "Cache poisoning across signature mutations",
      "Missing/unreadable source artifact bypass",
      "Path traversal and system file disclosure via source artifact",
      "Unauthenticated tampering of missing_observations or has_missing_data",
      "Time-of-check to time-of-use (TOCTOU) file replacement after caching",
      "Stale or revoked signing key usage",
      "Attestation replay across datasets or research records"
    ],
    "fail_closed_guarantee": true
  },
  "key_hierarchy": {
    "registry": "SigningKeyRegistry (thread-safe singleton)",
    "allowed_key_sources": [
      "Environment secrets (CBE_EVIDENCE_SIGNING_KEY)",
      "Authoritative vault"
    ],
    "untrusted_key_locations": [
      "/tmp",
      "data/",
      "caller payload"
    ],
    "revocation_enforcement": "Immediate fail-closed check on key_id and cache invalidation"
  },
  "supported_schemas": [
    "CBE-ATTESTATION-2.0.0",
    "CBE-ATTESTATION-1.0.0",
    "CBE-OBSERVATION-ATTESTATION-1.0.0",
    "1.0.0"
  ]
}
```
