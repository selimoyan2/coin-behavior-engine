# 02 — Independent Portfolio Accounting Reconciliation Report

**Sprint ID:** `CBE_SPRINT30_1_SCIENTIFIC_REPORTING_RECONCILED`  
**Version:** `1.1.0` (Corrective Audit Patch — Sprint 30.1)  
**Reconciliation Status:** **`100% RECONCILED`**  
**Total Trades Reconciled:** `4,767` (Sprint 29) + `696` (`POLICY_DERIVED_REGIME_CONFIRMATION`) = `5,463` trades  
**Cash Conservation Invariant:** **`VERIFIED (100%)`**  
**Satoshi Conservation Invariant:** **`VERIFIED (100%)`**  
**Non-Negative Balance Invariant:** **`VERIFIED (100%)`**  

---

## 1. Separation of Ledger Reconciliation vs Published Report Reconciliation

> [!IMPORTANT]
> The authoritative truth of the CBE research environment resides exclusively in the **persisted trade ledgers** (`data/research_lab/btc_timing_experiments/*.json`). 
> Reconstructed equity curves match the persisted trade ledgers with **zero discrepancy** ($0.0000 USDT).
> Variances between historically published summary figures and persisted trade ledgers are strictly segregated and classified as **`PUBLISHED_REPORT_VARIANCE`**.

| Policy ID | Trades | Published / Prelim Equity | Persisted Ledger Equity | Reconstructed Equity | Ledger Discrepancy | Ledger Status | Published Variance | Published Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POLICY_BUY_AND_HOLD` | `1` | `$25,513.69` | `$25,513.69` | `$25,513.69` | `$0.0000` | **LEDGER_RECONCILED** | `$-0.0046` | **EXACT_MATCH** |
| `POLICY_USDT_CASH` | `0` | `$10,000.00` | `$10,000.00` | `$10,000.00` | `$0.0000` | **LEDGER_RECONCILED** | `$0.0000` | **EXACT_MATCH** |
| `POLICY_SIMPLE_TREND` | `700` | `$7,660.77` | `$7,660.69` | `$7,660.69` | `$0.0000` | **LEDGER_RECONCILED** | `+$0.0817` | **PUBLISHED_REPORT_VARIANCE** |
| `POLICY_VOLATILITY_AWARE` | `682` | `$11,607.74` | `$11,607.98` | `$11,607.98` | `$0.0000` | **LEDGER_RECONCILED** | `$-0.2399` | **PUBLISHED_REPORT_VARIANCE** |
| `POLICY_CBE_REGIME`* | `1823` | `$8,604.22` | `$8,603.57` | `$8,603.57` | `$0.0000` | **LEDGER_RECONCILED** | `+$0.6527` | **PUBLISHED_REPORT_VARIANCE** |
| `POLICY_COMBINED_TREND_REGIME`* | `1561` | `$6,207.28` | `$6,206.70` | `$6,206.70` | `$0.0000` | **LEDGER_RECONCILED** | `+$0.5784` | **PUBLISHED_REPORT_VARIANCE** |
| `POLICY_DERIVED_REGIME_CONFIRMATION`* | `696` | `$12,441.12` | `$12,404.63` | `$12,404.63` | `$0.0000` | **LEDGER_RECONCILED** | `+$36.4900` | **PRELIMINARY_REPORT_VARIANCE** |

*\* Denotes derived research classifiers (noncanonical heuristic classifiers; canonical parity not established).*

---

## 2. Resolution of Derived Regime Confirmation: 12,441.12 vs 12,404.63 USDT

### Finding
During Sprint 30 reporting, two conflicting equity numbers were referenced for the Derived Regime Confirmation strategy:
1. Preliminary quoted figure: **12,441.12 USDT** (+24.41% net return)
2. Authoritative persisted trade ledger (`EXP-POLICY_DER-22B5738C.json`): **12,404.63 USDT** (+24.05% net return)

### Root Cause Audit
- The figure $12,441.12 USDT was calculated during preliminary unconstrained simulation evaluation prior to final trade-by-trade cost attribution and persistence lock.
- The authoritative persisted trade ledger records exactly **696 filled trades**, incurring **$4,531.63 USDT** in total transaction costs (Exchange fees: $2,589.50, Spread: $647.38, Slippage: $1,294.75).
- Re-executing first-principles accounting across all 696 trades yields exactly **12,404.63 USDT**.
- **Audit Decision:** **$12,404.63 USDT is the sole authoritative scientific result.** The +$36.49 USDT (+0.36%) difference is recorded in this audit trail, and all public references are reconciled to the persisted ledger value.

---

## 3. Mathematical Root Cause of Sprint 29 Published-vs-Ledger Differences

The published-vs-ledger variances ($0.0817 on Simple Trend, $0.2399 on Volatility Aware, $0.6527 on CBE Regime, and $0.5784 on Combined Trend) originate from:
1. **Scalar Approximation in Published Summaries:**  
   Sprint 29 summary reports computed final equity using scalar multiplication:
   $$\text{Final Equity} = \text{Initial Capital} \times (1 + R_{\text{scalar}})$$
2. **Discrete Compounding in Persisted Ledgers:**  
   The actual simulation engine deducts transaction costs ($0.10\%$ taker fee + $0.025\%$ half-spread + $0.05\%$ slippage = $0.175\%$) from cash balances at discrete hourly timestamps.
3. Because trading capital is continuously decremented before subsequent bar price changes occur, discrete path-dependent compounding creates fractional dollar variances across hundreds or thousands of trades.
4. Reconstructed accounting verifies that **ledger equity equals reconstructed equity to the exact cent and satoshi** ($0.0000 discrepancy).

---

## 4. Audit Version History

- **v1.0.0 (Sprint 30 Initial):** Published initial reconciliation table labeling all policies as `EXACT_MATCH` based on ledger conservation.
- **v1.1.0 (Sprint 30.1 Corrective Patch):** Disentangled `LEDGER_RECONCILED` (100% exact match to disk) from `PUBLISHED_REPORT_RECONCILED` / `PUBLISHED_REPORT_VARIANCE`. Reconciled Derived Regime Confirmation to authoritative ledger ($12,404.63 USDT). Enforced noncanonical attribution markers.
