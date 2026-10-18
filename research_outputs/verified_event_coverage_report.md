# Verified Event Coverage & Historical News Provenance Audit Report
**Sprint 11.06 Deliverable**  
**Generated:** 2026-10-18 12:30:30 UTC  
**Total Events Audited:** 122  
**Audit Standard:** Strict Historical Provenance, Temporal Causality & Anti-Lookahead Invariants

---

## 1. Executive Summary & Verdict

Sprint 11.05 ingested 122 historical events and reported that market-context filtering reduced strategy losses by avoiding trades during risk events.

This independent Sprint 11.06 audit investigated every single event across source primary documentation, publication timestamps, earliest defensible decision entry times, page dynamic update limitations, and economic causality.

### Key Audit Findings:

1. **Massive Altcoin & Equity Noise Contamination (95.9% Inert):**
   - **103 events (84.4%)** are Binance CMS announcements. **98 of these 103** relate exclusively to altcoin listings (e.g. INJ hard fork, HYPE seed tag, COAI trading competition), P2P Kenyan Shilling fee waivers, or retail trading carnivals. None of these events exerted any measurable influence on BTCUSDT spot liquidity or price behavior.
   - **14 events (11.5%)** are US SEC press releases. **13 of these 14** relate exclusively to traditional equity broker-dealers, advisory conflict-of-interest charges, cherry-picking enforcement, or micro-cap crowdfunding. Only 1 event addressed crypto asset custody rules for registered advisers.
   - Only **4 events (3.3%)** represent genuine Tier 1 macroeconomic releases (FOMC Minutes, Fed Discount Rate Minutes, BLS CPI, BLS Employment Situation).

2. **Derivatives Liquidation Telemetry Is a Candle Price Proxy:**
   - Event `EVT-LIQ-20261007-0815` ("$450M Long Liquidation Cluster Triggered Below $83.5k") was **NOT** sourced from an authentic derivatives liquidation feed or exchange order book telemetry.
   - It was synthesized post-hoc from Binance 5m kline volume and price drawdown. Using candle-derived price action as an "external context filter" represents circular reasoning and lookahead data contamination.
   - Under Sprint 11.06 strict provenance standards, this event is classified as `REJECT_DERIVATIVES_PROXY`.

3. **Trading Decision Filtering Attribution:**
   - Out of 122 events, **119 events never filtered any trades**.
   - Exactly **2 authentic macroeconomic events** (FOMC Minutes on Oct 7 and Fed Discount Rate Minutes on Oct 13) and **1 price-volume proxy event** (Oct 7 liquidation spike) were responsible for the trade rejection behavior in Strategy B.
   - On Oct 14, BLS CPI was released and correctly tracked, but technical criteria already blocked trade entry on that bar.

---

## 2. Event Provenance Breakdown

| Source Category | Source Name | Provider Count | Strict Provenance Verdict | Trade Filtering Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Central Bank** | Board of Governors of the Federal Reserve System | 2 | `PASS_STRICT_PROVENANCE` (2) | Active Macro Headwind Filter |
| **Macroeconomic Calendar** | U.S. Bureau of Labor Statistics (BLS) | 2 | `PASS_STRICT_PROVENANCE` (2) | High-Impact Economic Release |
| **Regulatory Agency** | US Securities and Exchange Commission (SEC) | 14 | `REJECT_NON_CRYPTO_EQUITY` (13)<br>`PASS_WITH_RESERVATION` (1) | Inert Equity / Traditional Fraud |
| **Exchange Operations** | Binance Exchange Official Announcements | 103 | `REJECT_ALTCOIN_NOISE` (103) | Inert Altcoin / Promo Announcements |
| **Market Telemetry Proxy** | Binance Derivatives Market Telemetry | 1 | `REJECT_DERIVATIVES_PROXY` (1) | Circular Price/Volume Calculation |
| **Total** | | **122** | **Strict Usable: 4 (3.3%)** | Active Filters: 3 |

---

## 3. Provenance & Archival Limitations

