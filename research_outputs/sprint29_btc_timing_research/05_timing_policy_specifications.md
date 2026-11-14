# TIMING POLICY MATHEMATICAL SPECIFICATIONS

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  
**Number of Supported Policies:** 6  

---

## 1. Policy Inventory & Target Allocation Rules

### Policy 1: Buy and Hold (`POLICY_BUY_AND_HOLD`)
- **Mathematical Rule:** Target BTC allocation $w_{BTC} = 1.0$ at all times.
- **Description:** Fully invested in BTC, never rebalances after initial purchase. Standard baseline benchmark.

### Policy 2: 100% USDT Cash (`POLICY_USDT_CASH`)
- **Mathematical Rule:** Target BTC allocation $w_{BTC} = 0.0$ at all times.
- **Description:** Zero BTC exposure, holds 100% USDT cash. Zero return, zero volatility, zero drawdown. Risk-free benchmark.

### Policy 3: Simple Trend Following (`POLICY_SIMPLE_TREND`)
- **Mathematical Rule:**
  $$w_{BTC} = \begin{cases} 1.0 & \text{if } SMA(20) \ge SMA(50) \\ 0.0 & \text{if } SMA(20) < SMA(50) \end{cases}$$
- **Description:** Classic dual moving average crossover. Fully invested in upward momentum; fully cash in downward momentum.

### Policy 4: Volatility-Aware Sizing (`POLICY_VOLATILITY_AWARE`)
- **Mathematical Rule:**
  Base signal $S = 1$ if $SMA(20) \ge SMA(50)$ else $0$.
  $$w_{BTC} = \begin{cases} 
  1.0 & \text{if } S = 1 \text{ and VolRegime} \in \{\text{COMPRESSED, NORMAL}\} \\
  0.50 & \text{if } S = 1 \text{ and VolRegime} = \text{HIGH} \\
  0.25 & \text{if } S = 1 \text{ and VolRegime} = \text{EXTREME} \\
  0.0 & \text{if } S = 0
  \end{cases}$$
- **Description:** Scales down exposure during elevated volatility to mitigate tail risk and drawdowns.

### Policy 5: CBE Regime Policy (`POLICY_CBE_REGIME`)
- **Mathematical Rule:**
  $$w_{BTC} = \begin{cases} 
  1.0 & \text{if Regime} = \text{MOMENTUM\_EXPANSION} \\
  0.50 & \text{if Regime} = \text{MEAN\_REVERTING} \\
  0.25 & \text{if Regime} = \text{HIGH\_VOLATILITY\_EXPANSION} \\
  0.0 & \text{if Regime} = \text{CAPITULATION}
  \end{cases}$$
- **Description:** Directly maps frozen CBE-0.7.0 market state classifications into target portfolio weights.

### Policy 6: Combined Trend + Regime Policy (`POLICY_COMBINED_TREND_REGIME`)
- **Mathematical Rule:**
  $$w_{raw} = 0.5 \cdot w_{trend} + 0.5 \cdot w_{regime}$$
  Snapped to nearest discrete grid weight $\{0.0, 0.25, 0.50, 0.75, 1.0\}$.
- **Description:** Hybrid multi-factor policy combining classical trend confirmation with machine learning regime state classification.
