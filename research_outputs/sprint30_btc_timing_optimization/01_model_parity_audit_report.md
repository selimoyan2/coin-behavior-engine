# 01 — Model Parity Audit Report (Canonical CBE-0.7.0 vs Research Adapter)

**Sprint ID:** `CBE_SPRINT30_BTC_TIMING_OPTIMIZATION`  
**Audit Timestamp:** `2026-11-15T00:29:29.333969+00:00`  
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)  
**Audit Verdict:** **`CANONICAL_PARITY_NOT_ESTABLISHED`**  
**Taxonomy Classification:** **`DERIVED_RESEARCH_CLASSIFIER`**  
**Canonical Parity:** **`False`**  

---

## 1. Executive Summary & Epistemological Ruling

The independent source code review of Sprint 29 identified a potential misattribution regarding the market regime classifications used in the BTC timing research experiments.

This audit establishes definitively:
- **Canonical Model Parity is NOT established.**
- The historical feature adapter (`historical_feature_adapter.py`) uses heuristic static thresholding on rolling 24-hour Parkinson volatility and standardized 24-hour return z-scores to assign candles to 6 descriptive clusters (`CONSOLIDATION_RANGING`, `RECOVERY_ACCUMULATION`, `MOMENTUM_EXPANSION`, `DISTRIBUTION`, `HIGH_VOLATILITY_EXPANSION`, `CAPITULATION`).
- In contrast, the canonical frozen model (`UnifiedMarketStateEngine`, CBE-0.7.0) defines 9 probabilistic market states (`QUIET`, `COMPRESSION`, `NORMAL`, `EXPANSION_WATCH`, `HIGH_VOLATILITY`, `TAIL_RISK_ELEVATED`, `JUMP_RISK_ELEVATED`, `EVENT_SHOCK_ACTIVE`, `DELEVERAGING_STRESS`) derived from multi-source inputs (spot OHLCV, perpetual derivatives funding and basis, ETF flows, macro event releases, and global trading sessions).
- Therefore, the classifications in Sprint 29 represent a **DERIVED_RESEARCH_CLASSIFIER**, not canonical CBE-0.7.0 model outputs.
- To maintain uncompromising scientific truth, all policies and deliverables must refer to these outputs as **Derived Research Regimes** rather than claiming canonical CBE outputs.
- In accordance with this finding, Experiment D (Canonical CBE Model) is formally classified as **`NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE`**.

---

## 2. Structural Comparison Matrix

| Audit Dimension | Canonical CBE-0.7.0 | Sprint 29 Research Adapter | Match Status | Scientific Analysis |
| :--- | :--- | :--- | :--- | :--- |
| `regime_state_taxonomy` | `['COMPRESSION', 'DELEVERAGING_STRESS', '` | `['CAPITULATION', 'CONSOLIDATION_RANGING'` | **✗ DIVERGENT** | Canonical CBE-0.7.0 MarketStateId defines 9 probabilistic states (QUIET, COMPRESSION, NORMAL, EXPANSION_WATCH, HIGH_VOLATILITY, TAIL_RISK_ELEVATED, JUMP_RISK_ELEVATED, EVENT_SHOCK_ACTIVE, DELEVERAGING_STRESS), whereas Sprint 29 adapter adopted 6 descriptive cluster names from Sprint 26 (CONSOLIDATION_RANGING, RECOVERY_ACCUMULATION, MOMENTUM_EXPANSION, DISTRIBUTION, HIGH_VOLATILITY_EXPANSION, CAPITULATION). |
| `feature_input_layers` | `['Spot Market (OHLCV)', 'Perpetual Deriv` | `['Spot Market (1h High, Low, Close only)` | **✗ DIVERGENT** | Canonical CBE-0.7.0 integrates multi-source information layers with deterministic fallback levels (U5 to U0). The adapter operates solely on spot 1-hour candles. |
| `inference_methodology` | `Multi-layer calibrated probabilistic cla` | `Heuristic static thresholding on rolling` | **✗ DIVERGENT** | Canonical CBE-0.7.0 uses statistical calibration with fallback hierarchy. The adapter applies threshold rules (z >= 1.25, z <= -1.75, vol >= q90). |
| `point_in_time_guarantee` | `Strict causal filtering on closed 5m can` | `Rolling window (168h) quantiles on compl` | **✓ MATCH** | Both implementations strictly respect causality with zero future lookahead. However, they evaluate on different frequencies (5m multi-layer vs 1h spot-only). |
| `causal_regime_engine_v1_cross_check` | `['HIGH_VOLATILITY', 'RANGE', 'TRANSITION` | `['CAPITULATION', 'CONSOLIDATION_RANGING'` | **✗ DIVERGENT** | Sprint 11.21 CausalRegimeEngine defines TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY, TRANSITION, UNCERTAIN. Adapter taxonomy diverges. |

---

## 3. Epistemological Directives & Trust Boundary Closure

1. **Renaming & Alias Enforcement:** `POLICY_CBE_REGIME` is registered alongside `POLICY_DERIVED_RESEARCH_REGIME` to explicitly acknowledge its derived nature.
2. **Exclusion from Production Claims:** No claims are made that these heuristic classifications represent production probabilistic model performance.
3. **Quarantine of Directional Predictions:** The zero directional trading eligibility invariant is strictly enforced (`DIRECTIONAL_TRADING_ELIGIBILITY = 0`).
