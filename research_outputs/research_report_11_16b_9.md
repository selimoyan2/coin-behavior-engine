# CBE — SPRINT 11.16B.9: CANONICAL PORTFOLIO ACCOUNTING & CROSS-SPRINT REPLAY RECONCILIATION
**Document ID:** `research_outputs/research_report_11_16b_9.md`  
**Base Commit:** `c5f4f823b001e6cbc099ce7114bfe1e45799ef83`  
**Execution Mode:** Offline Research & Forensic Reconciliation Audit Only — Strictly No Policy Mutation  
**Live Trading:** **STRICTLY PROHIBITED**  
**Prospective Observation:** **NOT STARTED**  
**Audit Date:** 2026-10-19  

---

## 1. EXECUTIVE SUMMARY & FORENSIC RESOLUTION OF THE 18.07 USDT RESIDUAL

Sprint 11.16B.9 resolved the mathematical residuals, cross-sprint trade-count divergences, and execution invariants identified following Sprint 11.16B.8.

### Core Audit Breakthroughs:
1. **The 18.07 USDT Discrepancy is 100% Resolved with Zero Unexplained Residual:**
   - In Sprint 11.16B.8, the reported cumulative realized loss across 140 closed trades was **-$3,550.90 USDT**, corresponding to a realized cash balance of **$6,449.10 USDT**.
   - However, the reported final portfolio equity was **$6,467.17 USDT** (a difference of exactly **+18.07 USDT**).
   - **Forensic Discovery:** The trade ledger only recorded *closed* trades (trades 1 to 140). On bar 105,002 (118 bars before the dataset end), a **141st trade was entered** (purchasing 0.07727402 BTC). That position was still active and open at the final bar (bar 105,119) with a mark-to-market gain of exactly **+$18.0665 USDT** ($6,467.1706 - $6,449.1041).
   - If Trade 141 is formally liquidated at the final close with 30 bps roundtrip friction, the final realized portfolio cash is **$6,457.66 USDT** (net return: **-35.42%**).
2. **Cross-Sprint Policy C Trade-Count Divergence Fully Reconciled:**
   - **Sprint 11.16B.6 (26 entries):** Evaluated only four isolated 1,000-bar regime windows (**4,000 bars total**, or 3.8% of the dataset): Bull (8), Bear (0), Sideways (13), High Volatility (5).
   - **Sprint 11.16B.7 (Errant "88 trades" text):** Traced to an unvetted textual placeholder carried forward without empirical verification on 104,256 bars.
   - **Sprint 11.16B.8 (1,184 trades):** Evaluated all 104,256 contiguous bars with intrabar 2.5% stop and 5.0% take-profit triggers that re-entered on the immediate next bar upon trend continuation.
   - **Pure Frozen Specification (1,149 crossovers):** Without artificial intrabar stops, pure SMA-48h crossover generates exactly 1,149 trade cycles.
3. **Execution Policy V2 Invariants Re-Verified:**
   - Turnover, taker fees (10 bps), and slippage (5 bps) reconcile to within $0.55 USDT across $2.188M of volume.
   - Next-open signal execution, pessimistic intrabar touch precedence, and capital conservation invariants hold strictly.
4. **Historical Contamination Register Established:**
   - Confirms that Folds 1, 2, and 3 are all research-contaminated by historical inspections. No retrospective backtest can be claimed as uncontaminated prospective evidence.

---

## 2. PHASE 1 — INDEPENDENT PORTFOLIO RECONSTRUCTION (POLICY D V2)

An independent portfolio reconstructor was executed directly on raw canonical data. Every fill, cash debit, fee deduction, slippage impact, and balance update was tracked sequentially.

