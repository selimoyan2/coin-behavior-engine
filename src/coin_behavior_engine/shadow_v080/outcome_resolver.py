"""Forward Outcome Resolver & Realized Volatility Engine for CBE-0.8.0 Shadow Collector.

Enforces:
- Exact horizon maturity:
  1h = 12 contiguous closed 5m bars.
  4h = 48 contiguous closed 5m bars.
  24h = 288 contiguous closed 5m bars.
- Strict rejection of premature outcome evaluation.
- Continuous forward window validation (rejects gaps > 300s).
- Target unit parity: Daily-scaled standard deviation (sigma_5m * sqrt(288)).
- Append-only outcome logging with references to original prediction hash.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.candidate_v080.feed_adapter import (
    CANDLE_INTERVAL_MS,
    CandleData,
)
from coin_behavior_engine.candidate_v080.inference_pipeline import TARGET_UNITS
from coin_behavior_engine.shadow_v080.evidence_lookup import (
    ForwardWindowResult,
    ForwardWindowStatus,
    PersistentEvidenceLookupV080,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    ShadowPredictionEvent,
)

logger = logging.getLogger("cbe_outcome_resolver")

HORIZON_BARS = {
    "1h": 12,
    "4h": 48,
    "24h": 288,
}


class PrematureOutcomeError(Exception):
    """Raised when an attempt is made to resolve an outcome before full window elapses."""
    pass


class OutcomeGapError(Exception):
    """Raised when forward candle sequence contains discontinuous timestamps."""
    pass


@dataclass
class ShadowOutcomeEvent:
    outcome_id: str
    prediction_event_hash: str
    forecast_origin_utc: str
    target_maturity_utc: str
    target_horizon: str
    candidate_branch: str
    point_forecast: float
    realized_volatility: float
    target_units: str
    actual_bars_evaluated: int
    interval_80_lower: float
    interval_80_upper: float
    interval_95_lower: float
    interval_95_upper: float
    in_interval_80: bool
    in_interval_95: bool
    status: str  # "MATURED_VALID" or "INVALID_GAP"
    evaluated_at_utc: str
    outcome_hash: str = ""
    maturity_candle_hash: str = ""
    maturity_entry_hash: str = ""
    record_label: str = "HISTORICAL_REPLAY"

    def compute_hash(self) -> str:
        d = asdict(self)
        d.pop("outcome_hash", None)
        canonical_bytes = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OutcomeResolverV080:
    """Manages forward outcome evaluation and immutable outcome event storage."""

    def __init__(
        self,
        store_dir: Path,
        evidence_lookup: Optional[PersistentEvidenceLookupV080] = None,
        outcome_index: Optional[Any] = None,
        prediction_index: Optional[Any] = None,
        quarantine_dir: Optional[Path] = None,
        enable_sqlite_index: bool = True,
    ):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.outcomes_file = self.store_dir / "shadow_outcomes.jsonl"
        self.quarantine_dir = Path(quarantine_dir) if quarantine_dir else (self.store_dir / "quarantine")
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index_outcomes.sqlite3"
        self._lock = threading.Lock()
        self._seen_predictions: Set[str] = set()
        self.evidence_lookup = evidence_lookup
        self.prediction_index = prediction_index

        self.enable_sqlite_index = enable_sqlite_index
        self.outcome_index = outcome_index
        if self.outcome_index is None and self.enable_sqlite_index:
            from coin_behavior_engine.shadow_v080.prediction_indexing import DurableOutcomeIndexV080
            self.outcome_index = DurableOutcomeIndexV080(
                store_dir=self.store_dir,
                outcomes_file=self.outcomes_file,
                quarantine_dir=self.quarantine_dir,
            )

        self._load_existing_outcomes()

    def _load_existing_outcomes(self) -> None:
        if self.outcome_index:
            self.outcome_index.rebuild_or_sync_from_journal(self.outcomes_file)
        self._file_offset = self.outcomes_file.stat().st_size if self.outcomes_file.exists() else 0
        if not self.outcomes_file.exists():
            return
        with open(self.outcomes_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        self._seen_predictions.add(data.get("prediction_event_hash", ""))
                    except Exception:
                        pass

    def has_outcome(self, prediction_hash: str) -> bool:
        if prediction_hash in self._seen_predictions:
            return True
        if self.outcome_index:
            return self.outcome_index.has_outcome(prediction_hash)
        return False

    def resolve_matured_predictions(
        self,
        pending_events: List[ShadowPredictionEvent],
        available_candles: Optional[List[CandleData]] = None,
        current_time_ms: Optional[int] = None,
        evidence_lookup: Optional[PersistentEvidenceLookupV080] = None,
        prediction_index: Optional[Any] = None,
    ) -> List[ShadowOutcomeEvent]:
        """Inspect pending prediction events and resolve matured outcomes against persistent evidence or available candles."""
        if not pending_events:
            return []

        active_lookup = evidence_lookup or self.evidence_lookup
        now_ms = current_time_ms if current_time_ms is not None else (
            available_candles[-1].timestamp_close if available_candles else None
        )
        resolved = []

        with self._lock:
            # 1. Primary path: Persistent Evidence Lookup
            if active_lookup is not None:
                resolved_pairs = []
                for pred in pending_events:
                    if pred.record_hash in self._seen_predictions:
                        continue

                    required_bars = HORIZON_BARS.get(pred.target_horizon)
                    if required_bars is None:
                        continue

                    origin_dt = pd.Timestamp(pred.forecast_origin_utc)
                    origin_ms = int(origin_dt.timestamp() * 1000)

                    window_res = active_lookup.get_forward_window(
                        origin_ts=origin_ms,
                        required_bars=required_bars,
                        current_time_ms=now_ms,
                        origin_is_close_time=True,
                    )

                    if window_res.status == ForwardWindowStatus.INCOMPLETE_PENDING:
                        continue

                    if window_res.status == ForwardWindowStatus.COMPLETE:
                        closes = [float(c.close) for c in window_res.candles]
                        if len(closes) > 1:
                            log_rets = np.diff(np.log(closes))
                            sigma_5m = float(np.std(log_rets, ddof=1)) if len(log_rets) > 1 else 0.0
                            realized_vol = float(sigma_5m * np.sqrt(288.0))
                            status = "MATURED_VALID"
                        else:
                            realized_vol = 0.0
                            status = "MATURED_VALID"
                    elif window_res.status == ForwardWindowStatus.INVALID_GAP:
                        realized_vol = float("nan")
                        status = "INVALID_GAP"
                    else:
                        continue

                    in_80 = (
                        not math.isnan(realized_vol)
                        and pred.interval_80["lower"] <= realized_vol <= pred.interval_80["upper"]
                    )
                    in_95 = (
                        not math.isnan(realized_vol)
                        and pred.interval_95["lower"] <= realized_vol <= pred.interval_95["upper"]
                    )

                    eval_utc = pd.Timestamp.now(tz="UTC").isoformat()
                    outcome = ShadowOutcomeEvent(
                        outcome_id=f"OUT-{pred.record_hash[:16]}-{pred.target_horizon}",
                        prediction_event_hash=pred.record_hash,
                        forecast_origin_utc=pred.forecast_origin_utc,
                        target_maturity_utc=pred.target_maturity_utc,
                        target_horizon=pred.target_horizon,
                        candidate_branch=pred.candidate_branch,
                        point_forecast=pred.point_prediction,
                        realized_volatility=realized_vol,
                        target_units=TARGET_UNITS,
                        actual_bars_evaluated=window_res.actual_bars,
                        interval_80_lower=pred.interval_80["lower"],
                        interval_80_upper=pred.interval_80["upper"],
                        interval_95_lower=pred.interval_95["lower"],
                        interval_95_upper=pred.interval_95["upper"],
                        in_interval_80=in_80,
                        in_interval_95=in_95,
                        status=status,
                        evaluated_at_utc=eval_utc,
                        maturity_candle_hash=window_res.maturity_entry.candle_hash if window_res.maturity_entry else (
                            window_res.maturity_candle.canonical_dict().get("close") if window_res.maturity_candle else ""
                        ),
                        maturity_entry_hash=window_res.maturity_entry.entry_hash if window_res.maturity_entry else "",
                        record_label=getattr(pred, "record_label", "HISTORICAL_REPLAY"),
                    )
                    outcome.outcome_hash = outcome.compute_hash()
                    resolved_pairs.append((pred, outcome, status))

                if not resolved_pairs:
                    return []

                combined_bytes = bytearray()
                current_offset = getattr(self, "_file_offset", 0)
                outcomes_with_meta = []
                resolved = []

                for pred, outcome, status in resolved_pairs:
                    line_str = json.dumps(outcome.to_dict(), sort_keys=True) + "\n"
                    line_bytes = line_str.encode("utf-8")
                    outcome_offset = current_offset + len(combined_bytes)
                    combined_bytes.extend(line_bytes)

                    self._seen_predictions.add(pred.record_hash)
                    outcomes_with_meta.append((outcome.to_dict(), outcome_offset, len(self._seen_predictions)))
                    resolved.append(outcome)

                with open(self.outcomes_file, "ab") as f:
                    f.write(combined_bytes)
                    f.flush()
                    os.fsync(f.fileno())
                self._file_offset = current_offset + len(combined_bytes)

                if self.outcome_index:
                    self.outcome_index.record_outcomes_batch(outcomes_with_meta)

                active_pred_index = prediction_index or self.prediction_index
                if active_pred_index:
                    for pred, outcome, status in resolved_pairs:
                        active_pred_index.mark_matured(
                            record_hash=pred.record_hash,
                            outcome_id=outcome.outcome_id,
                            status=status,
                        )

                return resolved

            # 2. Fallback path: In-Memory Candle Buffer
            if not available_candles:
                return []

            # Map candles by open timestamp
            candle_map = {c.timestamp_open: c for c in available_candles}
        now_ms = current_time_ms if current_time_ms is not None else available_candles[-1].timestamp_close
        resolved = []

        # Precompute O(1) index mappings for available candles
        close_to_idx = {c.datetime_close: i for i, c in enumerate(available_candles)}
        open_dt_to_idx = {c.datetime_open: i for i, c in enumerate(available_candles)}
        open_ms_to_idx = {c.timestamp_open: i for i, c in enumerate(available_candles)}
        earliest_c = available_candles[0] if available_candles else None

        with self._lock:
            resolved_pairs = []
            for pred in pending_events:
                if pred.record_hash in self._seen_predictions:
                    continue

                # Parse forecast origin open ms
                origin_dt = pd.Timestamp(pred.forecast_origin_utc)
                origin_ms = int(origin_dt.timestamp() * 1000)

                required_bars = HORIZON_BARS.get(pred.target_horizon)
                if required_bars is None:
                    continue

                # Locate the starting index of future candles
                # Case 1: Origin corresponds to candle close time (standard collector flow) -> forward window starts at next candle
                if pred.forecast_origin_utc in close_to_idx:
                    start_idx = close_to_idx[pred.forecast_origin_utc] + 1
                # Case 2: Origin corresponds to candle open time (open-relative test flows)
                elif pred.forecast_origin_utc in open_dt_to_idx:
                    start_idx = open_dt_to_idx[pred.forecast_origin_utc]
                elif origin_ms in open_ms_to_idx:
                    start_idx = open_ms_to_idx[origin_ms]
                elif earliest_c is not None:
                    # If origin candle was pruned, check if origin occurred right before buffer
                    if abs(earliest_c.timestamp_open - (origin_ms + 1000)) <= 2000 or (
                        earliest_c.timestamp_open > origin_ms - 2000 and earliest_c.timestamp_open <= origin_ms + 2000
                    ):
                        start_idx = 0
                    else:
                        start_idx = None
                else:
                    start_idx = None

                if start_idx is None or start_idx >= len(available_candles):
                    continue

                future_candles = available_candles[start_idx : start_idx + required_bars]
                has_gap = False

                # Check if forward window is complete
                if len(future_candles) < required_bars:
                    # Not yet matured
                    continue

                # Enforce maturity timing: latest future candle close must be <= now_ms
                latest_close_ms = future_candles[-1].timestamp_close
                if latest_close_ms > now_ms:
                    continue  # Premature maturity

                # Verify continuity of future window
                for idx in range(1, len(future_candles)):
                    step_diff = future_candles[idx].timestamp_open - future_candles[idx - 1].timestamp_open
                    if step_diff != CANDLE_INTERVAL_MS:
                        has_gap = True
                        break

                # Compute realized volatility: standard deviation of 5m log returns scaled by sqrt(288)
                closes = [c.close for c in future_candles]
                if len(closes) > 1 and not has_gap:
                    log_rets = np.diff(np.log(closes))
                    sigma_5m = float(np.std(log_rets, ddof=1)) if len(log_rets) > 1 else 0.0
                    realized_vol = float(sigma_5m * np.sqrt(288.0))
                    status = "MATURED_VALID"
                else:
                    realized_vol = float("nan")
                    status = "INVALID_GAP"

                # Check interval coverage
                in_80 = (
                    not math.isnan(realized_vol)
                    and pred.interval_80["lower"] <= realized_vol <= pred.interval_80["upper"]
                )
                in_95 = (
                    not math.isnan(realized_vol)
                    and pred.interval_95["lower"] <= realized_vol <= pred.interval_95["upper"]
                )

                eval_utc = pd.Timestamp.now(tz="UTC").isoformat()
                outcome = ShadowOutcomeEvent(
                    outcome_id=f"OUT-{pred.record_hash[:16]}-{pred.target_horizon}",
                    prediction_event_hash=pred.record_hash,
                    forecast_origin_utc=pred.forecast_origin_utc,
                    target_maturity_utc=pred.target_maturity_utc,
                    target_horizon=pred.target_horizon,
                    candidate_branch=pred.candidate_branch,
                    point_forecast=pred.point_prediction,
                    realized_volatility=realized_vol,
                    target_units=TARGET_UNITS,
                    actual_bars_evaluated=len(future_candles),
                    interval_80_lower=pred.interval_80["lower"],
                    interval_80_upper=pred.interval_80["upper"],
                    interval_95_lower=pred.interval_95["lower"],
                    interval_95_upper=pred.interval_95["upper"],
                    in_interval_80=in_80,
                    in_interval_95=in_95,
                    status=status,
                    evaluated_at_utc=eval_utc,
                )
                outcome.outcome_hash = outcome.compute_hash()

                resolved_pairs.append((pred, outcome, status))

            if not resolved_pairs:
                return []

            combined_bytes = bytearray()
            current_offset = getattr(self, "_file_offset", 0)
            outcomes_with_meta = []
            resolved = []

            for pred, outcome, status in resolved_pairs:
                line_str = json.dumps(outcome.to_dict(), sort_keys=True) + "\n"
                line_bytes = line_str.encode("utf-8")
                outcome_offset = current_offset + len(combined_bytes)
                combined_bytes.extend(line_bytes)

                self._seen_predictions.add(pred.record_hash)
                outcomes_with_meta.append((outcome.to_dict(), outcome_offset, len(self._seen_predictions)))
                resolved.append(outcome)

            with open(self.outcomes_file, "ab") as f:
                f.write(combined_bytes)
                f.flush()
                os.fsync(f.fileno())
            self._file_offset = current_offset + len(combined_bytes)

            if self.outcome_index:
                self.outcome_index.record_outcomes_batch(outcomes_with_meta)

            active_pred_index = prediction_index or self.prediction_index
            if active_pred_index:
                for pred, outcome, status in resolved_pairs:
                    active_pred_index.mark_matured(
                        record_hash=pred.record_hash,
                        outcome_id=outcome.outcome_id,
                        status=status,
                    )

            return resolved
