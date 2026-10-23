# CBE — Product Acceleration: Next Priorities Roadmap
## Post-Sprint 01 Implementation Roadmap

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9`  
**Focus:** Immediate High-Impact Product Capabilities  
**Date:** 2026-10-23  

---

### Priority 1: Staging Deployment & Coolify Smoke Verification
- **Objective:** Deploy the new Product Dashboard to the isolated staging container (`cbe-market-intelligence-staging`) on `coin.ozelweb.com.tr:8080`.
- **Requirements:**
  - Explicit operator authorization.
  - Zero disruption to production services or volumes.
  - Verification of all 7 dashboard tabs and the 8 new `/api/v1/product/*` endpoints via reverse proxy.

### Priority 2: Interactive Historical Candlestick & Regime Timeline (Canvas/SVG)
- **Objective:** Enable visual exploration of the multi-year BTCUSDT Parquet archive directly in the Market Behavior tab.
- **Requirements:**
  - Lightweight HTML5 Canvas / SVG rendering (zero heavyweight third-party charting libraries).
  - Bounded window aggregation (e.g. 500 candles at 1h or 4h resolution) to maintain sub-10 ms API latency.
  - Regime shading overlay (visualizing Compression, Normal, and High Volatility regimes on historical price action).

### Priority 3: Interactive Analog Similarity Explorer
- **Objective:** Allow operators to select any historical candle window and visualize its top-5 nearest historical analogs retrieved by the Analog Engine.
- **Requirements:**
  - Consume pre-computed Euclidean and DTW distance surfaces from `data/analogs/` or `research_outputs/`.
  - Display side-by-side pattern comparisons and subsequent forward trajectory dispersion.
  - Maintain prominent disclosure that analog matching provides volatility distribution bounds, not directional alpha.

### Priority 4: Macroeconomic Surprise & Volatility Reaction Heatmap
- **Objective:** Provide a visual calendar heatmap connecting the 40 verified macro events (SEC, FOMC, Discount Rate) with subsequent 5m/1h/4h ATR expansions.
- **Requirements:**
  - Interactive event drilldown displaying the exact claim, source docket, and market reaction envelope.
  - Keep unverified BLS CPI candidate strictly quarantined until official cryptographic authorization.

### Priority 5: Native Linux Benchmark Qualification (Physical Hardware)
- **Objective:** Resolve the 5 known WSL2 VHDX virtual SCSI disk sync latency bounds when dedicated native Linux NVMe hardware becomes available.
- **Policy Invariant:** In the meantime, do not weaken `os.fsync`, skip tests, or manipulate benchmark thresholds on Windows desktop hosts.
