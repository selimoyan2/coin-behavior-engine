# CBE Prospective Research Protocol: Scientific Pre-Registration & Shadow Governance

**Document ID:** `PRP-SPRINT-11-15`  
**Version:** `1.0.0-frozen`  
**Effective Date:** `2026-10-18T21:00:00Z`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `7ee1104564cfe2283d234284e220d0ef06f40963`  
**Status:** **PRE-REGISTERED & FROZEN FOR HUMAN OPERATOR AUTHORIZATION**  
**Execution Environment:** Strictly Isolated Offline Air-Gapped Research  

---

## 1. Scientific Mission & Epistemological Stance

The objective of the **Coin Behavior Engine (CBE) Prospective Research Protocol** is to establish an unassailable empirical standard for evaluating algorithmic spot decision-making on BTC/USDT without data snooping, post-hoc optimization, or survivorship contamination.

### Fundamental Scientific Invariants:
1. **Contamination Disclosure:** Historical backtests over the 365-day dataset (`market_state_dataset.parquet`) have been repeatedly analyzed across Sprints 11.10 through 11.14. Under the Neyman-Pearson and Popperian testing frameworks, repeated inspection invalidates classical hypothesis testing ($p$-values become uncalibrated).
2. **True Out-of-Sample Requirement:** Genuine validation can only occur on **unseen prospective market data** captured *after* policy definition, parameter freeze, and protocol pre-registration.
3. **Pre-Registration:** All candidate research policies, hyper-parameters, statistical test thresholds, evaluation horizons, and stop conditions are frozen **before** the prospective observation window begins.
4. **Offline Isolation:** This protocol prepares a **shadow readiness package**. It strictly prohibits automated live scoring, order generation, API credential binding, or exchange connectivity.

---

## 2. Air-Gapped System Architecture & Storage Decoupling

The shadow evaluation pipeline operates with complete physical and logical isolation:

```
[ Unseen Real-Time Market Feed / Ingestion Pipeline ]
                       │
                       ▼ (Read-Only 5m Aggregated Bar)
       ┌───────────────────────────────┐
       │   Data Freshness Gate         │ ◄─── Fail-Closed Check (<15 min latency)
       └──────────────┬────────────────┘
                      │
                      ▼
       ┌───────────────────────────────┐
       │   Frozen Policy Engine        │ ◄─── Read-Only Policy Freeze Manifest
       └──────────────┬────────────────┘
                      │
                      ▼
       ┌───────────────────────────────┐
       │  Shadow Decision Generator    │ ◄─── Sealed with Deterministic SHA-256
       └──────────────┬────────────────┘
                      │
                      ▼
       ┌───────────────────────────────┐
       │   Decision Hash Chain Ledger  │ ◄─── Append-Only, Monotonic Sequence
       └──────────────┬────────────────┘
                      │
         [ Causally Decoupled Wait ]
                      │
                      ▼
       ┌───────────────────────────────┐
       │   Shadow Outcome Ledger       │ ◄─── Linked solely by parent_decision_hash
       └───────────────────────────────┘
```

### Decoupled Storage Specifications:
- **Decision Ledger (`prospective_shadow_decisions.csv` / `.jsonl`):** Records decisions strictly at timestamp $t$ using only data available up to $t$.
- **Outcome Ledger (`prospective_shadow_outcomes.csv` / `.jsonl`):** Records outcomes evaluated at $t + H$, where $H$ is the pre-registered evaluation horizon.
- **Independence Guarantee:** The decision ledger has no knowledge of subsequent price excursion, realized PnL, or trade outcome. Modifying an outcome record does not alter the historical decision hash.

---

## 3. Machine-Readable Decision Record Schema

