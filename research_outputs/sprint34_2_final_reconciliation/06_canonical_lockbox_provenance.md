# 06. Canonical Lockbox Provenance & Cryptographic Verification — Sprint 34.2

**Sprint ID:** `CBE_SPRINT34_2_FINAL_RECONCILIATION_REGRESSION_CLOSURE_HISTORICAL_DATA_READINESS`  
**Execution Timestamp:** 2026-11-15T23:24:30+03:00  
**Model Version:** `CBE-0.7.0`  
**Status:** `STRICTLY_FROZEN`  
**Attribution Tier:** `CANONICAL_MODEL_CORE`  

---

## 1. Executive Summary of Lockbox Provenance

In Sprint 34 and Sprint 34.1, the canonical market state classification engine was decoupled from prospective runtime fitting side-effects. Previously, the `CanonicalModelResearchBridge` constructor fitted thresholds on the first 2,000 bars of the input dataset upon instantiation, introducing side effects and subtle lookahead risks.

To achieve 100% mathematical determinism, prefix invariance, and strict zero-side-effect execution, the pre-calibrated discovery state was extracted and sealed into a standalone frozen lockbox artifact:
`data/models/cbe_070_canonical_frozen_lockbox.pkl`.

This artifact represents the exact point-in-time calibration obtained during the initial discovery window (`2023-10-01T00:00:00Z` to `2023-12-23T07:00:00Z`, bars 0 through 2,000) under canonical model version `CBE-0.7.0`.

---

## 2. Cryptographic Fingerprint and File Attributes

| Property | Value / Specification |
|---|---|
| **Binary Lockbox Path** | `data/models/cbe_070_canonical_frozen_lockbox.pkl` |
| **Manifest Path** | `data/models/cbe_070_canonical_frozen_lockbox_manifest.json` |
| **SHA-256 Digest** | `3e089ffe584fac31c0bb6aa284a83ad6fdd0b0cffdf3b7645eec1a731d83fabd` |
| **Canonical Model Version** | `CBE-0.7.0` |
| **Freeze Policy** | `STRICTLY_FROZEN` — No runtime refitting, no weight alteration |
| **Discovery Training Window** | `2023-10-01T00:00:00Z` to `2023-12-23T07:00:00Z` |
| **Total Calibration Bars** | 2,000 hourly bars |
| **Serialization Standard** | Python `pickle` protocol 4, immutable state container |

### Frozen Calibration Thresholds
```json
{
  "vol_p25": 0.254757,
  "vol_p75": 0.454040,
  "comp_p25": 0.623250,
  "comp_p75": 1.203961,
  "oi_drop_p05": -0.050000,
  "basis_p05": -0.020000,
  "tail_thresholds_95": {
    "1h": 0.005,
    "4h": 0.01,
    "24h": 0.02
  },
  "jump_thresholds": {
    "1h": 0.01,
    "4h": 0.02,
    "24h": 0.04
  }
}
```

---

## 3. Provenance Equivalence Proof

To verify that the sealed lockbox artifact is mathematically identical to the frozen `UnifiedMarketStateEngine` canonical calibration, the following equivalence conditions were tested:

1. **Parameter Equivalence:**
   - Loading `cbe_070_canonical_frozen_lockbox.pkl` directly populates `engine.fitted_thresholds`, `engine.tail_thresholds_95`, and `engine.jump_thresholds`.
   - All scalar percentile values match `FROZEN_DISCOVERY_THRESHOLDS` down to floating-point epsilon ($< 10^{-12}$).
2. **Classification Equivalence:**
   - Classifying the 2023–2024 Discovery series and 2025 Sealed series using the lockbox yields exact bit-level agreement with the historical canonical classification.
   - Zero bars deviate in regime assignment (`NORMAL`, `QUIET`, `HIGH_VOLATILITY`, `COMPRESSION`, `EXPANSION_WATCH`, `TAIL_RISK_ELEVATED`, `DELEVERAGING_STRESS`).
3. **Prefix Invariance:**
   - Evaluating any slice $k \in \{24, 48, 72, \dots, N\}$ yields identical regime classifications for all bars $0 \dots k$, proving zero forward leakage.

---

## 4. Governance and Deployment Isolation

- The lockbox is strictly a read-only research artifact.
- It is classified as an approved canonical model artifact in `audit_artifact_inventory` and does not represent an unverified prospective deployable model.
- Live trading remains `PERMANENTLY_PROHIBITED` (HTTP 403).
