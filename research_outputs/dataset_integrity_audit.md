# CBE Sprint 11.12 Canonical Dataset Integrity Audit & Benchmark Lock

**Date:** 2026-10-18  
**Scope:** Canonical Dataset Fingerprinting, Continuity Verification, and Immutable Benchmark Specification  
**System:** Coin Behavior Engine (CBE) — Research Lab  
**Status:** **BENCHMARK LOCKED & VERIFIED**  

---

## 1. Canonical Dataset Identification & Fingerprint

| Attribute | Canonical Verified Specification | Status |
|---|---|---|
| **File Path** | `research_outputs/market_state_dataset.parquet` | VERIFIED |
| **SHA-256 Fingerprint** | `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487` | IMMUTABLE LOCK |
| **Trading Symbol** | `BTCUSDT` | VERIFIED |
| **Candlestick Interval** | `5m` (300 seconds) | VERIFIED |
| **Total Candle Count** | `105,120` continuous bars | VERIFIED |
| **Continuity** | Exactly `0` missing intervals ($100\%$ continuity) | VERIFIED |
| **Dataset Start Time** | `2025-10-18T11:30:00Z` (`1760787000000`) | VERIFIED |
| **Dataset End Time** | `2026-10-18T11:25:00Z` (`1792322700000`) | VERIFIED |
| **First Bar Open Price**| `$106,891.72` USD | VERIFIED |
| **Final Bar Close Price**| `$82,104.03` USD | VERIFIED |
| **Minimum Price** | `$57,800.19` USD | VERIFIED |
| **Maximum Price** | `$116,400.00` USD | VERIFIED |

---

## 2. Holdout Test Partition Specification

All strategy evaluations in Sprint 11.10, 11.11, and 11.12 are evaluated on the exact out-of-sample holdout slice:

- **Partition Index Range:** `[86,724 : 105,120)` (18,396 bars, exactly 63.875 days)
- **Start UTC:** `2026-08-15T14:30:00Z` (Timestamp: `1786804200000`)
- **End UTC:** `2026-10-18T11:25:00Z` (Timestamp: `1792322700000`)
- **Starting BTC Price:** `$63,040.01` USD (Bar 86,724 Open)
- **Ending BTC Price:** `$82,104.03` USD (Bar 105,119 Close)
- **Underlying Market Return:** `+30.24%`

---

## 3. Canonical Portfolio Accounting Invariants

1. **Initial Capital:** Exactly \$10,000.00 USDT for every strategy.
2. **Execution Timing:** Next-bar open execution. Decisions emitted at bar $t$ close fill at bar $t+1$ open.
3. **Institutional Transaction Friction:**
   - Taker Fee: 10 bps ($0.10\%$) on both entry and exit notionals.
   - Execution Slippage: 5 bps ($0.05\%$) on both entry and exit notionals.
   - Total Roundtrip Friction: 25 bps ($0.25\%$).
4. **Conservation of Cash and BTC Inventory:**
   - Cash cannot become negative.
   - BTC cannot be sold short (Spot long-only, zero leverage).
   - Capital conservation identity: $\text{Starting Equity} + \text{Net PnL} = \text{Ending Equity}$ holds exactly for every strategy.
5. **Mandatory Terminal Liquidation:**
   - Any open position at bar 105,119 is liquidated at closing price minus taker fee and slippage, ensuring ending equity equals final cash balance.
