# CBE — Sprint 08 Next Product Priorities

**Sprint Baseline Commit:** `bca29faa4963bf720576bab319dfb78aff435cf7`  
**Application Environment:** Coolify Linux VPS `srv1114257` (`168.231.125.238`)  
**Staging Service:** `cbe-market-intelligence-staging` (`127.0.0.1:18080->8000/tcp`)  

---

## 1. Top Recommended Next Engineering & Product Priorities

1. **Automated Batch Timeframe Derivation Pipeline on Staging:**
   - Integrate the multi-timeframe derivation engine directly into the Coolify staging admin/operations interface (`#module-operations`).
   - Add a one-click button in the UI to run dry-run validation and batch derivation for newly uploaded source partitions without SSH terminal intervention.

2. **Cross-Asset Comparative Analysis (ETHUSDT / SOLUSDT):**
   - Extend the `ComparativeMarketEngine` and `DatasetManager` schema to support multi-symbol historical archives.
   - Allow cross-asset comparative overlay (e.g. BTC vs ETH normalized return trajectory relative to macro events or halving dates).

3. **Macro Event Window Synchronized Trajectory Overlay:**
   - Allow researchers in the Comparative Workbench to select specific macroeconomic events (e.g. FOMC 50bps rate cut, CPI surprises) as anchor points.
   - Automatically align Period A and Period B around $T_0 = \text{Event Announcement}$ to contrast market response dynamics.

4. **Dynamic Regime Drift Threshold Alerts & Sensitivity Tuning:**
   - Allow researchers to adjust the PSI warning thresholds and volatility rank weights in `#module-drift`.
   - Provide exportable PDF/LaTeX research summaries of regime distribution shifts.

5. **Historical Research Report PDF Generator:**
   - Implement deterministic, client-side or server-side headless PDF report generation compiling comparative charts, metrics tables, and regime drift telemetry into an archival research memo.
