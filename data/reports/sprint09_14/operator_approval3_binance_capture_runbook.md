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

### Forensic Recovery & In-Place Truncation
- On container start/restart, `RawMarketEvidenceStore.verify_and_recover_chain()` streams `raw_candles_BTCUSDT_5m.jsonl` line-by-line without loading entire history into memory.
- Bounded memory footprint: maintains a rolling cache of 1,000 recent candles and an integer timestamp index.
- Verifies every per-record SHA-256 hash and the unbroken continuity of `prev_hash == previous.entry_hash`.
- If a sudden host reboot or container kill occurred mid-write at EOF:
  1. A forensic binary copy of corrupted trailing bytes is preserved in `quarantine/forensic_trailing_corruption_<timestamp>.bin`.
  2. The backup file is verified for completeness and SHA-256 hash match.
  3. A recovery audit log is written to `quarantine/recovery_audit.jsonl`.
  4. The file is truncated in-place using `os.truncate` at the exact valid offset. Preceding valid history is NEVER rewritten or altered.
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

> [!CAUTION]
> **DO NOT EXECUTE PRIOR TO FORMAL OPERATOR AUTHORIZATION.**
> Approval 3 has NOT been authorized. This procedure is documented for future authorized execution only.

When Approval 3 is granted, activation will follow this procedure:

1. **Prerequisites:**
   - Operator signs off on Approval 3.
   - Production CBE-0.7.0 verified healthy with $\ge$ 2.0 GiB available VPS RAM.
   - Host clock synchronized via NTP (drift < 100 ms).

2. **Dedicated Live Compose Deployment:**
   - Use dedicated compose file: `deploy/shadow_v080/docker-compose.coolify-live-capture.yaml`.
   - Dedicated persistent volume: `cbe_080_live_capture_data` (strictly separated from inert staging `cbe_080_shadow_data` and production data).
   - Set environment variables:
     - `CBE_BINANCE_COLLECTION_ENABLED=true`
     - `CBE_APPROVAL_3_AUTHORIZED=true`
     - `CBE_PROSPECTIVE_OBSERVATION_ENABLED=false` (Approval 4 remains locked)
     - `CBE_TRADING_DISABLED=true` (Permanently locked)

3. **Network Egress Controls (Host-Level Filtering):**
   To enforce least-privilege outbound networking on the shared host, apply iptables / nftables egress filtering to restrict container traffic strictly to Binance WebSocket (port 9443) and REST (port 443):
   ```bash
   # Identify container IP or docker bridge interface
   CONTAINER_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cbe_080_coolify_live_capture)

   # Allow DNS resolution (port 53 UDP/TCP)
   iptables -A DOCKER-USER -s $CONTAINER_IP -p udp --dport 53 -j ACCEPT
   iptables -A DOCKER-USER -s $CONTAINER_IP -p tcp --dport 53 -j ACCEPT

   # Allow Binance WSS (port 9443) and HTTPS (port 443)
   iptables -A DOCKER-USER -s $CONTAINER_IP -p tcp --dport 443 -j ACCEPT
   iptables -A DOCKER-USER -s $CONTAINER_IP -p tcp --dport 9443 -j ACCEPT

   # Drop all other outbound connections from live capture container
   iptables -A DOCKER-USER -s $CONTAINER_IP -j DROP
   ```

4. **Trigger Deployment & Monitor:**
   - Execute deployment in Coolify.
   - Monitor logs: confirm connection, initial 5m candle receipt, and zero trading.

---

## 8. SAFE SHUTDOWN & ROLLBACK PROCEDURE

If any feed anomaly, rate limit issue, or resource concern arises:

1. **Immediate Stop in Coolify:**
   Click **Stop** in the Coolify dashboard for `cbe_080_coolify_live_capture`.
   Alternatively, run on host:
   ```bash
   docker stop -t 10 cbe_080_coolify_live_capture
   ```

2. **Preserve Immutable Ledger:**
   The raw market evidence in `cbe_080_live_capture_data` is preserved automatically.

3. **Confirm Production Integrity:**
   ```bash
   docker ps --filter "name=coin-behavior-engine" --format "table {{.Names}}\t{{.Status}}"
   ls -la /opt/coin-behavior-engine/data/prospective/
   ```

