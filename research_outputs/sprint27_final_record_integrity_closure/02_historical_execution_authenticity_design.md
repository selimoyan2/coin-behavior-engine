# 02 — Historical Execution Authenticity Design (`P0-1`)

- **Primary Module:** `src/coin_behavior_engine/product/experiment_timeline_registry.py`
- **Implementation Commit SHA:** `6dd263fab00d6362d7196abf5112d847d84789b2`

## Three Non-Interchangeable Record Origins

1. `CATALOG_PROJECTION` — Discovered in the canonical catalog; `execution_started_at=None`, `execution_completed_at=None`, `output_artifact_ids=[]`, `result_digest=None`, `execution_attempts=[]`, `reproducibility_verdict="REPRODUCTION_NOT_ESTABLISHED"` (or `"REPRODUCTION_BLOCKED"` if quarantined).
2. `VERIFIED_HISTORICAL_EXECUTION` — Promoted only via `promote_to_verified_historical_execution()` when backed by an authentic execution log artifact on disk with verified SHA-256, start/completion timestamps, and output artifact SHA-256.
3. `OFFLINE_EXPERIMENT_EXECUTION` — Newly executed offline experiment registered with verified execution log and authentic artifact digest.

## Explicit Lifecycle States Supported

- `CATALOG_DISCOVERED`
- `HISTORICAL_EXECUTION_UNVERIFIED`
- `EXECUTION_EVIDENCE_AVAILABLE`
- `EXECUTION_EVIDENCE_VERIFIED`
- `REPRODUCTION_NOT_ESTABLISHED`
- Plus the 12 execution lifecycle states (`REGISTERED` through `BLOCKED`).
