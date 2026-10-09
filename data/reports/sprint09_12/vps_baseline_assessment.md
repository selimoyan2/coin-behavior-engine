# HOST RESOURCE BASELINE & OPERATIONAL CAPACITY ASSESSMENT

**HOST IDENTIFIER:** `srv1114257`  
**EVIDENCE SOURCE:** Operator-supplied read-only host telemetry (2026-10-09)  
**STATUS:** SINGLE-TIME SNAPSHOT AUDIT (NOT PROOF OF SUSTAINED CAPACITY)  

---

## 1. OBSERVED TELEMETRY SUMMARY

| Metric | Measured Value | Operational Interpretation |
|:---|:---:|:---|
| **Physical RAM** | ~7.8 GiB (~8,192 MB) | Base system capacity |
| **Used RAM** | ~4.5 GiB (57.7%) | Consumed by existing websites, databases, and Docker |
| **Available RAM** | ~3.2 GiB (41.0%) | Unallocated physical memory available for buffers and new services |
| **Swap Space** | **0 MB (NO SWAP)** | **CRITICAL:** Kernel OOM killer terminates processes immediately if RAM exhausts |
| **CPU Cores** | 2 logical cores | Shared across host OS and all container workloads |
| **Load Average** | 1.40 / 1.02 / 0.88 | Moderate baseline load (70% capacity on 2 cores) |
| **Root Disk** | 96 GB Total / 51 GB Available | 53% disk headroom (ample for shadow storage) |
| **Active Containers** | ~25 Docker containers | High multi-tenancy (Coolify, databases, production services) |
| **dmesg OOM Excerpt** | No matches found | No recent OOM events in supplied buffer sample |

---

## 2. SCIENTIFIC & OPERATIONAL INTERPRETATION

### Critical Finding: Zero Swap Architecture
Host `srv1114257` has **0 swap**. This means:
1. Memory allocation is completely unbuffered. If host available memory drops to zero, the Linux kernel invokes the `out_of_memory` (OOM) killer immediately.
2. Any candidate container must have a hard cgroup memory ceiling (`memory: 300M`) so that if the candidate leaks memory, Docker kills ONLY the shadow collector container and leaves neighbor websites and databases completely unharmed.

### Single-Time Snapshot Caution
The absence of OOM lines in the supplied dmesg excerpt indicates that no OOM killer invocations occurred in the recent ring buffer window. However, this is a single-time snapshot and does not prove historical absence of memory spikes during traffic surges or automated database backups.

### Operating Margin Plan
- **Candidate Budget:** Proposed container ceiling of **300 MB** represents:
  $$rac{300	ext{ MB}}{3,200	ext{ MB Available}} = \mathbf{9.37\%} 	ext{ of available RAM}$$
  $$rac{300	ext{ MB}}{8,192	ext{ MB Total}} = \mathbf{3.66\%} 	ext{ of total host RAM}$$
- **Safety Buffer:** Leaves **~2.9 GiB (>90%)** of available memory untouched for existing production databases, web servers, and operating system caches.
