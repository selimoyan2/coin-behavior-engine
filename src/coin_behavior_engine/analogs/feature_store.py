"""Causal Market Memory Feature Store for Historical Analog Learning Engine V1.

Sprint 11.19 Phase 1:
Generates deterministic point-in-time feature vectors from verified multi-year Binance Vision data:
- Multi-horizon returns (5m, 15m, 1h, 4h, 24h, 72h).
- Price-normalized realized volatility and 5m ATR%.
- Volume expansion/contraction z-scores and ratios.
- Trend strength and trend persistence.
- Drawdowns from recent highs and recovery from recent lows.
- Distance from rolling support and resistance.
- Volatility-normalized range width.
- Repeated support and resistance boundary tests.
- Breakout attempts and failed breakout rejections.
- Global equity exchange session context (TSE, HKEX, LSE, NYSE).
- Verified macroeconomic event context under conservative visibility.

Strict Invariants:
1. All features use strictly data available at or before query timestamp T_0 (no future leakage).
2. Rolling windows crossing the March 24, 2023 exchange outage (80 missing bars) are flagged and rejected.
3. Missing news coverage is never interpreted as 'no news occurred'.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.macro.global_session_calendar import GlobalSessionCalendar


@dataclass(frozen=True)
class FeatureVector:
    """Immutable point-in-time market memory state."""
    open_time: int
    datetime_utc: str
    close: float
    ret_5m: float
    ret_15m: float
    ret_1h: float
    ret_4h: float
    ret_24h: float
    ret_72h: float
    atr_5m_pct: float
    realized_vol_24h: float
    volume_zscore_24h: float
    volume_ratio_1h_24h: float
    trend_strength: float
    trend_persistence_4h: float
    drawdown_high_24h: float
    drawdown_high_72h: float
    recovery_low_24h: float
    recovery_low_72h: float
    dist_support_24h: float
    dist_resistance_24h: float
    range_width_pct_24h: float
    range_width_atr_ratio_24h: float
    support_tests_24h: int
    resistance_tests_24h: int
    failed_breakout_high_24h: bool
    failed_breakout_low_24h: bool
    active_sessions_count: int
    session_phase_tag: str
    minutes_to_nyse_open: Optional[float]
    macro_event_active_1h: bool
    macro_event_id: Optional[str]
    is_valid_window: bool
    rejection_reason: Optional[str]


class CausalFeatureStore:
    """Constructs and manages the deterministic multi-year causal feature matrix."""

    OUTAGE_START_MS = 1679661540000  # 2023-03-24 12:39:00 UTC
    OUTAGE_END_MS = 1679666400000    # 2023-03-24 14:00:00 UTC

    def __init__(
        self,
        df_5m: pd.DataFrame,
        events: Optional[List[Dict[str, Any]]] = None,
        calendar: Optional[GlobalSessionCalendar] = None
    ):
        """Initialize feature store with verified 5m candles.
        
        Args:
            df_5m: Continuous 5m OHLCV DataFrame containing ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time']
            events: List of audited event dictionaries conforming to historical event schema.
            calendar: GlobalSessionCalendar instance.
        """
        self.calendar = calendar or GlobalSessionCalendar()
        self.events = events or []

        # Sort and guarantee clean numeric types
        df = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype("float64")
        df["open_time"] = df["open_time"].astype("int64")
        if "close_time" in df.columns:
            df["close_time"] = df["close_time"].astype("int64")
        else:
            df["close_time"] = df["open_time"] + 299999

        self.df = df
        self.open_times = df["open_time"].to_numpy()
        self.close_times = df["close_time"].to_numpy()
        self._precompute_feature_matrix()

    def _precompute_feature_matrix(self):
        """Vectorized precomputation of historical rolling indicators."""
        df = self.df
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        open_p = df["open"]

        # 1. Multi-horizon continuous log/percentage returns
        df["ret_5m"] = (close / close.shift(1) - 1.0).fillna(0.0)
        df["ret_15m"] = (close / close.shift(3) - 1.0).fillna(0.0)
        df["ret_1h"] = (close / close.shift(12) - 1.0).fillna(0.0)
        df["ret_4h"] = (close / close.shift(48) - 1.0).fillna(0.0)
        df["ret_24h"] = (close / close.shift(288) - 1.0).fillna(0.0)
        df["ret_72h"] = (close / close.shift(864) - 1.0).fillna(0.0)

        # 2. 5m True Range and ATR%
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = tr.rolling(window=14, min_periods=1).mean()
        df["atr_5m_pct"] = (atr_14 / close).clip(lower=0.0001)

        # 3. 24h Realized Volatility (annualized of 5m log returns)
        log_ret_5m = np.log(close / prev_close).fillna(0.0)
        rolling_std_24h = log_ret_5m.rolling(window=288, min_periods=48).std()
        df["realized_vol_24h"] = (rolling_std_24h * np.sqrt(288 * 365)).fillna(0.0)

        # 4. Volume expansion & contraction z-score
        vol_mean_24h = volume.rolling(window=288, min_periods=48).mean()
        vol_std_24h = volume.rolling(window=288, min_periods=48).std().replace(0.0, 1.0)
        df["volume_zscore_24h"] = ((volume - vol_mean_24h) / vol_std_24h).fillna(0.0).clip(-3.0, 5.0)

        vol_sum_1h = volume.rolling(window=12, min_periods=1).sum()
        vol_sum_24h = volume.rolling(window=288, min_periods=12).sum()
        df["volume_ratio_1h_24h"] = (vol_sum_1h / (vol_sum_24h / 24.0).replace(0.0, 1.0)).fillna(1.0).clip(0.0, 10.0)

        # 5. Trend strength and persistence
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_72 = close.ewm(span=72, adjust=False).mean()
        df["trend_strength"] = ((ema_12 - ema_72) / (close * df["atr_5m_pct"])).fillna(0.0).clip(-5.0, 5.0)

        is_above_ema72 = (close > ema_72).astype(float)
        df["trend_persistence_4h"] = is_above_ema72.rolling(window=48, min_periods=1).mean()

        # 6. Extremes, Drawdowns & Recovery
        high_288 = high.rolling(window=288, min_periods=12).max()
        low_288 = low.rolling(window=288, min_periods=12).min()
        high_864 = high.rolling(window=864, min_periods=48).max()
        low_864 = low.rolling(window=864, min_periods=48).min()

        df["drawdown_high_24h"] = ((close - high_288) / high_288).fillna(0.0)
        df["drawdown_high_72h"] = ((close - high_864) / high_864).fillna(0.0)
        df["recovery_low_24h"] = ((close - low_288) / low_288).fillna(0.0)
        df["recovery_low_72h"] = ((close - low_864) / low_864).fillna(0.0)

        # 7. Support & Resistance Distance & Range Width
        df["dist_support_24h"] = ((close - low_288) / close).fillna(0.0)
        df["dist_resistance_24h"] = ((high_288 - close) / close).fillna(0.0)
        df["range_width_pct_24h"] = ((high_288 - low_288) / close).fillna(0.0)
        df["range_width_atr_ratio_24h"] = (df["range_width_pct_24h"] / df["atr_5m_pct"]).fillna(0.0).clip(0.0, 50.0)

        # 8. Boundary tests (within 0.25% of 24h high/low)
        near_high = (high >= high_288 * 0.9975).astype(int)
        near_low = (low <= low_288 * 1.0025).astype(int)
        df["resistance_tests_24h"] = near_high.rolling(window=288, min_periods=1).sum().astype(int)
        df["support_tests_24h"] = near_low.rolling(window=288, min_periods=1).sum().astype(int)

        # 9. Breakout attempts & rejections
        prior_high_288 = high_288.shift(1)
        prior_low_288 = low_288.shift(1)
        df["failed_breakout_high_24h"] = ((high > prior_high_288) & (close < prior_high_288)).fillna(False)
        df["failed_breakout_low_24h"] = ((low < prior_low_288) & (close > prior_low_288)).fillna(False)

        # 10. Gap / Outage validity flag
        # A 72h window (864 bars) is invalid if it crosses the March 24, 2023 outage
        window_start_ms = df["open_time"] - (864 * 300000)
        window_end_ms = df["open_time"]
        crosses_outage = (window_start_ms <= self.OUTAGE_END_MS) & (window_end_ms >= self.OUTAGE_START_MS)
        has_min_history = df.index >= 864
        df["is_valid_window"] = has_min_history & (~crosses_outage)
        df["rejection_reason"] = None
        df.loc[~has_min_history, "rejection_reason"] = "INSUFFICIENT_HISTORY_UNDER_864_BARS"
        df.loc[crosses_outage, "rejection_reason"] = "WINDOW_CROSSES_20230324_EXCHANGE_OUTAGE"

    def get_feature_vector_at(self, timestamp: Any) -> Optional[FeatureVector]:
        """Extract point-in-time feature vector for exact query timestamp T_0.
        
        Args:
            timestamp: ISO string or epoch ms.
        """
        if isinstance(timestamp, str):
            ts_ms = int(pd.to_datetime(timestamp, utc=True).value // 1_000_000)
        elif isinstance(timestamp, (int, np.integer)):
            ts_ms = int(timestamp)
        elif isinstance(timestamp, pd.Timestamp):
            ts_ms = int(timestamp.value // 1_000_000)
        else:
            raise TypeError(f"Unsupported timestamp format: {type(timestamp)}")

        # Only closed candles are visible: close_time <= ts_ms
        idx = np.searchsorted(self.close_times, ts_ms, side="right") - 1
        if idx < 0:
            return None

        row = self.df.iloc[idx]
        ts_dt = pd.to_datetime(ts_ms, unit="ms", utc=True)

        # Session context
        sess_data = self._compute_session_context(ts_dt)

        # Macro event context under conservative visibility rules
        macro_active, macro_id = self._compute_macro_event_context(ts_ms)

        return FeatureVector(
            open_time=int(row["open_time"]),
            datetime_utc=str(pd.to_datetime(row["open_time"], unit="ms", utc=True)),
            close=float(row["close"]),
            ret_5m=float(row["ret_5m"]),
            ret_15m=float(row["ret_15m"]),
            ret_1h=float(row["ret_1h"]),
            ret_4h=float(row["ret_4h"]),
            ret_24h=float(row["ret_24h"]),
            ret_72h=float(row["ret_72h"]),
            atr_5m_pct=float(row["atr_5m_pct"]),
            realized_vol_24h=float(row["realized_vol_24h"]),
            volume_zscore_24h=float(row["volume_zscore_24h"]),
            volume_ratio_1h_24h=float(row["volume_ratio_1h_24h"]),
            trend_strength=float(row["trend_strength"]),
            trend_persistence_4h=float(row["trend_persistence_4h"]),
            drawdown_high_24h=float(row["drawdown_high_24h"]),
            drawdown_high_72h=float(row["drawdown_high_72h"]),
            recovery_low_24h=float(row["recovery_low_24h"]),
            recovery_low_72h=float(row["recovery_low_72h"]),
            dist_support_24h=float(row["dist_support_24h"]),
            dist_resistance_24h=float(row["dist_resistance_24h"]),
            range_width_pct_24h=float(row["range_width_pct_24h"]),
            range_width_atr_ratio_24h=float(row["range_width_atr_ratio_24h"]),
            support_tests_24h=int(row["support_tests_24h"]),
            resistance_tests_24h=int(row["resistance_tests_24h"]),
            failed_breakout_high_24h=bool(row["failed_breakout_high_24h"]),
            failed_breakout_low_24h=bool(row["failed_breakout_low_24h"]),
            active_sessions_count=sess_data["active_count"],
            session_phase_tag=sess_data["phase_tag"],
            minutes_to_nyse_open=sess_data["minutes_to_nyse"],
            macro_event_active_1h=macro_active,
            macro_event_id=macro_id,
            is_valid_window=bool(row["is_valid_window"]),
            rejection_reason=row["rejection_reason"]
        )

    def _compute_session_context(self, ts_dt: pd.Timestamp) -> Dict[str, Any]:
        """Compute exchange session counts and proximity."""
        q_dt = ts_dt.to_pydatetime()
        if q_dt.tzinfo is None:
            q_dt = q_dt.replace(tzinfo=datetime.timezone.utc)

        active_count = 0
        minutes_to_nyse = None
        phase_tag = "OFF_SESSION"

        for ex in self.calendar.EXCHANGES:
            tz = getattr(self.calendar, f"TZ_{'HONG_KONG' if ex == 'HKEX' else ('NEW_YORK' if ex == 'NYSE' else ('TOKYO' if ex == 'TSE' else 'LONDON'))}")
            local_dt = q_dt.astimezone(tz)
            open_utc = self.calendar.get_exchange_open_utc(ex, local_dt.date())
            if open_utc is not None:
                durations_hours = {"TSE": 6.0, "HKEX": 6.5, "LSE": 8.5, "NYSE": 6.5}
                diff_m = (ts_dt - open_utc).total_seconds() / 60.0
                if 0 <= diff_m <= durations_hours[ex] * 60:
                    active_count += 1
                if ex == "NYSE":
                    minutes_to_nyse = round(-diff_m if diff_m < 0 else diff_m, 1)
                    if -60 <= diff_m < 0:
                        phase_tag = "NYSE_PRE_OPEN"
                    elif 0 <= diff_m <= 60:
                        phase_tag = "NYSE_OPEN"

        if active_count >= 2 and phase_tag == "OFF_SESSION":
            phase_tag = "SESSION_OVERLAP"
        elif active_count == 1 and phase_tag == "OFF_SESSION":
            phase_tag = "SINGLE_SESSION"

        return {
            "active_count": active_count,
            "minutes_to_nyse": minutes_to_nyse,
            "phase_tag": phase_tag
        }

    def _compute_macro_event_context(self, ts_ms: int) -> Tuple[bool, Optional[str]]:
        """Identify if a macroeconomic event occurred in [T - 1h, T] and is visible under conservative delay."""
        one_hour_ms = 3600 * 1000
        for evt in self.events:
            uncert = evt.get("dissemination_delay_estimate") or evt.get("availability_uncertainty_interval")
            if uncert:
                avail_str = uncert.get("conservative_visibility_utc") or uncert.get("latest_conservative_available_at_utc")
            else:
                avail_str = evt.get("available_at_utc")

            if avail_str:
                avail_ms = int(pd.to_datetime(avail_str, utc=True).value // 1_000_000)
                # Event must be causally visible (avail_ms <= ts_ms) and fresh within last 1h
                if avail_ms <= ts_ms and (ts_ms - avail_ms) <= one_hour_ms:
                    return True, evt.get("event_id")

        return False, None
