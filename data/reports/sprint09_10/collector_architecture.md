# CBE-0.8.0 SHADOW COLLECTOR ARCHITECTURE SPECIFICATION

**PROJECT:** coin-behavior-engine  
**VERSION:** CBE-0.8.0-SHADOW  
**MODULE PATH:** `src/coin_behavior_engine/shadow_v080/`  
**STATUS:** IMPLEMENTED & AUDITED (OFFLINE DEVELOPMENT ONLY)  

---

## 1. ARCHITECTURAL OVERVIEW & ISOLATION

The CBE-0.8.0 Shadow Collector is designed as an autonomous, decoupled research daemon that observes live market behavior without impacting or mutating production CBE-0.7.0 execution.

```
+-----------------------------------------------------------------------------------+
|                           PROSPECTIVE SHADOW RUNTIME                              |
|                                                                                   |
|  [ Candle Source ] ---> [ Bounded Buffer (350) ] ---> [ Feature Pipeline ]       |
|    - Offline Fixture         - Deduplication            - volatility_realized_24h |
|    - Live (Locked)           - Continuity Audit         - compression_ratio       |
|                              - Atomic Snapshots         - volume_zscore_24h       |
|                                                                 |                 |
|                                                                 v                 |
|                                                     [ Dual-Branch Inference ]     |
|                                                       - Ridge Point Forecast      |
|                                                       - Market State Classifier   |
|                                                       - Candidate C (Global)      |
|                                                       - Candidate E (Hybrid)      |
|                                                                 |                 |
|                                                                 v                 |
|  [ Forward Outcome Engine ] <----------------------- [ Immutable Event Store ]    |
|    - 1h (12 bars)                                      - Append-Only JSONL        |
|    - 4h (48 bars)                                      - SHA-256 Hash Chain       |
|    - 24h (288 bars)                                    - Label: HISTORICAL_REPLAY |
+-----------------------------------------------------------------------------------+
```

---

## 2. COMPONENT RESPONSIBILITIES

1. `configuration.py`: Hard safety interlocks (`network_enabled=False`, `live_shadow_enabled=False`, `trading_enabled=False`), storage directories, and resource budgets.
2. `candle_source.py`: Source abstraction separating offline fixture playback from the public Binance spot klines REST client. Enforces rate limits and network lockouts.
3. `feature_pipeline.py`: Reuses `FeedAdapterV080` to enforce closed-candle causality, FIFO buffer eviction, and feature quality metadata.
4. `inference_runner.py`: Executes Candidate C and Candidate E simultaneously, verifying identical point forecasts and market states across all horizons (1h, 4h, 24h).
5. `prediction_store.py`: Append-only JSONL storage protected by unbroken SHA-256 hash chaining from `SHADOW_GENESIS_HASH`.
6. `outcome_resolver.py`: Evaluates forward realized volatility once forward maturity windows have elapsed, ensuring no forward-looking lookahead during prediction generation.
7. `event_integrity.py`: Cryptographic auditor validating hash continuity, record checksums, and monotonic commit timestamps.
8. `health_monitor.py`: Local observation-only telemetry tracking buffer size, memory RSS, disk consumption, and error states.
9. `collector.py`: Master orchestrator driving the 10-state eligibility machine (`CaptureState`).
10. `cli.py`: Standalone CLI supporting dry-run verification and offline replay.
