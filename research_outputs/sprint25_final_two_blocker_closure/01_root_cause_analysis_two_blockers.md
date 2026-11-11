# CBE — SPRINT 25 FINAL TWO-BLOCKER CLOSURE: ROOT-CAUSE ANALYSIS

- **Repository:** `selimoyan2/coin-behavior-engine`
- **Branch:** `main`
- **Verified Starting HEAD:** `6233c21839b93a430023a2e3dcd5a14b9a193710`
- **Implementation Commit SHA:** `e69d5d1204f8bc61c969c2c1de77fdf4b048f727`
- **Canonical Scientific Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)
- **Governance Decision:** `TECHNICAL_NO_GO`

---

## 1. Blocker 1 — Dataset Provenance Trust Boundary (`scientific_readiness.py` & Cross-Module)

### Confirmed Defect
In `src/coin_behavior_engine/product/scientific_readiness.py`, the `DATASET_PROVENANCE` readiness dimension previously granted `DimensionStatus.VERIFIED` using directory-existence and file-existence heuristics:
1. `Path("data/binance_spot_multiyear/1h/").exists()` for `BTCUSDT-SPOT-1H-2022-2026`
2. `Path("data/normalized/binance_pilot_2022_01/").exists()` for `BTCUSDT-SPOT-15M-2024-Q1`
3. `Path("data/historical/futures/raw/").exists()` for `BTCUSDT-PERP-FUNDING-2022-2026`
4. `Path("research_outputs/sprint23_delivery/").exists()` for `CBE-RUNTIME-VOLUME-MOUNTINFO`
5. Bare file check `imp.exists() and imp.is_file()` on `dataset_provenance_ref`
6. Calling `ObservationCompletenessAttestationVerifier.verify_attestation(..., enforce_source_file_integrity=False)` in both `scientific_readiness.py` and `evidence_gap_analyzer.py`, which bypassed physical source artifact SHA-256 verification.

### Root Cause
Existence of a local directory or JSON file was treated as sufficient proof of dataset provenance, and source file integrity checking was disabled during attestation verification in readiness/gap evaluation.

### Corrective Fix Implemented
- Implemented `ScientificReadinessEvaluator.verify_dataset_provenance(record)` and `ScientificReadinessEvaluator.create_signed_intake_manifest(...)`.
- Removed all directory-existence and bare file-existence shortcuts.
- Enforced `enforce_source_file_integrity=True` across all attestation verification calls in `scientific_readiness.py` and `evidence_gap_analyzer.py`.
- A dataset now reaches `VERIFIED` (`INTEGRITY_VERIFIED` in Evidence Graph) **only** when backed by:
  1. A cryptographically valid, non-expired, non-revoked attestation verified via `ObservationCompletenessAttestationVerifier.verify_attestation(record, att, use_cache=True, enforce_source_file_integrity=True)` with exact `dataset_id` binding and physical `source_artifact` SHA-256 verification, OR
  2. A cryptographically signed intake manifest (`intake_manifest` / `intake_manifest_path`) issued by a trusted issuer (`TRUSTED_ISSUERS`), signed by an active key in `signing_key_registry`, bound to `dataset_id` and `record_id`, with verified physical existence and exact SHA-256 match for all listed artifacts and `record.source_artifact`.
- Synchronized identical dataset provenance semantics across all 6 modules: `scientific_readiness.py`, `evidence_graph.py`, `evidence_gap_analyzer.py`, `research_priority_engine.py`, `research_decision_reports.py`, and `research_intelligence_workspace.py`.

---

## 2. Blocker 2 — Independent Reference Validation in `ReproducibilityLabEngine` (`reproducibility_lab.py`)

### Confirmed Defect
In `src/coin_behavior_engine/product/reproducibility_lab.py`, reference outputs could be populated from newly computed values when reference fields were absent or when caller overrides were provided:
1. `PROC_PARKINSON_VOLATILITY`: `ref_val = float(raw_json.get("parkinson_volatility", round(computed_annualized, 4)))`
2. `PROC_FUNDING_RATE_SUMMARY`: `be.get("observed_median_funding_bps", median_bps)`, `be.get("observed_min_funding_bps", min_bps)`, `be.get("observed_max_funding_bps", max_bps)`, and fallback to `mean_bps` / `neg_count`
3. `PROC_REGIME_STABILITY_EVAL`: `raw_json.get("holdout_metrics", {}).get("direction_match_rate", match_rate)` and `audit.get("direct_transition_rate_pct", computed_rate_pct)` plus arithmetic division of stored summary counts instead of raw candle recomputation
4. `PROC_DTW_PATTERN_DISTANCE`: `raw_json.get("dtw_distance", computed_dtw)` and `cand.get("composite_distance", computed_comp_dist)`
5. `PROC_STORAGE_VERIFICATION`: `neg_tests.get("total_negative_tests", recomputed_count)` and returning `OUTPUTS_MATCHED` from historical report inspection alone without raw `mountinfo_content` re-execution.

### Root Cause
Default arguments in `.get(key, computed_value)` and unauthenticated `override_reference` dictionaries allowed self-comparison and caller-injected reference outputs to produce `OUTPUTS_MATCHED`.

### Corrective Fix Implemented
- Removed every computed-to-reference fallback across all 5 allowlisted procedures.
- Added `ReferenceBlockedReason` (`MISSING_TRUSTED_REFERENCE`, `UNVERIFIED_REFERENCE_PROVENANCE`, `MISSING_RAW_OBSERVATIONS`, `HISTORICAL_REPORT_INSPECTION_ONLY`, `SOURCE_ARTIFACT_INTEGRITY_FAILED`) and `ReproducibilityLabEngine.validate_reference_provenance(...)` + `create_signed_reference_provenance(...)`.
- Enforced strict reference provenance gates before and during procedure execution:
  - Reference must predate the reproduction attempt (`created_during_reproduction_attempt` is rejected; `recorded_at_utc < start_time_utc`).
  - Reference must come from a verified entry in `TRUSTED_ARTIFACT_REGISTRY` (with physical SHA-256 verification), a valid cryptographic attestation, or a signed `reference_provenance` envelope (or explicit `trusted_fixture_context=True` in isolated unit tests).
  - Caller-supplied `override_reference` without verified provenance or `trusted_fixture_context=True` is rejected with `REPRODUCTION_BLOCKED` (`UNVERIFIED_REFERENCE_PROVENANCE`).
  - `PROC_REGIME_STABILITY_EVAL` recomputes regime transitions directly from the 8,736 raw 15m candles in `data/historical/historical_binance_btcusdt_15m_q1_2024.parquet` via `RegimeClassificationAuditor(candles).audit_trend_transitions()`.
  - `PROC_STORAGE_VERIFICATION` returns `REPRODUCTION_BLOCKED` (`HISTORICAL_REPORT_INSPECTION_ONLY`, `storage_test_reexecuted=False`) when only the historical JSON report is present without raw `mountinfo_content` input.

---

## 3. Historical Commit SHA Correction
- A previous Sprint 25 report textually cited `6233c21a4f0037a5015b3c58cfa9d3000b0f4fdc`.
- The actual verified commit SHA in Git and GitHub (`origin/main`) for that milestone is `6233c21839b93a430023a2e3dcd5a14b9a193710`.
- Git history was not rewritten; this correction is explicitly documented across the final Sprint 25 delivery artifacts.
