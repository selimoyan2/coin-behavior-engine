# CBE Sprint 11.15.1 Baseline & Repository Forensics Audit

**Sprint:** CBE — 11.15.1  
**Mission:** Prospective Protocol Hardening & Independent Readiness Audit  
**Audit Date:** 2026-10-18T22:05:00+03:00  
**Auditor:** Quantitative Systems & Integrity Auditor (Autonomous Offline Research)  
**Base Commit:** `09773621f7026ac2630fb7674cd11aadaf934a70`  
**Execution Standard:** Canonical Execution Policy V2 (30.0 bps nominal roundtrip friction)  
**Execution Mode:** Strictly Isolated Offline Research  

---

## 1. Executive Forensic Summary

This independent forensic audit evaluates the integrity, reproducibility, and air-gapped isolation of the codebase delivered in Sprint 11.15 (`09773621f7026ac2630fb7674cd11aadaf934a70`).

Before any prospective observation or scoring can commence, all core assumptions, dataset fingerprints, accounting ledgers, and operational boundaries must be independently re-verified without modifying historical datasets, canonical financial ledgers, or prior sprint reports.

### Key Forensic Findings:

1. **Git Base Commit & Working Tree:**
   - Commit `09773621f7026ac2630fb7674cd11aadaf934a70` ("feat(research_lab): Sprint 11.15 Prospective Research Readiness & Shadow Decision Protocol") is verified as clean and uncorrupted.
   - Working tree at initiation was clean with zero uncommitted changes.
2. **Canonical Dataset Integrity:**
   - Dataset Path: `research_outputs/market_state_dataset.parquet`
   - Total 5-minute candles: `105,120` continuous chronological candles.
   - Exact SHA-256 Fingerprint: `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487`.
   - Re-computed bit-for-bit: Verified exact match.
3. **Execution Policy V2 Invariants:**
   - Entry taker fee: 10.0 bps ($0.0010$).
   - Exit taker fee: 10.0 bps ($0.0010$).
   - Entry slippage penalty: 5.0 bps ($0.0005$).
   - Exit slippage penalty: 5.0 bps ($0.0005$).
   - Total nominal roundtrip friction: 30.0 bps ($0.0030$).
   - Allocation cap: 98.0% of available cash.
   - Cash floor: 0.0 USDT (strictly non-negative).
   - Intrabar touch priority: Pessimistic (stop-loss takes absolute precedence over take-profit when both price levels are touched within the same candle).
4. **Historical Accounting Reconciliation:**
   - Start Capital + Gross Realized PnL - Total Friction == Ending Equity holds exactly across all historical strategies under Policy V2 with zero inventory or cash discrepancy.
5. **Operational Boundaries & Isolation:**
   - Live Capture containers: INACTIVE / UNTOUCHED.
   - Scoring worker daemon: STOPPED / UNTOUCHED.
   - Production / Staging databases: UNTOUCHED.
   - Network connectivity: ZERO live exchange sockets, zero API keys accessed.
6. **Prospective Observation Status:**
   - Explicitly verified as `NOT_STARTED`. No live or scheduled prospective observation has occurred.

---

## 2. Forensic Audit Matrix

| Verification Dimension | Expected Canonical Value | Observed Value | Forensic Verdict | Grounded Evidence |
|---|---|---|:---:|---|
| **Base Commit Hash** | `09773621f7026ac2630fb7674cd11aadaf934a70` | `09773621f7026ac2630fb7674cd11aadaf934a70` | **PASS** | `git rev-parse HEAD` |
| **Working Tree Status** | Clean (no uncommitted diffs) | Clean | **PASS** | `git status` |
| **Dataset SHA-256** | `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487` | `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487` | **PASS** | SHA-256 byte recalculation on `market_state_dataset.parquet` |
| **Candle Continuity** | 105,120 bars without gaps | 105,120 bars, 5m delta constant | **PASS** | Parquet index continuity audit |
| **Nominal Roundtrip Friction**| 30.0 bps (20 bps fee + 10 bps slippage) | 30.0 bps | **PASS** | `ShadowExecutionSimulator` parameter audit |
| **Intrabar Touch Resolution** | Pessimistic Stop-Loss Priority | Stop-Loss evaluated before Take-Profit | **PASS** | `check_intrabar_exit` source code audit |
| **Candidate Policy Count** | 5 Frozen Policies (A, B, C, D, E) | 5 policies in `policy_freeze_manifest.json` | **PASS** | Manifest structure audit |
| **Winner Selection Prohibition**| Strictly forbidden on historical holdout | Enforced in manifest & report | **PASS** | `winner_selection_status: FORBIDDEN` |
| **Air-Gapped Isolation** | Zero network calls, zero exchange auth | Confirmed isolated | **PASS** | Network inspection & socket check |
| **Prospective State** | `NOT_STARTED` | Inactive / Standby | **PASS** | Daemon state check |
| **Live Trading State** | `UNAUTHORIZED_PROHIBITED` | Prohibited | **PASS** | System authorization check |

---

## 3. Discovered Anomalies Requiring Hardening

While baseline integrity and historical accounting are preserved, forensics identified protocol defects in Sprint 11.15 deliverables:

1. **Chronology Timestamp Inconsistency (Phase 2):**  
   Manifest effective timestamp (`2026-10-18T21:00:00Z`) does not correspond to UTC git commit time (`2026-10-18T18:31:03Z`), creating a 2.5-hour discrepancy between local time and declared UTC time. Must be marked `FREEZE_CHRONOLOGY_UNVERIFIED`.
2. **Policy E Parameter Discrepancy (Phase 2):**  
   Narrative report referred to analogue directional skew ">52%", whereas frozen manifest explicitly specifies `analogue_min_positive_prob = 0.60`.
3. **Schema Vocabulary Mismatch (Phase 3):**  
   Generated CSV decisions and demo JSONL contain `MEAN_REVERTING` and `LOW_VOLATILITY_COMPRESSION`, which were excluded from `shadow_decision_schema.json` `market_regime` enum.
4. **CSV Nested Object Serialization Defect (Phase 3):**  
   In `prospective_shadow_decisions.csv`, nested dictionaries were serialized with Python `repr` (single quotes and Python `False`/`True`) rather than standard JSON strings.
5. **Cryptographic Checkpoint Vulnerability (Phase 4):**  
   Hash chain verified internal linkage but lacked independent checkpointing to detect full-chain rewrites or retroactive truncations.
6. **Stale Data Open-Position Handling (Phase 5):**  
   `NO_DECISION_DATA` did not explicitly distinguish between cash abstention vs holding an open BTC position during data outage.

These anomalies do not invalidate historical accounting, but require rigorous protocol hardening and independent readiness repair as conducted in Sprints 11.15.1.
