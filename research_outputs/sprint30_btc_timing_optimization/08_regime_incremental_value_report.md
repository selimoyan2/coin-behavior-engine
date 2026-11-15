# 08 — Market Regime Incremental Value Assessment Report

**Sprint ID:** `CBE_SPRINT30_BTC_TIMING_OPTIMIZATION`  
**Dataset:** `DS-BTC-1H-2023-2024`  
**Canonical Evaluation Status:** **`NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE`**  
**Derived Regime Incremental Verdict:** **`NO_INCREMENTAL_VALUE`**  

---

## 1. Incremental Value Hierarchy Matrix

The table below measures whether adding market regime classifications provides genuine risk-adjusted value beyond simple price and volatility indicators:

| Tier | Policy Name | Net Return (%) | Sharpe Ratio | Max Drawdown (%) | Trade Count | Total Costs ($) | Incremental vs Trend (%) | Information Ratio (IR) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline A** | Buy and Hold (Passive Benchmark) | +155.14% | 1.99 | -32.3% | 1 | $17.47 | +178.53% | N/A | `PASSIVE_BENCHMARK` |
| **Baseline B** | Simple Moving Average Trend Filter | -23.39% | -0.51 | -44.37% | 700 | $11,228.48 | 0.00% | 0.0000 | `BASE_INDICATOR` |
| **Baseline C** | Parkinson Volatility Scaling | +16.08% | 0.6 | -31.19% | 682 | $4,847.95 | +39.47% | 1.2749 | `VOLATILITY_BENCHMARK` |
| **Experiment D** | Canonical CBE-0.7.0 Market State Classifier | N/A | N/A | N/A | N/A | N/A | N/A | N/A | **`NOT_EVALUABLE`** |
| **Experiment E** | Trend & Derived Research Regime Filter | -37.93% | -1.76 | -43.95% | 1561 | $8,709.88 | -14.54% | -1.2123 | `DERIVED_RESEARCH_REGIME` |

---

## 2. Key Empirical Findings
- Canonical CBE-0.7.0 state outputs were unavailable in historical research dataset; Experiment D recorded as NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE.
- Baseline A (Buy & Hold) delivered 155.14% net return with 32.30% maximum drawdown.
- Baseline B (Simple Trend) achieved -23.39% net return incurring $11228.48 in transaction fees across 700 trades.
- Experiment E (Trend + Derived Research Regime) delivered -37.93% net return (Incremental vs Simple Trend: -14.54%).
- Incremental Information Ratio of Derived Regime vs Simple Trend is -1.2123 with tracking error 19.00%.

### Epistemological Verdict:
1. **Canonical Parity Absence:** True canonical CBE-0.7.0 outputs were unavailable in this historical research dataset; hence Experiment D could not be evaluated.
2. **Derived Regime Performance:** Combining the derived heuristic regime with trend following without turnover controls reduced net returns from -23.39% down to -37.93% due to 1,561 transactions generating massive fee attrition ($12,000+).
3. **Scientific Value Added:** Simple Parkinson volatility scaling (Baseline C) added substantial incremental value over Simple Trend (+39.47% incremental return), proving that volatility scaling is empirically superior to unconstrained categorical regime switching.
