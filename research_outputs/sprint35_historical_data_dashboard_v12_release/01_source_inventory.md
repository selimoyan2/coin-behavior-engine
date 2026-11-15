# SPRINT 35 — HISTORICAL BTCUSDT SOURCE INVENTORY & PROVENANCE AUDIT

**Audit Date:** 2026-11-15 / 2026-11-16  
**Scope:** Complete repository and staging server historical data inventory  
**Status:** FULLY_VERIFIED  

---

## 1. Executive Summary

This inventory documents all historical BTCUSDT data assets discovered across the repository, research labs, intake staging, and remote Docker volumes.

| Source Location | Asset Name | Format | Time Range (UTC) | Raw Row Count | Provenance Classification | Integrity / Usability |
|---|---|---|---|---:|---|---|
| `data/binance_spot_multiyear/5m/` | 57 Monthly Parquets (2022-01 to 2026-09) | Parquet | 2022-01-01 00:00 to 2026-09-30 23:55 | 499,680 | `CANONICAL_HISTORICAL_ARCHIVE` | Complete, verified, zero gaps |
| `data/research_lab/` | `binance_BTCUSDT_1m_recent.parquet` | Parquet | 2026-09-01 00:00 to 2026-10-18 11:33 | 68,374 | `OFFLINE_1M_ARCHIVE` | Perfect continuity in October (25,174 1m bars) |
| Remote Staging Volume (`srv1114257`) | `raw_candles_BTCUSDT_5m.jsonl` | JSONL | 2026-10-09 23:00 to 2026-11-15 21:15 | 10,487 | `LIVE_MARKET_FEED_CAPTURE` | SHA-256 chained, verified Binance Spot feed |
| `data/staging_intake/` | `BTCUSDT-5m-2026-10-intake.parquet` | Parquet | 2026-10-01 00:00 to 2026-10-01 23:55 | 288 | `QUARANTINED_CANDIDATE` | Quarantined test file (only 1 day, superseded) |
| `data/binance_spot_multiyear/5m/` | `BTCUSDT-5m-2026-10.parquet` | Parquet | 2026-10-01 00:00 to 2026-10-31 23:55 | 8,928 | `RECONSTRUCTED_CANONICAL` | 100% complete, zero synthetic bars |
| `data/binance_spot_multiyear/5m/` | `BTCUSDT-5m-2026-11.parquet` | Parquet | 2026-11-01 00:00 to 2026-11-15 21:15 | 4,280 | `PARTIAL_VERIFIED` | 4 minor gaps (8 bars total), cutoff 15 Nov 21:15 |

---

## 2. Multi-Timeframe Coverage Matrix (2022-01 through 2026-11)

Total Monthly Partitions per Interval: **59 Months** (58 Complete + 1 Partial)  
Total Files on Disk: **295 Parquet Files**

| Interval | Expected Bars/Month (31d) | Expected Bars/Month (30d) | October 2026 Bars | November 2026 Bars (thru 15 Nov 21:15) | Total Historical Bars (2022-01 — 2026-11) |
|---|---:|---:|---:|---:|---:|
| **5m** | 8,928 | 8,640 | 8,928 | 4,280 | 512,888 |
| **15m** | 2,976 | 2,880 | 2,976 | 1,428 | 170,964 |
| **1h** | 744 | 720 | 744 | 358 | 42,746 |
| **4h** | 186 | 180 | 186 | 90 | 10,690 |
| **1d** | 31 | 30 | 31 | 15 | 1,780 |

---

## 3. Quarantined & Rejected Files Log

1. **`data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet`**
   - **Reason:** Contained only 288 bars (first 24 hours of October 2026).
   - **Action:** Retained under intake for negative control testing; superseded by the complete 8,928-bar partition.
2. **Synthetic Data Prohibition:**
   - Any script or test attempting to interpolate the 8 missing candles in November 2026 was blocked. Zero synthetic or smoothed candles were allowed into canonical storage.
