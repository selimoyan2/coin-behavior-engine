# PROSPECTIVE ELIGIBILITY AUDIT: FEATURE COMPUTABLE VS PROSPECTIVE SCORING ELIGIBLE

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. PURPOSE & SCIENTIFIC PRINCIPLES

In historical backtesting and offline model development, forecasts can mathematically be computed as soon as the rolling lookback satisfies minimal rolling window criteria (`MIN_WARMUP_BARS = 72` bars, representing 6 hours of 5-minute data).

However, in a genuine **prospective shadow observation protocol**, a forecast must satisfy all formal empirical constraints of prospective observation. A forecast generated during warm-up (bars 72–287) must **never** be counted as an eligible prospective observation.

---

## 2. STRICT CRITERIA COMPARISON

| Dimension | `FEATURE_COMPUTABLE` (Historical Replay) | `PROSPECTIVE_SCORING_ELIGIBLE` (Genuine Shadow) |
|:---|:---|:---|
| **Lookback Required** | $\ge 72$ contiguous bars (`MIN_WARMUP_BARS`) | $\ge 288$ contiguous bars (`FULL_WARMUP_BARS`) |
| **Collector State** | `WARMING_UP` or `FULL_WINDOW_READY` | Strictly `ELIGIBLE` |
| **Candle Continuity** | No gaps in preceding 72 bars | Zero gaps in full 288-bar lookback |
| **Source Provenance** | Replay fixtures or live buffer | Authenticated closed exchange candles |
| **Timing & Clock** | Monotonic timestamps | Clock skew $\le 2000$ ms, receipt $\ge$ close |
| **Durable Commit** | Appended to JSONL | Committed strictly prior to outcome maturity |
| **Record Label** | `HISTORICAL_REPLAY` or `WARMUP_REPLAY` | `PROSPECTIVE_SHADOW` |
| **Scoring Evaluation** | Excluded from prospective Brier/ECE scores | Included in prospective performance evaluation |

---

## 3. FAIL-CLOSED ENFORCEMENT IN COLLECTOR

1. In `collector.py`, if the rolling buffer has $72 \le 	ext{len} < 288$ candles:
   - `recon.status` is `"READY_PARTIAL_WARMUP"`.
   - `quality.eligible_for_prospective_scoring` is strictly `False`.
   - `state_machine.is_eligible` is strictly `False`.
   - `data_quality["prospective_scoring_eligible"]` is strictly `False`.
   - `record_label` is forced to `"WARMUP_REPLAY"` even if configured with `PROSPECTIVE_SHADOW`.
2. Exactly at 288 contiguous candles:
   - State machine transitions to `FULL_WINDOW_READY` and subsequently `ELIGIBLE`.
   - Predictions transition to `eligible_for_prospective_scoring: True`.
   - Denominators for prospective scoring strictly filter for `eligible_for_prospective_scoring == True`.
