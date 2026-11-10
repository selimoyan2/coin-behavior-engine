# Dataset Artifact Binding Verification

```json
{
  "verification_timestamp_utc": "2026-11-10T11:30:00Z",
  "bindings_enforced": [
    {
      "field": "record_id",
      "enforcement": "Strict equality with record.id",
      "failure_code": "REPLAY_ATTACK_DETECTED"
    },
    {
      "field": "dataset_id",
      "enforcement": "Strict equality with record.dataset_id",
      "failure_code": "DATASET_ID_MISMATCH"
    },
    {
      "field": "source_artifact_sha256",
      "enforcement": "Strict equality with record.source_artifact_sha256",
      "failure_code": "ARTIFACT_HASH_MISMATCH"
    },
    {
      "field": "disk_file_integrity",
      "enforcement": "SHA-256 of physical disk file matches signed hash",
      "failure_code": "SOURCE_ARTIFACT_HASH_MISMATCH"
    },
    {
      "field": "observation_boundaries",
      "enforcement": "Start & end match record observation boundaries",
      "failure_code": "OBSERVATION_WINDOW_MISMATCH"
    },
    {
      "field": "window_cadence",
      "enforcement": "Cadence matches record sampling cadence",
      "failure_code": "CADENCE_MISMATCH"
    },
    {
      "field": "observation_count",
      "enforcement": "Observation count equals (end - start) // cadence",
      "failure_code": "OBSERVATION_COUNT_MISMATCH"
    },
    {
      "field": "missing_observations",
      "enforcement": "Signed claim must be 0 for continuous complete assertion",
      "failure_code": "INCONSISTENT_COMPLETENESS_METADATA"
    },
    {
      "field": "has_missing_data",
      "enforcement": "Signed claim must be False for continuous complete assertion",
      "failure_code": "INCONSISTENT_COMPLETENESS_METADATA"
    }
  ],
  "status": "VERIFIED_FAIL_CLOSED"
}
```