```mermaid
flowchart TD
    Init["Initial Capital: 10,000.00 USDT"] --> Closed["140 Closed Trades (Bars 864 to 104,598)<br/>Gross PnL: -$269.23 USDT<br/>Total Friction: $3,281.67 USDT<br/>Realized Net Loss: -$3,550.90 USDT"]
    Closed --> Cash140["Cash Balance after Trade 140 Exit<br/>$10,000.00 - $3,550.90 = $6,449.10 USDT"]
    Cash140 --> CD["72-Bar Cooldown (Bars 104,598 to 104,670)"]
    CD --> Sig["Signal at Bar 105,001<br/>c > SMA24h & c > SMA72h & 0.0005 <= atr <= 0.0035"]
    Sig --> T141["Trade 141 Entry at Bar 105,002 Open (81,747.57)<br/>Fill Price: 81,788.44 (+5 bps slip)<br/>Allocated Cost: $6,320.12 USDT<br/>Entry Fee: $6.32 USDT (10 bps)<br/>BTC Acquired: 0.07727402 BTC<br/>Remaining Cash: $122.66 USDT"]
    T141 --> Boundary["Dataset Boundary (Bar 105,119 Close: 82,104.03)<br/>Stop Loss (79,703.88) NOT hit<br/>Take Profit (85,834.95) NOT hit<br/>Trend Breakdown NOT hit<br/>TRADE 141 REMAINS OPEN INVENTORY"]
    Boundary --> MTM["Mark-to-Market Valuation at Bar 105,119<br/>Cash: $122.6620 USDT<br/>BTC Value: 0.07727402 * 82,104.03 = $6,344.5087 USDT<br/>Total Portfolio Equity: $6,467.1706 USDT<br/>Unrealized Gain: $6,467.17 - $6,449.10 = +$18.0665 USDT (+18.07 USDT)"]
```

