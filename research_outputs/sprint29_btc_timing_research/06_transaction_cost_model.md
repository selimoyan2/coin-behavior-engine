# TRANSACTION COST MODEL & SLIPPAGE SPECIFICATION

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  

---

## 1. Canonical Cost Profiles

| Parameter | LOW_COST Profile | BASE_COST Profile (Default) | HIGH_COST Profile |
| :--- | :---: | :---: | :---: |
| Taker Exchange Fee | 5.0 bps (0.05%) | 10.0 bps (0.10%) | 20.0 bps (0.20%) |
| Bid-Ask Half-Spread | 1.0 bps (0.01%) | 2.5 bps (0.025%) | 5.0 bps (0.05%) |
| Adverse Slippage | 1.0 bps (0.01%) | 5.0 bps (0.05%) | 15.0 bps (0.15%) |
| **Total One-Way Drag** | **7.0 bps (0.07%)** | **17.5 bps (0.175%)** | **40.0 bps (0.40%)** |
| **Round-Trip Cost** | **14.0 bps (0.14%)** | **35.0 bps (0.35%)** | **80.0 bps (0.80%)** |

---

## 2. Mathematical Impact Formula

For order volume $V$ (in USDT) and nominal execution price $P_{nominal}$:

1. **Effective Buy Price:**
   $$P_{eff}^{buy} = P_{nominal} \times \left(1 + \frac{\text{spread}}{2} + \text{slippage}\right)$$
2. **Effective Sell Price:**
   $$P_{eff}^{sell} = P_{nominal} \times \left(1 - \frac{\text{spread}}{2} - \text{slippage}\right)$$
3. **Exchange Fee:**
   $$\text{Fee}_{USDT} = V \times \text{taker\_fee}$$
4. **Total Trade Cost Impact:**
   $$\text{Cost}_{total} = \text{Fee}_{USDT} + V \times \left(\frac{\text{spread}}{2} + \text{slippage}\right)$$
