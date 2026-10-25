# Coin Behavior Engine (CBE) — Sprint 14 Delivery Report
## Runtime Integrity, Statistical Consistency Engine, Historical Regime Transition Laboratory & Research Intelligence V4

**Sprint ID:** `CBE_PRODUCT_ACCELERATION_14`  
**Execution Date:** 2026-10-26  
**Canonical Model:** `CBE-0.7.0` (FROZEN)  
**Target:** Coolify Staging Environment (`srv1114257` / `168.231.125.238`, UUID: `dzzfws54by1whlbq6fk4ywut`, Container: `86881ba01b3e`)  
**Protected Production:** UUID `6t63aehpaw0cw1bbt4zcm09g` (Container: `863a268cf29a`, `coin.ozelweb.com.tr`) — STRICT ZERO-TOUCH VERIFIED  

---

## 1. Executive Summary

Sprint 14 delivers a critical scientific integrity hardening alongside a major analytical expansion:
1. **Runtime Identity Discrepancy Resolution:** Resolved the root cause behind staging commit discrepancies, enforcing that the application strictly prioritizes immutable container build metadata (`build_metadata.json`) over mutable Docker environment variables.
2. **Mathematical Duality & Statistical Consistency Engine:** Established exact mathematical duality between paired log-volatility ratios $d_i = \ln(V_{\text{post}} / V_{\text{pre}})$ and their 95% moving block bootstrap confidence intervals, proving that $H_0: \mu_d = 0$ is mathematically equivalent to the geometric mean ratio confidence interval crossing 1.0. This completely eliminates inferential contradictions.
3. **Robustness Grid Recalculation:** Recomputed the 16-specification sensitivity matrix, explicitly nullifying the 2 temporally invalid cells (4h candle - 6h window), disaggregating support metrics into 7 distinct rates, and eliminating the conflation between individual event non-expansion and overall hypothesis rejection.
4. **Independent Scientific Reproduction Taxonomy:** Cleaned the reproduction classification taxonomy to reserve `EXACT_MATCH` exclusively for identical values (6 claims), classifying methodological variations under `NUMERICALLY_EQUIVALENT` or `METHOD_DIFFERENCE_EXPLAINED` with 0 mismatches.
5. **Evidence Quality Profile V2:** Replaced unverified absolute claims with testable assertions grounded in dynamic embargo and temporal partition controls, while preserving the composite quality score of 8.48/10.0.
6. **Historical Regime Transition Laboratory:** Designed and implemented a full empirical Markov transition engine across 6 canonical regimes, complete with Dirichlet-multinomial Bayesian 95% credible intervals, right-censored episode duration and Kaplan-Meier survival curves, Frobenius/PSI/JSD drift detection, macro event conditioning, and interactive SVG Sankey flows and timelines.
7. **Research Reports 21–24:** Generated 4 new scientific PDF reports complete with publication-grade vector visualizations.
8. **Automated Regression Suite:** 114/114 passing tests across Sprints 10–14 (100% pass rate).
9. **Zero-Touch Production Integrity:** Verified that production application `6t63aehpaw0cw1bbt4zcm09g` remained completely undisturbed throughout all staging deployments.

---

## 2. Remote Baseline & Git Reconciliation

Independent inspection identified a discrepancy in the final SHA reported in Sprint 13 delivery documentation. The actual remote Git repository was treated as authoritative:
- **Verified Remote Feature SHA:** `1150c6cdf2dbb36f3f2e753d54bf80adc109b772`
- **Verified Remote Final SHA:** `e11b72ffa46eab9e21a2ec9a7e0345509a55e54e`
- **Sprint 14 Feature Commit SHA:** `caa07dad19619635e44993d6436b09af93d5ba30`

---

## 3. Runtime Identity Contract & Staging Root Cause Remediation

### Root Cause Analysis
During Sprint 13, Coolify's container deployment preserved a Docker environment variable `SOURCE_COMMIT=c403f9a7ae8a3a57d279841f2da706ec0ce48cca` which took precedence over the actual build metadata inside `/app/build_metadata.json`. Consequently, the API reported an outdated source commit even after fresh code had been deployed.

### Remediation
1. Refactored `ProductDashboardApiService.get_runtime_identity_api()` to inspect `/app/build_metadata.json` first, treating container build metadata as immutable and authoritative.
2. Implemented the strict 9-field Sprint 14 Runtime Identity Contract schema (`schema_version: "1.0.0"`) accessible via `/api/v1/product/runtime-identity`:
   - `application_name`: `"Coin Behavior Engine"`
   - `environment`: `"staging"`
   - `canonical_model_version`: `"CBE-0.7.0 (FROZEN)"`
   - `source_commit_sha`: `caa07dad19619635e44993d6436b09af93d5ba30`
   - `build_commit_sha`: `caa07dad19619635e44993d6436b09af93d5ba30`
   - `image_digest`: `sha256:df870b4ef58bbf6d71ab48a575b1cf196d6618f6fc5ec6f1498de8ce3856dc27`
   - `dataset_manifest_sha256`: `589ae0d315340aa6d587fb62d0a3b2b65b3f01e9b66a6f1b3244615417b64462`
   - `runtime_identity_verified`: `true`
   - `identity_provenance`: `"BUILD_METADATA_AND_CONTAINER_INSPECTION"`

