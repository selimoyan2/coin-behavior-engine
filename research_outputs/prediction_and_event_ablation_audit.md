# Prediction & Event Intelligence Ablation Audit (Canonical Holdout Truth)

**Dataset Fingerprint:** `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487`  
**Holdout Bars:** 86,724 to 105,120 (18,396 bars)  
**Execution Standard:** Canonical Execution Policy V2 (30 bps nominal roundtrip)  
**Audit Status:** **CANONICAL GROUND TRUTH**  

---

## 1. Tripartite Ablation Matrix (Holdout Partition, $10,000 Capital)

To isolate the genuine incremental contribution of:
1. **Trend & Regime Rules Alone** (Strategy H)
2. **Behavioral Analogue Predictions** (Strategy G vs Strategy H)
3. **Point-in-Time Event Context Filtering** (Strategy I vs Strategy G)

| Strategy ID | Strategy Specification | Trades | Win Rate | Gross PnL | Friction | Net PnL | Net Return | Sharpe | Max DD | Time in USDT |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **STRAT_H_NO_ANALOGUES** | Pure Trend + Regime Filter (Ablation Baseline) | 38 | 44.7% | +$768.63 | $1,105.68 | -$337.05 | **-3.37%** | -1.17 | 9.82% | 87.4% |
| **STRAT_G_PATIENT_DYN** | Trend + Regimes + **Analogue Signals** | 56 | 44.6% | +$1,079.03 | $1,650.71 | -$571.68 | **-5.72%** | -1.55 | 14.50% | 78.9% |
| **STRAT_I_WITH_EVENTS** | Trend + Regimes + Analogues + **Event Context** | 56 | 44.6% | +$1,079.03 | $1,650.71 | -$571.68 | **-5.72%** | -1.55 | 14.50% | 78.9% |

---

## 2. Key Scientific Findings & Refutations

### Finding 1: Analogue Predictions Harmed Financial Decision Performance (-2.35% Drag)
- Adding multi-horizon analogue predictions to pure trend filters increased trade frequency from 38 to 56 trades (+47.4% turnover increase).
- Although gross PnL increased by +$310.40, additional transaction friction was -$545.03.
- **Incremental Net PnL of Analogue Model:** **-$234.63 (-2.35% net return)**.
- **Maximum Drawdown:** Worsened from 9.82% (pure trend) to 14.50% (with analogues).
- **Conclusion:** On this holdout partition, behavioral analogue predictions generated false-positive re-entries during sideways consolidation, resulting in net economic destruction.

### Finding 2: Macro Event Filtering Added Zero Active Alpha on Holdout (0 False Entries Blocked)
- Strategy I produced identical trade entries, exits, friction, and net PnL to Strategy G (**56 trades, -$571.68 net PnL**).
- Zero negative macro events coincided with the 56 entry bars on the holdout partition.
- **Conclusion:** Prior narrative assertions claiming that event filtering blocked 2 regulatory false entries were speculative narrative not supported by simulation data.

### Finding 3: Buy-and-Hold Dominance
- Buy-and-Hold achieved **+29.26%** (+$2,926.43 net PnL) with only $27.43 in friction.
- All active dynamic strategies underperformed both Buy-and-Hold and USDT Cash (0.00%) due to transaction drag in choppy market regimes.