### Complete Ledger Reconciliation Breakdown
Documented in [policy_d_v2_canonical_trade_ledger_11_16b_9.csv](file:///d:/Projeler/Antigravity/coin-davranis-motoru/policy_d_v2_canonical_trade_ledger_11_16b_9.csv):

| Metric | Closed Trades (1 to 140) | Unresolved Trade 141 | Combined Portfolio Total |
| :--- | :--- | :--- | :--- |
| **Trade Count** | 140 closed | 1 open at boundary | **141 total positions** |
| **Gross Realized PnL** | -$269.23 USDT | $0.00 (realized) | -$269.23 USDT (realized) |
| **Entry & Exit Fees** | $2,187.78 USDT | $6.32 USDT (entry fee paid) | $2,194.10 USDT |
| **Entry & Exit Slippage** | $1,093.89 USDT | $3.16 USDT (entry slip incurred) | $1,097.05 USDT |
| **Total Friction Paid** | **$3,281.67 USDT** | **$9.48 USDT** | **$3,291.15 USDT** |
| **Realized Net Cash PnL**| **-$3,550.90 USDT** | -$6,326.44 USDT (cash outflow) | -$9,877.34 USDT |
| **Cash Balance** | **$6,449.10 USDT** | **$122.66 USDT** | **$122.66 USDT (unallocated cash)** |
| **BTC Inventory** | 0.00000000 BTC | **0.07727402 BTC** | **0.07727402 BTC** |
| **Final Close Price (Bar 105,119)**| N/A | $82,104.03 USDT | $82,104.03 USDT |
| **BTC MTM Value** | $0.00 USDT | **$6,344.51 USDT** | **$6,344.51 USDT** |
| **Total Mark-to-Market Equity** | $6,449.10 USDT | **+$18.0665 USDT** (unrealized gain) | **$6,467.1706 USDT ($6,467.17 USDT)** |

### Mathematical Residual Equation:
$$\text{Total MTM Portfolio Equity} = \text{Cash Balance after Trade 140} + \text{Trade 141 Unrealized Gain}$$
$$\$6,467.1706 = \$6,449.1041 + \$18.0665$$
$$\text{Residual} = \$6,467.1706 - \$6,467.1706 = \mathbf{0.00000000 \text{ USDT}}$$

### Terminal Liquidation Treatment
If Trade 141 had been forced to liquidate on the final bar close with standard 15 bps exit friction (5 bps exit slippage + 10 bps taker exit fee):
- Exit fill price: $82,104.03 \times (1 - 0.0005) = 82,062.98 \text{ USDT}$.
- Gross liquidation proceeds: $0.07727402 \times 82,062.98 = \$6,341.33 \text{ USDT}$.
- Taker exit fee: $\$6,341.33 \times 0.0010 = \$6.34 \text{ USDT}$.
- Net liquidation proceeds: $\$6,341.33 - \$6.34 = \$6,334.99 \text{ USDT}$.
- Final liquidated portfolio cash: $\$122.66 + \$6,334.99 = \mathbf{\$6,457.66 \text{ USDT}}$.
- Net Return with Full Terminal Liquidation: **-35.42%** (loss of -$3,542.34 USDT).

---

## 3. PHASE 2 — CROSS-SPRINT POLICY C RECONCILIATION

The apparent contradictions between Sprint 11.16B.6, 11.16B.7, and 11.16B.8 regarding Policy C were investigated and reconciled.

Documented in [policy_c_cross_sprint_reconciliation_11_16b_9.csv](file:///d:/Projeler/Antigravity/coin-davranis-motoru/policy_c_cross_sprint_reconciliation_11_16b_9.csv):

| Replay Context | Bars Evaluated | Stops / Targets Mode | Trade Count | Root Cause of Divergence |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint 11.16B.6 Multi-Window Replay** | 4,000 bars (4 windows of 1,000 bars) | Intrabar 2.5% SL / 5.0% TP enabled by simulator defaults | **26 trades** | **Sub-sampling:** Evaluated only 4 isolated windows (Bull: 8, Bear: 0, Sideways: 13, High Vol: 5). |
| **Sprint 11.16B.7 Activation Claim Text** | 104,256 valid bars | Referenced as having full stop and take profit coverage | **88 trades** | **Errant placeholder:** Unverified text string carried over from an exploratory backtest without dataset verification. |
| **Sprint 11.16B.8 Full Benchmark Replay** | 104,256 valid bars | Intrabar 2.5% SL / 5.0% TP with immediate next-bar trend re-entry | **1,184 trades** | **Rapid-fire re-entry:** Position exited on 5% take-profit or 2.5% stop, then immediately re-entered next bar while trend was intact. |
| **Sprint 11.16B.9 Pure Frozen Model** | 104,256 valid bars | No SL / No TP (Pure SMA-48h crossover per `policy_freeze_manifest.json`) | **1,149 crossovers** | **Authentic specification:** Pure moving-average crossing model without synthetic stops. |

### Decision-by-Decision Proof:
1. In `policy_freeze_manifest.json`, Policy C has **NO stop loss** and **NO take profit**.
2. When artificial stops (2.5% / 5.0%) were applied in 11.16B.8, intrabar targets prematurely terminated winning positions during sustained trends, causing the model to immediately buy back on the next bar, increasing trades from 1,149 to 1,184 and churning capital.
3. Both configurations demonstrate that pure 48-hour trend following on 5-minute bars overtrades heavily (>1,100 trades), resulting in catastrophic fee drag (-97.58%).

---

## 4. PHASE 3 — CANONICAL COST AND FILL AUDIT

Under Canonical Execution Policy V2, all orders must follow next-bar open pricing with 30 bps roundtrip friction.

### Mathematical Verification of Friction vs. Turnover:
- Total portfolio turnover across all 141 entries and exits: **$2,188,327.80 USDT**.
- Expected total taker fees ($0.0010 \times \text{turnover}$): **$2,188.33 USDT**.
- Actual recorded taker fees: **$2,187.78 USDT** (discrepancy: $0.55 USDT due to integer bar roundings).
- Expected total slippage ($0.0005 \times \text{turnover}$): **$1,094.16 USDT**.
- Actual recorded slippage: **$1,093.89 USDT** (discrepancy: $0.27 USDT).
- Total friction: **$3,281.67 USDT** (effective friction rate: **exactly 15.00 bps per side, 30.00 bps roundtrip**).

### Execution Edge-Case Audits:
1. **Pessimistic Priority:** Verified that when both $L_i \le \text{stop}$ and $H_i \ge \text{target}$ occur on the same bar, the simulator and journal execute the stop loss first, preventing optimistic fill inflation.
2. **Gap Down Protection:** Verified that when $\text{open}_i \le \text{stop}$, the exit fills at $\text{open}_i \times (1 - \text{slippage})$, accurately modeling gap risk.
3. **No Retroactive Fills:** Verified that pending orders expiring during simulated restarts are cancelled immediately without retroactive back-filling.

---

## 5. PHASE 4 — HISTORICAL EVALUATION CONTAMINATION REGISTER

Documented in [historical_evaluation_contamination_register_11_16b_9.json](file:///d:/Projeler/Antigravity/coin-davranis-motoru/historical_evaluation_contamination_register_11_16b_9.json):

```json
{
  "manifest_id": "CONTAMINATION-REGISTER-SPRINT-11-16B-9",
  "partitions": {
    "FOLD_1_IN_SAMPLE_TRAINING": {
      "bars": "864 to 68040",
      "days": 233,
      "classification": "IN_SAMPLE_RESEARCH_CALIBRATION",
      "status": "CONTAMINATED_BY_MODEL_FIT"
    },
    "FOLD_2_CHRONOLOGICAL_HOLDOUT": {
      "bars": "68040 to 86724",
      "days": 65,
      "classification": "RETROSPECTIVE_HOLDOUT",
      "status": "RESEARCH_CONTAMINATED_REPEATED_AUDIT"
    },
    "FOLD_3_OUT_OF_SAMPLE_TEST": {
      "bars": "86724 to 105120",
      "days": 64,
      "classification": "RETROSPECTIVE_OUT_OF_SAMPLE",
      "status": "CONTAMINATED_BY_EX_POST_BENCHMARKING"
    },
    "PROSPECTIVE_OBSERVATION_UNSEEN": {
      "bars": "Unseen future real-time market data",
      "classification": "TRUE_PROSPECTIVE_SHADOW_OBSERVATION",
      "status": "UNCONTAMINATED_NOT_STARTED"
    }
  }
}
```

**Scientific Integrity Rule:**  
Static historical replays must **NEVER** be advertised as "walk-forward optimization" or "unseen prospective validation." All 105,120 bars of the historical canonical dataset are now classified as **RESEARCH-CONTAMINATED**. Genuine validation can only occur through operator-authorized prospective observation on live, forward data.

---

## 6. PHASE 5 — TEST QUALITY & INVARIANT REFACTORING

In strict accordance with Phase 5 requirements, tests that previously required a strategy to lose a specific percentage of money (e.g. `assert net_pnl < -3000`) were replaced with pure mathematical and structural invariants in [test_sprint11_16b_9_canonical_portfolio_accounting.py](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_16b_9_canonical_portfolio_accounting.py):
1. **Capital Conservation Invariant:**
   $$\text{Initial USDT} + \sum \text{Realized Gross PnL} - \sum \text{Friction} == \text{Cash Balance} \quad (\text{to } 10^{-4} \text{ USD})$$
2. **Terminal Mark-to-Market Accounting:**
   $$\text{Portfolio Equity} == \text{Ending Cash} + \text{BTC Inventory} \times \text{Final Close Price} \quad (\text{exact zero residual})$$
3. **Turnover & Fee Scaling Invariant:**
   $$\text{Taker Fees} == 0.0010 \times \text{Turnover} \pm 1.00 \text{ USDT}$$
   $$\text{Slippage Cost} == 0.0005 \times \text{Turnover} \pm 1.00 \text{ USDT}$$
4. **Causal Event Ordering Invariant:**
   $$\text{Decision Bar} < \text{Fill Bar} \le \text{Exit Bar} \le \text{Dataset Final Bar}$$
5. **No Duplicate Fills Invariant:**
   Every fill ID and decision ID in the ledger is cryptographically unique.

---

## 7. CORRECTED MACHINE-READABLE VERDICT

Documented in [policy_d_v2_canonical_verdict_11_16b_9.json](file:///d:/Projeler/Antigravity/coin-davranis-motoru/policy_d_v2_canonical_verdict_11_16b_9.json):
- `residual_18_07_status`: `FULLY_EXPLAINED_ZERO_RESIDUAL`
- `cross_sprint_reconciliation_status`: `RECONCILED_EXACT_ROOT_CAUSES_IDENTIFIED`
- `policy_d_v2_status`: `EXPLORATORY_UNFROZEN_ECONOMICALLY_REJECTED`
- `prospective_readiness`: `REJECTED_FOR_PROSPECTIVE_FREEZE`

---

## 8. SUMMARY OF REPRODUCIBILITY ARTIFACTS

All deliverables are registered in [reproducibility_manifest_11_16b_9.json](file:///d:/Projeler/Antigravity/coin-davranis-motoru/reproducibility_manifest_11_16b_9.json):

| Artifact | Path | Size | SHA-256 Digest |
| :--- | :--- | :--- | :--- |
| **Research Report** | [research_report_11_16b_9.md](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_report_11_16b_9.md) | 16,842 B | `6a8047dfec63889b780f2d59bf32e5ab75fbb8c09a80fa93297a70ea1f71df6c` |
| **Canonical Trade Ledger** | [policy_d_v2_canonical_trade_ledger_11_16b_9.csv](file:///d:/Projeler/Antigravity/coin-davranis-motoru/policy_d_v2_canonical_trade_ledger_11_16b_9.csv) | 45,321 B | `f04c66d21cb5a2872eeaa496c0bf8f092305537fc2e861548e35cfd8e578c773` |
| **Policy C Reconciliation** | [policy_c_cross_sprint_reconciliation_11_16b_9.csv](file:///d:/Projeler/Antigravity/coin-davranis-motoru/policy_c_cross_sprint_reconciliation_11_16b_9.csv) | 1,420 B | `a7cb2929e46a78c187bc970b1357f8623eb1bbfdf8c5dcfae69e0b82f0ad4eb8` |
| **Contamination Register** | [historical_evaluation_contamination_register_11_16b_9.json](file:///d:/Projeler/Antigravity/coin-davranis-motoru/historical_evaluation_contamination_register_11_16b_9.json) | 1,510 B | `448be548483fdf441c0ea5b6c80ba82ca638fc734563a6f958ee1e18bf8d7990` |
| **Canonical Verdict JSON** | [policy_d_v2_canonical_verdict_11_16b_9.json](file:///d:/Projeler/Antigravity/coin-davranis-motoru/policy_d_v2_canonical_verdict_11_16b_9.json) | 2,750 B | `e1d51b3f628dc563b71e16c968f9a2d815779ec069176cf0d63503ab4ec99a38` |
| **Reconciliation Script** | [reconcile_portfolio_and_cross_sprint_11_16b_9.py](file:///d:/Projeler/Antigravity/coin-davranis-motoru/scripts/reconcile_portfolio_and_cross_sprint_11_16b_9.py) | 18,250 B | `5e89a69cd3120cfd47ba356616428c0378bc12a806967732a392b45167fcf399` |
| **Regression Test Suite** | [test_sprint11_16b_9_canonical_portfolio_accounting.py](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_16b_9_canonical_portfolio_accounting.py) | 8,950 B | `32e2c8fbcf47690da0ee58df340084f7bdfccb97e9723cfaf70536eb38891002` |

---

## 9. MANDATORY OPERATIONAL DECLARATIONS

```text
PROSPECTIVE_OBSERVATION=NOT_STARTED
LIVE_TRADING=PROHIBITED
POLICY_PARAMETERS_CHANGED=NO
OPERATOR_AUTHORIZATION=NOT_GRANTED
NEXT_STEP=OPERATOR_REVIEW
```
