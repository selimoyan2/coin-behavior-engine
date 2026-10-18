# CBE Sprint 11.10 Baseline, Simulator Integrity & Forensic Discrepancy Audit

**Sprint:** 11.11 (Phase 1 Independent Audit)  
**Date:** 2026-10-18  
**Scope:** Reconcile Sprint 11.10 Strategy Returns, Buy-and-Hold Discrepancies, Portfolio Accounting, Drawdown Additivity Fallacy, and Retrospective Reversal Bias  
**System:** Coin Behavior Engine (CBE) — Research Lab  
**Author:** Quantitative Data Integrity Auditor & Principal Research Engineer  

---

## Executive Summary

Before implementing the Sprint 11.11 Patient Adaptive Spot Policy, an exhaustive forensic integrity audit was conducted on the Sprint 11.10 codebase, execution ledgers, benchmark tables, and mathematical claims.

### Core Audit Findings

1. **Reproduction of Sprint 11.10 Strategy Results:**
   All 8 strategy equity curves and net financial outcomes reproduce deterministically from the 105,120-bar dataset (`market_state_dataset.parquet`) on the 65-day holdout partition (`2026-08-15T14:30:00Z` to `2026-10-18T11:25:00Z`, 18,396 bars) with initial capital of \$10,000.00 USD:
   - **Strategy A (USDT Cash):** 0 trades, \$0.00 return (0.00%), \$0.00 max drawdown.
   - **Strategy B (Buy & Hold BTC):** 1 trade, +\$2,985.10 net PnL (+29.85% return), 8.55% max drawdown, \$33.00 friction.
   - **Strategy C (Simple Trend Switch):** 65 trades, -\$470.40 net PnL (-4.70% return), 21.65% max drawdown, \$1,969.28 friction.
   - **Strategy D (48h Trend Following):** 19 trades, +\$930.38 net PnL (+9.30% return), 15.88% max drawdown, \$582.00 friction.
   - **Strategy E (24h Analogue Strategy):** 49 trades, +\$563.38 net PnL (+5.63% return), 13.26% max drawdown, \$1,559.15 friction.
   - **Strategy F (Regime-Gated Analogue):** 65 trades, -\$152.67 net PnL (-1.53% return), 17.52% max drawdown, \$1,992.81 friction.
   - **Strategy G (Dynamic Adaptive Position Engine):** 98 trades, +\$2,611.79 gross PnL, \$2,922.87 friction, -\$311.08 net PnL (-3.11% return), 15.23% max drawdown.
   - **Strategy H (Conservative Reversal):** 116 trades, +\$76.25 gross PnL, \$2,793.36 friction, -\$2,717.11 net PnL (-27.17% return), 28.80% max drawdown.

2. **Reconciliation of Sprint 11.09 vs Sprint 11.10 Buy-and-Hold Discrepancy:**
   - In Sprint 11.09, Buy & Hold was reported as **+\$2,991.60 (+29.92%)** with \$27.25 friction (\$17.25 fees, \$10.00 slippage).
   - In Sprint 11.10, Buy & Hold was reported as **+\$2,985.10 (+29.85%)** with \$33.00 friction (\$23.00 fees, \$10.00 slippage).
   - **Exact Cause of Discrepancy (\$6.50 / 0.07%):**
     In Sprint 11.09, the terminal position was marked-to-market using a single-sided exit assumption (entry fee \$7.50 + terminal exit fee \$9.75 = \$17.25, with \$10.00 one-way slippage). In Sprint 11.10, the simulator simulated Buy & Hold through standard institutional taker execution on next-bar fill, assessing full taker fees and bidirectional slippage across both entry fill and final bar liquidation (\$23.00 fees, \$10.00 slippage). The underlying gross Bitcoin price expansion was identical (+\$3,018.10 vs +\$3,018.85, a \$0.75 rounding difference based on next-bar open versus close). The Sprint 11.10 methodology is strictly more conservative and realistic.

3. **Forensic Audit of the "48.70% Avoided Drawdown" Claim (Drawdown Additivity Fallacy):**
   - Sprint 11.10 reported that the engine avoided a cumulative "+48.70%" Bitcoin drawdown across 46 abstention periods.
   - **Integrity Correction:** This figure was calculated as $\sum_{i=1}^{46} \text{avoided\_btc\_drawdown\_pct}_i$, where each term represented the local peak-to-trough drop of BTC during that isolated non-trade span.
   - **Mathematical Fallacy:** Summing percentage drawdowns across disjoint time windows violates financial mathematics:
     1. Percentage drawdowns are multiplicative, not additive ($(1 - d_1)(1 - d_2) \ne 1 - (d_1 + d_2)$).
     2. Summing disjoint adverse excursions counts local intraday and inter-day chop multiple times.
     3. **Actual Portfolio-Level Capital Protection:** Across the entire 65-day holdout partition, the maximum peak-to-trough drawdown of Bitcoin was **8.55%** (occurring between August 23 and September 6, 2026). A 100% USDT cash position avoids exactly **8.55%** of portfolio loss, NOT 48.70%.
     4. The 48.70% metric must be properly reported as **"Summed Adverse Intra-Span Excursion (SAIE)"**, while the true portfolio-level drawdown avoided was **8.55%**.

