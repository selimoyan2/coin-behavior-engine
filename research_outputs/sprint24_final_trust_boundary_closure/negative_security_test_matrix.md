# Negative Security Test Matrix (25 Scenarios)
```json
{
  "test_suite": "tests/test_sprint_product_acceleration_24_trust_boundary_closure.py",
  "total_scenarios": 25,
  "scenarios_passed": 25,
  "scenarios": [
    {
      "id": 1,
      "name": "Self-declared VERIFIED without signature",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "SIGNATURE_EMPTY_OR_INVALID",
      "result": "PASS"
    },
    {
      "id": 2,
      "name": "Self-declared verified_continuous_series=true without trusted authority",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "UNKNOWN_ISSUER",
      "result": "PASS"
    },
    {
      "id": 3,
      "name": "Forged signature",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "SIGNATURE_VERIFICATION_FAILED",
      "result": "PASS"
    },
    {
      "id": 4,
      "name": "Modified signed payload",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "SIGNATURE_VERIFICATION_FAILED",
      "result": "PASS"
    },
    {
      "id": 5,
      "name": "Unknown issuer",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "UNKNOWN_ISSUER",
      "result": "PASS"
    },
    {
      "id": 6,
      "name": "Revoked key",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "REVOKED_SIGNING_KEY",
      "result": "PASS"
    },
    {
      "id": 7,
      "name": "Wrong dataset identifier",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "DATASET_ID_MISMATCH",
      "result": "PASS"
    },
    {
      "id": 8,
      "name": "Wrong research record identifier",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "REPLAY_ATTACK_DETECTED",
      "result": "PASS"
    },
    {
      "id": 9,
      "name": "Wrong source SHA-256",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "ARTIFACT_HASH_MISMATCH",
      "result": "PASS"
    },
    {
      "id": 10,
      "name": "Wrong observation start/end",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "OBSERVATION_WINDOW_MISMATCH",
      "result": "PASS"
    },
    {
      "id": 11,
      "name": "Wrong cadence",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "CADENCE_MISMATCH",
      "result": "PASS"
    },
    {
      "id": 12,
      "name": "Wrong observation count",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "OBSERVATION_COUNT_MISMATCH",
      "result": "PASS"
    },
    {
      "id": 13,
      "name": "Unsupported schema version",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "UNSUPPORTED_SCHEMA_VERSION",
      "result": "PASS"
    },
    {
      "id": 14,
      "name": "Replay against another research record",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "REPLAY_ATTACK_DETECTED",
      "result": "PASS"
    },
    {
      "id": 15,
      "name": "Missing trusted verification key",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "MISSING_TRUSTED_VERIFICATION_KEY",
      "result": "PASS"
    },
    {
      "id": 16,
      "name": "Signing key stored in an untrusted location",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "UNTRUSTED_KEY_LOCATION",
      "result": "PASS"
    },
    {
      "id": 17,
      "name": "Valid explicit timestamp intersection without attestation",
      "rejection_code": null,
      "overlap_valid": true,
      "result": "PASS"
    },
    {
      "id": 18,
      "name": "Two valid authenticated continuous series",
      "rejection_code": null,
      "overlap_valid": true,
      "result": "PASS"
    },
    {
      "id": 19,
      "name": "Mixed timestamp and attested-series intersection",
      "rejection_code": null,
      "overlap_valid": true,
      "result": "PASS"
    },
    {
      "id": 20,
      "name": "Misaligned sampling grids",
      "rejection_code": "DISJOINT_OBSERVATION_WINDOWS",
      "overlap_valid": false,
      "result": "PASS"
    },
    {
      "id": 21,
      "name": "Exactly 99 shared observations",
      "rejection_code": "INSUFFICIENT_OVERLAP",
      "overlap_valid": false,
      "result": "PASS"
    },
    {
      "id": 22,
      "name": "Exactly 100 shared observations",
      "rejection_code": null,
      "overlap_valid": true,
      "result": "PASS"
    },
    {
      "id": 23,
      "name": "Duplicate timestamps",
      "rejection_code": "DUPLICATED_OBSERVATIONS_DETECTED",
      "overlap_valid": false,
      "result": "PASS"
    },
    {
      "id": 24,
      "name": "Missing observations despite a claimed complete series",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "MISSING_OBSERVATIONS_DETECTED",
      "result": "PASS"
    },
    {
      "id": 25,
      "name": "Attestation becoming invalid after source artifact modification",
      "rejection_code": "ATTESTATION_VERIFICATION_FAILED",
      "subcode": "ARTIFACT_TAMPERED",
      "result": "PASS"
    }
  ]
}
```