# 04 — Cross-Experiment Comparison Intelligence Specification (Module 27.3)

- **File:** `src/coin_behavior_engine/product/cross_experiment_comparison.py`
- **Primary Class:** `CrossExperimentComparisonEngine`

## 8-Point Comparability Gate
1. `metric_definitions_match`
2. `units_match`
3. `methodologies_compatible`
4. `observation_periods_identified`
5. `dataset_overlap_quantified`
6. `model_versions_compatible`
7. `statistical_procedures_comparable`
8. `evidence_provenance_established`

## Canonical Verdicts & Scientific Safeguards
- Verdicts: `DIRECTLY_COMPARABLE`, `CONDITIONALLY_COMPARABLE`, `DESCRIPTIVE_ONLY`, `NOT_COMPARABLE`, `INSUFFICIENT_EVIDENCE`.
- Rejects raw p-value ranking (`RAW_P_VALUE_RANKING_PROHIBITED`), overlapping-window independence claims (`OVERLAPPING_SAMPLES_CANNOT_CLAIM_INDEPENDENCE`), and zero-imputation of missing metrics (`ZERO_IMPUTATION_OF_MISSING_METRICS_PROHIBITED`).
