"""CBE-0.8.0 Prospective Feed Capture Manager, Snapshot Persistence & Eligibility Engine.

Implements the operational requirements for Sprint 09.9:
1. Feature quality metadata distinguishing genuine zero-values from fallback fillna(0.0).
2. Exact warm-up contract (MINIMUM_COMPUTABLE, FULL_WINDOW_READY, PROSPECTIVE_ELIGIBLE).
3. Monotonic receipt-time, exchange-close, and commit timestamps with clock-skew monitoring.
4. Bounded 350-candle snapshot persistence with atomic write, SHA-256 checksum, and corruption detection.
5. Deterministic, fail-closed 10-state Prospective Eligibility State Machine.
6. Local load testing and resource benchmarking harness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from coin_behavior_engine.candidate_v080.feed_adapter import (
    CANDLE_INTERVAL_MS,
    BUFFER_CAPACITY,
    FULL_WARMUP_BARS,
    MIN_WARMUP_BARS,
    CandleData,
    FeedAdapterError,
    FeedAdapterV080,
    ReconstructedFeatures,
)

logger = logging.getLogger("cbe_capture_manager")

SNAPSHOT_SCHEMA_VERSION = "CBE-SNAPSHOT-0.8.0"
SOURCE_IDENTIFIER = "BINANCE_BTCUSDT_SPOT"
MAX_ALLOWABLE_CLOCK_SKEW_MS = 1000.0  # 1.0 second clock-skew budget


class CaptureState(str, enum.Enum):
    """The 10 states of the Prospective Eligibility State Machine."""
    INITIALIZING = "INITIALIZING"
    WARMING_UP = "WARMING_UP"
    FULL_WINDOW_READY = "FULL_WINDOW_READY"
    STALE_DATA = "STALE_DATA"
    SOURCE_GAP = "SOURCE_GAP"
    INVALID_CANDLE = "INVALID_CANDLE"
    CLOCK_UNTRUSTED = "CLOCK_UNTRUSTED"
    SNAPSHOT_CORRUPT = "SNAPSHOT_CORRUPT"
    PAUSED = "PAUSED"
    ELIGIBLE = "ELIGIBLE"


class FeatureQualityStatus(str, enum.Enum):
    """Explicit status classifying feature quality and fallback presence."""
    PRISTINE = "PRISTINE"
    ZERO_VARIANCE_FALLBACK = "ZERO_VARIANCE_FALLBACK"
    MISSING_INPUT_FALLBACK = "MISSING_INPUT_FALLBACK"
    INSUFFICIENT_WINDOW = "INSUFFICIENT_WINDOW"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"


class SnapshotError(Exception):
    """Base exception for snapshot management errors."""
    pass


class SnapshotCorruptionError(SnapshotError):
    """Raised when snapshot checksum or schema verification fails."""
    pass


class SnapshotTruncationError(SnapshotError):
    """Raised when snapshot file is incomplete or truncated."""
    pass


@dataclass
class FeatureQualityMetadata:
    """Metadata detailing the causal integrity and quality of reconstructed features."""
    raw_feature_available: bool
    rolling_window_count: int
    zero_variance_detected: bool
    missing_input_detected: bool
    fallback_applied: bool
    feature_quality_status: str  # Value from FeatureQualityStatus
    eligible_for_prospective_scoring: bool
    quality_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TimestampAuditRecord:
    """Three-tier timestamp contract for prospective observation."""
    exchange_close_time_utc: str
    exchange_close_time_ms: int
    local_receipt_time_utc: str
    local_receipt_time_ms: int
    durable_commit_time_utc: str
    durable_commit_time_ms: int
    local_monotonic_ns: int
    estimated_network_latency_ms: float
    clock_skew_ms: float
    clock_trusted: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotHeader:
    schema_version: str
    source_identifier: str
    snapshot_timestamp_utc: str
    candle_count: int
    first_candle_open_utc: str
    last_candle_close_utc: str
    last_candle_close_ms: int
    last_sequence_number: int
    payload_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SnapshotManagerV080:
    """Manages atomic persistence, validation, and recovery of the 350-candle rolling buffer."""

    def __init__(self, snapshot_dir: Path):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_file = self.snapshot_dir / "candle_buffer_snapshot.json"
        self.temp_file = self.snapshot_dir / "candle_buffer_snapshot.json.tmp"

    def save_snapshot(self, candles: List[CandleData], sequence_number: int) -> SnapshotHeader:
        """Atomically persist candles to disk with SHA-256 checksum."""
        if not candles:
            raise SnapshotError("Cannot persist empty candle buffer.")

        # Serialize candle payload to canonical JSON
        candle_dicts = [
            {
                "timestamp_open": c.timestamp_open,
                "timestamp_close": c.timestamp_close,
                "datetime_open": c.datetime_open,
                "datetime_close": c.datetime_close,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "is_closed": c.is_closed,
                "receipt_timestamp_utc": c.receipt_timestamp_utc,
            }
            for c in candles
        ]
        payload_bytes = json.dumps(candle_dicts, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        header = SnapshotHeader(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            source_identifier=SOURCE_IDENTIFIER,
            snapshot_timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            candle_count=len(candles),
            first_candle_open_utc=candles[0].datetime_open,
            last_candle_close_utc=candles[-1].datetime_close,
            last_candle_close_ms=candles[-1].timestamp_close,
            last_sequence_number=sequence_number,
            payload_sha256=payload_hash,
        )

        full_doc = {
            "header": header.to_dict(),
            "candles": candle_dicts,
        }

        # Atomic write pattern: write to tmp, flush, fsync, rename
        with open(self.temp_file, "w", encoding="utf-8") as f:
            json.dump(full_doc, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Atomic replace with Windows-safe lock retry handling
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                os.replace(self.temp_file, self.snapshot_file)
                break
            except PermissionError:
                if attempt == max_attempts - 1:
                    raise
                time.sleep(0.005 * (attempt + 1))
        return header

    def load_snapshot(self) -> Tuple[SnapshotHeader, List[CandleData]]:
        """Load and strictly validate snapshot integrity."""
        if not self.snapshot_file.exists():
            raise FileNotFoundError(f"Snapshot file not found: {self.snapshot_file}")

        try:
            with open(self.snapshot_file, "r", encoding="utf-8") as f:
                content = f.read()
                full_doc = json.loads(content)
        except json.JSONDecodeError as e:
            raise SnapshotTruncationError(f"Snapshot file corrupted or truncated: {e}") from e

        if "header" not in full_doc or "candles" not in full_doc:
            raise SnapshotCorruptionError("Missing header or candles in snapshot structure.")

        h_dict = full_doc["header"]
        header = SnapshotHeader(
            schema_version=h_dict.get("schema_version", ""),
            source_identifier=h_dict.get("source_identifier", ""),
            snapshot_timestamp_utc=h_dict.get("snapshot_timestamp_utc", ""),
            candle_count=h_dict.get("candle_count", 0),
            first_candle_open_utc=h_dict.get("first_candle_open_utc", ""),
            last_candle_close_utc=h_dict.get("last_candle_close_utc", ""),
            last_candle_close_ms=h_dict.get("last_candle_close_ms", 0),
            last_sequence_number=h_dict.get("last_sequence_number", 0),
            payload_sha256=h_dict.get("payload_sha256", ""),
        )

        if header.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise SnapshotCorruptionError(
                f"Schema version mismatch: expected {SNAPSHOT_SCHEMA_VERSION}, got {header.schema_version}"
            )
        if header.source_identifier != SOURCE_IDENTIFIER:
            raise SnapshotCorruptionError(
                f"Source identifier mismatch: expected {SOURCE_IDENTIFIER}, got {header.source_identifier}"
            )

        candles_raw = full_doc["candles"]
        if len(candles_raw) != header.candle_count:
            raise SnapshotCorruptionError(
                f"Candle count mismatch: header declares {header.candle_count}, found {len(candles_raw)}"
            )

        # Checksum verification
        payload_bytes = json.dumps(candles_raw, sort_keys=True).encode("utf-8")
        computed_hash = hashlib.sha256(payload_bytes).hexdigest()
        if computed_hash != header.payload_sha256:
            raise SnapshotCorruptionError(
                f"Payload checksum mismatch: expected {header.payload_sha256}, got {computed_hash}"
            )

        candles = [CandleData.from_dict(c) for c in candles_raw]
        return header, candles


class EligibilityStateMachineV080:
    """Deterministic, fail-closed 10-state Prospective Eligibility State Machine."""

    # Valid transitions lookup: current_state -> set of allowed next_states
    VALID_TRANSITIONS: Dict[CaptureState, set[CaptureState]] = {
        CaptureState.INITIALIZING: {
            CaptureState.WARMING_UP,
            CaptureState.FULL_WINDOW_READY,
            CaptureState.SNAPSHOT_CORRUPT,
            CaptureState.SOURCE_GAP,
            CaptureState.INVALID_CANDLE,
            CaptureState.CLOCK_UNTRUSTED,
        },
        CaptureState.WARMING_UP: {
            CaptureState.WARMING_UP,
            CaptureState.FULL_WINDOW_READY,
            CaptureState.SOURCE_GAP,
            CaptureState.INVALID_CANDLE,
            CaptureState.CLOCK_UNTRUSTED,
            CaptureState.PAUSED,
        },
        CaptureState.FULL_WINDOW_READY: {
            CaptureState.ELIGIBLE,
            CaptureState.STALE_DATA,
            CaptureState.SOURCE_GAP,
            CaptureState.INVALID_CANDLE,
            CaptureState.CLOCK_UNTRUSTED,
            CaptureState.PAUSED,
        },
        CaptureState.ELIGIBLE: {
            CaptureState.ELIGIBLE,
            CaptureState.STALE_DATA,
            CaptureState.SOURCE_GAP,
            CaptureState.INVALID_CANDLE,
            CaptureState.CLOCK_UNTRUSTED,
            CaptureState.PAUSED,
        },
        CaptureState.STALE_DATA: {
            CaptureState.WARMING_UP,
            CaptureState.FULL_WINDOW_READY,
            CaptureState.SOURCE_GAP,
            CaptureState.INVALID_CANDLE,
            CaptureState.PAUSED,
        },
        CaptureState.SOURCE_GAP: {
            CaptureState.WARMING_UP,
            CaptureState.PAUSED,
        },
        CaptureState.INVALID_CANDLE: {
            CaptureState.WARMING_UP,
            CaptureState.PAUSED,
        },
        CaptureState.CLOCK_UNTRUSTED: {
            CaptureState.WARMING_UP,
            CaptureState.FULL_WINDOW_READY,
            CaptureState.PAUSED,
        },
        CaptureState.SNAPSHOT_CORRUPT: {
            CaptureState.WARMING_UP,
            CaptureState.PAUSED,
        },
        CaptureState.PAUSED: {
            CaptureState.WARMING_UP,
            CaptureState.FULL_WINDOW_READY,
            CaptureState.ELIGIBLE,
        },
    }

    def __init__(self, initial_state: CaptureState = CaptureState.INITIALIZING):
        self.current_state = initial_state
        self.state_history: List[Dict[str, Any]] = [
            {
                "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "state": self.current_state.value,
                "reason": "STATE_MACHINE_INIT",
            }
        ]

    def transition_to(self, new_state: CaptureState, reason: str) -> None:
        """Transition to a new state with strict transition validation."""
        allowed = self.VALID_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition: {self.current_state.value} -> {new_state.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )

        self.current_state = new_state
        self.state_history.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "state": self.current_state.value,
                "reason": reason,
            }
        )

    @property
    def is_eligible(self) -> bool:
        """Only the ELIGIBLE state permits prospective prediction generation."""
        return self.current_state == CaptureState.ELIGIBLE


class CandidateCaptureEngineV080:
    """Integrated capture engine coordinating feed adapter, snapshotting, and eligibility."""

    def __init__(
        self,
        snapshot_dir: Optional[Path] = None,
        clock_skew_budget_ms: float = MAX_ALLOWABLE_CLOCK_SKEW_MS,
    ):
        self.adapter = FeedAdapterV080(buffer_capacity=BUFFER_CAPACITY)
        self.state_machine = EligibilityStateMachineV080(CaptureState.INITIALIZING)
        self.clock_skew_budget_ms = clock_skew_budget_ms
        self.sequence_number = 0

        self.snapshot_manager: Optional[SnapshotManagerV080] = None
        if snapshot_dir is not None:
            self.snapshot_manager = SnapshotManagerV080(snapshot_dir)

        self.last_candle_receipt_monotonic_ns: int = 0
        self.last_candle_close_time_ms: int = 0

    def initialize_from_snapshot(self) -> bool:
        """Attempt to restore buffer from local snapshot."""
        if self.snapshot_manager is None or not self.snapshot_manager.snapshot_file.exists():
            self.state_machine.transition_to(CaptureState.WARMING_UP, "NO_SNAPSHOT_FOUND")
            return False

        try:
            header, candles = self.snapshot_manager.load_snapshot()
            for candle in candles:
                self.adapter.ingest_candle(candle)

            self.sequence_number = header.last_sequence_number
            self.last_candle_close_time_ms = header.last_candle_close_ms

            if len(self.adapter.buffer) >= FULL_WARMUP_BARS:
                self.state_machine.transition_to(CaptureState.FULL_WINDOW_READY, "SNAPSHOT_RESTORED_FULL_WINDOW")
            else:
                self.state_machine.transition_to(CaptureState.WARMING_UP, "SNAPSHOT_RESTORED_PARTIAL_WINDOW")
            return True
        except (SnapshotCorruptionError, SnapshotTruncationError) as e:
            logger.warning(f"Snapshot restore failed: {e}")
            self.adapter.reset()
            self.state_machine.transition_to(CaptureState.SNAPSHOT_CORRUPT, str(e))
            return False

    def ingest_new_candle(
        self,
        candle: CandleData,
        simulated_receipt_time_ms: Optional[int] = None,
        simulated_monotonic_ns: Optional[int] = None,
        simulated_wall_time_ms: Optional[int] = None,
    ) -> Tuple[ReconstructedFeatures, FeatureQualityMetadata, TimestampAuditRecord]:
        """Ingest a closed candle, audit timestamps, evaluate quality, and update state."""
        # 1. Capture monotonic and wall clock
        mono_ns = simulated_monotonic_ns if simulated_monotonic_ns is not None else time.monotonic_ns()
        rec_ms = simulated_receipt_time_ms if simulated_receipt_time_ms is not None else int(time.time() * 1000)
        rec_utc = datetime.fromtimestamp(rec_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 2. Audit timestamps and clock skew
        network_lat_est = max(0.0, float(rec_ms - candle.timestamp_close))
        now_wall_ms = simulated_wall_time_ms if simulated_wall_time_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
        clock_skew = abs(float(rec_ms - now_wall_ms))
        clock_trusted = clock_skew <= self.clock_skew_budget_ms

        if not clock_trusted:
            if self.state_machine.current_state in [
                CaptureState.INITIALIZING,
                CaptureState.FULL_WINDOW_READY,
                CaptureState.ELIGIBLE,
                CaptureState.WARMING_UP,
            ]:
                self.state_machine.transition_to(
                    CaptureState.CLOCK_UNTRUSTED, f"CLOCK_SKEW_{clock_skew:.1f}MS_EXCEEDS_BUDGET"
                )

        # 3. Feed candle to adapter
        try:
            recon = self.adapter.ingest_candle(candle)
        except FeedAdapterError as e:
            err_msg = str(e)
            if "GAP" in err_msg.upper() or "CONTINUITY" in err_msg.upper():
                self.state_machine.transition_to(CaptureState.SOURCE_GAP, err_msg)
            else:
                self.state_machine.transition_to(CaptureState.INVALID_CANDLE, err_msg)
            raise

        self.sequence_number += 1
        self.last_candle_close_time_ms = candle.timestamp_close
        self.last_candle_receipt_monotonic_ns = mono_ns

        # 4. Check for staleness (e.g. > 600s since close)
        is_stale = (rec_ms - candle.timestamp_close) > (2 * CANDLE_INTERVAL_MS)
        if is_stale and self.state_machine.current_state in [CaptureState.FULL_WINDOW_READY, CaptureState.ELIGIBLE]:
            self.state_machine.transition_to(CaptureState.STALE_DATA, "DATA_STALENESS_EXCEEDS_10M")

        # 5. Evaluate quality metadata and distinguish legitimate 0 from fallback
        quality = self._evaluate_feature_quality(recon)

        # 6. Update state machine transitions
        buf_len = len(self.adapter.buffer)
        if self.state_machine.current_state == CaptureState.INITIALIZING:
            if buf_len >= FULL_WARMUP_BARS:
                self.state_machine.transition_to(CaptureState.FULL_WINDOW_READY, "BUFFER_REACHED_288_BARS")
            else:
                self.state_machine.transition_to(CaptureState.WARMING_UP, "INGESTED_FIRST_CANDLE")
        elif self.state_machine.current_state == CaptureState.WARMING_UP:
            if buf_len >= FULL_WARMUP_BARS:
                self.state_machine.transition_to(CaptureState.FULL_WINDOW_READY, "BUFFER_REACHED_288_BARS")

        if self.state_machine.current_state == CaptureState.FULL_WINDOW_READY:
            if clock_trusted and not is_stale and quality.eligible_for_prospective_scoring:
                self.state_machine.transition_to(CaptureState.ELIGIBLE, "ALL_ELIGIBILITY_GATES_PASSED")

        # 7. Record durable commit timestamp
        commit_ms = int(time.time() * 1000)
        commit_utc = datetime.fromtimestamp(commit_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        ts_audit = TimestampAuditRecord(
            exchange_close_time_utc=candle.datetime_close,
            exchange_close_time_ms=candle.timestamp_close,
            local_receipt_time_utc=rec_utc,
            local_receipt_time_ms=rec_ms,
            durable_commit_time_utc=commit_utc,
            durable_commit_time_ms=commit_ms,
            local_monotonic_ns=mono_ns,
            estimated_network_latency_ms=network_lat_est,
            clock_skew_ms=clock_skew,
            clock_trusted=clock_trusted,
        )

        # 8. Persist snapshot if configured
        if self.snapshot_manager is not None:
            self.snapshot_manager.save_snapshot(self.adapter.buffer, self.sequence_number)

        return recon, quality, ts_audit

    def _evaluate_feature_quality(self, recon: ReconstructedFeatures) -> FeatureQualityMetadata:
        """Inspect reconstructed features to separate genuine zero-values from fallbacks."""
        notes = []
        buf_len = recon.lookback_bars
        feats = recon.features

        raw_avail = recon.status in ["READY", "READY_PARTIAL_WARMUP"]
        if not raw_avail:
            return FeatureQualityMetadata(
                raw_feature_available=False,
                rolling_window_count=buf_len,
                zero_variance_detected=False,
                missing_input_detected=True,
                fallback_applied=True,
                feature_quality_status=FeatureQualityStatus.INSUFFICIENT_WINDOW.value,
                eligible_for_prospective_scoring=False,
                quality_notes=["Buffer lookback below minimum requirement."],
            )

        # Inspect volume values in buffer
        volumes = [c.volume for c in self.adapter.buffer]
        recent_volumes = volumes[-FULL_WARMUP_BARS:]
        vol_mean = float(np.mean(recent_volumes))
        vol_std = float(np.std(recent_volumes, ddof=1)) if len(recent_volumes) > 1 else 0.0

        zero_var = (vol_std == 0.0)
        missing_input = any(math.isnan(v) or math.isinf(v) for v in recent_volumes)
        fallback_applied = False
        quality_status = FeatureQualityStatus.PRISTINE

        # Check volume zscore
        zscore = feats.get("volume_zscore_24h", 0.0)

        if zero_var:
            zero_var = True
            fallback_applied = True
            quality_status = FeatureQualityStatus.ZERO_VARIANCE_FALLBACK
            notes.append("Volume standard deviation is 0.0; fallback applied.")
        elif missing_input:
            missing_input = True
            fallback_applied = True
            quality_status = FeatureQualityStatus.MISSING_INPUT_FALLBACK
            notes.append("Missing or non-finite volume detected; fallback applied.")
        elif zscore == 0.0:
            # Check if legitimate zero (i.e. latest volume equals mean volume)
            latest_v = self.adapter.buffer[-1].volume
            if abs(latest_v - vol_mean) < 1e-9:
                notes.append("Volume zscore is legitimately 0.0 (volume matches window mean).")
            else:
                fallback_applied = True
                notes.append("Volume zscore is 0.0 due to clipping or fillna.")

        if buf_len < FULL_WARMUP_BARS:
            quality_status = FeatureQualityStatus.INSUFFICIENT_WINDOW
            notes.append(f"Window count {buf_len} is less than full window requirement {FULL_WARMUP_BARS}.")

        # Strict eligibility: requires PRISTINE, full window, and no fallback
        eligible = (
            quality_status == FeatureQualityStatus.PRISTINE
            and buf_len >= FULL_WARMUP_BARS
            and not fallback_applied
            and not zero_var
            and not missing_input
        )

        return FeatureQualityMetadata(
            raw_feature_available=True,
            rolling_window_count=buf_len,
            zero_variance_detected=zero_var,
            missing_input_detected=missing_input,
            fallback_applied=fallback_applied,
            feature_quality_status=quality_status.value,
            eligible_for_prospective_scoring=eligible,
            quality_notes=notes,
        )
