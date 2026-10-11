"""CBE-0.8.0 Persistent Market Evidence Lookup & Forward Window Verification Interface.

Sprint 09.16: Persistent Evidence-Based Outcome Resolution.

Provides a bounded, strictly read-only interface to the authoritative raw market evidence store:
1. Exact O(1) timestamp seek via disk-backed SQLite index.
2. Contiguous range retrieval across 1h (12 bars), 4h (48 bars), and 24h (288 bars) horizons.
3. Cryptographic hash references to underlying raw candle entries.
4. Causal forward window validation (rejecting premature evaluation and detecting data gaps).
5. Zero dependency on the in-memory rolling buffer.
6. Strictly read-only: does not modify or rewrite the append-only evidence ledger.
"""

from __future__ import annotations

import collections
import enum
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    CandleLifecycleState,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    MarketEvidenceEntry,
    RawMarketEvidenceStore,
)

logger = logging.getLogger("cbe_evidence_lookup")


class ForwardWindowStatus(str, enum.Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE_PENDING = "INCOMPLETE_PENDING"
    INVALID_GAP = "INVALID_GAP"
    MISSING_ORIGIN = "MISSING_ORIGIN"


@dataclass(frozen=True)
class ForwardWindowResult:
    """Detailed causal result of forward outcome window inspection."""
    is_complete: bool
    has_gap: bool
    status: ForwardWindowStatus
    candles: List[ValidatedCandle]
    expected_bars: int
    actual_bars: int
    target_maturity_ts_open: Optional[int]
    target_maturity_ts_close: Optional[int]
    maturity_candle: Optional[ValidatedCandle]
    maturity_entry: Optional[MarketEvidenceEntry]
    missing_timestamps: List[int]
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_complete": self.is_complete,
            "has_gap": self.has_gap,
            "status": self.status.value,
            "expected_bars": self.expected_bars,
            "actual_bars": self.actual_bars,
            "target_maturity_ts_open": self.target_maturity_ts_open,
            "target_maturity_ts_close": self.target_maturity_ts_close,
            "maturity_candle_hash": self.maturity_entry.candle_hash if self.maturity_entry else (
                self.maturity_candle.canonical_dict().get("close") if self.maturity_candle else None
            ),
            "missing_timestamps": self.missing_timestamps,
            "reason": self.reason,
        }


