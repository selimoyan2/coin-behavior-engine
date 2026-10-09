# NETWORK REQUEST BUDGET & RATE LIMIT SPECIFICATION

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. REQUEST PROFILES & CADENCE

| Phase | Request Type | Endpoint | Frequency | Payload Size | Weight Cost |
|:---|:---|:---|:---:|:---:|:---:|
| **Cold Start** | Historical Warm-up | `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&limit=350` | 1 request on boot | ~70 KB | 2 |
| **Steady State** | Finalized Bar Ingestion | `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&limit=2` | 1 req / 5 minutes | ~1 KB | 2 |
| **Gap Recovery** | Contiguity Repair | `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&startTime=...` | Bounded (max 2 reqs) | ~10 KB | 2 |

---

## 2. BINANCE RATE LIMIT CONSUMPTION

- **Binance IP Rate Limit:** 1,200 request weight per minute.
- **Steady State Rate:** 0.2 requests / minute (Weight = 0.4 / minute).
- **Rate Limit Utilization:**
  $$\frac{0.4}{1,200} = \mathbf{0.033\%} \text{ of Binance limit}$$
- **Safety Margin:** 99.967% headroom remaining.

---

## 3. RETRY & OUTAGE POLICY

1. Maximum retries per 5m interval: 3 attempts with exponential backoff (2s, 4s, 8s).
2. If all 3 retries fail: collector transitions to `PAUSED` fail-closed; does not flood Binance API.
3. No live API calls were made in this Sprint.
