"""Isolated Prospective Scoring Worker for CBE-0.8.0 Shadow Collector.

Sprint 09.18: Isolated Prospective Scoring Worker — Implementation Without Activation.

Enforces:
1. Strict process and container isolation:
   - Independent process reading verified raw Binance BTCUSDT 5m evidence via read-only index.
   - Separate writable persistence directory for prospective predictions and outcomes.
   - Zero access or ability to modify raw market evidence.
   - Network disabled (network_mode: "none").
   - Trading permanently disabled (CBE_TRADING_DISABLED=true).
2. Defense-in-depth authorization check:
   - Dynamic check via ProspectiveAuthorizationGuard at BACKGROUND_WORKER execution boundary.
   - Fail-closed if APPROVAL 4 is not strictly authorized.
3. Continuous Warmup Enforcement:
   - Requires minimum 288 contiguous closed 5m bars before prospective scoring.
   - Skips inference and logs warmup progress if warmup is incomplete or has gaps.
4. Immutable Start Boundary & Separation of Replay from Prospective Observation:
   - Persisted WorkerStartBoundaryRecord establishes the authorized start boundary.
   - Pre-boundary candles closed <= start boundary are strictly HISTORICAL_WARMUP and NEVER emit prospective live predictions.
   - Only post-boundary candles (> start boundary) can generate prospective predictions when authorized.
5. Durable Checkpointing & Crash-Safe Restart:
   - Tracks last_processed_entry_index and timestamps in worker_checkpoint.json via atomic writes (.tmp + replace).
   - Re-reading past candles is idempotent.
6. Zero-Discard Paged Pending Resolution:
   - Resolves pending predictions in bounded pages (e.g. 500 items).
   - Handles queue overflow (>2,000 items) without silent data loss via DurablePredictionIndexV080.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import pandas as pd

from coin_behavior_engine.candidate_v080.feed_adapter import (
    CANDLE_INTERVAL_MS,
    CandleData,
)
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.evidence_lookup import (
    PersistentEvidenceLookupV080,
)
from coin_behavior_engine.shadow_v080.feature_pipeline import FeaturePipelineV080
from coin_behavior_engine.shadow_v080.inference_runner import (
    DualBranchInferenceRunnerV080,
    DualBranchPredictionResult,
)
from coin_behavior_engine.shadow_v080.market_data_contract import (
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    MarketEvidenceEntry,
)
from coin_behavior_engine.shadow_v080.outcome_resolver import (
    HORIZON_BARS,
    OutcomeResolverV080,
    ShadowOutcomeEvent,
)
from coin_behavior_engine.shadow_v080.prediction_indexing import (
    DurablePredictionIndexV080,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    ImmutablePredictionStoreV080,
    ShadowPredictionEvent,
)
from coin_behavior_engine.shadow_v080.prospective_guard import (
    CausalDataEligibilityGuard,
    DiscontinuousCandlesError,
    ExecutionBoundary,
    InsufficientWarmupBarsError,
    ProspectiveAuthorizationError,
    ProspectiveAuthorizationGuard,
)

logger = logging.getLogger("cbe_scoring_worker")


# ==============================================================================
# Worker Start Boundary Record
# ==============================================================================

@dataclass
class WorkerStartBoundaryRecord:
    """Authoritative immutable record establishing the prospective live scoring boundary."""
    authorized_start_boundary_utc: str
    authorized_start_boundary_ts_ms: int
    git_commit: str
    authorization_digest: str
    last_captured_candle_timestamp_ms: int
    created_at_utc: str
    symbol: str = "BTCUSDT"
    interval: str = "5m"
    market_type: str = "SPOT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerStartBoundaryRecord":
        return cls(**data)

    def save(self, filepath: Path) -> None:
        """Atomically persist start boundary record to disk."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)

    @classmethod
    def load(cls, filepath: Path) -> Optional["WorkerStartBoundaryRecord"]:
        p = Path(filepath)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as exc:
            logger.warning(f"Failed to load start boundary record from {filepath}: {exc}")
            return None


# ==============================================================================
# Worker Checkpoint
# ==============================================================================

