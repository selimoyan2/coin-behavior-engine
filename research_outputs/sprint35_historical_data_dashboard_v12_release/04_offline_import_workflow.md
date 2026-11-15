# SPRINT 35 — OFFLINE HISTORICAL IMPORT WORKFLOW SPECIFICATION

**Protocol ID:** `CBE-DATA-IMPORT-PROTOCOL-V2.0`  
**Security Level:** STRICT_OFFLINE_AIRGAP  
**Scope:** Ingestion of raw external market data into canonical parquet partitions  

---

## 1. Five Mandatory Ingestion Gates

Before any external data file can be promoted to `data/binance_spot_multiyear/`:

```
[Raw Incoming File]
       │
       ▼
[Gate 1: Path Traversal & File Sanitization]
  - Absolute path resolution within repository sandbox
  - Rejection of parent directory traversal (..)
  - File extension verification (.csv, .jsonl, .parquet)
       │
       ▼
[Gate 2: Schema & Column Verification]
  - Required columns: open_time, datetime, open, high, low, close, volume
  - Timestamp type detection (ms epoch, ns epoch, ISO string)
  - UTC timezone localization
       │
       ▼
[Gate 3: OHLC Physics & Geometric Conservation]
  - High >= Low (strict)
  - High >= Open and High >= Close
  - Low <= Open and Low <= Close
  - Open > 0, High > 0, Low > 0, Close > 0, Volume >= 0
       │
       ▼
[Gate 4: Chronological Monotonicity & Zero-Synthesis Deduplication]
  - Strict deduplication on open_time (last received wins)
  - Monotonic ascending sorting
  - PROHIBITION: Zero interpolation or fabrication of missing candles
       │
       ▼
[Gate 5: Multi-Timeframe Resampling & Atomic Commit]
  - Canonical base is 5m
  - Resampling to 15m, 1h, 4h, 1d on exact UTC boundaries
  - Atomic rename (`.tmp_*.parquet` -> `.parquet`)
  - DatasetManager cache invalidation
```

---

## 2. Hardened CLI Execution Reference

To import a monthly partition offline:

```powershell
& .venv\Scripts\python.exe scripts/import_offline_historical_partition.py `
    --input data/staging_intake/raw_candles_BTCUSDT_5m.jsonl `
    --target-month 2026-11 `
    --symbol BTCUSDT `
    --base-interval 5m
```

On execution, the script generates a cryptographic receipt under `research_outputs/import_receipts/` containing the input SHA-256, output SHA-256s, candle counts, and gap audit.
