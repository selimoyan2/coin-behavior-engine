# BTC TIMING RESEARCH ENGINE — SYSTEM ARCHITECTURE SPECIFICATION

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  
**Execution Environment:** Isolated Offline Research Engine (Module 29)  
**Governance Invariants:**  
- `CANONICAL_MODEL = CBE-0.7.0` (STRICTLY FROZEN)  
- `RESEARCH_MODE = STRICTLY_OFFLINE_RESEARCH`  
- `DIRECTIONAL_TRADING_ELIGIBILITY = 0`  
- `LIVE_ORDER_EXECUTION = PERMANENTLY_PROHIBITED`  

---

## 1. Architectural Component Map

```
+-----------------------------------------------------------------------------------+
|                           CBE PRODUCT DASHBOARD V7                                |
|    [Overview] [Historical Analysis] [Timing Policies] [Paper Portfolio]           |
|    [Strategy Comparison] [Risk Analytics] [History & Reports]                    |
+------------------------------------------+----------------------------------------+
                                           | HTTP Read-only / Simulate POST
+------------------------------------------v----------------------------------------+
|                     ProductDashboardApiService (dashboard_api.py)                 |
|   /api/v1/product/research/btc-timing/{overview, policies, simulate, compare, ...}|
+------------------------------------------+----------------------------------------+
                                           | Internal Orchestration
+------------------------------------------v----------------------------------------+
|                   BTCTimingResearchCoordinator (Singleton)                       |
+------------------------------------------+----------------------------------------+
      |                   |                     |                    |
+-----v-----+      +------v------+       +------v------+       +-----v-----+
|  Dataset  |      |   Feature   |       |  Hypothesis |       |  Policy   |
|  Adapter  |      |   Adapter   |       |   Registry  |       |  Engine   |
+-----------+      +-------------+       +-------------+       +-----------+
      |                   |                     |                    |
+-----v-------------------v---------------------v--------------------v-----+
|                 Historical Simulation Engine & Accounting                 |
|  - HistoricalDecisionEngine (Lag T+1000ms, execution at open price)       |
|  - TransactionCostEngine (LOW, BASE, HIGH profiles)                       |
|  - PaperPortfolioEngine (Cash/BTC balance conservation, equity curve)    |
|  - PerformanceAnalyticsEngine (Sharpe, Sortino, Calmar, Drawdown, Drag)  |
|  - BenchmarkEngine (Buy & Hold vs USDT Cash comparison)                  |
|  - WalkForwardValidator (Expanding folds, OOS degradation analysis)       |
+------------------------------------------+----------------------------------------+
                                           | Atomic JSON Persistence
+------------------------------------------v----------------------------------------+
|               TimingResearchRepository (Atomic File System Storage)               |
|            data/research/btc_timing/{experiments, index.json, quarantines}        |
+-----------------------------------------------------------------------------------+
```
