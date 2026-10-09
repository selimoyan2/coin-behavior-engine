# Historical Training Pipeline Forensics
**Sprint:** 09.1  
**Date:** 2026-10-09 15:06:44 UTC  
**Model:** CBE-0.7.0 (Frozen)  

---

## 1. Pipeline Execution Trace
The scientific protocol in `src/coin_behavior_engine/market_state/research.py` was executed during Sprint 07 to produce research artifacts:

```
RAW PARQUET DATA
  ↓ (Load: event_features.parquet + features_with_outcomes_5m.parquet)
FEATURE ENGINEERING
  ↓ (Routed features, calendar indicators, interaction terms)
TIME-BASED SPLIT
  ↓ (Discovery: <2025-01-01, Validation: 2025, Holdout: 2026-01-01 to 2026-09-23)
SCALING
  ↓ (StandardScaler fitted in transient RAM on Discovery)
MODEL TRAINING
  ↓ (Ridge(alpha=100.0) fitted in transient RAM on Discovery)
VALIDATION EVALUATION
  ↓ (Predictions generated on Validation & Holdout for report metrics)
REPORT ARTIFACT GENERATION
  ↓ (29 summary CSV & JSON files written to data/reports/sprint07/)
ARTIFACT SERIALIZATION: [NEVER IMPLEMENTED / NEVER CALLED]
MODEL LOADING: [NEVER IMPLEMENTED / NEVER CALLED]
LIVE INFERENCE: [FELL BACK SILENTLY TO NAIVE PERSISTENCE]
```

---

## 2. Applicable Case Classification
- **PRIMARY CASE:** **CASE B (Trained but never serialized).**  
  The scikit-learn models (`Ridge`, `StandardScaler`, `LogisticRegression`) were instantiated and fitted in memory within `pipeline.run_pipeline()`, used to evaluate `r2_score` and `brier_score` for research CSV outputs, and then discarded when the Python process terminated.
- **SECONDARY CASE:** **CASE D (No loader implemented or called).**  
  In `src/coin_behavior_engine/prospective/worker.py`, lines 135–136 instantiate `self.engine = UnifiedMarketStateEngine()` and manually set `self.engine.is_fitted = True`. No loader function exists in the engine or worker to read weights from disk.
- **TERTIARY CASE:** **CASE E (Schema and shape mismatch).**  
  The training dataset contained `volume_zscore_24h` rather than `volume_zscore`, causing the Discovery fitting loop to train on 2 features, while `predict_bar` generated 3 features (`feats_arr.shape[1] == 3 != m.coef_.shape[0] == 2`).
- **QUATERNARY CASE:** **CASE F (Unavailable live features).**  
  Higher tier models U1–U5 require live derivatives, ETF, macro, and news streams that are disconnected in production (`SPOT_ONLY_U0`).
