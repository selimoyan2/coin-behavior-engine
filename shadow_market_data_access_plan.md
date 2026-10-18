# CBE Sprint 11.16A — Shadow Market Data Access Plan

**Execution Mode:** Architecture Design & Verification Only — NO ACTIVATION  
**Target Ingestion:** BTC/USDT 5-Minute Closed Candles  
**Source Baseline:** Volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data`  

---

## 1. Evaluation of Market Data Access Pathways

To supply real-time BTC/USDT market candles to the future prospective shadow engine, two technical pathways were evaluated:

| Technical Pathway | Architectural Design | Security & Air-Gap Profile | Resource & Network Impact | Feasibility & Recommendation |
|---|---|---|---|:---:|
| **Pathway A:<br>Authorized Read-Only Volume Mount** *(Recommended)* | Mounts existing volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data` in strict read-only mode (`:ro`). Reads `live_market_state.json` and `raw_candles_BTCUSDT_5m.jsonl`. | **Complete Air-Gap:** Container runs with `network_mode: "none"`. Zero outbound network access. Impossible to transmit trade orders. | **Zero Network Overhead:** No additional WebSocket connections or REST polling. Negligible disk read overhead. | **`RECOMMENDED (PENDING OPERATOR AUTHORIZATION)`** |
| **Pathway B:<br>Separate Public Market-Data Ingestion** *(Rejected)* | Deploys a new background collector process inside the shadow container connecting directly to Binance Spot public WebSocket/REST. | **Air-Gap Broken:** Requires `network_mode: "bridge"`, creating outbound TCP sockets and introducing attack surface / trading risk. | **Duplicate Load:** Doubles network I/O, memory footprint, and CPU overhead on a host with only 2 vCPUs and ~80% production load. | **`REJECTED`** |

---

## 2. Pathway A Ingestion Architecture & Data Contract

When authorized by an operator, the shadow observer will ingest candles via the read-only mount point `/app/data/live_capture`.

### Primary Ingestion Artifact: `live_market_state.json`
Every 5 minutes, `cbe-080-live-capture` writes an atomic JSON snapshot:
- **`timestamp_open_utc` & `timestamp_close_utc`:** Candle boundary in UTC.
- **`open_price_usdt`, `high_price_usdt`, `low_price_usdt`, `close_price_usdt`:** Verified OHLCV.
- **`volume_base` & `volume_usdt`:** Trade volume.
- **`is_closed`:** Must be `true` before evaluation.
- **`contiguous_bars_count`:** Continuous health indicator.
- **`writer_heartbeat_utc`:** Ingestion daemon liveness.

```json
{
  "candle_interval": "5m",
  "classification": "LIVE_OBSERVED",
  "close_price_usdt": 80943.34,
  "contiguous_bars_count": 794,
  "exchange_source": "BINANCE_SPOT",
  "high_price_usdt": 80997.09,
  "is_closed": true,
  "is_live": true,
  "is_research_eligible": true,
  "low_price_usdt": 80865.45,
  "open_price_usdt": 80868.01,
  "spot_price_usdt": 80943.34,
  "symbol": "BTCUSDT",
  "timestamp_close_utc": "2026-10-18T20:29:59Z",
  "timestamp_open_utc": "2026-10-18T20:25:00Z"
}
```

---

## 3. Data Freshness, Gaps & Timestamp Integrity Verification

The shadow observer must enforce three deterministic verification gates before processing any candle:

### Gate 1: Candle Finalization Lock
- If `is_closed != true`, the candle is still accumulating volume. The observer **refuses** evaluation and waits until the 5-minute bar closes.

### Gate 2: Latency & Staleness Ceiling (Fail-Closed)
- Let $T_{\text{obs}}$ be the candle `timestamp_close_utc`.
- Let $T_{\text{avail}}$ be the file modification time (`mtime`) of `live_market_state.json`.
- Latency is calculated as: $\Delta t = T_{\text{avail}} - T_{\text{obs}}$.
- Invariant:
  $$\Delta t \le 15.0 \text{ minutes} (900 \text{ seconds})$$
- If $\Delta t > 900\text{s}$ or if `live_market_state.json` fails to update for $> 15$ minutes, the observer immediately transitions to **`POSITION_OPEN_DATA_STALE`** (if holding BTC) or **`NO_DECISION_DATA`** (if in cash).

### Gate 3: Timestamp Continuity & Gap Detection
- Every closed 5m bar must have $T_{\text{open}}(t) = T_{\text{close}}(t-1) + 1\text{s}$.
- If a sequence gap is detected ($T_{\text{open}}(t) - T_{\text{close}}(t-1) > 1\text{s}$):
  1. The observer consults `recovery_candles_BTCUSDT_5m.jsonl`.
  2. If the gap was formally recovered and verified by Live Capture's recovery state machine, the recovered candles are processed in sequence.
  3. If the gap remains unrecovered, the observer emits a fail-closed decision with evidence rationale `GAP_UNRESOLVED_DATA_FROZEN` and freezes valuation without inventing synthetic fills.

---

## 4. Operator Authorization Boundary

In strict compliance with sprint restrictions:
- Protected raw evidence in volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data` **is not accessed by any prospective scoring engine** during Sprint 11.16A.
- Pathway A is fully specified and ready, but remains **`BLOCKED_PENDING_OPERATOR_AUTHORIZATION`**.
- Zero modifications to Live Capture container configuration were made.
- Zero new data-collection jobs were deployed.
