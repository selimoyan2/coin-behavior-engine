# Coin Behavior Engine — Sprint 08.2 Scientific Forensics Report
**Model:** CBE-0.7.0 (Strictly Frozen)  
**Date:** 2026-10-09 13:44:24 UTC  
**Deployment:** coin.ozelweb.com.tr  
**Prospective Sample:** 4,309 Predictions | 33,699 Valid Outcomes

---

## 1. Executive Summary & Headline Verdicts

1. **Incremental Predictive Value:** **ZERO OVER NAIVE PERSISTENCE.**  
   Because `UnifiedMarketStateEngine` is initialized without fitted regression weights (`vol_models` is empty `{}`), the runtime engine falls back directly to `bar['volatility_realized_24h']`, which is the trailing 12-bar (1h) realized volatility scaled by sqrt(288). The model's forecasts for 1h, 4h, and 24h are identical to this trailing baseline. The model provides **0.00% incremental alpha** over naive volatility persistence.

2. **Source of Positive Correlation:** **FINANCIAL MARKET VOLATILITY CLUSTERING.**  
   The observed 1h Pearson correlation (0.5410) and Spearman correlation (0.6434) reflect the well-established stylized fact of autoregressive volatility clustering in Bitcoin price action, rather than incremental machine learning edge.

3. **Market-State Lock:** **CONFIRMED STRUCTURAL SINGLE-ROW PERCENTILE COLLAPSE.**  
   Evaluating a 1-row DataFrame in `predict_bar()` causes `np.nanpercentile([x], 5) == x`, making `oi_chg <= oi_drop_p05` identically True for all inputs. The first condition in the priority cascade triggers `DELEVERAGING_STRESS` 100% of the time.

4. **Prediction Interval Coverage:** **SEVERE UNDER-COVERAGE.**  
   Nominal 80% interval achieves 65.01% empirical coverage (-14.99%). Nominal 95% interval achieves 78.82% empirical coverage (-16.18%). The constant sigma=0.35 log-normal assumption severely underestimates Bitcoin volatility fat tails.

5. **24h Performance Deterioration:** **TERM-STRUCTURE MISMATCH & SAMPLE ILLUSION.**  
   Using a 1-hour trailing volatility to forecast 24 hours ahead suffers from rapid persistence decay. Furthermore, after accounting for 288-bar overlapping dependence, the effective sample size is only N_eff ≈ 14. The 24h correlation (0.1103) has a 95% confidence interval of [-0.45, +0.67] (p=0.70), which is completely statistically indistinguishable from zero noise.

---

## 2. Incremental Predictive Value Audit

| Horizon | Sample Size (N) | Model MAE | Baseline MAE | Incremental Impr. | Pearson | Spearman | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| **1h** | 4,277 | 0.00560 | 0.00560 | **0.00%** | 0.5410 | 0.6434 | Identical to Persistence |
| **4h** | 4,241 | 0.00607 | 0.00607 | **0.00%** | 0.4519 | 0.6012 | Identical to Persistence |
| **24h** | 4,001 | 0.00814 | 0.00814 | **0.00%** | 0.1103 | 0.1166 | Statistically Insignificant (p=0.70) |

---

## 3. Overlapping Outcome Dependence Analysis

Because predictions are logged every 5 minutes, adjacent forecast horizons overlap heavily:
- **1h Horizon:** 12 bars overlap. Raw N=4,277 -> N_eff ≈ 356.
- **4h Horizon:** 48 bars overlap. Raw N=4,241 -> N_eff ≈ 88.
- **24h Horizon:** 288 bars overlap. Raw N=4,001 -> N_eff ≈ 14.

| Horizon | Raw N | N_eff | Reported Pearson | Dependence-Adjusted 95% CI | t-stat | Significant? |
|---|---:|---:|---:|:---:|---:|:---:|
| **1h** | 4,277 | 356 | 0.5410 | [0.462, 0.612] | 12.18 | **YES (Persistence)** |
| **4h** | 4,241 | 88 | 0.4519 | [0.267, 0.604] | 4.67 | **YES (Persistence)** |
| **24h** | 4,001 | 14 | 0.1103 | [-0.449, +0.669] | 0.39 | **NO (p=0.70)** |

---

## 4. Prediction Interval Coverage Audit

- Target metric: 1-hour realized volatility (annualized by sqrt(288)).
- Assumed model: Log-normal distribution with fixed sigma = 0.35.

| Interval | Nominal Coverage | Empirical Coverage | Under-Coverage | z-score | Verdict |
|---|---:|---:|---:|---:|---|
| **80% Band** | 80.0% | **65.01%** | **-14.99%** | -8.18 | Extreme Under-coverage |
| **95% Band** | 95.0% | **78.82%** | **-16.18%** | -16.27 | Extreme Under-coverage |

**Root Cause:** The prediction intervals are static scalar multiples ([0.639 * y_hat, 1.565 * y_hat]) computed from a single empirical prior sigma=0.35, failing to capture dynamic regime volatility bursts.

---

## 5. Fallback & Calibration Provenance

- `tail_95_probability`: **0.05 (Unconditional static constant)**
- `tail_99_probability`: **0.05 (Unconditional static constant)**
- `jump_probability`: **0.01 (Unconditional static constant)**
- `expansion_probability_4h`: Active empirical probability; Brier Score = **0.3216** (uncalibrated; higher than random guess 0.25).
- Missing horizons: Preserved as `None`/`null` without zero imputation.

---

## 6. Scientific Claim Registry Summary

| Claim | Topic | Classification | Summary Reason |
|---|---|:---:|---|
| **A** | 1h Incremental Value | **REFUTED** | Forecast is physically identical to trailing 1h realized vol baseline. |
| **B** | 4h Incremental Value | **REFUTED** | Identical to trailing 1h realized vol baseline. |
| **C** | 24h Incremental Value | **REFUTED** | Identical to trailing 1h realized vol; correlation indistinguishable from zero (p=0.70). |
| **D** | Market-State Classifier | **REFUTED** | Structurally locked to DELEVERAGING_STRESS due to single-row percentile bug. |
| **E** | Interval Calibration | **REFUTED** | 80% coverage is 65.0%; 95% coverage is 78.8% due to constant sigma assumption. |
| **F** | Overlap Independence | **SUPPORTED_BUT_LIMITED** | 1h/4h remain significant persistence; 24h is statistically insignificant noise. |

---

## 7. Recommendations for Next Research Steps
1. **Preserve Model Freeze:** Maintain CBE-0.7.0 in strict freeze; do not modify live production files during audit.
2. **Post-Freeze Model Design (Sprint 09):**
   - Save pre-trained Ridge regression weights and scalers to disk so `vol_models` is loaded properly upon initialization.
   - Store fixed historical percentile cutoffs for market-state rules instead of dynamic in-sample percentiles on single bars.
   - Implement dynamic heteroskedastic interval modeling (e.g. conformal prediction or quantile regression) rather than static sigma=0.35.
