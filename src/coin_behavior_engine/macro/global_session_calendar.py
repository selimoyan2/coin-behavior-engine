"""Global Market Session Calendar & Opening Relative Horizon Engine.

Sprint 11.17: Global Market Session Intelligence.
Implements authoritative, timezone-aware, holiday-aware session calendars for:
- Tokyo Stock Exchange (TSE: Asia/Tokyo, 09:00 JST open)
- Hong Kong Stock Exchange (HKEX: Asia/Hong_Kong, 09:30 HKT open)
- London Stock Exchange (LSE: Europe/London, 08:00 local open, GMT/BST DST shifts)
- New York Stock Exchange / Nasdaq (NYSE: America/New_York, 09:30 local open, EST/EDT DST shifts)

All internal representations use UTC timestamps.
Calculates opening-relative windows:
- Pre-open: 60, 30, and 10 minutes
- Post-open: 5, 10, 15, 30, and 60 minutes
- Subsequent horizons: 1h, 4h, 12h, and 24h
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SessionOpenEvent:
    exchange: str
    open_time_utc: pd.Timestamp
    date_local: datetime.date
    local_time: str
    is_holiday: bool
    is_early_close: bool


class GlobalSessionCalendar:
    """Accurate, historical timezone-aware session calendar for global equities."""

    TZ_TOKYO = ZoneInfo("Asia/Tokyo")
    TZ_HONG_KONG = ZoneInfo("Asia/Hong_Kong")
    TZ_LONDON = ZoneInfo("Europe/London")
    TZ_NEW_YORK = ZoneInfo("America/New_York")
    TZ_UTC = ZoneInfo("UTC")

    EXCHANGES = ["TSE", "HKEX", "LSE", "NYSE"]

    def __init__(self):
        self._init_holidays()

    def _init_holidays(self) -> None:
        """Initialize official exchange holidays for 2025 and 2026."""
        # 1. NYSE Holidays
        self.nyse_holidays: Set[datetime.date] = {
            # 2025
            datetime.date(2025, 1, 1),   # New Year's Day
            datetime.date(2025, 1, 20),  # MLK Day
            datetime.date(2025, 2, 17),  # Washington's Birthday
            datetime.date(2025, 4, 18),  # Good Friday
            datetime.date(2025, 5, 26),  # Memorial Day
            datetime.date(2025, 6, 19),  # Juneteenth
            datetime.date(2025, 7, 4),   # Independence Day
            datetime.date(2025, 9, 1),   # Labor Day
            datetime.date(2025, 11, 27), # Thanksgiving Day
            datetime.date(2025, 12, 25), # Christmas Day
            # 2026
            datetime.date(2026, 1, 1),   # New Year's Day
            datetime.date(2026, 1, 19),  # MLK Day
            datetime.date(2026, 2, 16),  # Washington's Birthday
            datetime.date(2026, 4, 3),   # Good Friday
            datetime.date(2026, 5, 25),  # Memorial Day
            datetime.date(2026, 6, 19),  # Juneteenth
            datetime.date(2026, 7, 3),   # Independence Day (observed)
            datetime.date(2026, 9, 7),   # Labor Day
            datetime.date(2026, 11, 26), # Thanksgiving Day
            datetime.date(2026, 12, 25), # Christmas Day
        }

        self.nyse_early_closes: Set[datetime.date] = {
            datetime.date(2025, 7, 3),   # Day before July 4
            datetime.date(2025, 11, 28), # Black Friday
            datetime.date(2025, 12, 24), # Christmas Eve
            datetime.date(2026, 11, 27), # Black Friday
            datetime.date(2026, 12, 24), # Christmas Eve
        }

        # 2. LSE Holidays
        self.lse_holidays: Set[datetime.date] = {
            # 2025
            datetime.date(2025, 1, 1),   # New Year's Day
            datetime.date(2025, 4, 18),  # Good Friday
            datetime.date(2025, 4, 21),  # Easter Monday
            datetime.date(2025, 5, 5),   # Early May Bank Holiday
            datetime.date(2025, 5, 26),  # Spring Bank Holiday
            datetime.date(2025, 8, 25),  # Summer Bank Holiday
            datetime.date(2025, 12, 25), # Christmas Day
            datetime.date(2025, 12, 26), # Boxing Day
            # 2026
            datetime.date(2026, 1, 1),   # New Year's Day
            datetime.date(2026, 4, 3),   # Good Friday
            datetime.date(2026, 4, 6),   # Easter Monday
            datetime.date(2026, 5, 4),   # Early May Bank Holiday
            datetime.date(2026, 5, 25),  # Spring Bank Holiday
            datetime.date(2026, 8, 31),  # Summer Bank Holiday
            datetime.date(2026, 12, 25), # Christmas Day
            datetime.date(2026, 12, 28), # Boxing Day (substitute)
        }

        self.lse_early_closes: Set[datetime.date] = {
            datetime.date(2025, 12, 24),
            datetime.date(2025, 12, 31),
            datetime.date(2026, 12, 24),
            datetime.date(2026, 12, 31),
        }

        # 3. TSE (Tokyo) Holidays
        self.tse_holidays: Set[datetime.date] = {
            # 2025
            datetime.date(2025, 1, 1),
            datetime.date(2025, 1, 2),
            datetime.date(2025, 1, 3),
            datetime.date(2025, 1, 13),
            datetime.date(2025, 2, 11),
            datetime.date(2025, 2, 24),
            datetime.date(2025, 3, 20),
            datetime.date(2025, 4, 29),
            datetime.date(2025, 5, 5),
            datetime.date(2025, 5, 6),
            datetime.date(2025, 7, 21),
            datetime.date(2025, 8, 11),
            datetime.date(2025, 9, 15),
            datetime.date(2025, 9, 23),
            datetime.date(2025, 10, 13),
            datetime.date(2025, 11, 3),
            datetime.date(2025, 11, 24),
            datetime.date(2025, 12, 31),
            # 2026
            datetime.date(2026, 1, 1),
            datetime.date(2026, 1, 2),
            datetime.date(2026, 1, 3),
            datetime.date(2026, 1, 12),
            datetime.date(2026, 2, 11),
            datetime.date(2026, 2, 23),
            datetime.date(2026, 3, 20),
            datetime.date(2026, 4, 29),
            datetime.date(2026, 5, 4),
            datetime.date(2026, 5, 5),
            datetime.date(2026, 5, 6),
            datetime.date(2026, 7, 20),
            datetime.date(2026, 8, 11),
            datetime.date(2026, 9, 21),
            datetime.date(2026, 9, 22),
            datetime.date(2026, 9, 23),
            datetime.date(2026, 10, 12),
            datetime.date(2026, 11, 3),
            datetime.date(2026, 11, 23),
            datetime.date(2026, 12, 31),
        }

        # 4. HKEX (Hong Kong) Holidays
        self.hkex_holidays: Set[datetime.date] = {
            # 2025
            datetime.date(2025, 1, 1),
            datetime.date(2025, 1, 29),
            datetime.date(2025, 1, 30),
            datetime.date(2025, 1, 31),
            datetime.date(2025, 4, 4),
            datetime.date(2025, 4, 18),
            datetime.date(2025, 4, 21),
            datetime.date(2025, 5, 5),
            datetime.date(2025, 5, 31),
            datetime.date(2025, 7, 1),
            datetime.date(2025, 10, 1),
            datetime.date(2025, 10, 7),
            datetime.date(2025, 10, 29),
            datetime.date(2025, 12, 25),
            datetime.date(2025, 12, 26),
            # 2026
            datetime.date(2026, 1, 1),
            datetime.date(2026, 2, 17),
            datetime.date(2026, 2, 18),
            datetime.date(2026, 2, 19),
            datetime.date(2026, 4, 3),
            datetime.date(2026, 4, 6),
            datetime.date(2026, 5, 25),
            datetime.date(2026, 6, 19),
            datetime.date(2026, 7, 1),
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 19),
            datetime.date(2026, 12, 25),
            datetime.date(2026, 12, 26),
        }

    def is_trading_day(self, exchange: str, local_date: datetime.date) -> bool:
        """Check if date is a weekday and not an exchange holiday."""
        if local_date.weekday() >= 5:
            return False

        if exchange == "NYSE":
            return local_date not in self.nyse_holidays
        elif exchange == "LSE":
            return local_date not in self.lse_holidays
        elif exchange == "TSE":
            return local_date not in self.tse_holidays
        elif exchange == "HKEX":
            return local_date not in self.hkex_holidays
        else:
            raise ValueError(f"Unknown exchange: {exchange}")

    def get_exchange_open_utc(self, exchange: str, local_date: datetime.date) -> Optional[pd.Timestamp]:
        """Compute the exact UTC Timestamp for an exchange open on a given local date."""
        if not self.is_trading_day(exchange, local_date):
            return None

        if exchange == "TSE":
            dt_local = datetime.datetime.combine(local_date, datetime.time(9, 0), tzinfo=self.TZ_TOKYO)
        elif exchange == "HKEX":
            dt_local = datetime.datetime.combine(local_date, datetime.time(9, 30), tzinfo=self.TZ_HONG_KONG)
        elif exchange == "LSE":
            dt_local = datetime.datetime.combine(local_date, datetime.time(8, 0), tzinfo=self.TZ_LONDON)
        elif exchange == "NYSE":
            dt_local = datetime.datetime.combine(local_date, datetime.time(9, 30), tzinfo=self.TZ_NEW_YORK)
        else:
            raise ValueError(f"Unknown exchange: {exchange}")

        dt_utc = dt_local.astimezone(datetime.timezone.utc)
        return pd.Timestamp(dt_utc)

    def generate_all_open_events(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> List[SessionOpenEvent]:
        """Generate all regular opening events in chronological UTC order."""
        events: List[SessionOpenEvent] = []
        cur_date = start_date
        while cur_date <= end_date:
            for ex in self.EXCHANGES:
                open_utc = self.get_exchange_open_utc(ex, cur_date)
                if open_utc is not None:
                    is_early = False
                    if ex == "NYSE" and cur_date in self.nyse_early_closes:
                        is_early = True
                    elif ex == "LSE" and cur_date in self.lse_early_closes:
                        is_early = True

                    events.append(
                        SessionOpenEvent(
                            exchange=ex,
                            open_time_utc=open_utc,
                            date_local=cur_date,
                            local_time="09:00" if ex == "TSE" else ("08:00" if ex == "LSE" else "09:30"),
                            is_holiday=False,
                            is_early_close=is_early,
                        )
                    )
            cur_date += datetime.timedelta(days=1)

        events.sort(key=lambda e: e.open_time_utc)
        return events

    def tag_dataset_session_windows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Exact window and horizon tagging relative to session openings."""
        df_out = df.copy()
        ts_series = pd.to_datetime(df_out["datetime_utc"], utc=True)
        min_ts = ts_series.min().date() - datetime.timedelta(days=2)
        max_ts = ts_series.max().date() + datetime.timedelta(days=2)

        events = self.generate_all_open_events(min_ts, max_ts)
        n = len(df_out)

        # Build index mapping for exact bar alignment
        ts_to_idx = {ts: i for i, ts in enumerate(ts_series)}

        for ex in self.EXCHANGES:
            ex_events = [e for e in events if e.exchange == ex]
            open_indices = [ts_to_idx[e.open_time_utc] for e in ex_events if e.open_time_utc in ts_to_idx]

            is_open_bar = np.zeros(n, dtype=int)
            pre_60m = np.zeros(n, dtype=int)
            pre_30m = np.zeros(n, dtype=int)
            pre_10m = np.zeros(n, dtype=int)

            post_5m = np.zeros(n, dtype=int)
            post_10m = np.zeros(n, dtype=int)
            post_15m = np.zeros(n, dtype=int)
            post_30m = np.zeros(n, dtype=int)
            post_60m = np.zeros(n, dtype=int)

            for idx in open_indices:
                is_open_bar[idx] = 1

                # Pre-open windows: [T_0 - X, T_0)
                # 10m = 2 bars before
                start_10m = max(0, idx - 2)
                pre_10m[start_10m:idx] = 1

                # 30m = 6 bars before
                start_30m = max(0, idx - 6)
                pre_30m[start_30m:idx] = 1

                # 60m = 12 bars before
                start_60m = max(0, idx - 12)
                pre_60m[start_60m:idx] = 1

                # Post-open windows: [T_0, T_0 + X)
                # 5m = 1 bar (the open bar)
                post_5m[idx] = 1

                # 10m = 2 bars [idx, idx+1]
                end_10m = min(n, idx + 2)
                post_10m[idx:end_10m] = 1

                # 15m = 3 bars [idx, idx+2]
                end_15m = min(n, idx + 3)
                post_15m[idx:end_15m] = 1

                # 30m = 6 bars [idx, idx+5]
                end_30m = min(n, idx + 6)
                post_30m[idx:end_30m] = 1

                # 60m = 12 bars [idx, idx+11]
                end_60m = min(n, idx + 12)
                post_60m[idx:end_60m] = 1

            df_out[f"{ex.lower()}_is_open_bar"] = is_open_bar
            df_out[f"{ex.lower()}_pre_10m"] = pre_10m
            df_out[f"{ex.lower()}_pre_30m"] = pre_30m
            df_out[f"{ex.lower()}_pre_60m"] = pre_60m
            df_out[f"{ex.lower()}_post_5m"] = post_5m
            df_out[f"{ex.lower()}_post_10m"] = post_10m
            df_out[f"{ex.lower()}_post_15m"] = post_15m
            df_out[f"{ex.lower()}_post_30m"] = post_30m
            df_out[f"{ex.lower()}_post_60m"] = post_60m

        # Weekday indicator & Weekend indicator
        weekdays = ts_series.dt.weekday.values
        df_out["is_weekend"] = (weekdays >= 5).astype(int)
        df_out["is_weekday"] = (weekdays < 5).astype(int)

        # Fast vectorized active session indicators
        dt_tky = ts_series.dt.tz_convert(self.TZ_TOKYO)
        dt_hkg = ts_series.dt.tz_convert(self.TZ_HONG_KONG)
        dt_lon = ts_series.dt.tz_convert(self.TZ_LONDON)
        dt_nys = ts_series.dt.tz_convert(self.TZ_NEW_YORK)

        # Tokyo 09:00 - 15:00 JST (540 to 900 mins)
        tky_mins = dt_tky.dt.hour * 60 + dt_tky.dt.minute
        tky_trading = dt_tky.dt.weekday < 5
        tky_holidays = set(self.tse_holidays)
        tky_not_holiday = ~dt_tky.dt.date.isin(tky_holidays)
        df_out["session_tokyo_active"] = (tky_trading & tky_not_holiday & (tky_mins >= 540) & (tky_mins < 900)).astype(int)

        # HKEX 09:30 - 16:00 HKT (570 to 960 mins)
        hkg_mins = dt_hkg.dt.hour * 60 + dt_hkg.dt.minute
        hkg_trading = dt_hkg.dt.weekday < 5
        hkg_holidays = set(self.hkex_holidays)
        hkg_not_holiday = ~dt_hkg.dt.date.isin(hkg_holidays)
        df_out["session_hkex_active"] = (hkg_trading & hkg_not_holiday & (hkg_mins >= 570) & (hkg_mins < 960)).astype(int)

        # London 08:00 - 16:30 Local (480 to 990 mins)
        lon_mins = dt_lon.dt.hour * 60 + dt_lon.dt.minute
        lon_trading = dt_lon.dt.weekday < 5
        lon_holidays = set(self.lse_holidays)
        lon_not_holiday = ~dt_lon.dt.date.isin(lon_holidays)
        df_out["session_london_active"] = (lon_trading & lon_not_holiday & (lon_mins >= 480) & (lon_mins < 990)).astype(int)

        # NYSE 09:30 - 16:00 Local (570 to 960 mins, or 780 for early close)
        nys_mins = dt_nys.dt.hour * 60 + dt_nys.dt.minute
        nys_trading = dt_nys.dt.weekday < 5
        nys_holidays = set(self.nyse_holidays)
        nys_early = set(self.nyse_early_closes)
        nys_not_holiday = ~dt_nys.dt.date.isin(nys_holidays)
        is_early_series = dt_nys.dt.date.isin(nys_early)
        close_mins_series = np.where(is_early_series, 780, 960)
        df_out["session_nyse_active"] = (nys_trading & nys_not_holiday & (nys_mins >= 570) & (nys_mins < close_mins_series)).astype(int)

        # Overlap: London & NYSE simultaneously active
        df_out["session_lon_ny_overlap"] = (df_out["session_london_active"] & df_out["session_nyse_active"]).astype(int)

        return df_out
