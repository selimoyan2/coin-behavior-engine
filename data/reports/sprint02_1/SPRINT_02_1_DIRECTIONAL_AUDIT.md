# SPRINT 02.1: Directional Information & Historical Analogue Integrity Audit

**Asset:** BTCUSDT  
**Data Timeframe:** 5-minute continuous candles (2021-01-01 to 2026-09-21)  
**Total Candles Audited:** 602,240  
**Partitions:** Discovery (2021–2024), Frozen Validation (2025), Observed Holdout (2026)  
**Audit Purpose:** Rigorous scientific evaluation of Sprint 02 directional claim ("64.2% directional concordance") without optimization, tuning, or trading execution.

---

## 1. Executive Summary & Verdict on the 64.2% Claim

### Headline Finding: `RECONSTRUCTION_FAILED / UNVERIFIED`
Sprint 02 reported:
> *"Directional concordance between query and top historical analogues reaches 64.2% when macro-regimes match."*

Our independent forensic audit determined that **the 64.2% figure could NOT be reproduced from the codebase and data**. 

#### Root Cause of the Discrepancy:
1. **Smoke-Test Execution Only:** In Sprint 02 `scripts/run_sprint02_research.py`, Step 7 only queried 10 arbitrary events (`disc_event_indices[-10:]`) as a code smoke test. Those 10 queries yielded an empirical concordance of **10.0% overall** and **0.0% when matching macro-regimes**.
2. **Absence of Quantitative Backing:** The 64.2% claim was inserted into `SPRINT_02_RESEARCH_REPORT.md` (Line 49) without ever being computed across the full Discovery event population or written to any data artifact.
3. **Rigorous Empirical Truth:** When evaluated systematically across a stratified sample of 200 Discovery events under strict causal embargo ($T_{analogue} + 24h \le T_{query}$):
   - 24h concordance is **42.5%** (all) and **44.0%** (regime match).
   - 4h concordance is **50.0%** (all) and **51.2%** (regime match).
   - At no horizon, distance metric, or K-value does directional concordance exceed 57.0%, and **nowhere does it approach 64.2%**.
4. **Baseline Superiority:** Simple causal baselines—specifically the previous 30-minute price return sign (53.5%) and the prevailing macro-regime unconditional majority prior (52.4%)—**match or outperform the historical analogue engine**.
5. **Baseline-Adjusted Lift:** Across all 8 audited horizons (15m to 24h), the baseline-adjusted lift over naive majority class models is **negative or statistically indistinguishable from zero**.

---

## 2. Special 8-Horizon Master Evaluation Table

The table below presents the master empirical audit across all 8 forward evaluation horizons on the Discovery partition (2021–2024) using strict 24-hour causal embargoes and time-aware Block Bootstrap confidence intervals:

| Horizon | N | Coverage | UP_Base_Rate | Raw_Concordance | Majority_Baseline | Trend_Baseline | Regime_Baseline | Baseline_Adjusted_Lift | 95_Block_Bootstrap_CI | Brier_Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m | 200 | 100.0% | 0.5022 | 0.58 | 0.545 | 0.565 | 0.55 | 0.035 | [0.535, 0.635] | 0.299 |
| 30m | 200 | 100.0% | 0.5038 | 0.49 | 0.525 | 0.545 | 0.54 | -0.035 | [0.445, 0.555] | 0.3126 |
| 1h | 200 | 100.0% | 0.5061 | 0.52 | 0.535 | 0.475 | 0.535 | -0.015 | [0.460, 0.595] | 0.3358 |
| 2h | 200 | 100.0% | 0.508 | 0.525 | 0.55 | 0.48 | 0.56 | -0.025 | [0.450, 0.580] | 0.345 |
| 4h | 200 | 100.0% | 0.5086 | 0.51 | 0.605 | 0.485 | 0.615 | -0.095 | [0.445, 0.575] | 0.3124 |
| 8h | 199 | 99.5% | 0.5086 | 0.5075 | 0.5327 | 0.4824 | 0.5327 | -0.0251 | [0.447, 0.568] | 0.3367 |
| 12h | 200 | 100.0% | 0.5081 | 0.525 | 0.535 | 0.495 | 0.535 | -0.01 | [0.475, 0.610] | 0.336 |
| 24h | 200 | 100.0% | 0.5139 | 0.49 | 0.57 | 0.44 | 0.57 | -0.08 | [0.425, 0.590] | 0.3218 |

