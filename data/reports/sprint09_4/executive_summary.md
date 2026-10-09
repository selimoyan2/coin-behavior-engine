# CBE-0.8.0 Sprint 09.4 Executive Summary

**Project:** Coin Behavior Engine  
**Sprint:** 09.4 — Market State Classifier Reconstruction & Probabilistic Calibration  
**Base Commit:** `81e5033`  
**Candidate Version:** `CBE-0.8.0`  
**Production Model:** `CBE-0.7.0` (STRICTLY FROZEN, 29/29 VERIFIED)  
**Overall Scientific Verdict:** **READY_FOR_CANDIDATE_INTEGRATION** (12/12 Gates PASS)  

---

## 1. Resolution of Identified Production Deficiencies

### Failure A: Market-State Collapse Resolved
- **Root Cause Proven:** CBE-0.7.0 evaluated single-row dynamic percentiles in `market_state/engine.py:370-373`, collapsing the `DELEVERAGING_STRESS` condition to `x <= x & y <= y`, which evaluates to True on every bar.
- **Remediation:** Reconstructed `MarketStateClassifierV080` with fixed historical reference quartiles learned strictly on Discovery (< 2025-01-01). Prohibited derivatives states in `SPOT_ONLY_U0`.
- **Holdout Outcome:** Replaced 100% mechanical collapse with a balanced, realistic distribution:
  - `NORMAL_VOLATILITY`: 46.16%
  - `LOW_VOLATILITY`: 46.83%
  - `HIGH_VOLATILITY`: 7.0%
  - State persistence: 1-hour diagonal probability > 94% across all states.

### Failure B: Forecast Interval Miscalibration Resolved
- **Deficiency in CBE-0.7.0:** Fixed lognormal $\sigma = 0.35$ resulted in severe under-coverage (~65% on nominal 80%, ~78.8% on nominal 95%).
- **Remediation:** Implemented `IntervalCalibratorV080` using split-conformal empirical residual quantiles fitted strictly on Validation (2025) residuals around frozen Ridge forecasts.
- **Holdout Out-of-Sample Results (2026):**
  - **1h Horizon:** Nominal 80% $\to$ **78.41%** (error: 1.59%), Nominal 95% $\to$ **94.84%** (error: 0.16%)
  - **4h Horizon:** Nominal 80% $\to$ **79.15%** (error: 0.85%), Nominal 95% $\to$ **95.63%** (error: 0.63%)
  - **Monotonicity:** $0 \le L_95 \le L_80 \le \hat{y} \le U_80 \le U_95$ guaranteed across 100% of bars.
  - **Winkler Score:** Calibrated intervals achieve substantially superior (lower) Winkler scores compared to uncalibrated baseline (1h 80% ratio: 0.8609, 1h 95% ratio: 0.8144, 4h 80% ratio: 0.9333).

---

## 2. Scientific Decision Gates Summary

All 12 Scientific Decision Gates (Gates A through L) evaluated to **PASS**:
- **Gate A (Root Cause):** PASS — Single-row percentile collapse mathematically reproduced.
- **Gate B (Tier Boundary):** PASS — No derivatives states emitted in `SPOT_ONLY_U0`.
- **Gate C (Discovery Thresholds):** PASS — Thresholds learned strictly on Discovery (< 2025-01-01).
- **Gate D (Non-Collapse):** PASS — No state > 80% prevalence; 3 distinct states observed.
- **Gate E (Persistence):** PASS — Minimum diagonal transition probability > 94%.
- **Gate F (Incremental Information):** PASS — State dummies provide statistically significant lift ($p < 10^{-10}$).
- **Gate G (Residual Calibration):** PASS — Calibration quantiles fitted on Validation (2025).
- **Gate H (Coverage Tolerance):** PASS — Holdout coverage well within [72%, 88%] and [90%, 98%].
- **Gate I (Monotonicity):** PASS — Strict nesting and non-negativity enforced.
- **Gate J (Winkler Superiority):** PASS — Lower Winkler scores across 1h and 4h horizons.
- **Gate K (Production Freeze):** PASS — 29/29 canonical artifacts verified.
- **Gate L (Isolation & Serialization):** PASS — Components fully serialized to JSON with lockbox validation.

---

## 3. Candidate Integration Readiness

The candidate components `MarketStateClassifierV080` and `IntervalCalibratorV080` are verified, deterministic, reproducible, and ready for future candidate integration into CBE-0.8.0.
Deployment remains strictly prohibited.
