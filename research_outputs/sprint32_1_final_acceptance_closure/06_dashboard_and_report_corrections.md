# 06 — Dashboard and Research Evidence Corrections
## Versioned Corrections to Scientific Reporting, Accounting Classifications, and Production Integrity

**Sprint ID:** `CBE_SPRINT32_1_ACCOUNTING_AND_FORENSIC_CLOSURE`  
**Date UTC:** `2026-11-15T14:20:00Z`  
**Governing Standard:** `VERSIONED_CORRECTION_WITHOUT_SILENT_HISTORICAL_REWRITE`  

---

## 1. Summary of Versioned Corrections

In accordance with strict scientific integrity rules, original artifacts from Sprint 31 and Sprint 32 are preserved intact in their original directories (`sprint31_sealed_shadow_evaluation/` and `sprint32_scientific_validation_dashboard_v10/`). This document details the versioned corrections established in Sprint 32.1:

### 1.1. Accounting Reconciliation Verdicts
- **Previous Defect:** Sprint 32 applied `EXACT_MATCH_ZERO_DISCREPANCY` to policies with up to 0.87 USDT difference caused by an erroneous terminal price (87,640.40 USDT).
- **Corrected Standard:** 
  - Terminal price aligned with genuine bar 8759 close: **`87,648.22 USDT`**.
  - Reconstructed equity matches published equity to within half a cent ($< 0.0051$ USDT).
  - Verdicts explicitly separated:
    - `EXACT_MATCH` for strictly $0.0000$ USDT difference (`POLICY_USDT_CASH`).
    - `MATCH_WITH_DOCUMENTED_ROUNDING` for sub-cent ($\le 0.01$ USDT) rounding differences (`POLICY_BUY_AND_HOLD`, `POLICY_TREND_LOW_TURNOVER`, `POLICY_PERIODIC_REBALANCE`, `POLICY_DERIVED_REGIME_CONFIRMATION`, `POLICY_SIMPLE_TREND`).
  - Strict validator prohibits any nonzero difference from claiming exact zero-discrepancy.

### 1.2. Separation of Published vs Reconstructed Equity in Dashboard V10
- Dashboard V10 comparison table (`v10-comparison-tbody`) and REST API `/api/v1/product/research/btc-timing/v10/comparison` now explicitly provide both values:
  - `ending_equity_usdt`: Published simulation equity.
  - `reconstructed_equity_usdt`: Independently reconstructed equity from raw trade logs.
  - `equity_discrepancy_usdt`: Discrepancy amount (at most $0.0051$ USDT).
  - `reconciliation_verdict`: `MATCH_WITH_DOCUMENTED_ROUNDING` or `EXACT_MATCH`.
- UI badges display `Tam Eşleşme (0.00)` or `Yuvarlama (<$0.01)` accordingly.

### 1.3. Initial Capital Consistency
- All text references to $100,000 initial capital have been audited and corrected to **`10,000.00 USDT`**, matching the true and unchanging configuration of all simulation models, databases, and experiment ledgers.

### 1.4. Transaction Cost Conventions
- Transaction costs retain the unambiguous definition:
  - **One-way friction:** 17.5 bps ($0.00175$) per trade.
  - **Implied round-trip:** 35.0 bps ($0.00350$) for a full buy-then-sell cycle.

### 1.5. Statistical Claims and Epistemological Honesty
- Single-sample time series violations ($N=1$ year, serial dependence, volatility clustering) preclude asymptotic p-values.
- Significance claims remain strictly revoked: **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**.
- Effect sizes are reported strictly under descriptive thresholds:
  - H1 (Fee Reduction): `DESCRIPTIVE_THRESHOLD_MET` (-88.31%)
  - H2 (Net Return Improvement): `DESCRIPTIVE_THRESHOLD_MET` (+33.81 pp)
  - H3 (Drawdown Dampening): `DESCRIPTIVE_THRESHOLD_MET` (+25.92 pp)
  - H4 (Alpha vs Buy & Hold): `DESCRIPTIVE_THRESHOLD_FAILED` (-19.10 pp)
  - H5 (Turbulence Resilience): `DESCRIPTIVE_THRESHOLD_MET` (+20.27 pp)

### 1.6. Production Zero-Touch Continuity
- Forensic evidence confirms that container `fdbdba96e677` was terminated and replaced by container `33c3b568c4c1` at `2026-11-15T11:04:21Z` via Coolify deployment 573.
- Historical continuity claims have been formally updated to:
  **`PRODUCTION_ZERO_TOUCH_CONTINUITY_NOT_PROVEN`**.
