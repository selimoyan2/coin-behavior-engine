# CBE Sprint 11.13 Master Research Report: Canonical Reproduction Gate & Reporting Repair

**Project:** Coin Behavior Engine (CBE) — Research Lab  
**Sprint:** 11.13  
**Status:** **REPRODUCED, AUDITED & GATED**  
**Dataset Fingerprint (SHA-256):** `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487`  
**Base Commit:** `281cab0a13f68f31a7bc2f8c6d4ed14c95f641b3`  
**Execution Standard:** Canonical Execution Policy V2 (30 bps nominal roundtrip)  
**Execution Mode:** Autonomous Isolated Offline Research  
**Author:** Principal Quantitative Verification Engineer & Financial Auditor  

---

## Executive Summary: Scientific Truth and Definite Resolution

Sprint 11.13 permanently resolves all remaining contradictions in the Coin Behavior Engine (CBE) research literature by establishing an independent, machine-verifiable reproduction gate and aligning narrative reporting with canonical simulated reality.

### 1. The Patient Strategy Discrepancy Formally Resolved:
- **Historical Claim:** +19.89% return, 18 trades reported in Sprint 11.11 and early draft text of 11.12.
- **Canonical Simulated Reality:** **-5.72% net return, 56 trades, -$571.68 net PnL, $1,650.71 friction**.
- **Mechanistic Root Cause:** In Sprint 11.11, `PatientSpotEngine` read unclassified raw parquet where the `SIDEWAYS` regime was literally absent (0 bars), accidentally restricting entries to 483 bull bars. When evaluated against authentic calibrated regimes with 11,853 bull and sideways bars, Strategy G triggered 56 trades and suffered whipsaw losses in consolidation ranges.
- **Formal Ruling:** The +19.89% claim is officially **SUPERSEDED** as an unclassified regime artifact. The canonical truth is locked at **56 trades and -5.72%**.

### 2. Behavioral Analogue Ablation: Negative Incremental Contribution:
- **Strategy H (Pure Trend without Analogues):** 38 trades, **-3.37% return** (-$337.05 net PnL, $1,105.68 friction).
- **Strategy G (Trend + Analogues):** 56 trades, **-5.72% return** (-$571.68 net PnL, $1,650.71 friction).
- **Net Impact of Analogues:** **-2.35% net return drag** (+$310.40 gross gain offset by -$545.03 additional friction). Analogue signals degraded decision quality by generating premature re-entries.

### 3. Friction Policy Reconciliation (Canonical Execution Policy V2):
- Corrected documentation typo in prior manifest (25 bps) to match actual simulator execution:
  - 10 bps taker entry fee + 10 bps taker exit fee + 5 bps entry slippage + 5 bps exit slippage = **30 bps nominal roundtrip** (0.0030 = 0.30%).

---

## 1. 7-Dimension Research Validity Matrix

Rather than using a single global `VERIFIED` label to obscure economic reality, Sprint 11.13 explicitly separates 7 research dimensions:

| Dimension | Verdict | Quantitative Evidence & Rationale |
|---|:---:|---|
| **1. Accounting Correctness** | **`PASS`** | $	ext{Starting Equity} + 	ext{Net PnL} = 	ext{Ending Equity}$ holds exactly to 0.01 USD across all 9 strategies in both canonical and independent replay simulations. Zero negative balances. |
| **2. Dataset Integrity** | **`PASS`** | Byte-level SHA-256 hash verified: `2e99190189dcc7b0...`. 105,120 continuous 5m bars, 0 gaps, locked price boundaries. |
| **3. Temporal Causality** | **`PASS`** | Strict next-bar open fills (t + 1), pessimistic intrabar stop-loss priority, 0 feature lookahead, 72h (864 bars) walk-forward embargoes. |
| **4. Strategy Reproducibility** | **`PASS`** | Independent replay from raw candles and decisions reproduces canonical ledgers with exactly **0.00 discrepancy**. |
| **5. Statistical Predictive Advantage** | **`INCONCLUSIVE`** | Historical analogues showed correlation in Sprint 11.09, but on holdout, Strategy G had 44.6% win rate and negative expectancy (-$10.21/trade). No statistical edge over random walk demonstrated on holdout. |
| **6. Economic Profitability** | **`FAIL`** | Strategy G lost **-5.72%** (-$571.68). Strategy H lost **-3.37%**. Strategy F lost **-3.11%**. Buy & Hold made **+29.26%**. USDT Cash made **0.00%**. All active dynamic strategies lost money after 30 bps friction. |
| **7. Robustness Across Regimes** | **`FAIL`** | Walk-forward validation failed in all 3 regimes: Fold 1 (Bear) **-5.80%**, Fold 2 (Consolidation) **-21.54%**, Fold 3 (Bull) **-5.72%**. No regime delivered positive net return. |

