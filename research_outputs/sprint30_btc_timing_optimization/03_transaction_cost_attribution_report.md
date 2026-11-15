# 03 — Transaction Cost Attribution & Excessive Trading Diagnostics Report

**Sprint ID:** `CBE_SPRINT30_BTC_TIMING_OPTIMIZATION`  
**Dataset:** `DS-BTC-1H-2023-2024` (9,528 continuous hourly candles)  
**Cost Model:** `BASE_COST` (10 bps fee, 5 bps spread, 10 bps slippage)  

---

## 1. Monetary Transaction Cost Decomposition

The table below decomposes the total transaction costs into its three economic components:
1. **Exchange Commission Fees:** Direct exchange taker fee (0.10%).
2. **Half-Spread Liquidity Costs:** Cost of crossing the bid-ask spread (0.025%).
3. **Execution Slippage:** Adverse market impact (0.05%).

| Policy ID | Trade Count | Traded Notional ($) | Total Fees ($) | Total Spread ($) | Total Slippage ($) | Total Cost ($) | Fee Drag (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POLICY_SIMPLE_TREND` | 700 | $6,416,273.92 | $6,416.27 | $1,604.07 | $3,208.14 | $11,228.48 | 112.28% |
| `POLICY_VOLATILITY_AWARE` | 682 | $2,770,254.22 | $2,770.25 | $692.56 | $1,385.13 | $4,847.95 | 48.48% |
| `POLICY_CBE_REGIME` | 1823 | $4,935,416.10 | $4,935.42 | $1,233.85 | $2,467.71 | $8,636.98 | 86.37% |
| `POLICY_COMBINED_TREND_REGIME` | 1561 | $4,977,071.81 | $4,977.07 | $1,244.27 | $2,488.54 | $8,709.88 | 87.10% |

---

## 2. Root Cause Analysis of Excessive Trading in Sprint 29 Policies

### 1. Simple Moving Average Trend Filter (700 trades, 641.6x turnover)
- **Primary Driver:** MA Crossover Whipsaws.
- During the $60,000–$70,000 consolidation range (March–October 2024), BTC price repeatedly crossed the 50-hour SMA back and forth.
- Because the policy had zero hysteresis buffer, each minor cross triggered a binary 100% position flip (0% BTC <-> 100% BTC), resulting in 571 whipsaw reversals within 24 hours.

### 2. Volatility-Aware Allocation (682 trades, 442.2x turnover)
- **Primary Driver:** Continuous Volatility Quantile Churn.
- Parkinson rolling volatility crossed quantile thresholds frequently, triggering continuous small rebalancing orders on price drift without an economic minimum notional threshold.

### 3. Derived Regime Allocation (1,823 trades, 493.5x turnover)
- **Primary Driver:** Hourly Regime State Oscillation.
- Because market regimes were evaluated hourly without multi-bar confirmation, transient 1-hour noise in return z-scores caused continuous allocation flipping.

---

## 3. Structural Mitigations Implemented in Sprint 30

1. **Hysteresis Bands (±2%):** Prevents binary flips on moving average touches.
2. **Minimum Holding Periods (72 hours):** Locks exposure to eliminate intraday whipsaw.
3. **Minimum Rebalance Threshold (10%):** Rejects rebalances where allocation shifts by less than 10%.
4. **Scheduled Frequency (Weekly):** Rebalances only on Monday 00:00 UTC.
