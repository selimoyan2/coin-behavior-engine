"""Historical candle validation for offline research.

Enforces strict time-series continuity, OHLC invariants, gap detection,
and exchange operating start boundaries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from coin_behavior_engine.research.historical.dataset_contract import (
    BINANCE_SPOT_BTCUSDT_GENESIS_MS,
)

EXPECTED_INTERVAL_MS = 300_000  # 5 minutes


@dataclass(frozen=True)
class HistoricalValidationReport:
    """Detailed report produced by HistoricalCandleValidator."""

    is_valid: bool
    total_candles: int
    valid_candles: int
    gap_count: int
    missing_candle_count: int
    gaps: list[dict[str, Any]] = field(default_factory=list)
    duplicate_count: int = 0
    duplicate_timestamps: list[int] = field(default_factory=list)
    boundary_violation_count: int = 0
    boundary_violations: list[dict[str, Any]] = field(default_factory=list)
    start_timestamp_ms: int | None = None
    end_timestamp_ms: int | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HistoricalCandleValidator:
    """Validates historical 5m OHLCV candle streams for offline research."""

    def __init__(
        self,
        expected_interval_ms: int = EXPECTED_INTERVAL_MS,
        genesis_timestamp_ms: int = BINANCE_SPOT_BTCUSDT_GENESIS_MS,
        max_reported_violations: int = 100,
    ) -> None:
        self.expected_interval_ms = expected_interval_ms
        self.genesis_timestamp_ms = genesis_timestamp_ms
        self.max_reported_violations = max_reported_violations

    def validate(
        self,
        candles: Iterable[Mapping[str, Any]],
    ) -> HistoricalValidationReport:
        """Validate an iterable of candle dictionaries/mappings."""
        total = 0
        valid = 0
        gaps: list[dict[str, Any]] = []
        missing_candle_count = 0
        duplicate_timestamps: list[int] = []
        boundary_violations: list[dict[str, Any]] = []
        errors: list[str] = []

        prev_ts: int | None = None
        start_ts: int | None = None
        end_ts: int | None = None

        for idx, candle in enumerate(candles):
            total += 1
            has_violation = False

            # Extract fields
            try:
                open_ts = int(candle.get("open_time", candle.get("timestamp_ms", candle.get("timestamp", -1))))
                op = float(candle["open"])
                hi = float(candle["high"])
                lo = float(candle["low"])
                cl = float(candle["close"])
                vol = float(candle.get("volume", 0.0))
            except (KeyError, TypeError, ValueError) as exc:
                if len(boundary_violations) < self.max_reported_violations:
                    boundary_violations.append({
                        "index": idx,
                        "error": f"Invalid or missing data types: {exc}",
                        "candle": dict(candle),
                    })
                has_violation = True
                continue

            if start_ts is None:
                start_ts = open_ts
            end_ts = open_ts

            # Genesis check
            if open_ts < self.genesis_timestamp_ms:
                has_violation = True
                if len(boundary_violations) < self.max_reported_violations:
                    boundary_violations.append({
                        "index": idx,
                        "timestamp_ms": open_ts,
                        "error": f"Candle timestamp {open_ts} is prior to Binance genesis {self.genesis_timestamp_ms}",
                    })

            # Duplicate / Monotonicity check
            if prev_ts is not None:
                if open_ts == prev_ts:
                    duplicate_timestamps.append(open_ts)
                    has_violation = True
                    if len(boundary_violations) < self.max_reported_violations:
                        boundary_violations.append({
                            "index": idx,
                            "timestamp_ms": open_ts,
                            "error": f"Duplicate timestamp detected at {open_ts}",
                        })
                elif open_ts < prev_ts:
                    has_violation = True
                    if len(boundary_violations) < self.max_reported_violations:
                        boundary_violations.append({
                            "index": idx,
                            "timestamp_ms": open_ts,
                            "prev_timestamp_ms": prev_ts,
                            "error": f"Non-monotonic timestamp: current={open_ts} < prev={prev_ts}",
                        })
                else:
                    # Check gap
                    diff = open_ts - prev_ts
                    if diff > self.expected_interval_ms:
                        missing_bars = (diff // self.expected_interval_ms) - 1
                        missing_candle_count += missing_bars
                        gaps.append({
                            "from_ts": prev_ts,
                            "to_ts": open_ts,
                            "diff_ms": diff,
                            "missing_bars": missing_bars,
                        })

            # OHLC invariants
            # 1. Non-negative prices & volumes
            if lo < 0 or hi < 0 or op < 0 or cl < 0 or vol < 0:
                has_violation = True
                if len(boundary_violations) < self.max_reported_violations:
                    boundary_violations.append({
                        "index": idx,
                        "timestamp_ms": open_ts,
                        "error": f"Negative value in OHLCV: O={op}, H={hi}, L={lo}, C={cl}, V={vol}",
                    })

            # 2. High >= max(open, close)
            if hi < max(op, cl):
                has_violation = True
                if len(boundary_violations) < self.max_reported_violations:
                    boundary_violations.append({
                        "index": idx,
                        "timestamp_ms": open_ts,
                        "error": f"High {hi} is less than max(open={op}, close={cl})",
                    })

            # 3. Low <= min(open, close)
            if lo > min(op, cl):
                has_violation = True
                if len(boundary_violations) < self.max_reported_violations:
                    boundary_violations.append({
                        "index": idx,
                        "timestamp_ms": open_ts,
                        "error": f"Low {lo} is greater than min(open={op}, close={cl})",
                    })

            # 4. High >= Low
            if hi < lo:
                has_violation = True
                if len(boundary_violations) < self.max_reported_violations:
                    boundary_violations.append({
                        "index": idx,
                        "timestamp_ms": open_ts,
                        "error": f"High {hi} is less than Low {lo}",
                    })

            # 5. Bar closure check (if close_time present)
            if "close_time" in candle and candle["close_time"] is not None:
                try:
                    close_ts = int(candle["close_time"])
                    expected_close = open_ts + self.expected_interval_ms - 1
                    # Some sources use +300000 instead of +299999
                    if abs(close_ts - expected_close) > 1:
                        has_violation = True
                        if len(boundary_violations) < self.max_reported_violations:
                            boundary_violations.append({
                                "index": idx,
                                "timestamp_ms": open_ts,
                                "error": f"Unexpected close_time {close_ts}, expected {expected_close}",
                            })
                except (ValueError, TypeError):
                    pass

            prev_ts = open_ts
            if not has_violation:
                valid += 1

        if total == 0:
            errors.append("Dataset is empty")
        if gaps:
            errors.append(f"Detected {len(gaps)} gap(s) with {missing_candle_count} missing bars")
        if duplicate_timestamps:
            errors.append(f"Detected {len(duplicate_timestamps)} duplicate timestamp(s)")
        if boundary_violations:
            errors.append(f"Detected {len(boundary_violations)} boundary/data violation(s)")

        is_valid = (
            total > 0
            and len(gaps) == 0
            and len(duplicate_timestamps) == 0
            and len(boundary_violations) == 0
        )

        return HistoricalValidationReport(
            is_valid=is_valid,
            total_candles=total,
            valid_candles=valid,
            gap_count=len(gaps),
            missing_candle_count=missing_candle_count,
            gaps=gaps,
            duplicate_count=len(duplicate_timestamps),
            duplicate_timestamps=duplicate_timestamps,
            boundary_violation_count=len(boundary_violations),
            boundary_violations=boundary_violations,
            start_timestamp_ms=start_ts,
            end_timestamp_ms=end_ts,
            errors=errors,
        )
