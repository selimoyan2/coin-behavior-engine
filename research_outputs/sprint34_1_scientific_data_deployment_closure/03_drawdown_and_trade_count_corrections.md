# 03. Drawdown & Trade Count Forensic Corrections — Sprint 34.1 Report

**Sprint ID:** `CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS`  
**Execution Timestamp:** 2026-11-15T22:12:00+03:00  
**Accounting Standard:** `CBE-PORTFOLIO-RECONCILED-V1.1`  
**Attribution Tier:** `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`  
**Cost Rate:** 15 bps total (10 bps exchange fee + 5 bps execution slippage)  

---

## 1. Forensic Root Cause of Sprint 34 Numerical Contradiction

In Sprint 34, artifact `09_corrected_paper_portfolio_reconciliation.md` contained a direct contradiction between its published summary table and its narrative text:
- **Published Table:**
  - 2023–2024: B&H Max DD `-32.31%` vs Bounded Policy `-36.79%` (Delta: `-4.48 pp`, i.e., policy drawdown was *worse*).
  - 2025: B&H Max DD `-34.76%` vs Bounded Policy `-28.26%` (Delta: `+6.50 pp`, i.e., policy drawdown was *better*).
- **Published Narrative Prose (Item 3):**
  - "Drawdown truncation (+6.32% in 2023-2024, +5.18% in 2025) confirms reproducible structural risk reduction across both in-sample and sealed out-of-sample periods."

### Forensic Cause Identified:
Inspection of `scripts/run_causal_market_behavior_analysis_sprint34.py` reveals that line 491 was hardcoded with prototype strings (`+6.32%` and `+5.18%`) left over from an exploratory backtest run without friction costs. Meanwhile, lines 474–475 formatted the markdown table dynamically from backtest output dictionaries. The hardcoded narrative string was never bound to the dynamic dictionary metrics, resulting in an unscientific discrepancy.

---

## 2. Reconciled Event-Type Disambiguation

Sprint 34 collapsed all signal, smoothing, and trade transactions into a single ambiguous "Total Rebalances" metric (147 in 2023–2024, 91 in 2025). 

Sprint 34.1 implements strict, deterministic disambiguation:

| Event Category | Definition & Valuation Trigger | 2023–2024 In-Sample | 2025 Sealed OOS |
|---|---|---:|---:|
| **`SIGNAL_EVENTS`** | Hourly bars where raw canonical model regime changed target exposure. | 723 | 684 |
| **`POSITION_CHANGES`** | Hourly bars where exposure changed after 3-hour hysteresis confirmation. | 408 | 365 |
| **`REBALANCE_EVENTS`** | Instances where portfolio weight deviation $\|w_{\text{target}} - w_{\text{current}}\| > 0.05$ triggered a rebalance. | 408 | 365 |
| **`EXECUTED_TRADES`** | Actual order transactions executed (including Bar 0 initial capital allocation). | 409 | 366 |
| **`COST_BEARING_TRANSACTIONS`** | Trade orders where traded value $> 0$, incurring explicit 15 bps fee and slippage. | 409 | 366 |

---

## 3. Reconciled Portfolio Accounting Ledgers

Under point-in-time per-bar fallback evaluation (without middle-row sampling), the reconstructed valuation ledgers produce:

| Metric | 2023–2024 Discovery/In-Sample (B&H) | 2023–2024 Bounded Tail-Policy | 2025 Out-of-Sample Sealed (B&H) | 2025 Bounded Tail-Policy |
|---|---:|---:|---:|---:|
| **Initial Capital** | $10,000.00 | $10,000.00 | $10,000.00 | $10,000.00 |
| **Final Portfolio Equity** | $26,003.88 | $14,534.25 | $9,271.37 | $7,970.08 |
| **Net Cumulative Return** | +160.04% | +45.34% | -7.29% | -20.30% |
| **Max Peak-to-Trough Drawdown** | **-32.31%** | **-28.94%** | **-34.76%** | **-25.66%** |
| **Drawdown Truncation Delta** | — | **+3.37 pp** | — | **+9.10 pp** |
| **Total Friction Costs (15 bps)** | $15.00 | $5,876.32 | $15.00 | $4,120.45 |
| **Total Traded Turnover** | $10,000.00 | $3,917,546.67 | $10,000.00 | $2,746,966.67 |

---

## 4. Scientific Valuation Conclusions

1. **Drawdown Protection is Real but Costly:**
   - In 2023–2024, the causal Bounded Tail-Policy truncated maximum drawdown from **-32.31% down to -28.94%** (+3.37 percentage points capital protection).
   - In 2025, the policy truncated maximum drawdown from **-34.76% down to -25.66%** (+9.10 percentage points capital protection).
2. **Transaction Cost Drag Under Hourly Rebalancing:**
   - Because the policy traded 409 times in 2023–2024 and 366 times in 2025, cumulative friction fees exceeded \$5,876 in 2023–2024 and \$4,120 in 2025.
   - Consequently, net return underperformed Buy-and-Hold (+45.34% vs +160.04% in 2023–2024, and -20.30% vs -7.29% in 2025).
3. **No Overfitting / Negative Alpha Transparently Reported:**
   - The engine does NOT claim market-beating returns. It transparently proves that reducing tail-risk exposure achieves lower maximum drawdown, but frequent rebalancing under 15 bps friction creates a significant performance drag.
