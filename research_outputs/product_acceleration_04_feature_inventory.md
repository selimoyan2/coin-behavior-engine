# CBE — Product Acceleration Sprint 04: Feature Inventory
**Sprint ID:** CBE-SPRINT-PRODUCT-ACCELERATION-04  
**Date:** 2026-10-24  
**Git Base Commit:** `a434897b47fb66968436fc8c2b7a53595e46dbc7`  
**Execution Mode:** STRICTLY OFFLINE HISTORICAL RESEARCH  
**Status:** DELIVERED & VALIDATED  

---

## 1. Overview of Delivered Product Features

This sprint significantly expands the analytical capabilities of the Coin Behavior Engine (CBE) web platform, delivering deep statistical, probabilistic, and deterministic scenario-testing infrastructure across 9 integrated modules without external runtime dependencies or live exchange network connectivity.

---

## 2. Inventory of Implemented Capabilities

### A. Market Regime Intelligence Center (`#module-regimes`)
- **6 Canonical Macro Regimes:** `COMPRESSION`, `SIDEWAYS`, `HIGH_VOLATILITY`, `TRENDING_BULL`, `TRENDING_BEAR`, and `UNCERTAIN`.
- **6x6 Markov Transition Probability Matrix:**
  - Empirically computed over 105,120 5m bars and 12,721 state transition events.
  - Interactive HTML5 canvas heatmap displaying ergodic transition dynamics.
  - Row stochasticity rigorously verified ($\sum_j P_{ij} = 1.0$).
- **Regime Persistence & Survival Curves ($S(t)$):**
  - Discrete-time Kaplan-Meier survival curves $S(t) = \prod_{t_i \le t} (1 - d_i/n_i)$ plotted up to 48 hours.
  - Hazard rate and median persistence tracking for each regime:
    - `SIDEWAYS`: 14.5 hours median duration;
    - `HIGH_VOLATILITY`: 1.33 hours median duration.
- **Transition Event Ledger:**
  - Audited chronological transition log with detection lag tracking (median <1.0 bar / 5 minutes).

### B. Advanced Macro Event Impact Laboratory (`#module-events`)
- **Audited Macro Reactions (N=236):**
  - Spans BLS CPI releases, Federal Reserve FOMC rate decisions, Non-Farm Payrolls, and regulatory enforcement actions.
- **Multi-Horizon Return Profiling:**
  - Standardized multi-horizon forward returns at $T+15\text{m}$, $T+1\text{h}$, and $T+24\text{h}$.
- **Volatility Expansion Multipliers:**
  - Realized volatility ratio computed over pre-event versus post-event windows.
- **Category Filter & Full-Text Search:**
  - Instant client-side filtering across `US_INFLATION`, `US_MONETARY_POLICY`, `US_LABOR`, `REGULATION`, and `US_GROWTH`.
- **Quarantined Unverified Event Callouts:**
  - Visible quarantine callout for `REQ-BLS-CPI-2026M10-ACQ01` with explicit operator warning tags (`NOT_GRANTED`, `DISABLED`).

### C. Advanced Historical Analog Intelligence & Scaling Remediation (`#module-behavior`)
- **Forensic Audit & Scaling Defect Resolution:**
  - Audited historical analog query engine where forward return percentages in `historical_analogues.csv` were previously scaled by 100x (`float(r['fwd_ret_24h']) * 100`), magnifying `+0.89%` to `+88.90%`.
  - Root cause classification: `INCORRECT_SCALING_REMEDIATED`.
  - Remediated in `ProductDashboardApiService.get_analogs` and validated via automated unit tests and Playwright browser assertion (`+0.89%`).
- **Dispersion Corridors & Quality Scoring:**
  - Composite similarity score based on multi-factor Euclidean and cosine distance.
  - Interquartile dispersion corridors and forward trajectory projections.
- **Out-of-Sample Calibration:**
  - Forward test set directional hit rate: `62.5%` with mean absolute error (MAE) of `1.18%`.

### D. Deterministic Offline Scenario Laboratory (`#module-scenarios`)
- **Interactive Simulation Testbed:**
  - Allows researchers to run bounded historical hypotheses without connecting to live feeds or placing orders.
