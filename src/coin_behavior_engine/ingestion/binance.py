"""Binance public historical market data provider implementation."""

from __future__ import annotations

import time
from typing import Any, List, Optional, Tuple, Union
import httpx
import pandas as pd

from coin_behavior_engine.ingestion.base import MarketDataProvider
from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_ms


class BinanceMarketDataProvider(MarketDataProvider):
    """Fetches spot historical market klines from Binance public API without API keys."""

    def __init__(
        self,
        base_url: str = "https://api.binance.com",
        klines_endpoint: str = "/api/v3/klines",
        rate_limit_pause_sec: float = 0.05,
        max_retries: int = 5,
        timeout_sec: float = 15.0
    ):
        self.base_url = base_url.rstrip("/")
        self.klines_endpoint = klines_endpoint
        self.rate_limit_pause_sec = rate_limit_pause_sec
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout_sec)

    def validate_response(self, raw_records: Any) -> bool:
        """Validate that raw response is a list of kline rows with expected length."""
        if not isinstance(raw_records, list):
            return False
        if len(raw_records) == 0:
            return True
        first = raw_records[0]
        # Binance klines have 12 elements
        return isinstance(first, list) and len(first) >= 11

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[Union[int, str, pd.Timestamp]] = None,
        end_time: Optional[Union[int, str, pd.Timestamp]] = None,
        limit: int = 1000
    ) -> List[List[Any]]:
        """Fetch up to `limit` klines starting at or after `start_time`."""
        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1000),
        }
        if start_time is not None:
            params["startTime"] = to_utc_ms(start_time)
        if end_time is not None:
            params["endTime"] = to_utc_ms(end_time)

        url = f"{self.base_url}{self.klines_endpoint}"
        retries = 0

        while retries <= self.max_retries:
            try:
                response = self.client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if not self.validate_response(data):
                        raise ValueError(f"Invalid Binance kline response format: {data[:1] if data else 'empty'}")
                    if self.rate_limit_pause_sec > 0:
                        time.sleep(self.rate_limit_pause_sec)
                    return data
                elif response.status_code in (429, 418):
                    wait = 2 ** (retries + 1)
                    logger.warning(f"Rate limited by Binance (status {response.status_code}). Backing off for {wait}s...")
                    time.sleep(wait)
                    retries += 1
                else:
                    logger.warning(f"Binance API returned status {response.status_code}: {response.text}")
                    retries += 1
                    time.sleep(1.0)
            except Exception as e:
                retries += 1
                wait = 1.5 * retries
                logger.warning(f"Request failed ({e}). Retry {retries}/{self.max_retries} in {wait:.1f}s...")
                time.sleep(wait)

        raise RuntimeError(f"Failed to fetch Binance klines after {self.max_retries} attempts for params {params}")

    def get_available_range(
        self,
        symbol: str,
        interval: str
    ) -> Tuple[Optional[int], Optional[int]]:
        """Retrieve earliest and latest available timestamps in milliseconds."""
        # Earliest candle
        first_batch = self.fetch_klines(symbol, interval, start_time=0, limit=1)
        earliest = first_batch[0][0] if first_batch else None

        # Latest candle
        latest_batch = self.fetch_klines(symbol, interval, limit=1)
        latest = latest_batch[0][0] if latest_batch else None

        return earliest, latest

    def close(self):
        """Close HTTP client."""
        self.client.close()
