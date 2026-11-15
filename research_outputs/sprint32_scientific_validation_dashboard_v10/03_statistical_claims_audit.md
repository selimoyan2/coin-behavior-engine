# 03 — Statistical Claims Audit Report
## Rigorous Re-Evaluation of Sprint 31 H1–H5 Hypotheses

**Sprint ID:** `CBE_SPRINT32_SCIENTIFIC_VALIDATION_DASHBOARD_V10`  
**Audit Date UTC:** `2026-11-15T11:45:57.660801+00:00`  
**Methodological Verdict:** **`DESCRIPTIVE_EVIDENCE_VALIDATED_STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**  

---

## 1. Executive Methodological Finding

> [!WARNING]
> In Sprint 31, deterministic differences between single simulation paths on 2025 data were reported with p-values (e.g. $p < 0.001$).  
> This audit determines that:
> 1. **Hourly observations are serially dependent.** Financial returns exhibit volatility clustering and autocorrelation. Treating 8,760 hourly candles as independent observations is mathematically invalid.
> 2. **Sample size of independent paths is N = 1.** A single historical trajectory over one calendar year cannot establish asymptotic statistical distributions.
> 3. **Bonferroni correction does not manufacture statistical significance.** Adjusting nominal alpha from 0.05 to 0.01 corrects for family-wise error only when valid test statistics exist.
> 
> Therefore, all reported p-values are formally revoked and classified as:  
> **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**  
> Observed empirical differences are retained under the honest scientific standard:  
> **`DESCRIPTIVE_THRESHOLD_MET`** or **`DESCRIPTIVE_THRESHOLD_FAILED`**.

---

## 2. Comprehensive Hypotheses Audit Matrix

| Hypothesis | Name | Metric | Effect Size | Descriptive Status | Statistical Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **H1** | Turnover Controls Reduce Transaction Costs | `transaction_cost_reduction_pct` | Costs reduced by 88.31% ($6,789.12 -> $793.47, saving $5,995.65 USDT). | **`DESCRIPTIVE_THRESHOLD_MET`** | **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`** |
| **H2** | Reduced Transaction Costs Improve Net Strategy Return | `net_return_difference_percentage_points` | Net return improved by +33.80 percentage points (-62.60% -> -28.80%), preserving $3,380.57 of equity. | **`DESCRIPTIVE_THRESHOLD_MET`** | **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`** |
| **H3** | Turnover Controls Dampen Maximum Drawdown Severity | `max_drawdown_severity_reduction_percentage_points` | Maximum drawdown severity curbed from -65.12% to -39.20% (improvement of 25.92 pp). | **`DESCRIPTIVE_THRESHOLD_MET`** | **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`** |
| **H4** | Active Low-Turnover Policy Outperforms Passive Buy & Hold | `excess_return_over_buy_and_hold_percentage_points` | Active timing delivered -28.80% vs Buy & Hold -9.69% (underperformance: -19.11 pp). | **`DESCRIPTIVE_THRESHOLD_FAILED`** | **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`** |
| **H5** | Derived Regime Confirmation Adds Incremental Value Over Simple Trend | `net_return_improvement_percentage_points` | Net return improved by +20.27 pp (-62.60% -> -42.33%) and Sharpe improved by +0.72 (-3.00 -> -2.28). | **`DESCRIPTIVE_THRESHOLD_MET`** | **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`** |

---

## 3. Detailed Hypothesis Re-Evaluation

### H1: Turnover Controls Reduce Transaction Costs
- **Null Hypothesis ($H_0$):** H0: Low-turnover controls do not reduce transaction costs relative to unconstrained trend (E[Costs_low] >= E[Costs_simple]).
- **Alternative Hypothesis ($H_1$):** H1: Low-turnover controls reduce transaction costs (E[Costs_low] < E[Costs_simple]).
- **Observation Unit:** Deterministic 1-year simulation path (57 trades vs 616 trades)
- **Sample Size:** N = 1 annual market realization (8,760 hourly candles)
- **Target Threshold:** `Cost reduction >= 50.0%`
- **Observed Test Statistic:** `88.31`
- **Descriptive Verdict:** **`DESCRIPTIVE_THRESHOLD_MET`**
- **Statistical Significance:** **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**
- **Serial Dependence Assessment:** Trade triggers are driven by trend state durations that exhibit serial autocorrelation. A single backtest does not provide independent trade samples.
- **Violated Statistical Assumptions:**
  - Independent and identically distributed (i.i.d.) observations
  - Repeated independent path trials (N=1 historical path)
- **Canonical Model Attribution:** `NOT_APPLICABLE (Rule-based technical timing policy)`
- **Epistemic Interpretation:** Descriptively confirmed: Hysteresis bands and holding periods reliably curtail trade frequency and transaction costs. However, population-level statistical significance cannot be established from a single historical trajectory.

### H2: Reduced Transaction Costs Improve Net Strategy Return
- **Null Hypothesis ($H_0$):** H0: Reduced transaction friction does not improve net annual return over unconstrained trend (E[Return_low] <= E[Return_simple]).
- **Alternative Hypothesis ($H_1$):** H1: Reduced transaction friction improves net annual return (E[Return_low] > E[Return_simple]).
- **Observation Unit:** Deterministic 1-year simulation path (8,760 hourly steps)
- **Sample Size:** N = 1 annual market realization
- **Target Threshold:** `Return difference > 0.0 percentage points`
- **Observed Test Statistic:** `33.8`
- **Descriptive Verdict:** **`DESCRIPTIVE_THRESHOLD_MET`**
- **Statistical Significance:** **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**
- **Serial Dependence Assessment:** Hourly portfolio equity returns exhibit severe serial autocorrelation and volatility clustering (ARCH/GARCH dynamics). Treating hourly bars as independent observations artificially deflates standard errors.
- **Violated Statistical Assumptions:**
  - Zero return autocorrelation (hourly returns are serially dependent)
  - Stationarity across market regimes
  - Asymptotic independence of observations
