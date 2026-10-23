# CBE — SPRINT PRODUCT ACCELERATION 05: DATASET ARCHITECTURE SPECIFICATION
## Rolling Historical Data Architecture, Dynamic Partitions & Quality Governance

**Document Version:** 1.0.0  
**Status:** IMPLEMENTED & AUDITED  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit Reconciled:** `36ccafcc8543a241ba7bf193e4aceb28c8bf7858`  
**Execution Mode:** STRICTLY OFFLINE HISTORICAL RESEARCH  

---

## 1. Architectural Overview

Prior to Sprint 05, the Coin Behavior Engine relied on static date boundaries terminating strictly in September 2026 (`2026-09-30 23:55:00 UTC`). Attempting to view or query dates outside this static interval led to interface freezes or silent fallback to stale periods.

Sprint 05 transforms CBE into an extensible rolling historical market intelligence platform:
- **Canonical Storage:** Immutable, cryptographically hashed Parquet files organized hierarchically: `data/binance_spot/{interval}/BTCUSDT/{year}/{month}.parquet`.
- **Dynamic Partition Discovery:** Runtime discovery through `DatasetManager` scanning physical disk partitions across supported intervals (`5m`, `15m`, `1h`, `4h`, `1d`).
- **Deterministic Manifest Computation:** Multi-file SHA-256 digests generating reproducible manifest revisions (`cbe-manifest-v2-addf635b47aa`).
- **Partial & Current-Month Extensibility:** Ingestion engine accepts partial calendar months (e.g. October 1–10) with exact row counting, completeness ratios, and non-blocking metadata.
- **Fail-Closed Missing Data Protocol:** Unimported months return explicit HTTP 200 `{"status": "no_data", "available": false, ...}` triggering visual alerts rather than fabricated synthetic candles.

---

## 2. Directory Hierarchy and Storage Layout

```
data/binance_spot/
├── 5m/
│   └── BTCUSDT/
│       ├── 2022/ (01..12.parquet)
│       ├── 2023/ (01..12.parquet)
│       ├── 2024/ (01..12.parquet)
│       ├── 2025/ (01..12.parquet)
│       └── 2026/ (01..09.parquet)  <-- Dynamic append partition point
├── 15m/
│   └── BTCUSDT/...
├── 1h/
│   └── BTCUSDT/...
├── 4h/
│   └── BTCUSDT/...
└── 1d/
    └── BTCUSDT/...
```

---

## 3. Ingestion & Validation Pipeline (`coin_behavior_engine.data_import`)

The offline importer enforces five strict validation layers:
1. **Schema Integrity:** Mandates `[datetime, open_time, open, high, low, close, volume]`.
2. **Numeric Finiteness:** No `NaN`, `Inf`, `-Inf`, or `null` values permitted.
3. **Price & Volume Positivity:** `open, high, low, close > 0` and `volume >= 0`.
4. **OHLC Geometric Consistency:**
   $$\text{high} \ge \max(\text{open}, \text{close})$$
   $$\text{low} \le \min(\text{open}, \text{close})$$
5. **Temporal Monotonicity & Spacing:** Strict monotonic increase matching interval delta (e.g., 300,000 ms for 5m). Rejects overlaps and duplicates.
6. **Atomic Publishing:** Staged in temporary scratch files before atomic filesystem replace, ensuring zero partial-write corruption.
7. **Immutable Audit Receipts:** Generates cryptographically verifiable receipts under `research_outputs/import_receipts/`.

---

## 4. Manifest Integrity & Cache Invalidation

The `DatasetManager` maintains an in-memory thread-safe cache protected by monotonic modification tracking:
- **Manifest ID:** `cbe-manifest-v2-{hash[:12]}`
- **Cache Eviction:** Automatically invalidated whenever new partitions are published or touched.
- **Query Bounds:** Supports `limit`, `offset`, `day`, `time_slot`, `start_date`, and `end_date` filters without full-table re-scans.
