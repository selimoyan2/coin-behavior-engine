# Sprint 37 — Repository Baseline, Scope & Governance Architecture

**Sprint ID:** `CBE_SPRINT37_MARKET_REGIME_PREDICTIVE_VALIDITY_LAB_V3`
**Repository:** `selimoyan2/coin-behavior-engine`
**Branch:** `research/sprint37-predictive-validity`
**Verified Production Application SHA:** `313fc5ca242e497f1e221002c798fc5910bd6284`
**Canonical Model:** `CBE-0.7.0` (STRICTLY_FROZEN)
**Execution Mode:** `STRICTLY_OFFLINE_RESEARCH`
**Live Trading:** `PERMANENTLY_PROHIBITED`
**Production Deployment:** `NOT_AUTHORIZED` (`STRICT_ZERO_TOUCH`)

---

## 1. Mission & Objective
The objective of Sprint 37 is to scientifically test whether the 6 canonical market regimes (`SIDEWAYS`, `UNCERTAIN`, `TRENDING_BULL`, `TRENDING_BEAR`, `POSSIBLE_REVERSAL`, `HIGH_VOLATILITY`) carry statistically reliable, temporally reproducible, and economically meaningful predictive information regarding future price dynamics across 5 forward horizons (1h, 4h, 12h, 24h, 72h), or if they are purely descriptive ex-post labels.

Scientific integrity dictates that negative or null findings must be reported transparently without inventing speculative alpha or falsifying results.

## 2. Governance Constraints
- **Model Freeze:** Zero modifications to `CBE-0.7.0` model architecture, parameters, or feature weights.
- **Production Zero-Touch:** The live production environment at `https://coin.ozelweb.com.tr` (container `b2cb2c5b662d` on port 8000) remains untouched.
- **Staging Deployment:** Authorized for isolated staging container on port 18080 only.
- **Trading Prohibition:** All live order endpoints return HTTP 403 Forbidden.
