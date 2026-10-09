# PROSPECTIVE SCIENTIFIC EXPERIMENT PROTOCOL (CBE-0.8.0)

**EXPERIMENT ID:** `EXP-CBE-0.8.0-SHADOW-2026-V1`  
**PROTOCOL VERSION:** `CBE-PROTOCOL-0.8.0-V1`  
**DURATION:** 4 Consecutive Calendar Weeks (28 Days = 8,064 Five-Minute Cycles)  

---

## 1. SCIENTIFIC ELIGIBILITY & WARM-UP RULES

1. **Window Requirement:** Requires **288 contiguous closed 5-minute candles** (24 hours).
2. **Pre-288 Bars (Bars 72–287):** Computable for feature validation only. All generated predictions are strictly tagged `record_label="WARMUP_REPLAY"` and disqualified from prospective performance scoring.
3. **Bar 288 Onward:** Tagged `record_label="PROSPECTIVE_SHADOW"`, eligible for prospective scoring if and only if:
   - State machine is in `CaptureState.ELIGIBLE`.
   - `clock_trusted == True` (skew $\le 2000$ ms, receipt $\ge$ close).
   - `is_stale == False` (receipt $\le$ close + 10m).
   - No feature fallback applied.

---

## 2. CANDIDATE INTEGRITY & DUAL-BRANCH PAIRING

- **Candidate C (Global Calibration):** Ridge point forecast + symmetric empirical residual intervals.
- **Candidate E (State-Conditioned Calibration):** Identical Ridge point forecast + asymmetric causal market-state conditioned intervals.
- **Pairing Guarantee:** Both candidates evaluate on the exact same closed bar, same feature vector, and same forecast origin.

---

## 3. IMMUTABLE RECORDING & CONSERVATION

- **Cryptographic Hash Chain:** Every prediction is appended to a SHA-256 tamper-evident hash chain.
- **Commitment Precedence:** Durable commit timestamp strictly precedes outcome maturity ($t_{commit} < t_{mat}$).
- **Conservation Identity:**
  $$N_{predictions} = N_{matured\_valid} + N_{pending} + N_{disqualified}$$
