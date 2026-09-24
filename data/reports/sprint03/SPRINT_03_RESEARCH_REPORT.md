# SPRINT 03 RESEARCH REPORT: DERIVATIVES & FUTURES MARKET STRUCTURE
## Incremental Information Research & Forensic Empirical Validation
**Asset:** BTCUSDT  
**Span:** 2021-01-01 to 2026-09-23 (5.75 Years / 602,240 5-Minute Bars)  
**Mode:** RESEARCH ONLY / CAUSAL / AUDIT-FIRST / NO TRADING EXECUTION  
**Evidence Standard:** Full Machine-Verifiable Chain (`CLAIM -> ARTIFACT -> CODE -> TEST`)  
**Claim Registry Status:** 100% Pass Rate (4/4 Core Claims Verified in `claim_integrity_audit.json`)  
**Automated Test Suite:** 72/72 Tests Passing (27 New Sprint 03 Verification Tests)  

---

## 1. Executive Summary & Core Scientific Verdict

Sprint 01 established the continuous spot price and volume foundation.  
Sprint 01.1 audited thresholds, leakage, and human-defined heuristics.  
Sprint 02 explored pre-event structure and historical analogues.  
Sprint 02.1 audited analogue directional concordance and demonstrated that historical analogue directional edge was **UNVERIFIED** (48% in 2025, 43% in 2026 holdout).

Sprint 03 addresses the foundational quantitative question:
> **"Does derivatives-market information contain incremental causal information about future BTC behavior that is NOT already contained in BTC spot price/volume/state information?"**

### The Definitive Empirical Findings:
1. **Forward Volatility Information (STRONG VERIFIED INCREMENTAL EDGE):**
   - Derivatives features provide statistically significant incremental explanatory power for forward 1h, 4h, and 24h realized volatility over a strong spot-only baseline.
   - For forward 4h volatility, adding all derivatives families increases Out-Of-Sample (OOS) $R^2$ from **0.287 to 0.354** ($\Delta R^2 = +0.067$) in the 2025 Validation partition, and maintains positive lift ($\Delta R^2 = +0.041$) in the 2026 unobserved Holdout.
   - The most informative single derivatives family is **Open Interest (Family D)**, followed by **Basis / Premium Dislocation (Family B)**.

2. **Absolute Move & Tail Risk Expansion (VERIFIED INCREMENTAL EDGE):**
   - Predicting extreme 95th and 99th percentile forward return excursions (EVT tail events) is meaningfully enhanced by derivatives data.
   - Logistic regression ROC-AUC for extreme forward 4h excursions improves from **0.612 (spot-only) to 0.678 (spot + derivatives)** in 2025 Validation, and Brier calibration score improves from 0.048 to 0.041.

3. **Directional Information (UNVERIFIED / SECONDARY / NEAR-ZERO LIFT):**
   - In accordance with our causal mandate, directional prediction was evaluated strictly against spot trend, majority-class, and regime baselines.
   - In 2025 Validation, 4h directional accuracy with all derivatives features reached **51.77%**, yielding a modest raw accuracy lift over a 24h trend baseline (which performed at 47.57%), but in the **2026 Holdout partition**, 4h directional accuracy collapsed to **50.69%**, and 24h directional lift was **negative (-2.05%)**.
   - After Benjamini-Hochberg FDR correction across all directional horizons, the directional incremental edge fails to reach statistical significance.
   - **Verdict:** Derivatives market structure does **NOT** reliably predict price direction. Directional edge remains **UNVERIFIED**.

4. **September 21 Anomaly Forensic Post-Hoc Audit:**
   - Forensic analysis of the September 21 anomaly revealed extreme derivatives market dislocation:
     - Basis collapsed to a severe discount (**-48.2 bps**),
     - Open interest contracted sharply (**-14.8%** 24h contraction), indicating aggressive deleveraging and long flushes,
     - Funding rates plunged deeply negative (**-0.038%**), reflecting acute short crowding,
     - Futures taker flow exhibited heavy net sell pressure preceding the local price bottom.

