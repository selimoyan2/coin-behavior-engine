"""Historical data acquisition, local caching, and timeframe aggregation.

Sprint 11.03: Market Behavior Research Lab.
Handles Binance Spot 1m klines acquisition, local immutable storage,
read-only Live Capture imports, and strict anti-leakage multi-timeframe aggregation.
"""

from __future__ import annotations

import json
import logging
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pandas as pd

from coin_behavior_engine.research_lab.configuration import ResearchLabConfig
from coin_behavior_engine.research_lab.contracts import CandleData, Resolution

logger = logging.getLogger("cbe_research_lab.historical_data")


class TimeframeAggregator:
    """Aggregates granular candles (e.g., 1m) into higher timeframes without future leakage.
    
    A higher timeframe bar is ONLY completed when all constituent lower timeframe
    bars within its window have closed.
    """

    TIMEFRAME_MS = {
        Resolution.M1.value: 60_000,
        Resolution.M5.value: 300_000,
        Resolution.M15.value: 900_000,
        Resolution.H1.value: 3_600_000,
        Resolution.H4.value: 14_400_000,
        Resolution.D1.value: 86_400_000,
    }

    @classmethod
    def aggregate(
        cls,
        candles: List[CandleData],
        target_interval: str = "5m",
        symbol: str = "BTCUSDT",
        allow_partial_boundaries: bool = False,
    ) -> List[CandleData]:
        """Aggregate lower timeframe candles into target_interval bars deterministically.
        
        Strictly requires all constituent bars to be present and complete unless
        allow_partial_boundaries is explicitly set to True.
        """
        target_ms = cls.TIMEFRAME_MS.get(target_interval)
        if not target_ms:
            raise ValueError(f"Unsupported target interval: {target_interval}")
        if not candles:
            return []

        source_interval = candles[0].interval
        if source_interval == target_interval:
            return list(candles)

        source_ms = cls.TIMEFRAME_MS.get(source_interval, 60_000)
        if target_ms % source_ms != 0:
            raise ValueError(f"Target interval {target_interval} ({target_ms}ms) is not an integer multiple of source {source_interval} ({source_ms}ms)")

        expected_bars_per_bucket = target_ms // source_ms
        aggregated: List[CandleData] = []
        
        # Group candles by bucket
        current_bucket_open_ts: Optional[int] = None
        current_bucket_candles: List[CandleData] = []

        for c in candles:
            bucket_ts = (c.timestamp_open // target_ms) * target_ms
            
            if current_bucket_open_ts is None:
                current_bucket_open_ts = bucket_ts
                current_bucket_candles = [c]
            elif bucket_ts == current_bucket_open_ts:
                current_bucket_candles.append(c)
            else:
                # Previous bucket finished. Only emit if it contains expected bars or partials allowed
                is_complete = len(current_bucket_candles) == expected_bars_per_bucket
                if is_complete or allow_partial_boundaries:
                    agg_bar = cls._build_bar(
                        current_bucket_candles,
                        current_bucket_open_ts,
                        target_ms,
                        target_interval,
                        symbol,
                    )
                    aggregated.append(agg_bar)
                current_bucket_open_ts = bucket_ts
                current_bucket_candles = [c]

        # Final bucket
        if current_bucket_candles:
            is_complete = len(current_bucket_candles) == expected_bars_per_bucket
            if is_complete or allow_partial_boundaries:
                agg_bar = cls._build_bar(
                    current_bucket_candles,
                    current_bucket_open_ts,
                    target_ms,
                    target_interval,
                    symbol,
                )
                aggregated.append(agg_bar)

        return aggregated

    @classmethod
    def _build_bar(
        cls,
        bucket_candles: List[CandleData],
        bucket_open_ts: int,
        interval_ms: int,
        interval_str: str,
        symbol: str,
    ) -> CandleData:
        bucket_close_ts = bucket_open_ts + interval_ms - 1
        dt_open = datetime.fromtimestamp(bucket_open_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        dt_close = datetime.fromtimestamp(bucket_close_ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        open_price = bucket_candles[0].open
        close_price = bucket_candles[-1].close
        high_price = max(c.high for c in bucket_candles)
        low_price = min(c.low for c in bucket_candles)
        volume = sum(c.volume for c in bucket_candles)
        quote_volume = sum(c.quote_volume for c in bucket_candles)
        trades_count = sum(c.trades_count for c in bucket_candles)
        taker_buy_base = sum(c.taker_buy_base_volume for c in bucket_candles)

        return CandleData(
            timestamp_open=bucket_open_ts,
            timestamp_close=bucket_close_ts,
            datetime_open_utc=dt_open,
            datetime_close_utc=dt_close,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            quote_volume=quote_volume,
            trades_count=trades_count,
            taker_buy_base_volume=taker_buy_base,
            is_closed=True,
            symbol=symbol,
            interval=interval_str,
            provenance=f"DERIVED_{interval_str.upper()}_FROM_1M",
        )


class BinanceHistoricalAdapter:
    """Acquires and caches public Binance Spot historical klines."""

    def __init__(self, config: Optional[ResearchLabConfig] = None):
        self.config = config or ResearchLabConfig()

    def fetch_klines_chunk(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[CandleData]:
        """Fetch a single chunk of klines from Binance public API with exponential retry."""
        if not self.config.allow_network_download:
            raise RuntimeError("Network download is disabled in ResearchLabConfig.")

        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_time_ms,
            "limit": limit,
        }
        if end_time_ms is not None:
            params["endTime"] = end_time_ms

        url = f"{self.config.binance_base_url}/klines?{urllib.parse.urlencode(params)}"
        last_err: Optional[Exception] = None

        for attempt in range(self.config.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "CBE-Research-Lab/1.0", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.config.request_timeout_seconds) as resp:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                    time.sleep(self.config.rate_limit_pause_seconds)
                    return self._parse_binance_raw_klines(raw_data, symbol, interval)
            except Exception as e:
                last_err = e
                backoff = self.config.retry_backoff_base_seconds * (2 ** attempt)
                logger.warning(f"Binance API attempt {attempt + 1} failed: {e}. Backing off {backoff:.2f}s...")
                time.sleep(backoff)

        raise RuntimeError(f"Failed to fetch Binance klines after {self.config.max_retries} attempts: {last_err}")

    def fetch_range(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        progress_callback: Optional[Any] = None,
    ) -> List[CandleData]:
        """Fetch a wide date range with deterministic pagination."""
        all_candles: List[CandleData] = []
        current_start = start_time_ms
        interval_ms = TimeframeAggregator.TIMEFRAME_MS.get(interval, 60_000)

        while current_start < end_time_ms:
            chunk = self.fetch_klines_chunk(
                symbol=symbol,
                interval=interval,
                start_time_ms=current_start,
                end_time_ms=end_time_ms,
                limit=1000,
            )
            if not chunk:
                break

            all_candles.extend(chunk)
            last_candle = chunk[-1]
            
            if progress_callback:
                progress_callback(len(all_candles), last_candle.datetime_open_utc)

            # Advance next window
            next_start = last_candle.timestamp_open + interval_ms
            if next_start <= current_start:
                break
            current_start = next_start

            if len(chunk) < 1000:
                # Reached end of available data
                break

        return all_candles

    def save_to_cache(self, candles: List[CandleData], cache_path: Path) -> None:
        """Save candles to local Parquet cache."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        records = [c.to_dict() for c in candles]
        df = pd.DataFrame.from_records(records)
        df.to_parquet(cache_path, index=False)
        logger.info(f"Cached {len(candles)} candles to {cache_path}")

    def load_from_cache(self, cache_path: Path) -> List[CandleData]:
        """Load candles from local Parquet cache."""
        if not cache_path.is_file():
            raise FileNotFoundError(f"Cache file not found: {cache_path}")
        df = pd.read_parquet(cache_path)
        candles = []
        for _, row in df.iterrows():
            c = CandleData(
                timestamp_open=int(row["timestamp_open"]),
                timestamp_close=int(row["timestamp_close"]),
                datetime_open_utc=str(row["datetime_open_utc"]),
                datetime_close_utc=str(row["datetime_close_utc"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                quote_volume=float(row.get("quote_volume", 0.0)),
                trades_count=int(row.get("trades_count", 0)),
                taker_buy_base_volume=float(row.get("taker_buy_base_volume", 0.0)),
                is_closed=bool(row.get("is_closed", True)),
                symbol=str(row.get("symbol", "BTCUSDT")),
                interval=str(row.get("interval", "1m")),
                provenance=str(row.get("provenance", "CACHE")),
            )
            candles.append(c)
        return candles

    def _parse_binance_raw_klines(
        self,
        raw_rows: List[List[Any]],
        symbol: str,
        interval: str,
    ) -> List[CandleData]:
        """Convert Binance raw kline array to typed CandleData instances."""
        candles: List[CandleData] = []
        for r in raw_rows:
            # Binance kline format:
            # 0: open_time, 1: open, 2: high, 3: low, 4: close, 5: volume, 6: close_time,
            # 7: quote_volume, 8: trades, 9: taker_buy_base, 10: taker_buy_quote, 11: ignore
            t_open = int(r[0])
            t_close = int(r[6])
            dt_open = datetime.fromtimestamp(t_open / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            dt_close = datetime.fromtimestamp(t_close / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            c = CandleData(
                timestamp_open=t_open,
                timestamp_close=t_close,
                datetime_open_utc=dt_open,
                datetime_close_utc=dt_close,
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
                quote_volume=float(r[7]),
                trades_count=int(r[8]),
                taker_buy_base_volume=float(r[9]),
                is_closed=True,
                symbol=symbol,
                interval=interval,
                provenance="BINANCE_SPOT_REST",
            )
            candles.append(c)
        return candles


class LiveCaptureEvidenceAdapter:
    """Read-only import adapter for previously verified Live Capture evidence."""

    @classmethod
    def load_evidence_candles(
        cls,
        evidence_dir: Path,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
    ) -> List[CandleData]:
        """Strictly read-only extraction of raw and committed recovery candles."""
        raw_file = evidence_dir / f"raw_candles_{symbol}_{interval}.jsonl"
        recovery_file = evidence_dir / f"recovery_candles_{symbol}_{interval}.jsonl"

        candles_by_ts: Dict[int, CandleData] = {}

        if raw_file.is_file():
            with open(raw_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        entry = json.loads(line_s)
                        c_dict = entry.get("candle", {})
                        c = cls._candle_from_dict(c_dict, source_provenance="LIVE_CAPTURE_RAW")
                        candles_by_ts[c.timestamp_open] = c
                    except Exception:
                        pass

        if recovery_file.is_file():
            with open(recovery_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        entry = json.loads(line_s)
                        c_dict = entry.get("candle", {})
                        c = cls._candle_from_dict(c_dict, source_provenance="LIVE_CAPTURE_RECOVERY")
                        # Do not overwrite raw candles if already present
                        if c.timestamp_open not in candles_by_ts:
                            candles_by_ts[c.timestamp_open] = c
                    except Exception:
                        pass

        sorted_candles = [candles_by_ts[ts] for ts in sorted(candles_by_ts.keys())]
        return sorted_candles

    @classmethod
    def _candle_from_dict(cls, d: Dict[str, Any], source_provenance: str) -> CandleData:
        return CandleData(
            timestamp_open=int(d["timestamp_open"]),
            timestamp_close=int(d["timestamp_close"]),
            datetime_open_utc=str(d["datetime_open_utc"]),
            datetime_close_utc=str(d["datetime_close_utc"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d["volume"]),
            quote_volume=float(d.get("quote_volume", 0.0)),
            trades_count=int(d.get("trades_count", 0)),
            taker_buy_base_volume=float(d.get("taker_buy_base_volume", 0.0)),
            is_closed=bool(d.get("is_closed", True)),
            symbol=str(d.get("symbol", "BTCUSDT")),
            interval=str(d.get("interval", "5m")),
            provenance=source_provenance,
        )
