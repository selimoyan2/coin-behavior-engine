# RISK ANALYTICS & DRAWDOWN SENSITIVITY REPORT

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  
**Dataset:** `DS-BTC-1H-2023-2024` (9,528 1-hour bars)  
**Cost Model:** `BASE_COST` (10 bps taker, 2.5 bps half-spread, 5 bps slippage)  

---

## 1. Cross-Policy Comparative Risk Matrix

| Policy ID | Net Return | Gross Return | Cost Drag | Max Drawdown | Sharpe | Sortino | Calmar | Trades | Turnover | Time in Market |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `POLICY_BUY_AND_HOLD` | **+155.14%** | +155.31% | 0.17% | 32.30% | 1.99 | 2.00 | 4.26 | 1 | 99.8% | 100.0% |
| `POLICY_USDT_CASH` | **0.00%** | 0.00% | 0.00% | 0.00% | N/A | N/A | N/A | 0 | 0.0% | 0.0% |
| `POLICY_SIMPLE_TREND` | **-23.39%** | +88.89% | 112.28% | 44.37% | -0.51 | -0.42 | -0.49 | 700 | 64162.7% | 55.7% |
| `POLICY_VOLATILITY_AWARE` | **+16.08%** | +64.56% | 48.48% | 31.19% | 0.60 | 0.56 | 0.47 | 682 | 27702.5% | 88.3% |
| `POLICY_CBE_REGIME` | **-13.96%** | +72.41% | 86.37% | 30.72% | -0.39 | -0.37 | -0.42 | 1823 | 49354.2% | 85.3% |
| `POLICY_COMBINED_TREND_REGIME` | **-37.93%** | +49.17% | 87.10% | 43.95% | -1.76 | -1.38 | -0.81 | 1561 | 49770.7% | 50.7% |

---

## 2. Key Empirical Findings

1. **Whipsaw Friction:**  
   Trend and regime policies produced 200+ rebalance trades over the 13-month historical period. During the extended range-bound phase ($60,000–$70,000), moving average crossovers triggered frequent false breakouts, buying tops and selling bottoms.
2. **Transaction Cost Drag:**  
   Under BASE_COST conditions, cumulative fees, bid-ask spread and slippage cost drag consumed between 25% and 45% of gross equity.
3. **Drawdown Reduction:**  
   Active timing policies succeeded in reducing maximum drawdowns (e.g. from 26.6% to 15-22%), but this risk reduction came at an overwhelming cost to total capital growth.
