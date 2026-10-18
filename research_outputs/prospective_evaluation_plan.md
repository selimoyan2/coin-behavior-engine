# CBE Prospective Evaluation Plan: Statistical Hypotheses, Metrics & Verification Horizon

**Document ID:** `PEP-SPRINT-11-15`  
**Version:** `1.0.0-frozen`  
**Effective Date:** `2026-10-18T21:00:00Z`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `7ee1104564cfe2283d234284e220d0ef06f40963`  
**Execution Standard:** Canonical Execution Policy V2 (30.0 bps nominal roundtrip friction)  
**Readiness Status:** `PRE-REGISTERED & LOCKED`  

---

## 1. Executive Purpose & Evaluation Scope

This document specifies the rigorous quantitative framework, statistical hypotheses, and verification milestones governing the future prospective shadow evaluation of the Coin Behavior Engine (CBE).

To eliminate selection bias, **all evaluation criteria are fixed prior to the arrival of the first prospective data point**. No metric, hypothesis, or evaluation window may be modified once observation commences.

---

## 2. Prospective Horizon & Minimum Sample Requirements

```
Prospective Observation Window: 30 Calendar Days (8,640 consecutive 5m candles)
                                     │
      ┌──────────────────────────────┼──────────────────────────────┐
      ▼                              ▼                              ▼
Week 1 (Days 1–7)             Week 2 (Days 8–14)             Weeks 3–4 (Days 15–30)
2,016 candles                  2,016 candles                  4,608 candles
Data Pipeline Integrity        First Regime Transition        Full Sample Statistical Test
```

### Statistical Power & Sample Size Invariants:
1. **Minimum Duration:** 30 continuous calendar days ($8,640$ consecutive 5-minute bars).
2. **Minimum Trade Cycles:** At least 20 completed roundtrip trade cycles per active candidate policy.
   - *Rationale:* With $N < 20$, the standard error of the mean return is too wide to reject $H_0$ at the $\alpha = 0.05$ significance level.
3. **Regime Representation:** The prospective window must contain at least two distinct classified market regimes (e.g., Sideways + Trend, or Bull + Bear Cascade). If the entire 30-day window remains within a single ultra-tight compression regime ($< 3.0\%$ ATR), the evaluation window extends until a regime transition occurs.

---

## 3. Pre-Registered Statistical Hypotheses

All candidate policies will be evaluated against formal null hypotheses:

### Hypothesis 1: Absolute Economic Significance (vs. USDT Cash)
- **Null Hypothesis ($H_{0,1}$):** Under 30 bps roundtrip friction, the mean net trade return of the candidate policy is non-positive:
  $$H_{0,1}: \mu_{\text{net}} \le 0.0\%$$
- **Alternative Hypothesis ($H_{1,1}$):** The candidate policy achieves positive net return after all fees and slippage:
  $$H_{1,1}: \mu_{\text{net}} > 0.0\% \quad (\alpha = 0.05, \text{one-tailed } t\text{-test})$$

### Hypothesis 2: Risk-Adjusted Edge (vs. BTC Buy-and-Hold)
- **Null Hypothesis ($H_{0,2}$):** The annualized Sharpe ratio of the candidate policy is less than or equal to the Buy-and-Hold benchmark:
  $$H_{0,2}: \text{Sharpe}_{\text{policy}} \le \text{Sharpe}_{\text{BNH}}$$
- **Alternative Hypothesis ($H_{1,2}$):** The candidate policy generates superior risk-adjusted returns:
  $$H_{1,2}: \text{Sharpe}_{\text{policy}} > \text{Sharpe}_{\text{BNH}} \quad (\text{Jobson-Korkie test with Ledoit-Wolf correction})$$

### Hypothesis 3: Selective Entry Value (vs. Unfiltered Trend Following)
- **Null Hypothesis ($H_{0,3}$):** The multi-timeframe selective entry gates do not reduce net loss or increase net return compared to the unconstrained 48h trend model (Policy C):
  $$H_{0,3}: \text{Net PnL}_{\text{Policy D}} \le \text{Net PnL}_{\text{Policy C}}$$
- **Alternative Hypothesis ($H_{1,3}$):** Selective gating suppresses false breakouts and significantly conserves capital:
  $$H_{1,3}: \text{Net PnL}_{\text{Policy D}} > \text{Net PnL}_{\text{Policy C}}$$

### Hypothesis 4: Abstention Efficiency (Avoided Drawdown vs. Opportunity Cost)
- **Null Hypothesis ($H_{0,4}$):** Total avoided drawdown achieved by remaining in USDT is less than or equal to total opportunity cost incurred:
  $$H_{0,4}: \sum \text{Avoided DD} \le \sum \text{Opportunity Cost}$$
- **Alternative Hypothesis ($H_{1,4}$):** Remaining in cash delivers net positive defensive economic value:
  $$H_{1,4}: \sum \text{Avoided DD} > \sum \text{Opportunity Cost}$$

---

## 4. Master Evaluation Scorecard Metrics

On every evaluation checkpoint, the five frozen candidate policies will be compiled into the standardized scorecard:

