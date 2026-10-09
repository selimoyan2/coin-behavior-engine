# SPRINT 09.9: PASSIVE DATA CAPTURE ARCHITECTURE AUDIT

**DATE:** 2026-10-09  
**PURPOSE:** Determine the technical feasibility of capturing live closed candles without modifying CBE-0.7.0.

---

## 1. PRODUCTION WORKER PERSISTENCE AUDIT

An audit of `src/coin_behavior_engine/prospective/worker.py` and `src/coin_behavior_engine/prospective/store.py` reveals:
1. The production worker persists **only**:
   - `PredictionRecord` (point forecasts, market state, timestamps).
   - `OutcomeRecord` (realized return when matured).
   - `audit_log.jsonl` (hash-chained initialization and freeze verification events).
2. The production worker **does NOT persist raw OHLCV candles** to disk or SQLite.
3. The production worker keeps only a transient 60-candle DataFrame in RAM and discards it after computing each prediction.

**Consequence**: A "passive tap" reading solely from production files **cannot obtain raw closed candles**.

---

## 2. COMPARISON OF ISOLATED CAPTURE DESIGNS

| Architecture | Description | API Requests | Production Impact | Feasibility |
| :--- | :--- | :--- | :--- | :--- |
| **A. Passive File Sniffer** | Attempt to read candles from CBE-0.7.0 disk output | 0 | Zero | **Infeasible** (CBE-0.7.0 does not store raw candles) |
| **B. Shared Ingestion Process** | Single collector writes candles to shared SQLite / FIFO queue; both engines read | 1 req / 5m | Requires modifying CBE-0.7.0 ingestion | **Prohibited** (Violates frozen CBE-0.7.0 model freeze) |
| **C. Independent Dedicated Poller** | Isolated daemon polling Binance `/api/v3/klines?limit=350` every 5 min | 1 req / 5m (288 / day) | **Zero (completely independent process)** | **RECOMMENDED & FEASIBLE** |
| **D. External Observation Host** | Entirely separate VPS running shadow capture | 1 req / 5m | Zero | Feasible, but incurs extra infrastructure cost |

---

## 3. RESOURCE & RATE-LIMIT IMPACT OF ARCHITECTURE C

- **Binance API Limits**: Binance provides an IP rate limit of 1,200 request weight per minute.
- **Dedicated Poller Consumption**:
  - Request: `GET /api/v3/klines?symbol=BTCUSDT&interval=5m&limit=350`
  - Weight: 2 per call.
  - Frequency: 1 call per 300 seconds.
  - Rate-limit consumption: `2 / (1,200 * 5) = 0.033%` of the available rate-limit budget.
- **Safety**: Running this isolated process locally consumes virtually zero network budget, does not touch CBE-0.7.0, and ensures strict prospective capture readiness.
