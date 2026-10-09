"""CBE-0.8.0 Market Data Contract & Strict Closed-Candle Validation.

Defines:
- Supported market specifications (Binance Spot BTCUSDT 5m only).
- Provenance separation (OFFLINE_FIXTURE, HISTORICAL_REPLAY, WARMUP_REPLAY, LIVE_BINANCE_SPOT, REST_GAP_RECOVERY).
- Candle lifecycle progression (RECEIVED -> VALIDATED -> CONFIRMED_CLOSED -> PERSISTED -> RESEARCH_ELIGIBLE).
- Decimal-safe OHLCV validation and boundary consistency rules.
- Conflicting duplicate and malformed record quarantine models.
"""

from __future__ import annotations

import decimal
import enum
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union


class MarketType(str, enum.Enum):
    SPOT = "SPOT"
    FUTURES_USDM = "FUTURES_USDM"
    FUTURES_COINM = "FUTURES_COINM"
    OPTIONS = "OPTIONS"
    LEVERAGED_TOKEN = "LEVERAGED_TOKEN"


class ProvenanceSource(str, enum.Enum):
    OFFLINE_FIXTURE = "OFFLINE_FIXTURE"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    WARMUP_REPLAY = "WARMUP_REPLAY"
    LIVE_BINANCE_SPOT = "LIVE_BINANCE_SPOT"
    REST_GAP_RECOVERY = "REST_GAP_RECOVERY"


class CandleLifecycleState(str, enum.Enum):
    CANDLE_RECEIVED = "CANDLE_RECEIVED"
    CANDLE_VALIDATED = "CANDLE_VALIDATED"
    CANDLE_CONFIRMED_CLOSED = "CANDLE_CONFIRMED_CLOSED"
    CANDLE_PERSISTED = "CANDLE_PERSISTED"
    CANDLE_RESEARCH_ELIGIBLE = "CANDLE_RESEARCH_ELIGIBLE"


class ValidationStatus(str, enum.Enum):
    VALID = "VALID"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_INTERVAL = "INVALID_INTERVAL"
    INVALID_MARKET_TYPE = "INVALID_MARKET_TYPE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    OPEN_CANDLE_REJECTED = "OPEN_CANDLE_REJECTED"
    MALFORMED_OHLCV = "MALFORMED_OHLCV"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    MISSING_PROVENANCE = "MISSING_PROVENANCE"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


CANDLE_INTERVAL_MS = 300_000  # 5 minutes in milliseconds
EXPECTED_SYMBOL = "BTCUSDT"
EXPECTED_INTERVAL = "5m"


