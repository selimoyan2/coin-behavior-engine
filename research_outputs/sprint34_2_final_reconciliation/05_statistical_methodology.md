# 05. Authoritative Statistical Inference & Overlap Audit Methodology — Sprint 34.2

**Sprint ID:** `CBE_SPRINT34_2_FINAL_RECONCILIATION_REGRESSION_CLOSURE_HISTORICAL_DATA_READINESS`  
**Execution Timestamp:** 2026-11-15T23:26:00+03:00  
**Attribution Tier:** `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`  
**Methodology Standard:** `FINITE_SAMPLE_LAPLACE_CORRECTED_BLOCK_BOOTSTRAP_V1.2`  
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)  

---

## 1. Executive Summary of Statistical Audit

This document establishes the authoritative scientific methodology for hypothesis testing on forward market metrics across canonical regimes.

Key scientific resolutions:

1. **Effective Degrees of Freedom (761 vs 781 Blocks Resolved):**
   - For a 24-hour horizon, consecutive hourly observations share 23 of 24 bars (95.83% overlap).
   - In the valid forward evaluation space of $N = 18,264$ bars, the true number of non-overlapping 24h blocks is:
     $$N_{\text{eff}} = \left\lfloor \frac{18,264}{24} \right\rfloor = 761 \text{ blocks}$$
   - The legacy citation of 781 blocks was an unadjusted calculation derived from 18,744 raw bars prior to warmup exclusion ($18,744 / 24 = 781.0$).
2. **Resolution of Bootstrap vs Non-Overlapping Subsample Discrepancy:**
   - In earlier reports, bootstrap empirical $p$-values were reported as exact $0.0$ while non-overlapping subsample $p$-values were non-significant ($p = 0.8169$).
   - This occurred because unadjusted $F$ ($F = 5.41$, inflated by $N = 18,264$ overlapping degrees of freedom) was tested against null permutations. In 500 trials, the null $F$ distribution rarely exceeded $5.41$ simply because $5.5 \times 10^{-5} \ll 1/500$.
   - Non-overlapping subsampling eliminates the artificial degrees of freedom, proving that forward returns are statistically indistinguishable across regimes ($F = 0.4452, p = 0.8169$).
3. **Finite-Sample Monte Carlo Correction ($p \neq 0.0$ Rule):**
   - Under standard finite-sample bootstrap principles (Davison & Hinkley, 1997; North et al., 2002), empirical $p$-values must never be reported as exact $0.0$.
   - An unbiased Laplace plus-one correction is enforced:
     $$p = \frac{r + 1}{B + 1}$$
     For $r = 0$ exceedances out of $B = 500$ repetitions, $p = \frac{1}{501} \approx 0.0020$.
4. **Scientific Classification Verdicts:**
   - **Forward Return Predictability:** Classified as `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`.
   - **Forward Downside Risk Separation (MAE):** Classified as `DESCRIPTIVE_HISTORICAL_FINDING` (demonstrating structural volatility persistence, not investment alpha).
   - **2025 Dataset Provenance:** The 2025 historical dataset, having been previously inspected and reported in Sprint 31, is classified as sealed historical evaluation data, **never as fresh independent validation**.

---

## 2. Mathematical Framework & Null Hypotheses

### Hypothesis 1: Forward Return Invariance
- **Null Hypothesis ($H_0^{\text{return}}$):** Mean forward log-return over horizon $h$ is identical across all canonical market regimes:
  $$H_0: \mu_{\text{NORMAL}} = \mu_{\text{QUIET}} = \mu_{\text{HIGH\_VOL}} = \mu_{\text{COMPRESSION}} = \dots$$
- **Test Statistic:** One-way ANOVA $F$-statistic and Kruskal-Wallis non-parametric $H$-statistic.

### Hypothesis 2: Forward Downside Risk Separation
- **Null Hypothesis ($H_0^{\text{risk}}$):** Mean Maximum Adverse Excursion ($\text{MAE} = \min_{t \le s \le t+h} \frac{P_s - P_t}{P_t}$) is identical across all canonical regimes:
  $$H_0: \mathbb{E}[\text{MAE} \mid \text{Regime}_i] = \mathbb{E}[\text{MAE} \mid \text{Regime}_j] \quad \forall i, j$$

---

## 3. Horizon-by-Horizon Authoritative Results

| Horizon | Total Bars ($N$) | Non-Overlapping Blocks ($N_{\text{eff}}$) | Return Non-Overlap $F$ | Return Non-Overlap $p$ | Return Bootstrap Laplace $p$ | Return Scientific Verdict | Risk (MAE) Non-Overlap $p$ | Risk (MAE) Scientific Verdict |
|---|---:|---:|---:|---:|---:|:---:|---:|:---:|
| **6h** | 18,282 | 3,047 | 2.1217 | 0.0600 | 0.0020 | **STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED** | < 0.0001 | **DESCRIPTIVE_HISTORICAL_FINDING** |
| **24h** | 18,264 | **761** | 0.4452 | **0.8169** | 0.0020 | **STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED** | **0.0008** | **DESCRIPTIVE_HISTORICAL_FINDING** |
| **72h** | 18,216 | 253 | 1.1973 | 0.3110 | 0.0339 | **STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED** | 0.2209 | **DESCRIPTIVE_HISTORICAL_FINDING** |
| **168h** | 18,120 | 107 | 0.3474 | 0.8828 | 0.0020 | **STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED** | 0.1882 | **DESCRIPTIVE_HISTORICAL_FINDING** |

---

## 4. Block-Length Sensitivity Analysis (24h Horizon, $B=500$, Seed=42)

To evaluate sensitivity to serial correlation and block length selection, stationary moving block bootstrap was executed across block lengths $b \in \{12, 24, 48, 96\}$:

| Block Length ($b$) | Return Exceedances ($r$) | Return Laplace $p$ | 95% Null CI for Return $F$ | MAE Exceedances ($r$) | MAE Laplace $p$ | 95% Null CI for MAE $F$ |
|---|---:|---:|---|---:|---:|---|
| **12h** ($h/2$) | 0 | 0.0020 | $[0.1378, 2.3021]$ | 0 | 0.0020 | $[0.1345, 2.3551]$ |
| **24h** ($h$) | 0 | 0.0020 | $[0.1412, 2.3244]$ | 0 | 0.0020 | $[0.1298, 2.3482]$ |
| **48h** ($2h$ - Primary) | 0 | 0.0020 | $[0.1401, 2.2985]$ | 0 | 0.0020 | $[0.1322, 2.3810]$ |
| **96h** ($4h$) | 0 | 0.0020 | $[0.1425, 2.3110]$ | 0 | 0.0020 | $[0.1309, 2.3644]$ |

### Methodological Interpretation:
The 95% null distribution for $F$ consistently centers around $1.00$ with upper 97.5% percentile near $2.31$ across all block lengths. Because $F_{\text{unadj}} = 5.41$ exceeds $2.31$ under all block lengths, the unadjusted test rejected the null solely due to overlapping window bias. When non-overlapping subsampling is used, the observed $F = 0.4452$ falls comfortably within the null distribution ($p = 0.8169$), proving that regime-conditioned directional forward return differences are statistically non-significant.
