# CBE — HISTORICAL DATA EXPANSION & OPERATOR IMPORT WORKFLOW
## Offline Validation, Dry-Run Previews, Partition Integrity & Atomic Publication

**Document Version:** 1.0.0  
**Status:** DELIVERED & ACTIVE  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Execution Mode:** STRICTLY OFFLINE HISTORICAL RESEARCH  

---

## 1. Executive Protocol & Safety Principles

The Coin Behavior Engine (CBE) enforces a strict **Zero-Live-Ingestion** contract:
1. **Zero External API/WebSocket Egress:** The engine will never automatically fetch, poll, or scrape data from Binance or any other exchange.
2. **Authorized Staging Directory Ingestion:** Data is introduced strictly via operator-supplied files placed in an authorized local staging directory.
3. **No Synthetic Market Fabrication:** If market data is not present for a requested period (e.g. October 2026), the engine issues an explicit `no_data` alert and will never synthesize fictitious price action.
4. **Non-Destructive Atomic Publishing:** Ingestion writes to temporary staging partitions first, computes checksums and cross-interval checks, and only then atomically moves into the canonical archive.
5. **Conflict Rejection:** Any candidate file with timestamps overlapping existing data with conflicting OHLCV values is immediately aborted.

---

## 2. Ingestion CLI Workflow Commands

The engine provides a unified CLI via the module:
```bash
python -m coin_behavior_engine.data_import
```

### Step 1: Pre-Import Validation & Schema Audit (`validate`)
Verifies schema compliance, numeric finiteness, OHLC geometric validity, and monotonicity.
```bash
python -m coin_behavior_engine.data_import \
  --mode validate \
  --source /path/to/candidate/BTCUSDT-5m-2026-10.parquet \
  --symbol BTCUSDT \
  --interval 5m
```

### Step 2: Dry-Run Publication Impact Preview (`preview`)
Analyzes target partition existence, completeness ratios, detected gaps, and preview of resulting manifest hash **without altering the canonical archive**:
```bash
python -m coin_behavior_engine.data_import \
  --mode preview \
  --source /path/to/candidate/BTCUSDT-5m-2026-10.parquet \
  --symbol BTCUSDT \
  --interval 5m
```

### Step 3: Atomic Staged Ingestion & Publication (`import`)
Executes validation, conflict checks, atomic staging write, canonical manifest rebuild, cache invalidation, and immutable receipt emission:
```bash
python -m coin_behavior_engine.data_import \
  --mode import \
  --source /path/to/candidate/BTCUSDT-5m-2026-10.parquet \
  --symbol BTCUSDT \
  --interval 5m \
  --allow-partial
```

### Step 4: Post-Publication Integrity Verification (`verify`)
Re-verifies the newly published partition directly from the canonical store:
```bash
python -m coin_behavior_engine.data_import \
  --mode verify \
  --symbol BTCUSDT \
  --interval 5m \
  --month 2026-10
```

### Step 5: Audit Trail Inspection (`list-imports`, `inspect-receipt`)
Lists historical import receipts or inspects a specific cryptographically signed receipt:
```bash
python -m coin_behavior_engine.data_import --list-imports
python -m coin_behavior_engine.data_import --inspect-receipt IMP-20261024-XXXX
```

---

## 3. Handling Partial Current-Month Datasets (e.g. October 1–15, 2026)

When importing an active or partial calendar month:
- Use `--allow-partial` flag (enabled by default).
- The engine marks partition status as `PARTIAL` rather than `COMPLETE`.
- Completeness percentage is calculated as:
  $$\text{Completeness} = \frac{\text{Actual Candles}}{\text{Total Month Hours} \times 12} \times 100\%$$
- Research readiness engine marks analytical modules accordingly (preventing forward outcome leakage in historical analogs).
- UI timeline enables navigation across available days (`01..15`) while disabling future unimported days.
