# CBE Sprint 11.15.1 Fail-Closed Position Safety & Data Failure Audit

**Sprint:** CBE — 11.15.1  
**Mission:** Prospective Protocol Hardening & Independent Readiness Audit  
**Audit Target:** Stale Feed Handling, Inventory Preservation, Price Gaps & Fill Verification  
**Audit Date:** 2026-10-18T22:25:00+03:00  
**Base Commit:** `09773621f7026ac2630fb7674cd11aadaf934a70`  
**Execution Standard:** Canonical Execution Policy V2 (30.0 bps)  

---

## 1. Executive Summary & Architecture

In historical backtesting, data feeds are clean and contiguous. In prospective shadow observation, network dropouts, websocket disconnects, and exchange API throttles occur.

A naive fail-closed policy that simply emits `NO_DECISION_DATA` or liquidates exposure when data is missing introduces severe survivorship and execution biases. Sprint 11.15.1 decouples **Signal Generation**, **Data Availability**, **Hypothetical Execution**, and **Portfolio Valuation** into explicit, fail-closed operational states.

---

## 2. Four Operational Cases: Specification & Invariants

```
                                [Incoming 5m Observation]
                                            │
                                            ▼
                             Is Data Fresh & Valid? (Latency <= 15m)
                                    /               \
                                   /                 \
                                [YES]               [NO]
                                 │                   │
                        Evaluate Policy       Check Position State
                                 │                   │
                                 │         ┌─────────┴─────────┐
                                 │         ▼                   ▼
                                 │   [No Position]       [Open Long Position]
                                 │         │                   │
                                 │   `NO_DECISION_DATA`  `POSITION_OPEN_DATA_STALE`
                                 │   (Remain in Cash)    (Preserve BTC Inventory,
                                 │                        Mark-to-Market Frozen,
                                 │                        No Liquidation Invented)
                                 │
                                 ▼
                     Next-Bar Execution Check
                                 │
                       Is Next Open Available?
                               /       \
                              /         \
                           [YES]        [NO]
                            │            │
                     Execute Fill   `EXECUTION_PENDING_DATA`
                     (with gap &    (Zero Invented Fills,
                      friction)      Order Queued/Discarded)
```

---

### Case A — No Open BTC Position (Cash Invariant)
- **Scenario:** The engine is 100% in USDT cash and incoming candle data is stale ($>15$ minutes latency) or completely missing.
- **Fail-Closed Rule:** Under no circumstances may a new position be entered.
- **Emitted Action:** `NO_DECISION_DATA`.
- **Accounting Invariant:** USDT balance remains untouched. Inventory remains $0.0\text{ BTC}$. Cash streak tracking increments.

### Case B — Existing Hypothetical BTC Position (Inventory Preservation)
- **Scenario:** The engine is holding an active BTC spot position when data feed disconnects or goes stale.
- **Critical Failure Mode Avoided:** Naive simulators often assume either (a) an immediate exit at the last price or (b) an unverified stop-loss exit. In reality, during an exchange outage or client disconnect, an unexecuted position remains open in the market.
- **Fail-Closed Rule:** The engine MUST NOT invent a liquidation. Spot BTC inventory is preserved exactly.
- **Emitted Action:** `POSITION_OPEN_DATA_STALE`.
- **Valuation State:** `VALUATION_UNAVAILABLE_MARK_FROZEN`. Equity is conservatively marked at the last verified close price with uncertainty score forced to $1.0$.

### Case C — Price Gap Through Stop-Loss (Realistic Slippage)
- **Scenario:** An open long has a stop-loss at $60,000. During the next candle, the market opens at $58,500 (gap down of 2.5% below stop).
- **Critical Failure Mode Avoided:** Backtests that assume fills occur exactly at the stop price ($60,000$) severely understate downside risk.
- **Pessimistic Intrabar Rule:** In `ShadowExecutionSimulator.check_intrabar_exit`:
  $$\text{if } P_{\text{open}} \le P_{\text{stop}} \implies \text{Fill Price} = P_{\text{open}} \times (1 - \text{slippage})$$
  The fill is executed at the actual opening price ($58,500$), absorbing the full price gap.

### Case D — Missing Next-Bar Open Price (Execution Refusal)
- **Scenario:** A policy emits `BUY_CANDIDATE` at bar close $t$, but candle $t+1$ has a missing or malformed opening price (`open <= 0`, `NaN`, or missing record).
- **Fail-Closed Rule:** Under Policy V2, no execution may be hallucinated or interpolated.
- **Emitted State:** `EXECUTION_REJECTED_MISSING_PRICE`. The entry order is voided or flagged `EXECUTION_PENDING_DATA`. Capital remains in USDT.

---

## 3. Explicit Data Failure States

| State Identifier | Trigger Condition | Position Action | Balance & Valuation Impact |
|---|---|---|---|
| **`NO_DECISION_DATA`** | Stale/missing feed while in USDT cash | Remain 100% USDT cash | Cash preserved, 0.0 BTC, no trades |
| **`POSITION_OPEN_DATA_STALE`** | Stale/missing feed while holding BTC | Maintain open position | BTC preserved, no exit invented, equity mark frozen |
| **`EXECUTION_PENDING_DATA`** | Trade signaled but execution candle open missing | Abort/defer order fill | No cash deducted, no BTC acquired |
| **`VALUATION_UNAVAILABLE`** | Feed offline during MTM calculation cycle | Hold portfolio state | Mark-to-market flagged uncertain ($u=1.0$) |

---

## 4. Air-Gapped Safety Confirmation

This audit verifies that the engine contains zero execution adapters to Binance, Coinbase, or any other live exchange. All simulation routines operate entirely in local memory on verified immutable data structures.
