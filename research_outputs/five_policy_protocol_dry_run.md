# CBE Sprint 11.15.1 — Five-Policy Deterministic Dry-Run Report

> [!WARNING]
> **DISCLAIMER: HISTORICAL_PROTOCOL_DRY_RUN_NOT_PROSPECTIVE**
> This evaluation is an offline engineering dry-run executed on historical candles (500 bars, index 86724 to 87224) to verify simultaneous protocol execution, cryptographic chaining, and Policy V2 portfolio accounting.
> **ZERO of these results constitute prospective evidence or validation of strategy profitability.**
> **No winner policy has been or will be selected from this historical data.** All 5 candidate policies remain frozen.

---

## 1. Protocol Verification Audit Criteria

In accordance with Sprint 11.15.1 Phase 7 specifications:

1. **Simultaneous Execution:** All 5 candidate research policies executed simultaneously across identical historical 5-minute candles.
2. **Schema Compliance:** Every issued decision record conformed to the hardened `shadow_decision_schema.json` specification.
3. **Cryptographic Integrity:** All 5 independent decision streams produced unbroken SHA-256 hash chains verified by `DecisionHashChain.verify_integrity()`.
4. **Execution Policy V2 Invariants:** Next-bar market orders and intrabar triggers executed with exact 30.0 bps roundtrip friction (10 bps taker entry + 10 bps taker exit + 5 bps entry slip + 5 bps exit slip).
5. **Exact Portfolio Conservation:** Every ledger row verified the conservation equation:
   $$\text{Starting Capital} + \text{Total Gross PnL} - \text{Total Friction} = \text{Ending Equity}$$
   with maximum observed absolute error $\le 0.000001$ USDT across all 2,500 record bars.
6. **Explicit Ledger Labeling:** Every row in `historical_five_policy_dry_run_ledger.csv` carries `stream_label = HISTORICAL_PROTOCOL_DRY_RUN_NOT_PROSPECTIVE`.
7. **Non-Contamination Lock:** These dry-run metrics are recorded exclusively for protocol integrity and are strictly excluded from future prospective evaluation.

---

## 2. Comparative Dry-Run Policy Summary Table

| Policy ID | Trades | Final USDT | Final BTC | Final Equity | Return % | Max DD % | Total Friction | Chain Head Hash | Chain Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`POLICY_A_USDT_CASH`** | 0 | $10,000.00 | 0.000000 | $10,000.00 | +0.00% | 0.00% | $0.00 | `dcb4b4054f1cde5a...` | **`INTACT_AND_VERIFIED`** |
| **`POLICY_B_BTC_BUY_AND_HOLD`** | 0 | $190.20 | 0.155392 | $10,051.07 | +0.51% | -0.96% | $14.70 | `7a78c01488a1f155...` | **`INTACT_AND_VERIFIED`** |
| **`POLICY_C_TREND48_FOLLOWING`** | 6 | $186.04 | 0.151878 | $9,823.92 | -1.76% | -2.33% | $189.06 | `945ac52329da6ba3...` | **`INTACT_AND_VERIFIED`** |
| **`POLICY_D_SELECTIVE_TREND_ONLY`** | 0 | $190.20 | 0.155195 | $10,038.55 | +0.39% | -0.96% | $14.70 | `bb9340c5a243a018...` | **`INTACT_AND_VERIFIED`** |
| **`POLICY_E_SELECTIVE_ANALOGUE_ASSISTED`** | 0 | $190.20 | 0.155195 | $10,038.55 | +0.39% | -0.96% | $14.70 | `8e23a99342d5ab7a...` | **`INTACT_AND_VERIFIED`** |

---

## 3. Policy Execution Observations

- **`POLICY_A_USDT_CASH`:** 
  Zero trades, 100% abstention (`WAIT_USDT`). Portfolio remained at exactly $10,000.00 USDT cash with zero friction and zero drawdown.
- **`POLICY_B_BTC_BUY_AND_HOLD`:** 
  Entered long at bar 1 open under 98% allocation cap, paying 15 bps entry friction ($14.70 USDT). Held BTC inventory continuously through all 500 bars. Equity mirrored spot price fluctuations.
- **`POLICY_C_TREND48_FOLLOWING`:** 
  Executed trend breakout entries when price crossed above 48-hour SMA and exited when falling below, incurring 30 bps roundtrip friction on roundtrips.
- **`POLICY_D_SELECTIVE_TREND_ONLY`:** 
  Applied multi-timeframe trend alignment (24h and 72h SMA), anti-chase ceiling (<= 2.25% above 24h SMA), and volatility filtering, substantially reducing turnover while holding cash during chop.
- **`POLICY_E_SELECTIVE_ANALOGUE_ASSISTED`:** 
  Applied selective trend gates plus frozen analogue directional hurdle (`analogue_prob >= 0.60`).

---

## 4. Cryptographic Hash Chain Verification

All 5 policy chains verified intact from genesis parent `0000000000000000000000000000000000000000000000000000000000000000` through sequence number 499:

- Every record's SHA-256 hash was recursively computed over its canonical UTF-8 JSON representation.
- Every record verified that its `parent_decision_hash` matched the preceding record's `decision_hash`.
- No duplicate decision IDs, sequence gaps, or timestamp order inversions occurred.

---

## 5. Ledger Artifact Reference

- Complete row-by-row decision and equity ledger: [`historical_five_policy_dry_run_ledger.csv`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/historical_five_policy_dry_run_ledger.csv)
- Total Ledger Records: 2,500 rows (500 bars $	imes$ 5 policies).
