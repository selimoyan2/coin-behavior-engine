# CBE Sprint 11.16B.2 — Live Market Data Compatibility & Feature Sufficiency Audit

**Document Version:** 1.0.0-sprint11.16b.2  
**Target Ingestion Artifact:** `live_market_state.json` (published by container `zgit1s3n1acdtqtsxp0s44vj`)  
**Audit Standard:** Strict Mathematical Feature Sufficiency — No Feature Substitution  
**Auditor:** Quantitative Systems Architect & Research Data Auditor  

---

## 1. Executive Summary & Required Status Declaration

This audit conducted an end-to-end compatibility analysis between the data published in `live_market_state.json` and the empirical feature requirements of the five frozen prospective research policies (Policies A through E).

### Core Audit Finding
While `live_market_state.json` reliably provides closed 5-minute spot candle attributes (OHLCV, timestamps, heartbeat), **it is a single-candle scalar payload that lacks historical candle arrays, rolling window series, pre-calculated moving averages (48h, 72h), ATR inputs, and analogue reference libraries**.

Furthermore, the live capture container currently reports `contiguous_bars_count: 810`, which is **below the minimum 864 bars required for a 72-hour SMA**.

### Formal Declaration
```
MARKET_DATA_CONTRACT=INSUFFICIENT
```
Reading `live_market_state.json` in isolation is mathematically insufficient to evaluate Policies C, D, and E upon container startup. Prospective observation cannot begin until a safe, fail-closed historical feature feeding architecture is implemented.

---

## 2. Ingestion Artifact Audit: `live_market_state.json`

### 2.1 Empirical Payload Structure
Inspecting the live published state on host `srv1114257`:
```json
{
  "candle_interval": "5m",
  "classification": "LIVE_OBSERVED",
  "close_price_usdt": 81117.56,
  "contiguous_bars_count": 810,
  "exchange_source": "BINANCE_SPOT",
  "high_price_usdt": 81147.47,
  "is_closed": true,
  "is_live": true,
  "is_research_eligible": true,
  "low_price_usdt": 81117.55,
  "open_price_usdt": 81139.13,
  "price_change_24h_pct": 0.0167,
  "provenance_source": "LIVE_BINANCE_SPOT",
  "schema_version": "1.0.0",
  "snapshot_generation_timestamp_utc": "2026-10-18T21:50:00.294607+00:00",
  "spot_price_usdt": 81117.56,
  "symbol": "BTCUSDT",
  "timestamp_close_utc": "2026-10-18T21:49:59Z",
  "timestamp_open_utc": "2026-10-18T21:45:00Z",
  "volume_base": 12.14031,
  "volume_usdt": 984952.8010537,
  "warmup_status": "FULL_WINDOW_READY",
  "writer_heartbeat_utc": "2026-10-18T21:50:00.294607+00:00"
}
```

### 2.2 Field-by-Field Compliance Verification
| Required Specification | Target Field / Expression | In `live_market_state.json`? | Compliance Verdict |
|---|---|:---:|:---:|
| **BTCUSDT Symbol Identity** | `"symbol": "BTCUSDT"` | Yes | **PASS** |
| **5-Minute Interval** | `"candle_interval": "5m"` | Yes | **PASS** |
| **UTC Timestamps** | `timestamp_open_utc`, `timestamp_close_utc` | Yes | **PASS** |
| **Closed-Candle Confirmation** | `"is_closed": true` | Yes | **PASS** |
| **OHLCV Attributes** | `open_price_usdt`, `high_price_usdt`, `low_price_usdt`, `close_price_usdt`, `volume_base` | Yes | **PASS** |
| **Snapshot Generation Time** | `snapshot_generation_timestamp_utc` | Yes | **PASS** |
| **Writer Heartbeat Freshness** | `writer_heartbeat_utc` | Yes | **PASS** |
| **Continuity Indicator** | `contiguous_bars_count: 810` | Yes | **PASS** |
| **24h Rolling Change** | `price_change_24h_pct: 0.0167` | Yes (scalar) | **PASS** |
| **24h Fast SMA History** | Requires 288 consecutive close prices | **NO** | **FAIL (Missing series)** |
| **48h Trend SMA History** | Requires 576 consecutive close prices | **NO** | **FAIL (Missing series)** |
| **72h Slow SMA History** | Requires 864 consecutive close prices | **NO** | **FAIL (Missing series)** |
| **ATR Volatility Lookback** | Requires high/low/close array (14-288 bars) | **NO** | **FAIL (Missing series)** |
| **Analogue Reference Windows**| Requires historical analogue database | **NO** | **FAIL (Missing library)** |

---

## 3. Mathematical Gaps & Policy Feature Incompatibilities

