# CBE — Feature Inventory & Capability Mapping
## Sprint Product Acceleration 01

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9`  
**Execution Mode:** `OFFLINE_RESEARCH_AND_PRODUCT_DEVELOPMENT`  
**Date:** 2026-10-23  

---

### Executive Summary

This inventory maps all existing capabilities of the Coin Behavior Engine into four functional domains, classifying their actual technical status based on verified repository evidence.

**Classification Taxonomy:**
- `IMPLEMENTED`: Full backend engine, data models, APIs, and user interface delivered and verified.
- `PARTIAL`: Core backend logic implemented; UI or integration partially completed.
- `BACKEND_ONLY`: Algorithmic or persistence layer exists; lacks direct user interface.
- `UI_ONLY`: Interface prototype exists without live backend connectivity.
- `BLOCKED_BY_GOVERNANCE`: Policy, safety, or legal interlock intentionally prohibits execution.
- `NOT_IMPLEMENTED`: Architectural concept only; no functional codebase exists.

---

### B1. Research and Market Structure

| Capability | Status | Implementation Details | Evidence & Artifacts |
| :--- | :---: | :--- | :--- |
| **Historical Candle Processing** | `IMPLEMENTED` | Multi-year Parquet archival store across 6 timeframes (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`) for `BTCUSDT`. | `data/binance_spot_multiyear/`, `src/coin_behavior_engine/ingestion/` |
| **Market Regime Classification** | `PARTIAL` | Historical classifier operational. Raw CBE-0.7.0 model percentile comparison flaw (`x <= x`) is safely masked to `UNKNOWN` in UI. Corrected candidate classifier is offline research only. | `src/coin_behavior_engine/regimes/`, `regime_transition_matrix_11_21.json` |
| **Trend & Volatility Analysis** | `IMPLEMENTED` | Realized volatility, multi-horizon ATR, rolling quantiles (Q10-Q90), and volatility expansion likelihood. | `src/coin_behavior_engine/features/`, `src/coin_behavior_engine/product/intelligence_api.py` |
| **Funding-Related Research** | `IMPLEMENTED` | 8-hour perpetual funding rate predictability, AR(1) persistence, and pure compute latency (< 22 ms). Gross carry vs net fee friction accounting. | `tests/test_sprint09_38_funding_predictability.py`, `funding_full_suite_performance_11_23_5b6_5_5c.json` |
| **Market Behavior Classification** | `IMPLEMENTED` | State detection across 7 canonical states: `NORMAL`, `COMPRESSION`, `EXPANSION_WATCH`, `HIGH_VOLATILITY`, `QUIET`, `DELEVERAGING_STRESS`, `EVENT_SHOCK_ACTIVE`. | `src/coin_behavior_engine/market_state/`, `src/coin_behavior_engine/product/dashboard_api.py` |
| **Statistical Confidence & Sample Gating** | `IMPLEMENTED` | Minimum sample gates (N >= 5, N >= 30, N >= 100). Small samples trigger `YETERSİZ ÖRNEK` badges. | `src/coin_behavior_engine/calibration/`, `src/coin_behavior_engine/prospective/analytics.py` |
| **Research Contamination Tracking** | `IMPLEMENTED` | Explicit labeling of historical datasets as `RESEARCH_CONTAMINATED` vs prospective `INDEPENDENT_EVALUATION`. | `src/coin_behavior_engine/audit/`, `data_contracts.py` |
| **Walk-Forward Evaluation** | `IMPLEMENTED` | Sequential out-of-sample forward evaluation avoiding lookahead bias. | `walk_forward_evaluation_11_16b_8.csv`, `data/reports/sprint07/` |
| **Economic Significance Assessment** | `IMPLEMENTED` | Canonical portfolio accounting, fee friction deduction (maker 0.02% / taker 0.04%), slippage modeling. | `src/coin_behavior_engine/accounting/`, `test_sprint11_16b_9_canonical_portfolio_accounting.py` |

---

### B2. News and Event Research

| Capability | Status | Implementation Details | Evidence & Artifacts |
| :--- | :---: | :--- | :--- |
| **News / Event Records** | `IMPLEMENTED` | 40 verified macro and regulatory events with structured schemas, published UTC timestamps, and exact claims. | `data/research_lab/verified_events_cache.json` |
| **Source Provenance** | `IMPLEMENTED` | Tier 1 official agency attribution (`SEC.gov`, `FederalReserve.gov`, `U.S. Treasury`). | `src/coin_behavior_engine/research_lab/news_adapters.py` |
| **Event Classification** | `IMPLEMENTED` | Taxonomy: `REGULATORY_ENFORCEMENT_ACTION`, `MONETARY_POLICY_DISCOUNT_RATE`, `MACRO_ECONOMIC_INDICATOR`. | `tests/test_sprint11_23_macro_events_and_reactions.py` |
| **Historical Event Impact** | `IMPLEMENTED` | Event reaction ledger tracking 5m, 1h, and 4h price / volatility reactions following official publications. | `btc_event_reaction_ledger_11_23.parquet` |
| **BLS CPI Candidate Status** | `IMPLEMENTED` | Formally registered candidate `REQ-BLS-CPI-2026M10-ACQ01`; explicitly flagged as `PROPOSED (UNVERIFIED)`. | `bls_acquisition_request_11_23_5b6.json`, `/api/v1/product/events` |
| **Official-Source Verification** | `IMPLEMENTED` | Cryptographic signature & domain-bound scope engine requiring privileged administrative approval. | `src/coin_behavior_engine/prospective/observation_authorization.py` |
| **News-Conditioned Research Eligibility** | `BLOCKED_BY_GOVERNANCE` | Directional trading eligibility is strictly ZERO (`NEWS_CONDITIONED_EDGE: NOT_ESTABLISHED`). | `data_contracts.py`, `dashboard_api.py` |

