# Analogue Freeze Identity & Candidate Eligibility Audit — Sprint 11.16B.6

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `dbc825315e58c0b71263a3f5bb9b2d383d4d46ea`  
**Evaluation Mode:** Autonomous Offline Research Only — NO ACTIVATION  
**Document Classification:** Scientific Integrity & Protocol Audit  

---

## 1. Executive Summary

This independent audit assesses the mathematical, algorithmic, and temporal identity between the compact analogue runtime (`CompactAnalogueRuntime`, introduced in Sprint 11.16B.5) and the historically registered Policy E reference specification (`POLICY_E_SELECTIVE_ANALOGUE_ASSISTED`).

The audit separates four distinct dimensions of protocol validity:
1. **Numerical Implementation Parity:** Mathematical precision of nearest-neighbor distance calculation, feature normalization, and directional probability calculation.
2. **Candidate Eligibility Parity:** Temporal filtering, temporal spacing, and candidate inclusion rules across historical partitions.
3. **Prospective No-Leakage Correctness:** Strict prevention of lookahead bias or future-state contamination during prospective evaluation.
4. **Frozen-Policy Identity:** Verification of whether the compact candidate library is bitwise or mathematically identical to the candidate pool evaluated in legacy research sprints.

### Audit Verdict: `PROPOSED_CORRECTED_POLICY_REQUIRING_PROSPECTIVE_FREEZE`

> [!IMPORTANT]
> Scientific integrity requires disclosing that the candidate pool of `CompactAnalogueRuntime` is **not bitwise identical** to the candidate pool evaluated by legacy historical backtest scripts.
> Specifically, legacy scripts allowed the candidate pool to dynamically expand into the holdout partition up to `t - 288`, whereas `CompactAnalogueRuntime` strictly caps candidates to the frozen training partition ($t \le 68,040$).
> This adjustment corrects a critical prospective lookahead hazard, but constitutes a **corrected prospective candidate freeze** rather than identical reproduction of the unconstrained legacy backtest.

---

## 2. Four-Dimensional Integrity Evaluation

| Dimension | Verification Method | Empirical Result | Scientific Status |
| :--- | :--- | :--- | :--- |
| **1. Numerical Parity** | Euclidean distance on $z$-score normalized 10D vectors vs NumPy reference | Max absolute vector distance diff $< 10^{-7}$; probability diff $0.0000$ | **PERFECT PARITY (PASS)** |
| **2. Candidate Eligibility** | Inspection of candidate indexing, exclusion intervals, and temporal thinning | All 67,752 candidates indexed from $t \in [288, 68040]$; $\ge 48$ bar spacing | **VERIFIED CORRECT** |
| **3. Prospective No-Leakage** | Timestamp inspection of maximum candidate index vs prospective boundary | $\max(t_{\text{cand}}) = \text{2026-06-11T17:25:00Z} < \text{2026-06-12}$ (Holdout start) | **LEAKAGE-FREE (PASS)** |
| **4. Frozen-Policy Identity** | Code comparison with `HistoricalAnalogueEngine` dynamic expansion logic | Legacy engine dynamically grew candidate pool into holdout; Compact engine freezes at $t=68,040$ | **DISCREPANCY DETECTED (PROPOSED_CORRECTED)** |

---

## 3. Discrepancy Breakdown & Historical Root Cause

### 3.1 Legacy Dynamic Candidate Expansion
In legacy historical research modules (such as `selective_entry_engine.py` and `canonical_truth_engine.py`), the reference engine populated candidate queries using:
```python
candidates = df.iloc[: current_idx - 288]
```
When evaluating holdout bars in July, August, or September 2026, the legacy engine dynamically ingested candles from June, July, and August as new candidate analogues.

### 3.2 Compact Runtime Frozen Training Partition
In `CompactAnalogueRuntime` (Sprint 11.16B.5), to ensure bounded memory footprint ($<15$ MB) and deterministic reproducibility without dynamic array resizing, the candidate library was frozen strictly to the canonical training partition:
$$\mathcal{C}_{\text{frozen}} = \{ x_t \mid 288 \le t \le 68,040 \}$$
Total candidate count: **67,752 vectors** (after applying the 48-bar forward-horizon exclusion).

