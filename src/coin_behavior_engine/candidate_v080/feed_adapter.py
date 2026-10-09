"""CBE-0.8.0 Isolated Causal Feed Adapter & Feature Reconstruction Engine.

Converts closed BTCUSDT spot 5-minute OHLCV candles into canonical features
for the frozen CBE-0.8.0 candidate model with strict:
1. Timestamp causality (latest_candle_close <= forecast_origin).
2. Interval continuity and closed-candle validation.
3. Zero future data access or lookahead.
4. Exact bit-for-bit mathematical parity against training-time definitions.
5. Fail-closed error handling and bounded rolling buffer management.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


CANDLE_INTERVAL_MS = 300_000  # 5 minutes in milliseconds
MIN_WARMUP_BARS = 72          # 6 hours minimum for rolling window with min_periods=72
FULL_WARMUP_BARS = 288        # 24 hours of 5-minute bars
BUFFER_CAPACITY = 350         # Bounded rolling window buffer (stores up to ~29 hours)


class FeedAdapterError(Exception):
    """Raised when feed adapter encounters an unrecoverable input or validation error."""
    pass


@dataclass
class CandleData:
    timestamp_open: int
    timestamp_close: int
    datetime_open: str
    datetime_close: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = True
    receipt_timestamp_utc: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CandleData":
        t_open = int(d.get("timestamp_open", d.get("open_time_ms", 0)))
        t_close = int(d.get("timestamp_close", d.get("close_time_ms", t_open + CANDLE_INTERVAL_MS - 1)))

        dt_open = d.get("datetime_open")
        if not dt_open:
            dt_open = datetime.fromtimestamp(t_open / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        dt_close = d.get("datetime_close")
        if not dt_close:
            dt_close = datetime.fromtimestamp(t_close / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return cls(
            timestamp_open=t_open,
            timestamp_close=t_close,
            datetime_open=dt_open,
            datetime_close=dt_close,
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d["volume"]),
            is_closed=bool(d.get("is_closed", True)),
            receipt_timestamp_utc=d.get("receipt_timestamp_utc"),
        )


@dataclass
class ReconstructedFeatures:
    features: Dict[str, float]
    forecast_origin_utc: str
    latest_source_candle_close_utc: str
    earliest_source_candle_utc: str
    lookback_bars: int
    status: str  # 'READY', 'WARMING_UP', 'SOURCE_GAP', 'INVALID_CANDLE', 'FEATURE_UNAVAILABLE'
    feature_fingerprint: str
    receipt_timestamp_utc: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeedAdapterV080:
    """Isolated local feed adapter and feature reconstruction pipeline for CBE-0.8.0."""

    CANONICAL_FEATURES = [
        "volatility_realized_24h",
        "volatility_compression_ratio",
        "volume_zscore_24h",
    ]

    def __init__(self, buffer_capacity: int = BUFFER_CAPACITY):
        self.buffer_capacity = buffer_capacity
        self.candles: List[CandleData] = []
        self.last_status: str = "WARMING_UP"

    @property
    def buffer(self) -> List[CandleData]:
        """Alias for self.candles for buffer-style access."""
        return self.candles

    def ingest_candle(self, candle: CandleData) -> ReconstructedFeatures:
        """Convenience method: add candle and immediately return reconstructed features."""
        ok, reason = self.add_candle(candle)
        if not ok and self.last_status in ["SOURCE_GAP", "INVALID_CANDLE"]:
            raise FeedAdapterError(reason)
        return self.reconstruct_features()

    def reset(self) -> None:
        """Clear rolling buffer."""
        self.candles.clear()
        self.last_status = "WARMING_UP"

    def validate_candle(self, candle: CandleData) -> Tuple[bool, str]:
        """Validate candle geometry, monotonicity, and finite numeric values."""
        # 1. Closed status check
        if not candle.is_closed:
            return False, "Candle is not closed"

        # 2. Finite positive price and volume check
        for field_name in ["open", "high", "low", "close", "volume"]:
            val = getattr(candle, field_name)
            if not math.isfinite(val):
                return False, f"Non-finite value in candle field '{field_name}': {val}"
            if val < 0.0:
                return False, f"Negative value in candle field '{field_name}': {val}"

        if candle.close <= 0.0 or candle.open <= 0.0:
            return False, "Price fields open and close must be strictly positive"

        # 3. OHLC relationship checks
        if candle.high < candle.low:
            return False, f"Candle high ({candle.high}) < low ({candle.low})"
        if candle.high < max(candle.open, candle.close):
            return False, f"Candle high ({candle.high}) < max(open, close)"
        if candle.low > min(candle.open, candle.close):
            return False, f"Candle low ({candle.low}) > min(open, close)"

        # 4. Timestamp validity check
        if candle.timestamp_close <= candle.timestamp_open:
            return False, f"Close timestamp ({candle.timestamp_close}) <= open timestamp ({candle.timestamp_open})"

        return True, "VALID"

    def add_candle(self, candle_input: Union[Dict[str, Any], CandleData]) -> Tuple[bool, str]:
        """Ingest a new candle into the rolling buffer with continuity verification."""
        if isinstance(candle_input, dict):
            try:
                candle = CandleData.from_dict(candle_input)
            except Exception as e:
                self.last_status = "INVALID_CANDLE"
                return False, f"Failed to parse candle dictionary: {e}"
        elif isinstance(candle_input, CandleData):
            candle = candle_input
        else:
            self.last_status = "INVALID_CANDLE"
            return False, f"Unsupported candle input type: {type(candle_input)}"

        # Validate geometry
        is_valid, reason = self.validate_candle(candle)
        if not is_valid:
            self.last_status = "INVALID_CANDLE"
            return False, reason

        if self.candles:
            prev = self.candles[-1]

            # Duplicate check
            if candle.timestamp_open == prev.timestamp_open:
                # Check if identical (idempotent duplicate)
                if (
                    candle.open == prev.open
                    and candle.high == prev.high
                    and candle.low == prev.low
                    and candle.close == prev.close
                    and candle.volume == prev.volume
                ):
                    return True, "IDEMPOTENT_DUPLICATE_IGNORED"
                else:
                    self.last_status = "INVALID_CANDLE"
                    return False, f"Conflicting candle received for timestamp {candle.timestamp_open}"

            # Out of order check
            if candle.timestamp_open < prev.timestamp_open:
                self.last_status = "INVALID_CANDLE"
                return False, f"Out of order candle: {candle.timestamp_open} < {prev.timestamp_open}"

            # Gap check
            expected_next_open = prev.timestamp_open + CANDLE_INTERVAL_MS
            if candle.timestamp_open > expected_next_open:
                gap_bars = (candle.timestamp_open - prev.timestamp_open) // CANDLE_INTERVAL_MS
                self.last_status = "SOURCE_GAP"
                # Keep new candle but flag gap
                self.candles.append(candle)
                if len(self.candles) > self.buffer_capacity:
                    self.candles.pop(0)
                return False, f"Source gap detected: missing {gap_bars - 1} bars between {prev.datetime_open} and {candle.datetime_open}"

        # Append valid candle
        self.candles.append(candle)
        if len(self.candles) > self.buffer_capacity:
            self.candles.pop(0)

        return True, "SUCCESS"

    def reconstruct_features(self) -> ReconstructedFeatures:
        """Reconstruct the canonical 3-feature vector causally from the rolling candle buffer."""
        n_bars = len(self.candles)

        if n_bars == 0:
            return ReconstructedFeatures(
                features={},
                forecast_origin_utc="",
                latest_source_candle_close_utc="",
                earliest_source_candle_utc="",
                lookback_bars=0,
                status="FEATURE_UNAVAILABLE",
                feature_fingerprint="",
                diagnostics={"error": "Buffer is empty"},
            )

        latest_candle = self.candles[-1]
        earliest_candle = self.candles[0]
        forecast_origin = str(latest_candle.datetime_close)
        latest_close_utc = str(latest_candle.datetime_close)
        earliest_open_utc = str(earliest_candle.datetime_open)
        receipt_ts = str(latest_candle.receipt_timestamp_utc) if latest_candle.receipt_timestamp_utc else None

        if n_bars < MIN_WARMUP_BARS:
            self.last_status = "WARMING_UP"
            return ReconstructedFeatures(
                features={},
                forecast_origin_utc=forecast_origin,
                latest_source_candle_close_utc=latest_close_utc,
                earliest_source_candle_utc=earliest_open_utc,
                lookback_bars=n_bars,
                status="WARMING_UP",
                feature_fingerprint="",
                receipt_timestamp_utc=receipt_ts,
                diagnostics={"bars_available": n_bars, "min_required": MIN_WARMUP_BARS},
            )

        # Extract numpy arrays from buffer
        closes = np.array([c.close for c in self.candles], dtype=np.float64)
        volumes = np.array([c.volume for c in self.candles], dtype=np.float64)

        # 1. Log returns
        # r_t = log(close_t / close_{t-1})
        log_rets = np.log(closes[1:] / closes[:-1])
        # Pad with 0.0 at the beginning to match length of candles
        log_rets = np.concatenate([[0.0], log_rets])

        # 2. Volatility Realized 24h (w=288, min_periods=72)
        # Sample standard deviation ddof=1
        w_vol24 = min(n_bars, 288)
        slice_vol24 = log_rets[-w_vol24:]
        vol_24h = float(np.std(slice_vol24, ddof=1)) if len(slice_vol24) >= 72 else 0.0

        # 3. Volatility Realized 1h (w=12, min_periods=3)
        w_vol1 = min(n_bars, 12)
        slice_vol1 = log_rets[-w_vol1:]
        vol_1h = float(np.std(slice_vol1, ddof=1)) if len(slice_vol1) >= 3 else 0.0

        # 4. Volatility Compression Ratio (vol_1h / vol_24h)
        comp_ratio = float(vol_1h / vol_24h) if vol_24h > 1e-12 else 1.0

        # 5. Volume Z-Score 24h (w=288, min_periods=72, clip=[-5.0, 15.0])
        w_vlm = min(n_bars, 288)
        slice_vlm = volumes[-w_vlm:]
        v_mean = float(np.mean(slice_vlm))
        v_std = float(np.std(slice_vlm, ddof=1)) if len(slice_vlm) > 1 else 0.0
        cur_vol = float(volumes[-1])

        if v_std > 1e-12:
            vol_z = float((cur_vol - v_mean) / v_std)
        else:
            vol_z = 0.0
        vol_z_clipped = float(np.clip(vol_z, -5.0, 15.0))

        features_dict = {
            "volatility_realized_24h": vol_24h,
            "volatility_compression_ratio": comp_ratio,
            "volume_zscore_24h": vol_z_clipped,
        }

        # Compute deterministic feature fingerprint
        fingerprint_payload = {
            "forecast_origin": forecast_origin,
            "features": {k: round(v, 9) for k, v in features_dict.items()},
        }
        fp_str = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
        fp_hash = hashlib.sha256(fp_str.encode("utf-8")).hexdigest()

        status = "READY" if n_bars >= FULL_WARMUP_BARS else "READY_PARTIAL_WARMUP"
        self.last_status = status

        return ReconstructedFeatures(
            features=features_dict,
            forecast_origin_utc=forecast_origin,
            latest_source_candle_close_utc=latest_close_utc,
            earliest_source_candle_utc=earliest_open_utc,
            lookback_bars=n_bars,
            status=status,
            feature_fingerprint=fp_hash,
            receipt_timestamp_utc=receipt_ts,
            diagnostics={
                "vol_1h_unscaled": vol_1h,
                "vol_24h_unscaled": vol_24h,
                "volume_mean": v_mean,
                "volume_std": v_std,
                "raw_vol_zscore": vol_z,
            },
        )
