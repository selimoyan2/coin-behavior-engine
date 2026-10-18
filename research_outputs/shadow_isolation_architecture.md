# CBE Sprint 11.16A — Shadow Observation Environment Isolation Architecture

**Execution Mode:** Architectural Design & Preflight Verification Only — NO ACTIVATION  
**Host Target:** `srv1114257` (`168.231.125.238`)  
**Base Code Commit:** `0a520ecc20cb45e9f8997a3f5a04e57e937d9c84`  

---

## 1. Architectural Mission & Tenets

The prospective shadow observation environment is designed to execute the five frozen candidate research policies on real, incoming BTC/USDT market data without active trading, without external order placement capability, and with complete physical and logical isolation from existing production and staging services.

### Core Non-Negotiable Invariants:
1. **Zero Production Mutation:** The container must not mount, write, or connect to any production database, SQLite file, or production volume (`6t63aehpaw0cw1bbt4zcm09g-*`).
2. **Zero Order Routing Capability:** The container must execute with `network_mode: "none"`. It possesses zero network sockets, eliminating any physical ability to transmit orders to Binance or any other exchange.
3. **Strict Resource Caps:** CPU quota must not exceed `0.20` vCPU and memory must not exceed `250 MB` to prevent resource starvation or OOM triggers on the host.
4. **Single-Direction Data Flow:** Live market data is accessed exclusively via a read-only (`:ro`) mount to the live capture evidence volume.
5. **Fail-Closed Default:** If market data is stale, corrupted, or unavailable, the container must freeze valuation, emit `NO_DECISION_DATA` or `POSITION_OPEN_DATA_STALE`, and take zero speculative action.

---

## 2. Container Isolation Specification

The prospective shadow observer architecture is formalized in the following Docker Compose configuration:

```yaml
version: '3.8'

services:
  cbe-prospective-shadow-observer:
    image: cbe-080-shadow:prospective-observer-frozen
    container_name: cbe_prospective_shadow_observer
    restart: "no"
    network_mode: "none"                  # Absolute air-gap: zero outbound network access
    read_only: true                       # Immutable root filesystem
    user: "1000:1000"                     # Non-root unprivileged execution
    pids_limit: 32                        # Thread starvation protection
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL                               # Drop all Linux kernel capabilities
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=33554432  # 32 MB non-executable temporary scratchpad
    environment:
      - CBE_ENV=prospective_shadow_observer
      - PYTHONUNBUFFERED=1
      - CBE_SYMBOL=BTCUSDT
      - CBE_INTERVAL=5m
      - CBE_LIVE_CAPTURE_DIR=/app/data/live_capture
      - CBE_SHADOW_DATA_DIR=/app/data/prospective_shadow
      - CBE_TRADING_DISABLED=true         # Software kill-switch permanently locked
      - CBE_RUN_MODE=OFFLINE_SHADOW_ONLY  # Prohibits order placement APIs
      - CBE_RECORD_LABEL=PROSPECTIVE_SHADOW
      - CBE_BASE_CODE_COMMIT=0a520ecc20cb45e9f8997a3f5a04e57e937d9c84
    mem_limit: 250m
    mem_reservation: 120m
    memswap_limit: 250m                   # Zero swap expansion permitted
    cpus: 0.20                            # Hard limit: maximum 20% of 1 core (10% of total host)
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    volumes:
      # Authorized read-only access to live market evidence
      - zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:/app/data/live_capture:ro
      # Fully isolated writable persistence for shadow decision chains and ledgers
      - cbe_prospective_shadow_data:/app/data/prospective_shadow:rw

volumes:
  zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:
    external: true
    name: ${CBE_CAPTURE_VOLUME_NAME:-zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data}
  cbe_prospective_shadow_data:
    name: cbe_prospective_shadow_data_v1
```

---

## 3. Detailed Isolation Dimension Analysis

