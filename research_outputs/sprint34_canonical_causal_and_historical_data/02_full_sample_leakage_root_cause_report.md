# SPRINT 34 — SCIENTIFIC ROOT CAUSE REPORT
## Full-Sample Quantile Leakage & Lookahead Bias in Sprint 33 Bridge

- **Sprint ID:** `CBE_SPRINT34_CANONICAL_EXECUTION_PARITY_CAUSAL_RESEARCH_AND_HISTORICAL_DATA`
- **Module Audited:** `src/coin_behavior_engine/product/btc_timing_research/canonical_model_research_bridge.py`
- **Priority:** P0 — Scientific Integrity Blockers
- **Status:** DEFECT_ISOLATED & QUANTIFIED

---

### 1. DEFECT DESCRIPTION & EXACT CODE LOCATIONS

In Sprint 33, `CanonicalModelResearchBridge.evaluate_historical_dataset()` performed the following transformations:

```python
# Lines 230-236 in canonical_model_research_bridge.py
vol_pos = vol[vol > 0]
vol_p25 = float(np.nanpercentile(vol_pos, 25)) if len(vol_pos) > 0 else 0.20
vol_p75 = float(np.nanpercentile(vol_pos, 75)) if len(vol_pos) > 0 else 0.65

comp_pos = comp[comp > 0]
comp_p25 = float(np.nanpercentile(comp_pos, 25)) if len(comp_pos) > 0 else 0.70
comp_p75 = float(np.nanpercentile(comp_pos, 75)) if len(comp_pos) > 0 else 1.30

# Lines 240-241 (for derivatives context)
oi_drop_p05 = float(np.nanpercentile(oi_chg[~np.isnan(oi_chg)], 5)) if np.any(~np.isnan(oi_chg)) else -0.05
basis_p05 = float(np.nanpercentile(basis[~np.isnan(basis)], 5)) if np.any(~np.isnan(basis)) else -0.02
```

Here, `vol`, `comp`, `oi_chg`, and `basis` are 1D NumPy arrays spanning the **entire evaluation dataset** $t \in [0, N-1]$ (e.g. 9,528 bars for 2023–2024 or 8,760 bars for 2025).

---

### 2. MECHANISM OF FUTURE-INFORMATION LEAKAGE

1. **Temporal Non-Locality:**
   When evaluating bar $t=0$ (e.g., January 1, 2023, 00:00 UTC), the thresholds `vol_p75` and `comp_p25` used to determine whether market conditions represent `HIGH_VOLATILITY`, `COMPRESSION`, or `NORMAL` were computed using observations up to December 31, 2024, 23:00 UTC ($t=9527$).
2. **Retrospective Regime Distortion:**
   If a market exhibits low volatility in year 1 and experiences high volatility in year 2, the full-sample 75th percentile is pulled higher by year 2 data. Consequently, volatility spikes in year 1 that would have exceeded historical distribution percentiles at the time are retrospectively categorized as `NORMAL`.
3. **Failure of Prefix Invariance:**
   Let $S_T = \{x_0, x_1, \dots, x_T\}$ be a historical series up to timestamp $T$.
   If the bridge is evaluated on $S_T$, the 75th percentile is $P_{75}(S_T)$, producing classification $C_T$.
   If future observations $\{x_{T+1}, \dots, x_{T+M}\}$ are appended and the bridge is re-evaluated on $S_{T+M}$, the new 75th percentile becomes $P_{75}(S_{T+M}) \ne P_{75}(S_T)$.
   As a direct mathematical consequence, the classification of bar $T$ retroactively changes ($C_T' \ne C_T$).

---

### 3. IMPACT ON EMPIRICAL RESULTS

1. **Forward Return & Tail Risk Distributions (Sprint 33 F1–F3):**
   Regime labels in 2023–2024 and 2025 were assigned using knowledge of the unconditional distribution of the entire period. While the individual forward returns were calculated point-in-time, the conditioning variable (the regime label) was contaminated by future distribution statistics.
2. **Paper Portfolio Bounded Policy (Sprint 33 Phase H):**
   The tail-protection policy reduced exposure when the regime was `TAIL_RISK_ELEVATED` or `HIGH_VOLATILITY`. Because `HIGH_VOLATILITY` depended on full-sample `vol_p75`, the timing of de-risking actions was conditioned on future volatility levels, introducing an unphysical risk-management advantage.

---

### 4. REQUIRED CAUSAL REMEDIATION

1. **Point-in-Time Calibration Architecture:**
   - **Method A (Authoritative Pre-Declared Frozen Calibration):** Thresholds $(\tau_{\text{vol,25}}, \tau_{\text{vol,75}}, \tau_{\text{comp,25}}, \tau_{\text{comp,75}})$ must be computed strictly on a pre-declared calibration partition (e.g. Discovery 2023 partition) and **frozen permanently** prior to the out-of-sample evaluation period.
   - **Method B (Expanding Causal Window):** For any bar $t$, quantiles must be evaluated strictly on the historical slice $[0, t-1]$ (with an initial warm-up period using pre-declared prior constants).
2. **Verification by Prefix-Invariance Testing:**
   For any timestamp $T$, the classification $R(T)$ evaluated on slice $[0, T]$ must be bit-level identical to the classification $R(T)$ evaluated on slice $[0, T+k]$ for all $k \ge 1$.
