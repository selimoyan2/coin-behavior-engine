# Root Cause Analysis: Scientific Integrity, Fail-Closed Comparison & Security Defects
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Governance Decision:** `TECHNICAL_NO_GO`  
**Execution Context:** Authorized Staging (`srv1114257:18080`) & Local Verification  
**Production Status:** STRICT ZERO-TOUCH (`coin.ozelweb.com.tr` / container `5e409c596a23`)

---

## 1. Executive Summary

During the independent acceptance audit of Sprint 24 (`CBE_PRODUCT_ACCELERATION_24`), four critical deficiencies were identified that compromised scientific rigor, data provenance, and frontend execution security:

1. **P0 Fabricated Scientific Metadata in Research Catalog:**
   The initial implementation of `ResearchWorkspaceV2Engine` relied on static hardcoded records (`_CANONICAL_RECORDS`) containing synthetic scientific metrics (e.g., invented Benjamini-Hochberg FDR $q$-values such as `0.0180`, `0.0120`, `0.0210`, optimistic $p$-values, unearned `SIGNED_VALID` signature assertions, and false `REPLICATED_CONFIRMED` statuses) instead of dynamically loading and verifying actual disk artifacts from historical research runs.
2. **P0 Permissive Scientific Comparison Gate & Stale Saved Comparisons:**
   The Comparison Lab allowed cross-cadence comparisons (e.g., pairing 8-hour funding rates with 1-hour spot bars) and permitted quarantined contaminated records (`RES-CRYPTO-01`) to generate difference analysis tables. Additionally, saved comparisons were retrieved and rendered statically from storage without dynamic revalidation against updated gate rules.
3. **P1 Operational Status Fail-Open Fallbacks:**
   `get_workspace_overview()` defaulted to `PERSISTENT_VERIFIED` if storage durability inspection encountered an error, and defaulted to an arbitrary report count of 6 rather than reporting the real file count or failing closed to `UNVERIFIED`. Furthermore, application process health was conflated with scientific validity and storage durability.
4. **P1 Frontend Global Search XSS Vulnerability:**
   The search dropdown in `research_explorer_ui.py` constructed HTML strings with unescaped query strings and item properties, injecting them via `element.innerHTML`, which exposed the operator session to DOM-based XSS attacks.

---

## 2. Root Cause Analysis by Defect

### 2.1 P0 — Fabricated Scientific Metadata in Research Catalog

* **Mechanism:** In Sprint 24, `_CANONICAL_RECORDS` in `research_intelligence_workspace.py` hardcoded descriptive fields alongside alleged empirical findings. It claimed `RES-FUND-01` had `volatility_ratio=1.120` and `holdout_fdr_q=0.0180` with `SIGNED_VALID` and `REPLICATED_CONFIRMED`.
* **Empirical Ground Truth:** Examination of the source file `data/reports/sprint09_38_funding_predictability_report.json` revealed:
  - The hypothesis failed statistical significance ($p=1.0000$, `statistically_significant_at_5pct=False`).
  - No cryptographic Ed25519 or HMAC signature existed on disk.
  - The sample size was 1,185 funding intervals, not continuous spot observations.
* **Correction Applied:**
  - Designed and deployed `ResearchCatalogProvider` (`research_catalog_provider.py`) implementing an authoritative 5-tier evidence precedence hierarchy (`CANONICAL_ARTIFACT` $\rightarrow$ `EVIDENCE_BUNDLE` $\rightarrow$ `SPEC_REGISTRY` $\rightarrow$ `HISTORICAL_PROVENANCE` $\rightarrow$ `UNVERIFIED_DESCRIPTIVE`).
  - True SHA-256 digests are computed directly from on-disk artifact bytes.
  - Missing or non-significant metrics are explicitly mapped to `None` / `null`, never replaced with fallback defaults ($p=0.05$ or $q=0.042$).
  - Statuses were corrected to `UNVERIFIED` and `EVIDENCE_MISSING`.

### 2.2 P0 — Permissive Scientific Comparison Gate

