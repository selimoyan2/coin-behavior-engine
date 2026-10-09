# SPRINT 09.8: PRODUCTION FEED ARCHITECTURE AUDIT

**Target:** Audit of Live CBE-0.7.0 Market Data Ingestion Pipeline  
**Source Code Inspected:** `src/coin_behavior_engine/prospective/worker.py` and `src/coin_behavior_engine/ingestion/binance.py`  
**Mode:** Read-only inspection (Zero exchange API calls, zero production mutation)  

---

## 1. MARKET DATA INGESTION CHARACTERISTICS

- **Market Data Provider:** Binance Spot Public REST API (`https://api.binance.com`).
- **Endpoint:** `/api/v3/klines` (public, requires no API keys or authentication).
- **Fetch Cadence:** Periodic every 5 minutes (timed to 5 seconds after candle close via `get_next_5m_target(buffer_sec=5.0)`).
- **Candle Interval:** `5m` (5 minutes).
- **Candle Closure Semantics:** Strictly closed candles. In Binance klines, `k[6]` represents `close_time_ms` (e.g., `12:04:59.999` for a bar opening at `12:00:00.000`).
- **OHLCV Fields Provided by API:**
  - `k[0]`: Open time ms
  - `k[1]`: Open price (string float)
  - `k[2]`: High price (string float)
  - `k[3]`: Low price (string float)
  - `k[4]`: Close price (string float)
  - `k[5]`: Volume (BTC base asset volume)
  - `k[6]`: Close time ms
  - `k[7]`: Quote asset volume (USDT)
  - `k[8]`: Number of trades
  - `k[9]`: Taker buy base asset volume
  - `k[10]`: Taker buy quote asset volume
- **Volume Units:** Base asset volume (`BTC`).
- **Timestamp Representation:** Milliseconds since Unix epoch (`open_time_ms`, `close_time_ms`).

---

## 2. DEFECT IDENTIFICATION IN EXISTING PRODUCTION WORKER

The inspection reveals the exact architectural reason why CBE-0.7.0 failed to compute 24-hour features:

1. **Deficient Historical Lookback Buffer:**
   `ProspectiveWorker.fetch_recent_klines(limit=60)` requests only **60 candles (5 hours)**.
   However, the canonical CBE-0.8.0 candidate model requires a 288-bar lookback (24 hours) with a minimum warm-up of 72 bars (6 hours).
2. **Ad-Hoc Feature Substitution:**
   Because only 60 bars were fetched, CBE-0.7.0 computed an ad-hoc 24-bar (2 hour) volume z-score instead of the true 288-bar volume z-score:
   ```python
   # CBE-0.7.0 line 282 in worker.py:
   mean_vol = np.mean(volumes[-24:]) if len(volumes) >= 24 else np.mean(volumes)
   std_vol = np.std(volumes[-24:]) if len(volumes) >= 24 else (np.std(volumes) + 1.0)
   vol_z = float((volumes[-1] - mean_vol) / (std_vol + 1e-8))
   ```
3. **Absence of Local Persistence:**
   The live worker did not persist historical raw candles to disk, requiring a fresh fetch upon every process restart.

---

## 3. FEED COMPATIBILITY VERDICT

- **Source API Capability:** **FULLY COMPATIBLE**. Binance `/api/v3/klines` supports `limit=1000` (up to 83 hours of 5-minute candles) in a single request.
- **Data Availability:** Base volume (`k[5]`) and closed prices (`k[4]`) are natively present.
- **Lookback Solution:** Maintaining a bounded rolling buffer of 300 candles in memory completely resolves the lookback requirement with **zero extra exchange polling**.
