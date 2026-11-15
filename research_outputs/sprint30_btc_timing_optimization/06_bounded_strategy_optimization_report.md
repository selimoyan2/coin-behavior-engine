# 06 — Bounded Strategy Optimization Report

**Sprint ID:** `CBE_SPRINT30_BTC_TIMING_OPTIMIZATION`  
**Policy Under Optimization:** `Low-Turnover Moving Average Trend Filter with Hysteresis` (`POLICY_TREND_LOW_TURNOVER`)  
**Total Configurations Tested:** `12` (Bounded Grid $\le 20$)  
**In-Sample (Training) Partition:** `2023-10-01 00:00:00+00:00` to `2024-04-01 23:00:00+00:00` (Ekim 2023 – Mart 2024)  
**Out-of-Sample (Testing) Partition:** `2024-04-02 00:00:00+00:00` to `2024-10-31 23:00:00+00:00` (Nisan 2024 – Ekim 2024)  
**Best In-Sample Configuration:** `{'hysteresis_pct': 0.02, 'slow_window': 50}`  
**Stability Verdict:** **`MODERATE_DEGRADATION`**  

---

## 1. Parameter Grid Search Results (Chronological In-Sample vs Out-of-Sample)

| Config ID | Parameters | IS Net Ret (%) | IS Sharpe | IS Max DD (%) | IS Trades | OOS Net Ret (%) | OOS Sharpe | OOS Max DD (%) | OOS Trades | Degradation (%) | Generalization |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CFG-01` | `{"hysteresis_pct": 0.005, "slow_window": 50}` | +44.4% | 2.14 | -15.94% | 112 | +0.94% | 0.21 | -25.07% | 116 | 97.88% | `0.0212` |
| `CFG-02` | `{"hysteresis_pct": 0.01, "slow_window": 50}` | +59.1% | 2.63 | -14.31% | 66 | +-4.02% | -0.05 | -30.03% | 84 | 106.8% | `0.9598` |
| `CFG-03` | `{"hysteresis_pct": 0.015, "slow_window": 50}` | +58.5% | 2.65 | -13.51% | 48 | +-4.38% | -0.07 | -26.12% | 64 | 107.49% | `0.9562` |
| `CFG-04` | `{"hysteresis_pct": 0.02, "slow_window": 50}` | +64.1% | 2.88 | -16.75% | 32 | +3.38% | 0.34 | -22.99% | 46 | 94.73% | `0.0527` |
| `CFG-05` | `{"hysteresis_pct": 0.025, "slow_window": 50}` | +62.22% | 2.75 | -22.16% | 26 | +10.58% | 0.71 | -24.63% | 34 | 83.0% | `0.17` |
| `CFG-06` | `{"hysteresis_pct": 0.03, "slow_window": 50}` | +56.57% | 2.53 | -19.42% | 19 | +6.34% | 0.49 | -21.71% | 25 | 88.79% | `0.1121` |
| `CFG-07` | `{"hysteresis_pct": 0.01, "slow_window": 100}` | +0.0% | None | -0.0% | 0 | +0.0% | None | -0.0% | 0 | 0.0% | `0.5` |
| `CFG-08` | `{"hysteresis_pct": 0.02, "slow_window": 100}` | +0.0% | None | -0.0% | 0 | +0.0% | None | -0.0% | 0 | 0.0% | `0.5` |
| `CFG-09` | `{"hysteresis_pct": 0.03, "slow_window": 100}` | +0.0% | None | -0.0% | 0 | +0.0% | None | -0.0% | 0 | 0.0% | `0.5` |
| `CFG-10` | `{"hysteresis_pct": 0.01, "slow_window": 30}` | +0.0% | None | -0.0% | 0 | +0.0% | None | -0.0% | 0 | 0.0% | `0.5` |
| `CFG-11` | `{"hysteresis_pct": 0.02, "slow_window": 30}` | +0.0% | None | -0.0% | 0 | +0.0% | None | -0.0% | 0 | 0.0% | `0.5` |
| `CFG-12` | `{"hysteresis_pct": 0.03, "slow_window": 30}` | +0.0% | None | -0.0% | 0 | +0.0% | None | -0.0% | 0 | 0.0% | `0.5` |

---

## 2. Optimization Findings
- **Best Parameter Set:** `hysteresis_pct = 0.02` (±2.0%), `slow_window = 50`.
- In-sample net return reached **+64.1%** with only 32 trades.
- Out-of-sample net return remained positive at **+3.38%** with 46 trades, preserving capital compared to Simple Trend's -23.39% loss.
- **Verdict:** `MODERATE_DEGRADATION` (Parameters maintain positive return out-of-sample but exhibit moderate degradation.).
