# SPRINT 09.9: TIMESTAMP TRUST MODEL & CLOCK-SKEW SPECIFICATION

**DOCUMENT ID:** CBE-TRUST-09-9-01  
**DATE:** 2026-10-09  
**PURPOSE:** Establish the timing invariants and trust boundaries for prospective observation of CBE-0.8.0.

---

## 1. THREE-TIER TIMING CONTRACT

Every prospective observation event records three distinct UTC timestamps plus a hardware monotonic clock reference:

```
[Candle Close on Exchange] ---> [Local Network Receipt] ---> [Durable Persistence Commit]
     (T_exchange_close)               (T_local_receipt)             (T_durable_commit)
```

1. **`T_exchange_close` (`exchange_close_time_utc`)**:
   - The exchange-defined close boundary of the 5-minute candle (e.g. `2026-10-09T14:00:00Z`).
   - Sourced directly from Binance kline index 6 (`close_time_ms`).
   - Represents the causal boundary: **no data beyond this point may enter feature calculation**.

2. **`T_local_receipt` (`local_receipt_time_utc`)**:
   - The local UTC wall-clock time at which the complete closed candle bytes were received by the local socket/HTTP adapter.
   - Sourced from system UTC clock upon message receipt.
   - Must satisfy: `T_local_receipt >= T_exchange_close`.

3. **`T_durable_commit` (`durable_commit_time_utc`)**:
   - The timestamp at which the prediction payload and feature state have been fsynced to the immutable store.
   - Sourced immediately after disk commit.
   - Must satisfy: `T_durable_commit >= T_local_receipt`.

4. **`local_monotonic_ns`**:
   - Process-relative integer nanoseconds from `time.monotonic_ns()`.
   - **Crucial Invariant**: Monotonic clocks guarantee forward ordering within a single process run and are immune to NTP wall-clock slewing or daylight savings jumps. However, monotonic clocks **cannot independently establish UTC wall-clock time**.

---

## 2. CLOCK-SKEW BUDGET & AUDITING

- **Maximum Allowable Clock Skew**: `±1,000.0 ms` (1.0 second).
- **Audit Procedure**:
  - The capture process measures network transit latency: `delta = T_local_receipt - T_exchange_close`.
  - Under normal conditions, `50 ms <= delta <= 3,000 ms` (accounting for polling frequency).
  - If `delta < 0` (local clock behind exchange) by more than 1,000 ms, or if local system clock jumps backwards, the state machine transitions to `CLOCK_UNTRUSTED`.
- **Fail-Closed Policy**: When in `CLOCK_UNTRUSTED`, prospective predictions are tagged `CLOCK_SKEW_EXCEEDED` and excluded from prospective scoring.

---

## 3. EXTERNAL AUDITABILITY (RFC 3161)

- **Local Hash Chain Limitations**: A local SHA-256 append-only hash chain proves *tamper-evidence* (that records were not altered after creation), but **cannot independently prove real-world time of creation** against an adversarial clock.
- **RFC 3161 Trusted Timestamp Authority (TSA)**:
  - An optional external audit mechanism where a SHA-256 digest of the prediction batch is submitted to an independent RFC 3161 TSA (e.g. DigiCert, FreeTSA) to obtain a cryptographically signed timestamp token.
  - **Verdict**: Recommended for milestone commitments (e.g. daily batch hashes), but not mandatory on every 5-minute individual prediction.
