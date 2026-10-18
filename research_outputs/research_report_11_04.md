# CBE Research Lab — Sprint 11.04 Master Research Report
**Title:** Research Integrity, Verified Market Context & First Reliable Strategy Benchmark  
**Generated:** 2026-10-18 11:57:00 UTC  
**Instrument:** `BTCUSDT` Spot (5m resolution)  
**Reconciled Historical Period:** `2026-09-23T11:35:00Z` to `2026-10-18T11:29:59Z` (7,199 complete 5m closed candles)  
**Safety Status:** RESEARCH ONLY — Simulation Without Execution Endpoints

---

## 1. Executive Summary & Core Results

Sprint 11.04 establishes the first verified, scientifically sound benchmark for the Coin Behavior Engine Research Lab.

- **Reconciled Dataset:** Exactly 7,199 complete, contiguous 5-minute candles derived from 35,995 1-minute bars without partial boundary artifacts.
- **Benchmark Buy & Hold:** Net Return: **-4.27%**, Max Drawdown: **8.27%**, Fees: **$19.58**, Sharpe: **-1.59**.
- **Benchmark Cash:** Net Return: **+0.00%**, Max Drawdown: **0.00%**, Fees: **$0.00**.
- **Strategy C (Risk-Controlled & HTF Aligned):** Net Return: **-3.06%**, Max Drawdown: **3.07%**, Fees: **$180.81**.
- **Strategy B (Verified Context Aware):** Explicitly abstained due to zero verified external news permalinks, preserving 100% of capital in Cash ($0.00 PnL, 0.0% drawdown).

---

## 2. Reconciled Strategy Comparison Table

```
                  Strategy  Return (%)  Net PnL ($)  Max Drawdown (%)  Win Rate (%)  Profit Factor  Expectancy ($)  Trades  Total Fees ($)  Fee Drag (%)  Abstention Bars  Sharpe
 Strategy_A_Technical_Only      -9.815      -981.48              9.78          19.7          0.109           -7.16     137          652.56          6.53             6794  -33.59
  Strategy_B_Context_Aware       0.000         0.00              0.00           0.0          0.000            0.00       0            0.00          0.00             7199    0.00
Strategy_C_Risk_Controlled      -3.057      -305.66              3.07          10.2          0.061           -6.24      49          180.81          1.81             7139  -21.55
    Benchmark_Buy_and_Hold      -4.273      -427.30              8.27           0.0          0.000            0.00       1           19.58          0.20                0   -1.59
            Benchmark_Cash       0.000         0.00              0.00           0.0          0.000            0.00       0            0.00          0.00             7199    0.00
```

---

## 3. Chronological Out-of-Sample Split Evaluation

The dataset was partitioned into chronological splits to prevent overfitting:
- **Train (50%):** Bars 0 to 3,599
- **Validation (25%):** Bars 3,599 to 5,399 (encompasses peak and decline)
- **Untouched Test (25%):** Bars 5,399 to 7,199 (post-decline recovery)

| Split | Strategy | Return (%) | Net PnL ($) | Max Drawdown (%) | Win Rate (%) | Trades | Fees ($) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TRAIN_50 | Strategy_A_Technical_Only | -5.99% | $-599.01 | 5.99% | 23.7% | 93 | $450.15 |
| TRAIN_50 | Strategy_B_Context_Aware | +0.00% | $0.00 | 0.00% | 0.0% | 0 | $0.00 |
| TRAIN_50 | Strategy_C_Risk_Controlled | -1.97% | $-197.22 | 1.99% | 9.7% | 31 | $115.06 |
| VAL_25 | Strategy_A_Technical_Only | -2.42% | $-241.51 | 2.46% | 10.7% | 28 | $138.01 |
| VAL_25 | Strategy_B_Context_Aware | +0.00% | $0.00 | 0.00% | 0.0% | 0 | $0.00 |
| VAL_25 | Strategy_C_Risk_Controlled | -0.54% | $-54.11 | 0.56% | 10.0% | 10 | $37.36 |
| TEST_25 | Strategy_A_Technical_Only | -1.69% | $-169.42 | 1.67% | 12.5% | 16 | $79.25 |
| TEST_25 | Strategy_B_Context_Aware | +0.00% | $0.00 | 0.00% | 0.0% | 0 | $0.00 |
| TEST_25 | Strategy_C_Risk_Controlled | -0.57% | $-56.81 | 0.57% | 12.5% | 8 | $29.89 |

---

## 4. Sensitivity Analysis (Transaction Friction & Slippage)

Performance of Strategy C across varying taker fees (0.05%, 0.10%, 0.15%) and slippage levels (0.02%, 0.05%, 0.10%):

```
Taker_Fee_Pct Slippage_Pct  Return_Pct  Net_PnL  Total_Fees  Total_Slippage  Max_Drawdown_Pct  Trades  Win_Rate_Pct
        0.05%        0.02%      -1.623  -162.33       91.09           27.13              1.70      49          26.5
        0.05%        0.05%      -2.163  -216.32       90.81           81.50              2.22      49          22.4
        0.05%        0.10%      -3.056  -305.59       90.39          171.48              3.07      49          10.2
        0.10%        0.02%      -2.522  -252.20      181.34           26.97              2.56      49          18.4
        0.10%        0.05%      -3.057  -305.66      180.81           81.13              3.07      49          10.2
        0.10%        0.10%      -3.940  -394.04      179.94          170.60              3.94      49           8.2
        0.15%        0.02%      -3.412  -341.22      270.76           26.82              3.41      49          10.2
        0.15%        0.05%      -3.941  -394.15      269.96           80.69              3.94      49           8.2
        0.15%        0.10%      -4.816  -481.65      268.62          169.76              4.82      49           4.1
```

---

## 5. Counterfactual Analysis Summary

Detailed counterfactual analysis for top winning and losing trades is exported to [`trade_counterfactuals.csv`](trade_counterfactuals.csv).
Key empirical findings:
1. **Higher-Timeframe Filter:** 80% of top losing trades were counter-trend entries where the 1-hour trend was negative. Enforcing 1-hour alignment avoided these losses entirely.
2. **Execution Drag:** Taker fees and slippage accounted for over 60% of gross drawdowns on 5-minute holding strategies. Lengthening holding horizons to 1-4 hours is essential to achieving an edge.

---
*Report produced by CBE Research Lab (Sprint 11.04).*
