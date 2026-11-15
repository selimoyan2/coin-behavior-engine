# SPRINT 34 — CANONICAL INFERENCE PARITY AUDIT
## Authoritative Architecture of UnifiedMarketStateEngine vs Research Bridge

- **Sprint ID:** `CBE_SPRINT34_CANONICAL_EXECUTION_PARITY_CAUSAL_RESEARCH_AND_HISTORICAL_DATA`
- **Canonical Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)
- **Source Under Audit:** `src/coin_behavior_engine/market_state/engine.py`
- **Bridge Under Audit:** `src/coin_behavior_engine/product/btc_timing_research/canonical_model_research_bridge.py`

---

### 1. AUTHORITATIVE INFERENCE ENTRY POINTS IN CBE-0.7.0

The frozen canonical class `UnifiedMarketStateEngine` exposes the following methods:

1. `fit_discovery(discovery_df: pd.DataFrame) -> None`:
   - Calibrates Ridge volatility models (`vol_models`), LogisticRegression tail models (`tail_models`), jump risk models (`jump_models`), state transition matrix (`state_transition_matrix`), and epistemic centroid/covariance.
   - Sets `self.is_fitted = True`.
2. `evaluate_data_quality(row: Union[pd.Series, Dict[str, Any]]) -> Tuple[DataQualityState, FallbackLevel]`:
   - Evaluates missingness across Spot, Derivatives, Session, Macro, and Events.
   - Maps missing inputs to `SPOT_ONLY_U0`, `SPOT_DERIVATIVES_U1`, `CORE_BASELINE_U2`, or `FULL_CONTEXT_U5`.
3. `predict_bar(bar: Union[pd.Series, Dict[str, Any]], fallback_override=None) -> Dict[str, Any]`:
   - Authoritative point-in-time single-bar inference method.
   - Requires `self.is_fitted == True` (raises `RuntimeError` otherwise).
   - Outputs:
     - `fallback_level`: Active Information Ladder level.
     - `data_quality_state`: Input degradation flag.
     - `current_market_state`: Discrete regime label from the 9-state taxonomy.
     - `volatility_forecasts`: Parametric forecasts and quantiles (p10 to p99) for 1h, 4h, 24h.
     - `tail_risk_probabilities`: P(Loss > 95th percentile) for 1h, 4h, 24h.
     - `jump_risk_probabilities`: P(Loss > 99th percentile) for 1h, 4h, 24h.
     - `transition_probabilities_1h`: Markov transition row given `current_market_state`.
     - `uncertainty_decomposition`: Aleatoric, Epistemic, and Total Uncertainty.
4. `predict_batch_volatility` and `predict_batch_tail_risk`:
   - Batch inference routines for fitted Ridge and LogisticRegression models.

---

### 2. DETAILED COMPARISON: SPRINT 33 BRIDGE VS AUTHORITATIVE CANONICAL MODEL

| Dimension | Authoritative Canonical (`UnifiedMarketStateEngine`) | Sprint 33 Bridge (`canonical_model_research_bridge.py`) | Parity Status |
|---|---|---|---|
| **Instantiation** | Requires calibration on Discovery data (`fit_discovery`) | Instantiated uncalibrated; ran independently | **NO PARITY** |
| **Inference Call** | `predict_bar()` computes Ridge + Logistic + Uncertainty | Used standalone vectorized `np.select` with custom thresholds | **NO PARITY** |
| **Fallback Evaluation** | Evaluated per bar via `evaluate_data_quality(bar)` | Evaluated once per entire dataset on median row | **PARTIAL** |
| **Regime Probabilities** | Returns discrete state + Markov 1h transition vector; **does not output 9-state concurrent probabilities** | Synthesized confidence score via heuristic formula | **DERIVED HEURISTIC** |
| **Epistemic Confidence** | Derived from Mahalanobis distance to Discovery centroid (`epistemic_uncertainty`) | Computed from availability % and ad-hoc regime penalties | **DERIVED HEURISTIC** |
| **Single-Bar Thresholds** | `_classify_market_states_series` recomputes percentiles on passed DataFrame | Recomputed percentiles over full historical series (Lookahead) | **DEFECT IN BOTH** |

---

### 3. THE SINGLE-BAR CLASSIFICATION DEFECT IN CANONICAL CODE

Inspection of `UnifiedMarketStateEngine.predict_bar()` reveals an architectural limitation in the frozen `CBE-0.7.0` codebase:

```python
# Lines 524-525 in engine.py
dummy_df = pd.DataFrame([bar])
current_state = self._classify_market_states_series(dummy_df).iloc[0]
```

When `dummy_df` has exactly 1 row:
- `vol_pos = vol[vol > 0]` has length 1.
- `vol_p75 = np.nanpercentile(vol_pos, 75)` evaluates to `vol[0]`.
- Condition `cond_high_vol = vol >= vol_p75` evaluates to `vol[0] >= vol[0]`, which is **always True** for any positive volatility!
- As a consequence, calling uncalibrated `predict_bar()` on individual isolated rows causes positive-volatility bars to collapse into `HIGH_VOLATILITY` unless preceded by `DELEVERAGING_STRESS` or `TAIL_RISK`.

---

### 4. CANONICAL ATTRIBUTION TAXONOMY (PHASE C MANDATE)

To eliminate false claims of canonical equivalence, all model outputs must be explicitly classified into three distinct categories:

1. `CANONICAL_AUTHORITATIVE_OUTPUT`:
   - Originates strictly from `UnifiedMarketStateEngine.predict_bar()` executed with a verified, fitted Discovery state.
   - Outputs: Parametric volatility forecasts, tail-risk probabilities, jump-risk probabilities, and Information Ladder fallback levels.
2. `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`:
   - Point-in-time causal classification that implements the canonical 9-state rules and Information Ladder fallback semantics using **pre-declared frozen Discovery thresholds** or expanding historical windows.
   - Used for multi-year historical series where full feature matrices (derivatives, ETF, macro) are partially available under `SPOT_ONLY_U0`.
3. `RESEARCH_HEURISTIC_OUTPUT`:
   - Empirical baseline classifiers (e.g. Baseline A rolling volatility quartiles, Baseline B SMA crossovers, Baseline C 4-state heuristic, Baseline D Parkinson/SMA).
   - Non-canonical synthetic confidence metrics.
