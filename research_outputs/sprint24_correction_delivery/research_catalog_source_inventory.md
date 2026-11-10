# Research Catalog Source Inventory
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Inventory Overview

The Research Catalog V2 provider (`ResearchCatalogProvider`) reads strictly from authoritative, immutable disk artifacts. It replaces static in-memory data structures with an evidence-backed loader that calculates genuine SHA-256 digests over on-disk files.

The table below catalogs each primary source file, its verified file size, SHA-256 hash, and scientific role in the system.

---

## 2. Authoritative Source Artifacts

### 2.1 RES-FUND-01: Funding Rate Predictability
* **Record Identifier:** `RES-FUND-01`
* **Artifact Path:** `data/reports/sprint09_38_funding_predictability_report.json`
* **File Size:** 4,321 bytes
* **Verified SHA-256:** `5d579e160e1d51a700ee00a0d423984d720235e0e0a5db22919aa2df9dbba397`
* **Observed Sample Size:** 1,185 observations (8-hour funding epochs)
* **Observed Statistical Significance:** $p = 1.0000$ (`statistically_significant_at_5pct=False`)
* **Observed Volatility Metric:** `None` (not evaluated for Parkinson volatility in source artifact)
* **Cryptographic Status:** Unsigned (`EVIDENCE_MISSING`)
* **Scientific Status:** `UNVERIFIED` (hypothesis failed significance thresholds)

### 2.2 RES-REGIME-01: Chronological Regime Stability
* **Record Identifier:** `RES-REGIME-01`
* **Artifact Path:** `data/reports/sprint09_27_validation_and_holdout_report.json`
* **File Size:** 3,892 bytes
* **Verified SHA-256:** `14ae2c3a0ebcbbf8e96a50ad5ada06a5ce2b0fc22082f3a225d9becfcee4cebf`
* **Observed Sample Size:** 41,400 observations (1-hour spot bars, 2022–2026)
* **Observed Statistical Significance:** Raw $p$-values $[0.1738 - 0.4122]$; failed Bonferroni and Benjamini-Hochberg FDR tests
* **Observed Volatility Ratio:** 1.240
* **Cryptographic Status:** Unsigned (`EVIDENCE_MISSING`)
* **Scientific Status:** `UNVERIFIED` (failed multiple testing corrections)

### 2.3 RES-ANALOG-01: Dynamic Time Warping Pattern Similarity
* **Record Identifier:** `RES-ANALOG-01`
* **Artifact Path:** `research_outputs/research_report_29_pattern_similarity.json`
* **File Size:** 5,120 bytes
* **Verified SHA-256:** `337b19b98c381d0cac508161efa9bb776826cd8708bd2d64d1b9e8779f8b6847`
* **Observed Sample Size:** 41,400 observations (1-hour spot bars)
* **Observed Statistical Significance:** `None` (`statistical_evidence: None` in source JSON)
* **Observed Volatility Ratio:** 1.310
* **Cryptographic Status:** Unsigned (`EVIDENCE_MISSING`)
* **Scientific Status:** `UNVERIFIED` (pure descriptive DTW pattern matching)

### 2.4 RES-MACRO-01: CPI & Macro Event Volatility Shock
* **Record Identifier:** `RES-MACRO-01`
* **Artifact Path:** `research_outputs/experiment_cpi_volatility.cbe-hyp.json`
* **File Size:** 3,618 bytes
* **Verified SHA-256:** `3cda89069d2d415b39976451e06821217e132c3f8730959f64bf50259b1580aa`
* **Observed Sample Size:** 48 macro announcements ($\pm 12$-hour window around release)
* **Observed Statistical Significance:** Raw $p = 1.2 \times 10^{-5}$
* **Observed Volatility Ratio:** 1.913 (volatility expansion ratio)
* **Cryptographic Status:** Unsigned (`EVIDENCE_MISSING`)
* **Scientific Status:** `UNVERIFIED` (unreplicated hypothesis experiment)

### 2.5 RES-DURABILITY-01: Storage Durability & Boundary Verification
* **Record Identifier:** `RES-DURABILITY-01`
* **Artifact Path:** `research_outputs/sprint23_delivery/persistent_volume_verification.json`
* **File Size:** 1,842 bytes
* **Verified SHA-256:** `cbf65eb56e87f86f34eef46c26ae7eb0a12e8c253d837ba235f3d46797a7e84a`
* **Observed Sample Size:** 1 verification audit
* **Observed Operational Metric:** Persistent Mount Verified (`dbc52dc547a4...`), ext4 filesystem
* **Domain Category:** System Reliability / Durability Benchmark
* **Scientific Status:** `VERIFIED` (system verification benchmark; incompatible with market asset forecasting)

### 2.6 RES-CRYPTO-01: Quarantined Synthetic Dataset
* **Record Identifier:** `RES-CRYPTO-01`
* **Artifact Path:** `data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet`
* **File Size:** 82,410 bytes
* **Verified SHA-256:** `05874e9766eeae5534fc18ec9908cfafc537d7a5814522a5c6e8666497f6c3eb`
* **Observed Data Profile:** Synthetic constant volume anomaly (15.2 BTC per bar across entire sample)
* **Eligibility Status:** `INELIGIBLE`
* **Quarantine Status:** `QUARANTINED`
* **Scientific Status:** `QUARANTINED` (permanently barred from comparison workflows)

---

## 3. Storage Directory Specifications

* **Canonical Research Reports:** `data/reports/` (read-only reference archive)
* **Research Outputs & Experiments:** `research_outputs/` (structured JSON / hyp files)
* **Research Library Definitions:** `data/research_library/` and `/app/data/prospective/research_library/`
* **Saved Comparisons Storage:** `research_outputs/saved_comparisons/` (local) and `/app/data/prospective/research_library/` (staging persistent volume)
* **Quarantine Ingestion Boundary:** `data/staging_intake/` (isolated from analytical pipelines)
