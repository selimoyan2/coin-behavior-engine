# CBE-0.7.0 Market-State Collapse: Root Cause Reproduction & Forensics

**Sprint:** 09.4  
**Subject:** Scientific Reproduction of Failure A (Mechanical Collapse to DELEVERAGING_STRESS)  
**Affected Component:** `src/coin_behavior_engine/market_state/engine.py` (lines 355–373, 524–526)  
**Status:** REPRODUCED AND MATHEMATICALLY PROVEN

---

## 1. Executive Summary

In CBE-0.7.0, all prospective predictions observed in production were assigned the single market state `DELEVERAGING_STRESS`.
This forensic report details the exact mathematical and implementation defect causing 100% state collapse.

The defect arises from a **single-row percentile evaluation flaw** combined with a **missing-derivatives fallback assumption**.

---

## 2. Implementation Defect Details

### Single-Bar Inference Path
In `src/coin_behavior_engine/market_state/engine.py`, runtime inference for a single incoming market bar is implemented as:

```python
# Lines 524–526:
dummy_df = pd.DataFrame([bar])
current_state = self._classify_market_states_series(dummy_df).iloc[0]
```

### Vectorized Percentile Calculation
Inside `_classify_market_states_series(df)`:

```python
# Lines 370–373:
oi_drop_p05 = float(np.nanpercentile(oi_chg, 5)) if len(oi_chg) > 0 else -0.05
basis_p05 = float(np.nanpercentile(basis, 5)) if len(basis) > 0 else -0.02

cond_delev = (oi_chg <= oi_drop_p05) & (basis <= basis_p05)
```

And lines 382–393:

```python
conditions = [
    cond_delev,
    cond_event,
    cond_jump,
    ...
]
choices = [
    MarketStateId.DELEVERAGING_STRESS.value,
    ...
]
```

---

## 3. Mathematical Proof of Collapse

1. **Percentile Identity on Scalar:**  
   For any array $X = [x]$ of length 1 and any percentile $q \in [0, 100]$:
   $$\text{percentile}([x], q) = x$$
   Therefore:
   $$\text{oi\_drop\_p05} = \text{oi\_chg}[0]$$
   $$\text{basis\_p05} = \text{basis}[0]$$

2. **Tautological Condition:**  
   The condition `(oi_chg <= oi_drop_p05) & (basis <= basis_p05)` simplifies to:
   $$(x \le x) \land (y \le y) \equiv \text{True} \land \text{True} \equiv \text{True}$$
   This condition is **identically True for every real number**!

3. **Missing Derivatives Vulnerability:**  
   Under the `SPOT_ONLY_U0` runtime tier, derivatives data is missing. The engine defaults missing series to `0.0`:
   $$\text{oi\_chg} = 0.0, \quad \text{basis} = 0.0$$
   Evaluating the condition gives:
   $$(0.0 \le 0.0) \land (0.0 \le 0.0) \equiv \text{True}$$

4. **Rule Order Precedence:**  
   Because `cond_delev` is the very first rule evaluated in `conditions`, `MarketStateId.DELEVERAGING_STRESS` is assigned immediately, short-circuiting all subsequent checks (volatility, compression, quiet, etc.).

---

## 4. Empirical Verification Evidence

- `single_row_oi_chg_value`: `0.0`
- `single_row_oi_p05_computed`: `0.0`
- `single_row_basis_value`: `0.0`
- `single_row_basis_p05_computed`: `0.0`
- `cond_delev evaluates to`: `True`
- Empirical production prevalence: **100.0%** DELEVERAGING_STRESS.

---

## 5. Architectural Remediation in CBE-0.8.0

1. **Fixed Historical Reference Thresholds:** Dynamic percentiles on runtime rows are completely eliminated. Thresholds are learned strictly on Discovery (< 2025-01-01) and frozen into `StateThresholdsV080`.
2. **Strict Tier Boundary:** `DELEVERAGING_STRESS` is strictly barred from `SPOT_ONLY_U0`.
3. **Decoupled Two-Layer Taxonomy:** Primary state represents mutually exclusive volatility levels (`LOW`, `NORMAL`, `HIGH`), while secondary flags (`COMPRESSION`, `EXPANSION`) capture dynamic regime structures.
