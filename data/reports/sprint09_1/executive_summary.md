# Coin Behavior Engine — Sprint 09.1 Executive Summary
**Sprint:** 09.1 — Frozen Model Artifact Recovery & Runtime Parity Audit  
**Date:** 2026-10-09 15:06:44 UTC  
**Production Model:** CBE-0.7.0 (Strictly Frozen)  
**Candidate Model:** CBE-0.8.0 (Not yet implemented)  

---

## 1. Verified Facts
1. **Zero Serialized Models:** No serialized Ridge models, scalers, or logistic calibrators exist on disk.
2. **Training Discarded in Memory:** Sprint 07 research fitted models in RAM, exported summary CSVs, and exited without saving weights.
3. **Empty Runtime Dictionary:** In prospective production, `self.engine.vol_models` is `{}`; the worker bypassed this via `is_fitted = True`.
4. **Dimension Mismatch:** Training data had `volume_zscore_24h` while engine declared `volume_zscore`, causing training to fit 2 features while runtime generates 3 features (`3 != 2`).
5. **17x Target Scale Incompatibility:** Historical targets were unscaled 5m return standard deviation (~0.00112); live outcomes and features are sqrt(288)-scaled (~0.01404).
6. **Data Availability:** All 4 historical parquet datasets exist locally on disk and allow 100% deterministic offline reproduction.

---

## 2. Inferences & Invariants
- The prospective system's reported performance (MAE 0.00560, Pearson 0.5410 at 1h) was generated entirely by the simple trailing realized volatility persistence fallback, not by machine learning inference.
- Loading the historical Sprint 07 model into production without reconciling the 17x target scaling gap would cause severe prediction errors (~0.0011 predicted vs ~0.0140 realized).

---

## 3. Scientific Decision Gates
- **GATES PASSED:** 3 / 9 (Gates F, G, I: Causal Timestamps, Offline Reproducibility, Future Architecture Design).
- **GATES BLOCKED / FAILED:** 6 / 9 (Gates A, B, C, D, E, H: Artifacts Missing, Provenance Unverified, Schema Mismatch, Scaler Missing, Target Scale Mismatch, SPOT_ONLY Incompatible).
- **Overall Verdict:** **BLOCKED FOR RUNTIME DEPLOYMENT.**

---

## 4. Next Step Recommendation
Maintain CBE-0.7.0 in strict freeze. In Sprint 09.2 (offline research):
1. Fix feature vector mapping (`volume_zscore_24h` -> `volume_zscore`).
2. Harmonize target scaling with sqrt(288).
3. Perform offline training and export an immutable bundle (`cbe_model_bundle_v080.json`).
4. Validate offline on prospective replay data before any live activation.
