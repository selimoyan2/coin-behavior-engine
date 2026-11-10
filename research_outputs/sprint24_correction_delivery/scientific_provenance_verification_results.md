# Scientific Provenance Verification Results
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Provenance Verification Protocol

Each record loaded by `ResearchCatalogProvider` underwent independent cryptographic and empirical verification:
1. **Byte-Level Digest Calculation:** The file designated by `source_artifact` was opened and read in 64 KB chunks to compute its actual SHA-256 digest.
2. **Hash Match Verification:** Computed digest was compared against the catalog manifest.
3. **Absence of Synthetic Fallbacks:** Checked that missing test statistics evaluate strictly to `None` in memory and are rendered as `N/A` or `-` in output presentations.
4. **Model Invariance:** Checked that every record strictly enforces `model_version == "CBE-0.7.0"`.

---

## 2. Verification Outcomes by Record

### 2.1 RES-FUND-01
* **Source Artifact:** `data/reports/sprint09_38_funding_predictability_report.json`
* **Computed SHA-256:** `5d579e160e1d51a700ee00a0d423984d720235e0e0a5db22919aa2df9dbba397`
* **Integrity Status:** `MATCH_CONFIRMED`
* **Observed Metrics:** `raw_p_value = 1.0`, `holdout_fdr_q = None`, `volatility_ratio = None`
* **Signature Status:** `EVIDENCE_MISSING` (no signature block present)
* **Replication Verdict:** `NOT_EVALUATED`

### 2.2 RES-REGIME-01
* **Source Artifact:** `data/reports/sprint09_27_validation_and_holdout_report.json`
* **Computed SHA-256:** `14ae2c3a0ebcbbf8e96a50ad5ada06a5ce2b0fc22082f3a225d9becfcee4cebf`
* **Integrity Status:** `MATCH_CONFIRMED`
* **Observed Metrics:** `raw_p_value = 0.1738`, `holdout_fdr_q = None`, `volatility_ratio = 1.240`
* **Signature Status:** `EVIDENCE_MISSING`
* **Replication Verdict:** `NOT_EVALUATED`

### 2.3 RES-ANALOG-01
* **Source Artifact:** `research_outputs/research_report_29_pattern_similarity.json`
* **Computed SHA-256:** `337b19b98c381d0cac508161efa9bb776826cd8708bd2d64d1b9e8779f8b6847`
* **Integrity Status:** `MATCH_CONFIRMED`
* **Observed Metrics:** `raw_p_value = None`, `holdout_fdr_q = None`, `volatility_ratio = 1.310`
* **Signature Status:** `EVIDENCE_MISSING`
* **Replication Verdict:** `NOT_EVALUATED`

### 2.4 RES-MACRO-01
* **Source Artifact:** `research_outputs/experiment_cpi_volatility.cbe-hyp.json`
* **Computed SHA-256:** `3cda89069d2d415b39976451e06821217e132c3f8730959f64bf50259b1580aa`
* **Integrity Status:** `MATCH_CONFIRMED`
* **Observed Metrics:** `raw_p_value = 0.000012`, `holdout_fdr_q = None`, `volatility_ratio = 1.913`
* **Signature Status:** `EVIDENCE_MISSING`
* **Replication Verdict:** `NOT_EVALUATED`

### 2.5 RES-DURABILITY-01
* **Source Artifact:** `research_outputs/sprint23_delivery/persistent_volume_verification.json`
* **Computed SHA-256:** `cbf65eb56e87f86f34eef46c26ae7eb0a12e8c253d837ba235f3d46797a7e84a`
* **Integrity Status:** `MATCH_CONFIRMED`
* **Observed Metrics:** Infrastructure durability verified
* **Signature Status:** `HMAC_SHA256_ATTESTED`
* **Replication Verdict:** `VERIFIED_OPERATIONAL`

### 2.6 RES-CRYPTO-01
* **Source Artifact:** `data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet`
* **Computed SHA-256:** `05874e9766eeae5534fc18ec9908cfafc537d7a5814522a5c6e8666497f6c3eb`
* **Integrity Status:** `MATCH_CONFIRMED`
* **Quarantine Verdict:** `CONTAMINATED_SYNTHETIC_VOLUME`

---

## 3. Automated Test Verification Results

All provenance tests in `tests/test_sprint_product_acceleration_24_correction.py` executed with 100% pass rate:
* `TestGroup1ResearchCatalogEvidenceIntegrity::test_catalog_records_have_actual_sha256_of_disk_files` $\rightarrow$ **PASSED**
* `TestGroup1ResearchCatalogEvidenceIntegrity::test_no_fabricated_scientific_values` $\rightarrow$ **PASSED**
* `TestGroup1ResearchCatalogEvidenceIntegrity::test_reconciliation_matrix_completeness` $\rightarrow$ **PASSED**
