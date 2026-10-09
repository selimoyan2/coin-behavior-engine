# SPRINT 09.10 DISCREPANCY AUDIT & PERFORMANCE FORENSICS

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  
**AUDIT TARGET:** `data/reports/sprint09_10/resource_measurements.json` & Section 21 Completion Report  

---

## 1. THE DISCREPANCY

In Sprint 09.10, `resource_measurements.json` recorded:

```json
{
  "mean_step_latency_ms": 685.5779,
  "p95_step_latency_ms": 1571.3103,
  "max_step_latency_ms": 1818.1596,
  "traced_peak_memory_mb": 7.318,
  "provisional_budgets": {
    "max_latency_ms": 150.0,
    "max_rss_mb": 150.0,
    "max_event_log_mb": 250.0
  },
  "compliance": "PASS (> 50x Headroom under VPS operational budgets)"
}
```

The accompanying Gate Registry and Executive Report marked `GATE_K_RESOURCE_LIMITS` as **PASS**.

This verdict was contradictory:
- `max_step_latency_ms` = 1,818.16 ms vs declared budget limit of 150.0 ms (12.1x over budget).
- `mean_step_latency_ms` = 685.58 ms vs declared budget limit of 150.0 ms (4.6x over budget).
- `traced_peak_memory_mb` = 7.318 MB was reported, but this represented only Python heap memory tracked by `tracemalloc`, not actual OS process RSS.

---

## 2. DETAILED FORENSIC ANSWERS TO THE 12 AUDIT QUESTIONS

### Q1: What exactly constitutes one measured step?
One step executes `ShadowCollectorV080.step()`. It performs:
1. Ingesting next closed candle from source.
2. Clock-skew and timestamp integrity checks.
3. Adding candle to 350-bar rolling buffer with geometry and duplicate verification.
4. Computing 3 canonical features (`volatility_realized_24h`, `volatility_compression_ratio`, `volume_zscore_24h`).
5. Evaluating causal market-state classifier (`LOW_VOLATILITY`, `NORMAL_VOLATILITY`, `HIGH_VOLATILITY`).
6. Running Ridge inference across 1h, 4h, and 24h horizons.
7. Calculating prediction intervals for Candidate C and Candidate E.
8. Generating 6 `ShadowPredictionEvent` objects (3 horizons × 2 branches) with SHA-256 hash chaining.
9. Writing each event to `shadow_predictions.jsonl` with `flush()` and `os.fsync()`.
10. Reading prior events from disk to resolve matured forward outcomes against contiguous windows.
11. Writing atomic 350-candle snapshot to disk (`candle_buffer_snapshot.json`).
12. Calling `EventIntegrityAuditorV080.audit_prediction_chain()` to re-verify the entire JSONL file.
13. Updating health telemetry.

### Q2: Does the step include model loading?
**No.** All model artifacts, scaler parameters, classification thresholds, and calibration tables are loaded once during `ShadowCollectorV080.initialize()`.

### Q3: Does it include feature reconstruction?
**Yes.** `self.feature_pipeline.compute_features()` reconstructs features over the rolling window on every step (~0.35 ms).

### Q4: Does it include Candidate C and E inference?
**Yes.** Ridge inference and interval computations for both branches across all 3 horizons are executed on every step (~0.07 ms total).

### Q5: Does it include JSONL persistence?
**Yes.** 6 events per cycle are written to `shadow_predictions.jsonl` with explicit `flush()` and `os.fsync()` calls (~5.9 ms total).

### Q6: Does it include outcome maturity processing?
**Yes.** `resolve_matured_predictions` checks forward window maturity for 1h, 4h, and 24h horizons on every step.

### Q7: Does it include snapshot writing?
**Yes.** In Sprint 09.10, `persist_snapshot()` atomically wrote the entire 350-candle buffer to disk on every step (~11.2 ms).

### Q8: Does it include full event-log integrity verification?
**YES.** This was the primary architectural bottleneck: on every single step, `EventIntegrityAuditorV080.audit_prediction_chain()` opened `shadow_predictions.jsonl` and re-read, deserialized, and re-computed SHA-256 digests for *every single historical event from genesis to the end of the file*.

### Q9: Does it include fixture loading?
**No.** Fixtures were pre-loaded into in-memory lists before the benchmark loop began.

### Q10: Does it include one-time initialization?
**No.** `collector.initialize()` was executed prior to entering the step timing loop.

### Q11: Are expensive operations repeated unnecessarily?
**YES, profoundly:**
1. `prediction_store.list_events()` read and deserialized the entire cumulative JSONL file from disk on every step to find pending outcomes.
2. `EventIntegrityAuditorV080.audit_prediction_chain()` scanned and re-hashed the entire cumulative file from genesis on every step ($O(N)$ per step, leading to $O(N^2)$ cumulative time).
3. In the benchmark harness itself, `tracemalloc.start()` was left active during timing, intercepting every memory allocation and stack frame, magnifying Python JSON deserialization overhead 5x–10x.

### Q12: Is the 150 ms target a per-candle latency budget, CPU-time budget, or end-to-end cycle budget?
In `ShadowCollectorConfig`, `max_latency_ms: 150.0` was documented as the per-step cycle budget. The Sprint 09.10 compliance text mistakenly claimed `PASS` by comparing 1,818 ms against the 300,000 ms (5-minute) cadence window rather than enforcing the 150 ms step budget.

---

## 3. AUDIT CONCLUSION

The original PASS verdict for `GATE_K_RESOURCE_LIMITS` was unjustified and scientifically invalid. Based on raw evidence from Sprint 09.10, `GATE_K` must be marked **FAIL**.
