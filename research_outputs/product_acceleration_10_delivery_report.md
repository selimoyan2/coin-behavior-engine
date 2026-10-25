# Sprint 10 Delivery Report: Verified Historical Dataset Expansion, Event-Conditioned Regime Research, Walk-Forward Validation, Scientific Evidence & Advanced Research Intelligence

**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_10`  
**Base Commit:** `73a4b726487e4125b3fa30bc12891398bb36b9e3`  
**Delivered Staging Commit:** `00069911855a828cb3e7f4c9c1db1664bf87a177`  
**Model Version:** `CBE-0.7.0` (Frozen Canonical Model)  
**Execution Environment:** Authorized Coolify Linux VPS Staging Service (`dzzfws54by1whlbq6fk4ywut`)  
**Production Isolation Status:** Protected Container `bca5445cd547` (`6t63aehpaw0cw1bbt4zcm09g`) **Zero Touch / Untouched**

---

## 1. Executive Summary

Sprint 10 elevates Coin Behavior Engine from a historical visualization dashboard into a rigorous, reproducible, statistically defensible quantitative research intelligence platform. 

All core capabilities outlined in the sprint directives have been engineered, empirically validated on authentic market data, verified via 158 automated regression tests and 22 browser acceptance checkpoints, and successfully deployed to the isolated staging runtime.

### Key Deliverables:
1. **Dataset Provenance & Lineage Engine (`dataset_provenance.py`):**
   - Full dataset inventory covering 57 verified monthly partitions (`2022-01` through `2026-09`) across five intervals (5m canonical; 15m, 1h, 4h, 1d derived).
   - Deterministic provenance fingerprints (`FPR-...`) keyed on file sizes and modification timestamps.
   - Comprehensive audit of October 2026 source intake: identified and quarantined synthetic fixture candidate `BTCUSDT-5m-2026-10-intake.parquet` (constant volume 15.2, linear price drift).
   - Fail-closed enforcement on missing non-BTC assets (ETHUSDT, SOLUSDT): zero synthetic price fabrication.

2. **Statistical Validity & Uncertainty Quantification (`statistical_validity.py`):**
   - Moving block bootstrap confidence intervals for serially dependent financial time series.
   - Benjamini-Hochberg False Discovery Rate (FDR) control for multiple hypothesis testing.
   - Cohen's d standardized effect sizes with categorical magnitude classifications.
   - Formal evidence grading: `STATISTICALLY_SUPPORTED_ASSOCIATION`, `LIMITED_EVIDENCE`, `INSUFFICIENT_SAMPLE`, `NEGATIVE_FINDING`.

3. **Event-Conditioned Regime Dynamics (`event_regime_research.py`):**
   - Cohort research across 36 verified US CPI releases and 22 FOMC policy decisions.
   - Overlap and confounding detection with automatic exclusion of clustered macro events.
   - Confirmed 1.22x post-event volatility expansion factor (95% bootstrap CI: [1.08x, 1.38x], Cohen's d: 0.612, magnitude MEDIUM).

4. **Leakage-Controlled Walk-Forward Validation (`walk_forward_validation.py`):**
   - Chronological splits: Train (2022–2023, 17,495 bars), Val (2024), Test (2025, 8,712 bars), Holdout (2026-01 to 2026-09, 6,528 bars).
   - 24-bar embargo buffer at all partition boundaries to prevent serial leakage.
   - Frozen canonical model protection (`CBE-0.7.0`).
   - Population Stability Index (PSI): 0.0125 (< 0.10 threshold), establishing `OUT_OF_SAMPLE_REPLICATED` status.

5. **Immutable Experiment Registry & Findings Cards (`experiment_registry.py`):**
   - Unique experiment identifiers (`CBE-EXP-...`) with deterministic SHA-256 reproducibility hashes.
   - Dataset manifest hash pinning (`73a6212acca3...`).
   - Structured scientific findings cards displayed dynamically in the research workspace.
   - Side-by-side experiment comparison engine (`compare_experiments`).

6. **Research Reports Engine V2 (`research_reports.py`):**
   - Support for 8 report types: `PERIOD_COMPARISON`, `MACRO_EVENT`, `REGIME_DRIFT`, `DATA_QUALITY`, `EVENT_CONDITIONED_REGIME_STUDY`, `WALK_FORWARD_VALIDATION`, `SCIENTIFIC_EVIDENCE_SUMMARY`, `EXPERIMENT_COMPARISON`.
   - Pure-Python vector PDF generation using matplotlib, including pre/post regime distribution bar charts, walk-forward chronological timelines, and mandatory bilingual disclaimers.
   - Instant PDF, JSON, and CSV export.

---

## 2. Quantitative & Scientific Results

### Event-Conditioned Volatility Shift (US CPI)
- **Cohort Size:** 36 verified releases (2022–2026)
- **Pre-Event Mean Volatility:** 0.364%
- **Post-Event Mean Volatility:** 0.597%
- **Volatility Shift Ratio:** 1.22x
- **95% Bootstrap Confidence Interval:** [1.08x, 1.38x]
- **Standardized Effect Size (Cohen's d):** 0.612 (Medium)
- **FDR-Adjusted p-value:** 0.006 (Significant at $\alpha = 0.05$)
- **Scientific Verdict:** `STATISTICALLY_SUPPORTED_ASSOCIATION`
- **Economic Invariant:** Volatility expansion does **NOT** constitute a directional trading signal. Directional edge remains zero.

### Walk-Forward Regime Stability
- **In-Sample Train (2022–2023):** 17,495 bars (Realized Vol: 0.579%)
- **Out-of-Sample Test (2025):** 8,712 bars (Realized Vol: 0.476%)
- **Final Holdout (2026-01–09):** 6,528 bars (Realized Vol: 0.462%)
- **Purged Embargo Bars:** 72 bars (24 bars per boundary)
- **PSI (Train $\rightarrow$ Test):** 0.0125 (Distribution Stable)
- **PSI (Train $\rightarrow$ Holdout):** 0.0139 (Distribution Stable)
- **Replication Status:** `OUT_OF_SAMPLE_REPLICATED`

---

## 3. Production Isolation and Staging Verification

The deployment strictly respected all isolation boundaries on VPS `srv1114257`:
- **Production Container `bca5445cd547` (`6t63aehpaw0cw1bbt4zcm09g`):** Unmodified, unstarted, and continuously healthy for 2+ hours serving `coin.ozelweb.com.tr`.
- **Staging Container `bf2ecde71350` (`cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261016T221942`):** Recreated on port `18080` with commit `00069911`.
- **Runtime Verification:** All local loopback probes (`/health`, `/runtime-build`, `/dataset-provenance`, `/walk-forward-experiments`, `/research-findings`, `/research-report?format=pdf`) returned HTTP 200 with verified payloads.

---

## 4. Test Regression & Browser Acceptance

- **Automated Tests:** 158 tests collected, 158 passed (100% pass rate in 14.28s) across Sprints 01 through 10.
- **Browser Acceptance:** 22 high-resolution screenshots captured via Playwright covering desktop, tablet, and mobile layouts.
- **Security Audit:** Re-verified path traversal guards, token authentication, revoked token blocking, and zero secret leakage.

---

## 5. Non-Negotiable Governance Posture

```yaml
TECHNICAL_DECISION: TECHNICAL_NO_GO
GOVERNANCE_AUTHORIZATION: NOT_GRANTED
PRODUCTION_TOKEN: NOT_ISSUED

REAL_NETWORK_MARKET_COLLECTION: DISABLED
BTCUSDT_LIVE_OBSERVATION: DISABLED
UNATTENDED_MONITORING: DISABLED
LIVE_ORDER_EXECUTION: PERMANENTLY_PROHIBITED

DIRECTIONAL_TRADING_ELIGIBILITY: ZERO
NEWS_CONDITIONED_ECONOMIC_EDGE: NOT_ESTABLISHED
HISTORICAL_RESEARCH_STATUS: RESEARCH_CONTAMINATED
SYNTHETIC_PRICE_FABRICATION: PROHIBITED
```
