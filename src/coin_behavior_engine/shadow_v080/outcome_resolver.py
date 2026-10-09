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

    def compute_hash(self) -> str:
        d = asdict(self)
        d.pop("outcome_hash", None)
        canonical_bytes = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OutcomeResolverV080:
    """Manages forward outcome evaluation and immutable outcome event storage."""

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.outcomes_file = self.store_dir / "shadow_outcomes.jsonl"
        self._lock = threading.Lock()
        self._seen_predictions: Set[str] = set()
        self._load_existing_outcomes()

    def _load_existing_outcomes(self) -> None:
        if not self.outcomes_file.exists():
            return
        with open(self.outcomes_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    self._seen_predictions.add(data.get("prediction_event_hash", ""))

    def has_outcome(self, prediction_hash: str) -> bool:
        return prediction_hash in self._seen_predictions

    def resolve_matured_predictions(
        self,
        pending_events: List[ShadowPredictionEvent],
        available_candles: List[CandleData],
        current_time_ms: Optional[int] = None,
    ) -> List[ShadowOutcomeEvent]:
        """Inspect pending prediction events and resolve matured outcomes against available candles."""
        if not pending_events or not available_candles:
            return []

        # Map candles by open timestamp
        candle_map = {c.timestamp_open: c for c in available_candles}
        now_ms = current_time_ms if current_time_ms is not None else available_candles[-1].timestamp_close
        resolved = []

        with self._lock:
            for pred in pending_events:
                if pred.record_hash in self._seen_predictions:
                    continue

                # Parse forecast origin open ms
                origin_dt = pd.Timestamp(pred.forecast_origin_utc)
                origin_ms = int(origin_dt.timestamp() * 1000)

                required_bars = HORIZON_BARS.get(pred.target_horizon)
                if required_bars is None:
                    continue

                # Collect future contiguous candles: from origin_ms up to required_bars
                future_candles: List[CandleData] = []
                has_gap = False
                prev_open = origin_ms

                for step in range(required_bars):
                    expected_open = prev_open + (CANDLE_INTERVAL_MS if step > 0 else 0)
                    candle = candle_map.get(expected_open)
                    if candle is None:
                        # Forward window incomplete
                        break
                    future_candles.append(candle)
                    prev_open = expected_open

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

                # Append to outcomes JSONL
                with open(self.outcomes_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(outcome.to_dict(), sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())

                self._seen_predictions.add(pred.record_hash)
                resolved.append(outcome)

        return resolved
