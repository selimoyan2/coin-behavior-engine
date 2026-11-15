# 01 — Portfolio Accounting Root Cause Analysis & Reconciliation
## Forensic Audit of Valuation Discrepancies Across Historical BTC Timing Policies

**Sprint ID:** `CBE_SPRINT32_1_ACCOUNTING_AND_FORENSIC_CLOSURE`  
**Audit Date UTC:** `2026-11-15T14:10:00Z`  
**Repository Baseline:** `e7d2d2504573e50f0e43a11ce04f45304b460ec3`  
**Auditor Classification:** `ALL_POLICIES_RECONCILED_WITH_DOCUMENTED_ROUNDING`  

---

## 1. Executive Summary of Discrepancies

In Sprint 32, the independent portfolio reconciliation report (`06_independent_portfolio_reconciliation.json`) reported the following values:

| Policy Key | Persisted Published Equity | Sprint 32 Auditor Reconstructed Equity | Apparent Discrepancy | Sprint 32 Inappropriate Verdict |
|---|---:|---:|---:|---|
| `POLICY_BUY_AND_HOLD` | 9,030.69 USDT | 9,029.88 USDT | -0.8101 USDT | `EXACT_MATCH_ZERO_DISCREPANCY` (False Claim) |
| `POLICY_TREND_LOW_TURNOVER` | 7,120.36 USDT | 7,119.73 USDT | -0.6307 USDT | `EXACT_MATCH_ZERO_DISCREPANCY` (False Claim) |
| `POLICY_PERIODIC_REBALANCE` | 9,777.47 USDT | 9,776.60 USDT | -0.8667 USDT | `EXACT_MATCH_ZERO_DISCREPANCY` (False Claim) |
| `POLICY_DERIVED_REGIME_CONFIRMATION` | 5,767.02 USDT | 5,766.89 USDT | -0.1332 USDT | `EXACT_MATCH_ZERO_DISCREPANCY` (False Claim) |
| `POLICY_SIMPLE_TREND` | 3,739.79 USDT | 3,739.79 USDT | +0.0032 USDT | `EXACT_MATCH_ZERO_DISCREPANCY` (False Claim) |
| `POLICY_USDT_CASH` | 10,000.00 USDT | 10,000.00 USDT | 0.0000 USDT | `EXACT_MATCH` |

---

## 2. Forensic Step-by-Step Investigation

### 2.1. Persisted Trade Ledger Location
All trade execution records are persisted in:
`research_outputs/sprint31_sealed_shadow_evaluation/08_historical_shadow_portfolio_results.json`
Every trade contains:
- `timestamp_ms`, `timestamp_iso`
- `side` (BUY/SELL)
- `nominal_price` ($P_{\text{nom}}$)
- `effective_price` ($P_{\text{eff}} = P_{\text{nom}} \times (1 \pm \text{half\_spread} \pm \text{slippage})$)
- `btc_quantity` (evaluated to 8 decimal places: satoshi precision)
- `fee_usdt` (10 bps of gross notional)
- `spread_cost_usdt` (2.5 bps half-spread)
- `slippage_cost_usdt` (5 bps slippage)
- `net_usdt_impact`
- `usdt_balance_after`, `btc_balance_after`, `equity_usdt_after`