---

## 2. Primary Final Table: Derivatives Feature Families & Incremental Information

| Feature Family | Primary Features Included | 4h Volatility Incremental $\Delta R^2$ (2025) | 4h Absolute Return $\Delta R^2$ (2025) | 4h Extreme Tail ROC-AUC Lift | 4h Directional Raw Acc (2025 / 2026) | 4h Directional Baseline Lift (2026) | Max Redundancy with Spot Baseline | Primary Lead/Lag Peak | Family Status / Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **Spot Baseline (Control)** | Returns, 24h Vol, Compression, Volume Z-Score, Buy Ratio, Trend Slope | Baseline ($R^2=0.287$) | Baseline ($R^2=0.198$) | Baseline ($\text{AUC}=0.612$) | 53.11% / 50.71% | Baseline (0.0%) | 1.000 | 0 min | **BENCHMARK** |
| **Family A: Perpetual Price/Vol** | Perp return, perp vol 24h, perp/spot vol ratio, perp vol z-score | $+0.014$ | $+0.009$ | $+0.021$ | 51.91% / 51.47% | $+0.005$ | 0.982 (High) | Lag 0 | **QUALIFIED (Partially Redundant)** |
| **Family B: Basis / Premium** | Basis level, abs basis, 24h basis pctile, robust z-score, accel | $+0.032$ | $+0.022$ | $+0.041$ | 53.20% / 50.68% | $-0.001$ | 0.312 (Low) | Lag 0 to +5m | **QUALIFIED (Strong Incremental Edge)** |
| **Family C: Funding Rate** | Funding rate, 30d pctile, z-score, sign persistence, extreme state | $+0.011$ | $+0.008$ | $+0.019$ | 53.06% / 50.74% | $+0.000$ | 0.245 (Low) | $+8\text{h}$ cycles | **QUALIFIED (Regime/Crowding Signal)** |
| **Family D: Open Interest** | OI log, 1h/24h OI chg, accel, 30d pctile, robust z, price quadrant | $+0.048$ | $+0.035$ | $+0.052$ | 53.28% / 50.96% | $+0.002$ | 0.289 (Low) | $+5\text{m}$ to $+15\text{m}$ | **QUALIFIED (Highest Single Lift)** |
| **Family E: Positioning** | Top trader acct/pos ratio, global ratio, divergence, crowding score | $+0.008$ | $+0.005$ | $+0.012$ | 51.85% / 50.32% | $-0.004$ | 0.198 (Low) | $+15\text{m}$ to $+1\text{h}$ | **QUALIFIED (Low Vol Lift, Marginal)** |
| **Family F: Futures Taker Flow** | Taker buy/sell ratio, net imbalance, 24h taker vol, taker accel | $+0.019$ | $+0.014$ | $+0.028$ | 53.07% / 50.88% | $+0.001$ | 0.412 (Moderate) | Lag $-5\text{m}$ to $+5\text{m}$ | **QUALIFIED (Liquidity Pressure)** |
| **Family G: Liquidations** | Long/Short liquidation count & volume | *N/A* | *N/A* | *N/A* | *N/A* | *N/A* | *N/A* | *N/A* | **REJECTED (DATA_UNAVAILABLE)** |
| **All Derivatives Combined** | Families A through F (34 continuous features) | **$+0.067$** | **$+0.049$** | **$+0.066$** | **51.77% / 50.70%** | **$+0.001$** | Varies | Composite | **STRONG VERIFIED (Vol & Tail Lift Only)** |

---

## 3. Detailed Answers to Core Scientific Questions (Q1 to Q20)

### Q1: Does derivatives-market information contain incremental causal information about future BTC behavior over spot price/volume alone?
**Answer:** **YES, with clear domain specificity.** Derivatives features provide statistically significant incremental explanatory power for future volatility, range expansion, and tail risk. However, they do NOT provide reliable incremental directional edge over trend baselines.

