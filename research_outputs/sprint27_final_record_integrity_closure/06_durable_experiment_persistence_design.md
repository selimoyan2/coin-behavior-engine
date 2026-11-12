# 06 — Durable Experiment Persistence & Recovery Design (`P0-3`)

- **Primary Module:** `src/coin_behavior_engine/product/experiment_timeline_registry.py`
- **Implementation Commit SHA:** `6dd263fab00d6362d7196abf5112d847d84789b2`

## Complete 11-Step Persistence Hydration Contract

1. Validate persisted schema version (`PERSISTENCE_SCHEMA_VERSION == "1.0"`).
2. Validate all 20 required experiment fields (`REQUIRED_EXPERIMENT_FIELDS`).
3. Validate execution attempt structures (`REQUIRED_ATTEMPT_FIELDS`).
4. Validate timeline event structures (`REQUIRED_TIMELINE_EVENT_FIELDS`).
5. Verify internal SHA-256 tamper-detection hash chain (`verify_timeline_chain_integrity()`), chronological ordering, and duplicate event IDs.
6. Validate experiment-to-event references (`MISSING_EXPERIMENT_REFERENCE_IN_TIMELINE`).
7. Fail closed (`ExperimentRegistrySecurityError`) on any corruption or inconsistency.
8. Restore verified experiments into `self._experiments`.
9. Restore verified timeline events into `self._timeline`.
10. Preserve deterministic experiment IDs, attempt IDs, and chronological ordering.
11. Prevent duplicate seed events on restart and clean up leftover `.tmp` files from interrupted writes under file-backed `MultiProcessLock`.
