# Unit Test Execution Results
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Test Execution Summary

* **Dedicated Correction Suite:** `tests/test_sprint_product_acceleration_24_correction.py` $\rightarrow$ **19 / 19 PASSED** (100%)
* **Workspace V2 Base Suite:** `tests/test_sprint_product_acceleration_24.py` $\rightarrow$ **28 / 28 PASSED** (100%)
* **Total Combined Unit Tests:** **47 / 47 PASSED** (100%)
* **Execution Duration:** 3.75 seconds

---

## 2. Dedicated Correction Test Suite Breakdown (`test_sprint_product_acceleration_24_correction.py`)

### Group 1: Evidence-Backed Research Catalog & Provenance Integrity
* `test_catalog_records_have_actual_sha256_of_disk_files` $\rightarrow$ **PASSED**  
  *Verified that all catalog entries match the actual SHA-256 hash of their disk artifact.*
* `test_no_fabricated_scientific_values` $\rightarrow$ **PASSED**  
  *Verified missing p-values and FDR q-values evaluate to `None`, not synthetic constants.*
* `test_reconciliation_matrix_completeness` $\rightarrow$ **PASSED**  
  *Verified formal reconciliation matrix documents discrepancies across all records.*

### Group 2: 12-Point Fail-Closed Scientific Comparison Gate
* `test_gate_rejects_cadence_mismatch` $\rightarrow$ **PASSED**  
  *Verified 8h vs 1h cadence mismatch fails closed with `SAMPLING_CADENCE_MISMATCH`.*
* `test_gate_rejects_quarantined_record` $\rightarrow$ **PASSED**  
  *Verified pairing with `RES-CRYPTO-01` fails closed with `QUARANTINED_RECORD`.*
* `test_gate_rejects_methodology_mismatch` $\rightarrow$ **PASSED**  
  *Verified system durability benchmark fails closed with `METHODOLOGY_MISMATCH`.*
* `test_gate_rejects_unknown_candidates` $\rightarrow$ **PASSED**  
  *Verified invalid candidate ID fails closed with `RESEARCH_NOT_FOUND`.*
* `test_gate_rejects_single_candidate_or_overflow` $\rightarrow$ **PASSED**  
  *Verified boundary limits ($N < 2$ and $N > 4$) fail closed.*
* `test_gate_accepts_valid_compatible_pair` $\rightarrow$ **PASSED**  
  *Verified `RES-REGIME-01` and `RES-ANALOG-01` pass gate with valid difference analysis.*
* `test_dynamic_revalidation_of_incompatible_saved_comparison` $\rightarrow$ **PASSED**  
  *Verified loaded legacy comparisons are dynamically re-evaluated and marked `REVALIDATION_FAILED`.*

### Group 3: Operational Status Fail-Closed & Health Domain Separation
* `test_storage_inspection_error_fails_closed_to_unverified` $\rightarrow$ **PASSED**  
  *Verified storage inspection error sets durability to `UNVERIFIED` (never `PERSISTENT_VERIFIED`).*
* `test_research_reports_count_never_falls_back_to_arbitrary_constant` $\rightarrow$ **PASSED**  
  *Verified report count fails closed to `None` / `UNAVAILABLE` rather than defaulting to 6.*
* `test_health_domains_are_strictly_separated` $\rightarrow$ **PASSED**  
  *Verified 5 independent health domains in overview response.*

### Group 4: Frontend Search XSS Prevention & Safe DOM Construction
* `test_search_uses_safe_dom_methods` $\rightarrow$ **PASSED**  
  *Verified DOM construction uses `createElement` and `textContent` without `innerHTML` injection.*
* `test_route_navigation_uses_allowlist` $\rightarrow$ **PASSED**  
  *Verified `ALLOWED_TABS` allowlist prevents navigation hijacking.*

### Group 5: Model Invariants & Trading Prohibition
* `test_canonical_model_version_strictly_cbe_070` $\rightarrow$ **PASSED**  
  *Verified all records enforce model version `CBE-0.7.0`.*
* `test_governance_decision_technical_no_go` $\rightarrow$ **PASSED**  
  *Verified governance decision remains strictly `TECHNICAL_NO_GO`.*
* `test_trading_permanently_prohibited` $\rightarrow$ **PASSED**  
  *Verified trading prohibition invariant.*
* `test_no_trading_signals_in_catalog_or_difference_analysis` $\rightarrow$ **PASSED**  
  *Verified absence of PnL, Sharpe, win rate, buy/sell markers.*

---

## 3. Base Workspace V2 Suite Breakdown (`test_sprint_product_acceleration_24.py`)

* **Group 1: Strict Identity Binding Hardening (2 tests):** Both passed.
* **Group 2: Research Discovery and Filtering (8 tests):** All passed.
* **Group 3: Scientific Comparison Lab & Gate (5 tests):** All passed.
* **Group 4: Overview Dashboard & Global Search (2 tests):** Both passed.
* **Group 5: API Contracts & Security (8 tests):** All passed.
* **Group 6: Scientific & Governance Invariants (3 tests):** All passed.
