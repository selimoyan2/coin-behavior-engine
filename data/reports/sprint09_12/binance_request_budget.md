# BINANCE PUBLIC API REQUEST BUDGET & WEIGHT ANALYSIS

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**ENDPOINT:** Binance Spot Public Market Data (`GET /api/v3/klines`)  

---

## 1. REQUEST QUANTIFICATION TABLE

| Operational Phase | Request Endpoint & Query | Cadence / Trigger | Request Weight | Daily Request Count | Daily Weight Total |
|:---|:---|:---:|:---:|:---:|:---:|
| **Cold Start** | `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&limit=350` | 1 request on container boot | 2 | 1 (boot only) | 2 |
| **Steady State** | `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&limit=2` | 1 request every 5 minutes | 2 | 288 | 576 |
| **Gap Recovery** | `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&startTime=...` | On missing sequence (max 3 bars) | 2 | $\le 10$ (worst-case) | $\le 20$ |
| **Total Daily Budget** | — | — | — | **~290 requests** | **~598 weight** |

---

## 2. BINANCE RATE LIMIT COMPARISON

- **Binance IP Rate Limit:** 1,200 weight / minute = 1,728,000 weight / day.
- **Collector Consumption:** 598 weight / day.
- **Consumption Ratio:**
  $$rac{598}{1,728,000} = \mathbf{0.0346\%} 	ext{ of Binance limit}$$
- **Impact on Neighbor Containers:** Negligible. Existing CBE-0.7.0 worker consumes ~576 weight/day. Combined consumption of both services is < 1,200 weight/day, representing < 0.07% of the IP threshold.

---

## 3. STRICT CONTROLS & TIMESTAMPS

1. **Closed Candles Only:** `limit=2` fetches the most recently closed bar. Open/unfinalized candles are ignored.
2. **Monotonicity Enforcement:** `timestamp_open` must strictly equal `prev_timestamp_close + 1`.
3. **Zero Requests in Current Sprint:** Zero live HTTP calls were made during Sprint 09.12.