| Metric Category | Specific Indicator | Mathematical Definition / Operational Formula | Target Threshold |
|---|---|---|:---:|
| **Capital & Return** | Starting Equity | Nominal initial USDT cash balance | $\$10,000.00$ |
| | Ending Equity | Final marked-to-market portfolio value | $> \$10,000.00$ |
| | Total Net Return (%) | $\frac{\text{Ending Equity} - \text{Starting Equity}}{\text{Starting Equity}} \times 100\%$ | $> 0.0\%$ |
| | Annualized Return (%) | Net Return scaled to 365.25 days | Benchmark |
| **Risk & Volatility** | Max Peak-to-Trough Drawdown (%) | $\max_{t} \left( \frac{\max_{s \le t} E_s - E_t}{\max_{s \le t} E_s} \right) \times 100\%$ | $< 12.0\%$ |
| | Annualized Sharpe Ratio | $\frac{\bar{r}_{\text{excess}}}{\sigma_r} \times \sqrt{105,120}$ | $> 1.00$ |
| | Annualized Sortino Ratio | $\frac{\bar{r}_{\text{excess}}}{\sigma_{\text{downside}}} \times \sqrt{105,120}$ | $> 1.50$ |
| **Trade Execution** | Completed Trade Cycles | Count of closed roundtrip trades | $\ge 20$ |
| | Win Rate (%) | $\frac{\text{Profitable Trades}}{\text{Completed Trades}} \times 100\%$ | $> 45.0\%$ |
| | Profit Factor | $\frac{\sum \text{Gross Gains}}{\sum \|\text{Gross Losses}\|}$ | $> 1.30$ |
| | Total Friction Drag ($) | $\sum (\text{Taker Fees} + \text{Slippage})$ | Minimal |
| **Abstention Value** | Time in USDT (%) | $\frac{\text{Bars in Cash}}{\text{Total Bars}} \times 100\%$ | Contextual |
| | Cumulative Avoided Drawdown (%)| $\sum \text{Avoided DD across cash windows}$ | Informational |
| | Cumulative Opportunity Cost ($)| $\sum \text{Opportunity Cost across cash windows}$ | Informational |
| | Abstention Net Edge ($) | $\text{Avoided DD Value} - \text{Opportunity Cost}$ | $> \$0.00$ |
| **Integrity & Audit** | Conservation Invariant Discrepancy | $\|\text{Start} + \text{Gross} - \text{Friction} - \text{End}\|$ | $\equiv \$0.00$ |
| | Hash Chain Audit Verdict | $O(N)$ cryptographic verification result | `PASS` |
| | Data Missingness Ratio (%) | $\frac{\text{NO\_DECISION\_DATA bars}}{\text{Total bars}} \times 100\%$ | $< 1.0\%$ |

---

## 5. Candidate Policy Matrix Under Evaluation

The prospective pipeline executes all 5 candidate policies in parallel over identical market inputs:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       5 FROZEN CANDIDATE POLICIES                           │
├────────────────────────────────┬────────────────────────────────────────────┤
│ Policy A: USDT Cash            │ Passive risk-free preservation benchmark   │
│ Policy B: BTC Buy-and-Hold     │ Beta benchmark (98% initial spot hold)     │
│ Policy C: Trend 48h Following  │ Classic unconstrained momentum baseline    │
│ Policy D: Selective Trend-Only │ Multi-timeframe trend + anti-chase + ATR   │
│ Policy E: Selective Analogue   │ Policy D gates + historical analogue skew  │
└────────────────────────────────┴────────────────────────────────────────────┘
```

---

## 6. Multi-Horizon Causally Decoupled Outcomes

Every decision $D_t$ logged to the hash chain is evaluated across multiple forward horizons in the decoupled outcome ledger:

1. **Horizon 12h (144 bars):** Short-term momentum persistence and immediate entry adverse excursion (MAE).
2. **Horizon 24h (288 bars):** Standard single-day holding period outcome.
3. **Horizon 48h (576 bars):** Medium-term trend continuation window.
4. **Horizon 72h (864 bars):** Maximum swing cycle horizon.

For each horizon, the outcome record computes:
- Maximum Favorable Excursion (MFE %)
- Maximum Adverse Excursion (MAE %)
- Realized Net PnL under Policy V2 stops
- Avoided Drawdown % (for `WAIT_USDT` decisions)
- Missed Appreciation % (for `WAIT_USDT` decisions)

---

## 7. Periodic Review Milestones & Verification Timeline

| Milestone | Horizon | Automated Verification Deliverables | Failure Triggers |
|---|---|---|---|
| **Checkpoint 1** | Day 7 (2,016 bars) | Feed integrity audit, latency audit, zero lookahead check | Data missingness $> 2.0\%$ |
| **Checkpoint 2** | Day 14 (4,032 bars) | Mid-point hash chain verification, trade cycle check | Hash chain broken |
| **Checkpoint 3** | Day 21 (6,048 bars) | Drawdown & circuit breaker audit, regime check | Drawdown $\ge 15.0\%$ |
| **Checkpoint 4** | Day 30 (8,640 bars) | Full statistical hypothesis testing, final master report | Sample $< 20$ trades (extend) |

---

## 8. Post-Evaluation Acceptance Criteria

At the conclusion of Day 30:
1. A candidate policy is deemed a **Viable Live Trading Candidate** if and only if:
   - $H_{0,1}$ is rejected at $p < 0.05$ (statistically significant positive net return).
   - Ending Equity exceeds Policy A (Cash).
   - Max Drawdown is strictly $< 15.0\%$.
   - Cryptographic hash chain verification passes with 100% integrity.
2. If no candidate policy achieves statistical significance:
   - The engine concludes that spot BTC algorithmic alpha under 30 bps friction cannot be confirmed.
   - The default recommendation remains **100% USDT Cash** or **Passive Buy-and-Hold**, strictly rejecting active deployment.
