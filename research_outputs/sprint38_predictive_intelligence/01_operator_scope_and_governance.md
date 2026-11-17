# CBE — SPRINT 38: OPERATOR SCOPE AND GOVERNANCE SPECIFICATION

**Sprint ID:** `CBE_SPRINT38_DASHBOARD_V15_EVIDENCE_EXPLORER`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Research Branch:** `research/sprint38-dashboard-v15-evidence-explorer`  
**Candidate Commit SHA:** `51cb27697814164983ade0016b5260709c68a33e`  
**Production Baseline SHA:** `c0951f67f2b6045a1c37c2278e69e4a3d467ffeb`  
**Operator Authorization:** RESEARCH & STAGING READINESS ONLY  
**Production Deployment:** OPERATOR_APPROVAL_REQUIRED (STRICT ZERO-TOUCH)  
**Live Trading Execution:** PERMANENTLY_PROHIBITED (HTTP 403 Forbidden)  
**Canonical Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  

---

## 1. SCOPE SUMMARY
Sprint 38 transforms the verified predictive validity research from Sprint 37 into Dashboard V15:
1. **Interactive Evidence Explorer:** 30 evaluated hypotheses with statistical effect sizes, 95% bootstrap CIs, HAC standard errors, FDR q-values, and click-to-inspect scientific modal.
2. **Volatility Forecast Benchmark Laboratory:** Statistically significant superior volatility forecasting vs GARCH(1,1) (Regime RMSE 16.0612 vs GARCH 17.4578, Diebold-Mariano p < 1e-5).
3. **Market Regime Persistence Intelligence:** Empirical Markov transitions and duration quantiles with explicit Tier 1 Nominal vs Tier 2 Analytical regime governance boundaries (`CANONICAL_PARITY_NOT_ESTABLISHED`).
4. **Directional Predictability Reality Check:** Transparently reporting 25 rejected directional hypotheses and +0.0518% unconditional drift with the mandatory Turkish disclaimer:
   > *"Yönsel fiyat tahmininde istatistiksel olarak güvenilir bir üstünlük henüz doğrulanmamıştır."*
5. **Statistical Confidence & Uncertainty Engine:** Block bootstrap (B=500), Newey-West HAC, and Benjamini-Hochberg FDR / Holm FWER.
6. **Scientific Limitations & Rejected Findings:** Complete transparency on 30 bps transaction cost drag and absence of directional edge.
7. **Historical Research Comparison:** Sprints 35-38 continuity across 59 months (Oct 2021 - Aug 2026, 42,717 hourly bars, 0 synthetic bars).

## 2. GOVERNANCE BOUNDARIES
- **Model Invariance:** Model weights, hyperparameters, and classification heuristics are strictly frozen in `CBE-0.7.0`.
- **Trading Prohibition:** All live order execution and trade endpoints return HTTP 403 Forbidden with `GOVERNANCE_VIOLATION`.
- **Zero-Touch Production:** Production container `46bfe4cf2031` at `https://coin.ozelweb.com.tr` remains running untouched with 0 restarts.
