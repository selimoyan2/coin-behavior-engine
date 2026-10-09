# SPRINT 09.8: VOLUME Z-SCORE 24H FORENSIC ANALYSIS

**Feature Name:** `volume_zscore_24h`  
**Status:** RECONSTRUCTED & MATHEMATICALLY VERIFIED (100% Exact Parity)  

---

## 1. TRAINING-TIME SPECIFICATION & PROVENANCE

In Sprint 02, the feature generation pipeline (`src/coin_behavior_engine/features/volume.py` and `scripts/run_sprint02_research.py`) established the canonical definition of `volume_zscore_24h` (aliased from `volume_zscore_baseline`):

```python
# Exact canonical formula:
w = 288  # 24 hours of 5-minute bars
min_p = max(2, w // 4)  # 72 bars (6 hours minimum warm-up)

v_mean = volume.rolling(window=w, min_periods=min_p).mean()
v_std = volume.rolling(window=w, min_periods=min_p).std().replace(0, np.nan)

# Volume z-score with clipping
volume_zscore_24h = ((volume - v_mean) / v_std).fillna(0.0).clip(-5.0, 15.0)
```

### Parameter Invariants:
1. **Raw Volume Source:** BTC base asset volume (Binance kline index 5).
2. **Rolling Window:** Exactly 288 bars (24.0 hours).
3. **Minimum Periods:** Exactly 72 bars (6.0 hours).
4. **Standard Deviation:** Sample standard deviation ($N-1$ degrees of freedom).
5. **Zero Variance Treatment:** Replaces zero with `NaN`, divides, then fills remaining NaNs with `0.0`.
6. **Clipping Bounds:** Hard clip at `[-5.0, 15.0]` to prevent extreme outlier leverage.

---

## 2. RECONSTRUCTION VERIFICATION

Using `FeedAdapterV080`, we recomputed `volume_zscore_24h` from raw historical closed candles and compared it against the precomputed derived research dataset (`features_with_outcomes_5m.parquet`):
- **Maximum Absolute Discrepancy:** `8.88e-16` (machine epsilon precision).
- **Parity Result:** **100% EXACT PARITY**.

---

## 3. PROSPECTIVE IMPLEMENTATION REQUIREMENTS

- **No New API Endpoint Required:** Binance `/api/v3/klines` provides `volume` directly.
- **Bounded Buffer:** A rolling buffer of 300 candles (capacity ~25 hours) in memory requires less than 50 KB of RAM.
- **Cold-Start Handling:** Upon worker startup, an initial fetch of `limit=300` candles instantly satisfies the 288-bar warm-up, allowing immediate valid feature generation on the very first prospective closed candle.
