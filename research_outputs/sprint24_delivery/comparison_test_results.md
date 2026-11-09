# Comparison Lab Test Results
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)
**Verification Method:** Unit Tests (`test_sprint_product_acceleration_24.py`) & Playwright Browser Tests (`run_playwright_sprint24.py`)

---

## 1. Automated Test Results

| Test ID | Test Description | Input Candidates | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **COMP-01** | Minimum Candidate Enforce | `["RES-FUND-01"]` (1 item) | Gate failure, alert user | Gate rejection: `< 2 candidates` | **PASSED** |
| **COMP-02** | Maximum Candidate Enforce | `["C1","C2","C3","C4","C5"]` (5 items) | Gate failure, alert user | Gate rejection: `> 4 candidates` | **PASSED** |
| **COMP-03** | Valid Triad Comparison | `["RES-FUND-01","RES-REGIME-01","RES-MACRO-01"]` | Gate passed, 3 columns rendered | Cross-candidate matrix rendered | **PASSED** |
| **COMP-04** | Valid Pair Comparison | `["RES-FUND-01","RES-CRYPTO-01"]` | Gate passed, 2 columns rendered | Cross-candidate matrix rendered | **PASSED** |
| **COMP-05** | Quarantined Candidate Rejection | `["RES-FUND-01","RES-QUARANTINED-01"]` | Gate failure, quarantine banner | Rejected: `RES-QUARANTINED-01 is quarantined` | **PASSED** |
| **COMP-06** | Pairwise Difference Analysis | `["RES-FUND-01","RES-REGIME-01"]` | Delta computation for Sharpe, Drawdown | Absolute and percentage differences displayed | **PASSED** |
| **COMP-07** | Comparison Persistence | Title: "Sprint 24 Triad Baseline" | Saved to `/app/data/prospective/saved_comparisons` | JSON persisted, returned via GET endpoint | **PASSED** |
| **COMP-08** | Saved Comparison Retrieval | Query saved comparisons list | Item appears in `#saved-comparisons-list` | 1 item listed, restore button functional | **PASSED** |

---

## 2. Statistical Invariant Adherence
- Pairwise deltas computed strictly as arithmetic differences: $\Delta = X_{\text{candidate}} - X_{\text{baseline}}$.
- Relative percentage computed strictly as: $\% = \frac{X_{\text{candidate}} - X_{\text{baseline}}}{|X_{\text{baseline}}|}$.
- Zero division handled gracefully with `N/A`.
- No model weights, hyperparameters, or training states were modified.
