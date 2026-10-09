"""CBE-0.8.0 Market Data Transport Adapters & Approval 3 Hard Safety Gates.

Defines:
- BaseMarketDataTransport interface.
- Strict Approval 3 gate: Live REST & WebSocket transports fail closed by default.
- MockMarketDataTransport: Fully deterministic, offline transport for comprehensive unit testing.
- BinanceSpotWebSocketAdapter: Full stdlib socket/ssl RFC 6455 framing client behind Approval 3 gate.
- BinanceSpotRestAdapter: Full stdlib urllib.request client behind Approval 3 gate.
- Exponential backoff with bounded jitter.
- Rate-limit handling (HTTP 429/418 simulation and handling).
- Stale feed detection and bounded inbound queue with backpressure.
- Maximum message size enforcement.
- Graceful shutdown lifecycle.
"""

from __future__ import annotations

import base64
import collections
import json
import logging
import os
import random
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
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

    def is_connected(self) -> bool:
        return self._connected


class BinanceSpotWebSocketAdapter(BinanceSpotLiveTransportBase):
    """Live WebSocket transport adapter for Binance Spot using standard library socket and ssl."""

    DEFAULT_HOST = "stream.binance.com"
    DEFAULT_PORT = 9443
    DEFAULT_PATH = "/ws/btcusdt@kline_5m"

    def __init__(
        self,
        config: ShadowCollectorConfig,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        path: str = DEFAULT_PATH,
        max_queue_size: int = 500,
        max_message_bytes: int = 65536,
        socket_timeout_sec: float = 5.0,
        only_finalized: bool = True,
        auto_reconnect: bool = True,
        max_reconnect_backoff_sec: float = 60.0,
        stale_timeout_sec: float = 900.0,
    ):
        super().__init__(config)
        self.host = host
        self.port = port
        self.path = path
        self.max_queue_size = max_queue_size
        self.max_message_bytes = max_message_bytes
        self.socket_timeout_sec = socket_timeout_sec
        self.only_finalized = only_finalized
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_backoff_sec = max_reconnect_backoff_sec
        self.stale_timeout_sec = stale_timeout_sec

        self._sock: Optional[ssl.SSLSocket] = None
        self._queue: collections.deque = collections.deque()
        self.total_messages_received = 0
        self.dropped_messages = 0
        self.intermediate_ticks_suppressed = 0
        self.reconnect_attempts = 0
        self._next_reconnect_time: float = 0.0
        self._last_message_time: float = time.time()
        self._last_ping_time: float = 0.0

    def connect(self) -> None:
        """Establish TLS connection and complete RFC 6455 WebSocket handshake."""
        self._verify_approval_3_gate()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

        try:
            raw_sock = socket.create_connection((self.host, self.port), timeout=self.socket_timeout_sec)
            ctx = ssl.create_default_context()
            self._sock = ctx.wrap_socket(raw_sock, server_hostname=self.host)
            self._sock.settimeout(self.socket_timeout_sec)
            self._perform_handshake()
            self._connected = True
            self.reconnect_attempts = 0
            self._next_reconnect_time = 0.0
            self._last_message_time = time.time()
            logger.info(f"WebSocket connected to {self.host}:{self.port}{self.path}")
        except Exception as e:
            self._connected = False
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
            raise TransportConnectionError(f"WebSocket connection to {self.host}:{self.port} failed: {e}") from e

    def _perform_handshake(self) -> None:
        """Perform HTTP 1.1 Upgrade to WebSocket (RFC 6455)."""
        nonce = os.urandom(16)
        key = base64.b64encode(nonce).decode("ascii")
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        if not self._sock:
            raise TransportConnectionError("Socket not initialized")
        self._sock.sendall(req.encode("ascii"))

        header_bytes = b""
        while b"\r\n\r\n" not in header_bytes:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise TransportConnectionError("Server closed connection during WebSocket handshake")
            header_bytes += chunk

        status_line = header_bytes.split(b"\r\n")[0].decode("ascii", errors="replace")
        if "101" not in status_line:
            raise TransportConnectionError(f"WebSocket handshake rejected by server: {status_line}")

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        """Send masked RFC 6455 frame from client to server."""
        if not self._sock:
            raise TransportConnectionError("Socket not connected")
        header = bytearray()
        header.append(0x80 | (opcode & 0x0F))

        length = len(payload)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(length.to_bytes(2, "big"))
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, "big"))

        mask_key = os.urandom(4)
        header.extend(mask_key)

        masked_payload = bytearray(length)
        for i in range(length):
            masked_payload[i] = payload[i] ^ mask_key[i % 4]

        self._sock.sendall(header + masked_payload)

    def _read_frame(self) -> Tuple[int, bytes]:
        """Read an incoming unmasked RFC 6455 frame from server."""
        if not self._sock:
            raise TransportConnectionError("Socket not connected")

        hdr = self._sock.recv(2)
        if not hdr or len(hdr) < 2:
            raise TransportConnectionError("Connection closed while reading frame header")

        b1, b2 = hdr[0], hdr[1]
        opcode = b1 & 0x0F
        has_mask = bool(b2 & 0x80)
        pay_len = b2 & 0x7F

        if pay_len == 126:
            ext = self._sock.recv(2)
            pay_len = int.from_bytes(ext, "big")
        elif pay_len == 127:
            ext = self._sock.recv(8)
            pay_len = int.from_bytes(ext, "big")

        if pay_len > self.max_message_bytes:
            raise OversizedMessageError(
                f"Incoming WebSocket frame ({pay_len} bytes) exceeds limit ({self.max_message_bytes})"
            )

        mask_key = None
        if has_mask:
            mask_key = self._sock.recv(4)

        payload_chunks = []
        received = 0
        while received < pay_len:
            to_read = min(4096, pay_len - received)
            chunk = self._sock.recv(to_read)
            if not chunk:
                raise TransportConnectionError("Connection dropped during payload read")
            payload_chunks.append(chunk)
            received += len(chunk)
        payload = b"".join(payload_chunks)

        if has_mask and mask_key:
            unmasked = bytearray(len(payload))
            for i in range(len(payload)):
                unmasked[i] = payload[i] ^ mask_key[i % 4]
            payload = bytes(unmasked)

        return opcode, payload

    def _handle_connection_loss(self, error: Optional[Exception] = None) -> None:
        """Safely clean up socket and initiate exponential backoff reconnection if enabled."""
        if self._sock:
            try:
                self._send_frame(0x8, b"")
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

        self._connected = False

        if self.auto_reconnect:
            self.reconnect_attempts += 1
            backoff = calculate_backoff(
                self.reconnect_attempts,
                base_sec=1.0,
                max_sec=self.max_reconnect_backoff_sec,
                jitter=True,
            )
            self._next_reconnect_time = time.time() + backoff
            err_details = f": {error}" if error else ""
            logger.warning(
                f"WebSocket connection lost{err_details}. Scheduled reconnect attempt {self.reconnect_attempts} in {backoff:.2f}s."
            )
        else:
            logger.warning("WebSocket connection closed (auto_reconnect disabled).")

    def poll_message(self) -> Optional[Any]:
        self._verify_approval_3_gate()

        # If disconnected, handle auto-reconnection
        if not self._connected or not self._sock:
            if not self.auto_reconnect:
                return None
            now = time.time()
            if now < self._next_reconnect_time:
                return None
            try:
                logger.info(f"Attempting WebSocket reconnect (attempt {self.reconnect_attempts})...")
                self.connect()
            except Exception as e:
                self.reconnect_attempts += 1
                backoff = calculate_backoff(
                    self.reconnect_attempts,
                    base_sec=1.0,
                    max_sec=self.max_reconnect_backoff_sec,
                    jitter=True,
                )
                self._next_reconnect_time = time.time() + backoff
                logger.warning(f"WebSocket reconnect attempt failed: {e}. Next attempt in {backoff:.2f}s.")
                return None

        # Check stale feed
        now = time.time()
        if now - self._last_message_time > self.stale_timeout_sec:
            logger.warning(
                f"Stale WebSocket feed: no messages for {now - self._last_message_time:.1f}s "
                f"(timeout: {self.stale_timeout_sec}s). Disconnecting to trigger reconnection."
            )
            self._handle_connection_loss(StaleFeedError(f"Stale feed timeout ({self.stale_timeout_sec}s)"))
            return None

        if self._queue:
            return self._queue.popleft()

        try:
            opcode, payload = self._read_frame()
            self._last_message_time = time.time()

            if opcode == 0x1:  # Text frame
                msg = json.loads(payload.decode("utf-8"))
                if self.only_finalized:
                    # Inspect if kline payload indicates unfinalized intermediate tick
                    k = msg.get("k", msg) if isinstance(msg, dict) else None
                    if isinstance(k, dict) and not k.get("x", False):
                        # Intermediate unfinalized tick - update liveness but do not yield candle
                        self.intermediate_ticks_suppressed += 1
                        return None
                self.total_messages_received += 1
                return msg
            elif opcode == 0x9:  # Ping frame -> respond with Pong
                self._send_frame(0xA, payload)
                logger.debug("Responded to RFC 6455 Ping frame with Pong.")
                return None
            elif opcode == 0xA:  # Pong frame
                logger.debug("Received RFC 6455 Pong frame.")
                return None
            elif opcode == 0x8:  # Close frame
                logger.info("Received RFC 6455 Close frame from server.")
                self._handle_connection_loss()
                return None
        except socket.timeout:
            return None
        except (TransportConnectionError, ConnectionResetError, BrokenPipeError, ssl.SSLError, OSError) as e:
            self._handle_connection_loss(e)
            return None
        except Exception as e:
            logger.warning(f"Unexpected WebSocket read error: {e}")
            self._handle_connection_loss(e)
            return None

        return None

    def disconnect(self) -> None:
        self.auto_reconnect = False
        if self._sock:
            try:
                self._send_frame(0x8, b"")
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._connected = False
        self._queue.clear()
        logger.info("WebSocket disconnected.")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "transport": "WebSocket",
            "approval_3_authorized": True,
            "queue_depth": len(self._queue),
            "total_received": self.total_messages_received,
            "dropped": self.dropped_messages,
            "intermediate_ticks_suppressed": self.intermediate_ticks_suppressed,
            "reconnect_attempts": self.reconnect_attempts,
            "last_message_time": self._last_message_time,
        }