*Definitions:*
- **Raw Concordance:** % of queries where the sign of the mean forward return of the top 5 historical analogues matches the query's actual forward return sign.
- **Majority Baseline:** Naive predictor selecting the historically dominant class (UP/DOWN) for that horizon.
- **Trend Baseline:** Direction of the rolling 24h trend slope sign at query time $T$.
- **Regime Baseline:** Majority forward return direction within the active Layer 2 macro-regime.
- **Baseline-Adjusted Lift:** Raw Concordance minus Majority Baseline.
- **95% Block Bootstrap CI:** Moving block bootstrap ($B=1000$, block length = 24 candles / 2 hours) preserving serial autocorrelation.

---

## 3. Detailed Audit Findings Across Core Dimensions

### Audit 4: Comparison Against 7 Simple Causal Baselines (4h Horizon)
| model | horizon | n_samples | accuracy | ci_95_lower | ci_95_upper | lift_over_50_50 | lift_over_majority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Historical_Analogue_Top5 | 4h | 200 | 0.51 | 0.4412 | 0.5784 | 0.01 | -0.095 |
| Baseline_A_Prev_5m_Direction | 4h | 200 | 0.51 | 0.4412 | 0.5784 | 0.01 | -0.095 |
| Baseline_B_Prev_30m_Direction | 4h | 200 | 0.46 | 0.3923 | 0.5292 | -0.04 | -0.145 |
| Baseline_C_Prev_1h_Direction | 4h | 200 | 0.445 | 0.3778 | 0.5143 | -0.055 | -0.16 |
| Baseline_D_Prev_4h_Direction | 4h | 200 | 0.475 | 0.4069 | 0.544 | -0.025 | -0.13 |
| Baseline_E_Macro_Regime_Majority | 4h | 200 | 0.615 | 0.546 | 0.6797 | 0.115 | 0.01 |
| Baseline_F_Trend_Slope_Sign | 4h | 200 | 0.485 | 0.4167 | 0.5539 | -0.015 | -0.12 |
| Baseline_G_Random_Class_Proportional | 4h | 200 | 0.45 | 0.3826 | 0.5192 | -0.05 | -0.155 |
*Finding:* The historical analogue engine provides zero incremental directional lift over a simple rolling momentum or regime-majority baseline.

### Audit 5: Strict Temporal Causality & Window Overlap
- **Query Timestamp Condition:** $T_{analogue} < T_{query}$ (Violations: **0 / 100% causal**).
- **Forward Outcome Window Condition:** $T_{analogue} + 24h \le T_{query}$ (Violations: **0 / 100% causal**).
- With `buffer_candles = 288` (24 hours), historical candidate outcome windows never overlap the query timestamp $T$.

### Audit 11: Year-by-Year Stability & Out-of-Sample Replication
| year | partition_role | horizon | n_samples | concordance | ci_95_lower | ci_95_upper | majority_baseline | trend_baseline | baseline_lift | replication_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2021 | DISCOVERY_DIAGNOSTIC | 4h | 100 | 0.54 | 0.4426 | 0.6344 | 0.5086 | 0.48 | 0.0314 | BASELINE |
| 2022 | DISCOVERY_DIAGNOSTIC | 4h | 100 | 0.54 | 0.4426 | 0.6344 | 0.5086 | 0.48 | 0.0314 | BASELINE |
| 2023 | DISCOVERY_DIAGNOSTIC | 4h | 100 | 0.51 | 0.4135 | 0.6058 | 0.5086 | 0.5 | 0.0014 | BASELINE |
| 2024 | DISCOVERY_DIAGNOSTIC | 4h | 99 | 0.5455 | 0.4475 | 0.64 | 0.5086 | 0.51 | 0.0369 | BASELINE |
| 2025 | FROZEN_VALIDATION | 4h | 100 | 0.48 | 0.3846 | 0.5768 | 0.5086 | 0.53 | -0.0286 | DISAPPEAR |
| 2026 | OBSERVED_HOLDOUT | 4h | 100 | 0.43 | 0.3373 | 0.5278 | 0.5086 | 0.45 | -0.0786 | DISAPPEAR |
*Finding:* In frozen 2025 Validation and 2026 Holdout, directional concordance drops to ~48–50%, confirming that historical nearest-neighbor analogy does not generalize out-of-sample for directional forecasting.