- **Canonical Model Attribution:** `NOT_APPLICABLE (Rule-based technical timing policy)`
- **Epistemic Interpretation:** Descriptively confirmed: Lower transaction costs directly preserved capital. Statistically, however, this single-year difference cannot be generalized as an unconditional alpha without multi-year regime bootstrap testing.

### H3: Turnover Controls Dampen Maximum Drawdown Severity
- **Null Hypothesis ($H_0$):** H0: Low-turnover controls do not reduce maximum drawdown severity (|MDD_low| >= |MDD_simple|).
- **Alternative Hypothesis ($H_1$):** H1: Low-turnover controls reduce maximum drawdown severity (|MDD_low| < |MDD_simple|).
- **Observation Unit:** Peak-to-trough path extremum over 8,760 hourly candles
- **Sample Size:** N = 1 trajectory path extremum
- **Target Threshold:** `Drawdown severity reduction >= 10.0 percentage points`
- **Observed Test Statistic:** `25.92`
- **Descriptive Verdict:** **`DESCRIPTIVE_THRESHOLD_MET`**
- **Statistical Significance:** **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**
- **Serial Dependence Assessment:** Serial dependence and path-dependence are inherent to drawdown series. Drawdown is an extreme-value path-dependent statistic. Observations within a single drawdown cycle are 100% dependent on prior path states.
- **Violated Statistical Assumptions:**
  - Independent observations
  - Extreme value asymptotic distribution on single realization
- **Canonical Model Attribution:** `NOT_APPLICABLE (Rule-based technical timing policy)`
- **Epistemic Interpretation:** Descriptively confirmed: Eliminating false-breakout whipsaws curbed cumulative equity decay from -65.12% to -39.20%. Statistically unestablished due to extreme-value path dependence.

### H4: Active Low-Turnover Policy Outperforms Passive Buy & Hold
- **Null Hypothesis ($H_0$):** H0: Active timing does not outperform passive Buy & Hold after costs (E[Return_active] <= E[Return_bnh]).
- **Alternative Hypothesis ($H_1$):** H1: Active timing outperforms passive Buy & Hold (E[Return_active] > E[Return_bnh]).
- **Observation Unit:** Deterministic 1-year simulation path
- **Sample Size:** N = 1 annual market realization
- **Target Threshold:** `Excess return > 0.0 percentage points`
- **Observed Test Statistic:** `-19.11`
- **Descriptive Verdict:** **`DESCRIPTIVE_THRESHOLD_FAILED`**
- **Statistical Significance:** **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**
- **Serial Dependence Assessment:** Serial dependence and autocorrelation in underlying price series caused policy lag at trend inflection points while bearing identical market sequences.
- **Violated Statistical Assumptions:**
  - Threshold met requirement (threshold was failed)
  - Sample size sufficiency for market regime diversity
- **Canonical Model Attribution:** `NOT_APPLICABLE (Rule-based technical timing policy)`
- **Epistemic Interpretation:** REJECTED: Active timing failed to outperform passive holding on 2025 unseen data. Trend-following lag in range-bound/whipsaw markets incurred negative alpha.

### H5: Derived Regime Confirmation Adds Incremental Value Over Simple Trend
- **Null Hypothesis ($H_0$):** H0: Derived regime confirmation does not improve net return or Sharpe ratio over simple trend (Delta_Return <= 0 or Delta_Sharpe <= 0).
- **Alternative Hypothesis ($H_1$):** H1: Derived regime confirmation improves net return and Sharpe ratio (Delta_Return > 0 and Delta_Sharpe > 0).
- **Observation Unit:** Deterministic 1-year simulation path
- **Sample Size:** N = 1 annual market realization
- **Target Threshold:** `Delta_Return > 0.0 and Delta_Sharpe > 0.0`
- **Observed Test Statistic:** `20.27`
- **Descriptive Verdict:** **`DESCRIPTIVE_THRESHOLD_MET`**
- **Statistical Significance:** **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**
- **Serial Dependence Assessment:** Serial persistence and multi-hour cluster autocorrelation characterize regime classification states.
- **Violated Statistical Assumptions:**
  - Independent observations
  - Canonical model equivalence (CANONICAL MODEL WAS NOT USED; only derived research proxy)
- **Canonical Model Attribution:** `DERIVED_RESEARCH_CLASSIFIER_ONLY (NOT CANONICAL CBE-0.7.0)`
- **Epistemic Interpretation:** Descriptively confirmed: Volatility and momentum regime filtering prevented several false breakouts. However, canonical model status was STRICTLY_FROZEN, so this reflects only the research proxy classifier, and statistical significance is unestablished.

---

## 4. Methodological Conclusion

By explicitly separating descriptive effect sizes from unestablished statistical discoveries, the Coin Behavior Engine maintains absolute epistemological integrity. Historical performance improvements are documented as empirical path observations without overclaiming predictive or statistical certainty.