---

### B3. Governance and Authorization

| Capability | Status | Implementation Details | Evidence & Artifacts |
| :--- | :---: | :--- | :--- |
| **Operator Identities** | `IMPLEMENTED` | Role-based RBAC (`RESEARCH_LEAD`, `SECURITY_AUDITOR`, `GOVERNANCE_ADMIN`) bound to Ed25519 public keys. | `src/coin_behavior_engine/prospective/observation_authorization.py` |
| **Roles and Permissions** | `IMPLEMENTED` | Granular capability segregation; zero execution capabilities granted to research roles. | `src/coin_behavior_engine/prospective/governance.py` |
| **Cryptographic Signatures** | `IMPLEMENTED` | Audited PyCA / OpenSSL `cryptography` library implementing Ed25519 (RFC 8032). Zero custom crypto. | `tests/test_sprint11_23_5b6_5_cryptography_hardening.py` |
| **Capability Grants** | `IMPLEMENTED` | Strongly-typed capability tokens (`OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION`). | `observation_authorization.py` |
| **Approval Records Store** | `IMPLEMENTED` | Transactional SQLite `TrustedApprovalStore` with concurrency locks and WAL journal mode. | `data/prospective/trusted_approval_store.sqlite3` |
| **Nonce Replay Protection** | `IMPLEMENTED` | `approval_nonces` table rejecting reused tokens with cryptographic request digests. | `observation_authorization.py` |
| **Audit Evidence Trail** | `IMPLEMENTED` | Append-only `audit_trail` table recording all governance proposals, checks, and decisions. | `observation_authorization.py` |
| **Technical Decision Status** | `IMPLEMENTED` | Fail-closed enforcement: `TECHNICAL_NO_GO` and `GOVERNANCE_AUTHORIZATION: NOT_GRANTED`. | `/api/v1/product/governance`, `final_go_no_go_*.json` |

---

### B4. Operations and Reliability

| Capability | Status | Implementation Details | Evidence & Artifacts |
| :--- | :---: | :--- | :--- |
| **Service Health Check** | `IMPLEMENTED` | Sub-millisecond `/health`, `/healthz`, `/ping` endpoints validating container runtime and model freeze. | `src/coin_behavior_engine/web/server.py` |
| **Version & Git Visibility** | `IMPLEMENTED` | Frozen model `CBE-0.7.0`, Git SHA `2e7ad236ba07f71...`, and branch tracking across all envelopes. | `/api/status`, `/api/v1/product/operations` |
| **Last Successful Offline Run** | `IMPLEMENTED` | Full regression qualification metadata from Sprint 11.23.5B-6.5.5C (2,102 passed). | `research_outputs/full_regression_report_11_23_5b6_5_5c.json` |
| **Data Freshness Monitoring** | `IMPLEMENTED` | 5 distinct pipeline timestamps with 30-minute staleness boundaries and fail-closed warnings. | `src/coin_behavior_engine/product/intelligence_api.py` |
| **Job Execution History** | `IMPLEMENTED` | Historical sprint execution manifests and research output logs. | `research_outputs/` |
| **Processing Error Isolation** | `IMPLEMENTED` | Graceful failure boundaries; errors in analytics do not crash server or expose internal traces. | `server.py`, `dashboard_api.py` |
| **Storage & Memory Telemetry** | `IMPLEMENTED` | Live directory disk usage breakdown (`data/`, `research_outputs/`) and Linux `VmRSS` memory tracking. | `/api/v1/product/operations` |
| **Research Artifact Browser** | `IMPLEMENTED` | Interactive web catalog and secure bounded preview over 540+ JSON, MD, CSV, and XML artifacts. | `src/coin_behavior_engine/product/dashboard_ui.py`, `/api/v1/product/artifacts` |

---

### Capability Distribution Summary

```
Total Identified Capabilities: 32
├── IMPLEMENTED:            29  (90.6%)
├── PARTIAL:                 2   (6.3%)
└── BLOCKED_BY_GOVERNANCE:   1   (3.1%)
```