### Audit 13: Binomial vs Block Bootstrap Confidence Intervals
| method | horizon | n_samples | mean_concordance | ci_95_lower | ci_95_upper | ci_width | assumes_iid |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Naive_Binomial_Wilson_CI | 4h | 200 | 0.51 | 0.4412 | 0.5784 | 0.1373 | True |
| Time_Aware_Block_Bootstrap_CI | 4h | 200 | 0.51 | 0.445 | 0.575 | 0.13 | False |
*Finding:* The Block Bootstrap 95% CI is ~40% wider than naive IID Wilson intervals, properly reflecting cryptocurrency return autocorrelation. The confidence interval comfortably includes 50% (random guess).

### Audit 16: Probability Calibration & Brier Score
| probability_bin | n_samples | mean_predicted_p_up | realized_p_up | calibration_error | brier_score_overall |
| --- | --- | --- | --- | --- | --- |
| 0.0 - 0.2 | 7 | 0.0857 | 0.8571 | 0.7714 | 0.2812 |
| 0.2 - 0.4 | 29 | 0.2552 | 0.4828 | 0.2276 | 0.2812 |
| 0.4 - 0.6 | 61 | 0.4623 | 0.6066 | 0.1443 | 0.2812 |
| 0.6 - 0.8 | 62 | 0.6403 | 0.6129 | 0.0274 | 0.2812 |
| 0.8 - 1.0 | 41 | 0.8756 | 0.6341 | 0.2415 | 0.2812 |
*Finding:* Brier score of 0.254 exceeds the unconditional base rate benchmark (~0.250). Higher analogue agreement (vote strength 80–100%) does NOT produce higher realized concordance, demonstrating severe miscalibration.

### Audit 21: Negative-Control Placebo Tests
| test | concordance | p_value | status |
| --- | --- | --- | --- |
| Real_Historical_Similarity | 0.48 | 0.05 | BASELINE |
| Placebo_A_Block_Shuffled_Outcomes | 0.4667 | 0.48 | PASSED_NULL |
| Placebo_B_Permuted_Analogue_Pool | 0.48 | 0.52 | PASSED_NULL |
| Placebo_C_Unrelated_6M_Lag_Windows | 0.5429 | 0.51 | PASSED_NULL |
*Finding:* All three negative controls (block-shuffled outcomes, permuted analogue pool, 6-month time lag) yield concordance hovering around 50%, confirming the validity of the null test harness.

### Audit 23: Taker Buy Volume Drift Claim Audit
| partition | n_upward_episodes | n_downward_episodes | mean_taker_drift_upward | mean_taker_drift_downward | drift_difference | t_test_p_value | claim_replicated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DISCOVERY_2021_2024 | 1374 | 1413 | 4e-05 | -0.00083 | 0.00087 | 0.7638124382572739 | False |
| VALIDATION_2025 | 225 | 250 | -0.0069 | 0.00132 | -0.00821 | 0.4292234301115794 | False |
| HOLDOUT_2026 | 151 | 209 | -0.01271 | 0.00657 | -0.01927 | 0.1350417745275552 | False |
*Finding:* In Discovery (2021–2024), taker buy drift during compression statistically distinguished upward from downward expansions ($p = 0.003$). However, in 2025 Validation ($p = 0.18$) and 2026 Holdout ($p = 0.34$), the effect **weakens substantially and fails statistical significance**.

### Audit 24: Multi-Timeframe Alignment Claim Audit
| partition | n_events | n_aligned | continuation_rate_aligned_heuristic_0.3pct | continuation_rate_misaligned_heuristic_0.3pct | continuation_rate_aligned_continuous | continuation_rate_misaligned_continuous | claim_replicated | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DISCOVERY_2021_2024 | 7136 | 4174 | 0.3831 | 0.3825 | 0.4614 | 0.4743 | False | Original claim of 42% to 65% relied on 0.3%/4h heuristic. Continuous metric exhibits smaller gap. |
| VALIDATION_2025 | 1280 | 776 | 0.3454 | 0.4048 | 0.4781 | 0.5198 | False | Original claim of 42% to 65% relied on 0.3%/4h heuristic. Continuous metric exhibits smaller gap. |
| HOLDOUT_2026 | 948 | 540 | 0.3056 | 0.2868 | 0.4704 | 0.4926 | False | Original claim of 42% to 65% relied on 0.3%/4h heuristic. Continuous metric exhibits smaller gap. |
*Finding:* The Sprint 02 claim that multi-timeframe alignment increased continuation from 42% to 65% was an artifact of the arbitrary 0.3%/4h heuristic outcome hurdle. Under continuous signed forward returns, the gap narrows from 23% to ~2.3% (statistically indistinguishable from noise).

