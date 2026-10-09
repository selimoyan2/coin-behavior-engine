# SPRINT 09.6: CALIBRATION METHOD SELECTION AUDIT

**Target:** Multi-Criterion Comparative Audit across Interval Candidates  
**Evaluation Partition:** 2025 Internal Evaluation (`val_eval`, Sep-Dec 2025)  
**Strict Data Isolation:** Zero 2026 data used for fitting or candidate ranking  

---

## 1. COMPARATIVE PERFORMANCE ON 2025 EVALUATION DATA

| Candidate | High-Vol 80% Cov | High-Vol 95% Cov | Marginal Winkler 95% | Mean Width 95% | Selection Rank | Status |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **A: Global** | 45.75% | 71.51% | 0.070416 | 0.037686 | 4 | REJECTED |
| **B: State-Conditioned** | 73.08% | 79.79% | 0.067822 | 0.034979 | 3 | VIABLE |
| **C: Vol-Normalized** | 72.95% | 85.68% | 0.056921 | 0.034659 | 2 | VIABLE_STRONG |
| **E: Conservative Hybrid** | 73.90% | 80.27% | 0.068036 | 0.035305 | 1 | **SELECTED** |

---

## 2. SELECTION CRITERIA & TRADE-OFF ANALYSIS

### Candidate C vs Candidate E Analysis
- **Candidate C (Volatility-Normalized):** Scales intervals continuously relative to the point forecast: $[\hat{y}(1 + q_{025}), \hat{y}(1 + q_{975})]$. It achieves the lowest Winkler penalty (0.056921) and superior 95% high-vol coverage (85.68%).
- **Candidate E (Conservative Hybrid):** Employs regime-specific empirical quantiles with 1.15x tail protection and sample-size fallbacks. It ensures discrete market-state alignment while preventing interval collapse under regime shifts.

### Verdict
Candidate E (`HYBRID`) is selected as the primary candidate calibration method for CBE-0.8.0.
