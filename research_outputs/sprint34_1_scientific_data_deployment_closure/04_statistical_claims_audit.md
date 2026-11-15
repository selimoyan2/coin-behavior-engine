# 04. Statistical Claims & Inference Audit — Sprint 34.1 Forensic Report

**Sprint ID:** `CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS`  
**Execution Timestamp:** 2026-11-15T22:13:00+03:00  
**Model Version:** `CBE-0.7.0` — `STRICTLY_FROZEN`  
**Statistical Rigor Standard:** Newey-West / Hansen-Hodrick Overlap Correction & Stationary Block Bootstrap  

---

## 1. Executive Summary: Overlap Inflation in Prior Sprints

In Sprint 34, artifact `08_corrected_incremental_value_assessment.md` claimed:
- Forward return separation: ANOVA $F = 5.36$, $p < 0.0001$.
- Forward downside risk (MAE) separation: ANOVA $F = 214.38$, $p < 10^{-15}$.

### The Mathematical Flaw:
These p-values were computed using standard textbook ANOVA, which strictly assumes **independent and identically distributed (i.i.d.) observations**.
In hourly financial time-series evaluated on 24-hour forward returns:
1. **95.83% Window Overlap:** Bar $t$ and bar $t+1$ share 23 out of 24 future prices. The rolling 24-hour forward returns are inherently serially correlated moving averages.
2. **Effective Degrees of Freedom:** While the dataset contains $N = 18,264$ hourly observations, the actual number of non-overlapping 24-hour blocks is only:
   $$N_{\text{eff}} \approx \frac{18,264}{24} = 761 \text{ independent blocks}$$
3. **Spurious Precision:** Feeding 18,264 observations into an unadjusted $F$-distribution treats 18,264 dependent data points as independent degrees of freedom, artificially compressing standard errors and driving p-values down to astronomical, unscientific levels ($p < 10^{-15}$).

---

## 2. Re-Evaluated Multi-Horizon Statistical Evidence

Sprint 34.1 re-evaluates all horizons ($h \in \{6\text{h}, 24\text{h}, 72\text{h}, 168\text{h}\}$) using both **non-overlapping subsampling** ($N_{\text{eff}}$) and **stationary block bootstrap** ($B = 500$, block length $b = 2h$):

| Horizon | Overlap % | Nominal Obs ($N$) | Effective Blocks ($N_{\text{eff}}$) | Return Unadj $F$ ($p$) | Return Non-Overlap $F$ ($p$) | Return Bootstrap $p$ | Return Verdict | Risk (MAE) Non-Overlap $F$ ($p$) | Risk (MAE) Verdict |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| **6h** | 83.33% | 18,282 | 3,047 | 6.28 (<0.0001) | 2.12 (0.0600) | 0.0000 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` | 19.15 (0.0000) | `DESCRIPTIVE_HISTORICAL_FINDING` |
| **24h** | 95.83% | 18,264 | 761 | 5.41 (<0.0001) | **0.45 (0.8169)** | 0.0000 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` | **4.26 (0.0008)** | `DESCRIPTIVE_HISTORICAL_FINDING` |
| **72h** | 98.61% | 18,216 | 253 | 2.31 (0.0414) | 1.20 (0.3110) | 0.0320 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` | 1.41 (0.2209) | `DESCRIPTIVE_HISTORICAL_FINDING` |
| **168h** | 99.40% | 18,120 | 107 | 6.24 (<0.0001) | **0.35 (0.8828)** | 0.0000 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` | 1.53 (0.1882) | `DESCRIPTIVE_HISTORICAL_FINDING` |

---

## 3. Scientific Categorization of Findings

To ensure scientific integrity and eliminate all overstatements of predictive power, empirical outcomes are formally classified into four standardized tiers:

### 1. `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` (Forward Return Separation)
- At 24h horizon, the non-overlapping subsample yields $F = 0.4452$, $p = 0.8169$.
- At 168h horizon, the non-overlapping subsample yields $F = 0.3474$, $p = 0.8828$.
- **Scientific Conclusion:** There is **no statistically significant forward return alpha** across market regimes once serial correlation and window overlap are properly accounted for. The model cannot reliably predict whether BTC will go up or down over 24h to 168h based solely on discrete regime classification.

### 2. `DESCRIPTIVE_HISTORICAL_FINDING` (Forward Downside Risk / MAE Separation)
- At 24h horizon, non-overlapping risk separation yields $F = 4.26$, $p = 0.0008$.
- `TAIL_RISK_ELEVATED` regimes consistently exhibit higher realized drawdowns (MAE) than `QUIET` regimes across both in-sample and out-of-sample partitions.
- **Scientific Conclusion:** Downside risk and volatility clustering are genuine, statistically verifiable physical properties of Bitcoin orderflow. While returns are unpredictable, volatility and drawdown hazard are structurally partitionable.

### 3. `EXPLORATORY_PREDICTIVE_EVIDENCE` (Short-Horizon 6h Volatility Dynamics)
- At the 6h horizon, borderline significance ($p \approx 0.06$) is observed under non-overlapping sampling.
- **Scientific Conclusion:** Regimes reflect short-term microstructure states that dissipate over multi-day horizons.

### 4. `INDEPENDENT_VALIDATION_NOT_ESTABLISHED` (Out-of-Sample Alpha Persistence)
- Net portfolio returns consistently underperformed Buy-and-Hold across both 2023–2024 (+45.34% vs +160.04%) and 2025 (-20.30% vs -7.29%) due to 15 bps turnover friction.
- **Scientific Conclusion:** Active timing policies based on regime transitions fail to generate positive alpha in independent validation.
