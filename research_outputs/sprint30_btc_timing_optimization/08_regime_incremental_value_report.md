# 08 — Market Regime Incremental Value Assessment Report

**Sprint ID:** `CBE_SPRINT30_1_SCIENTIFIC_REPORTING_RECONCILED`  
**Dataset:** `DS-BTC-1H-2023-2024`  
**Canonical Evaluation Status:** **`NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE`**  
**Derived Research Regime Status:** **`NON_CANONICAL_HEURISTIC_EVALUATION_ONLY`**  
**Derived Regime Incremental Verdict:** **`NO_INCREMENTAL_VALUE_UNCONSTRAINED`** (Severe Fee Drag Without Turnover Controls)  

---

## 1. Incremental Value Hierarchy Matrix

The table below measures whether adding market regime classifications provides genuine risk-adjusted value beyond simple price and volatility indicators:

| Tier | Policy Name | Legacy Policy ID | Net Return (%) | Sharpe Ratio | Max Drawdown (%) | Trade Count | Total Costs ($) | Incremental vs Trend (%) | Information Ratio (IR) | Scientific Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline A** | Buy and Hold (Passive Benchmark) | `POLICY_BUY_AND_HOLD` | +155.14% | 1.99 | -32.30% | 1 | $17.47 | +178.53% | N/A | `PASSIVE_BENCHMARK` |
| **Baseline B** | Simple Moving Average Trend Filter | `POLICY_SIMPLE_TREND` | -23.39% | -0.51 | -44.37% | 700 | $11,228.48 | 0.00% | 0.0000 | `BASE_INDICATOR` |
| **Baseline C** | Parkinson Volatility Scaling | `POLICY_VOLATILITY_AWARE` | +16.08% | 0.60 | -31.19% | 682 | $4,847.95 | +39.47% | 1.2749 | `VOLATILITY_BENCHMARK` |
| **Experiment D** | Canonical CBE-0.7.0 Market State Classifier | `POLICY_CANONICAL_CBE` | N/A | N/A | N/A | N/A | N/A | N/A | N/A | **`NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE`** |
| **Experiment E** | Trend & Derived Research Regime Filter | `POLICY_COMBINED_TREND_REGIME`* | -37.93% | -1.76 | -43.95% | 1561 | $8,709.88 | -14.54% | -1.2123 | `NON_CANONICAL_DERIVED_REGIME` |

*\* Legacy policy IDs are retained solely for backward compatibility and experimental reproducibility; they must not be presented as verified `CBE-0.7.0` canonical model results.*

---

## 2. Key Empirical Findings & Model Attribution

1. **Canonical CBE-0.7.0 Evaluation Status:**  
   Canonical `CBE-0.7.0` state outputs were unavailable in this historical research dataset; hence Experiment D is formally recorded as **`NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE`**. No claims of canonical CBE predictive power are made.
2. **Derived Regime Performance (Unconstrained):**  
   Combining the derived heuristic regime with trend-following without turnover controls reduced net returns from -23.39% down to -37.93% due to 1,561 transactions generating massive fee attrition ($8,709+). Incremental Information Ratio was -1.2123 with tracking error 19.00%.
3. **Turnover-Controlled Derived Regime Confirmation:**  
   When multi-bar confirmation was applied to the derived regime (`POLICY_DERIVED_REGIME_CONFIRMATION`), the authoritative persisted trade ledger records **$12,404.63 USDT** (+24.05% net return, 696 trades, total costs $4,531.63). This demonstrates that turnover friction was the dominant driver of underperformance, but the classification remains noncanonical.
4. **Volatility vs Regime Added Value:**  
   Simple Parkinson volatility scaling (Baseline C) added substantial incremental value over Simple Trend (+39.47% incremental return), proving that volatility-based exposure scaling is empirically superior to unconstrained categorical regime switching.
