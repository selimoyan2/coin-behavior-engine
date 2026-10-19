# CBE SPRINT 11.18 — RESEARCH REPORT
## Historical Market & News Intelligence Foundation
### Canonical Benchmark Closure + Multi-Year Causal Data Infrastructure

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `30f1c9516c8c5a9a3a494380a788b9b753a36518`  
**Execution Mode:** STRICTLY OFFLINE RESEARCH ONLY  
**Trading Scope:** BTC/USDT Spot — Long Only — No Leverage — No Short Selling  
**Audit Status:** COMPLETE & DETERMINISTICALLY VERIFIED  

---

## 1. EXECUTIVE SUMMARY & SPRINT OBJECTIVE

Sprint 11.18 establishes a certified, causal, multi-year data infrastructure enabling the Coin Behavior Engine (CBE) to learn from historical market dynamics, global exchange opening regimes, and macroeconomic catalysts spanning **2022-01-01 UTC to present**. 

Critically, this sprint accomplishes two primary mandates:
1. **Canonical Benchmark Closure:** Formally resolves historical discrepancies in benchmark Buy & Hold accounting across sprints (Bar 0 inception vs Bar 576 post-warmup inception) and validates the exact mathematical decomposition of session-timing performance attribution.
2. **Causal Data Infrastructure:** Implements a verifiable market and event data pipeline:
   - Official Binance Vision 1m monthly historical kline ingestion with cryptographic `.CHECKSUM` verification.
   - Deterministic multi-timeframe aggregation (5m, 15m, 1h, 4h, 1d) with zero synthetic imputation.
   - Audit of historical macroeconomic and news sources (ALFRED vintage records, BLS, SEC EDGAR, CryptoPanic, GDELT).
   - Standardized 19-field point-in-time event schema eliminating lookahead and revision bias.
   - `HistoricalReplayEngine` providing deterministic point-in-time state reconstruction with SHA-256 state fingerprinting.

---

## 2. PHASE 0 — CANONICAL BENCHMARK CLOSURE

### 2.1 BTC Buy & Hold Discrepancy Resolution
A systematic audit of the 105,120-bar canonical dataset (`market_state_dataset.parquet`) was executed to reconcile divergent figures reported in earlier sprints:

| Benchmark Specification | Inception Bar | Starting Time (UTC) | Entry Price | Terminal Price | Terminal MTM Equity (Return) | Terminal Liquid Equity (Return) | Total Roundtrip Friction |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Full-Sample Buy & Hold** | Bar 0 | 2025-10-18 11:30 | $106,891.72 | $82,104.03 | **$7,716.14 (-22.84%)** | **$7,704.87 (-22.95%)** | $25.97 USDT |
| **Post-Warmup Buy & Hold** | Bar 576 (48h) | 2025-10-20 11:30 | $110,810.88 | $82,104.03 | **$7,450.31 (-25.50%)** | **$7,439.44 (-25.61%)** | $25.58 USDT |

#### Root Cause Attribution of Earlier Discrepancies
- **-24.86% Liquid vs -22.95%:** The -24.86% figure present in the string comment of the Sprint 11.17.1 verdict JSON was a typographical transfer artifact from an intermediate unclosed bar draft. The canonical accounting from OHLCV yields exactly **-22.95%** liquidated return (**-22.84%** MTM).
- **+18.12% vs -25.61%:** The +18.12% figure in the 11.17.1 verdict string arose from an erroneous draft script assuming a hypothetical entry price of $67,900. The canonical post-warmup open at Bar 576 was $110,810.88, leading to a true liquid return of **-25.61%** (**-25.50%** MTM).

Both benchmarks are now canonically closed and permanently recorded in `research_outputs/benchmark_closure_11_18.json`.

### 2.2 Session Attribution & Turnover Control Audit
Sprint 11.17.1 identified that the Patient Session-Aware spot model outperformed its Session-Blind control by +3.22% net PnL (+$321.18 USDT). In this sprint, we verified the exact mathematical decomposition:

$$\Delta \text{Net PnL} = \Delta \text{Gross Trading PnL} + \Delta \text{Friction Savings}$$
$$\$321.18 = (-\$412.97) + \$734.15$$