* **Mechanism:** The previous gate only checked candidate count bounds ($[2..4]$) and basic ID existence, allowing methodologically incompatible records (e.g. operational disk durability benchmarks vs. market return series) or sampling cadence mismatches (8h funding vs. 1h price) to produce numerical difference tables.
* **Risk:** Mathematical subtraction between metrics computed over fundamentally different sampling frequencies or non-market domains produces scientifically invalid conclusions that mislead research operators.
* **Correction Applied:**
  - Implemented a 12-point fail-closed compatibility gate enforcing:
    1. Selection bounds ($[2..4]$).
    2. Candidate existence in catalog.
    3. Quarantine / contamination status (rejects `RES-CRYPTO-01`).
    4. Model version match (`CBE-0.7.0`).
    5. Provenance conflict checks.
    6. Methodology compatibility (rejects durability benchmarks paired with market models).
    7. Sampling cadence equality (rejects 8h vs 1h).
    8. Observation window overlap floor ($\ge 100$ intervals).
    9. Metric definition equivalency.
    10. Unit compatibility.
    11. Statistical evidence sufficiency.
    12. Explicit missing value handling.
  - Dynamic revalidation was implemented on retrieval: loading any saved comparison re-evaluates it against the 12-point gate. Incompatible records are immediately downgraded to `REVALIDATION_FAILED` with numerical difference analysis suppressed.

### 2.3 P1 — Operational Status Fail-Open Fallbacks

* **Mechanism:** On storage inspection failure, the overview method had a `try/except` block that assigned `"classification": "PERSISTENT_VERIFIED"`, and hardcoded `available_reports_count = 6`.
* **Risk:** Masked persistent volume detachment, permission errors, or data corruption, presenting a false state of health.
* **Correction Applied:**
  - Removed all optimistic fallbacks: storage inspection exceptions now set `"classification": "UNVERIFIED"`, `"verified_durable": false`, and degrade platform health.
  - Reports count returns the exact file count from disk or `None` on read failure.
  - Health domains are strictly separated into 5 independent subsystems: Application Process Health, Storage Durability, Evidence Integrity, Scientific Validity, and Governance Authorization.

### 2.4 P1 — Frontend Global Search DOM XSS Vulnerability

* **Mechanism:** `onWorkspaceGlobalSearch()` concatenated search query strings and returned metadata directly into template literals passed to `innerHTML`.
* **Risk:** An operator pasting an untrusted string or a manipulated backend payload containing HTML tags could execute arbitrary scripts in the authenticated operator context.
* **Correction Applied:**
  - Refactored `renderSearchResults` and `onWorkspaceGlobalSearch` to use native DOM node creation (`document.createElement`, `element.textContent`, `addEventListener`).
  - Added strict route allowlisting (`ALLOWED_TABS = ['overview', 'catalog', 'comparison', 'evidence', 'library', 'reports', 'operations', 'research-explorer', 'comparison-lab']`) and alphanumeric ID sanitization before navigation.

---

## 3. Verification Summary

| Area | Status Before Correction | Status After Correction | Verification Method |
| :--- | :--- | :--- | :--- |
| Catalog Metrics | Hardcoded synthetic numbers | Sourced from disk with true SHA-256 | `test_catalog_records_have_actual_sha256_of_disk_files` |
| Cadence Mismatch | Permitted in comparison | Rejected (`SAMPLING_CADENCE_MISMATCH`) | `test_gate_rejects_cadence_mismatch` |
| Quarantined Records | Included in comparison | Rejected (`QUARANTINED_RECORD`) | `test_gate_rejects_quarantined_record` |
| Saved Comparisons | Static stored state | Dynamic revalidation on load | `test_dynamic_revalidation_of_incompatible_saved_comparison` |
| Storage Errors | Defaulted to `PERSISTENT_VERIFIED` | Fails closed to `UNVERIFIED` | `test_storage_inspection_error_fails_closed_to_unverified` |
| Search Dropdown | Injected via `innerHTML` | Built via `createElement` / `textContent` | `test_search_uses_safe_dom_methods` |
| Staging Deployment | Unverified | Verified on `srv1114257:18080` (container `7e6268bbd2a7`) | Live curl & SSH execution |
| Production Container | Unverified | Untouched (`5e409c596a23` / 0 restarts) | Docker inspect & attestation |