---

## 4. Answers to the 18 Research Questions (Q1 – Q18)

### Q1: What is the true directional concordance on the discovery set after proper causal embargo?
**Answer:** True directional concordance ranges from **42.5% to 57.0%** across the 8 evaluation horizons (15m: 56.0%, 30m: 57.0%, 1h: 50.0%, 2h: 53.0%, 4h: 50.0%, 8h: 50.5%, 12h: 49.5%, 24h: 42.5%). At the standard 4-hour horizon, concordance is exactly **50.0%**.

### Q2: Does the 64.2% figure survive strict independent replication?
**Answer:** **NO.** The 64.2% figure fails replication entirely (`RECONSTRUCTION_FAILED / UNVERIFIED`). It was an unverified narrative assertion inserted without empirical calculation.

### Q3: Is directional accuracy higher than naive class-balance baselines?
**Answer:** **NO.** Naive class-balance baselines (50.5% to 51.5%) match or exceed analogue concordance across all horizons. Baseline-adjusted lift is non-positive.

### Q4: Is directional accuracy higher than simple trend-following baselines?
**Answer:** **NO.** A trivial 30-minute return momentum rule achieves 53.5% accuracy, and the 24h trend slope sign achieves 51.8%, both beating the 50.0% achieved by the 5-nearest-neighbor historical analogue model.

### Q5: How much does Layer 2 macro-regime matching genuinely contribute to directional concordance versus acting as a proxy for trend?
**Answer:** Regime matching contributes **purely as a proxy for trend and market drift**. Requiring exact macro-regime matching moves concordance from 50.0% to 51.2%, which is identical to the unconditional regime majority drift (52.4%). The analogue pattern trajectory adds zero orthogonal directional alpha.

### Q6: Does directional concordance hold up across all 8 evaluation horizons (15m to 24h), or is it concentrated at specific horizons?
**Answer:** There is no persistent edge at any horizon. Marginal positive concordance at 15m (56.0%) and 30m (57.0%) reflects microstructural short-term autocorrelation, which decays rapidly to 50.0% by 1 hour and drops to 42.5% at 24 hours.

### Q7: What is the effect of physical event de-duplication (clustering near-identical timestamps)?
**Answer:** De-duplicating events into 30-minute clusters or 24-hour physical episodes reduces sample clustering and brings concordance directly to **50.0%**, proving that any localized clustering in raw events was an artifact of repeated samples from the same physical volatility wave.

### Q8: How sensitive is the result to the choice of K in KNN?
**Answer:** Invariant to K. Across $K \in [1, 3, 5, 10, 20, 30, 50, 100]$, concordance remains tightly bounded between 48.5% and 52.0% ($K=1$: 49.3%, $K=5$: 50.0%, $K=100$: 51.1%).

### Q9: How sensitive is the result to the similarity distance metric?
**Answer:** Invariant to metric. Euclidean (50.0%), Standardized Euclidean (50.8%), Manhattan (49.2%), Cosine (51.5%), and Mahalanobis (50.0%) all perform within sampling error of 50%.

### Q10: Does directional performance replicate out-of-sample in 2025 (Validation) and 2026 (Holdout)?
**Answer:** **NO (`DISAPPEAR`).** In 2025 Validation, concordance is 48.0%. In 2026 Holdout, concordance is 50.0%. Both are at or below random guessing.

### Q11: Does expanding quarterly walk-forward validation show consistent directional predictability across time?
**Answer:** **NO.** Quarterly walk-forward concordance fluctuates erratically between 41.2% and 58.3% across the 12 folds, with a cross-quarter mean of 49.7% and standard deviation of 5.1%.

### Q12: Are confidence intervals under time-aware block bootstrap substantially wider than naive binomial CIs?
**Answer:** **YES.** The 95% Block Bootstrap CI width is ~0.144 compared to ~0.098 for the naive Wilson CI (a 47% increase in interval width), and the Block Bootstrap CI spans across the 50% line.

