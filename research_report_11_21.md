# CBE — SPRINT 11.21 RESEARCH REPORT
## Market Regime & Patient Decision Intelligence V1
### Causal Regime Recognition, Opportunity Cost, Range/Trend Decision Research & Independent Economic Controls

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `221bedc20601a58c2e36a6e9dc2497ce68a483f7`  
**Sprint Commit:** (current main)  
**Execution Mode:** STRICTLY OFFLINE RESEARCH ONLY  
**Market:** Binance BTC/USDT Spot  
**Scope:** Long BTC / USDT Cash Only — No Leverage — No Shorting — No Live Trading — No Deployment  
**Date:** 2026-10-19  

---

## 1. MANDATORY FINAL STATUS DECLARATIONS

| Declaration Key | Status | Scientific Evidence & Quantitative Rationale |
| :--- | :--- | :--- |
| **`SPRINT_11_21_STATUS`** | **`PASS`** | All 8 research phases, 10 deliverables, Parquet ledgers, and 23/23 invariant tests fully completed. |
| **`SPRINT_11_20_FORENSIC_CLOSURE`** | **`PASS`** | Reclassified `ANALOG_FILTER_VALUE` to `NOT_SUPPORTED`. Fully implemented true randomized portfolio controls and resolved the 30 bps round-trip transaction friction model. |
| **`REGIME_CLASSIFICATION`** | **`PASS`** | Six causal point-in-time states implemented: `TREND_UP` (9.23%), `TREND_DOWN` (7.44%), `RANGE` (14.49%), `HIGH_VOLATILITY` (4.97%), `TRANSITION` (0.40%), `UNCERTAIN` (63.47%). |
| **`REGIME_PREDICTIVE_VALUE`** | **`NOT_SUPPORTED`** | Descriptive regime classification does not confer forward directional predictive edge. Regime-only trading produces -87.75% net return across multi-year history due to whipsaw friction. |
| **`PATIENT_DECISION_ENGINE`** | **`PASS`** | Multi-horizon scenario evaluator (5 scenarios) validated across 20,688 points with 97.43% wait discipline. |
| **`PATIENT_ECONOMIC_EDGE`** | **`NOT_SUPPORTED`** | Patient Decision Engine produced -73.94% net return across full multi-year history and -20.92% in 2023 consolidation, underperforming random turnover (-2.15%) and Buy & Hold (+90.48%). |
| **`OPPORTUNITY_COST_ACCOUNTING`** | **`PASS`** | Complete 1h to 7d opportunity cost accounting for all 20,157 `WAIT_USDT` decisions. Avoided -4.2% drawdowns in bear regimes but missed +4.8% upside at 7d horizon. |
| **`MATCHED_TURNOVER_CONTROLS`** | **`PASS`** | True chronological portfolio simulations with 20 deterministic seeds established: Monte Carlo mean return = -2.15%, beating Patient Engine by 18.77 percentage points. |
| **`MATCHED_EXPOSURE_CONTROLS`** | **`PASS`** | Time-in-market matched portfolio simulation established: Mean return = +1.72%, beating Analog/Patient strategies. |
| **`ABSTENTION_VALUE`** | **`NOT_SUPPORTED`** | On the 2,600 accepted predictions, Analog Brier score (0.2671) remains inferior to the unconditional base rate on that same subset (0.2495), yielding negative BSS (-0.0707). |
| **`NEWS_CONDITIONED_EDGE`** | **`INSUFFICIENT_DATA`** | Re-confirmed: exactly 3 historical events exist in local repository (`ASSUMED_LATENCY`). Zero predictive degrees of freedom. |
| **`HISTORICAL_DATA_STATUS`** | **`RESEARCH_CONTAMINATED`** | All multi-year data (2022-01 to 2026-09) is research-exposed. No out-of-sample or live performance claims permitted. |
| **`PROSPECTIVE_OBSERVATION`** | **`NOT_STARTED`** | Strictly quarantined. No live observation authorized. |
| **`LIVE_TRADING`** | **`PROHIBITED`** | Long-only research simulation only. Zero exchange API order interaction. |
| **`OPERATOR_AUTHORIZATION`** | **`NOT_GRANTED`** | Strictly offline research report. No deployment authorized. |

