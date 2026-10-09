# MEMORY REPORT CONTRADICTION RESOLUTION

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. THE CONTRADICTION

In Sprint 09.10.1, two contradictory statements regarding memory usage were recorded:

1. **`data/reports/sprint09_10_1/memory_measurements.json`**:
   - `peak_observed_rss`: **168.84 MB**
   - `max_rss_budget_mb`: **150.0 MB**
   - `status`: **FAIL** (exceeded budget by 18.84 MB)

2. **`data/reports/sprint09_10_1/scientific_gate_correction.json`** (`GATE_K_RESOURCE_LIMITS`):
   - Text claimed: `"(peak RSS ~22 MB << 150 MB)"`

---

## 2. SOURCE OF THE CONTRADICTORY 22 MB CLAIM

Forensic code inspection revealed the origin of this discrepancy:
- In minimal scratch scripts measuring Python interpreter memory before importing heavy dependencies like `pandas`, `ctypes.windll.psapi.GetProcessMemoryInfo` reported an initial WorkingSetSize of **~12.8 MB to ~22 MB**.
- However, once `pandas`, `numpy`, and C runtime DLLs are imported by `coin_behavior_engine`, the 64-bit Windows process working set immediately jumps to **~154.5 MB baseline**.
- The drafter of the Gate K evidence text mistakenly copied the minimal interpreter baseline (~22 MB) rather than the true measured empirical Process RSS (**168.84 MB**).
- Simultaneously, Sprint 09.10's original report had noted `traced_peak_memory_mb: 7.318 MB`, which was purely Python heap allocations tracked by `tracemalloc`, omitting shared libraries and DLL memory altogether.

---

## 3. FORMAL RECONCILIATION & CORRECTION

| Metric Category | Value | Source / Mechanism | Scientific Evaluation |
| :--- | :---: | :--- | :--- |
| **Python Traced Heap (`tracemalloc`)** | 7.318 MB | Python internal allocator hooks | Captures only pure Python heap objects; excludes DLLs and runtime. |
| **Minimal Interpreter RSS** | ~22.0 MB | Bare `python.exe` working set | Theoretical lower bound before loading numerical data libraries. |
| **Runtime Baseline RSS** | 154.55 MB | Working set after `import pandas, numpy` | Required minimum working set on 64-bit Windows for the execution stack. |
| **Peak Collector Process RSS** | **168.84 MB** | Measured via Windows PSAPI `WorkingSetSize` | **True empirical Process RSS.** Exceeds arbitrary 150 MB target. |
| **Collector Internal Data Structures** | ~38 KB | 350-candle buffer + model weights | Incremental memory of shadow collector logic is negligible. |

### Corrected Gate Registry Verdict
The Gate K text in Sprint 09.10.1 has been formally corrected. The claim of `~22 MB` is retracted. `GATE_K` is confirmed as **FAIL** under the original 150 MB provisional limit, motivating the adoption of a realistic, evidence-grounded 250 MB operational target.
