"""CBE-0.8.0 Market Data Transport Adapters & Approval 3 Hard Safety Gates.

Defines:
- BaseMarketDataTransport interface.
- Strict Approval 3 gate: Live REST & WebSocket transports fail closed by default.
- MockMarketDataTransport: Fully deterministic, offline transport for comprehensive unit testing.
- Exponential backoff with bounded jitter.
- Rate-limit handling (HTTP 429/418 simulation).
- Stale feed detection and bounded inbound queue with backpressure.
- Maximum message size enforcement.
- Graceful shutdown lifecycle.
"""

from __future__ import annotations

import collections
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig

logger = logging.getLogger("cbe_transport_adapter")


class SafetyInterlockError(Exception):
    """Raised when an attempt is made to initiate live network transport without explicit Approval 3."""
    pass


class TransportConnectionError(Exception):
    """Raised when transport connection fails or drops unexpectedly."""
    pass


class RateLimitExceededError(Exception):
    """Raised when upstream rate limit (HTTP 429/418) is triggered."""
    pass


class StaleFeedError(Exception):
    """Raised when no message is received within the configured stale feed timeout."""
    pass


class QueueOverflowError(Exception):
    """Raised when inbound message queue exceeds configured capacity."""
    pass


class OversizedMessageError(Exception):
    """Raised when an incoming message frame exceeds the maximum allowed payload size."""
    pass


def calculate_backoff(
    attempt: int,
    base_sec: float = 1.0,
    max_sec: float = 60.0,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff with bounded full jitter."""
    exp = min(max_sec, base_sec * (2.0 ** attempt))
    if jitter:
        return random.uniform(0.0, exp)
    return exp


class BaseMarketDataTransport(ABC):
    """Abstract interface for Binance market data transports."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection or fail closed."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Gracefully terminate connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is actively connected."""
        pass

    @abstractmethod
    def poll_message(self) -> Optional[Any]:
        """Poll the next raw message from the inbound queue."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic and health telemetry."""
        pass


class MockMarketDataTransport(BaseMarketDataTransport):
    """Deterministic, offline transport for test execution and simulation."""

    def __init__(
        self,
        config: Optional[ShadowCollectorConfig] = None,
        max_queue_size: int = 500,
        stale_timeout_sec: float = 900.0,
        max_message_bytes: int = 65536,
    ):
        self.config = config or ShadowCollectorConfig()
        self.max_queue_size = max_queue_size
        self.stale_timeout_sec = stale_timeout_sec
        self.max_message_bytes = max_message_bytes

        self._connected = False
        self._queue: collections.deque = collections.deque()
        self._last_message_time: float = time.time()
        self.total_messages_received = 0
        self.dropped_messages = 0
        self.reconnect_attempts = 0
        self.is_rate_limited = False
        self.rate_limit_backoff_sec = 0.0

    def connect(self) -> None:
        self._connected = True
        self._last_message_time = time.time()
        logger.info("MockMarketDataTransport connected.")

    def disconnect(self) -> None:
        self._connected = False
        self._queue.clear()
        logger.info("MockMarketDataTransport disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def inject_message(self, raw_message: Any) -> None:
        """Inject a raw message into the mock queue, enforcing size and capacity limits."""
        if not self._connected:
            raise TransportConnectionError("Cannot inject message while transport is disconnected.")

        # Check payload size
        msg_str = str(raw_message)
        if len(msg_str.encode("utf-8")) > self.max_message_bytes:
            raise OversizedMessageError(
                f"Message size {len(msg_str.encode('utf-8'))} bytes exceeds limit {self.max_message_bytes}"
            )

        # Check queue overflow
        if len(self._queue) >= self.max_queue_size:
            self.dropped_messages += 1
            raise QueueOverflowError(
                f"Inbound queue capacity reached ({self.max_queue_size}). Backpressure engaged."
            )

        self._queue.append(raw_message)
        self.total_messages_received += 1
        self._last_message_time = time.time()

    def simulate_rate_limit(self, retry_after_sec: float = 60.0) -> None:
        """Simulate an upstream HTTP 429/418 rate limit."""
        self.is_rate_limited = True
        self.rate_limit_backoff_sec = retry_after_sec

    def check_stale_feed(self, current_time: Optional[float] = None) -> bool:
        """Check if transport has exceeded the stale feed timeout."""
        now = current_time if current_time is not None else time.time()
        if self._connected and (now - self._last_message_time > self.stale_timeout_sec):
            return True
        return False

    def poll_message(self) -> Optional[Any]:
        if not self._connected:
            return None
        if self.is_rate_limited:
            raise RateLimitExceededError(
                f"Upstream rate limit active. Backoff required: {self.rate_limit_backoff_sec}s"
            )
        if self._queue:
            return self._queue.popleft()
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "queue_depth": len(self._queue),
            "total_received": self.total_messages_received,
            "dropped": self.dropped_messages,
            "is_rate_limited": self.is_rate_limited,
            "last_message_time": self._last_message_time,
        }


class BinanceSpotLiveTransportBase(BaseMarketDataTransport, ABC):
    """Base class for live Binance transports with strict Approval 3 fail-closed interlocks."""

    def __init__(self, config: ShadowCollectorConfig):
        self.config = config
        self._connected = False
        self._verify_approval_3_gate()

    def _verify_approval_3_gate(self) -> None:
        """Strictly fail closed unless Approval 3 is explicitly authorized."""
        # 1. Config flag check
        if not getattr(self.config, "approval_3_authorized", False):
            raise SafetyInterlockError(
                "HARD SAFETY INTERLOCK: Live Binance market data capture is PROHIBITED. "
                "Approval 3 has not been granted (config.approval_3_authorized=False)."
            )
        # 2. Environment variable check
        if os.environ.get("CBE_APPROVAL_3_AUTHORIZED") != "true":
            raise SafetyInterlockError(
                "HARD SAFETY INTERLOCK: Live Binance market data capture is PROHIBITED. "
                "Approval 3 environment variable CBE_APPROVAL_3_AUTHORIZED is not 'true'."
            )
        # 3. Collection enabled check
        if os.environ.get("CBE_BINANCE_COLLECTION_ENABLED") != "true":
            raise SafetyInterlockError(
                "HARD SAFETY INTERLOCK: Binance collection is disabled (CBE_BINANCE_COLLECTION_ENABLED != 'true')."
            )
        # 4. Trading permanently prohibited check
        if self.config.trading_enabled or os.environ.get("CBE_TRADING_DISABLED") != "true":
            raise SafetyInterlockError(
                "HARD SAFETY INTERLOCK: Trading is permanently prohibited."
            )

    def connect(self) -> None:
        self._verify_approval_3_gate()
        raise NotImplementedError(
            "Live Binance transport network connection is NOT implemented in Sprint 09.14 (Preparation only)."
        )

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected


class BinanceSpotWebSocketAdapter(BinanceSpotLiveTransportBase):
    """Live WebSocket transport adapter for Binance Spot wss://stream.binance.com:9443/ws/btcusdt@kline_5m."""

    def poll_message(self) -> Optional[Any]:
        self._verify_approval_3_gate()
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {"connected": False, "transport": "WebSocket", "approval_3_authorized": False}


class BinanceSpotRestAdapter(BinanceSpotLiveTransportBase):
    """Live REST transport adapter for Binance Spot https://api.binance.com/api/v3/klines."""

    def poll_message(self) -> Optional[Any]:
        self._verify_approval_3_gate()
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {"connected": False, "transport": "REST", "approval_3_authorized": False}