class PersistentEvidenceLookupV080:
    """Bounded, read-only interface querying immutable market evidence via SQLite timestamp index."""

    def __init__(
        self,
        raw_market_dir: Optional[Union[str, Path]] = None,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        evidence_store: Optional[RawMarketEvidenceStore] = None,
    ):
        self.symbol = symbol
        self.interval = interval
        self.evidence_store = evidence_store

        if evidence_store is not None:
            self.raw_market_dir = evidence_store.raw_market_dir
            self.evidence_file = evidence_store.evidence_file
            self.index_file = evidence_store.index_file
        elif raw_market_dir is not None:
            self.raw_market_dir = Path(raw_market_dir)
            self.evidence_file = self.raw_market_dir / f"raw_candles_{self.symbol}_{self.interval}.jsonl"
            self.index_file = self.raw_market_dir / f"index_{self.symbol}_{self.interval}.sqlite3"
        else:
            raise ValueError("Either raw_market_dir or evidence_store must be supplied.")

        self._lock = threading.Lock()
        self._ro_conn: Optional[sqlite3.Connection] = None
        self._init_ro_connection()

    def _init_ro_connection(self) -> None:
        """Initialize read-only SQLite connection with query_only enforcement."""
        if not self.index_file.exists():
            return

        try:
            # Attempt strictly read-only URI connection
            uri_path = f"file:{self.index_file.resolve().as_posix()}?mode=ro"
            self._ro_conn = sqlite3.connect(uri_path, uri=True, check_same_thread=False)
        except Exception:
            try:
                self._ro_conn = sqlite3.connect(str(self.index_file), check_same_thread=False)
                self._ro_conn.execute("PRAGMA query_only = ON;")
            except Exception as e:
                logger.warning(f"Could not open SQLite index in read-only mode: {e}")
                self._ro_conn = None

    def _get_conn(self) -> Optional[sqlite3.Connection]:
        """Return available read-only index connection."""
        if self._ro_conn:
            return self._ro_conn
        if self.evidence_store and self.evidence_store._index_conn:
            return self.evidence_store._index_conn
        if self.index_file.exists():
            self._init_ro_connection()
            return self._ro_conn
        return None

    def has_timestamp(self, ts_open: int) -> bool:
        """Check if open timestamp exists in index."""
        conn = self._get_conn()
        if not conn:
            return False
        with self._lock:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM timestamp_index WHERE timestamp_open = ? LIMIT 1;", (ts_open,))
            return cur.fetchone() is not None

    def get_candle(self, ts_open: int) -> Optional[ValidatedCandle]:
        """Fetch ValidatedCandle by exact open timestamp."""
        if self.evidence_store:
            return self.evidence_store.get_candle_by_timestamp(ts_open)

        offset = self._get_offset_by_timestamp(ts_open)
        if offset is not None:
            return self._read_candle_at_offset(offset)
        return None

    def get_entry(self, ts_open: int) -> Optional[MarketEvidenceEntry]:
        """Fetch raw MarketEvidenceEntry with hash chain metadata by open timestamp."""
        offset = self._get_offset_by_timestamp(ts_open)
        if offset is not None:
            return self._read_entry_at_offset(offset)
        return None

    def _get_offset_by_timestamp(self, ts_open: int) -> Optional[int]:
        conn = self._get_conn()
        if not conn:
            return None
        with self._lock:
            cur = conn.cursor()
            cur.execute("SELECT byte_offset FROM timestamp_index WHERE timestamp_open = ? LIMIT 1;", (ts_open,))
            row = cur.fetchone()
            if row:
                return row[0]
        return None

    def _read_candle_at_offset(self, byte_offset: int) -> Optional[ValidatedCandle]:
        """Read and parse ValidatedCandle from jsonl file descriptor at byte offset."""
        if not self.evidence_file.exists():
            return None
        try:
            with open(self.evidence_file, "rb") as f:
                f.seek(byte_offset)
                raw_line = f.readline()
                if not raw_line:
                    return None
                data = json.loads(raw_line.decode("utf-8", errors="replace").strip())
                c_dict = data["candle"]
                return ValidatedCandle(
                    symbol=c_dict["symbol"],
                    interval=c_dict["interval"],
                    market_type=c_dict["market_type"],
                    timestamp_open=c_dict["timestamp_open"],
                    timestamp_close=c_dict["timestamp_close"],
                    datetime_open_utc=c_dict["datetime_open_utc"],
                    datetime_close_utc=c_dict["datetime_close_utc"],
                    open=str(c_dict["open"]),
                    high=str(c_dict["high"]),
                    low=str(c_dict["low"]),
                    close=str(c_dict["close"]),
                    volume=str(c_dict["volume"]),
                    quote_volume=str(c_dict.get("quote_volume", "0")),
                    trades_count=int(c_dict.get("trades_count", 0)),
                    taker_buy_base_volume=str(c_dict.get("taker_buy_base_volume", "0")),
                    is_closed=c_dict.get("is_closed", True),
                    provenance=c_dict.get("provenance", "LIVE_BINANCE_SPOT"),
                    receipt_timestamp_utc=c_dict.get("receipt_timestamp_utc", ""),
                    lifecycle_state=CandleLifecycleState.CANDLE_PERSISTED.value,
                )
        except Exception as exc:
            logger.warning(f"Error reading candle at offset {byte_offset}: {exc}")
            return None

    def _read_entry_at_offset(self, byte_offset: int) -> Optional[MarketEvidenceEntry]:
        """Read MarketEvidenceEntry from jsonl at byte offset."""
        if not self.evidence_file.exists():
            return None
        try:
            with open(self.evidence_file, "rb") as f:
                f.seek(byte_offset)
                raw_line = f.readline()
                if not raw_line:
                    return None
                data = json.loads(raw_line.decode("utf-8", errors="replace").strip())
                return MarketEvidenceEntry(
                    entry_index=int(data["entry_index"]),
                    prev_hash=str(data["prev_hash"]),
                    candle_hash=str(data["candle_hash"]),
                    entry_hash=str(data["entry_hash"]),
                    persisted_at_utc=str(data["persisted_at_utc"]),
                    candle=data["candle"],
                )
        except Exception as exc:
            logger.warning(f"Error reading entry at offset {byte_offset}: {exc}")
            return None

    def get_candles_range(self, start_ts_open: int, end_ts_open: int) -> List[ValidatedCandle]:
        """Query index for all offsets in range [start_ts_open, end_ts_open] and load candles."""
        conn = self._get_conn()
        if not conn:
            return []
        with self._lock:
            cur = conn.cursor()
            cur.execute(
                "SELECT byte_offset FROM timestamp_index WHERE timestamp_open >= ? AND timestamp_open <= ? ORDER BY timestamp_open ASC;",
                (start_ts_open, end_ts_open),
            )
            rows = cur.fetchall()

        candles: List[ValidatedCandle] = []
        for (offset,) in rows:
            c = self._read_candle_at_offset(offset)
            if c is not None:
                candles.append(c)
        return candles

    def get_latest_open_timestamp(self) -> Optional[int]:
        """Fetch greatest timestamp_open currently indexed."""
        conn = self._get_conn()
        if not conn:
            return None
        with self._lock:
            cur = conn.cursor()
            cur.execute("SELECT MAX(timestamp_open) FROM timestamp_index;")
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])
        return None

    def get_forward_window(
        self,
        origin_ts: int,
        required_bars: int,
        current_time_ms: Optional[int] = None,
        origin_is_close_time: bool = True,
    ) -> ForwardWindowResult:
        """Inspect and retrieve contiguous forward observation window for a forecast origin.

        Args:
            origin_ts: Origin timestamp in milliseconds (candle close time or open time).
            required_bars: Number of forward closed candles (12 for 1h, 48 for 4h, 288 for 24h).
            current_time_ms: Current observation clock. If None, uses latest committed candle close time.
            origin_is_close_time: True if origin_ts represents candle close time; False if open time.

        Returns:
            ForwardWindowResult indicating whether maturity has been reached, gap status, and candle records.
        """
        # 1. Determine first forward candle open timestamp
        if origin_is_close_time:
            # If origin corresponds to close timestamp (e.g. 12:00:00Z close), first forward candle opens at 12:00:00Z
            # In exchange millisecond timestamps, close is open + 299_999 ms, so close + 1 ms aligns to next open
            first_forward_open = (origin_ts + 1) if (origin_ts % CANDLE_INTERVAL_MS != 0) else origin_ts
        else:
            first_forward_open = origin_ts + CANDLE_INTERVAL_MS

        target_maturity_open = first_forward_open + (required_bars - 1) * CANDLE_INTERVAL_MS
        target_maturity_close = target_maturity_open + CANDLE_INTERVAL_MS - 1

        expected_timestamps = [first_forward_open + i * CANDLE_INTERVAL_MS for i in range(required_bars)]

        # 2. Check observation clock against exact maturity timestamp
        latest_known_ts = self.get_latest_open_timestamp()
        wall_clock = current_time_ms if current_time_ms is not None else (
            (latest_known_ts + CANDLE_INTERVAL_MS - 1) if latest_known_ts is not None else 0
        )

        if wall_clock < target_maturity_close:
            return ForwardWindowResult(
                is_complete=False,
                has_gap=False,
                status=ForwardWindowStatus.INCOMPLETE_PENDING,
                candles=[],
                expected_bars=required_bars,
                actual_bars=0,
                target_maturity_ts_open=target_maturity_open,
                target_maturity_ts_close=target_maturity_close,
                maturity_candle=None,
                maturity_entry=None,
                missing_timestamps=[],
                reason=f"Observation clock ({wall_clock}) has not reached exact maturity close ({target_maturity_close}).",
            )

        # 3. Query indexed offsets for the target window
        conn = self._get_conn()
        if not conn:
            return ForwardWindowResult(
                is_complete=False,
                has_gap=True,
                status=ForwardWindowStatus.INVALID_GAP,
                candles=[],
                expected_bars=required_bars,
                actual_bars=0,
                target_maturity_ts_open=target_maturity_open,
                target_maturity_ts_close=target_maturity_close,
                maturity_candle=None,
                maturity_entry=None,
                missing_timestamps=expected_timestamps,
                reason="SQLite index connection unavailable.",
            )

        with self._lock:
            cur = conn.cursor()
            cur.execute(
                "SELECT timestamp_open, byte_offset FROM timestamp_index WHERE timestamp_open >= ? AND timestamp_open <= ? ORDER BY timestamp_open ASC;",
                (first_forward_open, target_maturity_open),
            )
            rows = cur.fetchall()

        found_map: Dict[int, int] = {r[0]: r[1] for r in rows}
        missing = [ts for ts in expected_timestamps if ts not in found_map]

        if missing:
            # If the market has already advanced past maturity but bars are missing, flag explicit gap
            return ForwardWindowResult(
                is_complete=False,
                has_gap=True,
                status=ForwardWindowStatus.INVALID_GAP,
                candles=[],
                expected_bars=required_bars,
                actual_bars=len(found_map),
                target_maturity_ts_open=target_maturity_open,
                target_maturity_ts_close=target_maturity_close,
                maturity_candle=None,
                maturity_entry=None,
                missing_timestamps=missing,
                reason=f"Discontinuous window: {len(missing)} expected 5m candles missing in range.",
            )

        # 4. Load contiguous candles and maturity entry
        candles: List[ValidatedCandle] = []
        maturity_entry: Optional[MarketEvidenceEntry] = None

        for ts in expected_timestamps:
            offset = found_map[ts]
            c = self._read_candle_at_offset(offset)
            if c is None:
                return ForwardWindowResult(
                    is_complete=False,
                    has_gap=True,
                    status=ForwardWindowStatus.INVALID_GAP,
                    candles=candles,
                    expected_bars=required_bars,
                    actual_bars=len(candles),
                    target_maturity_ts_open=target_maturity_open,
                    target_maturity_ts_close=target_maturity_close,
                    maturity_candle=None,
                    maturity_entry=None,
                    missing_timestamps=[ts],
                    reason=f"Failed to read candle at offset {offset} for timestamp {ts}.",
                )

            if not c.is_closed:
                return ForwardWindowResult(
                    is_complete=False,
                    has_gap=True,
                    status=ForwardWindowStatus.INVALID_GAP,
                    candles=candles,
                    expected_bars=required_bars,
                    actual_bars=len(candles),
                    target_maturity_ts_open=target_maturity_open,
                    target_maturity_ts_close=target_maturity_close,
                    maturity_candle=None,
                    maturity_entry=None,
                    missing_timestamps=[],
                    reason=f"Candle at timestamp {ts} is not confirmed closed.",
                )

            candles.append(c)

        # Read maturity entry from ledger
        last_offset = found_map[target_maturity_open]
        maturity_entry = self._read_entry_at_offset(last_offset)

        return ForwardWindowResult(
            is_complete=True,
            has_gap=False,
            status=ForwardWindowStatus.COMPLETE,
            candles=candles,
            expected_bars=required_bars,
            actual_bars=len(candles),
            target_maturity_ts_open=target_maturity_open,
            target_maturity_ts_close=target_maturity_close,
            maturity_candle=candles[-1],
            maturity_entry=maturity_entry,
            missing_timestamps=[],
            reason="Full contiguous forward window verified.",
        )

    def close(self) -> None:
        """Close SQLite connection cleanly."""
        with self._lock:
            if self._ro_conn:
                try:
                    self._ro_conn.close()
                except Exception:
                    pass
                self._ro_conn = None

    def __del__(self) -> None:
        self.close()
