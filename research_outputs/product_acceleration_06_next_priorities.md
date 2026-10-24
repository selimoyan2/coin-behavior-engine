# CBE Product Acceleration — Post-Sprint 06 Strategic Roadmap & Priorities

**Sprint:** `CBE_PRODUCT_ACCELERATION_06`  
**Generated At:** 2026-10-24 08:25:30 UTC  
**Next Recommended Focus:** Sprint Product Acceleration 07  

---

## 1. Top Recommended Product Priorities

### Priority 1: Genuine October 2026 Archive Ingestion (When Authorized)
- Once the operator provides genuine, cryptographically authenticated historical data files for October 2026 (e.g. from official Binance monthly archives):
  1. Execute `python -m coin_behavior_engine.data_import -s <october_file> -m preview`.
  2. Inspect completeness percentage and ensure zero gaps.
  3. Execute `python -m coin_behavior_engine.data_import -s <october_file> -m import`.
  4. Verify cross-interval aggregation across $5m \rightarrow 15m \rightarrow 1h \rightarrow 4h \rightarrow 1d$.
  5. The UI and catalog will automatically transition freshness tier to `T-0_CURRENT_PERIOD`.

### Priority 2: Interactive Crosshair Comparative Window in Research Workbench
- Allow researchers to lock a historical anchor candle (e.g. FOMC announcement or volatility spike) in one split canvas while panning through comparison periods in a second canvas.
- Real-time percentage delta overlay ($R_t - R_0$) between anchor and comparison trajectories.

### Priority 3: Automated Cross-Interval Parquet Derivation (Offline Synthesizer)
- When a new monthly $5m$ partition is imported, provide an automated command to deterministically compile the matching $15m$, $1h$, $4h$, and $1d$ canonical partitions using the verified `CrossIntervalIntegrityEngine` mathematical aggregation rules.
- Eliminates manual downloading of multiple interval files from upstream exchanges while guaranteeing 100% mathematical parity.

### Priority 4: Dynamic Regime Distribution Drift Diagnostics
- Real-time rolling Wasserstein distance and Kullback-Leibler divergence calculations between historical regime distributions (e.g. 2022 bear market vs 2024–2026 compression).
- Early alert for regime model recalibration necessity without violating the freeze contract.

### Priority 5: Export Template Customizer in Scenario Lab
- Provide customizable JSON/CSV export schemas for quantitative researchers using Python/R/Julia, allowing selective column extraction, date formatting, and gzip/parquet compression.

---

## 2. Invariant Guidelines for Future Sprints

1. **Maintain Offline Research Purity:** Real-time web collection and exchange WebSocket connectivity remain strictly disabled until explicit operator governance authorization is signed and verified.
2. **Prevent Lookahead Leakage:** Forward outcome windows in pattern recognition must enforce $\ge 12$-bar quarantine boundaries.
3. **Preserve Production Separation:** Coolify production container `6t63aehpaw0cw1bbt4zcm09g` must never be touched during staging acceleration cycles.