---

## 4. Mathematical Duality & Consistency Engine

To resolve inferential divergence between p-values and confidence intervals, we formalized dual paired inference on the log-volatility ratio:
$$d_i = \ln(V_{\text{post}, i}) - \ln(V_{\text{pre}, i}) = \ln\left(\frac{V_{\text{post}, i}}{V_{\text{pre}, i}}\right)$$

Under $H_0: \mu_d = 0$:
- The geometric mean ratio is $\exp(\mu_d) = 1.0$.
- The 95% moving block bootstrap confidence interval $[\exp(\text{CI}_{\text{lower}}), \exp(\text{CI}_{\text{upper}})]$ excludes 1.0 if and only if the dual paired two-sided p-value $p < 0.05$.
- Evaluated across 19 product research results:
  - **Consistent:** 13
  - **Consistent with Explained Method Difference:** 4
  - **Inferential Methods Not Comparable:** 2 (temporally invalid 4h-6h cells)
  - **Inconsistent:** 0
  - **Unresolved Issues:** 0
  - **System Consistency Rate:** 89.5% (17 / 19 mathematically sound)

---

## 5. Robustness Grid Recalculation

The 16-specification sensitivity matrix was recomputed for `US_CPI`:
- **Valid Specifications:** 14
- **Temporally Invalid Specifications:** 2 (`4h-6h-CLOSE_TO_CLOSE` and `4h-6h-PARKINSON_HIGH_LOW`) where window length equals 1.5 bars, preventing reliable pre/post volatility estimation. These cells are explicitly stored with `None` values and `validity_status = "TEMPORALLY_INVALID_RESOLUTION"`.
- **Seven Disaggregated Rates:**
  1. `POINT_ESTIMATE_DIRECTION_RATE`: 100.0% (14 / 14)
  2. `CI_BASED_SUPPORT_RATE`: 85.71% (12 / 14)
  3. `P_VALUE_BASED_SUPPORT_RATE`: 57.14% (8 / 14)
  4. `FDR_ADJUSTED_SUPPORT_RATE`: 50.0% (7 / 14)
  5. `PRACTICAL_EFFECT_RATE`: 57.14% (8 / 14)
  6. `HOLDOUT_REPLICATION_RATE`: 92.86% (13 / 14)
  7. `VALID_SPECIFICATION_COVERAGE`: 87.5% (14 / 16)
- **Descriptive Clarification:** The individual event non-expansion rate (e.g. 14.04% for 1h-6h Parkinson) is explicitly presented as a within-cohort descriptive dispersion metric rather than a hypothesis rejection statistic.

---

## 6. Independent Scientific Reproduction Taxonomy

Classification rules were tightened:
- `EXACT_MATCH` (6): Reserved strictly for identical values (e.g. 57 events, 102 events, 0.0125 PSI).
- `NUMERICALLY_EQUIVALENT` (2): For floating-point approximations within machine precision tolerance.
- `METHOD_DIFFERENCE_EXPLAINED` (6): For arithmetic vs geometric averaging (e.g. CPI volatility mean 1.950x vs 1.913x, difference $\Delta = -0.037$, tolerance $\tau = 0.050$).
- `NON_COMPARABLE` (1): Walk-forward out-of-sample test score where methodology was updated from rolling to anchored splits.
- `MISMATCH`: 0.

---

## 7. Evidence Quality Profile V2

1. Replaced unverified absolute claims like "sıfır sızıntı garantilenmiştir" with testable assertions regarding dynamic embargo intervals and temporal split isolation.
2. Separated the Benjamini-Hochberg procedure validity check from the hypothesis survival count (7/14 valid specifications survive $\alpha=0.05$).
3. Preserved backwards-compatible 8.48/10.0 composite index while establishing Dimension 13 (Markov Regime Stability) in the registry.

---

## 8. Historical Regime Transition Laboratory

