# FORECAST EVENT TIME ORDERING & PROVENANCE AUDIT

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. THE 6-TIER TIMESTAMP CONTRACT

Every prediction and outcome event in the CBE-0.8.0 shadow architecture adheres to a strict six-tier chronological timeline:

```
[1. Candle Close] ---> [2. Local Receipt] ---> [3. Computation] ---> [4. Durable Commit] --------> [5. Horizon Maturity] ---> [6. Outcome Evaluation]
   T_close                T_receipt               T_compute              T_commit                     T_mat                      T_eval
```

1. **Exchange Candle Close Time ($T_{	ext{close}}$):** Exact millisecond when the 5-minute candle completes on Binance (`timestamp_close` / `datetime_close`).
2. **Local Receipt Time ($T_{	ext{receipt}}$):** UTC timestamp when the finalized candle payload arrives at the collector (`receipt_timestamp_utc`).
3. **Forecast Computation Time ($T_{	ext{compute}}$):** Timestamp when features and Ridge dual-branch inferences are evaluated.
4. **Durable Commit Time ($T_{	ext{commit}}$):** Timestamp when the `ShadowPredictionEvent` is fsynced to `shadow_predictions.jsonl`.
5. **Target Maturity Time ($T_{	ext{mat}}$):** Explicit timestamp when the forward evaluation window closes ($T_{	ext{close}} + 1	ext{h}/4	ext{h}/24	ext{h}$).
6. **Outcome Observation Time ($T_{	ext{eval}}$):** Timestamp when the subsequent candles are verified and realized volatility is computed.

---

## 2. CAUSAL ORDERING INVARIANTS

- **Invariant 1 (No Premature Receipt):** $T_{	ext{receipt}} \ge T_{	ext{close}} - 1000	ext{ ms}$. If receipt occurs prior to candle close, `CLOCK_UNTRUSTED` is triggered.
- **Invariant 2 (Durable Commitment Precedes Outcome):** $T_{	ext{commit}} < T_{	ext{mat}}$. A forecast committed at origin time $T$ matures at $T + 1	ext{h}, 4	ext{h}, 24	ext{h}$, proving zero lookahead.
- **Invariant 3 (Outcome Evaluation Follows Maturity):** $T_{	ext{eval}} \ge T_{	ext{mat}}$. Outcomes cannot be evaluated until the final future candle has fully closed.
- **Invariant 4 (Live Timestamp Reality):** Because live Binance WebSocket/REST connections have not been authorized, live network receipt timestamps are honestly marked **`NOT_VERIFIED`**.
