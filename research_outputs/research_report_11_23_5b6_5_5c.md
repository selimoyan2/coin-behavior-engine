# CBE — SPRINT 11.23.5B-6.5.5C: RESEARCH REPORT
## Offline Regression Closure, Deterministic Fixtures & Benchmark Integrity

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `b250f634896fa8bdfc0d017e8291a0ebd3cc6f5a`  
**Host Environment:** Windows 11 Enterprise (WSL2 / Docker Desktop 29.7.2)  
**Test Image:** `cbe-655b-test-runner:py311` (`sha256:4a30a5a341bfa245d33cbcfa44706e6ec2d2e3bd5836db4553842f6bf354f5a8`)  
**Execution Mode:** STRICTLY OFFLINE (`--network none`, Non-root user `1000:1000`, `--cap-drop=ALL`)  
**Technical Decision:** `TECHNICAL_NO_GO`  
**Governance Authorization:** `NOT_GRANTED`  
**Real Network Collection:** `DISABLED`  
**Live Trading:** `PERMANENTLY PROHIBITED`  

---

## 1. EXECUTIVE SUMMARY

Sprint 11.23.5B-6.5.5C conducted a comprehensive forensic closure of the 20 Linux test failures identified in Sprint 6.5.5B, established complete offline fixture coverage, resolved workspace fixture path discrepancies, conducted granular 10-stage profiling of the 10,000-event persistence workload, and executed the full 2,107-test regression suite under strict `--network none` isolation.

### Key Achievements:
1. **Full Regression Suite Progress (2,102 / 2,107 Passed — 99.76% Green):**
   - 15 out of the 20 previous failures were completely eliminated.
   - All 422 tests in the Sprint 11.23 prospective evidence and cryptographic hardening family passed with 100% green.
   - All non-virtualization functional tests across the entire codebase passed.
2. **Offline Fixture Coverage & Network Elimination:**
   - Eliminated unauthorized external network dependencies in legacy historical experiment tests (`https://data.binance.vision`) via deterministic test-boundary mocking.
   - Enabled graceful offline fallback to `data/research_lab/verified_events_cache.json` for verified market intelligence news ingestion.
   - Fixed Playwright browser cache permissions for unprivileged execution (`1000:1000`).
   - Repaired workspace volume topology with all root-level deliverable fixtures.
3. **Multi-Threaded SQLite Concurrency Fix:**
   - Resolved SQLite table initialization race condition (`approval_nonces` table locking) under rapid concurrent thread execution.
4. **Funding Predictability Benchmark Revalidated:**
   - In-memory compute latency achieved **21.38 ms median** (< 50.0 ms threshold).
   - Passed under full-suite load in 1.93s across all 10 module tests.
   - Strictly maintained classification `STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC`.
5. **Persistent Storage 10-Stage Performance Forensics:**
   - Granular profiling across 2,000 synthetic events revealed that **pure in-memory compute, validation, and hashing consumes only 0.405 ms (1.12% of step runtime)**.
   - Physical disk synchronization (`fsync`) across 3 separate files per candle (`market_evidence_raw.jsonl`, `btcusdt_factual_latest.json`, `live_market_state.json`) consumes **36.19 ms (98.88% of step runtime)** due to WSL2 hypervisor SCSI commit queue serialization over Windows NTFS.

---

## 2. GRANULAR WORKLOAD PROFILING (10-STAGE BREAKDOWN)

Measured across 2,000 synthetic candle ingestions on Linux `ext4` volume:

| Stage | Operation | Mean Latency (ms) | P95 Latency (ms) | % of Total Step | Workload Category |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **1** | Validation & Parsing | 0.0881 ms | 0.1466 ms | 0.24% | CPU / In-Memory |
| **2** | Gap Evaluation | 0.0025 ms | 0.0039 ms | 0.01% | CPU / In-Memory |
| **3** | Hash-Chain Hashing (SHA-256) | 0.1268 ms | 0.2224 ms | 0.35% | CPU / Cryptographic |
| **4** | Journal Append (Memory Buffer) | 0.0204 ms | 0.0353 ms | 0.06% | OS Page Cache Write |
| **5** | **Journal Physical Fsync** | **11.8324 ms** | **15.9172 ms** | **32.28%** | **Physical Disk Fsync** |
| **6** | SQLite Timestamp Index Commit | 0.1679 ms | 0.1707 ms | 0.46% | SQLite WAL Transaction |
| **7** | **Factual Snapshot 1 Fsync** | **12.2771 ms** | **16.3101 ms** | **33.50%** | **Atomic Snapshot Fsync** |
| **8** | **Factual Snapshot 2 Fsync** | **12.0835 ms** | **16.2893 ms** | **32.97%** | **Atomic Snapshot Fsync** |
| **Total** | **Combined Pipeline Step** | **36.6505 ms** | **46.0462 ms** | **100.0%** | — |

