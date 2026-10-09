# OPERATOR RUNBOOK: APPROVAL 3 PREPARATION
## SAFE BINANCE SPOT MARKET DATA CAPTURE FOUNDATION

> [!CAUTION]
> **PREPARATION ONLY — APPROVAL 3 HAS NOT BEEN GRANTED**
> This document specifies the operational design, data provenance, resource footprints, and authorization procedures for future live Binance market data collection.
> **DO NOT ACTIVATE LIVE COLLECTION, RUN NETWORK STREAMS, OR TRIGGER DEPLOYMENT.**

---

## 1. ARCHITECTURAL OVERVIEW & ISOLATION BOUNDARIES

The market data capture engine is designed as an isolated, single-pair (`BTCUSDT`), single-interval (`5m`) ingestion pipeline that writes to an append-only, tamper-evident ledger (`raw_candles_BTCUSDT_5m.jsonl`) backed by continuous SHA-256 hash chaining.

```
+---------------------------------------------------------------------------------------------------+
| SHARED HOST (srv1114257)                                                                          |
|                                                                                                   |
|  [ PRODUCTION WORKSPACE ]                      [ CBE-0.8.0 SHADOW CAPTURE (APPROVAL 3 DESIGN) ]   |
|  CBE-0.7.0 Live Service                        cbe_080_coolify_inert (Currently DEPLOYED_INERT)  |
|  - SQLite DB / Active Worker                   - Zero Database Connections                        |
|  - Unaffected by Shadow Staging                - Inbound-Only Binance Spot BTCUSDT 5m Stream      |
|  - Production Data at data/prospective/        - Isolated Volume: cbe_080_shadow_data             |
|                                                - Raw Storage: data/shadow_v080/raw_candles/       |
|                                                - Quarantine: data/shadow_v080/quarantine/         |
|                                                - Memory Ceiling: 300 MiB / CPU Quota: 0.25        |
|                                                - Approval 4 (Scoring): STRICTLY DISABLED          |
|                                                - Trading: PERMANENTLY PROHIBITED                  |
+---------------------------------------------------------------------------------------------------+
```

### Core Separation of Gates:
1. **Gate 1 (Offline Engineering):** Active and permitted (offline testing, deterministic fixtures).
2. **Gate 2 (Inert Staging Landing):** Completed (`cbe_080_coolify_inert` landed inert with exit 0).
3. **Gate 3 (Live Market Data Capture):** **NOT GRANTED**. Requires explicit operator approval.
4. **Gate 4 (Prospective Scored Inference):** **NOT GRANTED**. Requires separate future approval after 288 contiguous bars.

---

## 2. MARKET DATA CONTRACT & VALIDATION INVARIANTS

Every incoming candle payload must satisfy the following strict criteria before acceptance:

| Parameter | Mandatory Requirement | Violation Consequence |
| :--- | :--- | :--- |
| **Exchange** | Binance Spot | Rejected |
| **Symbol** | `BTCUSDT` (exact match) | Quarantined (`INVALID_SYMBOL`) |
| **Interval** | `5m` (300,000 ms) | Quarantined (`INVALID_INTERVAL`) |
| **Market Type** | `SPOT` only (no derivatives or futures) | Quarantined (`INVALID_MARKET_TYPE`) |
| **Closure Status** | Confirmed closed (`is_closed=True`, `x=True`) | Rejected (`OPEN_CANDLE_REJECTED`) |
| **Timestamp Alignment** | `timestamp_open % 300_000 == 0` | Quarantined (`TIMESTAMP_NOT_ALIGNED_TO_5M`) |
| **Interval Duration** | `timestamp_close == timestamp_open + 299_999` | Quarantined (`INVALID_INTERVAL_DURATION`) |
| **Price Invariants** | `open, high, low, close > 0`, `high >= low`, `high >= open/close`, `low <= open/close` | Quarantined (`PRICE_INVARIANT_VIOLATION`) |
| **Volume Invariant** | `volume >= 0.0` (non-negative) | Quarantined (`NEGATIVE_VOLUME`) |
| **Duplicates** | Exact timestamp + identical payload | Idempotently ignored (no duplicate write) |
| **Conflicting Duplicates** | Exact timestamp + conflicting payload | Quarantined (`CONFLICTING_PAYLOAD`) |

---

## 3. DATA PROVENANCE MODEL

Raw market evidence is categorized into mutually exclusive provenance tiers to preserve scientific integrity:

1. `OFFLINE_FIXTURE`: Synthetic or replayed historical test fixtures.
2. `HISTORICAL_REPLAY`: Historical closed candles used for offline backtesting or warm-up.
3. `WARMUP_REPLAY`: Initial historical candles loaded to seed the rolling buffer.
4. `LIVE_BINANCE_SPOT`: Genuine live market candles received during authorized Approval 3 observation.
5. `REST_GAP_RECOVERY`: Historical candles backfilled to recover a sequence gap.

> [!IMPORTANT]
> **PROVENANCE RULE:**
> No fixture or replay record may ever be labeled as `LIVE_BINANCE_SPOT`.
> Data backfilled under `REST_GAP_RECOVERY` can NEVER be submitted to prospective inference scoring or counted as genuine prospective observations.

---

