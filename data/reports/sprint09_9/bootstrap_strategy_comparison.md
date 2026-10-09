# SPRINT 09.9: BOOTSTRAP & WARM-UP STRATEGY COMPARISON

**EVALUATION DATE:** 2026-10-09  
**PROBLEM STATEMENT:** The legacy production worker fetches only 60 candles (`limit=60`) per poll. The canonical CBE-0.8.0 features require a contiguous 288-candle (24-hour) rolling window. How can a future capture process safely populate its 350-candle bounded buffer without lookahead, without production mutation, and with strict crash-recovery?

---

## 1. STRATEGY COMPARISON MATRIX

| Dimension | Option A: Incremental Accumulation (Poll 60x repeatedly) | Option B: One-Time Historical Bootstrap (Fetch 350 on start) | Option C: Validated Local Snapshot Restore | Option D: Full Causal Cold Warm-Up |
| :--- | :--- | :--- | :--- | :--- |
| **Causal Correctness** | Fails initially (Repeatedly polling the same 60 candles does not yield 350 unique bars) | **PASS** (Fetches immediately prior closed candles; strictly past data) | **PASS** (Restores validated past closed candles) | **PASS** (Zero external history; purely accumulates live closed bars) |
| **Network Requests** | Wasteful (redundant polls of identical candles) | 1 request on startup (`/api/v3/klines?limit=350`) | **0 network requests** | 1 request per 5 min for 24 hours (288 requests) |
| **Production Impact** | Zero (if isolated), but useless for 350-bar lookback | Zero (isolated independent read-only call) | **Zero (pure local file read)** | Zero (isolated independent read-only calls) |
| **Restart Safety** | Poor (resets lookback on every restart) | Moderate (re-fetches 350 bars on every process crash) | **Excellent** (Restores buffer instantly in < 10 ms) | Poor (Requires 24 hours of waiting after every crash) |
| **Data Continuity** | Gaps if process restarts; takes 24h to reach 288 | Continuous if API responds | **Continuous if snapshot is fresh (< 5m old)** | Discontinuous on any process interruption |
| **Disk Footprint** | None | None | **~85 KB per snapshot file** | None |
| **Operational Complexity**| Low (but defective) | Low | Low-Moderate | Low |
| **Failure Modes** | Lookback starvation; cannot compute 24h features | API rate limit / temporary network timeout | Snapshot corruption or stale snapshot | 24-hour latency before first prediction |

---

## 2. SCIENTIFIC & ENGINEERING RECOMMENDATION

### Recommended Hybrid Strategy: **Option C + Option B Fallback**
1. **Primary On Startup (Option C)**:
   - Check for local `candle_buffer_snapshot.json`.
   - Verify SHA-256 checksum and schema integrity.
   - If snapshot is valid and fresh (last close time within 300 seconds), load buffer and transition to `FULL_WINDOW_READY`.
2. **Secondary Fallback On Cold Start or Stale Snapshot (Option B)**:
   - If no snapshot exists, or snapshot is corrupt, or snapshot age > 300s (gap detected):
   - Issue a single, one-time read-only REST call to Binance `/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=350`.
   - Validate geometry and monotonic continuity of all 350 closed candles.
   - Populate buffer and immediately write a pristine atomic snapshot.
3. **Fail-Closed Safeguard (Option D)**:
   - If both local snapshot and initial API bootstrap fail, the system transitions to `WARMING_UP` and strictly suppresses prospective prediction scoring until 288 genuine live candles have accumulated.

**Conclusion**: Repeatedly fetching the existing 60-candle feed (Option A) is fundamentally incapable of bootstrapping a 288-bar lookback. The snapshot-first hybrid approach minimizes network dependency while eliminating 24-hour downtime on routine process restarts.
