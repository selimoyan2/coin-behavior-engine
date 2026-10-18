# CBE Sprint 11.16B.2 — Real Process Resource Validation & Container Headroom Audit

**Document Version:** 1.0.0-sprint11.16b.2  
**Target Specifications:** Docker cgroup `memory: 250M`, `cpus: '0.20'`, `pids_limit: 32`  
**Execution Standard:** Strictly Empirical Process-Level Profiling (Native OS Working Set / RSS)  
**Auditor:** Quantitative Systems Reliability & Performance Engineer  

---

## 1. Executive Summary & Core Verdict

The Sprint 11.16B.1 benchmark utilized Python `tracemalloc`, which measures internal heap allocations (recording 5.2 MB) but omits the base Python interpreter binary, shared C/C++ extension libraries (`numpy`, `pandas`), dynamic linkers, and page tables.

This audit conducted an isolated offline benchmark measuring **true native OS Resident Set Size (RSS)**, peak resident working set, sustained multi-candle memory growth, and process concurrency under the full five-policy execution runtime.

### Core Metrics Summary
| Metric | Measured Process Value | Proposed Container Limit | Margin / Safety Factor |
|---|:---:|:---:|:---:|
| **Interpreter Base RSS** | **26.18 MB** | — | Initial binary working set |
| **RSS After C-Extension Imports** | **106.99 MB** | 250.0 MB | Python + NumPy + Pandas footprint |
| **RSS After 5-Policy Initialization** | **106.99 MB** | 250.0 MB | Negligible instantiation overhead (<0.02 ms) |
| **Peak Resident Set Size (Peak RSS)** | **115.75 MB** | 250.0 MB | **2.16x Headroom (134.25 MB free)** |
| **Sustained Memory Growth (1,000 bars)**| **5.76 MB** | — | ~5.76 KB / bar across 5 chains |
| **Average Decision Latency** | **0.183 ms / candle** | 300,000 ms (5 min) | **0.00006% duty cycle** |
| **Peak Single-Candle Latency** | **1.175 ms** | 100 ms CFS quota period | Well within 20 ms CFS budget |
| **Observed Process Threads** | **1 thread** | 32 PIDs | 32x headroom |

### Architectural Verdict
- **30-Day Prospective Evaluation (8,640 bars):** **`SAFE`**. Starting from 107 MB and accumulating $\sim 5.76\text{ MB} / 1,000\text{ bars}$, total memory reaches $\sim 156.8\text{ MB}$ at day 30, remaining well inside the 250 MB cgroup ceiling.
- **Unbounded / 90-Day Risk Disclosure:** In an unpruned in-memory configuration over 90 days ($25,920\text{ bars}$), memory would grow to $\sim 256.3\text{ MB}$, creating an OOM risk. The runtime must therefore flush and prune in-memory records older than 1,000 bars to disk checkpoints.
- **CPU & CFS Quota Safety:** Average execution latency of 0.183 ms and peak latency of 1.175 ms mean the container sleeps $99.999\%$ of the time. The 0.20 CPU quota (20 ms execution per 100 ms period) will never experience CFS throttling.

---

## 2. Process Memory Breakdown & Lifecycle Stages

### 2.1 Native Process RSS Across Lifecycle
```
[1] Python Interpreter Base:            26.18 MB
       |
       | + NumPy, Pandas, Engine Imports (+80.81 MB)
       v
[2] Modules Loaded & Linked:           106.99 MB
       |
       | + Instantiate Policies A through E (+0.00 MB)
       v
[3] Engines Ready:                     106.99 MB
       |
       | + 1,000 5m Bars (5,000 Chained Decisions) (+5.76 MB)
       v
[4] After 1,000 Bars In-Memory:        112.75 MB
       |
       | + Cryptographic Checkpointing & Peak Transient
       v
[5] Peak Resident Working Set:         115.75 MB
```

### 2.2 Milestone Memory Tracking
Tracking RSS at regular intervals during continuous execution confirms smooth, predictable linear growth:
- **Bar 100:** 107.61 MB
- **Bar 250:** 108.54 MB
- **Bar 500:** 110.16 MB
- **Bar 750:** 111.50 MB
- **Bar 1,000:** 112.75 MB

The sustained memory growth rate is exactly:
$$\text{Growth Rate} = \frac{112.75 - 106.99}{1,000} = 0.00576\text{ MB/bar} = 5.76\text{ KB/candle}$$
Across 5 concurrent policy hash chains, each chained decision record incurs approximately $1.15\text{ KB}$ of resident RAM.

---

## 3. Latency Distribution & CPU Contention

Execution timings were recorded with high-resolution monotonic clocks (`time.perf_counter()`):

| Latency Percentile | Measured Latency | Meaning for 5-Minute Cycle |
|---|:---:|---|
| **Average** | **0.183 ms** | $0.00006\%$ of the 300-second candle interval |
| **p50 (Median)** | **0.160 ms** | Half of all evaluations finish in $\le 160\ \mu\text{s}$ |
| **p90** | **0.235 ms** | 90% of evaluations finish in $\le 235\ \mu\text{s}$ |
| **p99** | **0.599 ms** | 99% of evaluations finish in $\le 599\ \mu\text{s}$ |
| **Peak Single-Bar** | **1.175 ms** | Maximum recorded burst across 5 policies |

### CFS Quota Compliance
The proposed Docker quota `cpus: '0.20'` configures the Linux CFS scheduler with:
- `cpu.cfs_period_us = 100000` ($100\text{ ms}$)
- `cpu.cfs_quota_us = 20000` ($20\text{ ms}$)

Because the absolute peak evaluation burst is **1.175 ms**, it consumes only **5.8% of the available 20 ms allocation** within a single 100 ms period. Under no circumstances will the shadow observer experience kernel CPU throttling or introduce CPU contention to host processes.

---

## 4. Container Resource Comparison & Recommendations

| Parameter | Proposed Limit | Observed Requirement | Evaluation & Recommendation |
|---|:---:|:---:|---|
| **Memory Limit** | `250M` | Peak RSS: 115.75 MB | **SAFE for 30-day protocol (8,640 bars)**.<br>For >30 days, implement ring buffer pruning of in-memory lists older than 1,000 bars. |
| **Memory Reservation** | `150M` | Steady-state: ~110 MB | Recommended soft reservation to prevent host pressure. |
| **CPU Quota** | `0.20` | Peak burst: 1.175 ms | **SAFE**. Completely prevents CPU contention. |
| **PIDs Limit** | `32` | 1 thread / 1 process | **SAFE**. Protects host against fork-bombs. |

---

## 5. Recovery Latency Under Interruption
Simulating a sudden termination at bar 500:
- Reloading 2,500 historical decision records from serialized state, re-verifying full SHA-256 chain integrity across all 5 policies from genesis, and resuming bar 501 took **139.79 ms**.
- State recovery completes in less than 0.15 seconds, well within the 300-second window between market candles.
