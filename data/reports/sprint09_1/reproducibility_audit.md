# Historical Dataset & Model Reproducibility Audit
**Sprint:** 09.1  
**Date:** 2026-10-09 15:06:44 UTC  

---

## 1. Dataset Availability Verification
All historical training datasets exist locally on disk:
- `data/reports/sprint06/event_features.parquet` (53.7 MB, 602,240 bars: 2021-01-01 to 2026-09-23)
- `data/derived/features_with_outcomes_5m.parquet` (872.9 MB, contains `fwd_vol_*` forward outcomes)
- `data/reports/sprint05/etf_flow_features.parquet` (64.4 MB)
- `data/reports/sprint04/cross_asset_features.parquet` (5.8 MB)

---

## 2. Determinism of Model Retraining
- `Ridge(alpha=100.0)` has a closed-form analytical solution (X^T X + alpha I)^(-1) X^T y. There is zero stochasticity or random initialization.
- `StandardScaler` is strictly deterministic.
- Discovery partition boundary is exact: `datetime_open < '2025-01-01'`.
- Therefore, the historical models can be reproduced 100% deterministically offline.

---

## 3. Prerequisite Corrections for Retraining (Sprint 09.2+)
Before retraining candidate models for CBE-0.8.0:
1. Fix feature naming: Map `volume_zscore_24h` to `volume_zscore` so the feature vector has consistent length (3 features for U0).
2. Fix target scaling: Either train on sqrt(288)-scaled forward volatility or apply an explicit scaling layer at inference time.
3. Export model coefficients and scaler parameters to an immutable JSON/NumPy bundle.