- **Gross Trading PnL was Negative (-$412.97):** Filtering entries to exchange openings performed worse on pure asset drift.
- **Friction Savings was Positive (+$734.15):** The model saved $734.15 in fees and slippage by suppressing 47 unprofitable trades.
- **Matched-Turnover Control:** Sprint 11.17.1's static subsampling claim (-44.69%) was designated `NOT_INDEPENDENTLY_VERIFIED` because it did not model chronological cash compounding. When evaluated via true chronological portfolio execution with dynamic sizing ($Q_t = 0.98 \times \text{Cash}_t / P_t$, 1,000 iterations), the mean return was $-57.77\% \pm 1.35\%$, confirming that the apparent session advantage is an artifact of trade suppression in a bear market rather than genuine timing alpha.

---

## 3. PHASE 1 — BINANCE HISTORICAL MARKET DATA PIPELINE

### 3.1 Repository Inventory
An exhaustive scan of existing market datasets was conducted, documenting cryptographic fingerprints:
- `data/raw/btcusdt_5m_raw.parquet`: 602,240 5m bars (2021-01-01 to 2026-09-23), SHA-256: `9ee57fe64fc5a763f03b60e68d1844bca4587db2fa2cba4a88f7b587d55f04b2`.
- `research_outputs/market_state_dataset.parquet`: 105,120 5m bars (2025-10-18 to 2026-10-18), SHA-256: `ca782d8cba22fb097143dd9810a9fe3e97034c4fca28185c7423985bfec92ae1`.
- Complete manifest stored in `research_outputs/historical_market_inventory_11_18.json`.

### 3.2 Official Binance Vision Pilot Batch (2022-01)
To establish verified provenance for multi-year historical research from 2022 to present, a chunked ingestion pipeline was implemented targeting official Binance Vision archives (`https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/`).

The pilot batch `BTCUSDT-1m-2022-01.zip` was downloaded and audited:
- **Official Checksum:** `ce0e16e834331e70b3041677c7f409818d5904bb59cb7b880695e4cacd34fc09`
- **Calculated Checksum:** `ce0e16e834331e70b3041677c7f409818d5904bb59cb7b880695e4cacd34fc09` (Exact Match Verified)
- **File Size:** 2,229,634 bytes compressed (~18 MB uncompressed CSV)
- **1-Minute Bar Count:** 44,640 (100% of minutes in January 2022: 31 days × 24h × 60m)
- **Continuity & Gaps:** Zero timestamp gaps (monotonically 60,000 ms step), Zero duplicate timestamps.
- **OHLC Invariants:** Zero violations ($L \le O, C \le H$; $H \ge L$; $V \ge 0$).
- **Synthetic Imputation:** Strictly prohibited; fail-closed policy enforced.

### 3.3 Multi-Timeframe Deterministic Resampling
Deterministic aggregation rules were applied to resample the pristine 1m klines into standard analytical timeframes:
- **5-Minute (5m):** 8,928 bars
- **15-Minute (15m):** 2,976 bars
- **1-Hour (1h):** 744 bars
- **4-Hour (4h):** 186 bars
- **1-Day (1d):** 31 bars

All resampled series were exported to parquet with zero missing bars (`binance_data_quality_11_18.json`).

---

## 4. PHASE 2 — HISTORICAL NEWS & MACRO SOURCE AUDIT

An audit was conducted across news and macroeconomic providers (`historical_news_source_audit_11_18.md`):

1. **ALFRED (ArchivaL Federal Reserve Economic Data):** Certified as the primary source for US macroeconomic indicators (CPI, PCE, NFP, Unemployment, Fed Funds Rate). Native vintage tracking guarantees zero revision contamination.
2. **BLS Press Releases:** Scheduled high-frequency CPI and employment releases. Causal availability enforced at `release_time + 60s`.
3. **SEC EDGAR API:** Authoritative for Bitcoin ETF filings (S-1, 19b-4) with second-level ingestion timestamps.
4. **CryptoPanic & GDELT 2.0:** Aggregated sentiment and event detection streams with bounded ingestion latency buffers (45–180s for CryptoPanic, 15m for GDELT).
5. **Causal Latency Invariant:** In historical replay, an event is only visible if $T_{\text{available}} \le T_{\text{decision}}$, where $T_{\text{available}} = T_{\text{publish}} + \Delta t_{\text{feed}}$ ($\Delta t_{\text{feed}} \ge 60\text{s}$).

---

## 5. PHASE 3 — STANDARDIZED POINT-IN-TIME EVENT SCHEMA

