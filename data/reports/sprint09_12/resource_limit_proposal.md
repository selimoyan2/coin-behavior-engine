# CONSERVATIVE RESOURCE LIMIT PROPOSAL & RATIONALE

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**OPERATOR TARGET RSS:** 250 MB  

---

## 1. PROPOSED BOUNDS VS HISTORICAL CLAIMS

| Resource Metric | Sprint 09.11 Initial Proposal | Operator Preference | Sprint 09.12 Conservative Proposal | Rationale |
|:---|:---:|:---:|:---:|:---|
| **Process Target RSS** | 250 MB | 250 MB | **250 MB** | Honors operator target without memory bloat |
| **Hard Memory Ceiling** | 400 MB | Not Approved | **300 MB** | Lowers ceiling by 100 MB; provides 50 MB buffer for container cgroup overhead |
| **Container Memory Reservation** | None | Bounded | **150 MB** | Minimum guaranteed physical RAM |
| **CPU Quota** | None specified | Bounded | **0.25 cores (25%)** | Caps usage to 12.5% of host 2 cores |
| **CPU Reservation** | None | Bounded | **0.05 cores (5%)** | Baseline scheduling floor |
| **Log Rotation** | Unbounded | Bounded | **30 MB total** | 3 files × 10 MB |

---

## 2. DISTINCTION OF MEMORY TIERS

1. **Process RSS (Estimated ~110–135 MB on Linux):** The actual resident memory allocated to Python bytecode, numpy arrays, and SQLite buffers.
2. **Container CGroup Memory (Limit 300 MB):** Includes process RSS plus page cache, container runtime shims, and memory-mapped files. A 300 MB limit ensures the container is killed safely if cgroup usage exceeds 300 MB without host OOM impact.
3. **Host Available Memory (~3.2 GiB):** The container uses less than 9.4% of currently available host RAM.
