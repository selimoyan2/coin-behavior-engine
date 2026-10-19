"""
Sprint 11.23.3: Prospective BTC/USDT Observation Architecture
Provides research-only market observation for Binance Spot BTC/USDT around economic events.
Enforces strict trading prohibition, look-ahead isolation, candle integrity checks,
and multi-horizon descriptive reaction metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

@dataclass
class MarketCandle:
    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate_ohlcv(self) -> Tuple[bool, Optional[str]]:
        """Validates standard OHLCV price relations and finiteness."""
        if not (np.isfinite(self.open) and np.isfinite(self.high) and np.isfinite(self.low) and np.isfinite(self.close) and np.isfinite(self.volume)):
            return False, "NON_FINITE_VALUE_DETECTED"
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            return False, "NON_POSITIVE_PRICE"
        if self.volume < 0:
            return False, "NEGATIVE_VOLUME"
        if self.high < self.low:
            return False, "HIGH_LESS_THAN_LOW"
        if self.high < self.open or self.high < self.close:
            return False, "HIGH_VIOLATION"
        if self.low > self.open or self.low > self.close:
            return False, "LOW_VIOLATION"
        return True, None

@dataclass
class EventObservationReport:
    event_id: str
    official_published_at_utc: str
    safe_execution_start_utc: str
    candle_timeframe: str
    pre_event_window_minutes: int
    post_event_window_minutes: int
    data_continuity_status: str
    missing_candles_detected: int
    duplicate_candles_rejected: int
    
    # Pre-event descriptive metrics
    pre_60m_ret_pct: float
    pre_60m_volatility_pct: float
    
    # Post-event descriptive reaction metrics (strictly descriptive, no trading signals)
    post_15m_ret_pct: float
    post_15m_abs_ret_pct: float
    post_1h_ret_pct: float
    post_4h_ret_pct: float
    post_24h_ret_pct: float
    post_24h_mfe_pct: float
    post_24h_mae_pct: float
    post_24h_realized_vol_pct: float
    post_1h_relative_volume: float
    continuation_24h: bool
    reversal_24h: bool

    # Governance & Trading Isolation
    directional_trading_signal: str = "NONE_PROHIBITED"
    portfolio_allocation_authorized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ProspectiveMarketObserver:
    """
    Research-only market observer for prospective BTC/USDT reaction capture.
    Strictly barred from generating trade recommendations, orders, or allocations.
    """

    def __init__(self, ingestion_delay_seconds: float = 5.0) -> None:
        self.ingestion_delay_seconds = ingestion_delay_seconds

    def clean_and_validate_candles(
        self,
        candles_df: pd.DataFrame,
        expected_freq_minutes: int = 5
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Validates OHLCV rules, detects missing intervals, and removes duplicates deterministically.
        """
        if candles_df.empty:
            return candles_df, {"status": "EMPTY", "missing_count": 0, "duplicates_rejected": 0}

        df = candles_df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        initial_count = len(df)

        # 1. Deduplicate
        df = df.drop_duplicates(subset=["datetime"], keep="last")
        duplicates_rejected = initial_count - len(df)
        df = df.sort_values("datetime").reset_index(drop=True)

        # 2. Validate OHLCV
        valid_mask = (
            (df["high"] >= df["low"]) &
            (df["high"] >= df["open"]) &
            (df["high"] >= df["close"]) &
            (df["low"] <= df["open"]) &
            (df["low"] <= df["close"]) &
            (df["volume"] >= 0) &
            np.isfinite(df["open"]) &
            np.isfinite(df["high"]) &
            np.isfinite(df["low"]) &
            np.isfinite(df["close"])
        )
        df = df[valid_mask].reset_index(drop=True)

        # 3. Detect Missing Gaps
        diffs = df["datetime"].diff()[1:]
        expected_delta = pd.Timedelta(minutes=expected_freq_minutes)
        gaps = diffs[diffs > expected_delta]
        missing_count = sum(int(gap / expected_delta) - 1 for gap in gaps)

        meta = {
            "status": "VALID" if missing_count == 0 else "GAPS_DETECTED",
            "initial_rows": initial_count,
            "valid_rows": len(df),
            "duplicates_rejected": duplicates_rejected,
            "missing_count": missing_count,
            "start_time_utc": str(df["datetime"].min()),
            "end_time_utc": str(df["datetime"].max())
        }
        return df, meta

    def observe_event_window(
        self,
        event_id: str,
        t_pub_utc_str: str,
        uncertainty_seconds: float,
        market_df: pd.DataFrame,
        timeframe_minutes: int = 5
    ) -> EventObservationReport:
        """
        Observes BTC/USDT price movements across the pre-event (-60m) and post-event
        (+15m, +60m, +4h, +24h) horizons.
        Guarantees that safe execution starts strictly at or after t_pub + uncertainty.
        """
        df, meta = self.clean_and_validate_candles(market_df, expected_freq_minutes=timeframe_minutes)
        
        t_pub = pd.to_datetime(t_pub_utc_str, utc=True)
        t_safe = t_pub + pd.Timedelta(seconds=uncertainty_seconds)

        # Find safe execution candle: earliest candle whose Open >= t_safe
        post_candles = df[df["datetime"] >= t_safe].reset_index(drop=True)
        if len(post_candles) < 288: # Need 24h of 5m candles = 288
            # Partial window
            status = "OBSERVATION_INCOMPLETE"
        else:
            status = meta["status"]

        # Pre-event window (-60m to t_pub)
        t_pre_start = t_pub - pd.Timedelta(minutes=60)
        pre_candles = df[(df["datetime"] >= t_pre_start) & (df["datetime"] < t_pub)].reset_index(drop=True)

        if not pre_candles.empty:
            pre_ret = float((pre_candles["close"].iloc[-1] - pre_candles["open"].iloc[0]) / pre_candles["open"].iloc[0] * 100.0)
            pre_vol = float(np.std(pre_candles["close"].pct_change().dropna()) * np.sqrt(len(pre_candles)) * 100.0)
        else:
            pre_ret, pre_vol = 0.0, 0.0

        if not post_candles.empty:
            exec_open = float(post_candles["open"].iloc[0])
            safe_open_time = str(post_candles["datetime"].iloc[0])

            # +15m (3 bars of 5m or 15 bars of 1m)
            bars_15m = 3 if timeframe_minutes == 5 else 15
            bars_1h = 12 if timeframe_minutes == 5 else 60
            bars_4h = 48 if timeframe_minutes == 5 else 240
            bars_24h = 288 if timeframe_minutes == 5 else 1440

            idx_15m = min(len(post_candles) - 1, bars_15m - 1)
            idx_1h = min(len(post_candles) - 1, bars_1h - 1)
            idx_4h = min(len(post_candles) - 1, bars_4h - 1)
            idx_24h = min(len(post_candles) - 1, bars_24h - 1)

            ret_15m = float((post_candles["close"].iloc[idx_15m] - exec_open) / exec_open * 100.0)
            ret_1h = float((post_candles["close"].iloc[idx_1h] - exec_open) / exec_open * 100.0)
            ret_4h = float((post_candles["close"].iloc[idx_4h] - exec_open) / exec_open * 100.0)
            ret_24h = float((post_candles["close"].iloc[idx_24h] - exec_open) / exec_open * 100.0)

            # MFE / MAE over 24h
            sub_24h = post_candles.iloc[: idx_24h + 1]
            mfe_24h = float((sub_24h["high"].max() - exec_open) / exec_open * 100.0)
            mae_24h = float((exec_open - sub_24h["low"].min()) / exec_open * 100.0)
            realized_vol_24h = float(np.std(sub_24h["close"].pct_change().dropna()) * np.sqrt(len(sub_24h)) * 100.0)

            # Relative volume 1h
            vol_1h = float(post_candles["volume"].iloc[: idx_1h + 1].sum())
            baseline_vol = float(pre_candles["volume"].sum()) if not pre_candles.empty else vol_1h
            rel_vol = (vol_1h / baseline_vol) if baseline_vol > 0 else 1.0

            continuation = bool(np.sign(ret_15m) == np.sign(ret_24h))
            reversal = bool(np.sign(ret_15m) != np.sign(ret_24h))
        else:
            safe_open_time = str(t_safe)
            ret_15m = ret_1h = ret_4h = ret_24h = mfe_24h = mae_24h = realized_vol_24h = 0.0
            rel_vol = 1.0
            continuation = False
            reversal = False

        return EventObservationReport(
            event_id=event_id,
            official_published_at_utc=t_pub_utc_str,
            safe_execution_start_utc=safe_open_time,
            candle_timeframe=f"{timeframe_minutes}m",
            pre_event_window_minutes=60,
            post_event_window_minutes=1440,
            data_continuity_status=status,
            missing_candles_detected=meta["missing_count"],
            duplicate_candles_rejected=meta["duplicates_rejected"],
            pre_60m_ret_pct=round(pre_ret, 3),
            pre_60m_volatility_pct=round(pre_vol, 3),
            post_15m_ret_pct=round(ret_15m, 3),
            post_15m_abs_ret_pct=round(abs(ret_15m), 3),
            post_1h_ret_pct=round(ret_1h, 3),
            post_4h_ret_pct=round(ret_4h, 3),
            post_24h_ret_pct=round(ret_24h, 3),
            post_24h_mfe_pct=round(mfe_24h, 3),
            post_24h_mae_pct=round(mae_24h, 3),
            post_24h_realized_vol_pct=round(realized_vol_24h, 3),
            post_1h_relative_volume=round(rel_vol, 2),
            continuation_24h=continuation,
            reversal_24h=reversal,
            directional_trading_signal="NONE_PROHIBITED",
            portfolio_allocation_authorized=False
        )

    def evaluate_observation_window(self, candles_df: pd.DataFrame) -> Dict[str, Any]:
        """Evaluates a raw window of candles, returning clean data metrics and continuity status."""
        clean_df, meta = self.clean_and_validate_candles(candles_df)
        if clean_df.empty:
            return {"status": "EMPTY", "rows": 0}
        open_p = float(clean_df["open"].iloc[0])
        close_p = float(clean_df["close"].iloc[-1])
        ret_pct = float((close_p - open_p) / open_p * 100.0)
        return {
            "status": meta["status"],
            "rows": len(clean_df),
            "open_price": round(open_p, 2),
            "close_price": round(close_p, 2),
            "return_pct": round(ret_pct, 4),
            "missing_count": meta["missing_count"],
            "duplicates_rejected": meta["duplicates_rejected"]
        }
