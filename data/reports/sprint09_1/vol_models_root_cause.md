# vol_models Empty Dictionary — Root Cause Forensics
**Sprint:** 09.1  
**Date:** 2026-10-09 15:06:44 UTC  

---

## 1. The Immediate Defect
In Sprint 08.2, scientific forensics discovered that the runtime dictionary `self.engine.vol_models` is completely empty.
As a result:
`m = self.vol_models.get(active_model, {}).get(h)` returns `None`.
Line 469 in `engine.py` executes:
`pred_mean = float(bar.get("volatility_realized_24h", 0.002))`
For all horizons (1h, 4h, 24h), the model simply outputs the trailing 1-hour realized volatility.

---

## 2. Exact Execution Call Chain
1. `worker.py` starts `initialize_worker()`.
2. Line 135: `self.engine = UnifiedMarketStateEngine(model_version=FROZEN_MODEL_VERSION)`.
   - In `engine.__init__()`, line 121: `self.vol_models: Dict[str, Dict[str, Ridge]] = {}`.
   - `self.scalers = {}`.
   - `self.tail_models = {}`.
   - `self.jump_models = {}`.
3. Line 136: `self.engine.is_fitted = True`.
   - This bypasses the guard `if not self.is_fitted: raise RuntimeError(...)` without loading any models.
4. On every 5-minute cycle, `worker.process_bar()` calls `self.engine.predict_bar(bar)`.
5. Inside `predict_bar()` (lines 460–470):
   ```python
   for h in ["1h", "4h", "24h"]:
       m = self.vol_models.get(active_model, {}).get(h)
       scaler_vol = self.scalers.get(f"vol_{active_model}_{h}")
       if m is not None and scaler_vol is not None and feats_arr.shape[1] == m.coef_.shape[0]:
           ...
       else:
           pred_mean = float(bar.get("volatility_realized_24h", 0.002))
   ```
6. Because `m is None`, it drops to `else:` silently.

---

## 3. Multiple Layered Failure Modes
| Failure Mode | Classification | Impact |
|---|---|---|
| No serialization code | `MODEL_ARTIFACT_MISSING` | No model files were ever exported to disk during Sprint 07 research. |
| No loader implementation | `MODEL_LOADER_NOT_IMPLEMENTED` | Neither `engine.py` nor `worker.py` has a method to deserialize model weights. |
| Bypassed fitting check | `MODEL_LOADER_NOT_CALLED` | Setting `is_fitted = True` manually masked the uninitialized model state. |
| Feature shape mismatch | `MODEL_SCHEMA_MISMATCH` | Training fit on 2 features due to column naming; runtime generates 3 features (`3 != 2`). |
| Silent fallback | `SILENT_FALLBACK` | No exception or warning was raised when `m is None`, creating the illusion of active inference. |
