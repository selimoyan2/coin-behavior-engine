# CBE Sprint 11.16A — Shadow Environment Discovery & Infrastructure Audit

**Execution Date:** 2026-10-18T20:30:00Z (Local UTC+3: 2026-10-18T23:30:00+03:00)  
**Host Server:** `srv1114257` (`168.231.125.238`)  
**Base Code Commit:** `0a520ecc20cb45e9f8997a3f5a04e57e937d9c84`  
**Mode:** Strictly Read-Only Infrastructure Discovery — Zero Mutation  

---

## 1. Executive Summary

In accordance with CBE Sprint 11.16A Phase 1 instructions, a strictly read-only inspection of host server `srv1114257` was conducted. All four protected services were independently verified in their live states. System resources (CPU, RAM, swap, and disk) were measured, and resource contention risks were analyzed.

No containers were started, stopped, restarted, or modified. Zero configuration changes were made.

---

## 2. Protected Services Inventory & Live State

All four protected service identifiers specified in the Sprint 11.16A mandate were discovered and inspected:

| Service Role | Coolify Resource UUID | Live Container Name & ID | Runtime State | Memory Limit | CPU Limit | Network Mode | Volume Mounts |
|---|---|---|:---:|:---:|:---:|:---:|---|
| **1. Production CBE** | `6t63aehpaw0cw1bbt4zcm09g` | `6t63aehpaw0cw1bbt4zcm09g-215804874969`<br>`(a5510203abd2)` | **`running`**<br>(Up 21 hours) | **Unlimited** (`0`) | **Unlimited** (`0`) | `coolify`<br>(bridge) | `/var/lib/docker/volumes/6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data/_data`<br>$\rightarrow$ `/app/data/prospective` (`:rw`) |
| **2. Staging Market Intel** | `dzzfws54by1whlbq6fk4ywut` | `cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261016T221942`<br>`(ffec81e484f5)` | **`running`**<br>(Up 46 hours) | **300.0 MB**<br>(`314572800`) | **0.50 CPU**<br>(`500000000`) | `dzzfws54by1whlbq6fk4ywut`<br>(bridge) | 1. `/var/lib/docker/volumes/zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data/_data`<br>$\rightarrow$ `/app/data/live_capture` (**`:ro`**) <br>2. `b1b780dc...` $\rightarrow$ `/app/data/prospective` (`:rw`) |
| **3. Live Capture** | `zgit1s3n1acdtqtsxp0s44vj` | `cbe-080-live-capture-zgit1s3n1acdtqtsxp0s44vj-20261009T230053`<br>`(50b43f0da76a)` | **`running`**<br>(Up 37 hours) | **300.0 MB**<br>(`314572800`) | **0.25 CPU**<br>(`250000000`) | `zgit1s3n1acdtqtsxp0s44vj`<br>(bridge) | `/var/lib/docker/volumes/zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data/_data`<br>$\rightarrow$ `/app/data/live_capture` (**`:rw`**, Exclusive Writer) |
| **4. Stopped Scoring Worker** | `3v3dey5y1ybg6zqkv0wmuxtd` | `cbe-080-scoring-worker-3v3dey5y1ybg6zqkv0wmuxtd-20261011T214253`<br>`(82b53934d374)` | **`exited (137)`**<br>(2 days ago) | **300.0 MB**<br>(`314572800`) | **0.25 CPU**<br>(`250000000`) | **`none`**<br>(Isolated) | 1. `/var/lib/docker/volumes/zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data/_data`<br>$\rightarrow$ `/app/data/live_capture` (**`:ro`**)<br>2. `3v3dey5y1ybg6zqkv0wmuxtd_cbe-080-prospective-data` $\rightarrow$ `/app/data/prospective` (`:rw`) |

---

## 3. Host System Hardware & Resource Limits

Live hardware inspection was executed via Linux system diagnostics:

