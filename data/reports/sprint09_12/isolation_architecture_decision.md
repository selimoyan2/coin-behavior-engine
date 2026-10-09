# ISOLATION ARCHITECTURE DECISION MATRIX & SPECIFICATION

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**SELECTED DESIGN:** Dedicated Coolify-Managed Docker Container (Architecture A)  

---

## 1. COMPARATIVE EVALUATION OF ISOLATION OPTIONS

| Architecture | Description | Pros | Cons | Recommendation |
|:---|:---|:---|:---|:---:|
| **Option A: Dedicated Coolify Container** | Independent container managed via Coolify UI / Compose | • Strict cgroup memory & CPU limits<br>• Isolated non-root user<br>• Dedicated persistent volume<br>• Clean emergency stop | • Container daemon memory overhead (~20–30 MB) | **SELECTED** |
| **Option B: Standalone Restricted Process** | Systemd unit or background process on host | • Minimal memory overhead (~15 MB less) | • Difficult rollback in Coolify<br>• Host-level dependency management<br>• Weaker isolation from host OS | **REJECTED** |
| **Option C: Shared Transport / In-Process Worker** | Reusing CBE-0.7.0 market data transport | • Zero new Binance API calls | • Violates CBE-0.7.0 freeze<br>• Any crash crashes production<br>• Shared database risk | **STRICTLY PROHIBITED** |

---

## 2. DETAILED ISOLATION CONTROLS

The selected Architecture A enforces 10 strict isolation invariants:

1. **No Inbound Public HTTP Port:** Container exposes ZERO ports (`ports:` stanza omitted entirely). No HTTP dashboard, webhook, or external attack surface.
2. **Dedicated Storage Volume:** Writes strictly to `cbe_080_shadow_data`. Has ZERO mounts or permissions to `/app/data/production` or CBE-0.7.0 databases.
3. **Non-Root Execution:** Runs as unprivileged user `1000:1000`.
4. **CGroup Memory Ceiling:** Hard limit `300M` (`deploy.resources.limits.memory: 300M`).
5. **CGroup CPU Quota:** Hard limit `cpus: '0.25'` (maximum 25% of a single core).
6. **Bounded Logging:** Docker json-file logging capped at `max-size: "10m"`, `max-file: "3"`.
7. **Read-Only Codebase:** Application code mounted read-only or immutable in container image.
8. **No Automatic Redeployment:** Coolify Webhook / Git polling set to Manual Only.
9. **Zero Production Mutation:** Zero changes to CBE-0.7.0 worker codebase, database schemas, or crons.
10. **Single-Command Rollback:** `docker stop cbe_080_prospective_shadow` terminates the service in < 2 seconds.
