# Candidate Runtime Architecture (CBE-0.8.0 Specification)
**Sprint:** 09.1  
**Status:** SPECIFICATION ONLY (NOT IMPLEMENTED IN SPRINT 09.1)  

---

## 1. Immutable Model Bundle (`cbe_model_bundle_v080.json`)
A future CBE-0.8.0 candidate should package all weights into an immutable JSON or NPZ bundle:
```json
{
  "model_version": "CBE-0.8.0",
  "trained_at": "2026-10-XX",
  "historical_cutoff": "2026-09-23T23:59:59Z",
  "manifest_sha256": "...",
  "horizons": ["1h", "4h", "24h"],
  "model_tiers": ["U0"],
  "models": {
    "U0": {
      "1h": {
        "algorithm": "Ridge",
        "alpha": 100.0,
        "features": ["volatility_realized_24h", "volatility_compression_ratio", "volume_zscore"],
        "coefficients": [0.42, 0.05, -0.01],
        "intercept": 0.0008,
        "target_scaling_factor": 16.97056,
        "scaler": {
          "type": "StandardScaler",
          "mean": [0.001626, 0.985, 0.012],
          "scale": [0.001013, 0.312, 1.045]
        }
      }
    }
  }
}
```

---

## 2. Fail-Closed Deterministic Loader
```
                    [Load Model Bundle]
                             ↓
              [Verify SHA-256 against Lockbox]
                 /                       \
             (Valid)                  (Mismatch)
                ↓                          ↓
    [Verify Feature Shapes]       [HALT: FREEZE_VIOLATION]
         /            \
     (Match)       (Mismatch)
        ↓               ↓
[Activate Model]   [HALT: SCHEMA_ERROR]
```
- **Fail-Closed:** The engine must NEVER set `is_fitted = True` unless all required weights are loaded and validated.
- **Explicit Fallback:** If live features are missing (e.g. `SPOT_ONLY_U0`), the worker must log an explicit event (`FALLBACK_TO_PERSISTENCE`) rather than silently returning a fallback value as model inference.
