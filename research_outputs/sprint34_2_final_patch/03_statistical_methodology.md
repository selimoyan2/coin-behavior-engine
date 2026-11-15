# 03. Statistical Methodology & Serial Dependence Resolution — Sprint 34.2 Final Patch

**Sprint ID:** `CBE_SPRINT34_2_FINAL_PATCH_DRAWDOWN_STATISTICAL_INFERENCE_CLOSURE`  
**Standard:** `CBE-STATISTICAL-INFERENCE-RECONCILED-V1.3`  
**Attribution Tier:** `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`  
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)  
**Execution Mode:** `STRICTLY_OFFLINE_RESEARCH`  

---

## 1. Executive Summary: Resolution of the Bootstrap vs Non-Overlapping Discrepancy

In Sprint 34.2, an apparent scientific paradox was identified in the 24h forward-return statistical evidence:
- **Non-Overlapping Subsample ANOVA ($N_{\text{eff}} = 761$):** Reported $F = 0.4452, p = 0.8169$ (Fail to reject $H_0$; no predictive return separation).
- **Sprint 34.2 Block Bootstrap ($N = 18,264$):** Reported Laplace-corrected $p = 0.0020$ (Apparent strong statistical significance).

This document details the mathematical and empirical root cause of this discrepancy, describes the valid dependence-aware procedures implemented in this final patch, and confirms the authoritative evidence classifications.

---

## 2. Root Cause Forensic Analysis

### 2.1 The Overlap Problem in High-Frequency Price Series
When computing $h$-hour forward returns ($R_{t, t+h} = \frac{P_{t+h} - P_t}{P_t}$) on an hourly time-series ($t = 1, \dots, N$):
- For $h = 24$, adjacent observations share 23 of 24 hours of price action—a **95.83% observational overlap**.
- The consecutive error terms are governed by a moving average process of order $h-1$, inducing severe positive autocorrelation ($\rho_1 \approx 0.958$).
- In addition, canonical market regimes exhibit multi-day macro persistence (mean regime duration $> 20$ hours).

### 2.2 Why Sprint 34.2 Bootstrap Produced Spurious $p = 0.0020$
In Sprint 34.2, `scripts/compute_corrected_statistics_sprint34_2.py`:
1. Computed an unadjusted one-way ANOVA $F$-statistic on the full overlapping dataset ($N = 18,264$ bars), yielding $F_{\text{unadj}} = 5.4137$. Standard ANOVA degrees of freedom assume $18,264$ independent observations, inflating the nominal $F$-statistic by a factor of 12x due to degrees-of-freedom distortion.
2. In the permutation loop, the script drew blocks of price returns but applied `np.random.permutation(reg_indices)` bar-by-bar across individual hourly candles.
3. This bar-by-bar shuffling destroyed the temporal clustering and persistence of market regimes, forcing the simulated null distribution of $F$ to collapse to the standard $F$-distribution with mean $\mu \approx 1.0$ (95% CI: $[0.25, 2.05]$).
4. The script then counted how often a simulated null $F$ (mean $\approx 1.0$) exceeded the **overlap-inflated** observed statistic ($F = 5.4137$).
5. In 500 repetitions, exactly 0 permutations exceeded $5.4137$ ($r = 0$).
6. Applying the finite-sample Laplace correction $\frac{r + 1}{B + 1} = \frac{0 + 1}{500 + 1} = 0.0020$ produced the spurious claim of $p = 0.0020$.

The statistical error was two-fold:
1. **Comparing against an overlap-inflated test statistic** ($F = 5.4137$ instead of the true independent $F = 0.4452$).
2. **Employing an invalid null distribution** that failed to preserve the serial persistence of the predictor series (regimes).

---

## 3. Valid Dependence-Aware Methodologies

### 3.1 Method A: Non-Overlapping Permutation Bootstrap (Primary Authoritative Standard)
To eliminate observational overlap entirely:
1. Sample observations at strictly non-overlapping intervals: $t_k = k \cdot h$ for $k = 0, 1, \dots, N_{\text{eff}}-1$.
2. For $h = 24$, $N_{\text{eff}} = \lfloor 18,264 / 24 \rfloor = 761$ independent blocks.
3. Compute the sample test statistic: $F_{\text{non-overlap}} = 0.4452$ ($p = 0.8169$).
4. Under the null hypothesis $H_0$ (regimes contain no predictive return information), randomly permute the regime labels of the 761 independent blocks ($B = 1,000$ iterations).
5. For each iteration $b$, compute $F^{(b)}$.
6. Compute the empirical Laplace-corrected p-value:
   $$p_{\text{boot}} = \frac{\sum_{b=1}^B \mathbb{I}(F^{(b)} \ge F_{\text{non-overlap}}) + 1}{B + 1}$$

