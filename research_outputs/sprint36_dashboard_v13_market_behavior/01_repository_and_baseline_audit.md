# Sprint 36 — Repository, Baseline & Governance Audit

**Sprint ID:** `CBE_SPRINT36_DASHBOARD_V13_MARKET_BEHAVIOR_INTELLIGENCE`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Working Research Branch:** `research/sprint36-dashboard-v13-market-behavior`  
**Production Release Baseline SHA:** `f342e40546eca538db54d8d32861f6946617dd0b`  
**Documentation Release Baseline HEAD:** `d8b59b35203338ca8b4311707632cc204a83a0cc`  
**Canonical Model Version:** `CBE-0.7.0` (`STRICTLY_FROZEN`)  
**Research Mode:** `STRICTLY_OFFLINE_RESEARCH`  
**Live Trading Execution:** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden)  
**Production Staging Target:** `srv1114257` (`root@168.231.125.238`), Port `18080`  
**Production Container Invariant:** `d20a430d9704` on port `8000` (`STRICT_ZERO_TOUCH`)  

---

## 1. Audit Summary

1. **Production Isolation:** Production container `d20a430d9704` runs on port 8000 and serves `https://coin.ozelweb.com.tr`. It remains completely untouched throughout Sprint 36.
2. **Branch Lineage:** Research branch `research/sprint36-dashboard-v13-market-behavior` branched cleanly from baseline `d8b59b35203338ca8b4311707632cc204a83a0cc`.
3. **Data Completeness:** 58 complete months (2022-01 to 2026-10) + 1 partial verified month (2026-11 ending 2026-11-15 21:15 UTC).
4. **Zero Lookahead & Causal Separation:** All regime classifications, transition probabilities, and downside volatility metrics are strictly point-in-time.
