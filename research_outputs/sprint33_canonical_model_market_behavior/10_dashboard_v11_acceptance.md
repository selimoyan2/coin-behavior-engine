# Investment Research Dashboard V11 Acceptance Report
**Sprint ID:** CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR  
**Date:** 2026-11-15  
**Auditor:** CBE Autonomous Engineering Agent  
**Baseline Git SHA:** `c9e3907a226cfbe01e73f87c960156afdd874dc4`  
**Dashboard Version:** `Investment Research Dashboard V11 (Market Behavior Intelligence)`  
**Operational Status:** `ACCEPTED_AND_VERIFIED`  

---

## 1. Overview & Scope

Dashboard V11 expands the research workspace delivered in Sprint 32 (V10) by integrating empirical **Market Behavior Intelligence** powered by the authoritative `CBE-0.7.0` canonical model bridge.

### Core Sections Delivered & Verified (I1 through I7):

1. **I1 — Model Status Banner:**
   - Real-time indicator displaying `CBE-0.7.0` frozen status, lockbox verification (29/29 artifacts verified), active fallback level (`SPOT_ONLY_U0`), and feature availability (%54.55).
   - Clear legal disclaimer: `TARİHSEL PİYASA DAVRANIŞ İSTİHBARATI — CANLI AL-SAT SİNYALİ ÜRETMEZ`.

2. **I2 — Regime Explorer:**
   - Full historical regime distribution across 2023–2024 and 2025.
   - Persistence metrics table (Mean duration, median, 75th percentile, and max duration in hours).
   - Interactive 24-hour empirical transition matrix ($P(R_{t+24h} | R_t)$) with conditional color-coded probability cells.

3. **I3 — Forward Return Explorer:**
   - Multi-horizon return distribution explorer supporting 6h, 24h, 72h, and 168h (7 days).
   - Statistical telemetry: Sample size, mean return %, median %, standard deviation %, skewness, excess kurtosis, win rate %, 5th percentile (VaR), and 95th percentile.
   - Historical subperiod stability breakdown (2023 Bull Run, 2024 Pre-Halving, 2024 Post-Halving, 2025 Sealed Period).

4. **I4 — Risk Intelligence Panel:**
   - Downside risk profiling by regime.
   - Maximum Adverse Excursion (MAE) analysis: Mean MAE %, median MAE %, maximum drawdown %, and 5% threshold.
   - Left-tail risk metrics: VaR-95, CVaR-95 (Expected Shortfall), and CVaR-99.
   - Clear risk isolation findings highlighting `TAIL_RISK_ELEVATED` severity (-9.14% CVaR-95 vs. -3.12% in `QUIET`).

5. **I5 — Model Comparison View:**
   - Side-by-side comparative analysis between Canonical `CBE-0.7.0` (9/6 states) and Derived Research Heuristic (6 states).
   - Cross-tabulation confusion matrix and conceptual concordance metrics (67.4% alignment).
   - Epistemological guidance strictly separating production model outputs from exploratory laboratory heuristics.

6. **I6 — Scientific Evidence Ledger:**
   - Comprehensive inventory of all 21 research artifacts produced in Sprint 33.
   - File IDs, descriptions, media types, and verification badges (`VERIFIED`).

7. **I7 — Deployment Safety Status:**
   - Real-time telemetry on production container `4c6a29b5fbf6` (Port 8000, 0 restarts, healthy, strict zero-touch preserved).
   - Staging environment status (Port 18080, healthy).
   - Coolify deployment trigger audit summary and Option 3 isolation confirmation.
   - Permanent live trading prohibition lock (`HTTP 403 Forbidden`).

---

## 2. API Endpoint Verification Summary

All 7 dedicated V11 API endpoints were tested and verified with `HTTP 200 OK`:

| Endpoint Route | Status Code | Latency (Local) | Payload Size |
|---|:---:|:---:|:---:|
| `/api/v1/product/btc-timing/v11/model-status` | 200 OK | < 5 ms | 1.1 KB |
| `/api/v1/product/btc-timing/v11/regime-explorer` | 200 OK | < 8 ms | 3.4 KB |
| `/api/v1/product/btc-timing/v11/forward-returns` | 200 OK | < 12 ms | 5.2 KB |
| `/api/v1/product/btc-timing/v11/risk-intelligence` | 200 OK | < 6 ms | 3.1 KB |
| `/api/v1/product/btc-timing/v11/model-comparison` | 200 OK | < 7 ms | 2.8 KB |
| `/api/v1/product/btc-timing/v11/evidence-ledger` | 200 OK | < 4 ms | 3.6 KB |
| `/api/v1/product/btc-timing/v11/deployment-safety` | 200 OK | < 3 ms | 0.9 KB |

---

## 3. UI Acceptance & Epistemic Standards

- **Zero Console Errors:** JavaScript controllers use safe null checks and defensive DOM selectors.
- **Responsive Layout:** Grid and table containers feature horizontal scrolling (`overflow-x: auto`) for mobile and tablet viewports.
- **Epistemological Integrity:** Prominent visual warnings prevent misinterpretation of descriptive market intelligence as trading recommendations.
