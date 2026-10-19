# CBE SPRINT 11.18.1 — RESEARCH REPORT
## Historical Data Integrity & Real Event Replay Validation

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `88542c52b0c98369bd64c7393740c06d7042d7ff`  
**Execution Mode:** STRICTLY OFFLINE RESEARCH ONLY  
**Trading Scope:** Spot BTC/USDT Long-Only (No Leverage, No Shorting)  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  

---

## 1. EXECUTIVE SUMMARY & RESEARCH OBJECTIVE

Sprint 11.18.1 conducts an independent scientific audit and rigorous empirical validation of the historical market data and news infrastructure established in Sprint 11.18.

Key achievements in this sprint include:
1. **Independent Benchmark Recalculation:** Direct computation from raw market Parquet using high-precision `Decimal` arithmetic, eliminating reliance on pre-saved JSON status flags. Reconciled Bar 0 and Bar 576 Buy & Hold returns and resolved the 25.57 vs 25.58 USDT friction variance down to the penny.
2. **Multi-Year Binance Vision Coverage Inventory:** Cataloged 60 monthly periods (2022-01 to 2026-12), confirming 57 complete monthly archives available on official Binance Vision CDN (2022-01 to 2026-09). Downloaded, hashed, and verified 3 distinct market regime pilots (Bear: 2022-05, Bull: 2023-01, Sideways: 2023-07) with zero gaps, zero duplicates, and pristine OHLC bounds.
3. **Authentic Primary-Source Event Acquisition:** Cataloged 3 real-world events (BLS CPI May 2022, FOMC June 2022 Rate Hike, SEC Spot Bitcoin ETF Approval). Replaced unjustified static 60s latency assertions with empirically bounded availability uncertainty intervals $[\Delta t_{\min}, \Delta t_{\max}]$, and established that ALFRED vintage dates are daily publication dates rather than intraday timestamps.
4. **Real Event Causal Replay & Bidirectional Leak Prevention:** Executed historical replay across 5 decision moments around the real BLS CPI release, capturing a 16.5x volume surge (236 BTC to 3,909 BTC) and -1.83% price drop. Proved zero future information leakage via bidirectional forward-and-backward time stepping.
5. **Strict Executable Tests:** Added 9 tests executing directly against raw data files and byte arrays (36/36 tests passing across all recent sprints).

---

## 2. PHASE 1 — INDEPENDENT BENCHMARK RECALCULATION

### 2.1 Direct Parquet Recalculation with `Decimal` Precision
Using `market_state_dataset.parquet` (105,120 5m bars), calculations were performed directly from raw columns (`open`, `close`, `datetime_utc`) using Python's `Decimal` module:

- **Initial Capital:** 10,000.00 USDT
- **Allocation:** 98% (9,800.00 USDT allocated to BTC, 200.00 USDT cash reserve)
- **Fee Rate:** 0.0010 (10 bps) | **Slippage Rate:** 0.0005 (5 bps)
- **Terminal Bar:** Bar 105,119 (`2026-10-18T11:25:00Z` @ Close $82,104.03)

| Benchmark Metric | Bar 0 Inception (Full Sample) | Bar 576 Inception (Post-Warmup 48h) |
| :--- | :--- | :--- |
| **Inception Bar & Time** | Bar 0 (`2025-10-18T11:30:00Z`) | Bar 576 (`2025-10-20T11:30:00Z`) |
| **Entry Open Price** | $106,891.72 | $110,810.88 |
| **Entry Fill (with slip)** | $106,945.16586 | $110,866.28544 |
| **Entry Fee** | $9.80 USDT | $9.80 USDT |
| **Entry Slippage** | $4.90 USDT | $4.90 USDT |
| **Net Invested** | $9,790.20 USDT | $9,790.20 USDT |
| **BTC Quantity** | `0.09154411` BTC | `0.08830638` BTC |
| **Exit Fill (with slip)** | $82,062.977985 | $82,062.977985 |
| **Exit Fee (Exact)** | $7.512382... USDT | $7.246684... USDT |
| **Exit Slippage (Exact)** | $3.758070... USDT | $3.625155... USDT |
| **Terminal MTM Equity** | **$7,716.14 (-22.84%)** | **$7,450.31 (-25.50%)** |
| **Terminal Liquid Equity** | **$7,704.87 (-22.95%)** | **$7,439.44 (-25.61%)** |

