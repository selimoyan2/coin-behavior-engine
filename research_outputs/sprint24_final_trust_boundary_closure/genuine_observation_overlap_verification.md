# Genuine Observation Overlap Verification
```json
{
  "methodology": "Mathematical Set Intersection of Canonical ISO-8601 UTC Timestamps",
  "paths_supported": {
    "Path_A_Explicit_Timestamps": {
      "validation": "Normalization to YYYY-MM-DDTHH:MM:SSZ, duplicate rejection, invalid format rejection",
      "set_operation": "S_1 \u2229 S_2",
      "attestation_required": false
    },
    "Path_B_Authenticated_Continuous_Series": {
      "validation": "Cryptographic RFC-8785 attestation verification against record context",
      "grid_generation": "Discrete timestamps generated at step intervals from start to end",
      "set_operation": "S_1 \u2229 S_2",
      "misaligned_grid_handling": "Phase difference yields empty set, fails closed with DISJOINT_OBSERVATION_WINDOWS"
    },
    "Mixed_Path": {
      "validation": "Intersection between explicit timestamps and authenticated continuous series grid",
      "duration_division_prohibited": true
    }
  },
  "floor_enforcement": "n_shared >= 100",
  "status": "VERIFIED"
}
```