### 3.3 Scientific Implications
1. **Prospective Soundness:** Freezing candidates to $t \le 68,040$ is scientifically correct for prospective evaluation, because an observer deployed prospectively cannot retroactively re-index future holdout periods without re-training and re-validating the model.
2. **Historical Discrepancy:** If Policy E were backtested against late 2026 data using the expanding candidate pool, it would find different $k$-NN neighbors than when queried against the frozen $t \le 68,040$ matrix.
3. **Formal Classification:** Per Sprint 11.16B.6 requirements, Policy E must not be labeled `FROZEN_POLICY_IDENTITY_PASS`. It is formally classified as:
   $$\text{POLICY\_E\_STATUS} = \text{PROPOSED\_CORRECTED\_POLICY\_REQUIRING\_PROSPECTIVE\_FREEZE}$$

---

## 4. Empirical Performance Under Historical Replay

### 4.1 Volatility Gate Interaction (`vol_ok`)
Policy E inherits the entry filter of Policy D (`POLICY_D_SELECTIVE_TREND_ONLY`), which defines:
```python
trend_aligned = (close_p > sma_24h) and (close_p > sma_72h)
anti_chase_ok = close_p <= (sma_24h * 1.0225)
vol_ok = 0.015 <= atr_pct <= 0.065
analogue_ok = (analogue_prob is not None and analogue_prob >= 0.60)
```
Empirical analysis of the 105,120 5-minute candles in `market_state_dataset.parquet` reveals:
- **Median 5m ATR percentage:** $0.001337$ (0.134%).
- **Bars with $\text{ATR}_{14} / \text{close} \ge 0.015$:** Only 4 bars out of 105,120 across the entire year.
- **Bars satisfying all four entry conditions simultaneously:** **0 bars**.

### 4.2 Zero-Trade Execution Consequence
Because real 5-minute volatility rarely exceeds 1.5% per 5-minute bar, Policy D and Policy E executed **zero entries** across all four evaluation windows (Bull, Bear, Sideways, High Volatility).

Per Sprint 11.16B.6 core mandate:
> *"A policy with no executed trades must not receive EXECUTION_PARITY_PASS."*

Consequently:
- **Policy D Historical Status:** `BLOCKED_ZERO_TRADES_EXECUTED`
- **Policy E Historical Status:** `BLOCKED_ZERO_TRADES_EXECUTED`

### 4.3 Controlled Active Trade Parity Fixture
When tested in an engineered synthetic environment where $0.015 \le \text{ATR} \le 0.065$ and $\text{Prob}(\text{UP}) \ge 0.60$:
- Both reference simulator and independent journal executed identical BUY orders at `next_open * 1.0005`.
- Both placed identical stop-loss ($0.975 \times \text{fill}$) and take-profit ($1.05 \times \text{fill}$) levels.
- Both deducted exactly 10 bps taker fee and 5 bps entry slippage.
- Both executed intrabar stop-loss upon adverse price excursion with exact 15 bps exit friction.
- Cash and BTC balances reconciled with zero discrepancy down to \$0.0001 USDT.

---

## 5. Audit Recommendations for Prospective Activation Gate

1. **Do Not Activate Policy E in Live Production:** Until operator authorization resolves whether the volatility gate threshold was intended for daily volatility ($24\text{h}$) rather than 5-minute bar ATR.
2. **Formally Register Proposed Candidate Matrix:** The SHA-256 digest `058fbbfb88307db3d937ce82d4948e5a6ef6786da367503fa6ef31da8180f9bb` represents a leak-free prospective candidate library. If approved by the operator, this candidate matrix must be registered as the official frozen candidate library for prospective shadow observation.
3. **Maintain Fail-Closed Posture:** Keep Policy D and Policy E blocked from automated live scoring until parameter calibration is reviewed by the scientific operator.
