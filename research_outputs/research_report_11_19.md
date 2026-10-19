# CBE — SPRINT 11.19 RESEARCH REPORT
## Historical Analog Learning Engine V1: Causal Market Memory, Multi-Horizon Probabilistic Forecasting & Range Intelligence

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** [`bad8e7f27fa9a993b3b060402d54ef1cfab74a19`](https://github.com/selimoyan2/coin-behavior-engine/commit/bad8e7f27fa9a993b3b060402d54ef1cfab74a19)  
**Execution Mode:** STRICTLY OFFLINE RESEARCH ONLY  
**Market:** Binance BTC/USDT Spot  
**Scope:** NO LIVE TRADING — NO DEPLOYMENT — NO PROSPECTIVE ACTIVATION — NO OPTIMIZATION TO CLAIM PROFITS  
**Author:** CBE Autonomous Architecture & Research Engine  
**Date:** 2026-10-19  

---

## 1. Executive Summary & Scientific Purpose

Sprint 11.19 establishes the first scientifically testable implementation of the **Historical Analog Learning Engine V1** for the Coin Behavior Engine (CBE).

Prior to model exploration, the sprint resolves critical scientific integrity prerequisites:
1. **Forensic Reconciliation of Cross-Dataset Discrepancies:** Fully untangles the apparent conflict between the reported 0 USDT difference and the JSON 75.26 USDT price / 23.73 BTC volume discrepancy in `btcusdt_5m_raw.parquet`.
2. **Historical Contamination Register:** Formally rejects labeling 2026-01 to 2026-09 as "virgin out-of-sample", classifying all 57 months (2022–2026) as `RESEARCH_CONTAMINATED`.
3. **Event Provenance Downgrade:** Re-audits all three historical event records, downgrading their tier to `ASSUMED_LATENCY` due to the absence of independent node-level packet capture logs.
4. **Causal Pattern Similarity & Isolation:** Enforces strict forward outcome quarantine ($t_{cand} + 2016\text{ bars} \le T_0$) and temporal spacing (24h minimum separation) to prevent neighbor clustering.
5. **Multi-Horizon Probabilistic Forecasting:** Measures statistical skill against 5 baseline benchmarks using Brier score and pinball loss.
6. **Range Intelligence Evaluator:** Evaluates channel dynamics (specifically the 65,000–65,700 USDT channel) and proves why automatic buy/sell assumptions at boundaries lack an edge.

---

## 2. Phase 0 — Mandatory Scientific Closure

### 2.1. Cross-Dataset Discrepancy Forensic Resolution
In Sprint 11.18.2, a narrative summary reported "0.000000 USDT discrepancy" across datasets, while the actual JSON deliverable recorded a maximum price difference of 75.26 USDT and volume difference of 23.7321 BTC in `btcusdt_5m_raw.parquet`.

A deep candle-by-candle forensic audit across all **497,317 overlapping bars** revealed:
- **Total Identical Bars:** 497,309 bars (**99.9984% bitwise concordance**).
- **Total Mismatched Bars:** Exactly 8 candles.
- **Root Cause of the 75.26 USDT Price Difference:**
  The discrepancy occurred exclusively at `2026-09-23 20:20:00 UTC`, which was the **very last bar** of `btcusdt_5m_raw.parquet`. The file was dumped during live capture when only the first minute (20:20 UTC) of that 5-minute candle had elapsed. The completed official Binance Vision monthly archive contains the full 5-minute aggregation (20:20 to 20:25 UTC), during which price declined from 84,360.00 to 84,284.74 USDT and added 23.73 BTC of trading volume.
- **Root Cause of the 7 Minor 2022 Mismatches:**
  1 bar had a 0.01 USDT rounding difference (40,187.90 vs 40,187.89 on 2022-04-13 05:55 UTC), and 6 bars had minor volume differences (0.02 to 9.05 BTC) due to real-time REST API kline trade aggregation boundaries versus Binance Vision offline reconstructed trade ledgers.
- **Scientific Resolution & Quarantine:**
  `btcusdt_5m_raw.parquet` is NOT bitwise identical across all fields. The incomplete forming bar at `2026-09-23 20:20:00 UTC` is formally quarantined and excluded from research. The authoritative dataset for all multi-year research is designated as `data/binance_spot_multiyear/` (Vision archives).

### 2.2. Historical Contamination Governance
The entire multi-year dataset (2022-01 to 2026-09) is historical data.
- **Correction:** The designation of `2026-01 to 2026-09` as "virgin, prospective, or independent out-of-sample" in Sprint 11.18.2 is formally repudiated.
- **Classification:** All 57 months are recorded in [`contamination_register_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/contamination_register_11_19.json) as `RESEARCH_CONTAMINATED`.
- **Standard:** Chronological walk-forward evaluation is used, but all findings are explicitly documented as historical research evidence. True prospective validation is reserved strictly for live data generated after research rules are permanently locked.

### 2.3. Event Provenance Downgrade
- The three cataloged events (`REAL-EVT-20220610-BLS-CPI`, `REAL-EVT-20220615-FOMC-STATEMENT`, `REAL-EVT-20240110-SEC-ETF-APPROVAL`) possess statutory scheduled release timestamps.
- However, their intraday dissemination latency intervals ($[15\text{s}, 120\text{s}]$, $[10\text{s}, 90\text{s}]$, $[60\text{s}, 420\text{s}]$) represent empirical engineering bounds rather than primary node-level packet capture receipts.
- **Action:** All 3 events are formally downgraded to **`ASSUMED_LATENCY`**, and the overall status is recorded as **`EVENT_PROVENANCE = ASSUMED`**. Conservative visibility rules (withholding during assumed dissemination intervals) are strictly maintained.

---

## 3. Phase 1 — Causal Market Memory Feature Store

Implemented in [`src/coin_behavior_engine/analogs/feature_store.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/src/coin_behavior_engine/analogs/feature_store.py):
- **Feature Space:** 14 continuous standardized indicators covering returns (1h, 4h, 24h, 72h), normalized 5m ATR%, 24h realized volatility, volume z-scores, trend strength, trend persistence, drawdowns from rolling highs, recovery from rolling lows, support/resistance distances, and volatility-normalized range width.
- **Exchange Outage Invariant:** The March 24, 2023 Binance matching engine outage (80 missing bars from 12:39 to 14:00 UTC) is handled with strict causal gating. Any rolling feature window overlapping this outage is flagged `is_valid_window = False` and rejected from candidate eligibility.
- **News Coverage Policy:** Missing news records at $T_0$ are never interpreted as "no news occurred".

---

## 4. Phase 2 — Market Regime Intelligence

Implemented in [`src/coin_behavior_engine/analogs/regime_classifier.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/src/coin_behavior_engine/analogs/regime_classifier.py):
- **Regimes Classified:** `TREND_UP`, `TREND_DOWN`, `RANGE`, `HIGH_VOLATILITY`, `UNCERTAIN`.
- **Sample Distribution (500 historical sample points):**
  - `UNCERTAIN`: 63.8% (319 / 500)
  - `TREND_DOWN`: 12.8% (64 / 500)
  - `TREND_UP`: 11.8% (59 / 500)
  - `RANGE`: 9.0% (45 / 500)
  - `HIGH_VOLATILITY`: 2.6% (13 / 500)
- **Range Resolution Population Dynamics (45 evaluated range episodes over 24h horizon):**
  - `Breakdown Down Rate`: **40.0%** (18 episodes)
  - `Breakout Up Rate`: **35.6%** (16 episodes)
  - `Remained Intact Rate`: **24.4%** (11 episodes)
- **Scientific Takeaway:** Identified horizontal ranges broke down more frequently than they broke out upward or remained intact. Range trading cannot assume symmetric or guaranteed mean reversion.

---

## 5. Phase 3 & 4 — Historical Analog Retrieval & Probabilistic Forecasting

Implemented in [`src/coin_behavior_engine/analogs/similarity_engine.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/src/coin_behavior_engine/analogs/similarity_engine.py) and [`src/coin_behavior_engine/analogs/probabilistic_forecaster.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/src/coin_behavior_engine/analogs/probabilistic_forecaster.py):

### 5.1. Strict Causal Quarantine Invariant
For every query candle at index $Q$, candidate historical instances $C$ were restricted to:
$$C + 2016\text{ bars (7 days)} \le Q$$
This guarantees that candidate forward outcome paths were completely closed and finished in past history before decision time $T_0$. Temporal spacing of at least 288 bars (24h) between retrieved analogs prevented near-duplicate sample clustering.

### 5.2. Walk-Forward Evaluation & Comparative Statistical Skill

Evaluated over 50 chronological walk-forward test points across multi-year data:

```
+------------------------------------+------------------+-----------------------------+
| Benchmark / Model                  | 24h Brier Score  | Relative Performance        |
+------------------------------------+------------------+-----------------------------+
| Regime-Conditioned Base Rate       | 0.2460           | Best Calibrated Base Rate   |
| Unconditional Historical Base Rate | 0.2472           | Stable Historical Baseline  |
| Recent-Volatility Random Walk      | 0.2500           | Pure Driftless Benchmark    |
| Causal Analog Engine V1 (k=15)     | 0.3199           | UNDERPERFORMS BASE RATES    |
| Momentum / Persistence Baseline    | 0.3800           | Worst (Severe Overfitting)  |
+------------------------------------+------------------+-----------------------------+
```

### 5.3. Honest Scientific Verdict
- **Skill Verdict:** **`PROBABILISTIC_FORECAST_SKILL = NOT_SUPPORTED`**
- **Explanation:** In strict adherence to scientific honesty, the unoptimized V1 Analog Engine (Brier score 0.3199) did not outperform the unconditional base rate (0.2472) or regime-conditioned base rate (0.2460) in predicting 24h directional returns. The analog probabilities exhibited overconfidence on non-recurrent patterns. In accordance with sprint guidelines, **no selective post-hoc parameter tuning was performed to force a pass**.

---

## 6. Phase 5 — News-Conditioned Analog Research

Delivered in [`news_coverage_gap_11_19.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/news_coverage_gap_11_19.md):
- **Sample Size Insufficiency ($N=3$):** Exactly three verified/bounded events exist in the repository. Fitting supervised machine learning models on $N=3$ events is statistically meaningless.
- **Formal Status:** **`NEWS_CONDITIONED_EDGE = INSUFFICIENT_DATA`**.
- The engine abstains from news-conditioned modifications when coverage is absent, and defines a compliant roadmap for acquiring public domain BLS, FOMC, and SEC EDGAR historical archives.

---

## 7. Phase 6 — Range Intelligence Prototype

Implemented in [`src/coin_behavior_engine/analogs/range_intelligence.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/src/coin_behavior_engine/analogs/range_intelligence.py):

### Scenario Audit: BTC 65,000 – 65,700 USDT Consolidation Channel
- **Gross Channel Width:** 700 USDT (**1.08%**).
- **Round-Trip Spot Friction:** 0.30% (fee 0.10% + slip 0.05% entry and exit).
- **Net Tradable Room:** **0.78%** (509 USDT).
- **Historical Analog Empirical Results (at Support 65,000–65,200 USDT):**
  - Probability of Mean Reversion to Upper Boundary (65,700): **36.3%**
  - Probability of Breakdown below Support (<64,850): **58.0%**
  - Probability of Range Continuation / Inaction: **5.7%**
  - Expected MAE when buying at support: **-1.42%**
  - Realized Risk/Reward Ratio: **0.55**
- **Verdict:** **`NO_EDGE`**
- **Rationale:** Entering at 65,000 USDT on an unverified assumption of a guaranteed channel bounce is mathematically negative expectation. The breakdown probability (58.0%) exceeds the mean-reversion probability (36.3%), and net room (0.78%) is overwhelmed by the average adverse excursion (-1.42%).

---

## 8. Phase 7 — Resource & Operational Protection

- **Resource Telemetry:**
  - Full multi-year 5m dataset load time: **0.13 seconds** (27.97 MB RAM).
  - Feature matrix generation: **0.36 seconds**.
  - Peak Memory: `< 180 MB` (well under 450 MB ceiling).
- **Test Invariants:** All **9/9 sprint invariant unit tests** passed ([`tests/test_sprint11_19_analog_engine.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_19_analog_engine.py)), and all **37/37 cumulative tests** passed in **1.52s**.
- **Operational Protection:** Zero access, modification, or restart of VPS, Coolify, staging, or live capture containers.

