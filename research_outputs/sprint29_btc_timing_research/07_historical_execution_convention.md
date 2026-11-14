# HISTORICAL EXECUTION CONVENTION & CAUSALITY TIMELINE

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  

---

## 1. Information Availability Timeline

```
 Candle [T-1, T]                           Decision Point T                   Candle [T, T+1]
+-----------------------------------------+----------------------------------+-------------------------+
| Opens: T - 3,600,000 ms                 | T = Candle T Close Time          | Opens: T ms             |
| Price fluctuates (Open, High, Low)      | Indicators calculated on [0..T]  | Execution Price = Open  |
| Closes: T ms (Price becomes immutable)  | Publication Lag: T + 1000 ms     | Rebalance filled        |
+-----------------------------------------+----------------------------------+-------------------------+
```

1. **No Lookahead Guarantee:**
   A candle covering $[T-1, T]$ cannot be used for decision making until timestamp $T$.
2. **Simulated Execution Lag:**
   Orders generated from candle $T$ execute at timestamp $T + 1000$ ms using candle $T+1$'s open price.
3. **Execution Price:**
   Nominal execution price is strictly the opening price of the subsequent bar, adjusted for bid-ask spread and slippage.
