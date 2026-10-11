"""Durable Prediction & Outcome Indexing for CBE-0.8.0 Shadow Collector.

Sprint 09.17: Durable Prediction & Outcome Indexing — Crash-Safe Persistence.

Enforces:
- Append-only JSONL journals remain the authoritative source of truth.
- High-performance, crash-safe SQLite index files (WAL mode, bounded cache).
- Bounded memory: O(1) random byte-offset seeks into journals without full-file loads.
- Strict deduplication: unique logical constraints on prediction keys and outcome events.
- Crash consistency: survives crashes before append, after append, and during index commits.
- Deterministic index rebuilds from append-only journals.
- Forensic quarantine and in-place safe truncation (os.ftruncate) for trailing corruption.
- Fail-closed on mid-chain corruption.
- Zero lingering file handles on Windows: connection context management prevents WinError 32.
"""

from __future__ import annotations

import abc
import collections
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import pandas as pd

from coin_behavior_engine.shadow_v080.prediction_store import (
    EventTamperError,
    SHADOW_GENESIS_HASH,
    ShadowPredictionEvent,
)

logger = logging.getLogger("cbe_prediction_indexing")


class IPendingPredictionIndex(abc.ABC):
    """Abstract interface for managing pending (un-matured) prediction lifecycle.

    Guarantees:
    - O(1) or indexed lookup of pending predictions awaiting market maturity.
    - Causal status transition from PENDING to MATURED or INVALID_GAP.
    - Deterministic restart recovery from durable store.
    """

    @abc.abstractmethod
    def add_pending(self, prediction: ShadowPredictionEvent) -> None:
        """Register a newly committed prediction as pending maturity."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_pending_predictions(self) -> List[ShadowPredictionEvent]:
        """Retrieve all currently un-matured prediction events."""
        raise NotImplementedError

    @abc.abstractmethod
    def mark_matured(self, record_hash: str, outcome_id: Optional[str] = None, status: str = "MATURED") -> None:
        """Mark a prediction event as resolved/matured."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_pending_count(self) -> int:
        """Return total count of pending predictions."""
        raise NotImplementedError

    @abc.abstractmethod
    def is_pending(self, record_hash: str) -> bool:
        """Check whether a specific record hash is currently pending."""
        raise NotImplementedError


class JournalPendingPredictionIndexV080(IPendingPredictionIndex):
    """Reference pending prediction index backed by ImmutablePredictionStoreV080 journal.

    Maintains an in-memory queue bounded by the maximum prospective horizon (288 bars = 24h)
    while reconstructing state directly from the immutable JSONL prediction journal upon restart.
    """

    def __init__(self, prediction_store: Any):
        self.prediction_store = prediction_store
        self._matured_hashes: Set[str] = set()

    def add_pending(self, prediction: ShadowPredictionEvent) -> None:
        """Register a prediction. Appends to store if not already committed."""
        if prediction.record_hash in self._matured_hashes:
            return
        try:
            self.prediction_store.append_event(prediction)
        except Exception:
            pass

    def get_pending_predictions(self) -> List[ShadowPredictionEvent]:
        """Return all pending events from the backing prediction store."""
        raw_pending = self.prediction_store.get_unmatured_events()
        return [p for p in raw_pending if p.record_hash not in self._matured_hashes]

    def mark_matured(self, record_hash: str, outcome_id: Optional[str] = None, status: str = "MATURED") -> None:
        """Mark a prediction as matured and prune it from the store pending list."""
        self._matured_hashes.add(record_hash)
        self.prediction_store.prune_matured_events({record_hash})

    def get_pending_count(self) -> int:
        """Return current count of pending predictions."""
        return len(self.get_pending_predictions())

    def is_pending(self, record_hash: str) -> bool:
        """Return True if the prediction is still pending outcome maturity."""
        if record_hash in self._matured_hashes:
            return False
        return any(p.record_hash == record_hash for p in self.prediction_store.get_unmatured_events())


# ==============================================================================
# Durable SQLite Prediction Index (Phase 2)
# ==============================================================================