class BinanceSpotRestAdapter(BinanceSpotLiveTransportBase):
    """Live REST transport adapter for Binance Spot using standard library urllib."""

    DEFAULT_BASE_URL = "https://api.binance.com/api/v3/klines"

    def __init__(
        self,
        config: ShadowCollectorConfig,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout_sec: float = 10.0,
    ):
        super().__init__(config)
        self.base_url = base_url
        self.request_timeout_sec = request_timeout_sec
        self.total_requests = 0
        self.failed_requests = 0

    def connect(self) -> None:
        self._verify_approval_3_gate()
        self._connected = True
        logger.info("REST adapter initialized with verified Approval 3 gate.")

    def disconnect(self) -> None:
        self._connected = False
        logger.info("REST adapter disconnected.")

    def fetch_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
    ) -> List[List[Any]]:
        """Fetch historical or gap klines via Binance Spot REST API."""
        self._verify_approval_3_gate()
        params = [
            ("symbol", symbol),
            ("interval", interval),
            ("limit", str(limit)),
        ]
        if start_time is not None:
            params.append(("startTime", str(start_time)))
        if end_time is not None:
            params.append(("endTime", str(end_time)))

        query_str = urllib.parse.urlencode(params)
        url = f"{self.base_url}?{query_str}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CoinBehaviorEngine/0.8.0 (SafetyStaging; OfflineByDesign)",
                "Accept": "application/json",
            },
        )

        self.total_requests += 1
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not isinstance(data, list):
                    raise ValueError(f"Expected JSON array of klines, got {type(data).__name__}")
                return data
        except urllib.error.HTTPError as e:
            self.failed_requests += 1
            if e.code in (429, 418):
                retry_after = float(e.headers.get("Retry-After", 60.0))
                raise RateLimitExceededError(f"Binance upstream rate limit {e.code}. Backoff: {retry_after}s") from e
            raise TransportConnectionError(f"HTTP error {e.code} querying {url}: {e.reason}") from e
        except Exception as e:
            self.failed_requests += 1
            raise TransportConnectionError(f"Failed to fetch klines from {url}: {e}") from e

    def fetch_validated_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        provenance: Union[str, Any] = "REST_GAP_RECOVERY",
    ) -> List[Any]:
        """Fetch klines via REST and return validated candles under explicit provenance."""
        from coin_behavior_engine.shadow_v080.market_data_contract import (
            BinanceSpotCandleValidator,
            MarketType,
        )

        raw_klines = self.fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        validated = []
        for raw in raw_klines:
            candle, violations = BinanceSpotCandleValidator.validate_raw(
                raw_record=raw,
                provenance=provenance,
                market_type=MarketType.SPOT,
            )
            if candle is not None and not violations:
                validated.append(candle)
        return validated

    def poll_message(self) -> Optional[Any]:
        self._verify_approval_3_gate()
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "transport": "REST",
            "approval_3_authorized": True,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "dropped": 0,
        }
