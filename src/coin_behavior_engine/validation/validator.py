"""Data validation pipeline detecting anomalies, gaps, and structural issues."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime, validate_timestamp_plausibility


class IssueSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationIssue:
    severity: IssueSeverity
    issue_type: str
    message: str
    timestamp_open: Optional[int] = None
    datetime_open_utc: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


class DataValidator:
    """Validates cryptocurrency historical market datasets without silent mutative repairs."""

    def __init__(
        self,
        expected_interval_ms: int = 300_000,  # 5 minutes in ms
        max_allowed_consecutive_missing: int = 12,
        strict_ohlc_check: bool = True
    ):
        self.expected_interval_ms = expected_interval_ms
        self.max_allowed_consecutive_missing = max_allowed_consecutive_missing
        self.strict_ohlc_check = strict_ohlc_check

    def validate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run complete validation suite on dataset and return quality report dict."""
        issues: List[ValidationIssue] = []

        if df.empty:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    issue_type="EMPTY_DATASET",
                    message="Dataset contains 0 rows.",
                )
            )
            return self._format_report(df, issues)

        # 1. Check duplicate timestamps
        duplicates = df[df.duplicated(subset=["timestamp_open"], keep=False)]
        if not duplicates.empty:
            dup_count = len(duplicates)
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    issue_type="DUPLICATE_TIMESTAMPS",
                    message=f"Found {dup_count} duplicate timestamp records.",
                    details={"sample_timestamps": duplicates["timestamp_open"].head(5).tolist()},
                )
            )

        # 2. Check chronological ordering
        time_diffs = df["timestamp_open"].diff()
        is_sorted = (time_diffs.dropna() > 0).all()
        if not is_sorted:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    issue_type="NON_MONOTONIC_TIMESTAMPS",
                    message="Dataset is not sorted strictly chronologically.",
                )
            )

        # 3. Check timestamp plausibility & gaps
        min_ts = int(df["timestamp_open"].min())
        max_ts = int(df["timestamp_open"].max())
        if not validate_timestamp_plausibility(min_ts) or not validate_timestamp_plausibility(max_ts):
            for idx, row in df.iterrows():
                ts = int(row["timestamp_open"])
                if not validate_timestamp_plausibility(ts):
                    issues.append(
                        ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            issue_type="IMPOSSIBLE_TIMESTAMP",
                            message=f"Timestamp {ts} is outside plausible range [2000, 2100].",
                            timestamp_open=ts,
                        )
                    )

        # Gap detection
        missing_count = 0
        gap_details = []
        if len(df) > 1:
            step_deltas = df["timestamp_open"].diff().iloc[1:]
            gap_mask = step_deltas > self.expected_interval_ms
            if gap_mask.any():
                gap_indices = df.index[1:][gap_mask]
                for g_idx in gap_indices:
                    prev_ts = int(df.loc[g_idx - 1, "timestamp_open"])
                    curr_ts = int(df.loc[g_idx, "timestamp_open"])
                    gap_ms = curr_ts - prev_ts
                    missed = int(round(gap_ms / self.expected_interval_ms)) - 1
                    missing_count += missed

                    severity = (
                        IssueSeverity.ERROR
                        if missed >= self.max_allowed_consecutive_missing
                        else IssueSeverity.WARNING
                    )
                    gap_details.append({
                        "from_utc": str(to_utc_datetime(prev_ts)),
                        "to_utc": str(to_utc_datetime(curr_ts)),
                        "missed_candles": missed,
                        "gap_duration_minutes": gap_ms / 60_000,
                    })

                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.WARNING if missing_count < 20 else IssueSeverity.ERROR,
                        issue_type="MISSING_CANDLES_GAP",
                        message=f"Total missing candles detected across dataset: {missing_count}",
                        details={"total_gaps": len(gap_details), "top_gaps": gap_details[:10]},
                    )
                )

        # 4. Check OHLC validity
        # high >= low
        inv_hl = df[df["high"] < df["low"]]
        if not inv_hl.empty:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    issue_type="OHLC_HIGH_LESS_THAN_LOW",
                    message=f"Found {len(inv_hl)} records where High < Low.",
                    details={"sample_indices": inv_hl.index[:5].tolist()},
                )
            )

        # open within [low, high]
        out_open = df[(df["open"] < df["low"]) | (df["open"] > df["high"])]
        if not out_open.empty:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    issue_type="OHLC_OPEN_OUT_OF_BOUNDS",
                    message=f"Found {len(out_open)} records where Open is outside [Low, High].",
                    details={"sample_indices": out_open.index[:5].tolist()},
                )
            )

        # close within [low, high]
        out_close = df[(df["close"] < df["low"]) | (df["close"] > df["high"])]
        if not out_close.empty:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    issue_type="OHLC_CLOSE_OUT_OF_BOUNDS",
                    message=f"Found {len(out_close)} records where Close is outside [Low, High].",
                    details={"sample_indices": out_close.index[:5].tolist()},
                )
            )

        # non-positive prices
        neg_prices = df[(df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)]
        if not neg_prices.empty:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    issue_type="NON_POSITIVE_PRICE",
                    message=f"Found {len(neg_prices)} records with zero or negative price.",
                )
            )

        # 5. Check volume and trade counts
        neg_vol = df[(df["volume"] < 0) | (df.get("quote_volume", 0) < 0)]
        if not neg_vol.empty:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    issue_type="NEGATIVE_VOLUME",
                    message=f"Found {len(neg_vol)} records with negative volume.",
                )
            )

        if "trade_count" in df.columns:
            neg_trades = df[df["trade_count"] < 0]
            if not neg_trades.empty:
                issues.append(
                    ValidationIssue(
                        severity=IssueSeverity.CRITICAL,
                        issue_type="NEGATIVE_TRADE_COUNT",
                        message=f"Found {len(neg_trades)} records with negative trade counts.",
                    )
                )

        return self._format_report(df, issues, missing_count)

    def _format_report(
        self,
        df: pd.DataFrame,
        issues: List[ValidationIssue],
        missing_count: int = 0
    ) -> Dict[str, Any]:
        """Format final structured validation dictionary."""
        severity_counts = {sev.value: 0 for sev in IssueSeverity}
        for iss in issues:
            severity_counts[iss.severity.value] += 1

        start_ts = int(df["timestamp_open"].min()) if not df.empty else None
        end_ts = int(df["timestamp_open"].max()) if not df.empty else None

        report = {
            "validation_passed": severity_counts["CRITICAL"] == 0 and severity_counts["ERROR"] == 0,
            "total_candles": len(df),
            "date_range_start_utc": str(to_utc_datetime(start_ts)) if start_ts else None,
            "date_range_end_utc": str(to_utc_datetime(end_ts)) if end_ts else None,
            "missing_candles_count": missing_count,
            "severity_summary": severity_counts,
            "issues": [iss.to_dict() for iss in issues],
            "validated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        }
        return report