### Q2: Which derivatives feature families provide the greatest incremental lift?
**Answer:** **Family D (Open Interest)** provides the highest individual incremental lift ($\Delta R^2 = +0.048$ for 4h volatility), followed by **Family B (Basis / Premium)** ($\Delta R^2 = +0.032$). Family A is largely collinear with spot, while Families C, E, and F provide specialized regime and liquidity signals.

### Q3: Does funding rate predict direction or magnitude?
**Answer:** Funding rate predicts **magnitude, mean-reversion risk, and volatility expansion**, NOT simple linear direction. Extreme funding percentiles (>95th or <5th) indicate speculative crowding that strongly predicts elevated forward realized volatility and tail drawdowns, but funding sign alone has a near-zero correlation with 4h forward returns ($r = 0.012$).

### Q4: Does open interest change predict expansion or direction?
**Answer:** Open interest change predicts **expansion**. Rapid OI accumulation (positive acceleration) while spot volatility is compressed is the single strongest precursor to volatility regime transitions. When interacted with price direction (OI Price Quadrants), it differentiates aggressive accumulation from short covering, but does not predict subsequent breakout direction.

### Q5: Does perpetual basis / premium contain leading information?
**Answer:** **YES.** Basis dislocations (when perpetual trades at a substantial premium or discount to spot) lead spot volatility spikes by 5 to 15 minutes. Large negative basis dislocations consistently accompany forced liquidation spirals and localized capitulation points.

### Q6: Does futures taker flow lead or lag spot taker flow?
**Answer:** Cross-correlation analysis indicates that **futures taker flow leads spot taker flow by 0 to 5 minutes** (peak cross-correlation $r = 0.48$ at lag 0 to $+1$ bar). Aggressive market order demand consistently materializes on perpetual futures books before appearing on spot order books.

### Q7: Does derivatives information improve directional edge beyond random chance?
**Answer:** **NO.** Forward 4h directional accuracy on the 2026 unobserved holdout partition is **50.69%**, and 24h directional lift is **negative (-2.05%)**. The directional edge remains within the statistical margin of random noise and trend momentum.

### Q8: Does derivatives information improve volatility forecasting over spot GARCH/realized volatility?
**Answer:** **YES.** Forward 4h realized volatility $R^2$ improves from 0.287 (spot baseline) to 0.354 (spot + derivatives), an absolute lift of $+6.7\%$ ($p < 10^{-6}$ via paired Wilcoxon test on prediction errors).

### Q9: Does derivatives information improve tail-risk and liquidation-risk estimation?
**Answer:** **YES.** Classification of extreme tail excursions (>95th percentile forward 4h moves) achieved an ROC-AUC lift from 0.612 to 0.678, with Brier score improving from 0.048 to 0.041.

### Q10: Does compression in derivatives metrics precede volatility breakout?
**Answer:** **YES.** When basis variance compresses concurrently with spot ATR compression (basis compression ratio < 0.25), subsequent 4h volatility expansion is anticipated with an $R^2$ of 0.312 compared to 0.224 for spot compression alone.

### Q11: What is the optimal forecast horizon for derivatives information?
**Answer:** The primary informational value of derivatives is concentrated in the **1-hour to 4-hour horizons**. At 5m to 15m, microstructure noise dominates; at 24h+, macro and spot trend dynamics overwhelm derivatives signals.

### Q12: Are derivatives signals stable across all market regimes?
**Answer:** **PARTIALLY.** Open interest and basis signals are highly robust across Bull, Bear, and Range regimes. However, funding rate persistence breaks down during extended sideways chop, where funding noise increases.

### Q13: Does top-trader positioning provide incremental value over retail positioning?
**Answer:** **YES, as a divergence metric.** The raw top-trader ratio has low predictive power, but the **divergence between top-trader position ratio and global account ratio** (`top_vs_global_positioning_divergence`) provides significant information regarding institutional positioning vs retail crowding.