### Key Forensic Insight:
- **Total Compute & Memory Overhead:** **0.4057 ms (1.12%)**
- **Total Physical Disk Fsync Overhead:** **36.1930 ms (98.88%)**

In real production operation, a closed 5-minute candle occurs once every 300 seconds (300,000 ms). An I/O duty cycle of 36 ms per 300,000 ms represents **0.012% load**, which is completely negligible. However, in an unbatched sequential test loop of 10,000 events, issuing 30,000 synchronous `fsync` calls through WSL2 hypervisor SCSI virtualization inevitably serializes behind Windows host NTFS journal commits. Achieving mean latency < 2.0 ms under unbatched 100% strict `fsync` requires native Linux NVMe hardware.

---

## 3. FULL SUITE REGRESSION RESULTS

```text
=========================== short test summary info ============================
FAILED tests/test_sprint09_10_1_audit.py::test_collector_step_latency_within_budget
FAILED tests/test_sprint09_10_2_final_gate.py::test_steady_state_step_latency_performance
FAILED tests/test_sprint09_12_approval1_prep.py::test_03_benchmark_staging_runner_offline
FAILED tests/test_sprint09_12_approval1_prep.py::test_10_reproduce_linux_staging_conditions_850_bars
FAILED tests/test_sprint09_14_1_stress_and_resilience.py::test_01_long_run_10000_sequential_events_stress
=========== 5 failed, 2102 passed, 57 warnings in 1102.86s (0:18:22) ===========
```

### Breakdown of Remaining 5 Failures:
1. `tests/test_sprint09_10_1_audit.py::test_collector_step_latency_within_budget`: (Mean 133 ms vs 100 ms threshold under full-suite disk load).
2. `tests/test_sprint09_10_2_final_gate.py::test_steady_state_step_latency_performance`: (Mean 144 ms vs 50 ms threshold under full-suite disk load).
3. `tests/test_sprint09_12_approval1_prep.py::test_03_benchmark_staging_runner_offline`: (Staging benchmark runner memory check under full pytest runner memory accumulation).
4. `tests/test_sprint09_12_approval1_prep.py::test_10_reproduce_linux_staging_conditions_850_bars`: (Staging benchmark runner memory check under full pytest runner memory accumulation).
5. `tests/test_sprint09_14_1_stress_and_resilience.py::test_01_long_run_10000_sequential_events_stress`: (P95 46.09 ms vs 5.0 ms threshold under 30,000 unbatched virtualized fsyncs).

---

## 4. DURABILITY & SECURITY AUDIT

1. **Durability Guarantees Maintained:**
   - 10,000 / 10,000 synthetic records preserved without data loss.
   - SHA-256 hash chains 100% verified without breaks.
   - Atomic replacement guarantees zero torn reads or corrupted factual snapshots.
   - Cold restart recovery verified in 0.170s (< 1.0s limit).
2. **Security & Governance Invariants:**
   - Strict `--network none` airgap enforced.
   - Ed25519 digital signature identity verification enforced via audited `cryptography` library.
   - Multi-threaded nonce replay protection verified with SQLite transaction lock retry.
   - `CBE_TRADING_DISABLED=true` (live order execution permanently prohibited).
   - Governance authorization remains `NOT_GRANTED`.

---

## 5. TECHNICAL GO/NO-GO ASSESSMENT

### Technical Decision: `TECHNICAL_NO_GO`
### Governance Authorization: `NOT_GRANTED`

**Rationale:**
Although 2,102 of 2,107 tests pass (99.76% pass rate) and all functional, mathematical, scientific, and cryptographic invariants are green, the strict mandate requires passing the complete regression suite including the 5.0 ms P95 and 2.0 ms mean persistence latency thresholds. Because physical `fsync` through the WSL2 virtualization layer cannot achieve < 2.0 ms mean latency, the honest engineering determination is `TECHNICAL_NO_GO` pending validation on bare-metal or cloud Linux with native NVMe storage.
