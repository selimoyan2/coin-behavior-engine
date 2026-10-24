# CBE — Product Acceleration Sprint 07 Delivery Report
## Deterministic Multi-Timeframe Data Pipeline, Comparative Market Research Workbench, Regime Drift Intelligence & Research Reliability

**Repository:** `selimoyan2/coin-behavior-engine`  
**Target Infrastructure:** Coolify Linux VPS `srv1114257` (`168.231.125.238`)  
**Staging Service:** `cbe-market-intelligence-staging` (`dzzfws54by1whlbq6fk4ywut`) bound to `127.0.0.1:18080->8000/tcp`  
**Production Container:** `e27157318ede` (`6t63aehpaw0cw1bbt4zcm09g`) — Verified Unmodified  
**Delivery Git Commit:** `bca29faa4963bf720576bab319dfb78aff435cf7` (`bca29faa`)  
**Deployment Reconciliation:** Live Container `bca29faa` == Git HEAD `bca29faa` == Staging `.env` `bca29faa` (100% Match)  
**Overall Automated Tests:** 94 / 94 Passing (100% Pass Rate in 11.62s)  
**Browser Acceptance:** 16 Screenshots Captured via Headless Chromium (100% Pass)  

---

## 1. Executive Summary & Capabilities Delivered

Sprint 07 delivers significant quantitative research expansion to Coin Behavior Engine, directly addressing the core operator directive for accelerated, evidence-based market research workbench capabilities without micro-sprints or synthetic data fabrication.

### Core Deliverables:
1. **Deterministic Multi-Timeframe Dataset Derivation Engine:**
   - Implemented in `src/coin_behavior_engine/product/timeframe_derivation.py`.
   - Derives higher timeframe bars ($15m$, $1h$, $4h$, $1d$) strictly from canonical $5m$ source partitions.
   - Vectorized OHLCV aggregation: Open = first sub-bar open, High = max sub-bar high, Low = min sub-bar low, Close = last sub-bar close, Volume = sum of sub-bar volume.
   - Verified zero discrepancy against canonical Binance archive partitions for September 2026:
     - 15m (2,880 candles): price diff = 0.0, volume diff = 2.27e-13.
     - 1h (720 candles): price diff = 0.0, volume diff = 4.54e-13.
     - 4h (180 candles): price diff = 0.0, volume diff = 4.54e-13.
     - 1d (30 candles): price diff = 0.0, volume diff = 3.63e-12.
   - Strict incomplete window dropping: windows with fewer than expected sub-bars are dropped to avoid distorted candle geometries.

2. **Interactive Comparative Historical Market Workbench:**
   - Backend engine implemented in `src/coin_behavior_engine/product/comparative_workbench.py`.
   - Dedicated UI tab `#module-comparison` ("Karşılaştırma Laboratuvarı") in `dashboard_ui.py`.
   - Dual-period parameter controls (Period A & Period B) with independent month selection, timeframe synchronization, candle limits, and anchor candle locking.
   - Comprehensive comparative metrics: Net Return %, Annualized Realized Volatility %, Max Drawdown %, Price Amplitude %, Total Volume, and Missing Bars.
   - High-DPI Canvas visualizations:
     - Unified Normalized Trajectory Curve (%0.0 baseline alignment for comparative alpha / regime trajectory).
     - Side-by-side Candlestick charts with green/red bodies and wicks.
     - Formula-injection-safe CSV and JSON exports (escaped leading `=`, `+`, `-`, `@`).

3. **Regime Distribution Drift Intelligence Engine:**
   - Implemented in `src/coin_behavior_engine/product/regime_drift.py`.
   - Dedicated UI tab `#module-drift` ("Rejim Dağılım & Değişim").
   - Computes structural divergence between two observation windows across 105,120 historical bars:
     - **Population Stability Index (PSI):** Measures distribution drift with Laplace smoothing ($\epsilon=10^{-5}$) and status classifications (`STABLE` for $<0.1$, `MODERATE_DRIFT` for $0.1 \le PSI < 0.25$, `SIGNIFICANT_DRIFT` for $\ge 0.25$).
     - **Jensen-Shannon Divergence (JSD):** Symmetric, bounded divergence metric in $[0, 1]$.
     - **Wasserstein Volatility Distance:** Earth Mover's Distance computed on ordered volatility rank states.
     - **Mean Persistence Duration:** Consecutive run tracking in hours per regime.
     - **Transition Probability Matrix:** Conditional stochastic matrix $P(\text{to} \mid \text{from})$.
   - High-DPI canvas showing side-by-side grouped distribution bars (Cyan vs Amber).

