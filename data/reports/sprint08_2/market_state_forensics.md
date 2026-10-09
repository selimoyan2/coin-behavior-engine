# CBE-0.7.0 Market-State Classifier Forensics
**Sprint:** 08.2  
**Date:** 2026-10-09 13:44:24 UTC  
**Status:** CONFIRMED_DETERMINISTIC_LOCK  
**Observed Condition:** 100.0% of 4,309 prospective predictions classified as `DELEVERAGING_STRESS`.

---

## 1. Executive Summary
The Coin Behavior Engine live monitoring panel reports that all 4,308 prospective predictions since deployment have been classified as `DELEVERAGING_STRESS`. Static and dynamic forensic inspection has isolated the exact mathematical and architectural root cause: **a deterministic single-row percentile collapse bug inside `UnifiedMarketStateEngine.predict_bar()` coupled with zero-defaulting missing derivatives under `SPOT_ONLY_U0`**.

Under the current implementation, all alternative market states are **100% unreachable**.

---

## 2. Forensic Root Cause Analysis

### Structural Cause 1: Single-Row Percentile Collapse
In `src/coin_behavior_engine/market_state/engine.py` (lines 524–526):
```python
# 3. Market State Classification & Transition Probabilities
dummy_df = pd.DataFrame([bar])
current_state = self._classify_market_states_series(dummy_df).iloc[0]
```

Inside `_classify_market_states_series(df)` (lines 355–373):
```python
oi_chg = df["oi_change_1h"].values if "oi_change_1h" in df.columns else np.zeros(n)
basis = df["basis_level"].values if "basis_level" in df.columns else np.zeros(n)

oi_drop_p05 = float(np.nanpercentile(oi_chg, 5)) if len(oi_chg) > 0 else -0.05
basis_p05 = float(np.nanpercentile(basis, 5)) if len(basis) > 0 else -0.02

cond_delev = (oi_chg <= oi_drop_p05) & (basis <= basis_p05)
```

When evaluated on a 1-row DataFrame `dummy_df`:
1. `oi_chg` has length 1: `[x]`.
2. `np.nanpercentile([x], 5)` evaluates to `x`.
3. The condition `oi_chg <= oi_drop_p05` evaluates to `x <= x`, which is **identically TRUE** for any finite number x.
4. Similarly, `basis <= basis_p05` evaluates to `y <= y`, which is **identically TRUE** for any finite number y.
5. Therefore, `cond_delev` is `True & True == True`.
6. Because `cond_delev` is the **first condition** in the `np.select()` cascade mapped to `choices[0] = MarketStateId.DELEVERAGING_STRESS.value`, the classifier **always** terminates at condition 1.

### Structural Cause 2: Missing Derivatives Zero-Defaulting
Under `SPOT_ONLY_U0`, derivatives feeds are inactive. In `_classify_market_states_series`, missing columns default to `np.zeros(n)`.
Even if a multi-row DataFrame were evaluated:
- `oi_drop_p05 = np.nanpercentile([0.0, ..., 0.0], 5) == 0.0`.
- `basis_p05 = np.nanpercentile([0.0, ..., 0.0], 5) == 0.0`.
- `cond_delev = (0.0 <= 0.0) & (0.0 <= 0.0) == True` for every single row.

---

## 3. Counterfactual Testing Evidence
Five counterfactual synthetic bars were evaluated offline using the frozen classifier:
| Test Case | Input | Classified State | Locked? |
|---|---|---|:---:|
| `empty_bar` | `{}` | `DELEVERAGING_STRESS` | YES |
| `calm_spot_only` | `vol=0.0005, comp=1.5` | `DELEVERAGING_STRESS` | YES |
| `high_vol_spot_only` | `vol=0.0500, comp=0.5` | `DELEVERAGING_STRESS` | YES |
| `raging_bull_deriv` | `basis=0.15, oi_chg=0.25` | `DELEVERAGING_STRESS` | YES |
| `extreme_event_shock` | `is_event_active_4h=1.0` | `DELEVERAGING_STRESS` | YES |

Even an extreme event shock bar or a roaring bull derivatives bar collapses to `DELEVERAGING_STRESS` because condition 1 precedes all other conditions and is identically satisfied.

---

## 4. Reachability Matrix under SPOT_ONLY_U0
| Market State | Reachability |
|---|:---:|
| `DELEVERAGING_STRESS` | **100% (Locked)** |
| `QUIET` | 0% (Unreachable) |
| `COMPRESSION` | 0% (Unreachable) |
| `NORMAL` | 0% (Unreachable) |
| `EXPANSION_WATCH` | 0% (Unreachable) |
| `HIGH_VOLATILITY` | 0% (Unreachable) |
| `TAIL_RISK_ELEVATED` | 0% (Unreachable) |
| `JUMP_RISK_ELEVATED` | 0% (Unreachable) |
| `EVENT_SHOCK_ACTIVE` | 0% (Unreachable) |

---

## 5. Architectural Recommendation (Non-Model Sprint)
In a future post-freeze sprint:
1. Pre-fit and store static percentile cutoff values during discovery calibration rather than recalculating in-sample percentiles dynamically at runtime.
2. Require valid derivatives data before evaluating `cond_delev`, or route through a designated `SPOT_ONLY` state decision tree.
3. The frozen model CBE-0.7.0 must remain unmodified during Sprint 08.2.
