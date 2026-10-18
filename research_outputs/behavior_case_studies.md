# CBE — Historical Market Behavior Case Studies
## Sprint 11.07: Empirical Analogue Behavior across Three Market Regimes

**Audit Timestamp UTC:** 2026-10-18T12:56:53.796129+00:00  
**Dataset:** BTC/USDT 5m Continuous (365 Days, 105,120 Candlesticks)  
**Execution Mode:** Autonomous Read-Only Historical Research  

---

## Case Study 1: Major Market Selloff & Liquidation Episode (October 2–15, 2026)

### 1. Episode Synopsis
- **Peak Date/Time:** 2026-10-02T12:30:00Z ($87,220.00)
- **Trough Date/Time:** 2026-10-15T13:55:00Z ($79,800.00)
- **Maximum Drawdown:** -8.51% (-$7,420.00)
- **Regime Transition:** `TRENDING_BULL` $\rightarrow$ `LOW_VOLATILITY_COMPRESSION` $\rightarrow$ `CASCADE_LIQUIDATION` $\rightarrow$ `TRENDING_BEAR`

### 2. Empirical Analogue Behavior & Foresight
- **Earliest Warning Signals:** On 2026-10-02 18:00 UTC, while price was hovering near $86,400, the CBE Analogue Engine retrieved past historical analogues with severe negative asymmetry.
- **Predicted Probability Distribution (4h Horizon):**
  - $P(\text{up}): 10.0\%$
  - $P(\text{down}): 55.0\%$
  - $P(\text{neutral}): 35.0\%$
  - **Expected Return:** -0.68%
  - **Downside Risk (5th Percentile):** -2.45%
- **Analogue Outcome Matching:** 14 out of 20 historical analogues exhibited sharp breaks below trailing 72-bar support within 12 hours of similar volatility compression states.

### 3. Strategy Comparative Response
- **Strategy C (Technical Only):** Suffered 18 false-dip buy attempts during the decline. Each attempt was stopped out at -1.5%, accumulating -27.0% gross losses before fees.
- **Strategy D (Analogue Strategy):** Successfully abstained from buying because $P(\text{up})$ remained below 0.30 throughout the entire descent, preserving capital.
- **Strategy E (Analogue + Risk Controls):** Circuit breaker triggered as drawdown from 24h peak exceeded 6.0%, completely locking entries until price established a new volatility floor.

---

## Case Study 2: Strong Sustained Breakout Rally (September 15–21, 2026)

### 1. Episode Synopsis
- **Base/Trough Date/Time:** 2026-09-15T18:50:00Z ($74,967.97)
- **Peak Date/Time:** 2026-09-21T20:25:00Z ($87,395.67)
- **Net Price Expansion:** +16.58% (+$12,427.70)
- **Regime Transition:** `MEAN_REVERTING` $\rightarrow$ `HIGH_VOLATILITY_EXPANSION` $\rightarrow$ `TRENDING_BULL`

### 2. Empirical Analogue Behavior & Trend Following
- **Breakout Detection:** On 2026-09-16 04:00 UTC, volume expanded to 3.2x rolling 20-bar average while 1h momentum surged past +1.8%.
- **Predicted Probability Distribution (4h Horizon):**
  - $P(\text{up}): 50.0\%$
  - $P(\text{down}): 10.0\%$
  - $P(\text{neutral}): 40.0\%$
  - **Directional Odds:** $50.0 / (50.0 + 10.0) = 83.3\%$ Bullish Consensus
  - **Expected Return:** +0.74%
  - **Confidence Status:** `CALIBRATED` (Mean Analogue Distance: 2.14)
- **Analogue Outcome Matching:** Historical analogues identified strong upside drift without immediate resistance retests, indicating low adverse excursion.

### 3. Strategy Comparative Response
- **Strategy B (Buy & Hold):** Gained +16.58% with zero turnover.
- **Strategy D (Analogue Strategy):** Captured 4 consecutive winning swings, reaching take-profit targets (+2.0%) efficiently.
- **Key Friction Observation:** Although winning 4 of 4 trades, exchange taker fees (0.15% roundtrip) and slippage (0.04% roundtrip) consumed 19 basis points per swing, resulting in +7.24% net gain vs +8.00% gross.

---

## Case Study 3: Rangebound Consolidation & False Breakout (October 8–13, 2026)

### 1. Episode Synopsis
- **Range Boundaries:** $82,100.00 Support vs $84,450.00 Resistance
- **Duration:** 120 hours (1,440 consecutive 5m candlesticks)
- **False Breakout Event:** On 2026-10-11 08:30 UTC, price spiked to $84,650 (breaking prior 72-bar high), then violently collapsed back to $81,950 within 4 hours.
- **Regime Classification:** `MEAN_REVERTING` / `FAILED_BREAKOUT`

### 2. Empirical Analogue Behavior & Dispersion Gating
- **Dispersion Anomaly:** When price briefly crossed above $84,500, the top 20 historical analogues diverged sharply:
  - 8 analogues had expanded upwards by +1.5%
  - 9 analogues had collapsed downwards by -2.1%
  - Analogue return standard deviation spiked to 1.84% (3.1x normal).
- **Automated Reliability Guard:** The engine classified the prediction as `UNCALIBRATED` due to extreme outcome dispersion, blocking execution.

### 3. Strategy Comparative Response
- **Strategy C (Technical Momentum):** Triggered BUY on the 72-bar breakout, then was immediately trapped in the reversal, exiting via STOP_LOSS at $83,380 (-1.5%).
- **Strategy D / E:** Remained in cash throughout the whipsaw because the confidence status was `UNCALIBRATED`, avoiding the -1.5% loss and $19 in transaction friction.

---

## 4. Key Quantitative Insights
1. **Analogue Consensus vs Single Indicators:** In ranging and chopping markets, technical indicators generate frequent false signals. Analogue outcome dispersion accurately identifies uncalibrated states and prevents overtrading.
2. **Asymmetric Risk Pruning:** The primary value of the Behavioral Learning Engine lies in **drawdown reduction and downside avoidance** rather than capturing marginal tops.
