"""Abstract base provider for cryptocurrency market data ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd


class MarketDataProvider(ABC):
    """Abstract interface for historical market data providers."""

    @abstractmethod
    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[Union[int, str, pd.Timestamp]] = None,
        end_time: Optional[Union[int, str, pd.Timestamp]] = None,
        limit: int = 1000
    ) -> List[List[Any]]:
        """Fetch a batch of kline / candlestick records from the provider."""
        pass

    @abstractmethod
    def get_available_range(
        self,
        symbol: str,
        interval: str
    ) -> Tuple[Optional[int], Optional[int]]:
        """Return (earliest_timestamp_ms, latest_timestamp_ms) available from provider."""
        pass

    @abstractmethod
    def validate_response(self, raw_records: Any) -> bool:
        """Validate raw response structure against expected schema."""
        pass
