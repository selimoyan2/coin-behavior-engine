# Hardcoded Record Reconciliation Matrix
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Reconciliation Overview

This document provides the formal audit reconciliation comparing the claims made by the hardcoded Sprint 24 `_CANONICAL_RECORDS` structure against empirical facts verified directly from disk artifacts. Every discrepancy is cataloged alongside its final accepted status and explicit justification for downgrade.

---

## 2. Comparative Reconciliation Matrix

| Record ID | Claimed Metric | Claimed Status | Actual Source Artifact | Actual SHA-256 | Actual Verification Outcome | Final Status | Downgrade Justification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RES-FUND-01** | `volatility_ratio=1.120`, `holdout_fdr_q=0.0180` | `REPLICATED_CONFIRMED`, `SIGNED_VALID` | `data/reports/sprint09_38_funding_predictability_report.json` | `5d579e160e1d51a7...` | Sample size: 1,185 epochs. Models failed statistical significance ($p=1.0000$, `significant=False`). No Ed25519 signature. | `UNVERIFIED` / `EVIDENCE_MISSING` | Hypothesis failed significance testing in original report; no independent confirmation or signature exists. Synthetic FDR $q$-value removed. |
| **RES-REGIME-01** | `volatility_ratio=1.240`, `holdout_fdr_q=0.0120` | `REPLICATED_CONFIRMED`, `SIGNED_VALID` | `data/reports/sprint09_27_validation_and_holdout_report.json` | `14ae2c3a0ebcbbf8...` | Sample size: 41,400 bars. Raw $p$-values $[0.1738 - 0.4122]$. All models failed Bonferroni and Benjamini-Hochberg FDR thresholds. | `UNVERIFIED` / `EVIDENCE_MISSING` | Multiple testing control in source artifact documents hypothesis rejection. Unsigned artifact. Fabricated $q$-value removed. |
| **RES-ANALOG-01** | `volatility_ratio=1.310`, `holdout_fdr_q=0.0210` | `REPLICATED_CONFIRMED`, `SIGNED_VALID` | `research_outputs/research_report_29_pattern_similarity.json` | `337b19b98c381d0c...` | Sample size: 41,400 bars. `statistical_evidence: None` explicitly recorded in source report JSON. | `UNVERIFIED` / `EVIDENCE_MISSING` | Source report contains no statistical evidence bundle. Invented FDR $q$-value eliminated. Downgraded to unverified descriptive analog. |
| **RES-MACRO-01** | `volatility_ratio=1.450`, `holdout_fdr_q=0.0080` | `REPLICATED_CONFIRMED`, `SIGNED_VALID` | `research_outputs/experiment_cpi_volatility.cbe-hyp.json` | `3cda89069d2d415b...` | Observed expansion ratio: 1.913, raw $p=1.2 \times 10^{-5}$. Unsigned hypothesis bundle. | `UNVERIFIED` / `EVIDENCE_MISSING` | Single experiment without multi-analyst independent replication or signed evidence package. Corrected volatility metric to observed 1.913x. |
| **RES-DURABILITY-01**| Operational benchmark | `VERIFIED` | `research_outputs/sprint23_delivery/persistent_volume_verification.json` | `cbf65eb56e87f86f...` | Volume `dbc52dc547a4...` genuine mount verified. ext4 filesystem. | `VERIFIED` (Operational Only) | Durability benchmark is valid for infrastructure auditing, but quarantined from financial comparison due to `METHODOLOGY_MISMATCH`. |
| **RES-CRYPTO-01** | Synthetic volume series | `QUARANTINED` | `data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet` | `05874e9766eeae55...` | Constant volume anomaly of 15.2 BTC per 5m bar confirmed. | `QUARANTINED` / `INELIGIBLE` | Ineligible for analytical comparison. Compatibility gate strictly enforces fail-closed rejection (`QUARANTINED_RECORD`). |

---

## 3. Discrepancy Analysis

### 3.1 P-Value and FDR Q-Value Fabrication Elimination
In earlier versions, hypothetical research findings were assigned standard "significant" values ($q \in [0.008, 0.021]$) to demonstrate UI rendering. Under scientific integrity standards, this was flagged as misleading. All fabricated metrics have been removed. Fields without empirical backing evaluate strictly to `None` in Python and render as `N/A` or `-` in the frontend UI.

### 3.2 Cryptographic Signature Grounding
No artifact in the historical catalog currently possesses an Ed25519 detached signature. Claiming `SIGNED_VALID` without an actual signature file violated cryptographic trust boundaries. All unsigned artifacts now report `SignatureStatus.EVIDENCE_MISSING` or `UNSIGNED`.

### 3.3 Replication Claims
Replication requires independent reproduction by a separate researcher or system. None of the four initial hypotheses met the rigorous multi-analyst confirmation criteria. Their status has been set to `RecordStatus.UNVERIFIED` and `replication_verdict = NOT_EVALUATED`.
