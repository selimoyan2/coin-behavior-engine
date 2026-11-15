# SPRINT 34 — CANONICAL OUTPUT ATTRIBUTION REPORT
## Attribution Standards, Transparency & Provenance Boundaries

- **Sprint ID:** `CBE_SPRINT34_CANONICAL_EXECUTION_PARITY_CAUSAL_RESEARCH_AND_HISTORICAL_DATA`
- **Standard Enforced:** Three-Tier Epistemic Attribution Standard

---

### 1. ATTRIBUTION TIERS

Every data point, report metric, API response, and dashboard widget must explicitly declare its attribution tier according to the following definitions:

```text
+-----------------------------------------------------------------------------------+
| 1. CANONICAL_AUTHORITATIVE_OUTPUT                                                 |
|    - Direct execution of UnifiedMarketStateEngine (CBE-0.7.0).                   |
|    - Validated Discovery calibration weights and state transition matrices.       |
|    - Epistemic uncertainty derived from Mahalanobis distance to centroid.        |
|    - Applicable to: Volatility forecasts, tail/jump probabilities, fallback level. |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. CANONICAL_COMPATIBLE_DERIVED_OUTPUT                                            |
|    - Causal, point-in-time implementation of the canonical 9-state rule set.     |
|    - Uses pre-declared frozen calibration thresholds (from 2023 discovery split)  |
|      or causal expanding historical windows.                                      |
|    - Enforces strict Information Ladder fallback (SPOT_ONLY_U0).                  |
|    - Zero lookahead bias; passes Prefix-Invariance tests.                         |
|    - Applicable to: Long-horizon historical series classification & transition.   |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 3. RESEARCH_HEURISTIC_OUTPUT                                                      |
|    - Independent empirical benchmarks (Baselines A, B, C, D).                    |
|    - Non-probabilistic technical indicators (SMA trend, rolling volatility).     |
|    - Experimental risk-management bounds and exploratory policy rules.            |
+-----------------------------------------------------------------------------------+
```

---

### 2. RECONCILIATION OF SPRINT 33 BRIDGE METRICS

In Sprint 33, classifications and dashboard summaries were labeled as direct canonical outputs. Under the Sprint 34 audit:

1. **Sprint 33 Regime Classifications:** Reclassified from `CANONICAL_AUTHORITATIVE_OUTPUT` to `RESEARCH_HEURISTIC_OUTPUT` due to full-sample quantile conditioning.
2. **Sprint 34 Corrected Classifications:** Classified as `CANONICAL_COMPATIBLE_DERIVED_OUTPUT` when executed via point-in-time expanding windows or pre-declared calibration splits.
3. **Parametric Volatility and Risk Probabilities:** Classified as `CANONICAL_AUTHORITATIVE_OUTPUT` when invoked directly via `UnifiedMarketStateEngine.predict_bar()`.

---

### 3. API & UI ENFORCEMENT

The API endpoint `GET /api/v1/product/btc-timing/v11/model-status` and the new V11.1 dashboard components must return the following JSON structure:

```json
{
  "attribution_tier": "CANONICAL_COMPATIBLE_DERIVED_OUTPUT",
  "authoritative_model_engine": "UnifiedMarketStateEngine",
  "canonical_version": "CBE-0.7.0",
  "calibration_method": "PREDECLARED_FROZEN_DISCOVERY_SPLIT",
  "causal_integrity_status": "PREFIX_INVARIANCE_VERIFIED",
  "lookahead_leakage_status": "ZERO_LEAKAGE_CONFIRMED"
}
```