## 4. RESOURCE CONSUMPTION & VPS SAFETY BUDGETS

The capture foundation is engineered to share VPS resources without starving production:

- **CPU Utilization:** < 0.01 cores at rest (poll/sleep model; 1 processing tick every 5 minutes). Maximum peak < 0.05 CPU.
- **Memory (RSS):** Bounded rolling buffer (maximum 350 candles in memory $\approx$ 1.5 MB). Process RSS is capped at 150 MB internally, with a 300 MB hard container limit.
- **Inbound Queue Bounds:** Inbound transport message queue is limited to 500 messages with fail-safe backpressure (`QueueOverflowError`).
- **Disk I/O:** 1 atomic append write every 5 minutes ($\approx$ 250 bytes per candle). Zero random write thrashing.
- **Storage Growth:**
  - 288 candles/day $\approx$ 72 KB/day $\approx$ 26.3 MB/year.
  - Quarantined logs and audit trails are bounded with log rotation (`10m x 3`).
- **Database Load:** ZERO. The market capture foundation does not use SQLite or connect to any production database.

---

## 5. GAP DETECTION & CRASH RECOVERY POLICY

### Gap Detection
- Expected next open timestamp: `previous_open + 300,000 ms`.
- If `incoming_open > expected_open`, missing bars are calculated: `(incoming_open - expected_open) // 300_000`.
- A `GapEvent` is recorded, and the contiguous bar counter is reset to 1.
- Contiguity invariant: minimum 288 contiguous closed 5m candles without unrecovered gaps is required for `FULL_WINDOW_READY`.

### Crash Recovery
- On container start/restart, `RawMarketEvidenceStore.verify_and_recover_chain()` reads all entries in `raw_candles_BTCUSDT_5m.jsonl`.
- Verifies every per-record SHA-256 hash and the unbroken continuity of `prev_hash == previous.entry_hash`.
- If a sudden host reboot or container kill occurred mid-write, any trailing partial line at EOF is atomically truncated back to the last valid entry.
- If mid-chain tampering or corruption is detected, the store fails closed with `EvidenceCorruptionError`.

---

## 6. HOW OPERATORS VERIFY COLLECTION REMAINS DISABLED

To confirm that market data collection is currently disabled in the staging environment:

1. **Verify Environment Variables:**
   ```bash
   docker inspect cbe_080_coolify_inert --format '{{json .Config.Env}}'
   # Must contain:
   # "CBE_BINANCE_COLLECTION_ENABLED=false"
   # "CBE_PROSPECTIVE_OBSERVATION_ENABLED=false"
   # "CBE_TRADING_DISABLED=true"
   ```

2. **Verify Network Isolation:**
   ```bash
   docker inspect cbe_080_coolify_inert --format '{{.HostConfig.NetworkMode}}'
   # MUST RETURN: none
   ```

3. **Verify Container Quiescence:**
   ```bash
   docker ps -a --filter "name=cbe_080_coolify_inert" --format "table {{.Names}}\t{{.Status}}"
   # MUST SHOW: Exited (0)
   ```

4. **Verify Zero Binance REST/WS Sockets:**
   ```bash
   ss -tanp | grep -E "binance|stream|9443"
   # MUST RETURN ZERO CONNECTIONS
   ```

---

## 7. FUTURE ACTIVATION PROCEDURE (UPON EXPLICIT APPROVAL 3 ONLY)

> **DO NOT EXECUTE PRIOR TO FORMAL OPERATOR AUTHORIZATION.**

When Approval 3 is granted, activation will follow this procedure:

1. **Prerequisites:**
   - Operator signs off on Approval 3.
   - Production CBE-0.7.0 verified healthy with $\ge$ 2.0 GiB available VPS RAM.
   - Host clock synchronized via NTP (drift < 100 ms).

2. **Compose Configuration Update (Staging Compose Only):**
   - Change `network_mode: "none"` to an egress-restricted network allowing outbound HTTPS/WSS to Binance.
   - Set `CBE_BINANCE_COLLECTION_ENABLED=true`.
   - Set `CBE_APPROVAL_3_AUTHORIZED=true`.
   - Keep `CBE_PROSPECTIVE_OBSERVATION_ENABLED=false` (Approval 4 remains locked).
   - Keep `CBE_TRADING_DISABLED=true` (Permanently locked).

3. **Trigger Deployment:**
   - Execute single-container manual build in Coolify.
   - Monitor logs: confirm connection, initial 5m candle receipt, and zero trading.

---

## 8. SAFE SHUTDOWN & ROLLBACK PROCEDURE

If any feed anomaly, rate limit issue, or resource concern arises:

1. **Immediate Stop in Coolify:**
   Click **Stop** in the Coolify dashboard for `cbe_080_coolify_inert`.
   Alternatively, run on host:
   ```bash
   docker stop -t 10 cbe_080_coolify_inert
   ```

2. **Preserve Immutable Ledger:**
   The raw market evidence in `cbe_080_shadow_data` is preserved automatically.

3. **Confirm Production Integrity:**
   ```bash
   docker ps --filter "name=coin-behavior-engine" --format "table {{.Names}}\t{{.Status}}"
   ls -la /opt/coin-behavior-engine/data/prospective/
   ```
