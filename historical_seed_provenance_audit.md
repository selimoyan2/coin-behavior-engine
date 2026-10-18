# Historical Seed Provenance & Continuity Audit — Sprint 11.16B.4

**Sprint:** CBE — SPRINT 11.16B.4  
**Date:** 2026-10-19  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `a04abc9b99c891a6a6099bc9e99394405ba967fb`  
**Mode:** Autonomous Offline Research & Deterministic Verification Only  

---

## 1. Vulnerability Assessment: Prior Seed Ingestion Defects

In Sprint 11.16B.3, the initial `ingest_seed_candles()` implementation relied solely on a shallow boolean check:
```python
if not provenance.is_authorized:
    return False, "SEED_NOT_AUTHORIZED"
```
Independent GitHub source inspection flagged several critical risks:
1. **Unchecked Data Tampering:** The seed candles could be modified, fabricated, or truncated without triggering rejection, as long as `is_authorized = True`.
2. **Acceptance of Placeholder/Dummy Hashes:** Test fixtures and seed payloads used `"dummy"` as `dataset_sha256`, completely bypassing cryptographic verification.
3. **Unverified Timestamp Continuity:** Non-contiguous seed partitions (containing missing bars or time inversions) were not exhaustively verified against interval invariants.
4. **Boundary Timestamp Inconsistency:** Boundary timestamps (`start_timestamp_utc`, `end_timestamp_utc`) were not verified against the actual first and last candles in the payload.

---

## 2. Upgraded Cryptographic Verification Specification

Under Sprint 11.16B.4 Phase 2, `HistoricalSeedProvenance` and `PersistentRollingBuffer.ingest_seed_candles()` have been upgraded with mandatory end-to-end cryptographic verification:

### 2.1 Canonical Serialization Format
The SHA-256 digest is computed over a strictly deterministic, newline-delimited ASCII representation of each candle:
$$\text{Line}_i = \text{symbol},\text{interval},\text{timestamp\_open\_utc},\text{timestamp\_close\_utc},\text{open\_p:.8f},\text{high\_p:.8f},\text{low\_p:.8f},\text{close\_p:.8f},\text{volume\_base:.8f},\text{volume\_usdt:.8f}$$
$$\text{CanonicalDigest} = \text{SHA-256}\left(\sum_{i=0}^{N-1} \text{Line}_i\right)$$

### 2.2 Rejection of Dummy & Malformed Hashes
Any seed provenance whose `dataset_sha256` is empty, `"dummy"`, `"placeholder"`, or not a 64-character hexadecimal string is rejected immediately with:
`REJECTED_DUMMY_OR_INVALID_HASH`

### 2.3 Boundary & Continuity Enforcement
1. **Start Boundary:** `candles[0].timestamp_open_utc == provenance.start_timestamp_utc`.
2. **End Boundary:** `candles[-1].timestamp_open_utc == provenance.end_timestamp_utc`.
3. **Candle Count:** `len(candles) == provenance.candle_count` and `len(candles) >= 864`.
4. **Interval Monotonicity & Spacing:** For all $i \in [1, N-1]$, $(T_{\text{open}, i} - T_{\text{open}, i-1}) \equiv 300\text{ seconds}$. Any step $\ne 300\text{s}$ triggers `NON_CONTIGUOUS_TIMESTAMPS`.
5. **Manifest Matching:** If an expected manifest digest is provided, the computed digest must match with 100% bitwise equality.

---

## 3. Robust Gap Handling & Post-Gap Recovery

### 3.1 Prohibition of Disjoint Feature Calculations
Moving averages ($\text{SMA}_{288}$, $\text{SMA}_{576}$, $\text{SMA}_{864}$) and volatility measures ($\text{ATR}_{14}$) assume uniform, uninterrupted 5-minute sampling. Evaluating these indicators across a time gap yields corrupted, mathematically unfaithful signals.

### 3.2 Implemented Gap State Machine
When a snapshot arrives with $\Delta t > 300\text{s}$:
1. **Immediate Warmup Invalidation:** `self._gap_detected = True` and `self.is_warmup_ready = False`.
2. **Buffer Purging:** The existing buffer is cleared (`self.clear()`) because pre-gap bars cannot be causally stitched to post-gap bars.
3. **Execution Denial:** The bridge emits `BridgeStatus.GAP_DETECTED` with `execution_eligible = False`.
4. **Recovery Requirement:** The bridge enters an explicit recovery state requiring 864 fresh contiguous 5-minute bars or an authenticated recovery seed batch before `is_warmup_ready` can be re-established.
5. **Position Preservation:** In-flight BTC positions remain held without fictional fills; no panic liquidation or lookahead closing occurs.

---

## 4. Verification & Negative Regression Testing

All seed integrity rules were validated with dedicated negative unit tests in `tests/test_sprint11_16b_4_data_bridge_parity.py`:
- `test_04_invalidate_warmup_on_detected_gap`: Verifies buffer purging and warmup invalidation on a 600s gap.
- `test_07_reject_seed_with_modified_ohlcv_data_sha256_mismatch`: Modifies a single close price by +$1.00; confirms rejection with `HASH_MISMATCH` and 0 candles loaded.
- `test_08_reject_seed_with_non_contiguous_timestamps`: Introduces a 10-minute gap inside the seed; confirms rejection with `NON_CONTIGUOUS_TIMESTAMPS`.
- `test_09_reject_seed_with_fewer_than_864_candles`: Provides 500 candles; confirms rejection with `INSUFFICIENT_CANDLES`.
