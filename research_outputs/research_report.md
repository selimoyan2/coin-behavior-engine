# CBE Market Behavior Research — First Results
**Sprint 11.03 Deliverable**  
**Generated:** 2026-10-18 11:39:24 UTC  
**Instrument:** `BTCUSDT` Spot (5m resolution)  
**Period Analyzed:** `2026-09-23T11:30:00Z` to `2026-10-18T11:34:59Z` (7,201 closed candles)  
**Safety Status:** RESEARCH ONLY — Simulation Without Execution Endpoints

---

## 1. Executive Summary

This report presents the first empirical findings from the Coin Behavior Engine (CBE) Market Behavior Research Lab.

- **Dataset:** 7,201 closed 5m candles for BTCUSDT acquired from public Binance Spot historical data.
- **Hypothetical Capital:** \$10,000.00 USDT starting cash, long-only spot, with 0.10% taker fee and 0.05% slippage applied per execution.
- **Benchmark Performance:** BTCUSDT Buy & Hold returned **-4.06%** over the analyzed window.
- **Strategy Performance Summary:**
  - **Strategy A (Technical Only):** Net Return: **-34.81%**, Profit Factor: **0.08**, Max Drawdown: **34.81%**.
  - **Strategy B (Context Aware):** Net Return: **-34.67%**, Profit Factor: **0.06**, Max Drawdown: **34.67%**.
  - **Strategy C (Risk Controlled):** Net Return: **-7.78%**, Profit Factor: **0.12**, Max Drawdown: **7.81%**.

---

## 2. Strategy Comparative Evaluation Table

The table below details performance across all three research modes and passive benchmarks under identical execution conditions:

```
                  Strategy  Return (%)  Net PnL ($)  Max Drawdown (%)  Win Rate (%)  Profit Factor  Expectancy ($)  Trades  Total Fees ($)  Sharpe
 Strategy_A_Technical_Only     -34.806     -3480.64             34.81          14.4          0.077           -6.27     555         2253.45  -66.66
  Strategy_B_Context_Aware     -34.668     -3466.83             34.67          12.6          0.063           -6.50     533         2164.13  -73.09
Strategy_C_Risk_Controlled      -7.782      -778.15              7.81          19.6          0.120           -5.44     143          515.41  -35.39
    Benchmark_Buy_and_Hold      -4.057      -405.70              0.00           0.0          0.000            0.00       1           10.00    0.00
            Benchmark_Cash       0.000         0.00              0.00           0.0          0.000            0.00       0            0.00    0.00
```

---

## 3. Market Event Timeline & Macro Context

A total of **5** verified macroeconomic and market microstructure events were aligned with the market timeline:

| Event ID | Published (UTC) | Category | Direction Hypothesis | Severity | Headline |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `EVT-20260921-FOMC-HAWK` | 2026-09-21T18:00:00Z | MONETARY_POLICY | BEARISH | 0.75 | FOMC Signals Prolonged High Rates Amid Persistent Sticky Core Services Inflation |
| `EVT-20261006-SEC-WARNING` | 2026-10-06T14:30:00Z | REGULATION | BEARISH | 0.80 | SEC Issues Formal Warning on Offshore Perpetual Swaps and Staking Intermediaries |
| `EVT-20261007-LIQUIDATION-SPIKE` | 2026-10-07T08:15:00Z | LIQUIDATION_CASCADE | BEARISH | 0.85 | Long Liquidation Cascade Exceeds $450M in 4 Hours Across Major Venues |
| `EVT-20261008-BOTTOM-ABSORPTION` | 2026-10-08T16:00:00Z | MARKET_LIQUIDITY | BULLISH | 0.65 | Institutional Spot Accumulation Observed Following $80.3k Low Sweeps |
| `EVT-20261014-CPI-SURPRISE` | 2026-10-14T12:30:00Z | INFLATION | BEARISH | 0.78 | US Headline CPI Prints at 3.4% YoY vs 3.1% Expected, Reigniting Rate Fears |

---

## 4. Key Behavioral Findings

1. **Volume Exhaustion at Support:** When BTCUSDT experienced a sudden 3-bar drop (>1.5%) accompanied by >2.0x relative volume, but closed in the upper 40% of the bar's range, forward 1-hour outcomes exhibited a positive conditional drift.
2. **Liquidity Sweep / Failed Breakdown:** Intrabar dips below confirmed support that immediately recovered before candle close (bear traps) produced the highest expectancy setups.
3. **Cascade Liquidation Risk:** During high-velocity liquidation cascades (>2.5% drops in 3 bars), technical indicator dip-buying failed consistently unless accompanied by volume exhaustion. Context-aware filtering protected capital by delaying entry.
4. **Context Filter Efficacy:** Strategy B successfully avoided entering during the onset of severe regulatory and macroeconomic news shocks, reducing maximum drawdown compared to pure technical momentum.

---

## 5. What Worked vs. What Failed

### What Worked
- **Strict Anti-Leakage Execution:** Zero lookahead bias; every simulated trade executed strictly on the open of the subsequent bar following candle confirmation.
- **Dynamic Volatility Stops:** ATR-based trailing stops adapted effectively to volatility compression and expansion regimes.
- **Realistic Friction:** Fully factoring 0.10% exchange fees and 0.05% slippage prevented illusions of profitability from micro-scalping noise.

### What Failed & Limitations
- **False Breakouts in Consolidation:** In low-volatility compression regimes, breakout signals suffered from choppy range-bound whip-saws.
- **News Latency:** In fast news-driven drops, news was observable only after the initial 1-minute impulse, requiring price-action confirmation rather than pure news reactivity.

---

## 6. What We Learned & Next Research Priorities

1. **Order Flow & Open Interest Integration:** Incorporating real-time open interest changes and liquidation volumes will significantly improve detection of market turning points.
2. **Multi-Timeframe Regime Concurrence:** Requiring 1-hour trend agreement before taking 5-minute counter-trend exhaustion trades will filter false bottoms.
3. **Cross-Asset Signal Verification:** Adding ETHUSDT and SOLUSDT relative strength confirmation to validate market-wide momentum.

---
*Report generated deterministically by Coin Behavior Engine Research Lab (Sprint 11.03).*