4. **Hardened Scientific Research Readiness Policy:**
   - Updated `src/coin_behavior_engine/product/research_readiness.py`.
   - Eliminated false `PARTIALLY_READY` (33.2%) for missing candidate periods.
   - Unimported candidate months (e.g. October 2026) fail-closed with status `BLOCKED_NO_DATA`, score `0.0%`, and Turkish user guidance banner:
     *"Bu dönem için doğrulanmış piyasa verisi bulunmuyor. Araştırma modülleri kullanılamaz."*
   - Imported canonical months (2022-01 to 2026-09) score `100.0%` (`READY`).

5. **Integrated Product API Endpoints:**
   - `GET /api/v1/product/comparative-analysis`
   - `GET /api/v1/product/comparative-export`
   - `GET /api/v1/product/regime-drift`
   - `GET /api/v1/product/derivation-status`

---

## 2. Verification Deliverables Inventory

| # | Artifact / Report File | Status | Description |
|---|---|---|---|
| 1 | `research_outputs/product_acceleration_07_baseline_reconciliation.json` | Generated | Pre-development VPS, container, and Git baseline audit |
| 2 | `research_outputs/product_acceleration_07_derivation_report.json` | Generated | Exact mathematical parity audit of derived vs canonical partitions |
| 3 | `research_outputs/product_acceleration_07_dataset_lineage.json` | Generated | Partitions lineage, source hashes, and algorithm version CBE-MTD-1.0.0 |
| 4 | `research_outputs/product_acceleration_07_comparison_validation.json` | Generated | Benchmark dual-period comparison (2024-03 vs 2024-11) |
| 5 | `research_outputs/product_acceleration_07_regime_drift_validation.json` | Generated | Benchmark regime drift execution (PSI=0.0304, JSD=0.0055, Wasserstein=0.2921) |
| 6 | `research_outputs/product_acceleration_07_readiness_validation.json` | Generated | Fail-closed validation (2026-10 BLOCKED_NO_DATA 0.0% vs 2026-09 READY 100.0%) |
| 7 | `research_outputs/product_acceleration_07_test_report.json` | Generated | Full pytest execution audit (94/94 passing, 100% pass rate) |
| 8 | `research_outputs/product_acceleration_07_performance_report.json` | Generated | Execution latency, memory RSS, and throughput benchmarks |
| 9 | `research_outputs/product_acceleration_07_browser_acceptance.md` | Generated | 16 browser screenshots gallery across Desktop, Tablet, and Mobile |
| 10 | `research_outputs/product_acceleration_07_staging_verification.json` | Generated | Remote VPS staging container deployment and live API query receipts |
| 11 | `research_outputs/product_acceleration_07_delivery_report.md` | Generated | This comprehensive sprint completion report |
| 12 | `research_outputs/product_acceleration_07_next_priorities.md` | Generated | Prioritized research, performance, and workflow extensions for Sprint 08 |

---

## 3. Remote Staging Deployment & Governance Compliance

- **Target Staging Host:** Linux VPS `168.231.125.238` (Coolify-managed)
- **Staging Service Container:** `6139364c0c1c` (Bound to `127.0.0.1:18080->8000/tcp`, Status: `Up (healthy)`)
- **Active Build Commit:** `bca29faa4963bf720576bab319dfb78aff435cf7` (`bca29faa`)
- **Production Container:** `e27157318ede` (`6t63aehpaw0cw1bbt4zcm09g`) — `Up About an hour (healthy)`, zero modifications made.
- **Governance Invariants:**
  - `TECHNICAL_DECISION: TECHNICAL_NO_GO`
  - `GOVERNANCE_AUTHORIZATION: NOT_GRANTED`
  - `PRODUCTION_TOKEN: NOT_ISSUED`
  - `REAL_NETWORK_MARKET_COLLECTION: DISABLED`
  - `BTCUSDT_LIVE_OBSERVATION: DISABLED`
  - `UNATTENDED_MONITORING: DISABLED`
  - `LIVE_ORDER_EXECUTION: PERMANENTLY_PROHIBITED`
