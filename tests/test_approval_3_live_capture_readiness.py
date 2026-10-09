"""CBE-0.8.0 Approval 3 Live Capture Readiness & Verification Suite.

Tests:
1. Strict fail-closed safety pre-flight interlocks for live capture.
2. Binance WebSocket client RFC 6455 handshake, frame parsing, masking, and ping/pong.
3. Intermediate unfinalized tick filtering (only_finalized=True) to protect evidence ledger.
4. WebSocket connection loss detection and exponential backoff reconnection.
5. Stale feed timeout detection and automatic recovery.
6. Binance REST adapter rate-limit backoff (HTTP 429/418) handling.
7. End-to-end REST gap recovery with strict REST_GAP_RECOVERY provenance and audit logging.
8. LiveCaptureService lifecycle, signal handling, and fail-closed termination.
9. Deployment configuration compliance (read-only root, 300MB RAM, 0.25 CPU, restart="no", dedicated volume).

IMPORTANT: ALL TESTS ARE FULLY OFFLINE. ZERO LIVE NETWORK CALLS TO BINANCE.
"""

from __future__ import annotations

import io
import json
import os
import signal
import socket
import ssl
import time
import urllib.error
from pathlib import Path
from unittest import mock

import pytest
import yaml

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.live_capture_service import (
    LiveCaptureService,
    main as live_capture_main,
    verify_live_capture_preflight,
)
from coin_behavior_engine.shadow_v080.market_capture_engine import MarketCaptureEngineV080
from coin_behavior_engine.shadow_v080.market_data_contract import (
    BinanceSpotCandleValidator,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.transport_adapter import (
    BinanceSpotLiveTransportBase,
    BinanceSpotRestAdapter,
    BinanceSpotWebSocketAdapter,
    MockMarketDataTransport,
    OversizedMessageError,
    RateLimitExceededError,
    SafetyInterlockError,
    StaleFeedError,
    TransportConnectionError,
    calculate_backoff,
)


@pytest.fixture
def clean_env(monkeypatch):
    """Ensure clean environment for test execution."""
    vars_to_clear = [
        "CBE_APPROVAL_3_AUTHORIZED",
        "CBE_BINANCE_COLLECTION_ENABLED",
        "CBE_TRADING_DISABLED",
        "CBE_PROSPECTIVE_OBSERVATION_ENABLED",
        "CBE_APPROVAL_4_AUTHORIZED",
        "CBE_RECORD_LABEL",
        "CBE_ENV",
    ]
    for v in vars_to_clear:
        monkeypatch.delenv(v, raising=False)


@pytest.fixture
def authorized_env(monkeypatch, tmp_path):
    """Set strictly authorized environment for Approval 3 live capture."""
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")
    monkeypatch.setenv("CBE_SHADOW_DATA_DIR", str(tmp_path / "live_capture"))
    monkeypatch.setenv("CBE_RAW_MARKET_DIR", str(tmp_path / "live_capture" / "raw_market"))
    monkeypatch.setenv("CBE_QUARANTINE_DIR", str(tmp_path / "live_capture" / "quarantine"))


# ==============================================================================
# 1. FAIL-CLOSED SAFETY PRE-FLIGHT INTERLOCKS
# ==============================================================================

def test_preflight_missing_approval_3(monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

    is_valid, violations = verify_live_capture_preflight()
    assert not is_valid
    assert any("Approval 3 is NOT authorized" in v for v in violations)


def test_preflight_collection_disabled(monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

    is_valid, violations = verify_live_capture_preflight()
    assert not is_valid
    assert any("Binance collection is disabled" in v for v in violations)


def test_preflight_trading_not_disabled(monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "false")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

    is_valid, violations = verify_live_capture_preflight()
    assert not is_valid
    assert any("Trading interlock violated" in v for v in violations)


def test_preflight_prospective_scoring_violation(monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

    is_valid, violations = verify_live_capture_preflight()
    assert not is_valid
    assert any("Prospective scoring must be disabled" in v for v in violations)
    assert any("Approval 4 is pending" in v for v in violations)


def test_preflight_invalid_record_label(monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "UNVERIFIED_DATA")

    is_valid, violations = verify_live_capture_preflight()
    assert not is_valid
    assert any("CBE_RECORD_LABEL must be 'LIVE_BINANCE_SPOT'" in v for v in violations)


def test_live_capture_service_fail_closed_on_unauthorized(clean_env):
    with pytest.raises(SafetyInterlockError) as exc_info:
        LiveCaptureService()
    assert "LiveCaptureService fail-closed" in str(exc_info.value)


def test_live_capture_main_exits_one_on_unauthorized(clean_env, monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "false")
    exit_code = live_capture_main()
    assert exit_code == 1


# ==============================================================================
# 2. WEBSOCKET TRANSPORT FRAMING, HANDSHAKE & MASKING
# ==============================================================================

class MockSocket:
    """In-memory mock socket simulating server RFC 6455 WebSocket responses."""

    def __init__(self, incoming_data: bytes = b"", simulate_eof: bool = False):
        self.incoming = io.BytesIO(incoming_data)
        self.outgoing = io.BytesIO()
        self.closed = False
        self.simulate_eof = simulate_eof
        self.timeout = 5.0

    def settimeout(self, t: float) -> None:
        self.timeout = t

    def sendall(self, data: bytes) -> None:
        if self.closed:
            raise BrokenPipeError("Socket closed")
        self.outgoing.write(data)

    def recv(self, bufsize: int) -> bytes:
        if self.closed:
            return b""
        data = self.incoming.read(bufsize)
        if not data and self.incoming.tell() >= len(self.incoming.getvalue()):
            if self.simulate_eof:
                return b""
            # Simulate socket timeout if empty
            raise socket.timeout("timed out")
        return data

    def close(self) -> None:
        self.closed = True


def make_server_frame(opcode: int, payload: bytes) -> bytes:
    """Helper to encode an unmasked RFC 6455 server-to-client frame."""
    frame = bytearray()
    frame.append(0x80 | (opcode & 0x0F))
    length = len(payload)
    if length <= 125:
        frame.append(length)
    elif length <= 65535:
        frame.append(126)
        frame.extend(length.to_bytes(2, "big"))
    else:
        frame.append(127)
        frame.extend(length.to_bytes(8, "big"))
    frame.extend(payload)
    return bytes(frame)


def test_websocket_handshake_and_connect(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotWebSocketAdapter(config)

    handshake_resp = (
        b"HTTP/1.1 101 Switching Protocols\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\n\r\n"
    )
    mock_sock = MockSocket(handshake_resp)

    with mock.patch("socket.create_connection", return_value=mock.MagicMock()), \
         mock.patch("ssl.create_default_context") as mock_ssl_ctx:
        mock_ssl_ctx.return_value.wrap_socket.return_value = mock_sock
        adapter.connect()
        assert adapter.is_connected()
        assert b"Upgrade: websocket" in mock_sock.outgoing.getvalue()
        assert b"Sec-WebSocket-Key:" in mock_sock.outgoing.getvalue()


def test_websocket_client_sends_masked_frames(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotWebSocketAdapter(config)
    mock_sock = MockSocket()
    adapter._sock = mock_sock
    adapter._connected = True

    # Send client Pong frame (opcode 0xA)
    test_payload = b"ping_payload"
    adapter._send_frame(0xA, test_payload)

    sent_data = mock_sock.outgoing.getvalue()
    assert len(sent_data) > 0
    # First byte must have FIN bit (0x80) and opcode 0xA
    assert sent_data[0] == 0x8A
    # Second byte must have MASK bit set (0x80)
    assert sent_data[1] & 0x80 != 0


# ==============================================================================
# 3. INTERMEDIATE TICK FILTERING & PING/PONG
# ==============================================================================

def test_websocket_suppresses_intermediate_ticks(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotWebSocketAdapter(config, only_finalized=True)

    # 1. Unfinalized kline tick ("x": false)
    tick_unfinalized = {
        "e": "kline",
        "E": 1700000000000,
        "s": "BTCUSDT",
        "k": {
            "t": 1700000000000,
            "T": 1700000299999,
            "s": "BTCUSDT",
            "i": "5m",
            "o": "35000.0",
            "c": "35050.0",
            "h": "35100.0",
            "l": "34950.0",
            "v": "10.5",
            "x": False,
            "q": "367500.0",
            "n": 50,
            "V": "5.0",
        },
    }
    # 2. Finalized closed candle ("x": true)
    tick_finalized = {
        "e": "kline",
        "E": 1700000300000,
        "s": "BTCUSDT",
        "k": {
            "t": 1700000000000,
            "T": 1700000299999,
            "s": "BTCUSDT",
            "i": "5m",
            "o": "35000.0",
            "c": "35080.0",
            "h": "35120.0",
            "l": "34950.0",
            "v": "25.0",
            "x": True,
            "q": "875000.0",
            "n": 120,
            "V": "12.0",
        },
    }

    raw_frame_1 = make_server_frame(0x1, json.dumps(tick_unfinalized).encode("utf-8"))
    raw_frame_2 = make_server_frame(0x1, json.dumps(tick_finalized).encode("utf-8"))

    mock_sock = MockSocket(raw_frame_1 + raw_frame_2)
    adapter._sock = mock_sock
    adapter._connected = True

    # First poll reads unfinalized tick -> must return None and suppress
    msg1 = adapter.poll_message()
    assert msg1 is None
    assert adapter.intermediate_ticks_suppressed == 1

    # Second poll reads finalized candle -> must return payload
    msg2 = adapter.poll_message()
    assert msg2 is not None
    assert msg2["k"]["x"] is True
    assert adapter.total_messages_received == 1


def test_websocket_handles_ping_with_masked_pong(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotWebSocketAdapter(config)
    ping_payload = b"binance_ping_12345"
    ping_frame = make_server_frame(0x9, ping_payload)

    mock_sock = MockSocket(ping_frame)
    adapter._sock = mock_sock
    adapter._connected = True

    # Polling Ping frame must respond with Pong and return None
    res = adapter.poll_message()
    assert res is None

    sent_data = mock_sock.outgoing.getvalue()
    assert len(sent_data) > 0
    # Opcode must be 0xA (Pong)
    assert sent_data[0] == 0x8A


def test_websocket_handles_close_frame(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotWebSocketAdapter(config)
    close_frame = make_server_frame(0x8, b"")

    mock_sock = MockSocket(close_frame)
    adapter._sock = mock_sock
    adapter._connected = True

    res = adapter.poll_message()
    assert res is None
    assert not adapter.is_connected()


# ==============================================================================
# 4. CONNECTION LOSS & BOUNDED EXPONENTIAL BACKOFF
# ==============================================================================

def test_websocket_reconnection_backoff(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotWebSocketAdapter(
        config,
        auto_reconnect=True,
        max_reconnect_backoff_sec=60.0,
    )
    # Simulate connection established then dropped during frame read
    mock_sock = MockSocket(b"", simulate_eof=True)  # EOF causes TransportConnectionError
    adapter._sock = mock_sock
    adapter._connected = True

    # Poll fails and triggers backoff schedule
    res = adapter.poll_message()
    assert res is None
    assert not adapter.is_connected()
    assert adapter.reconnect_attempts == 1
    assert adapter._next_reconnect_time > time.time()

    # Immediate next poll should return None because backoff has not expired
    res2 = adapter.poll_message()
    assert res2 is None
    assert not adapter.is_connected()

    # Fast forward time to expire backoff and mock successful reconnect
    adapter._next_reconnect_time = time.time() - 1.0
    with mock.patch.object(adapter, "connect") as mock_connect:
        adapter.poll_message()
        mock_connect.assert_called_once()


def test_websocket_stale_feed_timeout(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotWebSocketAdapter(
        config,
        stale_timeout_sec=10.0,
        auto_reconnect=True,
    )
    mock_sock = MockSocket()
    adapter._sock = mock_sock
    adapter._connected = True
    adapter._last_message_time = time.time() - 20.0  # Stale

    res = adapter.poll_message()
    assert res is None
    assert not adapter.is_connected()
    assert adapter.reconnect_attempts == 1


# ==============================================================================
# 5. REST ADAPTER & RATE LIMIT HANDLING
# ==============================================================================

def test_rest_adapter_rate_limit_429(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotRestAdapter(config)
    adapter.connect()

    # Simulate HTTP 429 Too Many Requests with Retry-After header
    http_error = urllib.error.HTTPError(
        url="https://api.binance.com/api/v3/klines",
        code=429,
        msg="Too Many Requests",
        hdrs={"Retry-After": "45"},
        fp=io.BytesIO(b'{"code": -1003, "msg": "Way too many requests"}'),
    )

    with mock.patch("urllib.request.urlopen", side_effect=http_error):
        with pytest.raises(RateLimitExceededError) as exc_info:
            adapter.fetch_klines(symbol="BTCUSDT", interval="5m")
        assert "429" in str(exc_info.value)
        assert "45" in str(exc_info.value)


def test_rest_adapter_fetch_validated_klines(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    adapter = BinanceSpotRestAdapter(config)
    adapter.connect()

    # Binance Spot 5m kline array format (timestamp 1700000100000 is aligned to 5m)
    mock_kline = [
        1700000100000,       # 0: Open time
        "35000.0",           # 1: Open
        "35200.0",           # 2: High
        "34900.0",           # 3: Low
        "35150.0",           # 4: Close
        "150.5",             # 5: Volume
        1700000399999,       # 6: Close time
        "5280000.0",         # 7: Quote asset volume
        1200,                # 8: Number of trades
        "75.25",             # 9: Taker buy base asset volume
        "2640000.0",         # 10: Taker buy quote asset volume
        "0",                 # 11: Ignore
    ]

    mock_resp = io.BytesIO(json.dumps([mock_kline]).encode("utf-8"))
    mock_resp.headers = {}

    with mock.patch("urllib.request.urlopen", return_value=mock_resp):
        candles = adapter.fetch_validated_klines(
            symbol="BTCUSDT",
            interval="5m",
            start_time=1700000100000,
            end_time=1700000399999,
            provenance=ProvenanceSource.REST_GAP_RECOVERY,
        )
        assert len(candles) == 1
        c = candles[0]
        assert isinstance(c, ValidatedCandle)
        assert c.timestamp_open == 1700000100000
        assert c.provenance == ProvenanceSource.REST_GAP_RECOVERY.value
        assert c.open == "35000.0"
        assert c.close == "35150.0"


# ==============================================================================
# 6. END-TO-END GAP RECOVERY VIA REST
# ==============================================================================

def test_engine_gap_detection_and_rest_recovery(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
        full_warmup_bars=10,
    )
    engine = MarketCaptureEngineV080(config)

    t0 = 1700000100000
    t1 = t0 + 300000
    t2 = t1 + 300000  # Missing!
    t3 = t2 + 300000

    def make_raw(ts_open):
        return {
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": ts_open,
                "T": ts_open + 299999,
                "s": "BTCUSDT",
                "i": "5m",
                "o": "35000.0",
                "c": "35050.0",
                "h": "35100.0",
                "l": "34950.0",
                "v": "10.0",
                "x": True,
                "q": "350500.0",
                "n": 50,
                "V": "5.0",
            },
        }

    # Process candle 0 and candle 1 (contiguous)
    r0 = engine.process_raw_message(make_raw(t0))
    assert r0["status"] == "PERSISTED"
    assert r0["is_contiguous"] is True

    r1 = engine.process_raw_message(make_raw(t1))
    assert r1["status"] == "PERSISTED"
    assert r1["is_contiguous"] is True
    assert engine.gap_detector.contiguous_closed_bars == 2

    # Process candle 3 (skipping candle 2) -> Gap detected!
    r3 = engine.process_raw_message(make_raw(t3))
    assert r3["status"] == "PERSISTED"
    assert r3["is_contiguous"] is False
    assert r3["gap_detected"] is True
    assert engine.gap_detector.has_unrecovered_gaps
    assert engine.gap_detector.unrecovered_gaps_count == 1
    assert engine.gap_detector.contiguous_closed_bars == 1  # Reset!

    gap_event = engine.gap_detector.gaps[0]
    gap_id = gap_event.gap_id

    # Create mock REST adapter to recover the missing candle
    mock_rest = mock.MagicMock(spec=BinanceSpotRestAdapter)
    mock_rest.fetch_klines.return_value = [
        [
            t2, "35050.0", "35150.0", "35000.0", "35100.0", "12.0",
            t2 + 299999, "421200.0", 60, "6.0", "210600.0", "0"
        ]
    ]

    ok, msg = engine.recover_gap_via_rest(gap_id, mock_rest)
    assert ok, f"Recovery failed: {msg}"
    assert not engine.gap_detector.has_unrecovered_gaps
    assert gap_event.recovered is True
    assert gap_event.recovery_provenance == ProvenanceSource.REST_GAP_RECOVERY.value

    # Verify audit file was written
    audit_file = config.quarantine_dir / "gap_recovery_audit.jsonl"
    assert audit_file.exists()
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    audit_entry = json.loads(lines[0])
    assert audit_entry["gap_id"] == gap_id
    assert audit_entry["recovery_provenance"] == "REST_GAP_RECOVERY"


# ==============================================================================
# 7. LIVE CAPTURE SERVICE LIFECYCLE & SIGNAL HANDLING
# ==============================================================================

def test_live_capture_service_max_ticks_and_shutdown(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
        full_warmup_bars=5,
    )
    mock_transport = MockMarketDataTransport(config)

    service = LiveCaptureService(config=config, transport=mock_transport)

    # Inject 3 closed candles (aligned to 5m)
    base_ts = 1700000100000
    mock_transport.connect()
    for i in range(3):
        ts = base_ts + (i * 300000)
        mock_transport.inject_message({
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": ts,
                "T": ts + 299999,
                "s": "BTCUSDT",
                "i": "5m",
                "o": "35000.0",
                "c": "35050.0",
                "h": "35100.0",
                "l": "34950.0",
                "v": "10.0",
                "x": True,
                "q": "350500.0",
                "n": 50,
                "V": "5.0",
            },
        })

    # Run for max 3 ticks
    exit_code = service.run(max_ticks=3)
    assert exit_code == 0
    assert service.engine.total_persisted == 3
    assert service.engine.gap_detector.contiguous_closed_bars == 3
    assert not service.transport.is_connected()


def test_live_capture_service_sigterm_handling(authorized_env, tmp_path):
    config = ShadowCollectorConfig(
        approval_3_authorized=True,
        shadow_data_dir=tmp_path / "live_capture",
    )
    mock_transport = MockMarketDataTransport(config)
    service = LiveCaptureService(config=config, transport=mock_transport)

    # Trigger stop via signal handler
    service._handle_signal(signal.SIGINT, None)
    assert service._stop_requested is True


# ==============================================================================
# 8. COMPOSE DEPLOYMENT SPECIFICATION COMPLIANCE
# ==============================================================================

def test_compose_live_capture_deployment_invariants():
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-live-capture.yaml")
    assert compose_path.exists(), "Compose file must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    svc = doc["services"]["cbe-080-live-capture"]

    # Invariants
    assert svc["restart"] == "no", "Restart policy must be 'no'"
    assert svc["read_only"] is True, "Root filesystem must be read_only"
    assert svc["user"] == "1000:1000", "Runtime user must be 1000:1000"
    assert svc["pids_limit"] == 64, "PIDs limit must be 64"
    assert svc["mem_limit"] == "300m", "Memory limit must be 300m"
    assert svc["cpus"] == 0.25, "CPU quota must be 0.25"
    assert "ports" not in svc, "No public host ports exposed"

    # Volume mounts
    volumes = svc["volumes"]
    assert any("cbe_080_live_capture_data:/app/data/live_capture:rw" in v for v in volumes)
    assert not any("cbe_080_shadow_data" in v for v in volumes), "Zero mounts to shadow_data"

    # Environment fail-closed defaults
    env_list = svc["environment"]
    env_dict = {}
    for item in env_list:
        if "=" in item:
            k, v = item.split("=", 1)
            env_dict[k] = v

    assert env_dict.get("CBE_APPROVAL_3_AUTHORIZED") == "false", "Default must fail closed"
    assert env_dict.get("CBE_BINANCE_COLLECTION_ENABLED") == "false", "Default must fail closed"
    assert env_dict.get("CBE_TRADING_DISABLED") == "true", "Trading permanently prohibited"
    assert env_dict.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "false", "Scoring disabled"
    assert env_dict.get("CBE_APPROVAL_4_AUTHORIZED") == "false", "Approval 4 isolated"
    assert env_dict.get("CBE_RECORD_LABEL") == "LIVE_BINANCE_SPOT"
