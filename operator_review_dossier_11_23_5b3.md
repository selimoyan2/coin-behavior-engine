# CBE — SPRINT 11.23.5B-3: OPERATOR REVIEW DOSSIER
## Single-Event Prospective Observation Pilot — U.S. CPI & BTC/USDT Spot

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `192524507416d9b9010bad07dcb2b6805b94c6cc`  
**Target Research Market:** Binance BTC/USDT Spot  
**Status:** READY FOR OPERATOR REVIEW (EXECUTION STRICTLY BLOCKED)  
**Date:** 2026-10-20 17:29:11 UTC

---

### A. RESEARCH OBJECTIVE

The Coin Behavior Engine (CBE) prospective research architecture is designed to capture point-in-time, causally clean observations of BTC/USDT spot market behavior immediately before, during, and after an official macroeconomic announcement.

Target Event Family: **U.S. Consumer Price Index (CPI) — Bureau of Labor Statistics (BLS)**

The pilot aims to establish a verified, defensible empirical foundation for:
1. Baseline price and volatility immediately prior to release (T-15m to T-1m).
2. Point-in-time official document availability timestamp.
3. Immediate post-release market reaction (T+1m, T+5m, T+15m, T+30m).
4. Post-event realized volatility and top-of-book bid-ask spread dynamics.

---

### B. METHODOLOGICAL & RESEARCH LIMITATIONS

The human operator must explicitly review and acknowledge these core research constraints:
1. **Zero Established Directional Edge:** CBE has not established any predictive or directional trading edge conditioned on economic releases.
2. **Historical Data Contamination:** The historical dataset (Sprint 09–11.23) remains classified as `RESEARCH_CONTAMINATED` due to look-ahead consensus revisions. Historical results cannot be cited as validation.
3. **Single-Event Statistical Inadequacy:** A single observation cannot establish a strategy, calibrate a risk model, or prove an economic hypothesis. It serves purely as an operational proof-of-observation.
4. **Consensus Unavailability:** Research-grade, licensed contemporaneous consensus evidence is currently `UNAVAILABLE`. Economic surprise relationships cannot be calculated or claimed.
5. **Microstructure & Clock Uncertainty:** 1-minute OHLCV candles do not reflect tick-level order book dynamics. Network latency and exchange clock offsets introduce unavoidable timing uncertainty (~100–500 ms).

---

### C. APPROVED SCOPE PROPOSAL

| Parameter | Approved Constraint | Enforcement Mechanism |
|---|---|---|
| Target Event | Exactly 1 Event (BLS CPI) | Single-event sequential pilot runner queue depth = 1 |
| Target Market | Binance Spot BTC/USDT | Hardcoded symbol allowlist; derivatives/margin denylisted |
| Sources | `bls.gov`, `data-api.binance.vision` | Strict domain allowlist in `ReadOnlyResearchTransport` |
| Exchange Credentials | Strictly NONE (Public endpoints only) | Sensitive header denylist (`x-mbx-apikey`, `Authorization`) |
| Request Budget | Exactly 20 requests | Transactional quota reservation in `TrustedApprovalStore` |
| Data Volume Budget | Exactly 5 MB (5,242,880 bytes) | Content-Length check & streaming byte counter |
| Duration Limit | 30 minutes (1800s) [or 35m if extended] | Monotonic timer stop condition in pilot runner |
| Background Automation | STRICTLY PROHIBITED | No crons, no daemons, no background tasks |
| Trading Actions | PERMANENTLY PROHIBITED | `LIVE_ORDER_EXECUTION` raises `TradingIsolationViolation` |

---

### D. REQUIRED OPERATOR DECISIONS

Prior to signing an authorization proposal, the human operator must formally decide on the following open items:

1. **Decision 1: Event Selection Confirmation**
   - Confirm selection of the upcoming U.S. BLS Consumer Price Index (CPI) release.
   - [ ] ACCEPT   [ ] REJECT
2. **Decision 2: Observation Duration Allocation**
   - Option A: Retain strict 30-minute (1800s) duration. (Post-event observation ends at T+29m).
   - Option B: Extend duration to 35 minutes (2100s). (Permits complete T+30m post-event candle closure).
   - [ ] OPTION A (30m)   [ ] OPTION B (35m)
3. **Decision 3: Request Budget Concurrence**
   - Confirm adherence to the 20-request budget (2 baseline + 10 polling + 5 post-event + 3 buffer).
   - [ ] ACCEPT   [ ] REJECT
4. **Decision 4: Source Allowlist Concurrence**
   - Confirm restricted domain access: `bls.gov`, `www.bls.gov`, `data-api.binance.vision`.
   - [ ] ACCEPT   [ ] REJECT
5. **Decision 5: Evidence Readiness Sign-Off**
   - Confirm that execution remains BLOCKED until official BLS calendar document is imported and verified.
   - [ ] CONFIRMED
6. **Decision 6: Emergency Stop & Revocation Procedure**
   - Confirm familiarity with `TrustedApprovalStore.revoke_approval()` and `ProspectivePilotRunner.request_stop()`.
   - [ ] CONFIRMED

---

### E. AUTHORIZATION BOUNDARY & NON-EXECUTION DECLARATION

**CRITICAL NOTICE:** This dossier is an information package for human operator review. It does NOT grant authorization, generate production keys, or activate network access.

- Production Signing Keys: **NOT PROVISIONED**
- Operator Authorization: **NOT GRANTED**
- Real Network Collection: **DISABLED**
- Live Order Execution: **PROHIBITED**
