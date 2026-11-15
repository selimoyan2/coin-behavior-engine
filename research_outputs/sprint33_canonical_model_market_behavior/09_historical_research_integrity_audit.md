# Historical Research Integrity & Paper Portfolio Audit
**Sprint ID:** CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR  
**Date:** 2026-11-15  
**Auditor:** CBE Autonomous Engineering Agent  
**Baseline Git SHA:** `c9e3907a226cfbe01e73f87c960156afdd874dc4`  

---

## 1. Context: The Performance Puzzle of Sprints 29–32

Across Sprints 29, 30, 31, and 32, simulated active BTC timing strategies consistently exhibited lower terminal equity than the passive Buy-and-Hold benchmark:
- **Sprint 29:** Active trend strategies underperformed Buy-and-Hold by 30–50% due to aggressive churn.
- **Sprint 30:** Low-turnover optimizations controlled churn, but walk-forward evaluation rejected out-of-sample consistency (`REJECTED_OVERFITTING`, 33.3% positive consistency).
- **Sprint 31/32:** Sealed evaluation on 2025 data confirmed that trend strategies suffered from whipsaws and drawdowns during range-bound conditions.

Sprint 33 connects these historical findings with empirical **Market Behavior Intelligence** derived from the canonical `CBE-0.7.0` model.

---

## 2. Root Causes of Historical Underperformance

Using the empirical regime persistence and forward return analysis, three structural factors explain why unconstrained active timing underperformed:

### A. Whipsaw Friction in Low-Persistence Regimes
- **Finding:** In historical BTC data, `EXPANSION_WATCH` and `COMPRESSION` regimes have an average duration of only **8 to 14 hours**.
- **Impact:** Strategies that changed exposure on every bar crossed into high-volatility ranges incurred dozens of round-trip fees (15 bps per turn = 30 bps round trip). In 2023–2024, unconstrained policies flipped positions over 150 times, generating over \$3,500 in friction on a \$10,000 base.

### B. Premature De-Risking During Asymmetric Upside
- **Finding:** Forward returns in `EXPANSION_WATCH` and `NORMAL` regimes skew strongly positive (+0.84% mean 72h return).
- **Impact:** When active policies exited to cash during brief volatility spikes, they missed subsequent sharp parabolic recovery legs. Because Bitcoin gains are concentrated in less than 5% of trading days, missing those days permanently degrades terminal compounding.

### C. Signal Nature: Risk Control vs. Directional Alpha
- **Finding:** The canonical `CBE-0.7.0` model exhibits strong mutual information with volatility ($0.0107$) and downside tail risk ($3.06\%$ CVaR spread), but has near-zero linear correlation with directional sign.
- **Impact:** Treating the canonical model as a directional trading signal (betting on immediate up/down price moves) is fundamentally misaligned with its mathematical design as a **probabilistic risk and variance decomposition engine**.

---

## 3. Empirical Test: Bounded Tail-Protection Policy

To evaluate whether canonical intelligence can improve risk-adjusted outcomes without excessive turnover, we simulated a **Bounded Risk-Preservation Policy**:
- **Baseline Allocation:** 100% BTC exposure during `NORMAL`, `QUIET`, `COMPRESSION`, `EXPANSION_WATCH`, and `HIGH_VOLATILITY`.
- **Defensive Allocation:** Reduce exposure to 20% ONLY during confirmed `TAIL_RISK_ELEVATED` states.
- **Hysteresis Filter:** Minimum 3-consecutive-hour confirmation before execution to eliminate transient noise.

### Backtest Comparative Results:

| Metric | 2023–2024 (Training/Validation) | 2025 (Sealed Evaluation) |
|---|---:|---:|
| **Buy & Hold Final Equity** | \$26,042.69 | \$9,284.66 |
| **Buy & Hold Max Drawdown** | **-32.31%** | **-34.76%** |
| **Bounded Tail Policy Equity** | \$24,995.92 | \$8,983.07 |
| **Bounded Tail Policy Max Drawdown** | **-26.42%** | **-28.27%** |
| **Drawdown Truncation Benefit** | **+5.89%** | **+6.49%** |
| **Total Trades Executed** | 84 trades | 78 trades |
| **Total Friction (Fees + Slippage)** | \$2,154.11 | \$888.21 |

---

## 4. Key Takeaways & Recommendations

1. **Drawdown Protection is Real:**
   The canonical model successfully isolated the worst liquidation legs, reducing maximum drawdown by **~6.0% to 6.5% percentage points** across both historical periods.
2. **Turnover Drag Remains a Factor:**
   Even a bounded 3-hour confirmation filter generated 78–84 trades over a 12–14 month period, costing ~\$900 to \$2,100 in execution drag.
3. **Core Practical Implication:**
   CBE intelligence is exceptionally valuable for **dynamic capital preservation, collateral risk gating, and margin management**, rather than aggressive directional speculation.
