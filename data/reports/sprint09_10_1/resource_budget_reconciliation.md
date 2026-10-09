# RESOURCE BUDGET RECONCILIATION & TARGET ANALYSIS

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. REVIEW OF PROVISIONAL BUDGETS

In Sprint 09.9 and Sprint 09.10, four provisional resource budgets were set in `ShadowCollectorConfig`:

| Budget Parameter | Value | Nature of Budget | Enforced in Code? | Empirical Status |
| :--- | :---: | :--- | :---: | :--- |
| **`max_latency_ms`** | 150.0 ms | Engineering performance target | Monitored in telemetry | **FAIL (1,818 ms unoptimized)**<br>**PASS (17.9 ms optimized)** |
| **`max_rss_mb`** | 150.0 MB | Arbitrary engineering target | Monitored in telemetry | **FAIL (168.8 MB runtime baseline)** |
| **`max_network_requests_per_minute`** | 2 | Operational rate limit | **Enforced by rate-limiter** | **PASS (0 in offline mode)** |
| **`max_event_log_mb`** | 250.0 MB | Operational storage ceiling | Documented boundary | **PASS (82.6 MB at 30 days)** |

---

## 2. DETAILED ANALYSIS PER BUDGET

### A. Step Latency Budget (`max_latency_ms = 150.0`)
- **Scientific Requirement:** None. Financial time series inference does not change its mathematical result whether computed in 10 ms or 1,000 ms, provided it completes before the next 5-minute bar (300,000 ms).
- **Operational Requirement:** Must complete well within the 300,000 ms 5-minute candle interval to prevent CPU starvation and backpressure on the host system.
- **Original Measurement:** Unoptimized implementation reached 1,818 ms max, violating the declared 150 ms target.
- **Optimized Measurement:** Decoupling $O(N)$ full-history log re-reading and full-chain re-auditing reduced steady-state step latency to ~17.9 ms mean and ~40.3 ms P95, safely restoring compliance under the 150 ms budget.

### B. Memory Budget (`max_rss_mb = 150.0`)
- **Nature:** An arbitrary engineering target based on small VPS sizing.
- **Empirical Measurement:**
  - Python 3.11 64-bit interpreter with numpy, pandas, and C runtimes loaded on Windows maps ~154–168 MB into the working set before any collector processing occurs.
  - The actual data footprint of `shadow_v080` (350 candles buffer + model weights) is ~38 KB.
  - Total process RSS peaked at **168.84 MB**, exceeding the arbitrary 150.0 MB ceiling by 18.84 MB.
- **Reconciliation:** The 150 MB target was improperly formulated without accounting for the baseline memory footprint of the standard 64-bit Python/pandas runtime. On Linux VPS environments, RSS typically hovers around 90–120 MB for this stack, but on 64-bit Windows, DLL loading pushes working set to ~165 MB.
- **Recommendation:** Revise the operational host memory budget to **250.0 MB RSS**, which provides comfortable headroom for 64-bit Python runtimes across both Windows and Linux without masking memory leaks.

### C. Network Request Budget (`max_network_requests_per_minute = 2`)
- **Nature:** Hard operational rate limit to protect public exchange API quotas and prevent IP bans.
- **Enforcement:** Hard-coded in `ReadOnlyLiveBinanceSource` with a 30-second inter-request delay (`min_interval = 60.0 / 2`).
- **Empirical Status:** 100% compliant. In offline simulation mode, zero network requests were made.

### D. Event Log Storage Budget (`max_event_log_mb = 250.0`)
- **Nature:** Host disk storage budget for a 30-day continuous shadow run.
- **Empirical Status:**
  - At 288 cycles/day × 6 events/cycle = 1,728 events/day.
  - At 30 days: 51,840 prediction events (~44.4 MB) + 50,112 outcome events (~38.2 MB) = **82.6 MB total**.
  - 82.6 MB is well within the 250.0 MB budget (33% utilization).
  - At 90 days: total log size reaches ~250.5 MB, indicating log rotation or compression is advisable for runs exceeding 90 days.
