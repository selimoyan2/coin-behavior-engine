# 03 — Experiment Registry & Research Timeline Specification (Module 27.2)

- **File:** `src/coin_behavior_engine/product/experiment_timeline_registry.py`
- **Primary Class:** `ExperimentTimelineRegistryService`

## Required 20 Experiment Record Fields
`experiment_id`, `research_id`, `experiment_type`, `experiment_title`, `hypothesis_id`, `methodology_id`, `model_version` (`CBE-0.7.0`), `parameter_fingerprint`, `dataset_id`, `dataset_fingerprint`, `execution_mode` (`STRICTLY_OFFLINE_RESEARCH`), `execution_status`, `started_at`, `completed_at`, `duration_ms`, `input_artifact_ids`, `output_artifact_ids`, `result_digest`, `verification_status`, and `provenance_verdict`.

## 9 Lifecycle States & Trust Separation
`REGISTERED`, `INPUTS_VALIDATED`, `EXECUTING`, `EXECUTION_COMPLETED`, `EXECUTION_FAILED`, `EVIDENCE_VERIFIED`, `REPRODUCED`, `REPORT_GENERATED`, `BLOCKED`.
- `EXECUTION_COMPLETED` never implies `SCIENTIFICALLY_VERIFIED` (`UNVERIFIED_SCIENTIFIC_STATUS_PROMOTION_BLOCKED`).
- Append-only timeline events (`ExperimentTimelineEvent`) include `previous_event_digest` and `event_digest`, verified by `verify_timeline_hash_chain()`.
