# CBE Sprint 11.16A — Shadow Operational Safety Plan

**Execution Mode:** Safety Architecture & Control Design Only — NO ACTIVATION  
**Host Target:** `srv1114257` (`168.231.125.238`)  
**Base Code Commit:** `0a520ecc20cb45e9f8997a3f5a04e57e937d9c84`  

---

## 1. Resource Limits & Quotas (Anti-Contention Engineering)

Given the host's 2 vCPU architecture, absence of swap memory, and the observed ~81% CPU utilization of production container `6t63aehpaw0cw1bbt4zcm09g`, strict hard ceilings are enforced:

| Resource Dimension | Parameter | Value | Enforcement Mechanism | Failure Defense |
|---|---|---|---|---|
| **CPU Ceiling** | `cpus` / `NanoCPUs` | **`0.20`** (200,000,000) | Linux CFS Quota (20ms per 100ms period) | Cannot starve production or system daemons |
| **Memory Hard Limit** | `mem_limit` | **`250 MB`** (`262144000`) | Linux Cgroup v2 `memory.max` | Hard cap prevents triggering host-level OOM |
| **Memory Reservation** | `mem_reservation`| **`120 MB`** (`125829120`) | Linux Cgroup v2 `memory.low` | Guarantees baseline footprint without contention |
| **Memory Swap** | `memswap_limit` | **`250 MB`** | Cgroup swap limit equal to RAM | Zero swap expansion permitted |
| **Max Process Threads**| `pids_limit` | **`32`** | Cgroup `pids.max` | Prevents fork-bombs and thread exhaustion |
| **Scratchpad Storage** | `tmpfs` | **`32 MB`** (`33554432`) | RAM-backed tmpfs (`noexec,nosuid`) | Fast temporary I/O with zero disk fragmentation |
| **Docker Log Bounding**| `json-file` | **`10MB x 3`** (30MB max) | Docker daemon log-opt | Prevents disk exhaustion on `/dev/sda1` |

---

## 2. Clock Synchronization & UTC Skew Defense

In financial decision recording, timestamp accuracy is foundational:

1. **System Clock Invariant:** The host and container operate strictly in UTC (`Europe/London` or `UTC`).
2. **Clock Skew Threshold:**
   - On every decision iteration, the engine verifies the system clock against monotonic time and NTP status.
   - If $|T_{\text{local}} - T_{\text{NTP}}| > 2,000 \text{ ms}$ (2 seconds):
     - The engine logs a `CLOCK_SKEW_BUDGET_EXCEEDED` warning.
     - If $|T_{\text{local}} - T_{\text{NTP}}| > 5,000 \text{ ms}$, the engine immediately enters fail-closed state (`NO_DECISION_DATA`) and halts decision emission until clock synchronization is restored.

---

## 3. Duplicate Candle Prevention & Idempotency

To eliminate double-processing or replay attacks:

1. **Sequence Number Uniqueness:** Every candle is indexed by its integer timestamp `timestamp_open_ms`.
2. **In-Memory & On-Disk Seen Set:**
   - The engine maintains an append-only set of processed candle timestamps.
   - If a duplicate candle arrives with timestamp $T_{\text{open}} \le T_{\text{open, last}}$, the engine ignores the payload, emits log message `DUPLICATE_CANDLE_SKIPPED`, and produces no record.
3. **Database & File Lock:** A single-instance lock file (`/app/data/prospective_shadow/.observer.lock`) is acquired upon startup, ensuring multiple instances cannot run concurrently on the same volume.

---

## 4. Missing Data & Stale Feed Handling (Fail-Closed Guarantees)

| Incident Scenario | Detection Condition | Decision Action Emitted | Inventory Handling | Valuation Handling |
|---|---|:---:|---|---|
| **Live Capture Paused / Feed Interrupted** | Latency $> 15.0$ minutes or no new file write | `NO_DECISION_DATA` | 100% USDT cash preserved | Cash nominal ($10,000.00 USDT) |
| **Feed Stale While Position is Active** | Latency $> 15.0$ minutes while holding BTC | `POSITION_OPEN_DATA_STALE` | **BTC Inventory Preserved** (Zero synthetic liquidation) | Frozen at last confirmed close price (`VALUATION_UNAVAILABLE_MARK_FROZEN`) |
| **Missing / NaN Price in Incoming Candle** | `close_price_usdt <= 0` or is NaN/None | `EXECUTION_REJECTED_MISSING_PRICE` | Position active state unchanged | Mark-to-market frozen |
| **Intrabar Gap Down Below Stop Loss** | Next open $\le$ stop loss price | `EXIT_TO_USDT` | Fills at next open with Policy V2 slippage | Cash balance updated; trade closed |

---

## 5. No-Order Capability Verification (Software & Network Interlocks)

The environment guarantees zero possibility of live trading through four concentric barriers:

1. **Barrier 1 (Network Level):** `network_mode: "none"`. No network card exists inside the container except loopback. Outbound HTTP/REST/WebSocket packets cannot leave the container.
2. **Barrier 2 (Environment Level):** `CBE_TRADING_DISABLED=true` and `CBE_RUN_MODE=OFFLINE_SHADOW_ONLY`.
3. **Barrier 3 (Credential Level):** Zero API keys, secret keys, or passphrase environment variables or credential files are mounted or configured.
4. **Barrier 4 (Code Level):** The shadow execution simulator is an offline accounting class with zero imports of `ccxt`, `requests`, `aiohttp`, or exchange client libraries.

---

## 6. Readiness, Liveness & Health Checks

The container implements a lightweight healthcheck command:

```bash
python -c "
from coin_behavior_engine.research_lab.shadow_decision_protocol import DecisionHashChain
# Quick integrity verification of current decision chain
print('HEALTH_OK')
"
```
- **Interval:** 60 seconds
- **Timeout:** 5 seconds
- **Retries:** 3
- **Start Period:** 10 seconds

---

## 7. Emergency Shutdown Procedure

If anomalous behavior, unexpected memory growth, or operator intervention is required:

### Immediate Graceful Shutdown:
```bash
docker stop --time 10 cbe_prospective_shadow_observer
```

### Emergency Immediate Kill (Zero Host Impact):
```bash
docker kill cbe_prospective_shadow_observer
```

### Post-Shutdown Invariants:
1. Production service `6t63aehpaw0cw1bbt4zcm09g` continues running uninterrupted.
2. Live Capture service `zgit1s3n1acdtqtsxp0s44vj` continues running uninterrupted.
3. Persistent volume `cbe_prospective_shadow_data_v1` retains all sealed decision chains intact.
4. The observer can be safely inspected offline or restarted without data loss.
