# CBE — SPRINT PRODUCT ACCELERATION 03 ROADMAP & NEXT PRIORITIES

**Document:** `research_outputs/product_acceleration_02_next_priorities.md`  
**Base Commit:** Sprint Product Acceleration 02 Delivered  
**Governance Status:** `TECHNICAL_NO_GO` / `NOT_GRANTED`  
**Focus:** Visual Event Attribution, Liquidity Depth Analytics & Staging Deployment Execution  

---

## 1. STRATEGIC OVERVIEW

With Sprint 01 delivering the unified 7-module dashboard and Sprint 02 delivering the interactive Candlestick & Analog Explorers, Sprint 03 will focus on connecting the macro news/event catalog directly to the chart timeline and preparing safe, inert live capture telemetry.

---

## 2. PRIORITY OBJECTIVES FOR SPRINT 03

### Priority 1: Macro & Regulatory Event Candlestick Tagging
- **Objective:** Visually project the 40 verified regulatory and monetary events (`research_outputs/verified_macro_events.csv`) directly onto the historical candlestick chart.
- **Features:**
  - Distinct event marker pins along the time axis (e.g., 🏛️ for SEC/regulatory, 🏦 for FOMC/Fed, 📊 for CPI/macro).
  - Hover event tooltip displaying headline, event direction hypothesis, and severity rating.
  - Event Impact Window calculation: automated metric displaying $\Delta P_{15m}$, $\Delta P_{1h}$, and $\Delta P_{24h}$ around the event timestamp.

### Priority 2: Orderbook Depth & Liquidity Stress Visualization
- **Objective:** Add an orderbook liquidity depth inspector to Module 3 using offline historical L2 depth snapshots.
- **Features:**
  - Bid/Ask cumulative depth curve displaying depth imbalance (bid-heavy vs. ask-heavy).
  - Visual demonstration of spread widening during `HIGH_VOLATILITY` and `EXPANSION_WATCH` regimes.
  - Slippage simulator calculating hypothetical market order execution costs across different order sizes ($10k, $100k, $1M).

### Priority 3: Coolify Staging Container Deployment Execution
- **Objective:** Trigger the isolated staging container build on the Coolify Linux VPS.
- **Verification Plan:**
  - Build `cbe-market-intelligence-staging` image on the VPS.
  - Start container on `127.0.0.1:8080:8000`.
  - Validate HTTP 200 OK responses on `/product`, `/health`, and `/api/v1/product/historical-candles`.
  - Verify zero impact on production `coin-behavior-engine` running on the primary port.

### Priority 4: Inert Live Capture Bridge Specification
- **Objective:** Complete the architectural design and sandbox quarantine rules for prospective live capture (`cbe-080-live-capture`).
- **Safety Invariants:**
  - Strictly read-only market observation.
  - Memory-buffered circular queue (no unconstrained disk writes).
  - Zero order submission pathways: all trading endpoints hardcoded to fail-closed `DENYLISTED_TRADING_ENDPOINTS`.

---

## 3. GOVERNANCE AND SECURITY BOUNDARIES

- Production credentials and live trading remain **permanently prohibited**.
- External network requests remain **disabled**.
- All code changes must maintain 100% passing regression status.
