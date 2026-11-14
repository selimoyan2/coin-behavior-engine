# FROZEN MODEL CAPABILITY MAPPING & INDICATOR ISOLATION

**Sprint ID:** `CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO`  
**Model Identifier:** `CBE-0.7.0`  
**Model Status:** `STRICTLY_FROZEN`  
**Governance Invariant:** No model weights, classification boundaries, or feature logic may be retrained or altered.

---

## 1. Extracted Indicators & Regime Signals

The BTC Timing Research Engine uses only features computed strictly from historical price/volume data using the frozen CBE-0.7.0 specification:

1. **Trend Features:**
   - `SMA(20)`: 20-hour simple moving average of close price.
   - `SMA(50)`: 50-hour simple moving average of close price.
   - `EMA(12)`: 12-hour exponential moving average.
   - `EMA(26)`: 26-hour exponential moving average.
   - `sma_trend_signal`: Binary flag (1 if SMA20 >= SMA50 else 0).

2. **Volatility Features:**
   - `realized_vol_24h`: 24-hour rolling standard deviation of log returns.
   - `parkinson_vol_24h`: 24-hour Parkinson high-low extreme value volatility estimator.
   - `volatility_percentile`: Rolling quantile rank of current volatility over past 168 hours (7 days).
   - `volatility_regime`: Discrete state in `{'COMPRESSED_VOLATILITY', 'NORMAL_VOLATILITY', 'HIGH_VOLATILITY', 'EXTREME_VOLATILITY'}`.

3. **CBE-0.7.0 Market Regimes:**
   - `MOMENTUM_EXPANSION`: Strong upward trend with expanding volume and moderate volatility.
   - `CAPITULATION`: Sharp downward sell-off with extreme volatility and volume spike.
   - `MEAN_REVERTING`: Sideways range-bound oscillating behavior.
   - `HIGH_VOLATILITY_EXPANSION`: Directionless high-dispersion regime.

All indicator transformations are verified strictly point-in-time with zero future information leakage.
