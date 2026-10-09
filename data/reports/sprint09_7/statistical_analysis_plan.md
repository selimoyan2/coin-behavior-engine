# SPRINT 09.7: STATISTICAL ANALYSIS PLAN

**Protocol Plan:** SAP-CBE-0.8.0-PROSPECTIVE  
**Focus:** Dependence-aware evaluation of overlapping 5-minute time series forecasts  

---

## 1. DEPENDENCE-AWARE NON-OVERLAPPING STRIDING

Because 5-minute forecasts have overlapping evaluation windows (12 bars for 1h, 48 bars for 4h, 288 bars for 24h), successive residuals are autocorrelated by construction.

To avoid artificial inflation of sample size ($N$), the statistical analysis plan predeclares:
- **Horizon-Stride Subsampling:**
  - 1h: Step = 12 bars (every 60 minutes)
  - 4h: Step = 48 bars (every 240 minutes)
  - 24h: Step = 288 bars (every 1,440 minutes / 1 day)
- **Offset Sensitivity:** Evaluate across all possible starting offsets $k \in [0, \text{step}-1]$ to confirm robustness against arbitrary starting points.

---

## 2. PAIRED CIRCULAR BLOCK BOOTSTRAP

- **Replications:** $B = 500$ iterations.
- **Block Size:** $L = 288$ bars (24 hours), matching daily periodicity and residual clustering.
- **Random Seed:** Deterministically fixed to `42`.
- **Target Metric:** $\Delta \text{MAE} = |e_{\text{candidate}}| - |e_{\text{baseline}}|$.
- **Confidence Intervals:** 95% two-sided empirical percentile intervals $[q_{2.5}, q_{97.5}]$.
- **Significance Criterion:** $p < 0.05$ and CI strictly bounded away from zero.

---

## 3. HORIZON-SPECIFIC EVALUATION POLICY

1h, 4h, and 24h horizons must be analyzed and reported in separate standalone tables. Pooling horizons into an aggregated average score is prohibited.
