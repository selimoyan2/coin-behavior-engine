# RESOURCE CAPACITY PLANNING: WINDOWS WORKING SET VS LINUX RSS

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. EMPIRICAL MEMORY ACCOUNTING DIFFERENCES

| Component | Windows 64-bit Workstation (PSAPI) | Linux 64-bit Host (`/proc/self/status`) |
|:---|:---:|:---:|
| **Bare Interpreter Heap** | ~12.8–22.0 MB | ~11.5–18.0 MB |
| **Scientific Runtime (`numpy`/`pandas`)** | ~154.5 MB Working Set | ~90–105 MB `VmRSS` |
| **Shadow Buffer (350 bars)** | ~38 KB | ~38 KB |
| **Unmatured Queue (Bounded $\le 1728$)** | ~1.4 MB | ~1.4 MB |
| **Total Steady State RSS** | **~168.8 MB** | **~105–125 MB** (Estimated) |

- **Why Windows Working Set is Larger:** Windows PSAPI `WorkingSetSize` includes all mapped system DLLs, shared runtimes, and memory-mapped files currently paged into physical RAM. On Linux, `VmRSS` separates private anonymous memory from shared libraries.

---

## 2. SIZING & UPGRADE CRITERIA

1. **Target RSS Budget:** 250.0 MB (Provides > 120 MB headroom on Linux).
2. **Hard Safety Limit:** 400.0 MB.
3. **RAM Upgrade Threshold:** A VPS RAM upgrade is **NOT** recommended for CBE-0.8.0. An upgrade is only warranted if host available physical memory under baseline load drops below 400 MB.