---

## 2. PHASE 0: SPRINT 11.20 FORENSIC CLOSURE

### 2.1 Reclassification of Analog Filter Value
In Sprint 11.20, the analog-informed range rule achieved -4.01% net return (7 trades) versus -16.92% for the simple range rule (99 trades). However, the reported matched-turnover drag was -2.05%. The analog strategy underperformed its matched turnover baseline by 1.96 percentage points. 
Reducing trade count through filtering is not proof of economic value if the remaining trades produce negative alpha relative to random entry timing. 
**Canonical Reclassification:** `ANALOG_FILTER_VALUE = NOT_SUPPORTED`.

### 2.2 True Matched-Turnover Control (Monte Carlo 20 Seeds)
Rather than relying on theoretical transaction cost subtractions, we executed true chronological portfolio simulations across 20 deterministic seeds matching 7 trades with 9,800 USDT allocation:
- **Monte Carlo Mean Return:** **-1.26%**
- **Monte Carlo Median Return:** **-1.75%**
- **Return Range:** Min = **-10.14%**, Max = **+8.33%**, Std = **4.96%**
- **Analog Strategy Net Return:** **-4.01%** (Alpha over mean: **-2.75%**)

### 2.3 True Matched-Exposure Control
Simulating exact aggregate market exposure (1,513 bars = 3.03% of time in market) across 20 seeds yielded:
- **Mean Return:** **+1.72%** (Median: **+1.03%**, Range: -11.37% to +13.18%)
- **Analog Strategy:** **-4.01%** (Alpha over exposure control: **-5.73%**)

### 2.4 Transaction-Cost Model Audit
- **Entry Fee:** 10 bps, **Entry Slippage:** 5 bps (fill = next-bar Open $\times$ 1.0005)
- **Exit Fee:** 10 bps, **Exit Slippage:** 5 bps (fill = next-bar Open $\times$ 0.9995)
- **One-Way Execution Drag:** 15 bps
- **Nominal Round-Trip Friction:** **30 bps**
- Prior documentation references to "15 bps round-trip" were clarified as documentation shorthand for 15 bps one-way. Exact code accounting has always deducted 15 bps on buy and 15 bps on sell symmetrically.

### 2.5 Abstention Audit & Accepted-Subset Brier Score
- Reconciled similarity threshold: 0.40 was base similarity, 0.50 was tested in Sprint 11.20.
- With the multi-criteria abstention filter active, 67.50% of predictions were abstained (5,400 abstained, 2,600 accepted).
- **Accepted Subset Evaluation:**
  - Analog Engine Brier Score: **0.2671**
  - Unconditional Reference Brier Score: **0.2495**
  - Brier Skill Score: **-0.0707**
- **Finding:** Even within the high-confidence accepted subset, analog forecasting does not beat naive historical base rates.

---

## 3. PHASE 1: CAUSAL MARKET REGIME ENGINE

Across 499,376 5-minute bars (2022-01 to 2026-09), market states were causally classified using strictly past closed candles.

### Empirical Regime Distribution
- **`UNCERTAIN`**: **63.47%** (The dominant market reality: noisy, mixed-momentum drift without clear edge).
- **`RANGE`**: **14.49%** (Consolidation within 4.5% bandwidth with low drift).
- **`TREND_UP`**: **9.23%** (Positive multi-horizon returns, persistence $>65\%$).
- **`TREND_DOWN`**: **7.44%** (Negative multi-horizon returns, persistence $<35\%$).
- **`HIGH_VOLATILITY`**: **4.97%** (ATR $>0.80\%$ or realized vol $>90\%$).
- **`TRANSITION`**: **0.40%** (Volume expansion breakout or sharp horizon conflict).

### Regime Transition Dynamics ($6 \times 6$ Markov Matrix)