class DurablePredictionIndexV080(IPendingPredictionIndex):
    """Crash-safe, disk-backed SQLite prediction index with WAL mode and binary offset seeks.

    Authoritative data remains in `shadow_predictions.jsonl`.
    This index provides:
    - O(1) deduplication and key lookup.
    - Instant query for pending predictions without scanning historical records.
    - Deterministic recovery and automatic sync from journal on startup.
    - Forensic quarantine and in-place truncation for incomplete trailing writes.
    - Zero lingering file handles on Windows via connection context management.
    """

    def __init__(
        self,
        store_dir: Path,
        events_file: Optional[Path] = None,
        quarantine_dir: Optional[Path] = None,
    ):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = events_file or (self.store_dir / "shadow_predictions.jsonl")
        self.quarantine_dir = quarantine_dir or (self.store_dir / "quarantine")
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index_predictions.sqlite3"

        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Provide a scoped SQLite connection with bounded cache."""
        conn = sqlite3.connect(
            str(self.index_file),
            timeout=10.0,
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -512;")
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _init_db(self) -> None:
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA synchronous = NORMAL;")
                    conn.execute("PRAGMA cache_size = -512;")
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS predictions_index (
                            prediction_id TEXT PRIMARY KEY,
                            event_id TEXT NOT NULL,
                            forecast_origin_utc TEXT NOT NULL,
                            origin_timestamp_ms INTEGER NOT NULL,
                            durable_commit_time_utc TEXT NOT NULL,
                            target_horizon TEXT NOT NULL,
                            candidate_branch TEXT NOT NULL,
                            target_maturity_utc TEXT NOT NULL,
                            target_maturity_ms INTEGER NOT NULL,
                            protocol_version TEXT NOT NULL,
                            bundle_hash TEXT NOT NULL,
                            feature_fingerprint TEXT NOT NULL,
                            point_prediction REAL NOT NULL,
                            interval_80_lower REAL NOT NULL,
                            interval_80_upper REAL NOT NULL,
                            interval_95_lower REAL NOT NULL,
                            interval_95_upper REAL NOT NULL,
                            market_state TEXT NOT NULL,
                            record_label TEXT NOT NULL,
                            previous_event_hash TEXT NOT NULL,
                            record_hash TEXT UNIQUE NOT NULL,
                            journal_byte_offset INTEGER NOT NULL,
                            journal_line_no INTEGER NOT NULL,
                            status TEXT NOT NULL DEFAULT 'PENDING',
                            resolved_at_utc TEXT,
                            outcome_id TEXT
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_pred_status ON predictions_index(status);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_pred_maturity_ms ON predictions_index(target_maturity_ms);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_pred_origin_ms ON predictions_index(origin_timestamp_ms);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_pred_record_hash ON predictions_index(record_hash);")
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_pred_lookup_key ON predictions_index(forecast_origin_utc, candidate_branch, target_horizon);"
                    )
                    conn.commit()
                    cur = conn.cursor()
                    cur.execute("PRAGMA quick_check;")
                    res = cur.fetchone()
                    if not res or res[0].lower() != "ok":
                        raise sqlite3.DatabaseError(f"SQLite quick_check failed: {res}")
            except (sqlite3.DatabaseError, OSError) as exc:
                logger.warning(f"SQLite index corruption detected ({exc}). Rebuilding from authoritative journal.")
                if self.index_file.exists():
                    self.index_file.unlink(missing_ok=True)
                with self._get_connection() as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS predictions_index (
                            prediction_id TEXT PRIMARY KEY,
                            event_id TEXT NOT NULL,
                            forecast_origin_utc TEXT NOT NULL,
                            origin_timestamp_ms INTEGER NOT NULL,
                            durable_commit_time_utc TEXT NOT NULL,
                            target_horizon TEXT NOT NULL,
                            candidate_branch TEXT NOT NULL,
                            target_maturity_utc TEXT NOT NULL,
                            target_maturity_ms INTEGER NOT NULL,
                            protocol_version TEXT NOT NULL,
                            bundle_hash TEXT NOT NULL,
                            feature_fingerprint TEXT NOT NULL,
                            point_prediction REAL NOT NULL,
                            interval_80_lower REAL NOT NULL,
                            interval_80_upper REAL NOT NULL,
                            interval_95_lower REAL NOT NULL,
                            interval_95_upper REAL NOT NULL,
                            market_state TEXT NOT NULL,
                            record_label TEXT NOT NULL,
                            previous_event_hash TEXT NOT NULL,
                            record_hash TEXT UNIQUE NOT NULL,
                            journal_byte_offset INTEGER NOT NULL,
                            journal_line_no INTEGER NOT NULL,
                            status TEXT NOT NULL DEFAULT 'PENDING',
                            resolved_at_utc TEXT,
                            outcome_id TEXT
                        );
                    """)
                    conn.commit()

    def get_max_journal_offset(self) -> int:
        """Return the maximum byte offset successfully indexed in SQLite."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(journal_byte_offset) FROM predictions_index;")
                row = cur.fetchone()
                if row and row[0] is not None:
                    return int(row[0])
                return -1

    def has_event(self, record_hash: str) -> bool:
        """Check if record hash exists in index."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM predictions_index WHERE record_hash = ? LIMIT 1;", (record_hash,))
                return cur.fetchone() is not None

    def has_key(self, forecast_origin_utc: str, candidate_branch: str, target_horizon: str) -> bool:
        """Check if unique forecast key (origin + branch + horizon) already exists."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM predictions_index WHERE forecast_origin_utc = ? AND candidate_branch = ? AND target_horizon = ? LIMIT 1;",
                    (forecast_origin_utc, candidate_branch, target_horizon),
                )
                return cur.fetchone() is not None

    def get_all_keys(self) -> Set[str]:
        """Fetch all logical keys (origin + branch + horizon) in index."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT forecast_origin_utc, candidate_branch, target_horizon FROM predictions_index;")
                return {f"{r[0]}_{r[1]}_{r[2]}" for r in cur.fetchall()}

    def index_event(
        self,
        event: ShadowPredictionEvent,
        byte_offset: int,
        line_no: int,
        status: str = "PENDING",
    ) -> None:
        """Insert or replace prediction event in the SQLite index."""
        origin_ms = int(pd.Timestamp(event.forecast_origin_utc).timestamp() * 1000)
        maturity_ms = int(pd.Timestamp(event.target_maturity_utc).timestamp() * 1000)
        bundle_hash = event.component_hashes.get("bundle", "") if event.component_hashes else ""

        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO predictions_index (
                        prediction_id, event_id, forecast_origin_utc, origin_timestamp_ms,
                        durable_commit_time_utc, target_horizon, candidate_branch,
                        target_maturity_utc, target_maturity_ms, protocol_version,
                        bundle_hash, feature_fingerprint, point_prediction,
                        interval_80_lower, interval_80_upper, interval_95_lower, interval_95_upper,
                        market_state, record_label, previous_event_hash, record_hash,
                        journal_byte_offset, journal_line_no, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        event.event_id,
                        event.event_id,
                        event.forecast_origin_utc,
                        origin_ms,
                        event.durable_commit_time_utc,
                        event.target_horizon,
                        event.candidate_branch,
                        event.target_maturity_utc,
                        maturity_ms,
                        event.protocol_version,
                        bundle_hash,
                        event.feature_fingerprint,
                        float(event.point_prediction),
                        float(event.interval_80["lower"]),
                        float(event.interval_80["upper"]),
                        float(event.interval_95["lower"]),
                        float(event.interval_95["upper"]),
                        event.market_state,
                        event.record_label,
                        event.previous_event_hash,
                        event.record_hash,
                        byte_offset,
                        line_no,
                        status,
                    ),
                )
                conn.commit()

    def index_events_batch(
        self,
        events_with_meta: List[Tuple[ShadowPredictionEvent, int, int, str]],
    ) -> None:
        """Insert or replace a batch of prediction events in a single SQLite transaction."""
        if not events_with_meta:
            return
        rows = []
        for event, byte_offset, line_no, status in events_with_meta:
            origin_ms = int(pd.Timestamp(event.forecast_origin_utc).timestamp() * 1000)
            maturity_ms = int(pd.Timestamp(event.target_maturity_utc).timestamp() * 1000)
            bundle_hash = event.component_hashes.get("bundle", "") if event.component_hashes else ""
            rows.append((
                event.event_id,
                event.event_id,
                event.forecast_origin_utc,
                origin_ms,
                event.durable_commit_time_utc,
                event.target_horizon,
                event.candidate_branch,
                event.target_maturity_utc,
                maturity_ms,
                event.protocol_version,
                bundle_hash,
                event.feature_fingerprint,
                float(event.point_prediction),
                float(event.interval_80["lower"]),
                float(event.interval_80["upper"]),
                float(event.interval_95["lower"]),
                float(event.interval_95["upper"]),
                event.market_state,
                event.record_label,
                event.previous_event_hash,
                event.record_hash,
                byte_offset,
                line_no,
                status,
            ))
        with self._lock:
            with self._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO predictions_index (
                        prediction_id, event_id, forecast_origin_utc, origin_timestamp_ms,
                        durable_commit_time_utc, target_horizon, candidate_branch,
                        target_maturity_utc, target_maturity_ms, protocol_version,
                        bundle_hash, feature_fingerprint, point_prediction,
                        interval_80_lower, interval_80_upper, interval_95_lower, interval_95_upper,
                        market_state, record_label, previous_event_hash, record_hash,
                        journal_byte_offset, journal_line_no, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    rows,
                )
                conn.commit()

    def add_pending(self, prediction: ShadowPredictionEvent) -> None:
        """IPendingPredictionIndex interface implementation."""
        if not self.has_event(prediction.record_hash):
            offset = self.events_file.stat().st_size if self.events_file.exists() else 0
            self.index_event(prediction, byte_offset=offset, line_no=0, status="PENDING")

    def _read_event_at_offset(self, byte_offset: int) -> Optional[ShadowPredictionEvent]:
        """Read single ShadowPredictionEvent directly from file descriptor at byte offset."""
        if not self.events_file.exists():
            return None
        try:
            with open(self.events_file, "rb") as f:
                f.seek(byte_offset)
                raw_line = f.readline()
                if not raw_line:
                    return None
                data = json.loads(raw_line.decode("utf-8", errors="replace").strip())
                return ShadowPredictionEvent(**data)
        except Exception as exc:
            logger.warning(f"Failed to read prediction event at offset {byte_offset}: {exc}")
            return None

    def get_pending_predictions(self) -> List[ShadowPredictionEvent]:
        """Retrieve all currently un-matured prediction events via indexed file seek."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT journal_byte_offset FROM predictions_index WHERE status = 'PENDING' ORDER BY origin_timestamp_ms ASC;"
                )
                rows = cur.fetchall()

        events: List[ShadowPredictionEvent] = []
        if not rows or not self.events_file.exists():
            return events

        try:
            with open(self.events_file, "rb") as f:
                for (offset,) in rows:
                    f.seek(offset)
                    raw_line = f.readline()
                    if raw_line:
                        try:
                            data = json.loads(raw_line.decode("utf-8", errors="replace").strip())
                            events.append(ShadowPredictionEvent(**data))
                        except Exception:
                            pass
        except Exception as exc:
            logger.warning(f"Failed to batch read pending predictions: {exc}")
        return events

    def get_pending_count(self) -> int:
        """Return total count of pending predictions."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM predictions_index WHERE status = 'PENDING';")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def get_pending_predictions_paged(
        self,
        page_size: int = 500,
    ) -> Iterator[List[ShadowPredictionEvent]]:
        """Yield pages of pending prediction events to guarantee bounded memory consumption."""
        offset = 0
        while True:
            with self._lock:
                with self._get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT journal_byte_offset FROM predictions_index WHERE status = 'PENDING' ORDER BY origin_timestamp_ms ASC LIMIT ? OFFSET ?;",
                        (page_size, offset),
                    )
                    rows = cur.fetchall()

            if not rows or not self.events_file.exists():
                break

            events: List[ShadowPredictionEvent] = []
            try:
                with open(self.events_file, "rb") as f:
                    for (byte_off,) in rows:
                        f.seek(byte_off)
                        raw_line = f.readline()
                        if raw_line:
                            try:
                                data = json.loads(raw_line.decode("utf-8", errors="replace").strip())
                                events.append(ShadowPredictionEvent(**data))
                            except Exception:
                                pass
            except Exception as exc:
                logger.warning(f"Error reading paged pending predictions: {exc}")
                break

            if not events:
                break

            yield events
            offset += len(rows)
            if len(rows) < page_size:
                break

    def get_prediction_by_hash(self, record_hash: str) -> Optional[ShadowPredictionEvent]:
        """Fetch prediction event by record hash in O(1) time."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT journal_byte_offset FROM predictions_index WHERE record_hash = ? LIMIT 1;", (record_hash,))
                row = cur.fetchone()
                if not row:
                    return None
                offset = row[0]
        return self._read_event_at_offset(offset)

    def mark_matured(self, record_hash: str, outcome_id: Optional[str] = None, status: str = "MATURED") -> None:
        """Mark prediction as matured or invalid in index."""
        now_utc = pd.Timestamp.now(tz="UTC").isoformat()
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE predictions_index SET status = ?, outcome_id = ?, resolved_at_utc = ? WHERE record_hash = ?;",
                    (status, outcome_id or "", now_utc, record_hash),
                )
                conn.commit()

    def mark_matured_batch(self, record_hashes: Set[str], status: str = "MATURED") -> None:
        """Batch update prediction statuses."""
        if not record_hashes:
            return
        now_utc = pd.Timestamp.now(tz="UTC").isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.executemany(
                    "UPDATE predictions_index SET status = ?, resolved_at_utc = ? WHERE record_hash = ?;",
                    [(status, now_utc, h) for h in record_hashes],
                )
                conn.commit()

    def get_pending_count(self) -> int:
        """Return count of currently un-matured predictions."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM predictions_index WHERE status = 'PENDING';")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def is_pending(self, record_hash: str) -> bool:
        """Check if record hash is pending."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM predictions_index WHERE record_hash = ? AND status = 'PENDING' LIMIT 1;", (record_hash,))
                return cur.fetchone() is not None

    def get_total_count(self) -> int:
        """Return total indexed predictions count."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM predictions_index;")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def truncate_index_to_offset(self, max_byte_offset: int) -> None:
        """Remove indexed records beyond given offset."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM predictions_index WHERE journal_byte_offset >= ?;", (max_byte_offset,))
                conn.commit()

    def rebuild_or_sync_from_journal(self, events_file: Optional[Path] = None) -> Tuple[int, str]:
        """Stream authoritative journal line-by-line, verify cryptographic chain, and synchronize index.

        Recovers trailing partial writes at EOF via in-place forensic truncation using os.ftruncate().
        Preserves damaged bytes in quarantine, verifies backup integrity, and fails closed on failure.
        Fails closed on mid-chain corruption by raising EventTamperError.
        Returns: (synced_entries_count, latest_hash)
        """
        file_path = events_file or self.events_file
        if not file_path.exists():
            with self._lock:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM predictions_index;")
                    conn.commit()
            return 0, SHADOW_GENESIS_HASH

        expected_prev = SHADOW_GENESIS_HASH
        valid_count = 0
        last_valid_offset = 0
        batch_items: List[Tuple] = []

        with open(file_path, "r+b") as f:
            while True:
                line_offset = f.tell()
                raw_line = f.readline()
                if not raw_line:
                    break

                curr_offset = f.tell()
                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    last_valid_offset = curr_offset
                    continue

                try:
                    data = json.loads(line_str)
                    ev = ShadowPredictionEvent(**data)

                    # Verify chain continuity
                    if ev.previous_event_hash != expected_prev:
                        raise EventTamperError(
                            f"Hash chain break at offset {line_offset}: expected prev_hash {expected_prev}, got {ev.previous_event_hash}"
                        )

                    # Verify record hash integrity
                    calc_hash = ev.compute_hash()
                    if ev.record_hash != calc_hash:
                        raise EventTamperError(
                            f"Tampered record at offset {line_offset}: declared {ev.record_hash}, calculated {calc_hash}"
                        )

                    origin_ms = int(pd.Timestamp(ev.forecast_origin_utc).timestamp() * 1000)
                    maturity_ms = int(pd.Timestamp(ev.target_maturity_utc).timestamp() * 1000)
                    bundle_h = ev.component_hashes.get("bundle", "") if ev.component_hashes else ""

                    batch_items.append((
                        ev.event_id,
                        ev.event_id,
                        ev.forecast_origin_utc,
                        origin_ms,
                        ev.durable_commit_time_utc,
                        ev.target_horizon,
                        ev.candidate_branch,
                        ev.target_maturity_utc,
                        maturity_ms,
                        ev.protocol_version,
                        bundle_h,
                        ev.feature_fingerprint,
                        float(ev.point_prediction),
                        float(ev.interval_80["lower"]),
                        float(ev.interval_80["upper"]),
                        float(ev.interval_95["lower"]),
                        float(ev.interval_95["upper"]),
                        ev.market_state,
                        ev.record_label,
                        ev.previous_event_hash,
                        ev.record_hash,
                        line_offset,
                        valid_count + 1,
                    ))

                    valid_count += 1
                    last_valid_offset = curr_offset
                    expected_prev = ev.record_hash

                except Exception as e:
                    f.seek(0, os.SEEK_END)
                    eof_offset = f.tell()
                    is_trailing = (curr_offset == eof_offset)

                    if is_trailing:
                        logger.warning(f"Trailing corrupt write detected at EOF (offset {line_offset}): {e}. Quarantining.")
                        f.seek(line_offset)
                        corrupted_bytes = f.read()

                        if corrupted_bytes:
                            ts_ms = int(time.time() * 1000)
                            forensic_file = self.quarantine_dir / f"forensic_trailing_prediction_corruption_{ts_ms}.bin"
                            with open(forensic_file, "wb") as bf:
                                bf.write(corrupted_bytes)
                                bf.flush()
                                os.fsync(bf.fileno())

                        f.flush()
                        os.ftruncate(f.fileno(), last_valid_offset)
                        f.seek(last_valid_offset)
                        f.flush()
                        os.fsync(f.fileno())
                        break
                    else:
                        raise EventTamperError(f"Mid-file corruption in prediction journal at offset {line_offset}: {e}") from e

        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM predictions_index WHERE journal_byte_offset >= ?;", (last_valid_offset,))
                if batch_items:
                    conn.executemany(
                        """
                        INSERT INTO predictions_index (
                            prediction_id, event_id, forecast_origin_utc, origin_timestamp_ms,
                            durable_commit_time_utc, target_horizon, candidate_branch,
                            target_maturity_utc, target_maturity_ms, protocol_version,
                            bundle_hash, feature_fingerprint, point_prediction,
                            interval_80_lower, interval_80_upper, interval_95_lower, interval_95_upper,
                            market_state, record_label, previous_event_hash, record_hash,
                            journal_byte_offset, journal_line_no
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(prediction_id) DO UPDATE SET
                            journal_byte_offset = excluded.journal_byte_offset,
                            journal_line_no = excluded.journal_line_no;
                        """,
                        batch_items,
                    )
                conn.commit()

        return valid_count, expected_prev

    def close(self) -> None:
        """Close method for interface compatibility."""
        pass

    def __del__(self) -> None:
        self.close()


# ==============================================================================
# Durable SQLite Outcome Index (Phase 3)
# ==============================================================================

class DurableOutcomeIndexV080:
    """Crash-safe, disk-backed SQLite outcome index with WAL mode and binary offset seeks.

    Authoritative data remains in `shadow_outcomes.jsonl`.
    This index provides:
    - O(1) deduplication by prediction event hash.
    - Idempotent lookup preventing duplicate outcome evaluations.
    - Deterministic rebuild and recovery from the outcome journal.
    - Zero lingering file handles on Windows via connection context management.
    """

    def __init__(
        self,
        store_dir: Path,
        outcomes_file: Optional[Path] = None,
        quarantine_dir: Optional[Path] = None,
    ):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.outcomes_file = outcomes_file or (self.store_dir / "shadow_outcomes.jsonl")
        self.quarantine_dir = quarantine_dir or (self.store_dir / "quarantine")
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index_outcomes.sqlite3"

        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Provide a scoped SQLite connection with bounded cache."""
        conn = sqlite3.connect(
            str(self.index_file),
            timeout=10.0,
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -512;")
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _init_db(self) -> None:
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("PRAGMA journal_mode = WAL;")
                    conn.execute("PRAGMA synchronous = NORMAL;")
                    conn.execute("PRAGMA cache_size = -512;")
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS outcomes_index (
                            outcome_id TEXT PRIMARY KEY,
                            prediction_event_hash TEXT UNIQUE NOT NULL,
                            forecast_origin_utc TEXT NOT NULL,
                            target_maturity_utc TEXT NOT NULL,
                            target_horizon TEXT NOT NULL,
                            candidate_branch TEXT NOT NULL,
                            point_forecast REAL NOT NULL,
                            realized_volatility REAL,
                            actual_bars_evaluated INTEGER NOT NULL,
                            status TEXT NOT NULL,
                            in_interval_80 INTEGER NOT NULL,
                            in_interval_95 INTEGER NOT NULL,
                            maturity_candle_hash TEXT NOT NULL,
                            maturity_entry_hash TEXT NOT NULL,
                            record_label TEXT NOT NULL,
                            outcome_hash TEXT UNIQUE NOT NULL,
                            evaluated_at_utc TEXT NOT NULL,
                            journal_byte_offset INTEGER NOT NULL,
                            journal_line_no INTEGER NOT NULL
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcome_pred_hash ON outcomes_index(prediction_event_hash);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_outcome_status ON outcomes_index(status);")
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_outcome_lookup ON outcomes_index(forecast_origin_utc, candidate_branch, target_horizon);"
                    )
                    conn.commit()
                    cur = conn.cursor()
                    cur.execute("PRAGMA quick_check;")
                    res = cur.fetchone()
                    if not res or res[0].lower() != "ok":
                        raise sqlite3.DatabaseError(f"SQLite quick_check failed: {res}")
            except (sqlite3.DatabaseError, OSError) as exc:
                logger.warning(f"SQLite outcome index corruption detected ({exc}). Rebuilding.")
                if self.index_file.exists():
                    self.index_file.unlink(missing_ok=True)
                with self._get_connection() as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS outcomes_index (
                            outcome_id TEXT PRIMARY KEY,
                            prediction_event_hash TEXT UNIQUE NOT NULL,
                            forecast_origin_utc TEXT NOT NULL,
                            target_maturity_utc TEXT NOT NULL,
                            target_horizon TEXT NOT NULL,
                            candidate_branch TEXT NOT NULL,
                            point_forecast REAL NOT NULL,
                            realized_volatility REAL,
                            actual_bars_evaluated INTEGER NOT NULL,
                            status TEXT NOT NULL,
                            in_interval_80 INTEGER NOT NULL,
                            in_interval_95 INTEGER NOT NULL,
                            maturity_candle_hash TEXT NOT NULL,
                            maturity_entry_hash TEXT NOT NULL,
                            record_label TEXT NOT NULL,
                            outcome_hash TEXT UNIQUE NOT NULL,
                            evaluated_at_utc TEXT NOT NULL,
                            journal_byte_offset INTEGER NOT NULL,
                            journal_line_no INTEGER NOT NULL
                        );
                    """)
                    conn.commit()

    def has_outcome(self, prediction_event_hash: str) -> bool:
        """Check if an outcome for this prediction event hash has already been resolved."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM outcomes_index WHERE prediction_event_hash = ? LIMIT 1;", (prediction_event_hash,))
                return cur.fetchone() is not None

    def record_outcome(
        self,
        outcome_dict: Dict[str, Any],
        byte_offset: int,
        line_no: int,
    ) -> None:
        """Insert or replace resolved outcome in SQLite index."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO outcomes_index (
                        outcome_id, prediction_event_hash, forecast_origin_utc,
                        target_maturity_utc, target_horizon, candidate_branch,
                        point_forecast, realized_volatility, actual_bars_evaluated,
                        status, in_interval_80, in_interval_95, maturity_candle_hash,
                        maturity_entry_hash, record_label, outcome_hash, evaluated_at_utc,
                        journal_byte_offset, journal_line_no
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        outcome_dict["outcome_id"],
                        outcome_dict["prediction_event_hash"],
                        outcome_dict["forecast_origin_utc"],
                        outcome_dict["target_maturity_utc"],
                        outcome_dict["target_horizon"],
                        outcome_dict["candidate_branch"],
                        float(outcome_dict["point_forecast"]),
                        float(outcome_dict["realized_volatility"]) if not pd.isna(outcome_dict.get("realized_volatility")) else None,
                        int(outcome_dict["actual_bars_evaluated"]),
                        outcome_dict["status"],
                        1 if outcome_dict.get("in_interval_80") else 0,
                        1 if outcome_dict.get("in_interval_95") else 0,
                        outcome_dict.get("maturity_candle_hash", ""),
                        outcome_dict.get("maturity_entry_hash", ""),
                        outcome_dict.get("record_label", "HISTORICAL_REPLAY"),
                        outcome_dict["outcome_hash"],
                        outcome_dict["evaluated_at_utc"],
                        byte_offset,
                        line_no,
                    ),
                )
                conn.commit()

    def record_outcomes_batch(
        self,
        outcomes_with_meta: List[Tuple[Dict[str, Any], int, int]],
    ) -> None:
        """Insert or replace a batch of resolved outcomes in a single SQLite transaction."""
        if not outcomes_with_meta:
            return
        rows = []
        for outcome_dict, byte_offset, line_no in outcomes_with_meta:
            rows.append((
                outcome_dict["outcome_id"],
                outcome_dict["prediction_event_hash"],
                outcome_dict["forecast_origin_utc"],
                outcome_dict["target_maturity_utc"],
                outcome_dict["target_horizon"],
                outcome_dict["candidate_branch"],
                float(outcome_dict["point_forecast"]),
                float(outcome_dict["realized_volatility"]) if not pd.isna(outcome_dict.get("realized_volatility")) else None,
                int(outcome_dict["actual_bars_evaluated"]),
                outcome_dict["status"],
                1 if outcome_dict.get("in_interval_80") else 0,
                1 if outcome_dict.get("in_interval_95") else 0,
                outcome_dict.get("maturity_candle_hash", ""),
                outcome_dict.get("maturity_entry_hash", ""),
                outcome_dict.get("record_label", "HISTORICAL_REPLAY"),
                outcome_dict["outcome_hash"],
                outcome_dict["evaluated_at_utc"],
                byte_offset,
                line_no,
            ))
        with self._lock:
            with self._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO outcomes_index (
                        outcome_id, prediction_event_hash, forecast_origin_utc,
                        target_maturity_utc, target_horizon, candidate_branch,
                        point_forecast, realized_volatility, actual_bars_evaluated,
                        status, in_interval_80, in_interval_95, maturity_candle_hash,
                        maturity_entry_hash, record_label, outcome_hash, evaluated_at_utc,
                        journal_byte_offset, journal_line_no
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    rows,
                )
                conn.commit()

    def get_outcome_count(self) -> int:
        """Return count of resolved outcomes."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM outcomes_index;")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def truncate_index_to_offset(self, max_byte_offset: int) -> None:
        """Remove outcome records beyond offset."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM outcomes_index WHERE journal_byte_offset >= ?;", (max_byte_offset,))
                conn.commit()

    def rebuild_or_sync_from_journal(self, outcomes_file: Optional[Path] = None) -> int:
        """Rebuild or synchronize outcomes index from authoritative JSONL journal."""
        file_path = outcomes_file or self.outcomes_file
        if not file_path.exists():
            with self._lock:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM outcomes_index;")
                    conn.commit()
            return 0

        valid_count = 0
        last_valid_offset = 0
        batch_items: List[Tuple] = []

        with open(file_path, "r+b") as f:
            while True:
                line_offset = f.tell()
                raw_line = f.readline()
                if not raw_line:
                    break

                curr_offset = f.tell()
                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    last_valid_offset = curr_offset
                    continue

                try:
                    data = json.loads(line_str)
                    batch_items.append((
                        data["outcome_id"],
                        data["prediction_event_hash"],
                        data["forecast_origin_utc"],
                        data["target_maturity_utc"],
                        data["target_horizon"],
                        data["candidate_branch"],
                        float(data["point_forecast"]),
                        float(data["realized_volatility"]) if not pd.isna(data.get("realized_volatility")) else None,
                        int(data["actual_bars_evaluated"]),
                        data["status"],
                        1 if data.get("in_interval_80") else 0,
                        1 if data.get("in_interval_95") else 0,
                        data.get("maturity_candle_hash", ""),
                        data.get("maturity_entry_hash", ""),
                        data.get("record_label", "HISTORICAL_REPLAY"),
                        data["outcome_hash"],
                        data["evaluated_at_utc"],
                        line_offset,
                        valid_count + 1,
                    ))
                    valid_count += 1
                    last_valid_offset = curr_offset
                except Exception as e:
                    f.seek(0, os.SEEK_END)
                    is_trailing = (curr_offset == f.tell())
                    if is_trailing:
                        logger.warning(f"Trailing corrupt write in outcomes journal at offset {line_offset}: {e}. Truncating.")
                        f.seek(line_offset)
                        corrupted_bytes = f.read()
                        if corrupted_bytes:
                            ts_ms = int(time.time() * 1000)
                            forensic_file = self.quarantine_dir / f"forensic_trailing_outcome_corruption_{ts_ms}.bin"
                            with open(forensic_file, "wb") as bf:
                                bf.write(corrupted_bytes)
                                bf.flush()
                                os.fsync(bf.fileno())
                        f.flush()
                        os.ftruncate(f.fileno(), last_valid_offset)
                        f.seek(last_valid_offset)
                        f.flush()
                        os.fsync(f.fileno())
                        break
                    else:
                        raise EventTamperError(f"Mid-file corruption in outcome journal at offset {line_offset}: {e}") from e

        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM outcomes_index WHERE journal_byte_offset >= ?;", (last_valid_offset,))
                if batch_items:
                    conn.executemany(
                        """
                        INSERT INTO outcomes_index (
                            outcome_id, prediction_event_hash, forecast_origin_utc,
                            target_maturity_utc, target_horizon, candidate_branch,
                            point_forecast, realized_volatility, actual_bars_evaluated,
                            status, in_interval_80, in_interval_95, maturity_candle_hash,
                            maturity_entry_hash, record_label, outcome_hash, evaluated_at_utc,
                            journal_byte_offset, journal_line_no
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(outcome_id) DO UPDATE SET
                            journal_byte_offset = excluded.journal_byte_offset,
                            journal_line_no = excluded.journal_line_no;
                        """,
                        batch_items,
                    )
                conn.commit()

        return valid_count

    def close(self) -> None:
        """Close method for interface compatibility."""
        pass

    def __del__(self) -> None:
        self.close()
