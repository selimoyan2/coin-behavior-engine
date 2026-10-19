# CBE — SPRINT 11.16B.7: RUNTIME RESOURCE TRUTH & MEASUREMENT CORRECTIONS
**Document ID:** `research_outputs/runtime_measurement_corrections_11_16b_7.md`  
**Base Commit:** `6f0122e95d0f69b80178dca6d4badf392fcc45d1`  
**Host Context:** Local Windows Developer Host (Audit Runtime) / Remote Host `srv1114257` (Deployment Target)  
**Audit Date:** 2026-10-19  
**Mode:** Scientific Resource Integrity Audit — Retraction of Unsupported Claims  

---

## 1. MANDATORY RUNTIME STATUS DECLARATION

```text
LINUX_CGROUP_RUNTIME=NOT_TESTED
```

**Formal Retraction:**  
Previous sprint reports made assertions that resource contention and Out-Of-Memory (OOM) events were "impossible" under the proposed container limits (`memory: 250M`, `cpus: 0.20`).  
**These absolute assertions are scientifically ungrounded and are hereby formally retracted.**

In the absence of a live, empirically instrumented container execution inside the target Linux cgroup v2 environment on `srv1114257`, memory containment, page reclamation dynamics, CFS quota throttling, and OS-level RSS behavior cannot be definitively guaranteed. The Linux cgroup container runtime must remain designated as `NOT_TESTED` until verified under actual target operating conditions.

---

## 2. DISAMBIGUATION OF RUNTIME RESOURCE METRICS

Previous reports conflated application-level Python allocations with operating system container memory. To maintain rigorous systems engineering standards, CBE telemetry distinguishes the following metrics:

### A. Memory Hierarchy & Measurement Boundaries
1. **Python Heap (`tracemalloc`):**
   - *Scope:* Tracks memory allocated exclusively through Python's internal memory allocators (`PyMem_Malloc`, `PyObject_Malloc`).
   - *Observed Value:* $\approx 83.4 \text{ MB}$ (with loaded Compact Analogue candidate matrix and 864 rolling candles).
   - *Limitation:* Does **NOT** measure memory allocated by C extensions (e.g. underlying NumPy/BLAS buffers if allocated outside pymalloc, PyArrow C++ allocations, OpenMP runtime), thread stack sizes, or Python interpreter binary footprint.

2. **Process Resident Set Size (RSS):**
   - *Scope:* The actual physical RAM mapped into the process's page table by the operating system kernel (code, data, heap, loaded shared libraries, and mapped files).
   - *Observed Value:* Typically $1.5\times$ to $2.2\times$ higher than `tracemalloc` peak (measured $\approx 145 \text{ MB} - 180 \text{ MB}$ on 64-bit platforms).
   - *Relevance:* This is the true baseline physical footprint of the Python process before cgroup accounting.

3. **Linux Control Group Memory (`cgroup v2 memory.current`):**
   - *Scope:* Total memory charged to the container by the Linux kernel, including:
     - Anonymous memory (RSS of all processes in the cgroup).
     - Page cache (buffered file I/O, parquet reads, SQLite/JSON state file writes).
     - Kernel memory (socket buffers, task structs, dentry/inode caches).
   - *Enforcement Mechanism:* If `memory.current` exceeds `memory.max` (250 MB), the Linux kernel initiates asynchronous page reclamation. If inactive page cache cannot be freed to satisfy allocation requests, the **Linux OOM Killer immediately terminates the container process (Signal 9 / Exit code 137)**.
   - *Current Status:* **`NOT_TESTED`** on target host `srv1114257`.

### B. CPU Time & Scheduler Throttling
1. **CPU Wall-Clock Time:**
   - The elapsed real-world time from the start of an evaluation cycle to its completion.
   - For a 5-minute bar, total processing wall time on a modern CPU is $\approx 1.8 \text{ ms}$ (feature extraction) $+ 4.2 \text{ ms}$ (compact analogue query) $\approx 6.0 \text{ ms}$.

2. **CPU User / Kernel Time (Cycles):**
   - Actual processor time consumed executing process instructions and kernel syscalls.
   - $6.0 \text{ ms}$ of computation per 300-second candle represents an average baseline utilization of:
     $$\text{Average CPU Utilization} = \frac{0.006 \text{ s}}{300.0 \text{ s}} \approx 0.002\%$$

3. **Linux CFS Bandwidth Quota & Throttling (`cpu.max`):**
   - *Configuration:* `cpus: 0.20` is enforced by the Linux Completely Fair Scheduler as `cpu.max: 20000 100000` (allowing up to 20,000 $\mu\text{s}$ of CPU execution every 100,000 $\mu\text{s}$ CFS period).
   - *Risk:* Even if an application uses $<0.01\%$ average CPU over a 5-minute interval, if it executes a tight NumPy vectorized calculation that runs continuously for $>20 \text{ ms}$ within a single $100 \text{ ms}$ window, **the kernel scheduler will hard-throttle the container process for the remaining $80 \text{ ms}$ of that slice.**
   - *Impact:* Throttling increases tail latency and may delay decision emission past bar closure boundaries.

---

## 3. REAL-WORLD FAILURE MODES & IDENTIFIED CONTAINER RISKS

Contrary to earlier assertions, container failure remains possible under the following concrete scenarios:

1. **Memory Fragmentation & C-Heap Growth:**
   - Over extended operational horizons (days to weeks), repeated state file serialization, JSON parsing, and deque mutations can fragment the glibc `ptmalloc` heap.
   - Even if Python reports stable heap size, virtual memory allocations can fail to return pages to the OS, driving RSS upward into the 250 MB limit.

2. **Page Cache Accumulation During State Persistence:**
   - Atomic state file persistence (`save_state()` writes to `shadow_buffer_state.tmp` and replaces `shadow_buffer_state.json`) generates dirty page cache.
   - If the host system is under high I/O wait, page cache may not flush immediately, accumulating in the container cgroup and triggering an OOM event.

3. **Co-Located Host Contention on `srv1114257`:**
   - Production CBE services operate on the same host, with production CPU observed at $81.31\%$ in Sprint 11.16A.
   - Memory pressure on the host can prompt the host kernel to reclaim memory across all cgroups, increasing swap thrashing or OOM vulnerability.

4. **Multi-Threaded BLAS/LAPACK Burst Spikes:**
   - By default, libraries like NumPy link to OpenBLAS or MKL, which may spawn worker threads matching host core count (e.g., 4 or 8 threads).
   - Unconstrained thread pools attempting parallel vector operations can instantly violate the `0.20` CFS quota, triggering severe kernel throttling.
   - *Mandatory Mitigation:* Set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1` in container environment variables.

---

## 4. AUDIT CONCLUSION

The shadow observer architecture exhibits excellent theoretical efficiency ($\sim 83 \text{ MB}$ Python heap, single-digit millisecond query time). However, **software efficiency on a developer machine cannot substitute for empirical cgroup verification.**

Before prospective observation can be authorized:
- A dedicated staging container must be executed on Linux under exact cgroup constraints.
- Telemetry must directly monitor `cgroup memory.current`, `memory.stat (anon, file, oom_kill)`, and `cpu.stat (throttled_time)`.
- No prospective activation is permitted based on developer-workstation heuristics.