**Empirical Result ($h=24$):**
- $F_{\text{non-overlap}} = 0.4452$
- Parametric $p = 0.8169$
- Bootstrap $p_{\text{boot}} = 0.8002$ ($r = 799$ exceedances out of 1,000)
- The bootstrap and parametric p-values are in complete concordance ($p \approx 0.80$–$0.82$).

### 3.2 Method B: Circular Block Shift on Overlapping Data (Dependence-Preserving Null)
If testing on the full overlapping dataset ($N = 18,264$):
1. The null hypothesis must preserve the autocorrelation and block-persistence of both the returns and the regimes.
2. A circular shift (or stationary block permutation) shifts the entire regime sequence by a random lag $\tau \in [h, N-h]$.
3. Under this dependence-aware null, the simulated $F$-distribution shifts upwards to reflect the shared serial correlation (median null $F = 7.52$, 95th percentile $F = 22.22$).
4. Comparing the observed overlapping $F = 5.4137$ to this proper null distribution yields $p = 0.6647$.
5. This independently proves that an observed $F = 5.41$ on overlapping data is entirely typical under random noise with serial correlation.

### 3.3 Method C: Phase-Offset Sensitivity
To ensure the non-overlapping result is not an artifact of starting at hour 0:
- The independent subsampling was evaluated across all 24 possible starting hours ($s \in \{0, 1, \dots, 23\}$).
- Forward return p-values across all 24 offsets:
  - $\text{min}(p) = 0.1167$
  - $\text{median}(p) = 0.6954$
  - $\text{max}(p) = 0.9950$
- In **0 of 24 phase offsets** does $p$ reach significance at $\alpha = 0.05$.

---

## 4. Multi-Horizon Statistical Summary

| Horizon | Total Obs ($N$) | Effective Blocks ($N_{\text{eff}}$) | Return Non-Overlap $F$ | Return Parametric $p$ | Return Bootstrap $p$ | Scientific Classification (Returns) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **6h** | 18,282 | 3,047 | 2.1217 | 0.0600 | 0.0779 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` |
| **24h** | 18,264 | 761 | 0.4452 | 0.8169 | 0.8002 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` |
| **72h** | 18,216 | 253 | 1.1973 | 0.3110 | 0.3057 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` |
| **168h** | 18,120 | 107 | 0.3474 | 0.8828 | 0.8462 | `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` |

---

## 5. Distinction Between Return Alpha and Downside Risk Separation

A critical scientific finding reaffirmed by this audit is the sharp separation between predictive return alpha and downside tail risk:

### 5.1 Expected Forward Return Alpha
- Null Hypothesis: Mean return is equal across regimes ($\mu_1 = \dots = \mu_k$).
- Result at 24h: $F = 0.4452, p = 0.8169$, Bootstrap $p = 0.8002$.
- **Verdict:** `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`. Market regimes do NOT predict directional forward returns.

### 5.2 Downside Risk (Maximum Adverse Excursion - MAE)
- Null Hypothesis: Downside tail risk is equal across regimes.
- Result at 24h: $F = 4.2600, p = 0.000794$, Bootstrap $p = 0.0010$.
- Phase Offset Sensitivity: $\text{min}(p) = 0.000000, \text{median}(p) = 0.000053, \text{max}(p) = 0.010690$.
- **Verdict:** `DESCRIPTIVE_HISTORICAL_FINDING`. Regime-conditioned downside risk differences are statistically significant ($p < 0.01$).
- **Economic Explanation:** Volatility clustering and tail risk are strongly state-dependent (e.g., `TAIL_RISK_ELEVATED` exhibits significantly deeper intraday drawdowns than `BULL_STABLE_QUIET`). This explains why policy risk-budgeting achieves drawdown truncation (-28.94% vs -32.31% in 2023–2024; -25.66% vs -34.76% in 2025) despite producing zero positive excess return alpha.
