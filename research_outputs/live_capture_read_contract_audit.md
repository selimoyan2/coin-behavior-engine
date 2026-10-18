# CBE Sprint 11.16B.1 — Live Capture Publishing Architecture & Read Contract Audit

**Document Version:** 1.0.0-sprint11.16b.1  
**Audit Target:** Live Capture Container `zgit1s3n1acdtqtsxp0s44vj` & Volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data`  
**Execution Standard:** Strictly Empirical Code & Metadata Analysis (Zero Live State Mutation)  
**Evaluator:** Distributed Systems Architecture & Data Integrity Auditor  

---

## 1. Executive Summary & Core Findings

This audit inspects the publishing architecture of the CBE Live Capture service to establish a provably safe, contention-free read contract for the prospective shadow observer.

### Key Audit Findings
1. **SQLite / WAL Decoupling:** Live Capture uses SQLite (`index_BTCUSDT_5m.sqlite3` with `-wal` and `-shm` auxiliary files) purely as an internal sequence index. **The shadow observer does NOT and MUST NOT read or open SQLite/WAL files.**
2. **Atomic Snapshot Publishing:** Public market state is decoupled and exported exclusively via `AtomicSnapshotIO` to `live_market_state.json`.
3. **Zero Torn-Read Guarantee:** Writing uses temporary file writes with `os.fsync()` followed by atomic POSIX replacement (`os.replace()`). Readers reading `live_market_state.json` can never observe partially written, truncated, or torn records.
4. **VFS Read-Only Enclosure:** The shadow container mounts the volume strictly with `:ro` (`MS_RDONLY`). The Linux kernel will immediately reject any write attempt with `EROFS`, guaranteeing that Live Capture's active files can never be modified or corrupted.
5. **Zero SQLite Lock Contention:** Because the shadow container accesses only `live_market_state.json` and never accesses SQLite connection handles, zero SQLite lock contention or WAL checkpoint delays can occur.

---

## 2. Live Capture Architecture & Storage Layout

### 2.1 File System Topology
Within the volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data`:
```
/app/data/live_capture/
├── live_market_state.json                 # <-- EXCLUSIVE SHADOW INGESTION TARGET (Atomic JSON)
├── snapshots/
│   └── btcusdt_factual_latest.json       # Mirror snapshot for staging UI
├── raw_evidence/
│   └── raw_candles_BTCUSDT_5m.jsonl      # Append-only raw candle journal (SHA-256 hashed)
├── recovery/
│   └── gap_recovery_journal.jsonl        # Durable gap recovery logs
├── index_BTCUSDT_5m.sqlite3               # INTERNAL ONLY: SQLite sequence index
├── index_BTCUSDT_5m.sqlite3-wal           # INTERNAL ONLY: SQLite Write-Ahead Log
└── index_BTCUSDT_5m.sqlite3-shm           # INTERNAL ONLY: SQLite Shared-Memory Index
```

### 2.2 Why Reading SQLite / WAL Directly is Prohibited
Direct concurrent access to `index_BTCUSDT_5m.sqlite3` by multiple containers introduces critical operational failure modes:
1. **Lock Contention:** SQLite in WAL mode permits concurrent readers, but read transactions hold shared memory locks (`-shm`) that can block the writer during WAL checkpointing (`PRAGMA wal_checkpoint(TRUNCATE)`), causing the real-time capture WebSocket to lag.
2. **Read-Only Mount Failure:** Opening an active WAL SQLite database on a strictly read-only filesystem (`:ro`) can fail with `sqlite3.OperationalError: attempt to write a readonly database` if SQLite attempts to recover WAL shared memory.
3. **Coupling to Internal Schema:** Direct SQL table queries couple external consumers to Live Capture's internal database migrations.

**Resolution:** The shadow observer read contract explicitly **forbids opening SQLite files** and interacts exclusively with the published JSON snapshot.

---

## 3. Atomic Publication Mechanism (`AtomicSnapshotIO`)

Inspecting `src/coin_behavior_engine/product/market_data_adapter.py`:

```python
class AtomicSnapshotIO:
    @staticmethod
    def atomic_write(target_path: Path, payload: Dict[str, Any]) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target_path.with_suffix(".tmp." + str(os.getpid()))
        try:
            content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            with open(temp_file, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Guaranteed flushed to physical disk blocks
            os.replace(temp_file, target_path)  # Atomic rename in Linux kernel VFS
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise e
```

### Invariants Guaranteed by `atomic_write`:
1. **Atomicity:** Under Linux ext4/xfs filesystems, `os.replace` (backed by the `rename(2)` syscall) is an atomic directory metadata swap. A reader opening `live_market_state.json` will either read the previous valid JSON document or the new valid JSON document—never an intermediate state.
2. **Durability:** Calling `f.flush()` and `os.fsync(f.fileno())` before renaming ensures that the payload is committed to persistent storage, preventing zero-byte or corrupt files upon power or container failure.

---

## 4. Shadow Observer Ingestion Contract (`safe_read`)

The shadow observer consumes market data strictly through `AtomicSnapshotIO.safe_read()`:

```python
@staticmethod
def safe_read(target_path: Path) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    if not target_path.exists():
        return False, None, "FILE_NOT_FOUND"
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False, None, "INVALID_ROOT_TYPE_NOT_DICT"
        return True, data, None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return False, None, f"CORRUPT_JSON: {e}"
    except OSError as e:
        return False, None, f"IO_ERROR: {e}"
```

### Ingestion Validation Pipeline
When reading `live_market_state.json`, the shadow observer applies 5 fail-closed validation gates:
1. **Schema Integrity:** Verifies `schema_version == "1.0.0"`, `symbol == "BTCUSDT"`, and `candle_interval == "5m"`.
2. **Candle Closure:** Strictly requires `is_closed == True`. If a partial unclosed candle is encountered, execution aborts and no trading decision is issued.
3. **Freshness & Stale Guard:**
   - Let $T_{\text{avail}}$ be the `snapshot_generation_timestamp_utc` or file `mtime`.
   - If $(T_{\text{now}} - T_{\text{avail}}) > 900.0\text{ s}$ (15 minutes), the market feed is marked `STALE`.
   - The observer immediately fails closed: emits `WAIT_USDT` (if in cash) or `POSITION_OPEN_DATA_STALE` (if holding BTC), preventing decisions on stale prices.
4. **Heartbeat Liveness:** Verifies `writer_heartbeat_utc` is within 180 seconds, confirming the capture process is actively polling Binance.
5. **Contiguity Verification:** Verifies `is_research_eligible == True` and `contiguous_bars_count >= 288` (24h continuous data).

---

## 5. Security & Isolation Invariants

| Security Dimension | Implementation | Verification Mechanism |
|---|---|---|
| **Filesystem Isolation** | `:ro` mount flag in Docker Compose | Kernel enforces `MS_RDONLY`. Writes fail with `EROFS`. |
| **Network Isolation** | `network_mode: "none"` | Container has zero `eth0` network interface. Outbound traffic impossible. |
| **User Privileges** | Non-root `UID 1000:1000` | Process cannot escalate privileges or alter host mount points. |
| **Process Separation** | Separate Docker container namespace | Zero shared IPC, PID, or memory spaces with Live Capture. |

---

## 6. Formal Invariant Statement
The prospective shadow observer reading `live_market_state.json` via `AtomicSnapshotIO.safe_read()` over a read-only volume mount operates with **zero risk of data corruption, zero lock contention with SQLite/WAL files, and guaranteed atomic consistency**.