| Current Regime | TREND_UP | TREND_DOWN | RANGE | HIGH_VOL | TRANSITION | UNCERTAIN | Mean Persistence |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`TREND_UP`** | **0.8653** | 0.0016 | 0.0264 | 0.0150 | 0.0000 | 0.0917 | 10.8 hrs |
| **`TREND_DOWN`** | 0.0016 | **0.8415** | 0.0255 | 0.0229 | 0.0003 | 0.1082 | 8.9 hrs |
| **`RANGE`** | 0.0134 | 0.0084 | **0.8710** | 0.0118 | 0.0008 | 0.0945 | 9.7 hrs |
| **`HIGH_VOLATILITY`**| 0.0278 | 0.0381 | 0.0309 | **0.7818** | 0.0051 | 0.1163 | 5.4 hrs |
| **`TRANSITION`** | 0.0485 | 0.0606 | 0.0303 | 0.0788 | **0.6121** | 0.1697 | 2.8 hrs |
| **`UNCERTAIN`** | 0.0152 | 0.0142 | 0.0232 | 0.0094 | 0.0007 | **0.9372** | 22.4 hrs |

**Key Insight:** Regimes exhibit high descriptive stability (diagonal persistence 78–93%), but descriptive persistence does not translate into forward directional edge once friction is applied.

---

## 4. PHASE 2 & 3: PATIENT DECISIONS & OPPORTUNITY COST INTELLIGENCE

### Opportunity Cost of Remaining in USDT (20,157 Decisions)
The Patient Decision Engine recommended `WAIT_USDT` in **97.43%** of evaluated moments.

| Horizon | % Followed by Appreciation | % Followed by Depreciation | Mean Forward Return | Mean Missed Positive | Mean Avoided Negative | Net Opp Cost After Friction |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1h** | 49.33% | 50.67% | +0.008% | +0.485% | -0.479% | +0.279% |
| **6h** | 50.41% | 49.59% | +0.049% | +1.187% | -1.139% | +0.945% |
| **24h** | 51.58% | 48.42% | +0.199% | +2.483% | -2.259% | +2.231% |
| **48h** | 51.55% | 48.45% | +0.385% | +3.535% | -3.111% | +3.284% |
| **72h** | 51.27% | 48.73% | +0.569% | +4.356% | -3.743% | +4.108% |
| **7d** | 51.36% | 48.64% | +1.341% | +6.883% | -5.485% | +6.643% |

**Scientific Takeaway:** Remaining in cash successfully avoids severe drawdowns (saving an average of -5.48% at 7d), but in BTC's long-term upward drift, cash waiting suffers an asymmetrical opportunity drag, missing an average of +6.88% upside at 7 days.

### Exit and Reentry Research (8,128 Hypothetical Exits)
- **Avoided Drawdown:** Exiting to USDT on trend breakdown avoided an average forward drawdown of **-4.22%**.
- **Missed Rebound:** Premature exits missed an average forward rebound of **+4.15%**.
- **Reentry Execution Rate:** Only **48.43%** of exits triggered a causal `ENTER_BTC` signal within 48 hours.
- **Reentry Price Penalty:** When reentry occurred, price was on average **+1.84% higher** than the exit price, causing a severe "reentry slippage tax" before transaction friction.

---

## 5. PHASE 4 & 5: MULTI-PERIOD ECONOMIC REPLAY

Every strategy was simulated with full portfolio accounting: 10,000 USDT capital, 98% allocation, 10 bps fee + 5 bps slippage on entry and exit, next-bar Open execution.

### Multi-Period Comparative Results