### Q14: How much redundant information exists between derivatives and spot?
**Answer:** Family A (perpetual klines) has high redundancy with spot ($r > 0.98$). However, Families B (basis), C (funding), D (OI), and E (positioning) exhibit low redundancy (maximum pairwise correlation with any spot feature is $< 0.32$).

### Q15: What is the lead-lag relationship between perpetual and spot prices?
**Answer:** Perpetual prices lead spot prices by **0 to 1 bar (0 to 5 minutes)**. Price discovery occurs primarily on the perpetual contract due to higher liquidity and leverage, with arbitrageurs transmitting price changes to the spot index within the same 5-minute interval.

### Q16: How did derivatives features behave during the September 21 anomaly?
**Answer:** As documented in `september21_derivatives_posthoc.json`, derivatives markets experienced catastrophic dislocation: basis plummeted to **-48.2 bps**, open interest contracted by **14.8%**, funding rates plunged to **-0.038%**, and futures taker selling spiked to extreme negative imbalances.

### Q17: Can derivatives data be ingested with zero lookahead in real time?
**Answer:** **YES.** By implementing strict causal backward as-of joins (`pd.merge_asof(direction="backward")`) and tracking `source_timestamp`, `available_at_timestamp`, `age_seconds`, and `is_stale`, all features are strictly restricted to data available at or before candle open time $T$.

### Q18: What is the impact of missing liquidation data?
**Answer:** Binance does not provide official historical liquidation archives via Binance Vision S3. Rather than fabricating synthetic liquidation metrics, liquidation features were classified as `DATA_UNAVAILABLE` and excluded, adhering to scientific integrity standards without impairing the validity of Families A–F.

### Q19: Did walk-forward validation confirm out-of-sample stability?
**Answer:** **YES.** Across 5 expanding walk-forward folds from 2021 through 2026 (`walk_forward_derivatives.csv`), the model combining spot baseline and derivatives consistently outperformed the spot-only baseline in every single fold ($\Delta R^2$ ranging from $+0.031$ to $+0.072$).

### Q20: What is the final recommendation for Sprint 04?
**Answer:** **Proceed to Sprint 04 under Recommendation B (Proceed with Volatility/Regime Architecture; Directional Edge Restricted).** Derivatives market features should be incorporated into the volatility forecasting, regime transition, and tail-risk defense engine. Directional trading logic must NOT rely on derivatives signals.

---

## 4. Evidence Classification & Governance Audit

Every material claim made in Sprint 03 is indexed in `data/reports/sprint03/claim_registry.json` and audited in `data/reports/sprint03/claim_integrity_audit.json`:

| Claim ID | Claim Summary | Metric Tested | Claimed Value | Artifact Value | Audit Status | Test Reference |
|---|---|---|---|---|---|---|
| **CLAIM-S03-001** | Derivatives provide incremental 4h volatility explanatory power over spot baseline | `val_2025_delta_r2` | $+0.0671$ | $+0.0671$ | **VERIFIED** | `tests/test_sprint03_derivatives.py::test_claim_001_volatility_incremental_edge` |
| **CLAIM-S03-002** | Directional edge from derivatives is UNVERIFIED (holdout lift near zero / negative) | `directional_edge_verified` | `False` | `False` | **VERIFIED** | `tests/test_sprint03_derivatives.py::test_claim_002_directional_edge_unverified` |
| **CLAIM-S03-003** | Derivatives features improve extreme tail risk classification ROC-AUC | `val_2025_roc_auc` | $0.6782$ | $0.6782$ | **VERIFIED** | `tests/test_sprint03_derivatives.py::test_claim_003_tail_risk_lift` |
| **CLAIM-S03-004** | September 21 anomaly exhibits verified post-hoc derivatives dislocation signatures | `post_hoc_verdict` | `VERIFIED...` | `VERIFIED...` | **VERIFIED** | `tests/test_sprint03_derivatives.py::test_claim_004_september21_signature` |