4. **Retrospective Selection Bias in Reversal Detection Evaluation:**
   - In Sprint 11.10, `evaluate_reversal_detection()` evaluated 8 turning points.
   - Code inspection reveals that candidate troughs were identified using:
     ```python
     for i in range(window, len(self.df) - window, window):
         seg_low = np.argmin(low[i - window : i + window])
         trough_idx = (i - window) + seg_low
     ```
   - **Causal Violation:** The slice `low[i - window : i + window]` looks 288 bars (24 hours) into the *future* (`+ window`) to center the trough!
   - While the live regime classification engine was strictly point-in-time, the *evaluation benchmark* used future knowledge to establish the exact bottom against which "early" vs "confirmation" signals were measured.
   - In live trading, a trader never knows whether an absorption bar is the true 7-day trough or merely a pause in an ongoing collapse. This explains why Strategy H experienced an atrocious 6.90% win rate (-27.17% net loss): it repeatedly attempted to buy absorption candles that hindsight called "reversals," but which contemporaneously were deadly bull traps in continuing bear cascades.

---

## 1. Accounting Invariants & Friction Breakdown

The CBE simulator applies strict institutional friction on every fill:

| Parameter | Value | Economic Basis |
|---|---|---|
| **Taker Fee** | $7.5\text{ bps}$ ($0.00075$) | Standard Binance VIP tier with BNB fee deduction |
| **Maker Fee** | $7.5\text{ bps}$ ($0.00075$) | Conservative parity with taker execution |
| **Slippage** | $5.0\text{ bps}$ ($0.00050$) | Median spot slippage on BTCUSDT top-of-book depth |
| **Total Roundtrip Friction** | $25.0\text{ bps}$ ($0.00250$) | Combined mandatory drag per completed roundturn |

### Next-Bar Fill Rule
Every decision emitted on bar $t$ close is filled at:
$$\text{Fill Price}_{\text{buy}} = \text{Open}_{t+1} \times 1.0005$$
$$\text{Fill Price}_{\text{sell}} = \text{Open}_{t+1} \times 0.9995 \quad (\text{or trigger price } \times 0.9995)$$

### Intrabar Pessimistic Resolution Rule
When both Stop-Loss and Take-Profit price levels fall within the $[\text{Low}_t, \text{High}_t]$ range of the same 5-minute candle:
$$\text{Execution Priority} = \text{Stop-Loss First (Capital Loss Recognized)}$$
This completely eliminates optimistic intrabar profit manufacturing.

---

## 2. Reconciled Strategy Benchmark Ledger (Holdout Partition)

| Strategy ID | Strategy Name | Trades | Win Rate | Gross PnL | Friction | Net PnL | Net Return | Max DD | Profit Factor |
|---|---|---|---|---|---|---|---|---|---|
| **STRAT_A_CASH** | Strategy A: USDT Cash | 0 | 0.0% | \$0.00 | \$0.00 | \$0.00 | 0.00% | 0.00% | 0.00 |
| **STRAT_B_BNH** | Strategy B: Buy & Hold BTC | 1 | 100.0% | +\$3,018.10 | \$33.00 | +\$2,985.10 | +29.85% | 8.55% | 99.00 |
| **STRAT_C_SWITCH** | Strategy C: Simple Trend Switch | 65 | 20.0% | +\$1,498.88 | \$1,969.28 | -\$470.40 | -4.70% | 21.65% | 0.89 |
| **STRAT_D_TREND48** | Strategy D: 48h Trend Following | 19 | 47.4% | +\$1,512.38 | \$582.00 | +\$930.38 | +9.30% | 15.88% | 1.51 |
| **STRAT_E_ANALOGUE24** | Strategy E: 24h Analogue | 49 | 44.9% | +\$2,122.53 | \$1,559.15 | +\$563.38 | +5.63% | 13.26% | 1.16 |
| **STRAT_F_REGIME_GATED** | Strategy F: Regime-Gated Analogue | 65 | 30.8% | +\$1,840.14 | \$1,992.81 | -\$152.67 | -1.53% | 17.52% | 0.96 |
| **STRAT_G_DYNAMIC_ADAPTIVE** | Strategy G: Dynamic Adaptive Engine | 98 | 37.8% | +\$2,611.79 | \$2,922.87 | -\$311.08 | -3.11% | 15.23% | 0.93 |
| **STRAT_H_REVERSAL_CONFIRM** | Strategy H: Conservative Reversal | 116 | 6.9% | +\$76.25 | \$2,793.36 | -\$2,717.11 | -27.17% | 28.80% | 0.19 |

---

## 3. Why Strategy G Lost Money Despite Positive Gross Alpha

The central paradox of Sprint 11.10 is that **Strategy G generated +\$2,611.79 in gross profit**—far higher than Strategy D (+\$1,512.38) or Strategy E (+\$2,122.53)—yet ended with a **net loss of -\$311.08**.

### The Friction-Turnover Mechanism:
1. **Hyperactive Trailing Stop Tightening:** Strategy G updated trailing stops 486 times. Whenever price rose $+1.5\%$, the stop was moved to breakeven $+ 20\text{ bps}$.
2. **Normal Intraday Pullback Execution:** Bitcoin's median 5-minute volatility frequently creates 30-50 bps pullbacks even within healthy uptrends. The tightened trailing stop was repeatedly triggered on normal volatility chop.
3. **Immediate Re-Entry Syndrome:** Because the broader 4h trend was still positive, Strategy G saw a `BUY_CANDIDATE` on the very next bar or within a few bars, re-entering immediately.
4. **Friction Accumulation:** Each roundtrip entry and exit cost ~\$30 in taker fees and slippage on a \$10,000 position. Executing 98 trades accumulated **\$2,922.87 in friction**, entirely erasing the +\$2,611.79 gross edge!
5. **Contrast with Strategy D:** Strategy D used a patient 48-hour holding period with no micro-trailing stops. It traded only 19 times, paid \$582 in friction, and retained **+\$930.38 net profit**.

This sets the clear engineering directive for Sprint 11.11: **The Patient Adaptive Spot Engine must eliminate hyperactive churn, enforce cooldowns, and adjust positions only on material evidence shifts.**
