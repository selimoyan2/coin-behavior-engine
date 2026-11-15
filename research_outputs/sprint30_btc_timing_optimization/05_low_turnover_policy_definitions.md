# 05 — Experimental Low-Turnover Policy Definitions

**Sprint ID:** `CBE_SPRINT30_BTC_TIMING_OPTIMIZATION`  
**Module:** `experimental_policies.py`  

---

## 1. Low-Turnover Trend Filter with Hysteresis (`POLICY_TREND_LOW_TURNOVER`)
- **Fast Window:** 20 hours  
- **Slow Window:** 50 hours  
- **Hysteresis Band:** ±2.0%  
- **Rule:**
  - If in cash ($0\%$ BTC): Price must rise ABOVE $\text{SMA}_{50} \times 1.02$ to BUY ($100\%$ BTC).
  - If in BTC ($100\%$ BTC): Price must fall BELOW $\text{SMA}_{50} \times 0.98$ to SELL ($0\%$ BTC).
  - Inside the band $[0.98 \times \text{SMA}_{50}, 1.02 \times \text{SMA}_{50}]$, existing allocation is maintained.

## 2. Volatility Allocation with Threshold Filter (`POLICY_VOLATILITY_HYSTERESIS`)
- **Threshold:** 10.0%  
- **Rule:** Target allocation shifts only when the newly desired volatility tier differs from current allocation by at least 10%.

## 3. Derived Regime with Multi-Bar Confirmation (`POLICY_DERIVED_REGIME_CONFIRMATION`)
- **Confirmation Requirement:** 3 consecutive hourly bars in a new regime.  
- **Rule:** Transient 1–2 bar classification flickers are ignored.

## 4. Risk-Controlled Trend Following (`POLICY_RISK_CONTROL_TREND`)
- **Rule:** Trend following that caps exposure at 50% during ELEVATED volatility and cuts to 0% during EXTREME volatility or capitulation.

## 5. Weekly Periodic Rebalance Policy (`POLICY_PERIODIC_REBALANCE`)
- **Rule:** Rebalances strictly once per week on Monday 00:00 UTC based on trend filter. Intra-week noise is ignored.
