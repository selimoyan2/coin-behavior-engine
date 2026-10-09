# SPRINT 09.7: EXPERIMENT DURATION AND STOPPING RULES

**Protocol Rule:** STOP-CBE-0.8.0-PROSPECTIVE  

---

## 1. PREDECLARED OBSERVATION WINDOW

- **Initial Observation Window:** 30 calendar days (approximately 8,640 consecutive 5-minute bars).
- **Milestone Status:** The 30-day mark is an **operational checkpoint**, NOT an automatic declaration of predictive advantage or production readiness.
- **Window Extension:** If the 30-day window encounters unusually tranquil market conditions (e.g., fewer than 500 mature bars in `HIGH_VOLATILITY`), the observation period may be extended to 60 or 90 days.

---

## 2. MANDATORY PREDECLARED SAFETY STOPS

Observation must be immediately suspended and flagged for investigation upon any of the following safety stops:
1. **Cryptographic Chain Breach:** Hash mismatch or sequence gap detected during append-only event verification.
2. **Data Leakage / Forward Contamination:** Any record where `record_creation_timestamp > target_maturity_timestamp`.
3. **Target Unit Inconsistency:** Realized outcome calculation deviating from daily-scaled standard deviation.
4. **Resource Exhaustion:** Memory usage exceeding 200MB or CPU burst latency exceeding 1,000ms.
5. **Feed Data Corruption:** More than 5 consecutive missing bars from the spot feed.