@dataclass
class WorkerCheckpoint:
    """Crash-safe state tracking for the scoring worker."""
    last_processed_entry_index: int = -1
    last_processed_candle_timestamp_ms: int = 0
    last_outcome_resolution_timestamp_ms: int = 0
    total_entries_read: int = 0
    total_warmup_bars_buffered: int = 0
    total_predictions_emitted: int = 0
    total_outcomes_resolved: int = 0
    pending_predictions_count: int = 0
    updated_at_utc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerCheckpoint":
        return cls(**data)

    def save_atomic(self, filepath: Path) -> None:
        """Atomically persist checkpoint using write-to-tmp and replace."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        self.updated_at_utc = datetime.now(timezone.utc).isoformat()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)

    @classmethod
    def load(cls, filepath: Path) -> Optional["WorkerCheckpoint"]:
        p = Path(filepath)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as exc:
            logger.warning(f"Failed to load checkpoint from {filepath}: {exc}")
            return None


# ==============================================================================
# Worker Configuration
# ==============================================================================

VALID_RUN_MODES = frozenset({"PASSIVE_OBSERVATION", "OFFLINE_WARMUP", "PROSPECTIVE_LIVE"})

@dataclass
class WorkerConfigV080:
    evidence_dir: Path
    prospective_dir: Path
    symbol: str = "BTCUSDT"
    interval: str = "5m"
    market_type: str = "SPOT"
    batch_size: int = 50
    page_size: int = 500
    poll_interval_s: float = 1.0
    min_warmup_bars: int = 288
    max_buffer_bars: int = 350
    run_mode: str = "PASSIVE_OBSERVATION"  # "PASSIVE_OBSERVATION", "OFFLINE_WARMUP", or "PROSPECTIVE_LIVE"
    models_dir: Optional[Path] = None
    quarantine_dir: Optional[Path] = None
    env: Optional[Dict[str, str]] = None
    experiment_id: str = "EXP-CBE-0.8.0-SHADOW-2026-V1"
    protocol_version: str = "CBE-PROTOCOL-0.8.0-V1"

    def __post_init__(self) -> None:
        if self.run_mode not in VALID_RUN_MODES:
            raise ValueError(f"Invalid run_mode '{self.run_mode}'. Must be one of {sorted(VALID_RUN_MODES)}")


# ==============================================================================
# Isolated Prospective Scoring Worker
# ==============================================================================

class ProspectiveScoringWorkerV080:
    """Autonomous, isolated scoring worker consuming verified market evidence."""

    def __init__(self, config: WorkerConfigV080):
        self.config = config
        self.evidence_dir = Path(config.evidence_dir)
        self.prospective_dir = Path(config.prospective_dir)
        self.prospective_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.prospective_dir / "worker_checkpoint.json"
        self.boundary_file = self.prospective_dir / "authorized_start_boundary.json"
        self.quarantine_dir = Path(config.quarantine_dir) if config.quarantine_dir else (self.prospective_dir / "quarantine")
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

        # Fail-closed startup configuration checks
        env_map = self.config.env if self.config.env is not None else os.environ
        trading_val = env_map.get("CBE_TRADING_DISABLED", "true")
        if trading_val != "true":
            raise ProspectiveAuthorizationError(
                f"CBE_TRADING_DISABLED must be strictly 'true' (got '{trading_val}'). Trading is prohibited."
            )

        # 1. Read-Only Evidence Lookup (Zero ability to modify capture ledger)
        self.evidence_lookup = PersistentEvidenceLookupV080(
            evidence_dir=self.evidence_dir,
            symbol=config.symbol,
            interval=config.interval,
        )

        # 2. Durable Prediction Store & Index in isolated writable directory
        self.prediction_store = ImmutablePredictionStoreV080(
            store_dir=self.prospective_dir,
            quarantine_dir=self.quarantine_dir,
            enable_sqlite_index=True,
        )

        # 3. Durable Outcome Resolver in isolated writable directory
        self.outcome_resolver = OutcomeResolverV080(
            store_dir=self.prospective_dir,
            quarantine_dir=self.quarantine_dir,
        )

        # 4. Checkpoint & Start Boundary
        self.checkpoint = WorkerCheckpoint.load(self.checkpoint_file) or WorkerCheckpoint()
        self.start_boundary = WorkerStartBoundaryRecord.load(self.boundary_file)

        # 5. In-Memory Rolling Window Buffer (Bounded to max_buffer_bars)
        self._recent_candles: List[ValidatedCandle] = []
        self._lock = threading.RLock()
        self._stop_requested = False
        self._is_running = False

        # 6. Feature Pipeline & Model Inference Runner
        self._collector_config = ShadowCollectorConfig(
            symbol=config.symbol,
            interval=config.interval,
            max_buffer_candles=config.max_buffer_bars,
            full_warmup_bars=config.min_warmup_bars,
            models_dir=config.models_dir,
            shadow_data_dir=self.prospective_dir,
            experiment_id=config.experiment_id,
            protocol_version=config.protocol_version,
        )
        self.feature_pipeline = FeaturePipelineV080(self._collector_config)

        self.inference_runner: Optional[DualBranchInferenceRunnerV080] = None
        try:
            self.inference_runner = DualBranchInferenceRunnerV080(self._collector_config)
        except Exception as exc:
            logger.warning(f"Inference runner not initialized (models may not be loaded): {exc}")

        # 7. Restore warmup buffer if resuming
        self._restore_buffer_state()

    def _restore_buffer_state(self) -> None:
        """Restore rolling candle buffer from evidence lookup on startup."""
        if self.checkpoint.last_processed_candle_timestamp_ms > 0:
            window = self.evidence_lookup.get_backward_window(
                origin_ts=self.checkpoint.last_processed_candle_timestamp_ms,
                num_bars=min(self.config.max_buffer_bars, 350),
            )
            if window:
                self._recent_candles = list(window)
                self.feature_pipeline.adapter.reset()
                for c in self._recent_candles:
                    cdata = CandleData(
                        timestamp_open=c.timestamp_open,
                        timestamp_close=c.timestamp_close,
                        datetime_open=c.datetime_open_utc,
                        datetime_close=c.datetime_close_utc,
                        open=float(c.open),
                        high=float(c.high),
                        low=float(c.low),
                        close=float(c.close),
                        volume=float(c.volume),
                        is_closed=c.is_closed,
                    )
                    self.feature_pipeline.add_candle(cdata)
                self.checkpoint.total_warmup_bars_buffered = len(self._recent_candles)
                logger.info(
                    f"Restored rolling buffer with {len(self._recent_candles)} contiguous candles from evidence ledger."
                )

    def establish_start_boundary(
        self,
        git_commit: str = "unknown",
        auth_digest: str = "",
    ) -> WorkerStartBoundaryRecord:
        """Establish immutable prospective start boundary after explicit operator authorization.

        Enforces Gate 4 fail-closed authorization.
        """
        ProspectiveAuthorizationGuard.verify_authorization(
            boundary=ExecutionBoundary.BACKGROUND_WORKER,
            run_mode="PROSPECTIVE_LIVE",
            env=self.config.env,
        )

        latest_candle = self.evidence_lookup.get_latest_candle()
        last_ts = latest_candle.timestamp_close if latest_candle else 0
        now_utc = datetime.now(timezone.utc)
        boundary_ts = max(int(now_utc.timestamp() * 1000), last_ts)

        if not auth_digest:
            h = hashlib.sha256(
                f"{git_commit}:{boundary_ts}:{self.config.symbol}:{self.config.interval}".encode("utf-8")
            ).hexdigest()
            auth_digest = f"AUTH-DIGEST-{h[:16]}"

        record = WorkerStartBoundaryRecord(
            authorized_start_boundary_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            authorized_start_boundary_ts_ms=boundary_ts,
            git_commit=git_commit,
            authorization_digest=auth_digest,
            last_captured_candle_timestamp_ms=last_ts,
            created_at_utc=now_utc.isoformat(),
            symbol=self.config.symbol,
            interval=self.config.interval,
            market_type=self.config.market_type,
        )
        record.save(self.boundary_file)
        self.start_boundary = record
        logger.info(
            f"Immutable start boundary established at {record.authorized_start_boundary_utc} (ts={boundary_ts})"
        )
        return record

    def check_warmup_status(self) -> Tuple[bool, int, str]:
        """Verify whether minimum 288 contiguous closed 5m bars are available."""
        with self._lock:
            count = len(self._recent_candles)
            if count < self.config.min_warmup_bars:
                return False, count, f"Insufficient warmup: {count}/{self.config.min_warmup_bars} contiguous bars."

            # Check timestamp continuity across recent window
            prev_ts: Optional[int] = None
            for idx, c in enumerate(self._recent_candles[-self.config.min_warmup_bars:]):
                if prev_ts is not None:
                    if c.timestamp_open != prev_ts + CANDLE_INTERVAL_MS:
                        return (
                            False,
                            count,
                            f"Discontinuous candles at bar {idx}: gap between {prev_ts} and {c.timestamp_open}",
                        )
                prev_ts = c.timestamp_open

            return True, count, f"Full warmup satisfied with {count} contiguous bars."

    def process_next_batch(self) -> int:
        """Fetch and process the next incremental batch of verified evidence entries.

        Returns the number of evidence entries processed.
        """
        with self._lock:
            # 1. Fetch sequential batch after last processed entry_index
            entries = self.evidence_lookup.get_entries_after_index(
                last_entry_index=self.checkpoint.last_processed_entry_index,
                limit=self.config.batch_size,
            )

            if not entries:
                # No new evidence bars; perform outcome resolution on pending predictions
                resolved = self.resolve_pending_outcomes()
                self._save_checkpoint()
                return 0

            # 2. Ingest sequential entries
            for entry, candle in entries:
                self._process_single_candle(entry, candle)

            # 3. Resolve pending outcomes
            self.resolve_pending_outcomes()

            # 4. Checkpoint state atomically
            self._save_checkpoint()
            return len(entries)

    def _process_single_candle(self, entry: MarketEvidenceEntry, candle: ValidatedCandle) -> None:
        """Process an individual validated candle from the evidence ledger."""
        # 1. Maintain in-memory rolling buffer
        if self._recent_candles:
            last_open = self._recent_candles[-1].timestamp_open
            expected_next = last_open + CANDLE_INTERVAL_MS
            if candle.timestamp_open == last_open:
                # Duplicate / same candle; skip buffer append
                pass
            elif candle.timestamp_open == expected_next:
                self._recent_candles.append(candle)
            else:
                # Gap detected; attempt backward window reload from evidence store
                logger.warning(
                    f"Gap detected between buffer tail {last_open} and candle {candle.timestamp_open}. Reloading backward window."
                )
                window = self.evidence_lookup.get_backward_window(
                    origin_ts=candle.timestamp_open,
                    num_bars=min(self.config.max_buffer_bars, 350),
                )
                if window:
                    self._recent_candles = list(window)
                else:
                    self._recent_candles = [candle]
        else:
            self._recent_candles.append(candle)

        # Bound buffer to max lookback
        if len(self._recent_candles) > self.config.max_buffer_bars:
            self._recent_candles = self._recent_candles[-self.config.max_buffer_bars:]

        # Feed adapter update
        cdata = CandleData(
            timestamp_open=candle.timestamp_open,
            timestamp_close=candle.timestamp_close,
            datetime_open=candle.datetime_open_utc,
            datetime_close=candle.datetime_close_utc,
            open=float(candle.open),
            high=float(candle.high),
            low=float(candle.low),
            close=float(candle.close),
            volume=float(candle.volume),
            is_closed=candle.is_closed,
        )
        self.feature_pipeline.add_candle(cdata)

        # 2. Check Warmup
        warmup_ready, buf_count, msg = self.check_warmup_status()
        self.checkpoint.total_warmup_bars_buffered = buf_count
        self.checkpoint.last_processed_entry_index = entry.entry_index
        self.checkpoint.last_processed_candle_timestamp_ms = candle.timestamp_open
        self.checkpoint.total_entries_read += 1

        if not warmup_ready:
            logger.debug(f"Warmup in progress: {msg}")
            return

        # 3. Check Start Boundary: Pre-boundary vs Post-boundary separation
        is_pre_boundary = True
        if self.start_boundary is not None:
            if candle.timestamp_close > self.start_boundary.authorized_start_boundary_ts_ms:
                is_pre_boundary = False

        if is_pre_boundary:
            # Strictly pre-boundary: MUST NOT generate prospective live predictions
            # May be processed as HISTORICAL_WARMUP without emitting live prospective predictions
            logger.debug(
                f"Candle {candle.timestamp_open} is pre-boundary (closed {candle.timestamp_close} <= "
                f"{self.start_boundary.authorized_start_boundary_ts_ms if self.start_boundary else 'NONE'}). "
                "Prospective live scoring prohibited."
            )
            return

        # 4. Post-boundary Candidate Candle -> Prospective Inference
        if self.config.run_mode != "PROSPECTIVE_LIVE":
            # Running in offline / inactive mode; skip live prediction emission
            return

        # STRICT FAIL-CLOSED AUTHORIZATION GATE
        ProspectiveAuthorizationGuard.verify_authorization(
            boundary=ExecutionBoundary.BACKGROUND_WORKER,
            run_mode="PROSPECTIVE_LIVE",
            env=self.config.env,
        )

        # Causal Data Eligibility Check
        CausalDataEligibilityGuard.verify_causal_data_eligibility(
            candles=self._recent_candles[-self.config.min_warmup_bars:],
            current_candle=candle,
            current_time_ms=candle.timestamp_close,
            evidence_store=self.evidence_lookup,
            is_prospective=True,
            min_warmup_bars=self.config.min_warmup_bars,
        )

        # Reconstruct features & evaluate
        recon, quality = self.feature_pipeline.compute_features()
        if recon.status not in ("READY", "READY_PARTIAL_WARMUP") or not quality.eligible_for_prospective_scoring:
            logger.warning(f"Features not ready or not eligible for scoring: {recon.status}")
            return

        if self.inference_runner is None:
            logger.error("Inference runner is unavailable; cannot emit prospective predictions.")
            return

        origin_utc = recon.forecast_origin_utc
        dual_pred = self.inference_runner.predict(
            features=recon.features,
            forecast_origin_utc=origin_utc,
            record_label="PROSPECTIVE_LIVE",
            is_prospective=True,
            context_candles=self._recent_candles[-self.config.min_warmup_bars:],
            current_candle=candle,
            current_time_ms=candle.timestamp_close,
            evidence_store=self.evidence_lookup,
            require_evidence_store=True,
            env=self.config.env,
        )

        # Construct and persist ShadowPredictionEvent records for both branches
        now_iso = datetime.now(timezone.utc).isoformat()
        component_hashes = {
            "bundle_sha256": "7755ddcb369c29825f9205f09e805b2e518526726b4bd5d948787d24c9419ad0",
            "thresholds_sha256": "3979ab8e37377f1d5cb2623c63c20081078ae49c5bcbedcbb860affe3dfd95d9",
            "cal_c_sha256": "d7ce73edf6595c9ef167a8ec69f4e40f102dff2f32d8f265cf3efe4f60ef89ce",
            "cal_e_sha256": "6821136ad71411b8778c481055d4204640d19be0acaedaf8db3cd18ee3b4bf50",
        }

        cycle_events: List[ShadowPredictionEvent] = []
        for branch_name, intervals_dict in [
            ("candidate_c", dual_pred.candidate_c_intervals),
            ("candidate_e", dual_pred.candidate_e_intervals),
        ]:
            for h, fc in intervals_dict.items():
                h_mins = 60 if h == "1h" else (240 if h == "4h" else 1440)
                mat_dt = pd.Timestamp(origin_utc) + pd.Timedelta(minutes=h_mins)
                mat_utc = mat_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                ev = ShadowPredictionEvent(
                    event_id=f"PRED-{origin_utc[:16]}-{branch_name}-{h}",
                    experiment_id=self.config.experiment_id,
                    protocol_version=self.config.protocol_version,
                    candidate_branch=branch_name,
                    forecast_origin_utc=origin_utc,
                    durable_commit_time_utc=now_iso,
                    target_horizon=h,
                    target_maturity_utc=mat_utc,
                    feature_fingerprint=recon.feature_fingerprint,
                    component_hashes=component_hashes,
                    data_quality=asdict(quality),
                    point_prediction=dual_pred.point_forecasts.get(h, 0.0),
                    interval_80={"lower": fc.interval_80[0], "upper": fc.interval_80[1]},
                    interval_95={"lower": fc.interval_95[0], "upper": fc.interval_95[1]},
                    market_state=dual_pred.primary_state,
                    record_label="PROSPECTIVE_LIVE",
                )
                cycle_events.append(ev)

        # Batch append to durable prediction store
        if cycle_events:
            committed = self.prediction_store.append_events_batch(cycle_events)
            self.checkpoint.total_predictions_emitted += len(committed)
            logger.info(
                f"Committed {len(committed)} prospective prediction events for candle {candle.timestamp_open}."
            )

    def resolve_pending_outcomes(self) -> int:
        """Resolve matured pending predictions in memory-bounded pages without silent evictions."""
        total_resolved = 0
        now_ts = (
            self.checkpoint.last_processed_candle_timestamp_ms
            if self.checkpoint.last_processed_candle_timestamp_ms > 0
            else int(time.time() * 1000)
        )

        # Page through all pending predictions in durable index
        for page in self.prediction_store.get_unmatured_events_paged(page_size=self.config.page_size):
            if not page:
                continue

            resolved_outcomes = self.outcome_resolver.resolve_matured_predictions(
                pending_events=page,
                evidence_lookup=self.evidence_lookup,
                current_time_ms=now_ts,
            )

            if resolved_outcomes:
                matured_hashes = {o.prediction_event_hash for o in resolved_outcomes}
                self.prediction_store.prune_matured_events(matured_hashes)
                total_resolved += len(resolved_outcomes)

        self.checkpoint.total_outcomes_resolved += total_resolved
        self.checkpoint.pending_predictions_count = self.prediction_store.get_pending_count()
        self.checkpoint.last_outcome_resolution_timestamp_ms = now_ts
        return total_resolved

    def _save_checkpoint(self) -> None:
        """Atomically persist current checkpoint state."""
        self.checkpoint.pending_predictions_count = self.prediction_store.get_pending_count()
        self.checkpoint.save_atomic(self.checkpoint_file)

    def run_once(self) -> int:
        """Convenience single-pass execution."""
        return self.process_next_batch()

    def run(self) -> None:
        """Continuous execution loop until stop is requested."""
        self._is_running = True
        logger.info(
            f"ProspectiveScoringWorker started in mode={self.config.run_mode}. "
            f"Evidence dir: {self.evidence_dir}, Prospective dir: {self.prospective_dir}"
        )

        while not self._stop_requested:
            try:
                processed = self.process_next_batch()
                if processed == 0:
                    time.sleep(self.config.poll_interval_s)
            except ProspectiveAuthorizationError as auth_err:
                logger.error(f"Scoring worker halted due to authorization failure: {auth_err}")
                break
            except Exception as exc:
                logger.error(f"Unexpected error in scoring worker loop: {exc}", exc_info=True)
                time.sleep(self.config.poll_interval_s)

        self._is_running = False
        logger.info("ProspectiveScoringWorker stopped.")

    def stop(self) -> None:
        """Signal worker to stop gracefully."""
        self._stop_requested = True

    def get_evidence_health_report(self) -> Dict[str, Any]:
        """Perform read-only inspection of evidence health, warmup continuity, and worker stats."""
        with self._lock:
            warmup_ready, count, msg = self.check_warmup_status()
            latest = self.evidence_lookup.get_latest_candle()
            return {
                "run_mode": self.config.run_mode,
                "warmup_ready": warmup_ready,
                "buffered_bars": count,
                "min_warmup_bars": self.config.min_warmup_bars,
                "status_message": msg,
                "last_processed_entry_index": self.checkpoint.last_processed_entry_index,
                "last_processed_candle_timestamp_ms": self.checkpoint.last_processed_candle_timestamp_ms,
                "latest_evidence_candle_timestamp_ms": latest.timestamp_open if latest else None,
                "start_boundary_established": self.start_boundary is not None,
                "authorized_start_boundary_ts_ms": (
                    self.start_boundary.authorized_start_boundary_ts_ms if self.start_boundary else None
                ),
                "total_entries_read": self.checkpoint.total_entries_read,
                "total_predictions_emitted": self.checkpoint.total_predictions_emitted,
                "total_outcomes_resolved": self.checkpoint.total_outcomes_resolved,
                "pending_predictions_count": self.checkpoint.pending_predictions_count,
            }

    def close(self) -> None:
        """Cleanly close underlying stores and connections."""
        if hasattr(self, "evidence_lookup") and self.evidence_lookup:
            try:
                self.evidence_lookup.close()
            except Exception:
                pass
        if hasattr(self, "prediction_store") and self.prediction_store:
            if hasattr(self.prediction_store, "durable_index") and self.prediction_store.durable_index:
                try:
                    self.prediction_store.durable_index.close()
                except Exception:
                    pass
        if hasattr(self, "outcome_resolver") and self.outcome_resolver:
            if hasattr(self.outcome_resolver, "outcome_index") and self.outcome_resolver.outcome_index:
                try:
                    self.outcome_resolver.outcome_index.close()
                except Exception:
                    pass

    def __del__(self) -> None:
        self.close()


# ==============================================================================
# CLI / Container Entrypoint
# ==============================================================================

def main() -> None:
    """Entrypoint for cbe-080-scoring-worker container."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )

    evidence_dir = Path(os.getenv("CBE_RAW_MARKET_DIR", "/app/data/live_capture/raw_market"))
    prospective_dir = Path(os.getenv("CBE_PROSPECTIVE_DIR", "/app/data/prospective"))
    symbol = os.getenv("CBE_SYMBOL", "BTCUSDT")
    interval = os.getenv("CBE_INTERVAL", "5m")
    run_mode = os.getenv("CBE_RUN_MODE", "PASSIVE_OBSERVATION")
    app4_auth = os.getenv("CBE_APPROVAL_4_AUTHORIZED", "false")
    prosp_enabled = os.getenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    trading_disabled = os.getenv("CBE_TRADING_DISABLED", "true")

    logger.info("==================================================================")
    logger.info("CBE-0.8.0 PROSPECTIVE SCORING WORKER: STARTUP")
    logger.info(f"Symbol: {symbol}, Interval: {interval}")
    logger.info(f"Evidence Dir (RO): {evidence_dir}")
    logger.info(f"Prospective Dir (RW): {prospective_dir}")
    logger.info(f"Run Mode: {run_mode}")
    logger.info(f"CBE_APPROVAL_4_AUTHORIZED: {app4_auth}")
    logger.info(f"CBE_PROSPECTIVE_OBSERVATION_ENABLED: {prosp_enabled}")
    logger.info(f"CBE_TRADING_DISABLED: {trading_disabled}")
    logger.info("==================================================================")

    # Fail-closed checks on startup
    if trading_disabled != "true":
        logger.error(f"FATAL: CBE_TRADING_DISABLED is '{trading_disabled}'. Trading is prohibited.")
        sys.exit(1)

    if run_mode == "PROSPECTIVE_LIVE" or prosp_enabled == "true":
        if app4_auth != "true":
            logger.error(
                "FATAL: Prospective live mode requested but APPROVAL 4 IS NOT AUTHORIZED "
                f"(CBE_APPROVAL_4_AUTHORIZED='{app4_auth}'). Refusing startup."
            )
            sys.exit(1)

    if run_mode not in VALID_RUN_MODES:
        logger.error(f"FATAL: Invalid run_mode '{run_mode}'. Must be one of {sorted(VALID_RUN_MODES)}")
        sys.exit(1)

    config = WorkerConfigV080(
        evidence_dir=evidence_dir,
        prospective_dir=prospective_dir,
        symbol=symbol,
        interval=interval,
        run_mode=run_mode,
    )

    worker = ProspectiveScoringWorkerV080(config)
    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Shutdown requested via KeyboardInterrupt.")
        worker.stop()
    finally:
        worker.close()


if __name__ == "__main__":
    main()

