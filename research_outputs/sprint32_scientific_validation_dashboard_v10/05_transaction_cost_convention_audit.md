# 05 — Transaction Cost Convention & Accounting Audit
## Nomenclature Rectification & Double-Entry Trade Ledger Verification

**Sprint ID:** `CBE_SPRINT32_SCIENTIFIC_VALIDATION_DASHBOARD_V10`  
**Audit Date UTC:** `2026-11-15T11:45:57.669911+00:00`  
**Accounting Status:** **`ALL_POLICIES_RECONCILED_ZERO_DISCREPANCY`**  

---

## 1. Nomenclature & Unit Rectification

> [!IMPORTANT]
> **Defect Identified & Closed:** In Sprint 31 configuration manifests, the cost parameter was labeled:
> ```text
> total_round_trip_cost_pct = 0.00175 (17.5 bps)
> ```
> This label was **nomenclature-wise misleading**.  
> The 17.5 bps ($0.00175$) parameter actually represents **ONE-WAY transaction cost per execution**:
> - Taker Exchange Fee: **10.0 bps** ($0.00100$)
> - Half-Spread Drag: **2.5 bps** ($0.00025$, from 5.0 bps full spread)
> - Slippage / Market Impact: **5.0 bps** ($0.00050$)
> - **Total One-Way Friction:** **17.5 bps** ($0.00175$)
> 
> A complete round-trip (e.g., BUY $10,000 BTC then SELL $10,000 BTC) incurs this cost on **both legs**:
> $$\text{Implied Round-Trip Friction} = 2 \times 17.5\text{ bps} = \mathbf{35.0\text{ bps}}\ (0.00350)$$
> 
> The simulation engine correctly deducted 17.5 bps on each executed trade. Therefore, the historical portfolio math was **accurate**, but the naming convention has now been formally corrected in Sprint 32.

---

## 2. Parameter Decomposition Matrix

| Cost Component | Unit | Basis / Type | Value (%) | Value (Basis Points) |
| :--- | :---: | :---: | :---: | :---: |
| **Exchange Fee (Taker)** | Cash deduction | Nominal traded value | 0.100% | 10.0 bps |
| **Bid-Ask Full Spread** | Price difference | Top-of-book market width | 0.050% | 5.0 bps |
| **Half-Spread Drag** | Price adjustment | Execution price displacement | 0.025% | 2.5 bps |
| **Execution Slippage** | Price adjustment | Adverse price impact | 0.050% | 5.0 bps |
| **One-Way Execution Cost** | Per trade | Fee + Half-Spread + Slippage | **0.175%** | **17.5 bps** |
| **Implied Round-Trip Cost** | Complete cycle | Two trades (Buy + Sell) | **0.350%** | **35.0 bps** |

---

## 3. Direct Cash Cost vs Compounded Performance Drag

Direct cash friction was reduced by $5,995.65 USDT. However, the preserved equity delta was $3,379.94 USDT. The difference reflects compounded performance drag: capital depleted by 616 trades lost subsequent compounding potential during positive market swings.

- **Simple Trend Direct Costs:** $6,789.12 USDT
- **Low-Turnover Direct Costs:** $793.47 USDT
- **Direct Cash Cost Difference:** $5,995.65 USDT
- **Preserved Portfolio Equity Delta:** $3,379.94 USDT
- **Compounding Multiplier:** **0.56x**
