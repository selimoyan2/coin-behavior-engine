# Coin Behavior Engine — Sprint 09.2 Executive Summary
**Candidate Model:** CBE-0.8.0 (Offline Research Only)  
**Production Model:** CBE-0.7.0 (Strictly Frozen — Unchanged)  
**Date:** 2026-10-09T15:14:06.576942+00:00  

---

## 1. Research Objectives Achieved
1. **Reconstructed Model Bundle:** Serialized candidate Ridge models, scaler parameters, feature manifest, and target specifications into a deterministic, non-executable JSON bundle (`cbe_model_bundle_v080.json`).
2. **Resolved Feature Schema Mismatches:** Mapped `volume_zscore_24h` explicitly into the 3-feature `SPOT_ONLY_U0` manifest, eliminating the dimension mismatch ($3 \neq 2$) found in Sprint 09.1.
3. **Reconciled Target Scaling:** Unified target scaling under $\sqrt{288}$ daily-scale assumption ($16.97\times$), harmonizing model predictions directly with evaluation outcomes.
4. **Verified Numerical Parity:** Zero-dependency bundle inference reproduces `sklearn` Ridge predictions to machine precision (max discrepancy $< 10^{-12}$).

---

## 2. Baseline Challenge Results

### A. 1-Hour Horizon (1h) — PREDICTIVE ADVANTAGE CONFIRMED
- **Validation (2025):**
  - Ridge MAE: `0.006880` vs Persistence: `0.007086` (Lift: `+2.91%`)
  - Pearson: `0.6137` vs `0.6053`, $R^2$: `0.3616` vs `0.2107`.
- **Holdout (2026):**
  - Ridge MAE: `0.007068` vs Persistence: `0.007449` (Lift: `+5.11%`)
  - Pearson: `0.6407` vs `0.6162`, $R^2$: `0.3992` vs `0.2324`.
- **Dependence-Aware Stability:** Ridge beats persistence across **12 of 12 non-overlapping starting offsets**.

### B. 4-Hour Horizon (4h) — PREDICTIVE ADVANTAGE CONFIRMED
- **Validation (2025):**
  - Ridge MAE: `0.007084` vs Persistence: `0.007304` (Lift: `+3.02%`)
  - Pearson: `0.5885` vs `0.5526`, $R^2$: `0.3173` vs `0.1052`.
- **Holdout (2026):**
  - Ridge MAE: `0.006931` vs Persistence: `0.007425` (Lift: `+6.65%`)
  - Pearson: `0.6563` vs `0.6019`, $R^2$: `0.4096` vs `0.2038`.

### C. 24-Hour Horizon (24h) — MARGINAL / NO MATERIAL ADVANTAGE
- **Validation (2025):** Ridge MAE: `0.006892` vs Persistence: `0.006903`.
- **Holdout (2026):** Ridge MAE: `0.006024` vs Persistence: `0.005812`.
- **Scientific Verdict:** At the 24-hour horizon, trailing persistence is equal to or slightly stronger than the 3-feature Ridge regression. The Ridge candidate does NOT establish predictive superiority at 24h.

---

## 3. Scientific Release Gate Summary
- **Technical Integrity Gates (Gates A–G):** `7 / 7 PASS`
- **Predictive Superiority Gate (Gate H):**
  - `1h`: **PASS**
  - `4h`: **PASS**
  - `24h`: **FAIL / NO_SUPERIORITY**
- **Dependence-Aware Validation (Gate I):** `PASS`
- **Prospective Replay (Gate J):** `NOT_EVALUABLE` (read-only snapshot unavailable locally)
- **Overall Verdict:** **ARTIFACT_VALID — RESEARCH CANDIDATE ONLY**.

---

## 4. Next Step Recommendation
- Maintain CBE-0.7.0 strictly frozen in production.
- Do NOT deploy or activate CBE-0.8.0.
- For a future deployment consideration, hybridize horizons: adopt Ridge for 1h and 4h, but retain trailing persistence for 24h.
