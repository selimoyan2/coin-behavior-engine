# 02 — Raw-to-Merged Data Verification Report
## Verification of Multi-Month Parquet Concatenation

**Sprint ID:** `CBE_SPRINT32_SCIENTIFIC_VALIDATION_DASHBOARD_V10`  
**Dataset Target:** `DS-BTC-1H-2025-SEALED`  
**Verification Date:** `2026-11-15T11:45:57.660801+00:00`  
**Parity Status:** **`VERIFIED_EXACT_EQUIVALENCE`**  

---

## 1. Concatenation Parity Analysis

| Metric | Source Monthly Partitions (Sum) | Target Merged Dataset | Parity Status |
| :--- | :---: | :---: | :---: |
| **Total Files** | 12 files | 1 file | Expected |
| **Total Rows** | 8,760 rows | 8,760 rows | **EXACT MATCH** |
| **Columns Count** | 12 columns | 12 columns | **EXACT MATCH** |
| **Earliest Bar** | 2025-01-01 00:00:00+00:00 | 2025-01-01 00:00:00+00:00 | **EXACT MATCH** |
| **Latest Bar** | 2025-12-31 23:00:00+00:00 | 2025-12-31 23:00:00+00:00 | **EXACT MATCH** |
| **Bitwise Equality** | - | - | **100% IDENTICAL** |

---

## 2. Column-by-Column Value Verification

Every column of the concatenated monthly partitions was compared against the target merged parquet file:

1. `datetime`: **IDENTICAL** (0 differences)
2. `open_time`: **IDENTICAL** (0 differences)
3. `open`: **IDENTICAL** (0 differences)
4. `high`: **IDENTICAL** (0 differences)
5. `low`: **IDENTICAL** (0 differences)
6. `close`: **IDENTICAL** (0 differences)
7. `volume`: **IDENTICAL** (0 differences)
8. `close_time`: **IDENTICAL** (0 differences)
9. `quote_volume`: **IDENTICAL** (0 differences)
10. `count`: **IDENTICAL** (0 differences)
11. `taker_buy_volume`: **IDENTICAL** (0 differences)
12. `taker_buy_quote_volume`: **IDENTICAL** (0 differences)

---

## 3. Merge Reproducibility Verdict

The target dataset `historical_binance_btcusdt_1h_2025.parquet` is **reproducibly derived** from the 12 monthly partitions. Re-running the concatenation in an isolated Python environment generates the exact same table structure and identical candle data.
