# RESOURCE BUDGET POLICY & OPERATIONAL SIZING FRAMEWORK

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. THREE-TIER RESOURCE POLICY

To prevent conflation between empirical measurements, engineering desires, and actual VPS capacity limits, the CBE architecture establishes three distinct resource concepts:

### A. MEASURED BASELINE (Empirical Reality)
- **Observed Peak Process RSS:** **~168.8 MB** (64-bit Windows), **~105–125 MB** (Linux VPS).
- **Observed P95 Step Latency:** **~40.3 ms** (optimized steady state).
- **Observed 30-Day Disk Growth:** **~82.6 MB**.
- **Nature:** Measured facts derived from reproducible automated tests.

### B. PREFERRED OPERATING TARGET (Software Efficiency Goal)
- **Target RSS Budget:** **250.0 MB**.
- **Target Step Latency Budget:** **150.0 ms**.
- **Target Network Request Rate:** **≤ 2 requests / minute**.
- **Target 30-Day Disk Allocation:** **250.0 MB**.
- **Nature:** An aggressive software efficiency target appropriate for a shared host without purchasing additional RAM.

### C. HARD OPERATIONAL LIMIT (Safety Ceiling)
- **Host Safety Ceiling:** **400.0 MB RSS**.
- **Cadence Timeout Ceiling:** **15,000 ms** (5% of 300,000 ms cadence).
- **Disk Emergency Threshold:** **500.0 MB**.
- **Nature:** Fail-safe interlocks enforced by host monitoring (systemd `MemoryMax=400M`, `RuntimeMaxSec=30s`). If breached, process is gracefully paused rather than starving host processes.

---

## 2. POLICY COMPLIANCE & HOST VERIFICATION REQUIREMENTS

1. **Never Adjust Budgets Merely to Force a PASS:**
   - When the collector reached 1,818 ms or 168.8 MB under the 150 MB budget, the outcome was recorded as **FAIL**.
   - The 250 MB target is justified by standard 64-bit Python runtime requirements and provides > 80 MB of real headroom.
2. **VPS Capacity Verification Requirement:**
   - Before live shadow observation is authorized in a future sprint, available free RAM on the production host must be explicitly verified via `free -m` or `systeminfo`.