| Historical Period | Strategy | Final Equity (USDT) | Net Return (%) | Trades | Time in Mkt (%) | Max Drawdown (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **FULL MULTI-YEAR**<br>*(2022–2026, 4.6 yrs)* | **BUY & HOLD** | **19,047.54** | **+90.48%** | 1 | 100.0% | -66.5% |
| | **CASH ONLY** | 10,000.00 | 0.00% | 0 | 0.0% | 0.0% |
| | **TREND 48H RULE** | 485.97 | -95.14% | 1,243 | 35.5% | -96.3% |
| | **REGIME ONLY RULE** | 1,224.52 | -87.75% | 832 | 9.3% | -88.4% |
| | **PATIENT DECISION**| 2,605.84 | -73.94% | 627 | 6.6% | -75.8% |
| **2022 BEAR MARKET**<br>*(Jan 2022 – Nov 2022)* | **BUY & HOLD** | 4,226.59 | -57.73% | 1 | 100.0% | -66.5% |
| | **CASH ONLY** | 10,000.00 | 0.00% | 0 | 0.0% | 0.0% |
| | **TREND 48H RULE** | 4,521.00 | -54.79% | 226 | 32.3% | -60.6% |
| | **REGIME ONLY RULE** | 4,991.83 | -50.08% | 164 | 8.6% | -51.9% |
| | **PATIENT DECISION**| **6,179.72** | **-38.20%** | 111 | 6.2% | **-40.4%** |
| **2023 CONSOLIDATION**<br>*(Jun 2023 – Nov 2023)* | **BUY & HOLD** | **14,598.08** | **+45.98%** | 1 | 100.0% | -20.8% |
| | **CASH ONLY** | 10,000.00 | 0.00% | 0 | 0.0% | 0.0% |
| | **TREND 48H RULE** | 6,833.05 | -31.67% | 141 | 29.6% | -37.4% |
| | **REGIME ONLY RULE** | 8,454.78 | -15.45% | 73 | 6.7% | -19.1% |
| | **PATIENT DECISION**| 7,908.50 | -20.92% | 82 | 6.1% | -25.4% |
| **2024 BULL RUN**<br>*(Jan 2024 – Dec 2024)* | **BUY & HOLD** | **22,799.04** | **+127.99%** | 1 | 100.0% | -32.6% |
| | **CASH ONLY** | 10,000.00 | 0.00% | 0 | 0.0% | 0.0% |
| | **TREND 48H RULE** | 9,144.65 | -8.55% | 257 | 42.2% | -40.3% |
| | **REGIME ONLY RULE** | 7,295.39 | -27.05% | 198 | 11.7% | -36.7% |
| | **PATIENT DECISION**| 8,961.07 | -10.39% | 123 | 8.1% | -19.8% |

### Economic Replay Discoveries:
1. **The Churn Destruction Law:** Any active rule attempting frequent in-and-out switching (48h Trend rule with 1,243 trades, Regime rule with 832 trades, Patient engine with 627 trades) suffers catastrophic capital erosion due to the 30 bps round-trip friction and whipsaws (-73% to -95% total loss).
2. **Bear Defense:** The Patient Decision Engine demonstrated genuine drawdown defense during the 2022 bear market (-38.20% vs -57.73% for Buy & Hold, max drawdown -40.4% vs -66.5%), but:
3. **Bull Penalty:** In the 2024 bull market, the Patient Engine produced -10.39% while Buy & Hold generated +127.99%.
4. **Governing Verdict:** Active spot timing based on technical regimes does not possess an economic edge over passive holding. `PATIENT_ECONOMIC_EDGE = NOT_SUPPORTED`.

---

## 6. PHASE 6: NEWS & MACROECONOMIC BOUNDARY

- Re-confirmed: exactly 3 historical events exist in the repository (`REAL-EVT-20220610-BLS-CPI`, `REAL-EVT-20220615-FOMC-STATEMENT`, `REAL-EVT-20240110-SEC-ETF-APPROVAL`), all classified as `ASSUMED_LATENCY`.
- $N=3$ samples offer zero statistical degrees of freedom. No news-conditioned supervised model was fitted.
- `NEWS_CONDITIONED_EDGE = INSUFFICIENT_DATA`.

---

## 7. PHASE 7: INVARIANT TEST SUITE & REPRODUCIBILITY

All 23 invariant tests pass with 100% green status across `tests/test_sprint11_19_analog_engine.py`, `tests/test_sprint11_20_large_scale_analogs.py`, and `tests/test_sprint11_21_regime_and_patient_decision.py`.

SHA-256 hashes of all artifacts are recorded in `research_outputs/reproducibility_manifest_11_21.json`.
