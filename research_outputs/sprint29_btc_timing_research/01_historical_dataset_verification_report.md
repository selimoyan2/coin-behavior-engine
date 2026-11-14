# HISTORICAL BTC DATASET VERIFICATION REPORT

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  
**Dataset ID:** `DS-BTC-1H-2023-2024`  
**Symbol:** `BTCUSDT`  
**Timeframe:** `1h` (1 Hour / 3,600,000 ms)  
**Total Verified Bars:** `9528`  
**Physical File Path:** `data/historical/BTCUSDT-1h-2023-10-to-2024-11.parquet`  
**File SHA-256:** `b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874`  
**Earliest Open (UTC):** `2023-10-01T00:00:00Z`  
**Latest Open (UTC):** `2024-10-31T23:00:00Z`  
**Status:** `VERIFIED_AUTHENTIC`  

---

## 1. Cryptographic & Data Integrity Audit

| Check Description | Standard / Expectation | Measured Result | Status |
| :--- | :--- | :--- | :---: |
| Physical Existence | File exists on disk | Present (918,888 bytes) | PASS |
| SHA-256 Checksum | Matches registered provenance | `b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874` | PASS |
| Total Bar Count | Exactly 9,528 continuous hours | 9,528 bars | PASS |
| Monotonicity | Strictly increasing open timestamps | Strictly monotonic (Δt = +3,600,000 ms) | PASS |
| Duplicate Detection | Zero duplicate timestamps | 0 duplicates found | PASS |
| Missing Intervals | Zero gap intervals in coverage | 0 missing intervals | PASS |
| OHLC Consistency | High >= Low; High >= Open, Close | 0 violations detected | PASS |
| Price Positivity | Open, High, Low, Close > 0 | 100% positive values | PASS |
| Volume Validity | Volume >= 0 and finite | 0 negative / NaN volume values | PASS |
| UTC Standardization | Normalized to UTC ISO-8601 | 100% verified | PASS |

---

## 2. Dataset Partitioning & Information Availability

Point-in-time access is enforced via `HistoricalBTCDatasetAdapter.get_data_available_at(T)`.
A bar opening at `T_open` completes at `T_open + 3,600,000 ms`. A decision made at timestamp `T` can only observe completed bars where `open_time + 3,600,000 <= T`. Future data is strictly unreachable.

**Verification Token:** `HISTORICAL_DATASET_VERIFIED_DS_BTC_1H_2023_2024`
