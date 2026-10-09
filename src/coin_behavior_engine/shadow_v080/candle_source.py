"""Candle Data Source Abstractions & Network Safety Interlock for CBE-0.8.0.

Provides:
- BaseCandleSource interface.
- OfflineFixtureSource: reads from in-memory fixtures or historical parquet/csv files.
- ReadOnlyLiveBinanceSource: strictly read-only public REST client for Binance spot klines.
  Protected by a HARD SAFETY INTERLOCK that fails closed unless network and live shadow
  are explicitly authorized.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request
import json

from coin_behavior_engine.candidate_v080.feed_adapter import (
    CANDLE_INTERVAL_MS,
    CandleData,
)
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig

logger = logging.getLogger("cbe_candle_source")


class SafetyInterlockError(Exception):
    """Raised when an attempt is made to execute live network calls without explicit opt-in."""
    pass


class SourceDataError(Exception):
    """Raised when an upstream candle stream provides corrupted or malformed data."""
    pass


class BaseCandleSource(ABC):
    """Abstract base class for candle data ingestion."""

    @abstractmethod
    def fetch_next_candle(self) -> Optional[CandleData]:
        """Retrieve the next closed candle."""
        pass

    @abstractmethod
    def bootstrap_history(self, count: int = 350) -> List[CandleData]:
        """Retrieve up to `count` historical closed candles for buffer initialization."""
        pass


class OfflineFixtureSource(BaseCandleSource):
    """Offline deterministic candle source consuming pre-loaded fixtures."""

    def __init__(self, candles: List[CandleData]):
        self.candles = list(candles)
        self.cursor = 0

    def fetch_next_candle(self) -> Optional[CandleData]:
        if self.cursor < len(self.candles):
            candle = self.candles[self.cursor]
            self.cursor += 1
            return candle
        return None

    def bootstrap_history(self, count: int = 350) -> List[CandleData]:
        limit = min(count, len(self.candles))
        boot = self.candles[:limit]
        self.cursor = limit
        return boot

    def reset(self) -> None:
        self.cursor = 0


class ReadOnlyLiveBinanceSource(BaseCandleSource):
    """Strictly read-only public REST client for Binance BTCUSDT spot klines.

    HARD SAFETY INTERLOCK:
    Refuses any network call unless `config.network_enabled == True` AND
    `config.live_shadow_enabled == True`.
    """

    BASE_URL = "https://api.binance.com/api/v3/klines"

    def __init__(
        self,
        config: ShadowCollectorConfig,
        timeout_sec: float = 5.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ):
        self.config = config
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.last_request_time: float = 0.0
        self.request_count: int = 0

    def _verify_safety_interlock(self) -> None:
        """Fail closed if live network access is disabled."""
        if not self.config.network_enabled:
            raise SafetyInterlockError(
                "HARD SAFETY INTERLOCK: Network access is disabled (network_enabled=False)."
            )
        if not self.config.live_shadow_enabled:
            raise SafetyInterlockError(
                "HARD SAFETY INTERLOCK: Live shadow observation is disabled (live_shadow_enabled=False)."
            )
        if self.config.trading_enabled:
            raise SafetyInterlockError(
                "HARD SAFETY INTERLOCK: Trading is permanently prohibited."
            )

    def _execute_public_request(self, params: Dict[str, Any]) -> List[List[Any]]:
        """Execute a rate-limited, read-only GET request against Binance public klines."""
        self._verify_safety_interlock()

        # Rate limiting: max 2 requests per minute (min 20 seconds between calls)
        min_interval = 60.0 / max(1, self.config.max_network_requests_per_minute)
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        query = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}?{query}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CoinBehaviorEngine-Shadow/0.8.0 (ReadOnlyResearch)",
                "Accept": "application/json",
            },
        )

        last_err = None
        for attempt in range(self.max_retries):
            try:
                self.last_request_time = time.time()
                self.request_count += 1
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    if resp.status != 200:
                        raise SourceDataError(f"HTTP {resp.status} from Binance kline API")
                    data = json.loads(resp.read().decode("utf-8"))
                    return data
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                last_err = e
                sleep_sec = self.backoff_factor ** attempt
                time.sleep(sleep_sec)

        raise SourceDataError(f"Failed to fetch klines after {self.max_retries} attempts: {last_err}")

    def bootstrap_history(self, count: int = 350) -> List[CandleData]:
        """Fetch up to `count` historical closed candles for initial buffer bootstrap."""
        self._verify_safety_interlock()
        limit = min(count, 1000)
        params = {
            "symbol": self.config.symbol,
            "interval": self.config.interval,
            "limit": limit,
        }
        raw_klines = self._execute_public_request(params)
        candles = self._parse_binance_klines(raw_klines)
        # Drop the last candle if it's currently open
        now_ms = int(time.time() * 1000)
        closed_candles = [c for c in candles if c.timestamp_close <= now_ms]
        return closed_candles[-count:]

    def fetch_next_candle(self) -> Optional[CandleData]:
        """Fetch the most recently closed 5-minute candle."""
        self._verify_safety_interlock()
        params = {
            "symbol": self.config.symbol,
            "interval": self.config.interval,
            "limit": 2,
        }
        raw_klines = self._execute_public_request(params)
        candles = self._parse_binance_klines(raw_klines)
        now_ms = int(time.time() * 1000)
        closed = [c for c in candles if c.timestamp_close <= now_ms]
        if closed:
            return closed[-1]
        return None

    def _parse_binance_klines(self, klines: List[List[Any]]) -> List[CandleData]:
        """Parse Binance array kline format into validated CandleData objects."""
        candles = []
        for k in klines:
            try:
                t_open = int(k[0])
                t_close = int(k[6])
                o = float(k[1])
                h = float(k[2])
                l = float(k[3])
                c = float(k[4])
                v = float(k[5])  # BTC base asset volume
                rec_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                dt_open = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_open / 1000.0))
                dt_close = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_close / 1000.0))

                candles.append(
                    CandleData(
                        timestamp_open=t_open,
                        timestamp_close=t_close,
                        datetime_open=dt_open,
                        datetime_close=dt_close,
                        open=o,
                        high=h,
                        low=l,
                        close=c,
                        volume=v,
                        is_closed=True,
                        receipt_timestamp_utc=rec_utc,
                    )
                )
            except (ValueError, IndexError) as e:
                raise SourceDataError(f"Malformed kline entry from Binance: {k} ({e})") from e

        return candles