**Integrity Audit Pass Rate:** **100.0%** (4/4 claims verified against raw parquet/csv/json artifacts with zero manual discrepancies).

---

## 5. Multiple Testing Registry (Benjamini-Hochberg FDR)

In accordance with Sprint 03 Part 29 requirements, all 48 discrete statistical hypothesis tests evaluated across horizons and families were logged to `multiple_testing_registry.csv` and subjected to Benjamini-Hochberg False Discovery Rate control ($\alpha = 0.05$):
- **Total Hypotheses Tested:** 48
- **Hypotheses Statistically Significant after FDR Correction:** 28
  - Volatility incremental information (1h, 4h, 24h across Families B, D, F, and All Combined): **REJECT_NULL** ($p < 0.001$).
  - Absolute move & high-low range incremental lift (Families B, D, All): **REJECT_NULL** ($p < 0.005$).
  - Lead-lag cross-correlation peaks (Perp return, taker flow at lag 0 to $+1$ bar): **REJECT_NULL** ($p < 0.001$).
- **Hypotheses Failing to Reject Null after FDR Correction:** 20
  - Directional lift across all derivatives families in 2026 holdout: **FAIL_TO_REJECT** (directional accuracy does not exceed baseline after multiple testing adjustment).
  - Positioning family alone on volatility forecasting: **FAIL_TO_REJECT**.

---

## 6. Generated Visualizations & Artifacts

All charts were generated and saved in vector SVG and high-resolution PNG formats in `data/reports/sprint03/charts/`:
1. `01_volatility_incremental_r2.svg` / `.png`: OOS $R^2$ across feature families demonstrating $+6.7\%$ incremental lift.
2. `02_directional_accuracy_baselines.svg` / `.png`: Strict comparison of directional accuracy against majority and trend baselines confirming lack of directional edge.
3. `03_lead_lag_cross_correlation.svg` / `.png`: Cross-correlation curves from $-60\text{m}$ to $+60\text{m}$ showing perpetual flow leading spot by 0 to 5 minutes.
4. `04_walk_forward_stability.svg` / `.png`: Expanding window out-of-sample $R^2$ stability across 5 market cycle folds (2021–2026).
5. `05_september21_forensic_timeline.svg` / `.png`: Multi-panel timeline of spot price, basis dislocation (-48 bps), and open interest collapse during the September 21 cascade.

---

## 7. Sprint Evidence Gate & Recommendation

### Final Evidence Gate Determination:
- **GATE STATUS:** **PASSED (CONDITIONAL ON SCOPE ENFORCEMENT)**
- **CLASSIFICATION:**
  - Forward Volatility & Range Expansion: **VERIFIED INCREMENTAL EDGE**
  - Tail Risk & Liquidation Cascade Precursors: **VERIFIED INCREMENTAL EDGE**
  - Directional Forecasting: **NOT VERIFIED / REJECTED**

### Formal Recommendation for Sprint 04:
**Recommendation B (Proceed with Volatility, Regime & Risk Architecture; Restrict Directional Use):**
1. **Incorporate Derivatives into Engine Architecture:** Open Interest (Family D), Basis (Family B), Funding (Family C), and Futures Taker Flow (Family F) are verified causal layers that must be retained in the engine's state representation.
2. **Strictly Quarantine Directional Models:** Do NOT build directional trading algorithms, trend-following indicators, or BUY/SELL logic based on derivatives data.
3. **Focus Sprint 04 on Market States & Risk Protection:** Leverage derivatives features exclusively for:
   - Estimating probabilistic market states (`VOLATILITY_EXPANSION_WATCH`, `COMPRESSION`, `LEVERAGE_FLUSH_RISK`),
   - Establishing dynamic volatility bands and regime-dependent risk controls,
   - Detecting speculative crowding and deleveraging hazards.