```text
Host: Linux srv1114257 6.8.0-147-generic #147-Ubuntu SMP PREEMPT_DYNAMIC
CPU Cores: 2 vCPUs (x86_64)
Total Memory: 7,940 MB (7.755 GiB)
Used Memory: 4,955 MB (62.4%)
Available Memory: 2,985 MB (37.6%)
Swap Memory: 0 MB (SWAP DISABLED)
Root Disk Space (/): 96 GB Total | 53 GB Used (55%) | 44 GB Available (45%)
```

---

## 4. Resource Contention Analysis (CRITICAL RISK IDENTIFIED)

Live `docker stats --no-stream` telemetry reveals a significant operational constraint:

1. **Production Container Load:**
   - Container `6t63aehpaw0cw1bbt4zcm09g-215804874969` was observed consuming **81.31% CPU** and **615.7 MiB RAM**.
   - Because production has **no Docker memory limit** (`Memory = 0`) and **no CPU quota** (`NanoCPUs = 0`), it operates with unbounded resource access.
2. **Absence of Swap Space:**
   - Host system has **`Swap: 0 MB`**. Any host-wide memory exhaustion will immediately trigger the Linux kernel Out-Of-Memory (OOM) killer. If an unconstrained container allocates excessive memory, the OOM killer could terminate the production service.
3. **Mandatory Shadow Constraint:**
   - Any future prospective shadow observation container **must** enforce:
     - Strict memory hard limit: `mem_limit: 250M` (with `mem_reservation: 120M`).
     - Strict CPU quota: `cpus: 0.20` (throttled CFS quota to guarantee $\ge 1.80$ vCPUs remain available for production and system tasks).
     - Thread process limit: `pids_limit: 32`.

---

## 5. Docker Networks Audit

Inspection of `docker network ls` identified the following bridge topologies:

| Network Name | Driver | Scope | Connected CBE Services | Isolation Status |
|---|:---:|:---:|---|---|
| `3v3dey5y1ybg6zqkv0wmuxtd` | bridge | local | Scoring worker network (worker currently in `network_mode: "none"`) | Isolated |
| `dzzfws54by1whlbq6fk4ywut` | bridge | local | Staging service `cbe-market-intelligence-staging` | Isolated |
| `zgit1s3n1acdtqtsxp0s44vj` | bridge | local | Live Capture service `cbe-080-live-capture` | Outbound WebSocket to Binance Spot |
| `coolify` | bridge | local | Production service `6t63aehpaw0cw1bbt4zcm09g`, proxy, coolify-db | Production mesh |
| `none` | null | local | Used by stopped scoring worker | 100% air-gapped |

---

## 6. Live Evidence & Historical Market Data Sources

Inspection of volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data` confirmed continuous data ingestion:

- **Total Volume Footprint:** `6.1 MB`
- **Active Real-Time Snapshot:** `/app/data/live_capture/live_market_state.json`
  - Last generation timestamp: `2026-10-18T20:30:00.308256+00:00`
  - Latest observed BTC price: `$80,943.34 USDT`
  - Contiguous 5-minute bars recorded: **794 bars**
  - Heartbeat status: `FULL_WINDOW_READY`
- **Raw WebSocket Stream Journal:** `/app/data/live_capture/raw_market/raw_candles_BTCUSDT_5m.jsonl` (2.1 MB, immutable append-only hash-chained candles).
- **SQLite Fast Index:** `/app/data/live_capture/raw_market/index_BTCUSDT_5m.sqlite3` (84 KB + 3.7 MB WAL).
- **REST Gap Recovery Journal:** `/app/data/live_capture/raw_market/recovery_candles_BTCUSDT_5m.jsonl` (196 KB).
- **Canonical Offline Baseline Dataset:** `research_outputs/market_state_dataset.parquet` (105,120 candles, SHA-256 `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487`).

---

## 7. Discovery Conclusion

The physical host and container topology are fully mapped. Protected services remain 100% intact, untruncated, and unmodified. The path forward requires strict resource throttling and independent storage to safeguard the production environment.
