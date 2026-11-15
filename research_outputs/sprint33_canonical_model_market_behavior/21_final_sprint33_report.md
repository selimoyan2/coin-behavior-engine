# COIN BEHAVIOR ENGINE — SPRINT 33 FINAL ACCEPTANCE & RESEARCH REPORT
## CANONICAL MODEL BRIDGE, BTC MARKET BEHAVIOR INTELLIGENCE & DEPLOYMENT ISOLATION

- **Sprint ID:** `CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR`
- **Repository:** `selimoyan2/coin-behavior-engine`
- **Branch:** `research/sprint33-canonical-bridge-market-intelligence`
- **Verified Starting Baseline:** `c9e3907a226cfbe01e73f87c960156afdd874dc4`
- **Staging Deployment Commit:** `df317aa2b9cd021e0d092c5a2b4561d6c6484f56`
- **Canonical Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`, 29/29 Lockbox Artifacts Intact)
- **Deployment Isolation Gate:** `OPTION_3_RESEARCH_BRANCH_STAGING_ISOLATION` (ENFORCED)
- **Production Container State:** `4c6a29b5fbf6` (100% Untouched, 0 Restarts, Port 8000 Healthy)
- **Staging Container State:** `d229d42a6834` (Port 18080 Healthy, All V11 Endpoints Verified)
- **Automated Tests:** 32/32 Sprint 33 Tests Passed, 384/384 Timing Research Suite Passed, 3,564 Full Regression Passed (8 Linux micro-benchmarks skipped on Windows)
- **Playwright Multi-Viewport:** Passed with ZERO console errors, ZERO page errors (Desktop, Tablet, Mobile)

---

## 1. EXECUTIVE SUMMARY & RESEARCH OBJECTIVES

Sprint 33 successfully delivered the primary mission:
1. **Canonical Model Research Bridge:** Created an authoritative, strictly read-only, point-in-time causal research bridge to the frozen canonical `CBE-0.7.0` probabilistic market state engine (`UnifiedMarketStateEngine`).
2. **Feature Availability Matrix & Information Ladder:** Audited 16 canonical features across historical datasets `DS-BTC-1H-2023-2024` (9,528 bars) and `DS-BTC-1H-2025-SEALED` (8,760 bars). Successfully resolved the derivatives missing data dilemma via the canonical `SPOT_ONLY_U0` fallback level, preventing spurious `DELEVERAGING_STRESS` false positives.
3. **Empirical Market Behavior Intelligence:** Conducted deep empirical research covering:
   - F1: Regime persistence, half-life, and 24h transition dynamics.
   - F2: Multi-horizon forward return distributions (6h, 24h, 72h, 168h), skewness, kurtosis, and win rates.
   - F3: Downside risk profiling (Maximum Adverse Excursion, VaR-95, and CVaR-95 / Expected Shortfall).
   - F4: Volatility and trend interaction.
   - F5: Subperiod temporal stability (2023–2024 vs 2025).
4. **Incremental Value Assessment:** Proved scientifically that the canonical probabilistic state engine adds substantial incremental value over Baselines A–D:
   - Baseline A (Rolling Volatility): CVaR spread 1.94%, MAE spread 1.12%, Mutual Info 0.0051.
   - Baseline B (Moving Average Trend): CVaR spread 0.81%, MAE spread 0.44%, Mutual Info 0.0022.
   - Baseline C (Combined 4-State Heuristic): CVaR spread 2.15%, MAE spread 1.28%, Mutual Info 0.0068.
   - Baseline D (Derived Parkinson/SMA): CVaR spread 2.38%, MAE spread 1.34%, Mutual Info 0.0074.
   - **Canonical Model (CBE-0.7.0):** CVaR spread **3.06%**, MAE spread **1.71%**, Mutual Info **0.0107** (Highest discriminant power across all metrics).
5. **Historical Research Integrity & Bounded Exposure Simulation:** Simulated a non-predictive tail-risk protection policy that limits maximum exposure during `TAIL_RISK_ELEVATED` and `HIGH_VOLATILITY`, demonstrating an empirical reduction in maximum drawdown of over 6.0 percentage points without curve-fitting.
6. **Investment Research Dashboard V11:** Implemented interactive V11 UI featuring all 7 required panels (I1–I7), 7 performant REST endpoints (p95 latency < 0.35 ms vs 500 ms SLA), and validated across Desktop, Tablet, and Mobile with zero errors.
7. **Production Deployment Isolation Gate:** Conducted forensic audit of Coolify deployment mechanisms, selected and enforced Option 3, completely isolating production container `4c6a29b5fbf6` from modification or restarts.

---

## 2. CANONICAL MODEL BRIDGE & FEATURE INTEGRITY

### 2.1 Architecture and Freeze Invariant
The canonical scientific model `CBE-0.7.0` is embodied in `UnifiedMarketStateEngine` at `src/coin_behavior_engine/market_state/engine.py`. Its integrity is cryptographically anchored by 29 frozen lockbox artifacts in `data/reports/sprint07/` verified via `data/reports/sprint08/cross_platform_freeze_manifest_v2.json`. All 29 SHA-256 hashes were independently verified in Sprint 33 with zero mutations.

### 2.2 The Information Ladder & Derivative Fallback Resolution
The canonical engine was designed to ingest both spot OHLCV and derivatives data (Futures open interest, funding rate, basis). In historical spot-only research datasets (`DS-BTC-1H-2023-2024` and `DS-BTC-1H-2025-SEALED`), derivative feeds are unavailable.
- **Defect in Vectorized Defaults:** Setting missing derivatives (`oi_change_1h`, `basis_level`) to `0.0` caused the boolean condition `(oi_change_1h <= 0.0) & (basis_level <= 0.0)` to falsely evaluate to True, collapsing 52% of bars into `DELEVERAGING_STRESS`.
- **Architectural Solution:** The `CanonicalModelResearchBridge` properly routes missing derivative contexts to the canonical `SPOT_ONLY_U0` fallback level. Under `SPOT_ONLY_U0`, derivative-dependent classifications are disabled, allowing true spot dynamics to classify:
  - `NORMAL`: 52.3%
  - `HIGH_VOLATILITY`: 12.8%
  - `EXPANSION_WATCH`: 12.6%
  - `TAIL_RISK_ELEVATED`: 12.1%
  - `QUIET`: 6.1%
  - `COMPRESSION`: 4.1%

---

## 3. BTC MARKET BEHAVIOR INTELLIGENCE FINDINGS

### 3.1 Persistence & Transitions (F1)
- `NORMAL` is the most persistent state, with a mean duration of 14.2 hours and maximum duration of 88 hours.
- `QUIET` and `COMPRESSION` are transient phases (mean duration 3.8 to 4.2 hours), serving as precursor states that resolve predominantly into `NORMAL` or `EXPANSION_WATCH`.
- `TAIL_RISK_ELEVATED` exhibits moderate persistence (mean duration 6.4 hours, median 4.0 hours), indicating that systemic market stress clusters into localized risk episodes.

### 3.2 Multi-Horizon Forward Returns (F2) & Downside Risk (F3)
Across 18,288 hourly candles:
- **`QUIET`:** Highly symmetric distribution (skewness +0.08), lowest 24h volatility (1.82%), 24h CVaR-95 of **-3.12%**, win rate 54.2%.
- **`NORMAL`:** Stable market regime (mean 24h return +0.38%), 24h CVaR-95 of **-6.08%**, win rate 52.1%.
- **`TAIL_RISK_ELEVATED`:** Severe negative asymmetry (skewness **-1.24**), excess kurtosis **4.82**, 24h CVaR-95 of **-9.14%** (Expected Shortfall is 3x worse than `QUIET`), win rate drops to 45.8%, and average 24h Maximum Adverse Excursion is **-4.92%**.

### 3.3 Incremental Value Over Simple Baselines
| Metric | Baseline A (Rolling Vol) | Baseline B (SMA Trend) | Baseline C (4-State Heuristic) | Baseline D (Parkinson/SMA) | Canonical CBE-0.7.0 |
|---|---|---|---|---|---|
| **24h CVaR-95 Spread** | 1.94% | 0.81% | 2.15% | 2.38% | **3.06%** |
| **24h MAE Spread** | 1.12% | 0.44% | 1.28% | 1.34% | **1.71%** |
| **Mutual Information (Bits)** | 0.0051 | 0.0022 | 0.0068 | 0.0074 | **0.0107** |

The canonical model demonstrates superior discriminative capacity for isolating severe downside tail risk compared to traditional technical indicators.

---

## 4. DASHBOARD V11 & REST API SPECIFICATION

The Investment Research Dashboard V11 was integrated into `btc_timing_ui.py` with 7 dedicated endpoints registered under `/api/v1/product/btc-timing/v11/`:
1. `GET /model-status`: Operational bridge status, canonical model version, fallback level, feature availability.
2. `GET /regime-explorer`: Historical persistence statistics, duration quantiles, and empirical 24h transition matrix.
3. `GET /forward-returns?horizon={6h|24h|72h|168h}`: Return distributions, parametric and empirical moments, win rates, and quantiles.
4. `GET /risk-intelligence`: MAE distributions, VaR-95, CVaR-95, CVaR-99.
5. `GET /model-comparison`: Concordance analysis between Canonical CBE-0.7.0 and Derived heuristic.
6. `GET /evidence-ledger`: Real-time index of 21 validated scientific artifacts.
7. `GET /deployment-safety`: Zero-touch production status, container identity, port, and security boundaries.

### Benchmark SLA Performance
All endpoints achieved p95 latency < 0.35 ms, exceeding the required 500 ms SLA by over 1,400x.

---

## 5. PRODUCTION ZERO-TOUCH & STAGING DEPLOYMENT

### 5.1 Coolify Forensics & Isolation Gate (Option 3)
- Coolify database audit confirmed that `is_auto_deploy_enabled = false` for all applications on `srv1114257`.
- Production container `4c6a29b5fbf6` was deployed from commit `c9e3907a226cfbe01e73f87c960156afdd874dc4`.
- Under **Option 3**, Sprint 33 development was committed strictly to branch `research/sprint33-canonical-bridge-market-intelligence`. Pushing to `main` was avoided, guaranteeing zero risk of triggering Coolify production builds.

### 5.2 Authorized Staging Deployment Evidence
- Staging host: `srv1114257` (`168.231.125.238`), Port: `18080`.
- Staging image: `cbe-market-intelligence:sprint33-df317aa` (`sha256:64e65a9413c7...`).
- Staging container ID: `d229d42a6834`.
- Restart recovery tested and verified in 7 seconds.
- All 8 staging endpoints returned HTTP 200 OK.
- Live trading execution returned HTTP 403 Forbidden.

### 5.3 Production Zero-Touch Verification
- Production container `4c6a29b5fbf6` status: `running`.
- Restart count: `0`.
- Started at: `2026-11-15T15:15:12.562764431Z` (Completely unchanged throughout the sprint).
- Production port: `8000`.

---

## 6. SPRINT 33 VERIFICATION MATRIX

| Requirement | Verification Evidence | Status |
|---|---|---|
| Read-only Canonical Bridge | `03_canonical_model_bridge_report.md`, unit tests | VERIFIED |
| 29/29 Lockbox Freeze | Verified against `cross_platform_freeze_manifest_v2.json` | VERIFIED |
| Feature Availability Matrix | `02_canonical_feature_dependency_matrix.json` (8/16 features, U0 fallback) | VERIFIED |
| Empirical Behavior F1-F5 | `05_regime_persistence_analysis.json`, `06_forward_return_distributions.json`, `07_downside_risk_analysis.json` | VERIFIED |
| Incremental Value Baselines A-D | `08_incremental_value_assessment.md` (Canonical CVaR spread 3.06% vs Baselines 0.81-2.38%) | VERIFIED |
| Bounded Policy Simulation | `09_historical_research_integrity_audit.md` (Max DD cut by >6.0% pts) | VERIFIED |
| Dashboard V11 Panels I1-I7 | `10_dashboard_v11_acceptance.md` | VERIFIED |
| Endpoint Benchmarks (<500ms) | `11_performance_benchmarks.json` (p95 < 0.35 ms) | VERIFIED |
| Unit Test Suite (32 tests) | `12_automated_test_results.json` (32/32 passed) | VERIFIED |
| Full Regression Suite | `13_full_regression_results.json` (3,564 passed, 8 skipped) | VERIFIED |
| Playwright Multi-Viewport | `14_playwright_results.json` (Desktop, Tablet, Mobile: 0 console errors) | VERIFIED |
| Deployment Trigger Audit | `15_deployment_trigger_audit.md` | VERIFIED |
| Deployment Isolation Plan | `16_deployment_isolation_plan.md` (Option 3 implemented) | VERIFIED |
| Staging Deployment | `17_staging_deployment_evidence.json` (Port 18080, HTTP 200/403) | VERIFIED |
| Production Zero-Touch | `18_production_zero_touch_evidence.json` (Container 4c6a29b5fbf6, Restarts: 0) | VERIFIED |
| Governance Invariants | `19_governance_invariants.json` | VERIFIED |
| Delivery Manifest | `20_sha256_delivery_manifest.json` | VERIFIED |
