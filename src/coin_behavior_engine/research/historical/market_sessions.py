"""Market sessions and opening range tracking with timezone and DST awareness.

Covers:
- Asian session: 00:00 - 08:00 UTC
- London session: 08:00 - 16:30 local London time (Europe/London, DST-aware)
- New York session: 09:30 - 16:00 local New York time (America/New_York, DST-aware)
- London / New York overlap
- Full 24h crypto coverage (including OFF_SESSION)
- Candidate Opening Range Windows: 5m, 10m, 15m, 30m, 60m
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Mapping, Sequence
import zoneinfo

LONDON_TZ = zoneinfo.ZoneInfo("Europe/London")
NEW_YORK_TZ = zoneinfo.ZoneInfo("America/New_York")
UTC_TZ = timezone.utc


class MarketSession(str, Enum):
    """Trading session classifications."""

    ASIAN = "ASIAN"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    OFF_SESSION = "OFF_SESSION"


@dataclass(frozen=True)
class OpeningRangeWindow:
    """Opening range for a specific session and window size."""

    session: str
    window_minutes: int
    session_start_ms: int
    cutoff_ms: int
    high: float
    low: float
    is_finalized: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketSessionConfig:
    """Session configuration and active states for a given timestamp."""

    timestamp_ms: int
    dt_utc: datetime
    active_sessions: list[str]
    primary_session: str
    is_london_active: bool
    is_ny_active: bool
    is_asian_active: bool
    is_overlap: bool
    minute_of_day_utc: int

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["dt_utc"] = self.dt_utc.isoformat()
        return d


class MarketSessionDetector:
    """Detects market sessions and tracks candidate opening ranges."""

    SUPPORTED_OR_WINDOWS = (5, 10, 15, 30, 60)

    def __init__(self) -> None:
        self.london_start = time(8, 0)
        self.london_end = time(16, 30)
        self.ny_start = time(9, 30)
        self.ny_end = time(16, 0)
        self.asian_start = time(0, 0)
        self.asian_end = time(8, 0)

    def detect_session(self, timestamp_ms: int) -> MarketSessionConfig:
        """Classify sessions active at the given millisecond timestamp."""
        dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=UTC_TZ)
        time_utc = dt_utc.time()

        # Asian: 00:00 - 08:00 UTC
        is_asian = self.asian_start <= time_utc < self.asian_end

        # London: 08:00 - 16:30 Europe/London
        dt_london = dt_utc.astimezone(LONDON_TZ)
        time_london = dt_london.time()
        is_london = self.london_start <= time_london < self.london_end

        # New York: 09:30 - 16:00 America/New_York
        dt_ny = dt_utc.astimezone(NEW_YORK_TZ)
        time_ny = dt_ny.time()
        is_ny = self.ny_start <= time_ny < self.ny_end

        is_overlap = is_london and is_ny

        active: list[str] = []
        if is_overlap:
            active.append(MarketSession.LONDON_NY_OVERLAP.value)
        if is_london:
            active.append(MarketSession.LONDON.value)
        if is_ny:
            active.append(MarketSession.NEW_YORK.value)
        if is_asian:
            active.append(MarketSession.ASIAN.value)
        if not active:
            active.append(MarketSession.OFF_SESSION.value)

        # Primary session ranking: Overlap > NY > London > Asian > Off
        if is_overlap:
            primary = MarketSession.LONDON_NY_OVERLAP.value
        elif is_ny:
            primary = MarketSession.NEW_YORK.value
        elif is_london:
            primary = MarketSession.LONDON.value
        elif is_asian:
            primary = MarketSession.ASIAN.value
        else:
            primary = MarketSession.OFF_SESSION.value

        minute_of_day = dt_utc.hour * 60 + dt_utc.minute

        return MarketSessionConfig(
            timestamp_ms=timestamp_ms,
            dt_utc=dt_utc,
            active_sessions=active,
            primary_session=primary,
            is_london_active=is_london,
            is_ny_active=is_ny,
            is_asian_active=is_asian,
            is_overlap=is_overlap,
            minute_of_day_utc=minute_of_day,
        )

    def compute_opening_ranges(
        self,
        candles: Sequence[Mapping[str, Any]],
        window_minutes: int = 15,
        target_session: str = MarketSession.NEW_YORK.value,
    ) -> list[OpeningRangeWindow]:
        """Compute opening ranges for a specified session across all days in candle series."""
        if window_minutes not in self.SUPPORTED_OR_WINDOWS:
            raise ValueError(f"Unsupported window_minutes: {window_minutes}. Choose from {self.SUPPORTED_OR_WINDOWS}")

        window_ms = window_minutes * 60 * 1000
        ranges: list[OpeningRangeWindow] = []

        current_session_start_ms: int | None = None
        current_hi = -float("inf")
        current_lo = float("inf")
        was_active = False

        for c in candles:
            ts = int(c.get("open_time", c.get("timestamp_ms", c.get("timestamp", 0))))
            hi = float(c["high"])
            lo = float(c["low"])

            cfg = self.detect_session(ts)
            is_target_active = target_session in cfg.active_sessions

            # Session transition: inactive -> active starts new session window
            if is_target_active and not was_active:
                current_session_start_ms = ts
                current_hi = hi
                current_lo = lo

            elif is_target_active and current_session_start_ms is not None:
                # Inside session
                elapsed_ms = ts - current_session_start_ms
                if elapsed_ms < window_ms:
                    if hi > current_hi:
                        current_hi = hi
                    if lo < current_lo:
                        current_lo = lo

                if elapsed_ms + 300_000 >= window_ms:  # Bar ends at or after window cutoff
                    # Finalize opening range for this session day if not already recorded
                    cutoff_ms = current_session_start_ms + window_ms
                    # Check if already added for this session_start
                    if not any(r.session_start_ms == current_session_start_ms for r in ranges):
                        ranges.append(
                            OpeningRangeWindow(
                                session=target_session,
                                window_minutes=window_minutes,
                                session_start_ms=current_session_start_ms,
                                cutoff_ms=cutoff_ms,
                                high=current_hi,
                                low=current_lo,
                                is_finalized=True,
                            )
                        )

            elif not is_target_active and was_active:
                # Session ended
                current_session_start_ms = None

            was_active = is_target_active

        return ranges
