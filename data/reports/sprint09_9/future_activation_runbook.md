# FUTURE ACTIVATION RUNBOOK: CBE-0.8.0 PROSPECTIVE SHADOW EXPERIMENT
*(DOCUMENTATION ONLY — EXECUTION STRICTLY PROHIBITED)*

**STATUS:** FROZEN CANDIDATE RUNBOOK  
**CANDIDATE VERSION:** CBE-0.8.0  
**BRANCHES:** Candidate C (Global) & Candidate E (Regime-Conditional)  
**PRODUCTION MODEL:** CBE-0.7.0 (STRICTLY FROZEN)  

---

## 1. PRE-ACTIVATION GATES (CHECKLIST)

Before initiating live prospective shadow capture, all gates below must be signed off:
- [ ] **Human Scientific Approval**: Explicit written approval from the scientific lead.
- [ ] **Repository Integrity**: Clean Git working tree; HEAD matches audited commit hash.
- [ ] **Model Lockbox Verification**: All 29 canonical artifacts verified (`test_freeze_v2.py` PASS).
- [ ] **Candidate Artifact Hashes**: SHA-256 matches frozen bundle, thresholds, and calibrations.
- [ ] **Time Synchronization**: Host system NTP clock skew verified `< 100 ms`.
- [ ] **Snapshot Storage**: Dedicated directory allocated for `candle_buffer_snapshot.json`.
- [ ] **Coolify Auto Deploy**: Confirmed DISABLED.

---

## 2. ACTIVATION PROCEDURE

1. **Launch Shadow Process in Isolated Mode**:
   - Start dedicated shadow capture process as a separate systemd service or background daemon:
     ```bash
     python -m coin_behavior_engine.candidate_v080.shadow_worker --mode=observation_only
     ```
   - Verify process writes strictly to `data/prospective_v080/` (completely isolated from `data/prospective/`).
2. **Buffer Initialization**:
   - Process initializes via local snapshot (Option C) or single historical klines fetch (Option B).
   - Verifies 288 contiguous closed candles.
   - Enters `FULL_WINDOW_READY` -> `ELIGIBLE`.
3. **Telemetry & Dual Branch Logging**:
   - For every closed 5-minute candle:
     - Generate feature vector.
     - Evaluate Ridge point forecast (shared by both branches).
     - Evaluate Market State Classifier.
     - Evaluate Candidate C prediction intervals (global).
     - Evaluate Candidate E prediction intervals (regime-conditional).
     - Persist tamper-evident record to `data/prospective_v080/predictions/`.

---

## 3. REAL-TIME MONITORING METRICS

- **Process Memory**: RSS must remain `< 100 MB`.
- **Latency**: Feature reconstruction + dual inference `< 50 ms`.
- **Feed Continuity**: Zero `SOURCE_GAP` transitions.
- **Clock Skew**: Transit latency `delta < 1,000 ms`.
- **Production Health**: Ensure CBE-0.7.0 production dashboard and worker continue undisturbed.

---

## 4. EMERGENCY ROLLBACK PROCEDURE

If any abnormality, memory leak, or rate-limit conflict occurs:
1. **Immediately Stop Shadow Worker**:
   ```bash
   systemctl stop cbe-shadow-v080
   ```
2. **Verify Production Status**:
   - Check `coin.ozelweb.com.tr` and verify CBE-0.7.0 continues logging normal predictions.
3. **Isolate Artifacts**:
   - Move `data/prospective_v080/` to an immutable post-mortem directory for forensics.
   - Do NOT delete or modify existing historical data.