A JSON Schema (`point_in_time_event_schema_11_18.json`) was standardized containing 19 mandatory fields:
1. `event_id` (Deterministic string)
2. `published_at_utc` (Publisher ISO timestamp)
3. `available_at_utc` (Earliest machine-accessible timestamp)
4. `source_id` (Authenticated provider enum)
5. `category` (Financial taxonomy enum)
6. `headline` (Unedited string)
7. `raw_text` (Original body text/excerpt)
8. `entities` (List of recognized market entities)
9. `sentiment_label` (BULLISH / BEARISH / NEUTRAL / AMBIGUOUS)
10. `sentiment_score` (Float bounded in [-1.0, 1.0])
11. `expected_value` (Consensus prior to release)
12. `actual_value` (Released vintage value)
13. `previous_value` (Prior period value at this vintage)
14. `revision_indicator` (Boolean flag)
15. `vintage_date` (ALFRED vintage date YYYY-MM-DD)
16. `is_first_release` (Boolean flag)
17. `causal_delay_seconds` (Enforced delay integer)
18. `source_url` (Archival URL)
19. `checksum_sha256` (Content cryptographic hash)

---

## 6. PHASE 4 & 5 — CAUSAL HISTORICAL REPLAY ENGINE

The `HistoricalReplayEngine` (`src/coin_behavior_engine/research/historical_replay.py`) integrates market candles, global exchange opening schedules, and point-in-time events into an immutable state representation:

```
ReplayState:
  - query_time_utc
  - last_closed_candle (close_time <= query_time)
  - active_sessions (TSE, HKEX, LSE, NYSE)
  - session_relative_windows (PRE_OPEN_10M, POST_OPEN_10M, etc.)
  - visible_events (available_at_utc <= query_time)
  - state_hash_sha256 (Deterministic SHA-256 fingerprint)
```

### Demonstration of Causal Separation: NYSE Opening (2026-01-05)
- **Pre-Open ($T_0 - 10\text{m}$, 14:20:00 UTC):**
  - Session status: `PRE_OPEN` (`PRE_OPEN_10M`)
  - NYSE active: False (only LSE active)
  - Observed candles: 22,786 bars (last closed: 14:15:00 UTC)
  - Visible events: 2 events
  - State Hash: `bae47d1421ba6e6fc83aef3f50dfbe9159bec10ba833facb83d357859c037de3`
- **Post-Open ($T_0 + 10\text{m}$, 14:40:00 UTC):**
  - Session status: `OPEN` (`POST_OPEN_10M`)
  - NYSE active: True (LSE + NYSE active)
  - Observed candles: 22,790 bars (last closed: 14:35:00 UTC, +4 new 5m bars)
  - Visible events: 3 events (+1 newly released flash event)
  - State Hash: `d40cfc71b32d5d0aba566cdc4abbb45b07dce0492e9414c92b598f0067e909f9`

Deterministic reproducibility: 100% identical state hash across repeat invocations.

---

## 7. SCIENTIFIC & INVARIANT VERIFICATION

The dedicated test suite `tests/test_sprint11_18_causal_data_foundation.py` validates all core invariants:
- `test_benchmark_closure_accounting`: PASSED
- `test_binance_pilot_quality_and_invariants`: PASSED
- `test_resampling_determinism_and_counts`: PASSED
- `test_causal_news_and_future_leak_prevention`: PASSED
- `test_causal_unclosed_candle_rejection`: PASSED
- `test_deterministic_state_hash_reproducibility`: PASSED
- `test_event_schema_completeness`: PASSED
- `test_revision_immutability`: PASSED

---

## 8. MANDATORY SCIENTIFIC DECLARATIONS

| Dimension | Mandatory Declaration | Status |
| :--- | :--- | :--- |
| **Execution Mode** | Strictly Offline Research Only | ENFORCED |
| **Trading Scope** | Spot BTC/USDT Long-Only (No Leverage, No Shorting) | ENFORCED |
| **Benchmark Reconciliation** | Bar 0 (-22.95%) & Bar 576 (-25.61%) Canonically Closed | VERIFIED |
| **Data Ingestion Integrity** | Binance Vision SHA-256 Verified, Zero Gaps, Fail-Closed | VERIFIED |
| **Lookahead Prevention** | Strict Causal Isolation (Candles & Events) | VERIFIED |
| **Prospective Observation** | Not Started | PRESERVED |
| **Live Trading** | Strictly Prohibited | PRESERVED |
| **Operator Authorization** | Not Granted | PRESERVED |
| **Next Step** | Operator Review of Multi-Year Ingestion Foundation | PENDING |
