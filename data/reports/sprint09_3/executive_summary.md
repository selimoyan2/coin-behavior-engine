# Coin Behavior Engine — Sprint 09.3 Executive Summary
**Sprint:** 09.3 — Offline Shadow Replay & Prospective Parity Audit  
**Candidate Model:** CBE-0.8.0  
**Production Baseline:** CBE-0.7.0 (Strictly Frozen — Unchanged)  
**Date:** 2026-10-09T15:23:02.618730+00:00  

---

## 1. Answers to Core Research Questions

### Q1: Can historical live inputs be reconstructed without lookahead?
**Answer: YES.**  
All 3 canonical features (`volatility_realized_24h`, `volatility_compression_ratio`, `volume_zscore_24h`) are causally reconstructable from backward-looking candles $[t - 287, t]$. Out of 76,565 Holdout timestamps, **76,553 timestamps** are fully matured and causally isolated with zero forward lookahead.

### Q2: Does the serialized CBE-0.8.0 bundle produce correct inference?
**Answer: YES.**  
The immutable JSON bundle (`cbe_model_bundle_v080.json`, SHA-256 `906832a96d6012d3...`) verified cleanly against its lockbox. Pure zero-dependency bundle inference reproduces `sklearn` Ridge predictions to machine precision ($0.00\times 10^{-12}$ discrepancy across all samples).

### Q3: Do its 1h and 4h advantages survive prospective-style replay?
**Answer: YES.**  
- **1h Horizon:** Ridge MAE is `0.007068` vs Persistence `0.007449`, delivering a **+5.11% relative MAE improvement** ($R^2 = 0.399$ vs $0.232$).
- **4h Horizon:** Ridge MAE is `0.006931` vs Persistence `0.007425`, delivering a **+6.65% relative MAE improvement** ($R^2 = 0.410$ vs $0.204$).
- **24h Horizon:** Ridge MAE is `0.006024` vs Persistence `0.005812` ($-3.65\%$ relative degradation). At 24h, trailing persistence and 7d rolling averages remain superior.

### Q4: Are those improvements robust after overlapping-window adjustment?
**Answer: YES (for 1h and 4h).**  
- **1h Paired Block Bootstrap (500 resamples):** 95% Confidence Interval for paired MAE reduction is `[+0.000278, +0.000495]`, strictly excluding zero ($p < 0.001$). Ridge beats persistence across **100% of tested non-overlapping starting offsets**.
- **4h Paired Block Bootstrap:** 95% Confidence Interval is `[+0.000271, +0.000698]`, strictly excluding zero ($p < 0.001$).
- **24h Paired Block Bootstrap:** 95% Confidence Interval is `[-0.000555, +0.000157]`, confirming no statistically significant advantage.

### Q5: Is the candidate technically suitable for future shadow observation?
**Answer: YES, AS A SHADOW RUNTIME CANDIDATE ONLY.**  
CBE-0.8.0 is mathematically robust, fail-closed, and technically ready for future zero-risk passive shadow logging. However, it is **NOT APPROVED FOR PRODUCTION TRADING OR PRIMARY REPLACEMENT**. A future deployment should hybridize horizons (using Ridge for 1h/4h and trailing persistence for 24h).

---

## 2. Regime Robustness Highlights
- **Normal Volatility ($N=35,300$):** Ridge lift over persistence is **+9.54%**.
- **High Volatility ($N=5,373$):** Ridge lift over persistence is **+12.55%**.
- **Volatility Expansion ($N=15,896$):** Ridge lift over persistence is **+19.67%**.
- **Low Volatility / Compression:** Trailing persistence is slightly favored ($-4.7\%$) due to Ridge's positive intercept.

---

## 3. Scientific Decision Gates
- **Gates Passed:** `10 / 10 PASS`
- **Candidate Verdict:** `READY_FOR_FUTURE_SHADOW_REVIEW`
- **Deployment Status:** `PROHIBITED`
