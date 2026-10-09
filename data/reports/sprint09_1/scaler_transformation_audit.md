# Scaler and Preprocessing Transformation Audit
**Sprint:** 09.1  
**Date:** 2026-10-09 15:06:44 UTC  

---

## 1. Historical Scaler Design
In `UnifiedMarketStateEngine.fit_discovery()`:
- `StandardScaler()` was fitted on Discovery partition (`datetime_open < '2025-01-01'`).
- Feature preprocessing:
  ```python
  X = np.nan_to_num(sub[avail_feats].values, nan=0.0, posinf=1.0, neginf=-1.0)
  X = np.clip(X, -1e4, 1e4)
  scaler = StandardScaler()
  X_scaled = scaler.fit_transform(X)
  self.scalers[f"vol_{m_name}_{h}"] = scaler
  ```

---

## 2. Scaler Availability
- **Scaler parameters stored on disk:** **NONE.**
- Neither `scaler.mean_`, `scaler.scale_`, nor `scaler.var_` were serialized to disk.
- In runtime `worker.py`, `self.scalers = {}`.
- Because `scaler_vol is None`, line 463 in `predict_bar()` fails, dropping to unscaled execution or fallback.

---

## 3. Preprocessing Parity Rules for CBE-0.8.0
1. Scalers must be saved as explicit numeric arrays (`mean_`, `scale_`) inside the model bundle.
2. Missing value policy: During training, missing values were replaced by `nan=0.0`. Live runtime must follow the exact same imputation rule.
3. Clipping bounds: Inputs must be clipped to `[-1e4, 1e4]` identically in training and runtime.