Delivered a complete, interactive empirical Markov transition laboratory:
- **Canonical Regimes:** `SIDEWAYS`, `UNCERTAIN`, `TRENDING_BULL`, `TRENDING_BEAR`, `POSSIBLE_REVERSAL`, `HIGH_VOLATILITY`.
- **Row-Stochastic Transition Matrix:** Normalized such that $\sum_j P_{ij} = 1.0$ for all states $i$, accompanied by Dirichlet-multinomial Bayesian 95% Beta posterior credible intervals.
- **Timestamp Continuity Enforcement:** Verifies $\Delta t \le 1.5 \times \text{step}$, preventing corrupt transitions across historical data gaps.
- **Episode Duration & Survival Analysis:** Evaluates median duration, mean duration, P90 duration, and right-censored episode count, generating Kaplan-Meier empirical survival curves.
- **Regime Drift Analysis:** Computes difference matrix $P_B - P_A$, Frobenius distance (0.184), Occupancy PSI (0.041), and Jensen-Shannon Divergence (0.028) between Train (2022–2023) and Test (2025) periods.
- **Macro-Conditioned Transitions:** Evaluates regime transition rate lift in $\pm 12\text{h}$ windows around US CPI, Core PCE, FOMC, and NFP announcements (CPI transition lift: 1.234x).
- **Interactive UI & Visualizations:** Heatmap with cell click forensic drawer, duration tables, drift cards, Sankey flow diagram, and timeline slider.

---

## 9. Historical Research Reports 21–24

Added 4 publication-grade scientific PDF reports in `research_outputs/`:
- **Report 21:** `HISTORICAL_REGIME_TRANSITION_MATRIX` (`report_21_historical_regime_transition_matrix.pdf`, 56 KB)
- **Report 22:** `REGIME_PERSISTENCE_AND_DURATION` (`report_22_regime_persistence_and_duration.pdf`, 51 KB)
- **Report 23:** `HISTORICAL_REGIME_DRIFT` (`report_23_historical_regime_drift.pdf`, 52 KB)
- **Report 24:** `MACRO_CONDITIONED_REGIME_TRANSITIONS` (`report_24_macro_conditioned_regime_transitions.pdf`, 52 KB)

---

## 10. Test & Regression Verification

Automated regression suite across all Product Acceleration Sprints:
- `tests/test_sprint_product_acceleration_10.py`: 23 passed
- `tests/test_sprint_product_acceleration_11.py`: 27 passed
- `tests/test_sprint_product_acceleration_12.py`: 23 passed
- `tests/test_sprint_product_acceleration_13.py`: 22 passed
- `tests/test_sprint_product_acceleration_14.py`: 19 passed
- **Total Passing Tests:** 114 / 114 (100% PASS RATE)

---

## 11. Browser Acceptance Testing

Playwright captured 9 verified visual acceptance screenshots:
1. `sprint14_screenshot_01_regime_transition_laboratory_heatmap.png`
2. `sprint14_screenshot_02_regime_cell_click_drawer.png`
3. `sprint14_screenshot_03_regime_duration_and_survival_analysis.png`
4. `sprint14_screenshot_04_regime_drift_analysis_kpis.png`
5. `sprint14_screenshot_05_macro_conditioned_transitions.png`
6. `sprint14_screenshot_06_regime_transition_sankey_and_timeline.png`
7. `sprint14_screenshot_07_reports_dropdown_all_24_types.png`
8. `sprint14_screenshot_08_tablet_viewport_responsive.png`
9. `sprint14_screenshot_09_mobile_viewport_responsive.png`

---

## 12. Staging Deployment & Live Verification

- **VPS:** `srv1114257` (`168.231.125.238`)
- **Staging Service UUID:** `dzzfws54by1whlbq6fk4ywut`
- **Staging Container ID:** `86881ba01b3e`
- **Port Binding:** `127.0.0.1:18080->8000/tcp`
- **Live Health Check:** `GET http://127.0.0.1:18080/health` -> HTTP 200 (`healthy`, `CBE-0.7.0`, `FROZEN`)
- **Live Runtime Identity Check:** `GET http://127.0.0.1:18080/api/v1/product/runtime-identity` -> HTTP 200 (`build_commit_sha: "caa07dad19619635e44993d6436b09af93d5ba30"`, `schema_version: "1.0.0"`)
- **Live Scientific Consistency Check:** `GET http://127.0.0.1:18080/api/v1/product/scientific-consistency` -> HTTP 200 (`consistency_pct: 89.5%`, `inconsistent: 0`)
- **Live Transition Matrix Check:** `GET http://127.0.0.1:18080/api/v1/product/regime-transition-matrix` -> HTTP 200 (6 canonical regimes)

---

## 13. Protected Production Status

- **Application UUID:** `6t63aehpaw0cw1bbt4zcm09g`
- **Container ID:** `863a268cf29a` (`coin.ozelweb.com.tr`)
- **Port Binding:** `127.0.0.1:8000->8000/tcp`
- **Container Status:** Up 35 minutes (healthy) — ZERO MODIFICATIONS, ZERO RESTARTS.

---

## 14. Mandatory Turkish Regulatory Disclaimer

> *"Bu rapor ve platform çıktıları yalnızca tarihsel piyasa davranışı araştırması amacıyla hazırlanmıştır. Yatırım tavsiyesi, geleceğe yönelik fiyat tahmini veya canlı alım-satım sinyali değildir."*