### 2.2 Forensic Resolution of the 25.57 vs 25.58 USDT Cost Difference
The 1-cent variance documented between historical reports is resolved:
- **Unrounded Exact Friction Accumulation:**
  $$\text{Friction}_{\text{exact}} = \$9.80 + \$4.90 + \$7.246684... + \$3.625155... = \mathbf{\$25.571839... \to \$25.57\text{ USDT}}$$
- **Component-Wise Rounded Sum (Exchange Cash Ledger):**
  $$\text{Friction}_{\text{components}} = \$9.80 + \$4.90 + \$7.25 + \$3.63 = \mathbf{\$25.58\text{ USDT}}$$
Both values are mathematically exact under their documented conventions. For trade ledger accounting, exchange settlements post individual transactions rounded to the cent, resulting in 25.58 USDT in cumulative cash deductions.

### 2.3 Matched-Turnover Control Audit & Retracted Claims
- **Retraction of Static Subsampling Claim (-44.69%):** Sprint 11.17.1's reported -44.69% return from static subsampling is formally retracted. Static subsampling selected trades non-chronologically without preserving cash compounding or position continuity.
- **Dynamic Chronological Compounding Simulation ($Q_t = 0.98 \times \text{Cash}_t / P_t$):** Evaluating 1,000 forward chronological paths with random trade omission yielded a mean return of $-57.77\% \pm 1.35\%$ (terminal capital $\$4,223.14 \pm \$135.08$). In an asset with persistent downward drift (-22.95% to -25.61%), omitting trades preserves capital by reducing market exposure and transaction friction. The apparent session advantage is an artifact of trade suppression rather than timing alpha.
- **Retraction of N=19 Stop-Loss Reversal Claim:** The N=19 stop event sample has a 95% Wilson confidence interval of $[27.3\%, 68.3\%]$; no statistically valid claim of post-stop price reversal is supported.

---

## 3. PHASE 2 — MULTI-YEAR MARKET COVERAGE INVENTORY

### 3.1 2022–2026 Archive Catalog
An inventory of Binance Vision monthly 1-minute klines (`https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/`) was conducted:
- **Total Months Cataloged:** 60 months (2022-01 to 2026-12)
- **Remote Verified Available on Binance Vision:** 57 months (2022-01 to 2026-09)
- **Ongoing Month:** 2026-10 (available via daily archive `/daily/klines/`)
- **Future Months:** 2026-11, 2026-12

### 3.2 Distinct Market Regime Pilots Downloaded & Verified
To verify end-to-end data integrity across different market conditions, 3 distinct regime pilots were downloaded to `data/cache/` (gitignored) and verified against official `.CHECKSUM` files:

| Period | Market Regime | Official SHA-256 Checksum | 1m Bars | Monotonic 60s Step | Gaps / Dups | OHLC Violations | Monthly Return |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2022-01** | Baseline Benchmark | `ce0e16e834331e70b3041677c7f409818d5904bb59cb7b880695e4cacd34fc09` | 44,640 | 100% | 0 / 0 | 0 | -16.77% |
| **2022-05** | Bear / Stress (Terra/Luna) | `154311f08aa264e233b0c7b472aa490c8cfd1b6083ba86cf6c18134e50536b89` | 44,640 | 100% | 0 / 0 | 0 | -15.49% |
| **2023-01** | Bull / Recovery (Post-FTX) | `664116c2f33465d191684887f0d4834c02eb0a2635ada43eca855a99e6b6b0c5` | 44,640 | 100% | 0 / 0 | 0 | +39.80% |
| **2023-07** | Sideways / Consolidation | `8f32a4ef47bd758b33bfaf680a71792f8d97ca4d89ae55ff3d2272cc3974560c` | 44,640 | 100% | 0 / 0 | 0 | -4.07% |

All pilots exhibited zero gaps, zero duplicates, and zero OHLC violations ($L \le O, C \le H$; $H \ge L$; $V \ge 0$). No synthetic price filling was applied.

### 3.3 Multi-Year Capacity Planning (2022–2026)
- **Disk Storage:** 57 months compressed ZIP $\approx 131\text{ MB}$; uncompressed CSV $\approx 1.05\text{ GB}$; partitioned Parquet $\approx 350\text{ MB}$. Recommended disk buffer: 3.0 GB.
- **RAM Footprint:** Streaming chunked ingestion consumes $< 500\text{ MB}$. Full contiguous in-memory representation (float32/int64) occupies $\approx 220\text{ MB}$. Minimum system RAM: 4.0 GB.
- **Compute:** Multi-threaded checksum verification takes $\approx 20\text{s}$; Parquet conversion takes $\approx 45\text{s}$ on 4 cores.
- **Network:** Total download payload is $\approx 131\text{ MB}$ ($\approx 12\text{s}$ at 100 Mbps). Chunked batching (4 months/batch) with 500ms sleep prevents CDN rate limiting.
- **Git Governance:** Large raw data files are excluded via `.gitignore` in `data/cache/`. Only code, schemas, and small JSON manifests are committed to git.

