# CBE — Product Acceleration Sprint 03: Next Priorities (Sprint 04 Roadmap)

**Target Environment:** Coolify Linux VPS (`coin.ozelweb.com.tr`)  
**Authorized Scope:** Staging Service Iteration  
**Focus:** Analytical Depth, Volatility Modeling & Interactive Research Capabilities  

---

## 1. High-Priority Product Capabilities for Sprint 04

With the staging runtime repaired, all multi-year Parquet datasets bundled, and full interactive charting operational, the next sprint can focus on deep analytical tooling:

### Priority 1: Interactive Regime Transition Hazard Model
- **Objective:** Render real-time regime transition probability matrix and hazard rates directly inside the Market Behavior module.
- **Specification:**
  - Visualize 5-state Markov chain transition probabilities conditional on current duration in regime.
  - Overlay expected regime flip date on the primary candlestick chart.
  - Implement survival curves ($S(t)$) for low-volatility accumulation regimes.

### Priority 2: Multi-Asset Comparative Analog Overlays
- **Objective:** Expand analog explorer beyond BTCUSDT to include ETHUSDT, SOLUSDT, and macro benchmarks (SPY, DXY, Gold).
- **Specification:**
  - Cross-asset correlation heatmap across 2022-2026.
  - Beta-adjusted return paths during historical macro surprise events.
  - Multi-series canvas overlay on the research workspace.

### Priority 3: Interactive Strategy Backtest & Risk Horizon Replay
- **Objective:** Provide visual backtest verification for simple momentum and mean-reversion filters without any live execution capabilities.
- **Specification:**
  - Slider controls for lookback window, volatility filter, and holding period.
  - Replay equity curve, maximum drawdown, and Sharpe ratio on historical Parquet partitions.
  - Export backtest results to `research_outputs/`.

### Priority 4: Staging WebSocket Mock Replay
- **Objective:** Simulate real-time streaming market updates using offline Parquet replay over WebSocket.
- **Specification:**
  - Mock ticker and order book delta broadcaster at 1-second intervals.
  - Tests UI tick rendering latency and dynamic candle updates without external exchange connectivity.

---

## 2. Invariant & Governance Requirements

- **Live Trading:** Permanently prohibited.
- **Production Target:** `coin.ozelweb.com.tr` (`6t63aehpaw0cw1bbt4zcm09g`) remains isolated and untouched.
- **Network Acquisition:** Live external exchange collection remains disabled.