### A. Dynamic API Limitations (Binance CMS)
- Binance CMS announcements are retrieved via the dynamic endpoint `bapi/composite/v1/public/cms/article/list/query`.
- **Limitation:** The endpoint returns live JSON objects without public Git commit logs, immutable change records, or content-addressable hashes. Exchange operators can amend announcement text or delete obsolete notices.
- **Defensible Availability:** The earliest time an automated strategy could observe a CMS announcement is `releaseDate + 120 seconds` (reflecting polling frequency and cache invalidation).

### B. RSS Polling Latency (Federal Reserve & SEC)
- Both the Federal Reserve monetary press feed and SEC press releases are distributed via RSS XML feeds.
- **Limitation:** RSS `pubDate` records the server-side timestamp of publication. Automated ingestors experience polling latency (typically 30–60 seconds).
- **Defensible Availability:** In all Sprint 11.06 causality ablations, a minimum **60-second observation buffer** is enforced between `pubDate` and the earliest bar eligible for decision filtering.

### C. Embargoed Economic Releases (BLS CPI & NFP)
- BLS releases have strict federal embargo policies, published precisely at 08:30:00 US Eastern (12:30:00 UTC).
- **Defensible Availability:** High-frequency news feeds receive the data within 2–5 seconds. For 5-minute candle analysis, the event is defensibly observable on the candle opening at or immediately following 12:30:00 UTC.

---

## 4. Complete Audit Classification of Usable Events

| Event ID | Published (UTC) | Earliest Defensible UTC | Provenance Source | Category | Exact Factual Claim | Strict Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `EVT-SEC-202610011216` | 2026-10-01T12:16:07+00:00 | 2026-10-01T12:17:07+00:00 | US Securities and Exchange Commission | GENERAL_CRYPTO_POLICY | VERIFIED_ACCURATE | `PASS_WITH_RESERVATION_GENERAL_POLICY` |
| `EVT-BLS-NFP-20261002` | 2026-10-02T12:30:00Z | 2026-10-02T12:30:05+00:00 | U.S. Bureau of Labor Statistics | DIRECT_BTC_MACRO | VERIFIED_ACCURATE | `PASS_STRICT_PROVENANCE` |
| `EVT-LIQ-20261007-0815` | 2026-10-07T08:15:00Z | 2026-10-07T08:15:10+00:00 | Binance Derivatives Market Telemetry | DERIVATIVES_PRICE_PROXY | UNSUPPORTED_PROXY | `REJECT_DERIVATIVES_PROXY` |
| `EVT-FED-202610071800` | 2026-10-07T18:00:00+00:00 | 2026-10-07T18:01:00+00:00 | Board of Governors of the Federal Reserve System | DIRECT_BTC_MACRO | VERIFIED_ACCURATE | `PASS_STRICT_PROVENANCE` |
| `EVT-FED-202610131800` | 2026-10-13T18:00:00+00:00 | 2026-10-13T18:01:00+00:00 | Board of Governors of the Federal Reserve System | DIRECT_BTC_MACRO | VERIFIED_ACCURATE | `PASS_STRICT_PROVENANCE` |
| `EVT-BLS-CPI-20261014` | 2026-10-14T12:30:00Z | 2026-10-14T12:30:05+00:00 | U.S. Bureau of Labor Statistics | DIRECT_BTC_MACRO | VERIFIED_ACCURATE | `PASS_STRICT_PROVENANCE` |

---

## 5. Audit Conclusion

- **Genuine, verified macroeconomic events usable for research:** **4 events** (`EVT-FED-202610071800`, `EVT-FED-202610131800`, `EVT-BLS-CPI-20261014`, `EVT-BLS-NFP-20261002`).
- **Events rejected due to irrelevance, noise, or circular proxy construction:** **118 events (96.7%)**.
- The subsequent causality ablation experiments (Phase C) will evaluate whether filtering trades during the windows of these 4 genuine events produces any statistical alpha beyond simple trade frequency reduction.
