# PAPER PORTFOLIO DOUBLE-ENTRY ACCOUNTING SPECIFICATION

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  

---

## 1. Conservation of Value Equations

At any timestamp $t$:
$$E_t = B_{USDT, t} + B_{BTC, t} \times P_{BTC, t}$$
where:
- $E_t$ is total portfolio equity in USDT.
- $B_{USDT, t}$ is liquid uninvested USDT cash balance.
- $B_{BTC, t}$ is physical BTC quantity held.
- $P_{BTC, t}$ is the current mark-to-market BTC price.

## 2. Rebalancing Accounting

When a rebalance is required to reach target allocation $w^*$:
1. Desired BTC equity: $E_{target} = E_t \times w^*$
2. Current BTC equity: $E_{current} = B_{BTC, t} \times P_{BTC, t}$
3. Rebalance threshold: Rebalance is skipped if $|w_{actual} - w^*| < 0.01$ (1% drift deadband).
4. If buying:
   - Max spendable USDT: $B_{USDT, t}$
   - Cash outflow = $\Delta B_{BTC} \times P_{eff}^{buy} + \text{Fee}_{USDT}$
   - Cash balance decreases, BTC balance increases.
5. If selling:
   - Gross cash inflow = $\Delta B_{BTC} \times P_{eff}^{sell}$
   - Net cash inflow = Gross Inflow - $\text{Fee}_{USDT}$
   - BTC balance decreases, Cash balance increases.