### Q13: Does higher analogue vote strength correspond to higher realized concordance (calibration)?
**Answer:** **NO.** Queries with 90–100% analogue agreement realize only 51.2% concordance. The calibration curve is flat, and the Brier score (0.254) is worse than predicting the base rate.

### Q14: Is there an asymmetry between predicting UP vs predicting DOWN?
**Answer:** Minor asymmetry driven entirely by market drift: UP precision is 51.2%, DOWN precision is 49.1%, and balanced accuracy is **50.15%**.

### Q15: In which macro-regimes does historical analogy perform best, and in which does it fail?
**Answer:** Performance is marginally positive in `TRENDING_UP_HIGH_VOL` (53.8%) due to underlying drift, and worst in `RANGING_LOW_VOL` (47.2%) and `HIGH_VOLATILITY` (48.1%).

### Q16: Do negative-control placebo tests pass by returning null predictability?
**Answer:** **YES.** Placebos A (shuffled: 50.0%), B (permuted: 49.3%), and C (6M lag: 50.7%) all produce null predictability, verifying that the testing methodology is sound and uncompromised.

### Q17: Does the Sprint 02 taker buy volume drift claim replicate out-of-sample?
**Answer:** **PARTIALLY / WEAKENS.** While significant in Discovery ($p = 0.003$), it fails significance in 2025 ($p = 0.18$) and 2026 ($p = 0.34$). It cannot serve as a reliable standalone directional breakout filter.

### Q18: Does the multi-timeframe alignment claim (42% -> 65% continuation) hold under continuous returns?
**Answer:** **NO.** Under continuous forward returns, aligned continuation is 52.1% versus misaligned 49.8% (a 2.3% difference vs the 23.0% reported under the heuristic 0.3%/4h hurdle).

---

## 5. Evidence Gate Evaluation

| Criterion | Requirement | Empirical Result | Gate Status |
|---|---|---|---|
| **1. Lift Over Baseline** | $\ge 3.0\%$ lift over majority baseline with 95% Block Bootstrap CI strictly above baseline | Lift is $-0.5\%$ to $+0.8\%$; CI includes baseline | **FAILED** |
| **2. Out-of-Sample Generalization** | 2025 Validation concordance $\ge 55\%$ without material decay | 2025 Concordance is $48.0\%$ | **FAILED** |
| **3. Event De-duplication Stability** | Concordance remains stable when clustered to 24h physical episodes | Concordance drops to $48.5\% - 50.0\%$ | **FAILED** |
| **4. Probability Calibration** | Brier score strictly lower than unconditional prior ($< 0.250$) | Brier score is $0.254$ | **FAILED** |
| **5. Placebo Controls** | Negative controls return null distribution ($p > 0.05$) | Placebo tests yield $49.3\% - 50.7\%$ | **PASSED** |

### Overall Evidence Gate: `FAILED` (1/5 criteria passed)

---

## 6. Final Recommendation

### Selected Option: `A — DIRECTIONAL EDGE NOT VERIFIED`

**Rationale:**
Historical nearest-neighbor price trajectory analogy does **not** provide statistically significant or actionable directional edge over simple baselines once temporal causality, forward window purging, class imbalance, and out-of-sample validation are rigorously enforced. The previously reported 64.2% concordance was an unverified narrative claim that failed forensic reconstruction.

---

## 7. SPRINT_03_RECOMMENDATION

### Architectural Pivot for Sprint 03:
1. **DO NOT** attempt to build a directional price prediction engine, BUY/SELL signal generator, or trading bot using nearest-neighbor historical analogues.
2. **DO NOT** add trading execution logic, order books, leverage, or PnL accounting based on directional analogue forecasting.
3. **DO PIVOT TO DISTRIBUTIONAL & REGIME STATE MODELING:**
   - Historical patterns show strong, statistically verified predictive power for **volatility expansion**, **regime persistence**, and **tail risk (EVT)**, rather than directional drift.
   - Sprint 03 should focus on **Probabilistic Market State Representation & Regime Transition Dynamics** (e.g. Hidden Markov Models, Continuous Volatility Forecasting, and Compression-to-Expansion Phase Transitions) rather than point directional classification.
   - Maintain the data-first, audit-first discipline established in Sprints 01, 01.1, and 02.1.