```mermaid
flowchart TD
    subgraph Host["Host Server srv1114257 (2 vCPUs, 7.8GB RAM, 0MB Swap)"]
        subgraph Production["Production Ecosystem (FROZEN / UNTOUCHED)"]
            PROD_APP["Production Container (6t63aehpaw0cw1bbt4zcm09g)\nCPU: 81.3% | RAM: 615MB | Network: coolify"]
            PROD_VOL[("6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data\nPROD STORAGE")]
            PROD_APP -->|rw| PROD_VOL
        end

        subgraph Ingestion["Live Capture Engine (Approval 3)"]
            CAP_APP["cbe-080-live-capture (zgit1s3n1acdtqtsxp0s44vj)\nNetwork: zgit1s3n1acdtqtsxp0s44vj\nIngests Binance WebSocket"]
            CAP_VOL[("zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data\nRAW EVIDENCE JOURNAL")]
            CAP_APP -->|Exclusive rw| CAP_VOL
        end

        subgraph Shadow["Prospective Shadow Observer (Proposed / INERT)"]
            SHADOW_APP["cbe-prospective-shadow-observer\nCPU: <= 0.20 | RAM: <= 250MB | Network: NONE\nTRADING_DISABLED=true"]
            SHADOW_VOL[("cbe_prospective_shadow_data_v1\nINDEPENDENT DECISION LEDGER")]
            SHADOW_APP -->|rw| SHADOW_VOL
        end
    end

    CAP_VOL -.->|STRICTLY READ-ONLY (:ro)| SHADOW_APP
    SHADOW_APP x-.-x|NO CONNECTION / NO MUTATION| PROD_APP
    SHADOW_APP x-.-x|NO ACCESS / NO MOUNT| PROD_VOL
```

### 1. Independent Identity
The shadow observer container possesses its own distinct name (`cbe_prospective_shadow_observer`), image tag (`cbe-080-shadow:prospective-observer-frozen`), and unprivileged UID `1000:1000`. It does not reuse or share any container namespace.

### 2. Independent Storage Volume
All decision logs, hash chains, outcome records, and policy ledgers are written exclusively to `cbe_prospective_shadow_data_v1`. It has zero access to production volume `6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data` or staging volume `b1b780dc...`.

### 3. Read-Only Ingestion Boundary
Volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data` is mounted with the Docker `:ro` attribute. The Linux kernel guarantees that even root inside the container cannot write, truncate, or lock any file within this volume.

### 4. Zero Order Routing / Air-Gap
Configuring `network_mode: "none"` strips the container of all network interfaces except the loopback (`lo`). Any attempt by Python or any library to initiate an outbound socket connection raises an immediate `OSError: [Errno 101] Network is unreachable`.

### 5. Independence from Existing Services
The shadow container operates as a completely decoupled consumer. It does not require starting, stopping, restarting, or signalling `cbe-080-live-capture`, `cbe-market-intelligence-staging`, or production. If the shadow container terminates, neither production nor live capture is affected.

---

## 4. Crash Isolation & Blast Radius Assessment

| Failure Mode | Impact on Production | Impact on Live Capture | Behavior of Shadow Observer |
|---|:---:|:---:|---|
| **Shadow Container OOM (exceeds 250MB)** | **Zero** | **Zero** | Kernel terminates only `cbe-prospective-shadow-observer` with exit code 137. Production and capture continue unaffected. |
| **Shadow Process Unhandled Exception** | **Zero** | **Zero** | Container stops cleanly with `restart: "no"`. Preserved append-only logs remain intact on volume. |
| **Live Capture Restart / Temporary Interruption** | **Zero** | N/A | Shadow observer detects stale timestamp, emits `NO_DECISION_DATA` / `POSITION_OPEN_DATA_STALE`, and waits without crashing. |
| **Host High CPU Load (>95%)** | **Zero** | **Zero** | Linux CFS throttles shadow observer to at most 0.20 CPU, ensuring production retains execution priority. |

---

## 5. Architectural Verdict

The proposed shadow isolation architecture satisfies 100% of the isolation and safety requirements. It guarantees zero mutation to protected services, eliminates order-placement capabilities, and establishes an immutable read-only boundary for future observation.
