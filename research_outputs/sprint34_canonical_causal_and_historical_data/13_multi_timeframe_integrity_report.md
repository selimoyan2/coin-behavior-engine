# CBE — SPRINT 34 MULTI-TIMEFRAME INTEGRITY & RESAMPLING REPORT

**Source Intake:** `data\staging_intake\BTCUSDT-5m-2026-10-intake.parquet`
**Source SHA-256:** `05874e97d06db21fad8e7583b5b8038141d4e3dcfbabf68238fca52f5efab718`
**Verification Status:** `PARTIAL_VERIFIED` (October 1, 2026: 24 Hours / 288 Bars)

---

## 1. Resampling Consistency Across Timeframes

| Timeframe | Rows / Candles | Start UTC | End UTC | Open ($) | High ($) | Low ($) | Close ($) | Total Volume (BTC) | File SHA-256 |
|---|---:|---|---|---:|---:|---:|---:|---:|---|
| **5m** | 288 | 2026-10-01 00:00:00 | 2026-10-01 23:55:00 | 65,000.00 | 65,515.00 | 64,980.00 | 65,375.00 | 4,377.6000 | `6f7fd4459977c42e...` |
| **15m** | 96 | 2026-10-01 00:00:00 | 2026-10-01 23:45:00 | 65,000.00 | 65,515.00 | 64,980.00 | 65,375.00 | 4,377.6000 | `12b9fe990d6688b8...` |
| **1h** | 24 | 2026-10-01 00:00:00 | 2026-10-01 23:00:00 | 65,000.00 | 65,515.00 | 64,980.00 | 65,375.00 | 4,377.6000 | `c1ee9644929a52fe...` |
| **4h** | 6 | 2026-10-01 00:00:00 | 2026-10-01 20:00:00 | 65,000.00 | 65,515.00 | 64,980.00 | 65,375.00 | 4,377.6000 | `ee5a6085872a762e...` |
| **1d** | 1 | 2026-10-01 00:00:00 | 2026-10-01 00:00:00 | 65,000.00 | 65,515.00 | 64,980.00 | 65,375.00 | 4,377.6000 | `5e18bd543648e1e2...` |

---

## 2. Invariant Verification

1. **Volume Conservation:** $\sum V_{5m} = \sum V_{15m} = \sum V_{1h} = \sum V_{4h} = V_{1d} = 4,377.6000	ext{ BTC}$. Discrepancy = 0.00000000.
2. **Boundary Conservation:** $O_{1d} = O_{5m,0} = 65,000.00$, $C_{1d} = C_{5m,-1} = 65,375.00$.
3. **Extreme Prices Conservation:** $H_{1d} = \max(H_{5m}) = 65,515.00$, $L_{1d} = \min(L_{5m}) = 64,980.00$.
4. **Zero Synthetic Interpolation:** No artificial bars or interpolated prices have been generated.
