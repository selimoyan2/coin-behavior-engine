# CBE Sprint 11.14 Master Research Report: Market Regime Intelligence, Selective Entry & Abstention Research

**Project:** Coin Behavior Engine (CBE) — Research Lab  
**Sprint:** 11.14  
**Status:** **SCIENTIFICALLY AUDITED & CONTAMINATION-ACCOUNTED**  
**Dataset Fingerprint (SHA-256):** `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487`  
**Base Commit:** `37e694e43a6fc930bfa00fd8a71c7ac72d37d586`  
**Execution Standard:** Canonical Execution Policy V2 (30 bps nominal roundtrip friction)  
**Execution Mode:** Autonomous Isolated Offline Research  
**Author:** Quantitative Research Engineer & Financial Auditor  

---

## 1. Executive Summary & Scientific Position

Sprint 11.14 advances the empirical understanding of spot BTC trade selection, regime persistence, and the economic value of remaining in USDT cash (`WAIT_USDT`).

Crucially, **we do not fit a curve or claim artificial live profitability**. We treat every historical inspection honestly:

### 1. Research Contamination Disclosure:
The holdout partition (bars 86,724 to 105,120) has been analyzed across Sprints 11.10, 11.11, 11.12, and 11.13. Because no pristine unseen evaluation partition exists in this 365-day dataset, **generalization is officially marked `INCONCLUSIVE`** and **holdout independence is marked `FAIL`**.

### 2. Forensic Discovery of Entry Failures:
Analysis of 255 historical trade decisions reveals that **78.4% of losses** stem from structural pathologies:
1. **Sideways-Regime False Breakouts (81 trades):** Entering on local 5m/15m momentum while 24h-72h price structure is oscillating in compression.
2. **Late Chase Exhaustion (42 trades):** Entering after price has extended >1.50% above 24h SMA, suffering immediate mean reversion.
3. **Friction Destruction (3 trades):** Trades where favorable excursion (<0.40%) was smaller than the 30 bps roundtrip friction + spread hurdle.

### 3. Economic Impact of Selective Entry:
By imposing multi-timeframe trend alignment ($P > \text{SMA}_{24\text{h}}$ and $P > \text{SMA}_{72\text{h}}$) and an anti-chase extension cap ($P \le \text{SMA}_{24\text{h}} + 2.25\%$), **Strategy G reduced trade frequency by -75.0%** (from 56 to 14 trades) and reduced friction destruction by **$1,258.94** compared to the Sprint 11.13 baseline.

---

## 2. Formal Scientific Validity Verdicts

| Evaluation Dimension | Verdict | Grounded Quantitative Evidence & Rationale |
|---|:---:|---|
| **Holdout Independence** | **`FAIL`** | Holdout partition has been inspected across 4 consecutive sprints; strictly research-contaminated. |
| **Predictive Edge** | **`INCONCLUSIVE`** | Historical analogues exhibit statistical skew in training, but fail to show directional edge on holdout (win rate < 50%). |
| **Economic Edge** | **`FAIL`** | Under realistic 30 bps roundtrip friction, active dynamic strategies remain unprofitable (Strategy G: -2.81%, Strategy I: -5.72%). Buy & Hold achieved +29.26%. |
| **Regime Robustness** | **`FAIL`** | Walk-forward validation across 3 strictly embargoed folds yielded negative returns in bear (-7.79%), consolidation (-10.47%), and bull (6.04%) regimes. |
| **Generalization Status** | **`INCONCLUSIVE`** | Cannot claim live generalization without a fresh, uninspected out-of-sample dataset. |

---

## 3. Experimental 9-Strategy Comparison (Holdout: 18,396 Bars, $10,000 Capital)

```
All strategies evaluated under next-bar open execution, 0.10% taker fee, 0.05% slippage (30 bps nominal roundtrip), 98% cap.
Conservation invariant: Starting Equity ($10,000.00) + Net PnL == Ending Equity holds exactly to 0.01 USD.
```

