# Scientific Comparison Compatibility Rules
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)
**Engine Module:** `src/coin_behavior_engine/product/research_intelligence_workspace.py`

---

## 1. Gating Principles

Directly comparing disparate research candidates risks false-positive claims and invalid cross-regime deductions. The Comparison Lab enforces strict algorithmic compatibility gating before rendering cross-candidate matrices or computing delta statistics.

### Rule 1: Candidate Count Constraint
- Minimum Candidates: **2**
- Maximum Candidates: **4**
- Violations: Single-candidate evaluations or sets with >4 candidates are rejected before matrix evaluation.

### Rule 2: Research Family Compatibility
Candidates must share compatible methodology classes:
- Cross-paradigm comparisons (e.g. microstructure orderbook execution vs. macro quarterly indicators) trigger incompatibility warnings unless specifically bridged by normalized feature domains.
- Core research families (`momentum`, `regime_clustering`, `macro_relative_value`, `statistical_arbitrage`) are mutually comparable under normalized sample distributions.

### Rule 3: Regime Overlap Requirement
- Candidates must share a minimum sample overlap across the evaluated regime windows (`trending_bull`, `trending_bear`, `high_volatility`, `mean_reverting`).
- Minimum required overlapping observations: **100 sample intervals**.

### Rule 4: Statistical Significance Floor
- All candidates submitted for comparative delta analysis must have completed independent statistical testing with a recorded $p$-value ($p < 0.05$).
- Candidates with missing, fabricated, or uncomputed $p$-values are blocked from comparative delta ranking.

### Rule 5: Status Governance Gate
- Only candidates in `promoted`, `validated`, or `exploratory` states are eligible.
- Candidates marked `quarantined`, `rejected`, or `compromised` are strictly rejected by the gate.

---

## 2. Gate Decision Output Schema

```json
{
  "gate_passed": true,
  "incompatibility_reasons": [],
  "candidate_count": 3,
  "evaluated_candidates": [
    "RES-FUND-01",
    "RES-REGIME-01",
    "RES-MACRO-01"
  ],
  "regime_overlap_ratio": 0.85,
  "matrix": { ... },
  "difference_analysis": { ... }
}
```

When `gate_passed` is `false`, the UI displays a warning banner highlighting the specific failure condition and suppresses the difference analysis table to prevent erroneous conclusions.
