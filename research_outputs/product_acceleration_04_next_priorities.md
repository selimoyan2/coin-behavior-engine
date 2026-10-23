# CBE — Product Acceleration Sprint 04: Next Priorities

**Sprint ID:** CBE-SPRINT-PRODUCT-ACCELERATION-04  
**Date:** 2026-10-24  
**Status:** FORWARD-LOOKING ROADMAP  

---

## Strategic Product Recommendations for Sprint 05

Following the successful delivery and staging verification of Sprint 04, the following initiatives are prioritized:

### 1. High-Priority Research & Analytics Expansion
- **Continuous Multi-Asset Parquet Catalog:** Expand offline research dataset catalog from BTCUSDT to include ETHUSDT and SOLUSDT multi-year 1m/5m/1h archives.
- **Cross-Regime Analog Matching:** Allow analog pattern search to condition on matching both price action geometry and underlying macro regime state simultaneously.
- **Parametric VaR & Expected Shortfall (CVaR):** Integrate explicit Cornish-Fisher Value-at-Risk ($95\%$ and $99\%$) into the Deterministic Scenario Laboratory.

### 2. UI / UX Enhancements
- **Multi-Chart Synchronized Crosshair:** Support dual-pane synchronized scrolling between candlestick bars and the regime timeline canvas.
- **Scenario Comparison Deck:** Enable side-by-side comparison of two distinct deterministic scenarios (e.g., `SIDEWAYS 4h` vs `COMPRESSION 4h`).
- **Dark/Light Theme Toggle:** Maintain research readability in low-light trading desk environments.

### 3. Governance & Safe Staging Automation
- **Automated Coolify Webhook Sync:** Configure direct Coolify deploy webhooks for `cbe-market-intelligence-staging` on push to staging branches.
- **Artifact Signing & Hash Attestation:** Integrate cryptographic Ed25519 signatures directly into the research export headers for tamper-evident provenance.
