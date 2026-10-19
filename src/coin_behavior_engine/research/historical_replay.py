"""Causal Historical Market & Event Replay Engine.

Sprint 11.18: Multi-Year Causal Data Infrastructure.
Provides deterministic, point-in-time state reconstruction combining:
1. Closed historical OHLCV market candles (rejects unclosed forming candles).
2. Point-in-time financial and macroeconomic events (strictly enforces available_at_utc <= T).
3. Global exchange session context (TSE, HKEX, LSE, NYSE).
4. Cryptographic state fingerprinting via SHA-256(T).
"""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

from coin_behavior_engine.macro.global_session_calendar import (
    GlobalSessionCalendar,
    SessionOpenEvent,
)


@dataclass(frozen=True)
class ReplayState:
    query_time_utc: str
    query_timestamp_ms: int
    last_closed_candle: Optional[Dict[str, Any]]
    candle_count_observed: int
    active_sessions: List[str]
    session_relative_windows: Dict[str, Any]
    visible_events: List[Dict[str, Any]]
    visible_event_count: int
    state_hash_sha256: str


class HistoricalReplayEngine:
    """Deterministic, point-in-time historical replay engine ensuring causal isolation."""

    def __init__(
        self,
        candles_df: pd.DataFrame,
        events: Optional[List[Dict[str, Any]]] = None,
        calendar: Optional[GlobalSessionCalendar] = None,
    ):
        """Initialize engine with market candles and point-in-time events.
        
        Args:
            candles_df: DataFrame containing at least ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time']
            events: List of event dicts conforming to CBEPointInTimeEventSchema
            calendar: GlobalSessionCalendar instance
        """
        self.calendar = calendar or GlobalSessionCalendar()
        self.events = events or []
        
        # Prepare candles dataframe
        df = candles_df.copy()
        if "close_time" not in df.columns:
            if "timestamp_close" in df.columns:
                df["close_time"] = df["timestamp_close"]
            elif "timestamp_open" in df.columns:
                # Default 5-minute close if not specified
                df["close_time"] = df["timestamp_open"] + (5 * 60 * 1000 - 1)
            elif "open_time" in df.columns:
                df["close_time"] = df["open_time"] + (60 * 1000 - 1)
            else:
                raise ValueError("Candles dataframe must contain open_time or close_time")
                
        if "open_time" not in df.columns and "timestamp_open" in df.columns:
            df["open_time"] = df["timestamp_open"]
            
        df = df.sort_values("close_time").reset_index(drop=True)
        self.candles_df = df
        self._candle_close_times = df["close_time"].to_numpy()

    def _parse_timestamp_ms(self, ts: Union[str, int, float, pd.Timestamp, datetime.datetime]) -> int:
        """Convert input timestamp to epoch milliseconds."""
        if isinstance(ts, (int, np.integer)):
            # If greater than 1e11 (1973+ in ms), it is already in ms.
            # For testing with synthetic small integers, keep as integer.
            return int(ts)
        elif isinstance(ts, float):
            return int(ts)
        elif isinstance(ts, str):
            dt = pd.to_datetime(ts, utc=True)
            return int(dt.value // 1_000_000)
        elif isinstance(ts, (pd.Timestamp, datetime.datetime)):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            return int(ts.timestamp() * 1000)
        else:
            raise TypeError(f"Unsupported timestamp format: {type(ts)}")

    def get_session_status(self, timestamp_utc: pd.Timestamp) -> Dict[str, Any]:
        """Compute active session and opening-relative window status at query time."""
        active_sessions = []
        session_windows = {}

        # Query time in UTC
        q_dt = timestamp_utc.to_pydatetime()
        if q_dt.tzinfo is None:
            q_dt = q_dt.replace(tzinfo=datetime.timezone.utc)

        # Check all 4 exchanges
        for ex in self.calendar.EXCHANGES:
            # Exchange opening time for today
            tz = getattr(self.calendar, f"TZ_{'HONG_KONG' if ex == 'HKEX' else ('NEW_YORK' if ex == 'NYSE' else ('TOKYO' if ex == 'TSE' else 'LONDON'))}")
            local_dt = q_dt.astimezone(tz)
            local_date = local_dt.date()

            open_utc = self.calendar.get_exchange_open_utc(ex, local_date)
            window_info = {"status": "CLOSED", "minutes_to_open": None, "relative_tag": "OFF_SESSION"}

            if open_utc is not None:
                # Exchange duration: regular hours
                # TSE: 09:00 - 15:00 JST (6h)
                # HKEX: 09:30 - 16:00 HKT (6.5h)
                # LSE: 08:00 - 16:30 London (8.5h)
                # NYSE: 09:30 - 16:00 New York (6.5h)
                durations_hours = {"TSE": 6.0, "HKEX": 6.5, "LSE": 8.5, "NYSE": 6.5}
                close_utc = open_utc + pd.Timedelta(hours=durations_hours[ex])

                diff_minutes = (timestamp_utc - open_utc).total_seconds() / 60.0

                if 0 <= diff_minutes <= durations_hours[ex] * 60:
                    active_sessions.append(ex)
                    window_info["status"] = "OPEN"
                elif diff_minutes < 0:
                    window_info["status"] = "PRE_OPEN"
                else:
                    window_info["status"] = "POST_CLOSE"

                window_info["minutes_to_open"] = round(-diff_minutes, 1) if diff_minutes < 0 else round(diff_minutes, 1)

                # Pre-open / Post-open tags
                if -60 <= diff_minutes < 0:
                    if -10 <= diff_minutes < 0:
                        window_info["relative_tag"] = "PRE_OPEN_10M"
                    elif -30 <= diff_minutes < -10:
                        window_info["relative_tag"] = "PRE_OPEN_30M"
                    else:
                        window_info["relative_tag"] = "PRE_OPEN_60M"
                elif 0 <= diff_minutes <= 60:
                    if 0 <= diff_minutes <= 10:
                        window_info["relative_tag"] = "POST_OPEN_10M"
                    elif diff_minutes <= 30:
                        window_info["relative_tag"] = "POST_OPEN_30M"
                    else:
                        window_info["relative_tag"] = "POST_OPEN_60M"

            session_windows[ex] = window_info

        return {
            "active_sessions": sorted(active_sessions),
            "session_windows": session_windows
        }

    def get_point_in_time_state(self, timestamp: Union[str, int, float, pd.Timestamp, datetime.datetime]) -> ReplayState:
        """Construct the exact point-in-time market, event, and session state for query time."""
        ts_ms = self._parse_timestamp_ms(timestamp)
        ts_dt = pd.to_datetime(ts_ms, unit="ms", utc=True)
        ts_iso = ts_dt.isoformat()

        # 1. Closed market candles: close_time <= ts_ms
        # Binary search for rightmost closed candle
        idx = np.searchsorted(self._candle_close_times, ts_ms, side="right")
        candle_count = int(idx)
        
        last_closed = None
        if candle_count > 0:
            row = self.candles_df.iloc[candle_count - 1]
            last_closed = {
                "open_time": int(row["open_time"]),
                "close_time": int(row["close_time"]),
                "datetime_utc": str(pd.to_datetime(row["open_time"], unit="ms", utc=True)),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"])
            }

        # 2. Point-in-time events: available_at_utc <= ts_iso
        visible_events = []
        for evt in self.events:
            avail_str = evt.get("available_at_utc")
            if avail_str:
                avail_ms = self._parse_timestamp_ms(avail_str)
                if avail_ms <= ts_ms:
                    visible_events.append({
                        "event_id": evt["event_id"],
                        "category": evt.get("category"),
                        "available_at_utc": avail_str,
                        "headline": evt.get("headline"),
                        "sentiment_label": evt.get("sentiment_label"),
                        "checksum_sha256": evt.get("checksum_sha256")
                    })

        # Sort visible events deterministically by event_id
        visible_events.sort(key=lambda x: x["event_id"])

        # 3. Session status
        sess_data = self.get_session_status(ts_dt)

        # 4. Deterministic state hash
        hash_payload = {
            "query_timestamp_ms": ts_ms,
            "candle_count_observed": candle_count,
            "last_candle_close_time": last_closed["close_time"] if last_closed else None,
            "last_candle_close": last_closed["close"] if last_closed else None,
            "active_sessions": sess_data["active_sessions"],
            "visible_event_ids": [e["event_id"] for e in visible_events]
        }
        payload_bytes = json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        state_hash = hashlib.sha256(payload_bytes).hexdigest()

        return ReplayState(
            query_time_utc=ts_iso,
            query_timestamp_ms=ts_ms,
            last_closed_candle=last_closed,
            candle_count_observed=candle_count,
            active_sessions=sess_data["active_sessions"],
            session_relative_windows=sess_data["session_windows"],
            visible_events=visible_events,
            visible_event_count=len(visible_events),
            state_hash_sha256=state_hash
        )
