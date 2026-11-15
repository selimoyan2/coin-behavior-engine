# 07 — Out-of-Sample Stability, Walk-Forward Validation & Overfitting Reconciled Analysis

**Sprint ID:** `CBE_SPRINT30_1_SCIENTIFIC_REPORTING_RECONCILED`  
**Dataset:** `DS-BTC-1H-2023-2024`  
**Policy Under Evaluation:** `Low-Turnover Moving Average Trend Filter with Hysteresis` (`POLICY_TREND_LOW_TURNOVER`)  
**Single Chronological Split Verdict:** **`MODERATE_DEGRADATION`** (Exploratory Capital Preservation)  
**Three-Fold Walk-Forward Verdict:** **`REJECTED_OVERFITTING`** (Multi-Fold Generalization Failure)  

---

## 1. Disentangling Incompatible Experiments

To preserve epistemological integrity, the Coin Behavior Engine strictly separates two distinct, non-combinable validation protocols:

```
[Experiment A: Single Chronological Split]
  ├─ In-Sample (IS):   2023-10-01 to 2024-04-01 (6 months bull run)
  ├─ Out-of-Sample (OOS): 2024-04-02 to 2024-10-31 (7 months consolidation)
  └─ Result: IS +64.10% → OOS +3.38% (Degradation: 94.73%, Status: MODERATE_DEGRADATION)

[Experiment B: 3-Fold Expanding Walk-Forward Cross-Validation (WF-VAL-POLICY_TRE-3F)]
  ├─ Fold 1 (OOS Mar 2024 – May 2024): Test Net Return:  -0.86% (Loss)
  ├─ Fold 2 (OOS May 2024 – Aug 2024): Test Net Return:  -4.87% (Loss)
  ├─ Fold 3 (OOS Aug 2024 – Oct 2024): Test Net Return: +10.80% (Gain)
  └─ Summary: Positive OOS Consistency: 33.33%, Mean Degradation: 96.34%
     Scientific Verdict: REJECTED_OVERFITTING
```

> [!CAUTION]
> **No Averaging or Conflation:**  
> These two evaluations use different sample windows, fold geometries, and re-training horizons. 
> The +3.38% outcome from the single chronological test cannot be used to override or mask the 33.33% positive consistency in the 3-fold walk-forward cross-validation.

---

## 2. Rigorous 3-Fold Walk-Forward Cross-Validation (`WF-VAL-POLICY_TRE-3F`)

Derived directly from `13_walk_forward_turnover_controlled_results.json`:

| Fold Index | Training Window | Testing Window | Train Return (%) | Test Return (%) | Train Sharpe | Test Sharpe | Degradation (%) | Profitable OOS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | `2023-10-01` – `2024-03-07` | `2024-03-07` – `2024-05-26` | +62.29% | **-0.86%** | 3.27 | 0.06 | 101.38% | ❌ False |
| **Fold 2** | `2023-10-01` – `2024-05-26` | `2024-05-26` – `2024-08-13` | +60.93% | **-4.87%** | 2.22 | -0.56 | 107.99% | ❌ False |
| **Fold 3** | `2023-10-01` – `2024-08-13` | `2024-08-13` – `2024-10-31` | +53.10% | **+10.80%** | 1.58 | 1.60 | 79.66% | ✅ True |

### Aggregate Cross-Validation Metrics:
- **Mean In-Sample Return:** `+58.77%`
- **Mean Out-of-Sample Return:** `+1.69%`
- **Mean Return Degradation:** `96.34%`
- **Out-of-Sample Positive Consistency:** `33.33%` (Only 1 of 3 folds was positive)
- **Scientific Verdict:** **`REJECTED_OVERFITTING`**
- **Evidence Status:** `EXPLORATORY_ONLY` (`CLEAN_HOLDOUT_NOT_AVAILABLE` — 42 prior recorded reads in `holdout_usage_ledger.json`).

---

## 3. Scientific Synthesis: Why Claims of "Free of Overfitting" are False

1. **Market Regime Dependence:**  
   Trend-following policies with hysteresis (+2%) excel during steady directional expansion (e.g. October 2023 – March 2024, BTC +170%). However, when encountering sustained multi-month range-bound consolidation with sharp mean-reversions (such as Fold 1 and Fold 2 from March to August 2024), trend-following logic systematically buys near local tops and sells near local bottoms within the channel.
2. **Turnover Control vs Overfitting:**  
   Turnover controls (hysteresis band + 72h minimum holding) successfully eliminated catastrophic fee destruction (reducing trades from 700 to 78 and fees from $11,228 to $1,983). However, **reducing turnover does not automatically confer true out-of-sample edge**.
3. **Formal Epistemological Ruling:**  
   The policy is **NOT consistently stable and is NOT free of overfitting**. While it avoided large drawdowns, it failed multi-fold walk-forward validation (only 33.33% positive consistency, 96.34% degradation). Any claim that this strategy is production-ready or consistently profitable out-of-sample is scientifically rejected.
