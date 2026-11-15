# 07 — Out-of-Sample Stability & Degradation Analysis

**Sprint ID:** `CBE_SPRINT30_BTC_TIMING_OPTIMIZATION`  
**Stability Ruling:** **`MODERATE_DEGRADATION`**  

---

## 1. Scientific Analysis of Out-of-Sample Degradation

### Why Did Returns Degrade from +64.10% (In-Sample) to +3.38% (Out-of-Sample)?
1. **Regime Shift in the Underlying Market:**
   - **Training Window (Oct 2023 – Mar 2024):** Powerful secular bull market where BTC advanced from $27,000 to $73,000 (+170%). Trend-following strategies with hysteresis captured the entire upward expansion while avoiding whipsaws.
   - **Testing Window (Apr 2024 – Oct 2024):** Protracted 7-month choppy consolidation in the $53,000–$72,000 range.
2. **Protection Against Catastrophic Loss:**
   - While unconstrained Simple Trend suffered a **-23.39%** loss ($7,660 ending equity) due to 700 whipsaw executions, the low-turnover trend filter with 2% hysteresis delivered **+3.38%** out-of-sample and **+69.6%** over the full dataset ($16,963 ending equity).
3. **Conclusion:**
   - Parameter optimization does not immunize a trend-following policy against market regime shifts (bull market to consolidation), but turnover-control mechanisms successfully prevent catastrophic fee drag and capital destruction.