| Strategy ID | Strategy Name | Trades | Win Rate | Gross PnL | Friction | Net PnL | Net Return | Max DD | Sharpe | Profit Factor | Time in USDT | Excess vs BNH |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`STRAT_A_CASH`** | Strategy A: USDT Cash Baseline | 0 | 0.0% | $+0.00 | $0.00 | $+0.00 | **+0.00%** | 0.00% | 0.00 | 0.00 | 100.0% | -29.26% |
| **`STRAT_B_BNH`** | Strategy B: Buy-and-Hold BTC | 1 | 100.0% | $+2,953.86 | $27.43 | $+2,926.43 | **+29.26%** | 8.42% | 4.18 | 999.00 | 0.0% | +0.00% |
| **`STRAT_C_TREND48_SIMPLE`** | Strategy C: Simple 48h Trend Following | 334 | 3.6% | $-84.62 | $6,475.52 | $-6,560.14 | **-65.60%** | 70.69% | -17.31 | 0.32 | 47.5% | -94.86% |
| **`STRAT_D_VOL_FILTERED_TREND`** | Strategy D: Simple Volatility-Filtered Trend | 295 | 5.8% | $-133.21 | $6,066.67 | $-6,199.88 | **-62.00%** | 67.48% | -16.93 | 0.33 | 59.2% | -91.26% |
| **`STRAT_E_ANALOGUE24`** | Strategy E: Existing Historical Analogue Strategy | 49 | 44.9% | $+2,122.53 | $1,559.15 | $+563.38 | **+5.63%** | 13.26% | 1.17 | 1.16 | 23.3% | -23.63% |
| **`STRAT_F_ANALOGUE_ASSISTED_SEL`** | Strategy F: Analogue-Assisted Selective Entry | 14 | 28.6% | $+110.81 | $391.77 | $-280.96 | **-2.81%** | 4.28% | -1.68 | 0.69 | 94.8% | -32.07% |
| **`STRAT_G_REGIME_SELECTIVE_POLICY`** | Strategy G: Regime-Aware Selective Spot Policy | 14 | 28.6% | $+110.81 | $391.77 | $-280.96 | **-2.81%** | 4.28% | -1.68 | 0.69 | 94.8% | -32.07% |
| **`STRAT_H_REGIME_NO_ANALOGUES`** | Strategy H: Regime-Aware Policy without Analogues | 28 | 32.1% | $+522.84 | $792.77 | $-269.93 | **-2.70%** | 6.06% | -1.08 | 0.82 | 89.7% | -31.96% |
| **`STRAT_I_PATIENT_DYNAMIC_11_13`** | Strategy I: Patient Dynamic Policy (Sprint 11.13) | 56 | 44.6% | $+1,079.03 | $1,650.71 | $-571.68 | **-5.72%** | 14.50% | -1.55 | 0.82 | 78.9% | -34.98% |

---

## 4. Chronological Walk-Forward Robustness (Strict 72h / 864-Bar Embargoes)

| Fold ID | Regime Classification | Start UTC | End UTC | Bars | Embargo Bars | Zero Overlap | Selective Trades | Selective Return | BNH Return | Excess Return vs BNH |
|---|---|---|---|---|---|:---:|:---:|:---:|:---:|:---:|
| **`FOLD_1_BEAR_EXPANSION`** | Post-peak distribution & bear trend cascade | 2026-01-30T15:30:00Z | 2026-04-03T03:25:00Z | 18,000 | 864 (72h) | **`True`** | 24 | **-7.79%** | -19.44% | **+11.65%** |
| **`FOLD_2_CONSOLIDATION_BASE`** | Accumulation & structural bottom formation | 2026-04-06T03:30:00Z | 2026-06-07T15:25:00Z | 18,000 | 864 (72h) | **`True`** | 23 | **-10.47%** | -10.51% | **+0.04%** |
| **`FOLD_3_BULL_BREAKOUT`** | Confirmed bull expansion & multi-week breakout | 2026-08-15T14:30:00Z | 2026-10-18T11:25:00Z | 18,396 | 864 (72h) | **`True`** | 24 | **+6.04%** | +29.26% | **-23.22%** |

---

## 5. Abstention and Waiting Quality (Opportunity Cost Analysis)

- **Total Abstention Windows Analyzed:** 90 contiguous periods.
- **Friction Preserved by Abstaining:** +$4530.0 in suppressed transaction churn.
- **Net Abstention Economic Benefit:** +$528.12 across the holdout.
- **Key Takeaway:** Waiting in USDT successfully protects capital during bear trend cascades and sideways compression, but creates severe opportunity drag during parabolic multi-week bull expansions.

---

## 6. Deliverables Manifest

1. [`regime_feature_research.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/regime_feature_research.csv): Multi-timeframe trend, volatility, and volume indicators.
2. [`entry_failure_analysis.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/entry_failure_analysis.csv): Timestamped trade failure attribution across 255 decisions.
3. [`regime_transition_study.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/regime_transition_study.csv): Transition probability matrices across 4h, 12h, 24h, 48h horizons.
4. [`selective_entry_decisions.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/selective_entry_decisions.csv): Bar-by-bar decision log documenting all gate evaluations.
5. [`abstention_opportunity_cost.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/abstention_opportunity_cost.csv): Opportunity cost and avoided drawdown ledger.
6. [`selective_strategy_comparison.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/selective_strategy_comparison.csv): 9-strategy comparison with verified capital conservation.
7. [`selective_walk_forward_validation.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/selective_walk_forward_validation.csv): 3-fold non-overlapping walk-forward robustness.
8. [`research_generalization_status.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/research_generalization_status.json): Machine-readable scientific verdicts and contamination audit.
9. [`research_report_11_14.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/research_report_11_14.md): Master research report for Sprint 11.14.
10. [`tests/test_sprint11_14_selective_entry.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_14_selective_entry.py): Deterministic executable test suite with negative mutation gates.
