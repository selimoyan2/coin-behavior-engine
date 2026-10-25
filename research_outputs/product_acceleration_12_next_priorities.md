# Coin Behavior Engine (CBE) — Sprint 13 Priorities & Technical Roadmap
## Multi-Asset Raw Parquet Ingestion, Continuous Macro Release Sync, Live Experiment Worker & Advanced Visual Analytics

**Project:** Coin Behavior Engine (CBE)  
**Sprint Cycle:** `CBE_PRODUCT_ACCELERATION_13`  
**Base Architecture:** `CBE-0.7.0` (FROZEN)  
**Author:** Quantitative Systems Engineering & Research Architecture  
**Date:** 2026-10-25  

---

## 1. Context and Objective

With Sprint 12 delivering the Visual Research Builder, Independent Scientific Reproduction Engine, Interactive Historical Distribution Laboratory, and Portable Experiment Packages, Coin Behavior Engine has achieved a complete, reproducible research workflow.

Sprint 13 will focus on expanding data asset coverage, automating macro event ingestion pipelines, providing asynchronous experiment execution, and deepening interactive visual analytics.

---

## 2. Priority Capabilities for Sprint 13

### Priority 1: Multi-Asset Authentic Parquet Ingestion Pipeline
- **Problem:** Currently, only `BTCUSDT` has fully verified multi-year spot Parquet partitions. `ETHUSDT` and `SOLUSDT` are correctly classified as `SOURCE_NOT_AVAILABLE` under zero-synthetic rules.
- **Goal:** Ingest authentic historical multi-year 15m, 1h, 4h, and 1d Parquet partitions for `ETHUSDT` and `SOLUSDT` covering 2021–2026.
- **Verification:** Generate cryptographic SHA-256 manifests, verify continuous timestamp monotonicity, validate zero-imputation integrity, and unlock multi-asset cross-pair hypothesis testing in Visual Research Builder V2.

### Priority 2: Automated Macro Event Calendar Synchronizer
- **Problem:** Macroeconomic event data currently resides in static Parquet files (`historical_macro_events_11_23.parquet`).
- **Goal:** Build an automated synchronizer for Bureau of Labor Statistics (BLS) and Federal Reserve official release calendars.
- **Guardrails:** Synchronize only verified historical release timestamps; maintain immutable lineage logs; update the canonical taxonomy hierarchy (`US_INFLATION` parent $\rightarrow$ `US_CPI` child) with automatic schema verification.

### Priority 3: Interactive Specification Curve & Sensitivity Visualization
- **Problem:** Specification curve data is computed accurately in `robustness_explorer.py` and rendered in PDF Report 15, but frontend users interact with a tabular summary.
- **Goal:** Introduce an interactive SVG/HTML5 canvas-based specification curve chart in the web UI allowing researchers to click on individual specification points (e.g. 12h Close-to-Close vs 24h Parkinson) to view underlying sub-cohort candle plots and distribution shifts.

### Priority 4: Background Experiment Execution Queue & Worker Service
- **Problem:** Heavy bootstrap simulations (1,000 iterations across multiple epochs) execute synchronously within HTTP requests, capped at small sample sizes to avoid HTTP gateway timeouts.
- **Goal:** Implement an in-memory background worker queue with progress polling (`/api/v1/product/experiment-jobs/{id}/progress`) enabling 10,000-sample block bootstraps without blocking the dashboard event loop.

### Priority 5: Advanced Visual Distribution Comparison Widgets
- **Problem:** Distribution comparisons present static histograms and ECDFs.
- **Goal:** Enhance the Distribution Laboratory with interactive quantile-quantile (Q-Q) plots, Kernel Density Estimation (KDE) overlays, and dynamic bin width controls (Freedman-Diaconis rule vs Sturges rule).

### Priority 6: Automated Research Package Registry & GitOps Export
- **Problem:** Portable `.cbe-hyp.json` packages are exported locally.
- **Goal:** Integrate a versioned research experiment registry with automated Git commit hooks for collaborative team research reproducibility.

---

## 3. Mandatory Governance & Safety Constraints

1. **Zero-Touch Production Policy:** Production container `8a2bd64c1529` on port 8000 (`coin.ozelweb.com.tr`) must never be touched, stopped, restarted, or altered.
2. **Zero Price Fabrication:** No synthetic interpolation or imputed candlestick generation allowed.
3. **Mandatory Disclaimer:** All UI views, notebooks, and reports must present the Turkish legal disclaimer:
   > *"Bu rapor tarihsel veri araştırması amacıyla hazırlanmıştır. Yatırım tavsiyesi veya canlı alım-satım sinyali değildir."*