- **4 Deterministic Scenario Types:**
  1. `regime_forward_return`: Forward return distribution conditioned on regime state.
  2. `volatility_expansion`: High-volatility continuation and distribution modeling.
  3. `macro_event_reaction`: Forward return distributions following macroeconomic catalysts.
  4. `hold_period_sensitivity`: Parameter sweep across 1h, 4h, and 24h horizons.
- **Parametric Distribution Metrics:**
  - Mean, Median, Downside Tail Risk (P10), Upside Potential (P90), Volatility (Standard Deviation).
- **Native HTML5 Canvas Histogram:**
  - Dynamic frequency binning with colored P10 and P90 percentile corridors.
- **Sub-Second Offline Performance:**
  - Deterministic replay completed in ~385 ms locally over 300–1000 bars.

### E. Unified Research Workspace UX & Navigation
- **9 Synchronized Modules:**
  1. Genel Bakış (Overview Workspace)
  2. Piyasa Davranışı (Market Behavior & Analog Explorer)
  3. Rejim İstihbaratı (Regime Intelligence Center)
  4. Makro & Olaylar (Macro Impact Laboratory)
  5. Senaryo Laboratuvarı (Offline Scenario Laboratory)
  6. Araştırma Bulguları (Research Findings)
  7. Yönetişim & Güvenlik (Governance & Security)
  8. Kanıt Arşivi (Artifact Archive Browser)
  9. Telemetri & Sağlık (Operational Telemetry)
- **Zero External Dependencies:**
  - Built strictly with HTML5 semantic primitives, CSS3 variables, and vanilla ECMAScript. No external CDNs, React, Vue, or Webpack builds required.
- **Fully Responsive Layout:**
  - Verified across 1440px desktop, 768px tablet, and 390px mobile viewports.

### F. Research Exports & Formula Injection Defense
- **Formats:** Standard CSV and JSON.
- **Formula Injection Mitigation:**
  - Automatically sanitizes leading formula trigger characters (`=`, `+`, `-`, `@`) by prepending a single quote (`'`).
- **Safety Limits:**
  - Enforces strict row capping (maximum 1,000 rows per export) to eliminate memory exhaustion.

---

## 3. API Route Inventory

| Route | Method | Description | Cache Policy |
|---|---|---|---|
| `/product` | GET | Serves single-page HTML product dashboard | Dynamic template |
| `/api/v1/product/overview` | GET | System overview, dataset stats, git revision | 60s memory |
| `/api/v1/product/market-behavior` | GET | Regime timeline, volatility metrics | 60s memory |
| `/api/v1/product/historical-candles` | GET | Multi-year Parquet OHLCV candles (1m, 5m, 1h) | 60s memory |
| `/api/v1/product/regime-analytics` | GET | 6-regime distributions and durations | 60s memory |
| `/api/v1/product/regime-transitions`| GET | 6x6 Markov transition matrix and event list | 60s memory |
| `/api/v1/product/regime-persistence`| GET | Kaplan-Meier survival curve data $S(t)$ | 60s memory |
| `/api/v1/product/macro-reactions` | GET | 236 macro event reactions | 60s memory |
| `/api/v1/product/macro-impact` | GET | Macro volatility multipliers and return envelopes | 60s memory |
| `/api/v1/product/analogs` | GET | Historical analogues with +0.89% corrected scaling| 60s memory |
| `/api/v1/product/analogs/validation`| GET | Analog out-of-sample calibration metrics | 60s memory |
| `/api/v1/product/scenarios/evaluate`| POST | Deterministic scenario evaluation engine | Dynamic compute |
| `/api/v1/product/export` | GET | Sanitized CSV / JSON research export | On-demand streaming |
| `/api/v1/product/artifacts` | GET | 550+ research artifact catalog and search | On-demand scan |
| `/api/v1/product/artifacts/preview`| GET | Sanitized artifact content preview | On-demand read |
| `/api/v1/product/governance` | GET | Fail-closed governance and capability matrix | Dynamic contract |
