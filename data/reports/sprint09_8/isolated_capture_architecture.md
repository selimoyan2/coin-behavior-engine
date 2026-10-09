# SPRINT 09.8: ISOLATED DATA CAPTURE ARCHITECTURE

**Target:** Zero-Overhead Passive Data Tap for Future Prospective Shadow Worker  
**Design Principle:** Strict decoupling from production CBE-0.7.0 execution path  

---

## 1. ARCHITECTURAL TOPOLOGY

```text
[ Binance REST API (/api/v3/klines) ]
                |
                v (Single 5-minute request by background collector)
  [ Local Closed Candle Ingestion Tap ]
                |
                +---> [ CBE-0.7.0 Legacy Worker (Frozen) ]
                |
                +---> [ Bounded Rolling Buffer (300 candles in memory) ]
                                |
                                v
                [ FeedAdapterV080 (Feature Reconstruction) ]
                                |
                                v
                [ CandidateInferencePipelineV080 (CBE-0.8.0) ]
                                |
                +---------------+---------------+
                |                               |
                v                               v
        [ Branch C Forecast ]           [ Branch E Forecast ]
                |                               |
                +---------------+---------------+
                                |
                                v
        [ Append-Only Event Log (SHA-256 Hash Chain) ]
```

---

## 2. ENGINEERING ADVANTAGES & ISOLATION GUARANTEES

1. **Zero Additional Exchange API Polling:**
   The collector fetches a single response every 5 minutes. The 300-candle buffer is populated upon cold start and updated by appending 1 bar per cycle.
2. **Zero Database Locking / Polling:**
   All feature generation executes in memory without SQL or disk database locks.
3. **Fail-Closed Isolation:**
   If the shadow observer process crashes or encounters an error, the production CBE-0.7.0 worker is completely unaffected.
4. **Append-Only Serialization:**
   Predictions and mature outcomes are flushed to independent append-only files (`data/shadow/`) with low I/O footprint.
