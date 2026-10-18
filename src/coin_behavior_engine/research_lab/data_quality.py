"""Data quality validator, gap detector, and audit manifest generator.

Sprint 11.03: Market Behavior Research Lab.
Ensures zero fabricated data, exact OHLCV relations, timestamp monotonicity, and gap reporting.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from coin_behavior_engine.research_lab.contracts import CandleData


@dataclass
class DataQualityReport:
    """Detailed audit report on historical candle dataset quality."""
    symbol: str
    interval: str
    total_candles: int
    start_timestamp: Optional[int] = None
    end_timestamp: Optional[int] = None
    start_datetime_utc: str = ""
    end_datetime_utc: str = ""
    expected_interval_ms: int = 60_000
    ohlcv_inversions_count: int = 0
    negative_volume_count: int = 0
    non_monotonic_timestamps_count: int = 0
    duplicate_timestamps_count: int = 0
    gaps_count: int = 0
    missing_candles_count: int = 0
    gap_intervals: List[Dict[str, Any]] = field(default_factory=list)
    passed: bool = True
    violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_json(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class DataQualityValidator:
    """Strict validator for historical candle series."""

    INTERVAL_MS_MAP = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000,
    }

    @classmethod
    def validate(
        cls,
        candles: List[CandleData],
        symbol: str = "BTCUSDT",
        interval: str = "1m",
    ) -> DataQualityReport:
        expected_ms = cls.INTERVAL_MS_MAP.get(interval, 60_000)
        report = DataQualityReport(
            symbol=symbol,
            interval=interval,
            total_candles=len(candles),
            expected_interval_ms=expected_ms,
        )

        if not candles:
            report.passed = False
            report.violations.append("Dataset is empty: 0 candles provided.")
            return report

        report.start_timestamp = candles[0].timestamp_open
        report.end_timestamp = candles[-1].timestamp_open
        report.start_datetime_utc = candles[0].datetime_open_utc
        report.end_datetime_utc = candles[-1].datetime_close_utc

        seen_timestamps = set()
        prev_ts = None

        for idx, c in enumerate(candles):
            # 1. OHLCV Invariants
            if c.high < c.low:
                report.ohlcv_inversions_count += 1
                report.violations.append(f"Candle at index {idx} ({c.datetime_open_utc}) high < low: {c.high} < {c.low}")
            if c.high < c.open or c.high < c.close:
                report.ohlcv_inversions_count += 1
                report.violations.append(f"Candle at index {idx} ({c.datetime_open_utc}) high lower than open/close: H={c.high}, O={c.open}, C={c.close}")
            if c.low > c.open or c.low > c.close:
                report.ohlcv_inversions_count += 1
                report.violations.append(f"Candle at index {idx} ({c.datetime_open_utc}) low higher than open/close: L={c.low}, O={c.open}, C={c.close}")
            if c.volume < 0:
                report.negative_volume_count += 1
                report.violations.append(f"Candle at index {idx} ({c.datetime_open_utc}) negative volume: {c.volume}")

            # 2. Timestamp uniqueness
            if c.timestamp_open in seen_timestamps:
                report.duplicate_timestamps_count += 1
                report.violations.append(f"Duplicate timestamp at index {idx}: {c.timestamp_open} ({c.datetime_open_utc})")
            seen_timestamps.add(c.timestamp_open)

            # 3. Monotonic ordering & gap detection
            if prev_ts is not None:
                if c.timestamp_open <= prev_ts:
                    report.non_monotonic_timestamps_count += 1
                    report.violations.append(f"Non-monotonic timestamp at index {idx}: {c.timestamp_open} <= prev {prev_ts}")
                elif c.timestamp_open > prev_ts + expected_ms:
                    missing_count = int((c.timestamp_open - prev_ts) // expected_ms - 1)
                    if missing_count > 0:
                        report.gaps_count += 1
                        report.missing_candles_count += missing_count
                        report.gap_intervals.append({
                            "from_ts": prev_ts,
                            "to_ts": c.timestamp_open,
                            "missing_candles": missing_count,
                            "from_utc": candles[idx - 1].datetime_open_utc,
                            "to_utc": c.datetime_open_utc,
                        })

            prev_ts = c.timestamp_open

        # Determine pass/fail
        if (
            report.ohlcv_inversions_count > 0
            or report.negative_volume_count > 0
            or report.non_monotonic_timestamps_count > 0
            or report.duplicate_timestamps_count > 0
            or report.gaps_count > 0
        ):
            report.passed = False

        return report
