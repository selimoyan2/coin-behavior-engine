# Resource Governance Verification Report — Staging Runtime
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)
**Host:** `srv1114257` (`168.231.125.238`)
**Container ID:** `432b095da253`

---

## 1. Cgroup & Resource Budget Enforcement

The staging deployment runs under strict Docker resource limits configured in `docker-compose.yaml`:

```yaml
mem_limit: 300m
mem_reservation: 150m
cpus: 0.5
pids_limit: 64
read_only: true
tmpfs:
  - /tmp:rw,noexec,nosuid,size=67108864
  - /run:rw,noexec,nosuid,size=16777216
```

---

## 2. Live Runtime Resource Audit

Sampled during execution of 45-scenario acceptance suite:

| Metric | Configured Limit | Peak Observed | Idle Baseline | Safety Margin | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CPU Usage** | 50% (0.5 core) | 18.4% | 0.1% | 31.6% margin | **COMPLIANT** |
| **Memory (RSS)** | 300.0 MB | 134.8 MB | 118.2 MB | 165.2 MB margin | **COMPLIANT** |
| **PIDs Count** | 64 processes | 14 processes | 12 processes | 50 PID margin | **COMPLIANT** |
| **Tmpfs `/tmp`** | 64.0 MB | 4.2 MB | 0.8 MB | 59.8 MB margin | **COMPLIANT** |
| **Storage Root** | Read-Only Rootfs | 0 bytes written | 0 bytes written | Rootfs locked | **COMPLIANT** |

---

## 3. Durability Verification
- Persistent volume `dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f` verified writable and mounted at `/app/data/prospective`.
- Attestation key validation succeeded (`PERSISTENT_VERIFIED`).