---

## 4. PHASE 3 — AUTHENTIC HISTORICAL EVENT ACQUISITION

Three real-world primary-source events were acquired and fingerprinted ([`real_historical_event_inventory_11_18_1.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/real_historical_event_inventory_11_18_1.json)):

### 1. US Bureau of Labor Statistics (BLS) CPI May 2022 Release
- **Event ID:** `REAL-EVT-20220610-BLS-CPI`
- **Nominal Publication:** `2022-06-10T12:30:00Z` (08:30:00 US Eastern)
- **Official URL:** `https://www.bls.gov/news.release/archives/cpi_06102022.htm`
- **Source Precision:** Second-level scheduled embargo release.
- **Economic Value:** CPI-U YoY: 8.6% (Actual) vs 8.3% (Consensus Expected).
- **Availability Uncertainty Interval:** $[\Delta t_{\min} = 15\text{s}, \Delta t_{\max} = 120\text{s}]$ ($\text{Earliest: } 12:30:15\text{Z}, \text{Conservative: } 12:32:00\text{Z}$).
- **Content SHA-256:** `096377e8a38c238b163fcf13db1b2ad6b430c5e9db2ff8160824b209a3dc554f`
- **Licensing:** Public Domain (US Government Work, 17 U.S.C. § 105).

### 2. Federal Reserve FOMC 75 bps Rate Hike Statement
- **Event ID:** `REAL-EVT-20220615-FOMC-STATEMENT`
- **Nominal Publication:** `2022-06-15T18:00:00Z` (14:00:00 US Eastern)
- **Official URL:** `https://www.federalreserve.gov/newsevents/pressreleases/monetary20220615a.htm`
- **Source Precision:** Second-level scheduled release.
- **Economic Value:** Target Range: 1.50% - 1.75% (+75 bps, first 75 bps hike since 1994).
- **Availability Uncertainty Interval:** $[\Delta t_{\min} = 10\text{s}, \Delta t_{\max} = 90\text{s}]$ ($\text{Earliest: } 18:00:10\text{Z}, \text{Conservative: } 18:01:30\text{Z}$).
- **Content SHA-256:** `ec843f5544fcfa8269781cae93344d6db95454b5dfa929609f061f00ea1e457f`
- **Licensing:** Public Domain (US Government Work).

### 3. SEC Accelerated Spot Bitcoin ETF Approval Order
- **Event ID:** `REAL-EVT-20240110-SEC-ETF-APPROVAL`
- **Nominal Publication:** `2024-01-10T20:45:00Z` (15:45:00 US Eastern)
- **Official URL:** `https://www.sec.gov/files/rules/sro/nysearca/2024/34-99306.pdf`
- **Source Precision:** Minute-level EDGAR dissemination log (Release No. 34-99306).
- **Economic Value:** Accelerated approval for 11 spot bitcoin exchange-traded products.
- **Availability Uncertainty Interval:** $[\Delta t_{\min} = 60\text{s}, \Delta t_{\max} = 420\text{s}]$ ($\text{Earliest: } 20:46:00\text{Z}, \text{Conservative: } 20:52:00\text{Z}$).
- **Content SHA-256:** `0f8db9f18dd15f10b7b1ce81561da7038e8ec4344dbca8d5811776ceb613149e`
- **Licensing:** Public Domain (Federal Agency Rulemaking Order).

**Causal Governance Rules:**
1. **Rejection of Static Constants:** Unproven static 60s delays are rejected; uncertainty intervals $[\Delta t_{\min}, \Delta t_{\max}]$ reflect empirical distribution networks.
2. **ALFRED Vintage Distinction:** ALFRED vintage dates are daily publication dates (`YYYY-MM-DD`) utilized for revision tracking, not intraday availability timestamps.

---

## 5. PHASE 4 — REAL EVENT CAUSAL REPLAY VALIDATION

The upgraded `HistoricalReplayEngine` (v1.1.0) was evaluated on the authentic BLS CPI May 2022 release across five decision horizons ([`real_event_replay_audit_11_18_1.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/real_event_replay_audit_11_18_1.json)):

| Decision Horizon | Query Time (UTC) | Observed Bars | Last Closed Candle Close | Visible Events | Uncertain Status | State Hash (SHA-256) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$T - 10\text{m}$** | `2022-06-10T12:20:00Z` | 2,740 | $30,079.56 | `[]` | None | `8957ba8d6c813580436a5fae534f5d21a221f92aa3b02e60dafe2b0d876a4ba2` |
| **$T + 1\text{m}$** | `2022-06-10T12:31:00Z` | 2,742 | $30,106.32 | `[]` | `['REAL-EVT-BLS-CPI']` | `3788ff37fa7fcbe39c878e176da8e89f8d55fa48b89417c805eb38cb62287cf3` |
| **$T + 5\text{m}$** | `2022-06-10T12:35:00Z` | 2,743 | $29,553.89 | `['REAL-EVT-BLS-CPI']` | None | `2d5e227096e19c99e917d0966a3648356976f6bda207b8088be3355024479e09` |
| **$T + 10\text{m}$** | `2022-06-10T12:40:00Z` | 2,744 | $29,735.33 | `['REAL-EVT-BLS-CPI']` | None | `85a7061f185df1a2e79603e9fe7b797b5e43b17424683cfa6319803b9dd22df2` |
| **$T + 1\text{h}$** | `2022-06-10T13:30:00Z` | 2,754 | $29,449.16 | `['REAL-EVT-BLS-CPI']` | None | `8062ec7e5aa06a147d12f3bc30f9a941f6ca79d860d5dd70c6a51d957d9fbca8` |

### Key Empirical Findings:
1. **Market Microstructure Explosion:** At $T + 5\text{m}$ (first closed 5m bar containing the 12:30:00 release), volume surged **16.5x** (from 236 BTC pre-news to 3,909 BTC on the event bar), with an immediate $-1.83\%$ downward price revaluation.
2. **Uncertainty Window Handling:** At $T + 1\text{m}$ (12:31:00 UTC, within the $[15\text{s}, 120\text{s}]$ uncertainty interval), the event was correctly withheld from `visible_events` in conservative mode and flagged in `uncertain_events`, preventing premature trading on unconfirmed dissemination.
3. **Bidirectional State Invariance:** Stepping backward $T + 1\text{h} \to T + 10\text{m} \to T + 5\text{m} \to T + 1\text{m} \to T - 10\text{m}$ reproduced 100% bitwise identical state hashes as forward stepping. Zero state mutation or memory leak occurred.

---

## 6. PHASE 5 — EXECUTABLE TEST SUITE RESULTS

The dedicated test suite [`tests/test_sprint11_18_1_data_integrity.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_18_1_data_integrity.py) validates all requirements directly against source data:
- `test_independent_buy_and_hold_accounting_from_raw_parquet`: **PASSED**
- `test_sha256_file_verification_direct_bytes`: **PASSED**
- `test_binance_pilot_timestamp_normalization_and_continuity`: **PASSED**
- `test_resampling_price_and_volume_conservation`: **PASSED**
- `test_real_event_schema_and_primary_content_hash`: **PASSED**
- `test_real_event_replay_execution_and_hash_reproducibility`: **PASSED**
- `test_bidirectional_time_navigation_leak_prevention`: **PASSED**
- `test_availability_uncertainty_window_handling`: **PASSED**
- `test_chronological_matched_turnover_simulation`: **PASSED**

Across all recent sprint suites (11.16B.9, 11.17, 11.17.1, 11.18, 11.18.1): **36/36 tests passed**.

---

## 7. MANDATORY SCIENTIFIC DECLARATIONS & ACCEPTANCE GATES

```
================================================================================
ACCEPTANCE GATES — SPRINT 11.18.1
================================================================================
BENCHMARK_INDEPENDENTLY_VERIFIED=YES
MULTI_YEAR_COVERAGE_INVENTORIED=YES
REAL_HISTORICAL_EVENTS_VERIFIED=3
REAL_EVENT_CAUSAL_REPLAY=PASS
LOOKAHEAD_ISOLATION=PASS
RESEARCH_CONTAMINATION=PRESERVED
PROSPECTIVE_OBSERVATION=NOT_STARTED
LIVE_TRADING=PROHIBITED
OPERATOR_AUTHORIZATION=NOT_GRANTED
SPRINT_STATUS=PASS
================================================================================
```
