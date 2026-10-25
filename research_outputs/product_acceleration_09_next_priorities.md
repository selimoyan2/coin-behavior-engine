# CBE — Product Acceleration Sprint 10 Next Priorities

**Engine Version:** CBE-0.7.0  
**Target Release:** Sprint 10  
**Focus:** Verified Authentic Multi-Source Intake, Cross-Asset Cointegration & Automated Scheduled Research Reporting  

---

## 1. Top Engineering & Research Priorities

1. **Authentic October 2026 Raw Intake Verification:**
   - Ingest genuine, multi-exchange historical archives (e.g. validated historical zip archives) with multi-node checksum cross-verification.
   - Transition October 2026 from intake quarantine to canonical dataset publication once verifiable trade logs are provided.

2. **Cross-Asset Cointegration & Basis Forensics:**
   - Implement Engle-Granger two-step and Johansen cointegration tests between BTCUSDT spot and historical perpetual funding rates.
   - Add historical basis spread tracking and statistical arbitrage deviation metrics without directional signal generation.

3. **Multi-Horizon Macro Event Clustering:**
   - Group macro events by thematic economic shocks (e.g. Rate Hikes, CPI Upside Surprises, Geopolitical De-risking).
   - Compute aggregate ensemble trajectories and volatility clustering across 10-year horizons.

4. **Automated Scheduled PDF Research Digests:**
   - Introduce cron-based or trigger-based background compilation of weekly/monthly market behavior dossiers.
   - Archive timestamped PDF research briefs with cryptographic Ed25519 author signatures into the Research Evidence Archive.

5. **Production Migration Checklist:**
   - When governance authorizes promotion, provide a single-command blue/green zero-downtime deployment script to replicate staging build `1fc10b1a` into production without service disruption.