Every shadow decision is serialized according to [`shadow_decision_schema.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/shadow_decision_schema.json) with strict canonical formatting:

| Field Name | Type | Description |
|---|---|---|
| `decision_id` | `string` | Unique identifier format `DEC-YYYYMMDDHHMM-XXXXX` |
| `sequence_number` | `integer` | Strictly monotonic zero-indexed sequence integer |
| `observation_timestamp_utc` | `string` | ISO-8601 UTC timestamp of candle close |
| `data_availability_timestamp_utc` | `string` | ISO-8601 UTC timestamp when data was ingested |
| `source_identifier` | `string` | Canonical data feed identifier |
| `btc_spot_reference_price` | `number` | BTC/USDT spot closing price (rounded to 4 decimals) |
| `hypothetical_usdt_balance` | `number` | Simulated USDT cash balance |
| `hypothetical_btc_balance` | `number` | Simulated BTC spot inventory |
| `hypothetical_total_equity_usdt`| `number` | Total portfolio equity under mark-to-market |
| `market_regime` | `string` | Classified regime (`BEAR_TREND`, `BULL_TREND`, `SIDEWAYS`, `VOLATILE_BREAKOUT`, `UNCERTAIN`) |
| `forecast_probabilities` | `object` | Calibrated probabilities `{"p_up": float, "p_down": float, "p_flat": float}` |
| `uncertainty_score` | `number` | Entropy or ensemble variance in $[0.0, 1.0]$ |
| `decision` | `string` | Discrete action (`WAIT_USDT`, `BUY_CANDIDATE`, `HOLD_BTC`, `REDUCE_BTC`, `EXIT_TO_USDT`, `NO_DECISION_DATA`) |
| `hypothetical_target_price` | `number` / `null` | Pre-calculated limit/profit reference |
| `hypothetical_stop_price` | `number` / `null` | Pre-calculated stop-loss barrier |
| `evidence_rationale` | `object` | Explicit audit trail of triggered conditions or rejections |
| `policy_id` | `string` | Frozen policy ID (e.g. `POLICY_D_SELECTIVE_TREND_ONLY`) |
| `policy_version` | `string` | Frozen policy version string (e.g. `1.0.0-frozen`) |
| `code_commit_hash` | `string` | Git SHA of code base executing the decision |
| `parent_decision_hash` | `string` | SHA-256 hash of preceding record (or 64 zeros for Genesis) |
| `decision_hash` | `string` | Deterministic SHA-256 seal over canonical record |

---

## 4. Cryptographic Hash Chaining & Tamper Detection

To ensure forensic immutability without centralized authorities:
1. **Canonical JSON Serialization:** All keys sorted alphabetically, compact separators `(",", ":")`, floats formatted deterministically.
2. **Genesis Block:** The root record has `parent_decision_hash` set to 64 consecutive hexadecimal zeros:
   `0000000000000000000000000000000000000000000000000000000000000000`
3. **Chain Invariant:** For every record $i > 0$:
   $$\text{parent\_decision\_hash}_i \equiv \text{decision\_hash}_{i-1}$$
   $$\text{sequence\_number}_i \equiv \text{sequence\_number}_{i-1} + 1$$
   $$\text{observation\_timestamp}_i > \text{observation\_timestamp}_{i-1}$$
4. **Verification Algorithm:** An $O(N)$ audit routine recomputes the SHA-256 digest of every record from payload data and checks link parity. Any retroactive bit-flip, deletion, or re-ordering breaks verification instantly.

---

## 5. Fail-Closed Principles & Data Freshness Gates

In live algorithmic trading, stale or missing data is a primary source of catastrophic execution errors. The shadow protocol enforces strict defensive fail-closed rules:

1. **Max Allowed Ingestion Latency:** 15.0 minutes (3 candles).
   $$\Delta t_{\text{latency}} = t_{\text{availability}} - t_{\text{observation}}$$
   If $\Delta t_{\text{latency}} > 900 \text{ seconds}$, the engine rejects execution and emits `NO_DECISION_DATA`.
2. **Missing Candle Handling:** If a 5m bar gap is detected (e.g., $t_i - t_{i-1} > 300\text{s}$), the engine halts new entry signals, logs `NO_DECISION_DATA`, and forces the portfolio to default risk state:
   - If holding cash: Remain in `WAIT_USDT`.
   - If holding inventory: Evaluate stop-loss against last known price; do not permit new entries.
3. **Zero Lookahead:** If $t_{\text{availability}} < t_{\text{observation}}$, a catastrophic timestamp violation is raised and the execution runner terminates.

---

## 6. No-Trade (`WAIT_USDT`) as a First-Class Decision

Abstaining from trading is an active financial choice that conserves capital and friction. Every `WAIT_USDT` record is tracked with the same rigor as an entry trade:

1. **Abstention Duration:** Continuous time spent in 100% USDT cash (in hours and 5m bars).
2. **Avoided Drawdown Accounting:**
   $$\text{Avoided Drawdown} = \max\left(0, \frac{P_{\text{ref}} - \min_{t \in [0, H]} P_t}{P_{\text{ref}}}\right)$$
   Measures capital preserved by refusing to hold BTC during market cascades.
3. **Missed Appreciation Accounting:**
   $$\text{Missed Appreciation} = \max\left(0, \frac{\max_{t \in [0, H]} P_t - P_{\text{ref}}}{P_{\text{ref}}}\right)$$
   Measures upside foregone by remaining in cash.
4. **Economic Opportunity Cost:**
   $$\text{Opportunity Cost (USDT)} = \max\left(0, \frac{\text{Missed Appreciation} - \text{Roundtrip Friction}}{100}\right) \times \text{Equity}_{\text{USDT}}$$

---

## 7. Canonical Execution Policy V2 Rules

All hypothetical fills, inventory tracking, and balance reconciliations are governed by **Execution Policy V2**:
- **Asset Type:** Spot BTC/USDT (Long-only).
- **Execution Timing:** Next-bar open fill (Zero same-bar execution).
- **Roundtrip Friction:** 30.0 bps nominal:
  - 10.0 bps taker entry fee
  - 10.0 bps taker exit fee
  - 5.0 bps entry slippage
  - 5.0 bps exit slippage
- **Capital Allocation Cap:** 98.0% of available USDT cash (2.0% buffer for fees).
- **Intrabar Order Priority:** Pessimistic execution: If both Stop-Loss and Take-Profit price levels are touched within the same candle, **Stop-Loss is executed first**.
- **Gap Down Modeling:** If the bar open gaps down below the Stop-Loss price, fill occurs at the bar Open price (not the stop price).
- **Balance Invariant:** $\text{Ending Equity} \equiv \text{USDT Cash} + (\text{BTC Inventory} \times P_{\text{close}})$.
- **Capital Conservation:** $\text{Starting Equity} + \text{Gross PnL} - \text{Total Friction} \equiv \text{Ending Equity} \pm \$0.01$.

---

## 8. Quantitative Evaluation Horizon & Minimum Sample Requirements

To prevent premature conclusions or noise-fitting, prospective evaluation requires predefined statistical sample thresholds:

1. **Minimum Observation Duration:** 30 calendar days ($8,640$ consecutive 5-minute candles).
2. **Minimum Trade Cycles:** 20 completed roundtrip trade cycles per active policy.
3. **Regime Coverage Invariant:** The prospective sample must span at least two distinct classified regimes (e.g., Sideways + Trend, or Bull + Volatile Breakout).
4. **Pre-Registered Hypothesis Tests:**
   - **$H_{0,1}$ (Economic Edge):** Mean Net Return of Policy $\le 0$ under 30 bps friction.
   - **$H_{0,2}$ (Beta Outperformance):** Net Sharpe Ratio of Policy $\le$ Sharpe Ratio of Buy-and-Hold.
   - **$H_{0,3}$ (Abstention Quality):** Net PnL of Selective Policy $\le$ Net PnL of Unfiltered Trend Policy C.

---

## 9. Circuit Breakers & Emergency Stop Conditions

The shadow observation runner will automatically trigger an **Emergency Freeze / Stop** if any of the following boundaries are breached:

1. **Maximum Drawdown Breaker:** Portfolio equity drawdown $\ge 15.0\%$ from peak equity.
2. **Consecutive Loss Breaker:** 5 consecutive losing trade cycles.
3. **Data Quality Degradation:** Over 5.0% of bars in a rolling 24-hour window emit `NO_DECISION_DATA`.
4. **Hash Chain Invalidation:** Any single record fails cryptographic SHA-256 seal or parent link verification.
5. **Divergence Breaker:** Mark-to-market equity differs from cash-flow conservation equation by more than $\$0.05$.

---

## 10. Protocol Governance & Operator Authorization

This protocol is purely an offline scientific architecture. Under no circumstances may an automated agent activate real-time ingestion workers, connect to Binance API endpoints, or send orders to execution venues.

- **Current Status:** `READY_FOR_OPERATOR_AUTHORIZATION`
- **Activation Requirement:** Explicit, signed human operator command with validated external API credentials in an isolated, monitored worker container.
- **Reporting Invariant:** Any subsequent research report must state the five canonical statuses independently.
