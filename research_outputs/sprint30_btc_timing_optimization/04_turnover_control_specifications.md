# 04 — Turnover Control Engine Specifications

**Sprint ID:** `CBE_SPRINT30_BTC_TIMING_OPTIMIZATION`  
**Module:** `turnover_control_engine.py`  

---

## 1. Architectural Principles
The Turnover Control Engine enforces deterministic, rule-based constraints before any rebalance trade is permitted:

1. **Minimum Holding Period (`min_holding_period_hours`):**
   - After a rebalancing order executes, subsequent rebalancing requests are blocked until the elapsed time exceeds the holding period requirement (e.g. 24h, 72h, 168h).
2. **Allocation Hysteresis (`hysteresis_band_pct`):**
   - Creates a deadband buffer around technical triggers (e.g. ±2%).
3. **Minimum Rebalance Threshold (`min_rebalance_threshold_pct`):**
   - Rejects trade proposals where the difference between target allocation and current allocation is less than a minimum percentage (e.g. 5%, 10%, 15%).
4. **Rebalance Schedule Frequency (`rebalance_frequency`):**
   - Enforces periodic boundaries: `HOURLY`, `DAILY` (00:00 UTC), `WEEKLY` (Monday 00:00 UTC), `MONTHLY` (1st day 00:00 UTC).
5. **Minimum Trade Notional (`min_trade_notional_usdt`):**
   - Rejects economically insignificant orders under a threshold (e.g. $10, $100, $250).
6. **Turnover Budget Cap (`max_turnover_budget_ratio`):**
   - Imposes a hard ceiling on cumulative portfolio turnover.
7. **Transparent Trade Rejection Audit Ledger:**
   - Every rejected proposal is appended to `rejection_ledger` with timestamp, proposed allocation, current allocation, elapsed holding hours, notional, and exact rejection reason.
