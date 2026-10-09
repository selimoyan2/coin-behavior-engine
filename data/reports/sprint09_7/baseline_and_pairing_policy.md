# SPRINT 09.7: BASELINE AND PAIRING POLICY

**Policy Identifier:** CBE-0.8.0-BASELINE-PAIRING-V1  
**Scope:** Rules for paired prospective comparisons  

---

## 1. PREDECLARED BASELINES

Every prospective forecast from Candidate Branch C and Branch E will be evaluated against three causal baselines:

1. **BASELINE_1 (Persistence Forecast):**
   - Forward volatility forecast equals the most recently observed 24h realized volatility:
     $\hat{y}_{t+h} = \text{volatility\_realized\_24h}_t \times \sqrt{288}$.
2. **BASELINE_2 (Rolling Historical Mean):**
   - 30-day (8,640 bars) trailing mean of realized volatility.
3. **BASELINE_3 (CBE-0.7.0 Frozen Production Model):**
   - Production model forecast where available and comparable.
   - *Limitation Note:* CBE-0.7.0 suffered from market-state collapse (DELEVERAGING_STRESS) and fixed lognormal sigma heuristics. It is tracked for production comparison, not as a valid statistical ML benchmark.

---

## 2. STRICT PAIRING CRITERIA

Pairing comparisons between candidate branches and baselines are valid **if and only if** all five dimensions are identical:
1. **Same Symbol:** BTCUSDT spot.
2. **Same Forecast Origin:** Identical 5-minute bar close timestamp.
3. **Same Horizon:** 1h, 4h, or 24h evaluated independently.
4. **Same Target Units:** `Daily-scaled standard deviation (sigma_5m * sqrt(288))`.
5. **Same Outcome Window:** Realized volatility computed over the exact forward window $[t, t + h]$.

Unpaired cross-sample comparisons (e.g., comparing candidate performance on high-volatility days against baseline performance across all days) are strictly prohibited.
