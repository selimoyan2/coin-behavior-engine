# CBE-0.8.0 Sprint 09.5 Executive Summary

**Project:** Coin Behavior Engine  
**Sprint:** 09.5 — High-Volatility Calibration Repair & Scientific Consistency Audit  
**Base Commit:** `d6b326f`  
**Candidate Version:** `CBE-0.8.0`  
**Production Model:** `CBE-0.7.0` (STRICTLY FROZEN, 29/29 CANONICAL ARTIFACTS VERIFIED)  
**Overall Scientific Verdict:** **READY_FOR_CANDIDATE_INTEGRATION** (12/12 Gates PASS)  

---

## 1. High-Volatility Calibration Repair

### Defect Identified:
Global split-conformal calibration pooled all 2025 residuals, resulting in severe conditional under-coverage during high-volatility regimes (1h 80% coverage collapsed to 50.38% on Holdout 2026).

### Scientific Protocol & Internal 2025 Validation:
To prevent leakage and avoid tuning on the previously inspected 2026 Holdout, a strict chronological nested validation was conducted within 2025:
- **Fit Partition:** Jan 1 – Aug 31, 2025 (69,408 bars)
- **Evaluation Partition:** Sep 1 – Dec 31, 2025 (34,560 bars) with 288-bar forward embargoes

### Evaluated Candidates:
1. **Candidate A (Global Split-Conformal):** Internal High-Vol 80% coverage collapsed to **45.75%**.
2. **Candidate B (State-Conditioned):** Internal High-Vol 80% coverage reached **73.08%**.
3. **Candidate C (Volatility-Normalized):** Internal High-Vol 80% coverage reached **72.95%** with lowest Winkler score.
4. **Candidate D (Rolling 30d):** Internal High-Vol 80% coverage remained depressed at **53.33%**.
5. **Candidate E (Conservative Hybrid):** Best internal reliability, combining sample-size guarded state conditioning ($N \ge 500$) with a 1.15x upper tail safety factor, achieving **73.9%** high-volatility 80% coverage while reducing overall interval width.

On historical 2026 Holdout, Candidate E achieves **84.80%** 80% coverage and **97.95%** 95% coverage in `HIGH_VOLATILITY`.

---

## 2. Dependence-Aware Uncertainty Analysis
Using non-overlapping horizon strides and paired block bootstrap ($L = 288$ bars, 500 iterations):
- 1h High-Volatility 80% coverage lift: **+34.98%** (95% CI: [32.08%, 38.1%]).
- All-offset stride evaluations confirm coverage improvement is robust across all starting offsets.

---

## 3. Market-State Incremental Information Audit
- Chronological nested comparison confirms that discrete market state dummies yield **negative out-of-sample incremental $R^2$** ($-0.00023$) on 2026 Holdout.
- High in-sample F-statistics in earlier reports were artifacts of dense overlapping time-series data.
- **Scientific Conclusion:** Market-state labels provide no incremental point predictive edge beyond continuous features and are formally classified as **`DESCRIPTIVE_ONLY`**.

---

## 4. Scientific Consistency Audit & Versioned Artifacts
- The reporting discrepancy in Sprint 09.4 completion text (`49.33% / 46.88% / 3.79%`) has been audited and resolved; committed JSON reports (`46.83% / 46.16% / 7.00%`) are verified authoritative.
- Reconstructed calibration serialized as [`cbe_interval_calibration_v080_095.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/data/models/cbe_interval_calibration_v080_095.json) with lockbox [`cbe_calibration_lockbox_v095.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/data/models/cbe_calibration_lockbox_v095.json).
- Production deployment remains strictly prohibited.
