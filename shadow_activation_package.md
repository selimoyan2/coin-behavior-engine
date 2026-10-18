# CBE Sprint 11.16B.2 — Prospective Shadow Activation Package

**Document Version:** 1.0.0-sprint11.16b.2  
**Target Host Server:** `srv1114257` (`168.231.125.238`)  
**Deployment State:** INERT ARTIFACT — AWAITING OPERATOR AUTHORIZATION  
**Prospective Observation Status:** `NOT_STARTED`  
**Live Trading Status:** `PROHIBITED`  
**Auditor:** Quantitative Systems Architect & Deployment Reliability Lead  

---

## 1. Executive Summary & Activation Invariants

This package provides the complete, pre-flight verified specification for operating the five-policy prospective shadow observation container on host `srv1114257`.

### Core Deployment Invariants
1. **Zero Contention Guarantee:** Constrained by Linux CFS to `cpus: '0.20'` and `memory: 250M` (Peak RSS: 115.8 MB; 2.16x headroom).
2. **Complete Network Air-Gap:** Container runs with `network_mode: "none"`. It has no network interface (`eth0` absent) and cannot communicate with any network socket, exchange API, or remote host.
3. **Protected Service Immunity:** All four existing host services (Production, Staging, Live Capture, Stopped Scoring Worker) remain completely untouched and unmutated.
4. **Strict Read-Only Factual Ingestion:** Ingests `live_market_state.json` via a read-only volume mount (`:ro`). Zero write handles to capture storage.
5. **Standby Mode:** The proposed Docker Compose specification ([`shadow_observer.compose.proposed.yml`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/shadow_observer.compose.proposed.yml)) is strictly an **inert artifact**. Deployment commands have NOT been executed.

---

## 2. Technical Specification & Container Manifest

| Configuration Item | Concrete Value / Setting | Grounded Verification / Purpose |
|---|---|---|
| **Container Name** | `cbe-prospective-shadow-observer-v1` | Unique container identifier; zero collision with existing services. |
| **Image Reference** | `cbe-prospective-shadow:1.0.0-sprint11.16b` | Immutable reproducible build tag. |
| **Base Code Commit** | `b5bc3f69c2027fc23984eb5d661400437cdd9f97` | Commit HEAD of Sprint 11.16B.1. |
| **Policy Manifest Digest** | `6d6f181eb65001b4b9817b650273127731f05b03ad42858032a7f09f7045f1e8` | SHA-256 of `prospective_freeze_manifest_v2.json`. |
| **Network Configuration** | `network_mode: "none"` | Physical air-gap; outbound order routing impossible. |
| **CPU Resource Limit** | `cpus: '0.20'` (20 ms per 100 ms CFS period) | Peak execution latency is 1.175 ms; zero CPU contention. |
| **Memory Resource Limit**| `memory: 250M` | Peak RSS is 115.8 MB; provides 134.2 MB free headroom. |
| **PIDs Limit** | `pids: 32` | Prevents fork-bombs; runtime operates with 1 thread. |
| **Input Data Source** | `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:ro` | Volume mounted strictly read-only (`MS_RDONLY`). |
| **Output Data Storage** | `cbe_prospective_shadow_data_v1` | Independent named volume for append-only logs. |
| **Trading Configuration** | `CBE_TRADING_DISABLED=true` | Code-level assertion preventing order generation. |

---

## 3. Protected Services Inventory & Isolation Boundary

The four protected services on host `srv1114257` must remain completely untouched:

| Service Name | Container UUID / Name | Current State | Isolation Guarantee |
|---|---|:---:|---|
| **Production CBE Service** | `6t63aehpaw0cw1bbt4zcm09g`<br>`6t63aehpaw0cw1bbt4zcm09g-215804874969` | `running` | Runs on network `coolify`, volume `6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data`. Zero shared storage or network with shadow. |
| **Market Intelligence Staging** | `dzzfws54by1whlbq6fk4ywut`<br>`cbe-market-intelligence-staging-...` | `running` | Bound to `127.0.0.1:18080`. Mounts capture volume `:ro`. |
| **Live Capture Service** | `zgit1s3n1acdtqtsxp0s44vj`<br>`cbe-080-live-capture-...` | `running` | Exclusive `:rw` writer to `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data`. |
| **Stopped Scoring Worker** | `3v3dey5y1ybg6zqkv0wmuxtd`<br>`cbe-080-scoring-worker-...` | `exited (137)`| Exited worker; zero CPU/RAM impact. Left untouched. |

---

## 4. Operational Runbook: Health, Shutdown & Recovery

### 4.1 Health-Check Specification
The container health check evaluates the liveness of the prospective evaluation loop every 300 seconds:
```bash
python -c "import sys, json, time, pathlib; p = pathlib.Path('/app/data/shadow/ledgers/shadow_observer_heartbeat.json'); sys.exit(0 if p.is_file() and (time.time() - p.stat().st_mtime < 600) else 1)"
```
- If no heartbeat is updated within 600 seconds (2 missed 5m candles), the container is flagged `unhealthy`.

### 4.2 Graceful Shutdown Procedure
If the operator needs to pause or stop observation:
```bash
docker stop -t 30 cbe-prospective-shadow-observer-v1
```
The daemon intercepts `SIGTERM`, flushes the current in-memory decision record, fsyncs the hash chain index, writes a clean shutdown entry, and exits cleanly.

### 4.3 Recovery Procedure
Upon restart:
1. Daemon re-reads `prospective_five_policy_equity_ledger.csv` and the last block of each policy's `.jsonl` chain.
2. Re-computes SHA-256 digests from Genesis to head; if any discrepancy is detected, fails closed with `INTEGRITY_COMPROMISED`.
3. Re-loads the historical ring buffer and resumes prospective observation.

### 4.4 Audit Log Locations
- **Decisions Log:** `/app/data/shadow/decisions/policy_*_decisions.jsonl`
- **Outcomes Log:** `/app/data/shadow/outcomes/prospective_shadow_outcomes.jsonl`
- **Checkpoints:** `/app/data/shadow/checkpoints/daily_checkpoint_*.json`
- **Equity Ledger:** `/app/data/shadow/ledgers/prospective_five_policy_equity_ledger.csv`

---

## 5. Explicit Operator Authorization Requirements

Before launching the container, the human operator must complete three actions:
1. **Market Data Access Grant:** Sign the access grant for `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:ro`.
2. **Anchor Policy Freeze Commit:** Execute `git tag -s v11.16b2-prospective-freeze-baseline` with GPG private key.
3. **Approve Container Launch:** Review the compatibility audit and execute `docker compose -f shadow_observer.compose.proposed.yml up -d`.
