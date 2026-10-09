# Target and Horizon Parity Audit
**Sprint:** 09.1  
**Date:** 2026-10-09 15:06:44 UTC  

---

## 1. The ~17x Scale Mismatch (sqrt(288))
There is an unbridgeable scale discrepancy between historical research targets and prospective outcomes:

### Historical Research Target (`fwd_vol_{h}`)
- Defined in `src/coin_behavior_engine/outcomes/continuous.py` (line 88):
  `fwd_vol = rev_log_ret.rolling(h_steps, min_periods=h_steps).std().iloc[::-1].shift(-1)`
- This is the **unscaled 5-minute return standard deviation**.
- In `data/reports/sprint07/volatility_forecasts.csv`:
  - 1h Mean: **0.001124**
  - 4h Mean: **0.001180**
  - 24h Mean: **0.001259**

### Prospective Runtime Feature & Outcome (`realized_volatility`)
- Defined in `src/coin_behavior_engine/prospective/worker.py` (line 376):
  `vol = float(np.std(log_rets) * np.sqrt(288))`
- This is the **daily-annualized standard deviation** scaled by sqrt(288) = 16.97056.
- In live monitoring (`/api/analytics/horizons`):
  - 1h Realized Mean: **0.01404**
  - 4h Realized Mean: **0.01533**
  - 24h Realized Mean: **0.01533**

### Mathematical Scale Comparison
$$ \frac{\text{Prospective Outcome Mean}}{\text{Historical Target Mean}} = \frac{0.01404}{0.001124} \approx 12.49 \text{ to } 16.97 $$

---

## 2. Blocking Verdict
If the historically trained Sprint 07 Ridge model were loaded into production today, it would predict an unscaled value around `0.0011`. Evaluating this against live outcomes of `0.0140` would produce:
$$\text{MAE} \approx |0.0011 - 0.0140| = 0.0129$$
This would be **over 2.3x worse** than the current naive persistence fallback (`MAE = 0.00560`)!

Target scaling parity must be explicitly harmonized in CBE-0.8.0 before any model is deployed.

---

## 3. Feature Mislabelling in `worker.py`
In `worker.compute_incremental_features()`:
```python
rets = np.diff(closes) / closes[:-1]
vol_realized = float(np.std(rets[-12:]) * np.sqrt(288)) if len(rets) >= 12 else 0.002
```
`rets[-12:]` corresponds to 12 bars * 5 min = **1 hour**, but it is keyed in the return dictionary as:
`"volatility_realized_24h": vol_realized`
This is a misnomer: a 1-hour rolling metric is labeled as a 24-hour metric.