---

## 9. Deliverables Manifest

| Deliverable Path | Description |
| :--- | :--- |
| [`research_report_11_19.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_report_11_19.md) | Comprehensive scientific research report |
| [`cross_dataset_closure_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/cross_dataset_closure_11_19.json) | Forensic audit of 8 mismatched candles and terminal bar quarantine |
| [`contamination_register_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/contamination_register_11_19.json) | Multi-year research contamination register (2022–2026) |
| [`event_provenance_corrections_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/event_provenance_corrections_11_19.json) | Downgrade of all 3 events to `ASSUMED_LATENCY` |
| [`analog_feature_manifest_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/analog_feature_manifest_11_19.json) | Feature store schema and outage rejection rules |
| [`analog_retrieval_audit_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/analog_retrieval_audit_11_19.json) | Causal analog search diagnostics and cluster isolation |
| [`probabilistic_forecast_evaluation_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/probabilistic_forecast_evaluation_11_19.json) | Multi-horizon forecasts and comparative Brier scores |
| [`range_intelligence_audit_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/range_intelligence_audit_11_19.json) | Channel evaluation and 65,000–65,700 USDT case study |
| [`news_coverage_gap_11_19.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/news_coverage_gap_11_19.md) | Statistical data sufficiency and acquisition roadmap |
| [`reproducibility_manifest_11_19.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/reproducibility_manifest_11_19.json) | Cryptographic SHA-256 deliverable audit |
| [`tests/test_sprint11_19_analog_engine.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_19_analog_engine.py) | 9 executable invariant unit tests |

---

## 10. Mandatory Status Declarations

```yaml
SPRINT_11_19_STATUS: PASS
CROSS_DATASET_CLOSURE: PASS
CONTAMINATION_GOVERNANCE: PASS
EVENT_PROVENANCE: ASSUMED
CAUSAL_ANALOG_RETRIEVAL: PASS
PROBABILISTIC_FORECAST_SKILL: NOT_SUPPORTED
NEWS_CONDITIONED_EDGE: INSUFFICIENT_DATA
RANGE_INTELLIGENCE: PASS
MODEL_TRAINING: OFFLINE_RESEARCH_ONLY
HISTORICAL_DATA_STATUS: RESEARCH_CONTAMINATED
PROSPECTIVE_OBSERVATION: NOT_STARTED
LIVE_TRADING: PROHIBITED
OPERATOR_AUTHORIZATION: NOT_GRANTED
```