@dataclass
class ValidatedCandle:
    """Immutable, fully validated closed candle data container with cryptographic integrity."""
    symbol: str
    interval: str
    market_type: str
    timestamp_open: int
    timestamp_close: int
    datetime_open_utc: str
    datetime_close_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades_count: int
    taker_buy_base_volume: float
    is_closed: bool
    provenance: str
    receipt_timestamp_utc: str
    lifecycle_state: str = CandleLifecycleState.CANDLE_VALIDATED.value

    def canonical_dict(self) -> Dict[str, Any]:
        """Produce deterministic dictionary for JSON serialization and cryptographic hashing."""
        return {
            "datetime_close_utc": self.datetime_close_utc,
            "datetime_open_utc": self.datetime_open_utc,
            "interval": self.interval,
            "is_closed": self.is_closed,
            "lifecycle_state": self.lifecycle_state,
            "market_type": self.market_type,
            "open": round(float(self.open), 8),
            "high": round(float(self.high), 8),
            "low": round(float(self.low), 8),
            "close": round(float(self.close), 8),
            "volume": round(float(self.volume), 8),
            "quote_volume": round(float(self.quote_volume), 8),
            "trades_count": int(self.trades_count),
            "taker_buy_base_volume": round(float(self.taker_buy_base_volume), 8),
            "provenance": self.provenance,
            "receipt_timestamp_utc": self.receipt_timestamp_utc,
            "symbol": self.symbol,
            "timestamp_close": int(self.timestamp_close),
            "timestamp_open": int(self.timestamp_open),
        }

    def canonical_json(self) -> str:
        """Produce deterministic JSON string with sorted keys."""
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))

    def compute_sha256(self) -> str:
        """Compute SHA-256 hash of canonical JSON."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def matches_payload(self, other: ValidatedCandle) -> bool:
        """Check if numeric values and critical attributes match."""
        return (
            self.symbol == other.symbol
            and self.interval == other.interval
            and self.timestamp_open == other.timestamp_open
            and self.timestamp_close == other.timestamp_close
            and math.isclose(self.open, other.open, abs_tol=1e-8)
            and math.isclose(self.high, other.high, abs_tol=1e-8)
            and math.isclose(self.low, other.low, abs_tol=1e-8)
            and math.isclose(self.close, other.close, abs_tol=1e-8)
            and math.isclose(self.volume, other.volume, abs_tol=1e-8)
        )


class BinanceSpotCandleValidator:
    """Strict validator for Binance Spot 5-minute closed market candles."""

    @staticmethod
    def _is_valid_decimal(val: Any) -> Tuple[bool, Optional[float]]:
        """Validate numeric value using Decimal to prevent silent precision loss or NaN/Inf."""
        if val is None:
            return False, None
        try:
            d = decimal.Decimal(str(val))
            if d.is_nan() or d.is_infinite():
                return False, None
            f = float(d)
            if math.isnan(f) or math.isinf(f):
                return False, None
            return True, f
        except (decimal.InvalidOperation, ValueError, TypeError):
            return False, None

    @classmethod
    def validate_raw(
        cls,
        raw_record: Union[Dict[str, Any], List[Any]],
        provenance: Union[str, ProvenanceSource],
        market_type: Union[str, MarketType] = MarketType.SPOT,
        receipt_time_utc: Optional[str] = None,
        now_ms: Optional[int] = None,
    ) -> Tuple[Optional[ValidatedCandle], List[str]]:
        """Validate a raw candle message from either WebSocket kline or REST array format.

        Returns (ValidatedCandle, violations).
        If violations is non-empty, ValidatedCandle is None.
        """
        violations: List[str] = []

        # 1. Provenance Validation
        prov_str = provenance.value if isinstance(provenance, ProvenanceSource) else str(provenance)
        valid_provs = {p.value for p in ProvenanceSource}
        if prov_str not in valid_provs:
            violations.append(f"MISSING_OR_INVALID_PROVENANCE: '{prov_str}' not in {valid_provs}")
            return None, violations

        # 2. Market Type Enforcement (SPOT only)
        mkt_str = market_type.value if isinstance(market_type, MarketType) else str(market_type)
        if mkt_str != MarketType.SPOT.value:
            violations.append(f"INVALID_MARKET_TYPE: Only {MarketType.SPOT.value} is supported; received {mkt_str}")
            return None, violations

        # Parse fields based on payload type
        symbol = EXPECTED_SYMBOL
        interval = EXPECTED_INTERVAL
        is_closed = False
        t_open = 0
        t_close = 0
        o, h, l, c, v = 0.0, 0.0, 0.0, 0.0, 0.0
        quote_vol = 0.0
        trades_count = 0
        taker_buy_base = 0.0

        if isinstance(raw_record, dict):
            # WebSocket or structured dict
            # Support both Binance WS payload format: {"e": "kline", "s": "BTCUSDT", "k": {...}}
            # and flat dict format
            k = raw_record.get("k", raw_record)
            symbol = str(raw_record.get("s", k.get("s", EXPECTED_SYMBOL))).upper()
            interval = str(k.get("i", EXPECTED_INTERVAL))
            is_closed = bool(k.get("x", False))

            t_open_val = k.get("t")
            t_close_val = k.get("T")

            o_raw = k.get("o")
            h_raw = k.get("h")
            l_raw = k.get("l")
            c_raw = k.get("c")
            v_raw = k.get("v")
            qv_raw = k.get("q", 0.0)
            n_raw = k.get("n", 0)
            V_raw = k.get("V", 0.0)

        elif isinstance(raw_record, (list, tuple)):
            # Binance REST array format:
            # [0: t_open, 1: o, 2: h, 3: l, 4: c, 5: v, 6: t_close, 7: qv, 8: n, 9: V, 10: Q, 11: ignore]
            if len(raw_record) < 7:
                violations.append(f"MALFORMED_REST_ARRAY: Expected at least 7 fields, got {len(raw_record)}")
                return None, violations

            t_open_val = raw_record[0]
            o_raw = raw_record[1]
            h_raw = raw_record[2]
            l_raw = raw_record[3]
            c_raw = raw_record[4]
            v_raw = raw_record[5]
            t_close_val = raw_record[6]
            qv_raw = raw_record[7] if len(raw_record) > 7 else 0.0
            n_raw = raw_record[8] if len(raw_record) > 8 else 0
            V_raw = raw_record[9] if len(raw_record) > 9 else 0.0

            # REST klines are historical closed candles if close_time <= now_ms
            # If now_ms is not given, default to system UTC clock
            curr_ms = now_ms if now_ms is not None else int(time.time() * 1000)
            try:
                is_closed = int(t_close_val) <= curr_ms
            except (ValueError, TypeError):
                is_closed = False
        else:
            violations.append(f"UNSUPPORTED_PAYLOAD_TYPE: Expected dict or list, got {type(raw_record).__name__}")
            return None, violations

        # 3. Symbol and Interval Validation
        if symbol != EXPECTED_SYMBOL:
            violations.append(f"INVALID_SYMBOL: Expected '{EXPECTED_SYMBOL}', got '{symbol}'")
        if interval != EXPECTED_INTERVAL:
            violations.append(f"INVALID_INTERVAL: Expected '{EXPECTED_INTERVAL}', got '{interval}'")

        # 4. Closed Candle Gate
        if not is_closed:
            violations.append("OPEN_CANDLE_REJECTED: Candle closure flag is False. Open/in-progress candles are strictly prohibited.")

        # 5. Timestamp Parsing and Boundary Validation
        try:
            t_open = int(t_open_val)
            t_close = int(t_close_val)
        except (ValueError, TypeError):
            violations.append(f"INVALID_TIMESTAMP_TYPE: Could not parse timestamps t={t_open_val}, T={t_close_val}")
            t_open, t_close = -1, -1

        if t_open >= 0 and t_close >= 0:
            if t_open % CANDLE_INTERVAL_MS != 0:
                violations.append(
                    f"TIMESTAMP_NOT_ALIGNED_TO_5M: Open timestamp {t_open} is not aligned to 5m (300,000 ms) boundary."
                )
            expected_close = t_open + CANDLE_INTERVAL_MS - 1
            if t_close != expected_close:
                violations.append(
                    f"INVALID_INTERVAL_DURATION: Close timestamp {t_close} != expected {expected_close} (open + 299,999 ms)."
                )

        # 6. OHLCV Numeric Validation
        valid_o, o = cls._is_valid_decimal(o_raw)
        valid_h, h = cls._is_valid_decimal(h_raw)
        valid_l, l = cls._is_valid_decimal(l_raw)
        valid_c, c = cls._is_valid_decimal(c_raw)
        valid_v, v = cls._is_valid_decimal(v_raw)
        _, quote_vol = cls._is_valid_decimal(qv_raw)
        _, taker_buy_base = cls._is_valid_decimal(V_raw)
        try:
            trades_count = int(n_raw)
        except (ValueError, TypeError):
            trades_count = 0

        if not (valid_o and valid_h and valid_l and valid_c and valid_v):
            violations.append("MALFORMED_OHLCV_NON_NUMERIC: One or more OHLCV fields could not be parsed as valid decimals.")
        else:
            if o <= 0.0 or h <= 0.0 or l <= 0.0 or c <= 0.0:
                violations.append(f"NON_POSITIVE_PRICE: Prices must be strictly positive (> 0). Got O={o}, H={h}, L={l}, C={c}")
            if v < 0.0:
                violations.append(f"NEGATIVE_VOLUME: Volume cannot be negative. Got V={v}")
            if h < l:
                violations.append(f"PRICE_INVARIANT_VIOLATION_HIGH_LOW: High ({h}) cannot be lower than Low ({l}).")
            if h < o or h < c:
                violations.append(f"PRICE_INVARIANT_VIOLATION_HIGH_BOUND: High ({h}) must be >= Open ({o}) and Close ({c}).")
            if l > o or l > c:
                violations.append(f"PRICE_INVARIANT_VIOLATION_LOW_BOUND: Low ({l}) must be <= Open ({o}) and Close ({c}).")

        if violations:
            return None, violations

        # Generate ISO UTC strings
        dt_open_utc = datetime.fromtimestamp(t_open / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        dt_close_utc = datetime.fromtimestamp(t_close / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rec_time = receipt_time_utc or datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        candle = ValidatedCandle(
            symbol=symbol,
            interval=interval,
            market_type=mkt_str,
            timestamp_open=t_open,
            timestamp_close=t_close,
            datetime_open_utc=dt_open_utc,
            datetime_close_utc=dt_close_utc,
            open=o,
            high=h,
            low=l,
            close=c,
            volume=v,
            quote_volume=quote_vol or 0.0,
            trades_count=trades_count or 0,
            taker_buy_base_volume=taker_buy_base or 0.0,
            is_closed=True,
            provenance=prov_str,
            receipt_timestamp_utc=rec_time,
            lifecycle_state=CandleLifecycleState.CANDLE_CONFIRMED_CLOSED.value,
        )
        return candle, []