### 3.1 Policy C: 48-Hour Trend Following Model
- **Frozen Requirement:** $SMA_{576} = \frac{1}{576}\sum_{i=0}^{575} P_{\text{close}}[t-i]$.
- **Defect:** `live_market_state.json` provides only $P_{\text{close}}[t]$. A cold-started observer reading only this file has $N=1$ candle, making $SMA_{576}$ mathematically undefinable for $575$ bars (47.9 hours).

### 3.2 Policy D: Selective Regime-Aware Trend Policy
- **Frozen Requirements:**
  - Fast SMA: 24h = 288 bars.
  - Slow SMA: 72h = 864 bars.
  - ATR volatility band: $\frac{\text{ATR}_{14}}{P} \in [0.015, 0.065]$.
  - Anti-chase extension: $\frac{P - SMA_{288}}{SMA_{288}} \le 2.25\%$.
- **Defect:** Requires a minimum of **864 contiguous 5m bars**.
  - Currently, `contiguous_bars_count` on the host is **810** (< 864).
  - Even if `contiguous_bars_count` exceeds 864, the snapshot does not transmit the historical close array.

### 3.3 Policy E: Selective Analogue-Assisted Spot Policy
- **Frozen Requirements:** All Policy D inputs + $k$-NN pattern matching over historical market regimes with similarity $\ge 0.75$ and positive directional probability $\ge 0.60$.
- **Defect:** Analogue pattern matching requires comparing the current normalized 48-bar sequence against an indexed database of hundreds of historical analog candidates. This library is completely absent from the live snapshot volume.

---

## 4. Architectural Resolution Without Modifying Live Capture

The sprint mandate strictly forbids modifying Live Capture (`zgit1s3n1acdtqtsxp0s44vj`) or accessing unauthorized raw evidence. Furthermore, **silently replacing missing features with zero, default probabilities, or synthetic data is prohibited**.

### Safe Architecture Design: The Shadow Rolling Ring Buffer & Seed Ingestion

```
+-----------------------------------------------------------------------------------+
| Host Filesystem (Strictly Read-Only Mount)                                        |
| Volume: zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:ro                      |
|                                                                                   |
|  +---------------------------+                                                    |
|  | live_market_state.json    | (Atomic JSON, 1 closed bar every 5m)                |
|  +-------------+-------------+                                                    |
+----------------|------------------------------------------------------------------+
                 | AtomicSnapshotIO.safe_read()
                 v
+-----------------------------------------------------------------------------------+
| CBE Prospective Shadow Observer Container (Air-Gapped: network_mode="none")       |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Shadow Feature Buffer Manager (Capacity: 1,000 bars)                        |  |
|  |                                                                             |  |
|  | 1. On Cold Start:                                                          |  |
|  |    - Load frozen analogue library from bundled container image.             |  |
|  |    - Ingest historical seed partition (bars 104,256 to 105,120) from        |  |
|  |      immutable local bundle IF authorized, OR enter WARMUP_BUFFERING mode.  |  |
|  |                                                                             |  |
|  | 2. On Every New 5m Candle (live_market_state.json):                         |  |
|  |    - Verify candle continuity (timestamp monotonic, sequence contiguous).   |  |
|  |    - Append OHLCV to RingBuffer deque(maxlen=1000).                         |  |
|  |    - Check len(RingBuffer) >= 864:                                          |  |
|  |      * If < 864: Emit NO_DECISION_DATA (Insufficient Warmup).                |  |
|  |      * If >= 864: Compute exact SMA_288, SMA_576, SMA_864, ATR_14.          |  |
|  |                                                                             |  |
|  | 3. Fail-Closed Guard:                                                       |  |
|  |    - If gap detected, feed stale (>15m), or RingBuffer < 864:               |  |
|  |      * Emits NO_DECISION_DATA (if cash) or POSITION_OPEN_DATA_STALE (if long) |  |
|  |      * NEVER zero-fills or defaults probabilities.                          |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### Safety Principles of the Design
1. **Zero Mutation of Live Capture:** Live Capture continues its existing publication routine without code or configuration alterations.
2. **Zero Default Fallbacks:** If the internal buffer has fewer than 864 bars, the engine issues `NO_DECISION_DATA` with evidence rationale `"INSUFFICIENT_WARMUP_BARS: count={N} < 864"`.
3. **Analogue Library Bundling:** The analogue library is built into the read-only image layers (`/app/models/analogue_library_v1.parquet`), completely decoupled from the real-time live feed.

---

## 5. Conclusion & Activation Prerequisite
Until the Shadow Observer is packaged with an internal ring buffer manager and verified to hold $\ge 864$ contiguous bars:
```
MARKET_DATA_CONTRACT=INSUFFICIENT
```
This technical blocker prevents immediate prospective scoring and must be resolved before authorization.
