# 06. Canonical Fallback & Attribution Audit — Sprint 34.1 Forensic Report

**Sprint ID:** `CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS`  
**Execution Timestamp:** 2026-11-15T22:11:00+03:00  
**Model Version:** `CBE-0.7.0` — `STRICTLY_FROZEN`  
**Audit Scope:** Elimination of Middle-Row Dataset Fallback Check, Point-in-Time Fallback Evaluation, 3-Tier Attribution  

---

## 1. Elimination of Middle-Row Fallback Check

In Sprint 34, `CanonicalModelResearchBridge.evaluate_historical_dataset()` determined the fallback level for an entire dataset by sampling a single row in the middle:
```python
# SPRINT 34 LEGACY (REPLACED):
sample_row = df.iloc[n // 2]
dq_state, auto_fallback = self.engine.evaluate_data_quality(sample_row)
active_fallback = forced_fallback_level or auto_fallback
```

### Scientific Defects of Middle-Row Sampling:
1. **Non-Causal Dataset-Wide Assumption:** If the middle row had derivatives, the entire multi-year dataset was assumed to have derivatives, even if earlier or later periods lacked them.
2. **Lookahead Potential:** Evaluating an index $n // 2$ conditions early bar classifications on a future bar's schema completeness.
3. **Prefix Sensitivity:** If a series length changed, $n // 2$ moved to a different timestamp, potentially altering the fallback level of preceding bars.

---

## 2. Sprint 34.1 Point-in-Time Fallback Architecture

In Sprint 34.1, middle-row sampling is completely replaced with **per-bar point-in-time fallback evaluation**:

```python
# SPRINT 34.1 CAUSAL IMPLEMENTATION:
has_deriv_bar = ~(np.isnan(oi_chg) | np.isnan(basis))
if forced_fallback_level is not None:
    can_use_deriv = np.full(n, forced_fallback_level != FallbackLevel.SPOT_ONLY_U0) & has_deriv_bar
    active_fallback = forced_fallback_level
else:
    can_use_deriv = has_deriv_bar
    active_fallback = FallbackLevel.CORE_BASELINE_U2 if np.all(can_use_deriv) else (
        FallbackLevel.SPOT_DERIVATIVES_U1 if np.any(can_use_deriv) else FallbackLevel.SPOT_ONLY_U0
    )

# Vectorized Point-in-Time Regime Decisions:
cond_delev = np.where(can_use_deriv, (oi_chg <= oi_drop_p05_arr) & (basis <= basis_p05_arr), False)
cond_jump = np.where(can_use_deriv, (vol >= vol_p75_arr) & (oi_chg > 0.05), False)
cond_tail = np.where(
    can_use_deriv,
    (basis <= basis_p05_arr) | (vol >= vol_p75_arr * 1.2),
    vol >= (vol_p75_arr * 1.25),
)
```

### Key Guarantees:
1. **Strict Point-in-Time Causality:** Bar $t$ is evaluated purely using features available at or before bar $t$.
2. **Graceful Fallback Suppression:** When derivatives are absent at bar $t$, derivative-dependent states (`DELEVERAGING_STRESS`, `JUMP_RISK_ELEVATED`) evaluate to `False`, and `TAIL_RISK_ELEVATED` uses the spot-volatility threshold (`vol >= vol_p75 * 1.25`).
3. **100% Prefix Invariance:** For any bar $t$, adding future bars $t+1, \dots, t+k$ leaves the classification of bar $t$ completely unchanged.

---

## 3. Rigorous 3-Tier Attribution Hierarchy

| Tier Name | Provenance Standard | Execution Path | Usage Context |
|---|---|---|---|
| **`CANONICAL_AUTHORITATIVE_OUTPUT`** | Direct execution of frozen `CBE-0.7.0` `UnifiedMarketStateEngine.predict_bar()`. | Ridge regression volatility, logistic regression jump/tail probabilities, epistemic covariance. | Single-bar authoritative inference, production diagnostics. |
| **`CANONICAL_COMPATIBLE_DERIVED_OUTPUT`** | Vectorized classification using frozen discovery parameters (`FROZEN_DISCOVERY_THRESHOLDS`). | Point-in-time vectorized regime classification in `CanonicalModelResearchBridge`. | Multi-year historical research, causal backtesting, portfolio simulations. |
| **`RESEARCH_HEURISTIC_OUTPUT`** | Full-sample quantiles or experimental non-canonical heuristics. | Deprecated / diagnostic only. | Explicitly flagged and quarantined from canonical claims. |