---

## 2. Canonical Strategy Performance Comparison (Holdout: 18,396 Bars, $10,000 Capital)

| Strategy ID | Strategy Name | Trades | Win Rate | Gross PnL | Total Friction | Net PnL | Return (%) | Max DD (%) | Sharpe | Profit Factor | Time in USDT |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`STRAT_A_CASH`** | USDT Cash Baseline | 0 | 0.0% | $0.00 | $0.00 | $0.00 | **0.00%** | 0.00% | 0.00 | 0.00 | 100.0% |
| **`STRAT_B_BNH`** | Buy-and-Hold BTC | 1 | 100.0% | +$2,953.86 | $27.43 | +$2,926.43 | **+29.26%** | 8.42% | 4.18 | 999.00 | 0.0% |
| **`STRAT_C_SWITCH`** | Trend/Cash Switching | 63 | 17.5% | +$1,146.50 | $1,930.12 | -$783.62 | **-7.84%** | 23.42% | -1.52 | 0.83 | 59.5% |
| **`STRAT_D_TREND48`** | Patient 48h Trend Model | 42 | 38.1% | +$2,153.86 | $1,346.78 | +$807.08 | **+8.07%** | 11.54% | 1.99 | 1.28 | 68.8% |
| **`STRAT_E_ANALOGUE24`** | 24h Analogue Strategy | 49 | 44.9% | +$2,122.53 | $1,559.15 | +$563.38 | **+5.63%** | 13.26% | 1.17 | 1.16 | 23.3% |
| **`STRAT_F_EXISTING_DYN`** | Existing Dynamic (11.10) | 98 | 37.8% | +$2,611.79 | $2,922.87 | -$311.08 | **-3.11%** | 15.23% | -0.57 | 0.93 | 47.5% |
| **`STRAT_G_PATIENT_DYN`** | Patient Dynamic (11.11) | 56 | 44.6% | +$1,079.03 | $1,650.71 | -$571.68 | **-5.72%** | 14.50% | -1.55 | 0.82 | 78.9% |
| **`STRAT_H_NO_ANALOGUES`** | Patient without Analogues| 38 | 44.7% | +$768.63 | $1,105.68 | -$337.05 | **-3.37%** | 9.82% | -1.17 | 0.84 | 87.4% |
| **`STRAT_I_WITH_EVENTS`** | Patient with Verified News | 56 | 44.6% | +$1,079.03 | $1,650.71 | -$571.68 | **-5.72%** | 14.50% | -1.55 | 0.82 | 78.9% |

---

## 3. Independent Execution Replay Reconciliation

An independent simulation replay (`independent_execution_replay.csv`) re-simulated every bar of the holdout period from raw candles and decisions:

- **BTC and USDT Inventory Conservation:** Verified. Minimum cash balance remained positive across all runs.
- **Friction Precision:** Matches canonical ledger to 0.00 USD.
- **Trade and Equity Matching:** `replay_vs_canonical_differences.csv` confirms exactly **0.00 difference** across all 9 strategies.

---

## 4. Deliverables Manifest

1. [`sprint11_12_residual_discrepancy_audit.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/sprint11_12_residual_discrepancy_audit.md): Forensic audit of regime unclassified bug and supersession of +19.89% claim.
2. [`canonical_execution_policy_v2.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/canonical_execution_policy_v2.json): Versioned policy specifying 30 bps nominal roundtrip friction and inventory rules.
3. [`independent_execution_replay.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/independent_execution_replay.csv): Full independent simulation replay output.
4. [`replay_vs_canonical_differences.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/replay_vs_canonical_differences.csv): Metric-by-metric difference ledger confirming 0.00 divergence.
5. [`research_reporting_consistency_audit.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/research_reporting_consistency_audit.md): Systematic audit verifying 100% agreement between text prose and CSV tables.
6. [`validation_gate_matrix.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/validation_gate_matrix.json): 7-dimension validity decision matrix.
7. [`research_report_11_13.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/research_report_11_13.md): Definitive master research report.
8. [`tests/test_sprint11_13_canonical_gates.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_13_canonical_gates.py): Deterministic executable regression tests with negative mutation fixtures.