### 2.2. Valuation Timestamp and Dataset Bar
The evaluation dataset is `data/historical/historical_binance_btcusdt_1h_2025.parquet`, containing exactly 8,760 hourly bars (January 1, 2025 00:00:00 UTC through December 31, 2025 23:00:00 UTC).
- **Final Bar Index:** 8,759 (Bar #8,760)
- **Exact Valuation Timestamp:** `2025-12-31T23:00:00+00:00` (Unix timestamp ms: `1767222000000`)
- **Close Time:** `1767225599999` (`2025-12-31 23:59:59.999 UTC`)
- **OHLCV Values on Final Bar:**
  - Open: `87,728.30 USDT`
  - High: `87,728.30 USDT`
  - Low: `87,619.67 USDT`
  - **Close (Terminal Mark-to-Market Price): `87,648.22 USDT`**
  - Volume: `191.19123 BTC`

### 2.3. Root Cause of the 0.81–0.87 USDT Discrepancy
In Sprint 32, `src/coin_behavior_engine/product/btc_timing_research/transaction_cost_auditor.py` line 94 and line 180 erroneously hardcoded:
```python
final_btc_price: float = 87640.40  # ERRONEOUS HARDCODED PRICE
```
This hardcoded price created an artificial valuation error:
$$\Delta P = 87,648.22 - 87,640.40 = +7.82\text{ USDT per BTC}$$

Multiplying this price difference by the terminal BTC holdings of each policy explains the exact discrepancies observed in Sprint 32:

1. **`POLICY_BUY_AND_HOLD`:**
   - Terminal BTC: `0.10294779 BTC`
   - Artificial error: $0.10294779 \times 7.82 = +0.8051\text{ USDT}$
   - Reconstructed at 87,640.40: $7.49 + (0.10294779 \times 87640.40) = 9,029.88\text{ USDT}$
   - Reconstructed at genuine 87,648.22: $7.4944 + (0.10294779 \times 87648.22) = 9,030.6849\text{ USDT}$
   - Difference vs Published (9,030.69): **$-0.0051\text{ USDT}$** ($\le \frac{1}{2}$ cent).

2. **`POLICY_TREND_LOW_TURNOVER`:**
   - Terminal BTC: `0.08117562 BTC`
   - Artificial error: $0.08117562 \times 7.82 = +0.6348\text{ USDT}$
   - Reconstructed at 87,640.40: $5.47 + (0.08117562 \times 87640.40) = 7,119.73\text{ USDT}$
   - Reconstructed at genuine 87,648.22: $5.4655 + (0.08117562 \times 87648.22) = 7,120.3641\text{ USDT}$
   - Difference vs Published (7,120.36): **$+0.0041\text{ USDT}$** ($< \frac{1}{2}$ cent).

3. **`POLICY_PERIODIC_REBALANCE`:**
   - Terminal BTC: `0.11146963 BTC`
   - Artificial error: $0.11146963 \times 7.82 = +0.8717\text{ USDT}$
   - Reconstructed at 87,640.40: $7.36 + (0.11146963 \times 87640.40) = 9,776.60\text{ USDT}$
   - Reconstructed at genuine 87,648.22: $7.3603 + (0.11146963 \times 87648.22) = 9,777.4750\text{ USDT}$
   - Difference vs Published (9,777.47): **$+0.0050\text{ USDT}$** ($\le \frac{1}{2}$ cent).

4. **`POLICY_DERIVED_REGIME_CONFIRMATION`:**
   - Terminal BTC: `0.01646747 BTC`
   - Artificial error: $0.01646747 \times 7.82 = +0.1288\text{ USDT}$
   - Reconstructed at 87,640.40: $4323.67 + (0.01646747 \times 87640.40) = 5,766.89\text{ USDT}$
   - Reconstructed at genuine 87,648.22: $4323.6711 + (0.01646747 \times 87648.22) = 5,767.0155\text{ USDT}$
   - Difference vs Published (5,767.02): **$-0.0045\text{ USDT}$** ($< \frac{1}{2}$ cent).

5. **`POLICY_SIMPLE_TREND`:**
   - Terminal BTC: `0.00000000 BTC` (liquidated into USDT)
   - Unaffected by terminal BTC price: Cash balance is $3,739.7932\text{ USDT}$.
   - Difference vs Published (3,739.79): **$+0.0032\text{ USDT}$** ($< \frac{1}{2}$ cent).

6. **`POLICY_USDT_CASH`:**
   - Terminal BTC: `0.00000000 BTC`
   - Initial and final cash: $10,000.0000\text{ USDT}$.
   - Difference vs Published (10,000.00): **$0.0000\text{ USDT}$** (Exact Match).

---

## 3. Methodological and Reporting Rectifications

1. **Terminal Price Correction:**
   `transaction_cost_auditor.py` has been updated to use the authentic dataset closing price of **87,648.22 USDT** across all evaluation and reconciliation routines.
2. **Rejection of Inappropriate Zero-Discrepancy Claims:**
   The arbitrary tolerance threshold `< 1.50 USDT` has been removed. Any nonzero discrepancy is strictly prohibited from claiming `EXACT_MATCH_ZERO_DISCREPANCY` or `EXACT_MATCH`.
3. **Explicit Accounting Classifications:**
   - `EXACT_MATCH`: Residual is identically $0.0000\text{ USDT}$ (`POLICY_USDT_CASH`).
   - `MATCH_WITH_DOCUMENTED_ROUNDING`: Residual is bounded by fractional cent precision ($\le 0.01\text{ USDT}$), resulting strictly from intermediate trade rounding.
   - `MATERIAL_DISCREPANCY`: Residual exceeds 0.01 USDT but is within bounded parameters.
   - `UNRECONCILED`: Ledger missing or unaccounted divergence.
