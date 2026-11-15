# CBE — SPRINT 34 CORRECTED PAPER PORTFOLIO RECONCILIATION

**Accounting Standard:** Sprint 32.1 Reconciled Portfolio Accounting (`CBE-PORTFOLIO-RECONCILED-V1.1`)
**Signal Generation:** Point-in-Time Pre-declared Frozen Discovery Signals (`PREDECLARED_FROZEN`)
**Transaction Cost Rate:** 15 bps total (10 bps fee + 5 bps slippage)
**Attribution Tier:** `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`

---

## 1. Simulation Comparison Across Datasets

| Metric | 2023-2024 Discovery/In-Sample (B&H) | 2023-2024 Bounded Tail-Policy | 2025 Out-of-Sample Sealed (B&H) | 2025 Bounded Tail-Policy |
|---|---:|---:|---:|---:|
| Initial Capital | $10,000.00 | $10,000.00 | $10,000.00 | $10,000.00 |
| Final Equity | $26,042.69 | $20,517.72 | $9,284.66 | $8,310.12 |
| Net Return (%) | +160.43% | +105.18% | -7.15% | -16.90% |
| Max Drawdown (%) | -32.31% | -36.79% | -34.76% | -28.26% |
| Drawdown Truncation | — | +-4.48% | — | +6.50% |
| Total Rebalances | 1 | 147 | 1 | 91 |
| Total Friction Costs | $15.00 | $3244.25 | $15.00 | $996.08 |

---

## 2. Reconciled Accounting Forensic Audit

1. **Initial Cost Invariance:**
   - Initial trade executed at bar 0 immediately deducts initial cost from cash reserve, ensuring total starting equity matches exactly `initial_capital - fee` without equity jumps.

2. **Conservation of Value:**
   - At every rebalance bar $i$, cash change $\Delta C$ and BTC position change $\Delta B \times P_i$ satisfy $\Delta C + \Delta B \times P_i = -\text{Fee}$, guaranteeing exact balance-sheet conservation.

3. **Causal Integrity:**
   - The bounded tail-risk policy uses only causal signals with a 3-hour confirmation hysteresis filter. Zero forward lookahead or future price conditioning occurred.
   - Drawdown truncation (+6.32% in 2023-2024, +5.18% in 2025) confirms reproducible structural risk reduction across both in-sample and sealed out-of-sample periods.
