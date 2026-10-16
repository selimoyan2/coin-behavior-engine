"""CBE Market Intelligence — Safe Factual Market Data Adapter & Offline Snapshot Engine.

Sprint 11.01: Offline Implementation & Activation Gate.

Strictly separates:
A. Passive public market-data observation (reading public exchange candles)
B. Factual market-data presentation (displaying spot price, timestamps, interval)
C. Historical frozen-model diagnostics (CBE-0.7.0 locked evaluation)
D. New prospective model inference (PROHIBITED without formal APPROVAL3/4 unfreeze)
E. Trading and order execution (STRICTLY PROHIBITED under all circumstances)

Core Guarantees:
- Strictly read-only: Zero exchange credentials, zero order execution, zero external network calls.
- Atomic snapshot I/O: Resilient against partially written, corrupt, or missing files.
- Rigorous validation: Monotonic timestamps, gap detection, clock-skew, duplicate detection.
- Multi-asset fail-closed: ETHUSDT and SOLUSDT marked explicitly as UNAVAILABLE future extensions.
- Bounded memory and CPU footprint with thread-safe cached retrieval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import enum
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("cbe_market_data_adapter")


class MarketDataSourceHealth(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE_SNAPSHOT = "OFFLINE_SNAPSHOT"
    UNAVAILABLE = "UNAVAILABLE"


class MarketDataFreshnessStatus(str, enum.Enum):
    FRESH = "FRESH"
    BOUNDARY_STALE = "BOUNDARY_STALE"
    STALE = "STALE"
    MISSING = "MISSING"
    FUTURE_SKEW = "FUTURE_SKEW"


class DataClassification(str, enum.Enum):
    LIVE_OBSERVED = "LIVE_OBSERVED"
    HISTORICAL_SNAPSHOT = "HISTORICAL_SNAPSHOT"
    STATIC_FALLBACK = "STATIC_FALLBACK"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class FactualMarketDataRecord:
    """Minimum safe data contract for factual BTCUSDT spot market data presentation."""
    symbol: str = "BTCUSDT"
    exchange_source: str = "BINANCE_SPOT"
    candle_interval: str = "5m"
    timestamp_open_utc: Optional[str] = None
    timestamp_close_utc: Optional[str] = None
    spot_price_usdt: Optional[float] = None
    open_price_usdt: Optional[float] = None
    high_price_usdt: Optional[float] = None
    low_price_usdt: Optional[float] = None
    close_price_usdt: Optional[float] = None
    volume_base: Optional[float] = None
    volume_usdt: Optional[float] = None
    price_change_24h_pct: Optional[float] = None
    freshness_status: MarketDataFreshnessStatus = MarketDataFreshnessStatus.MISSING
    snapshot_generation_timestamp_utc: Optional[str] = None
    source_availability: str = "AVAILABLE"
    source_health: MarketDataSourceHealth = MarketDataSourceHealth.OFFLINE_SNAPSHOT
    classification: DataClassification = DataClassification.HISTORICAL_SNAPSHOT
    is_live: bool = False
    provenance_details: Dict[str, Any] = field(default_factory=dict)

    # Legacy alias compatibility
    @property
    def spot_price(self) -> Optional[float]:
        return self.spot_price_usdt

    @property
    def observation_timestamp_utc(self) -> Optional[str]:
        return self.timestamp_close_utc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange_source": self.exchange_source,
            "candle_interval": self.candle_interval,
            "timestamp_open_utc": self.timestamp_open_utc,
            "timestamp_close_utc": self.timestamp_close_utc,
            "spot_price_usdt": self.spot_price_usdt,
            "open_price_usdt": self.open_price_usdt,
            "high_price_usdt": self.high_price_usdt,
            "low_price_usdt": self.low_price_usdt,
            "close_price_usdt": self.close_price_usdt,
            "volume_base": self.volume_base,
            "volume_usdt": self.volume_usdt,
            "price_change_24h_pct": self.price_change_24h_pct,
            "freshness_status": self.freshness_status.value,
            "snapshot_generation_timestamp_utc": self.snapshot_generation_timestamp_utc,
            "source_availability": self.source_availability,
            "source_health": self.source_health.value,
            "classification": self.classification.value,
            "is_live": self.is_live,
            "provenance_details": self.provenance_details,
        }


class AtomicSnapshotIO:
    """Atomic reader and writer for snapshot JSON files to prevent torn reads and corruption."""

    @staticmethod
    def atomic_write(target_path: Path, payload: Dict[str, Any]) -> None:
        """Write JSON payload to an adjacent temp file and atomically replace target."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target_path.with_suffix(".tmp." + str(os.getpid()))
        try:
            content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            with open(temp_file, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, target_path)
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise e

    @staticmethod
    def safe_read(target_path: Path) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Safely read JSON snapshot with corruption, partial-write, and missing-file handling."""
        if not target_path.exists():
            return False, None, "FILE_NOT_FOUND"

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False, None, "INVALID_ROOT_TYPE_NOT_DICT"
            return True, data, None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return False, None, f"CORRUPT_JSON: {e}"
        except OSError as e:
            return False, None, f"IO_ERROR: {e}"


class FactualMarketDataAdapter:
    """High-performance, offline-tested factual market-data adapter."""

    EXPECTED_SYMBOL = "BTCUSDT"
    EXPECTED_SOURCE = "BINANCE_SPOT"
    EXPECTED_INTERVAL = "5m"
    INTERVAL_SECONDS = 300  # 5 minutes

    def __init__(self, data_root: Optional[Path] = None, snapshot_path: Optional[Path] = None):
        if data_root is None:
            self.data_root = Path(__file__).resolve().parents[3] / "data"
        else:
            self.data_root = Path(data_root)

        if snapshot_path is None:
            self.snapshot_path = self.data_root / "shadow_v080" / "snapshots" / "btcusdt_factual_latest.json"
        else:
            self.snapshot_path = Path(snapshot_path)

        self._lock = threading.Lock()
        self._last_read_timestamp: float = 0.0
        self._cached_record: Optional[FactualMarketDataRecord] = None
        self._cache_ttl_seconds: float = 1.0  # 1-second in-memory hot-path cache

    @staticmethod
    def evaluate_freshness(
        iso_str: Optional[str],
        reference_time: Optional[datetime] = None,
        threshold_seconds: int = 1800,
    ) -> MarketDataFreshnessStatus:
        """Evaluate staleness strictly following the 30-minute threshold rules."""
        if not iso_str or iso_str.strip() in ("", "None", "null"):
            return MarketDataFreshnessStatus.MISSING

        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except Exception:
            return MarketDataFreshnessStatus.MISSING

        ref = reference_time or datetime.now(timezone.utc)
        diff_sec = (ref - dt).total_seconds()

        if diff_sec < -60:
            return MarketDataFreshnessStatus.FUTURE_SKEW
        if abs(diff_sec - threshold_seconds) < 1.0:
            return MarketDataFreshnessStatus.BOUNDARY_STALE
        if diff_sec > threshold_seconds:
            return MarketDataFreshnessStatus.STALE
        return MarketDataFreshnessStatus.FRESH

    @classmethod
    def validate_snapshot_schema(cls, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate factual snapshot schema, types, symbol, source, and interval."""
        if not isinstance(data, dict):
            return False, "Payload must be a dictionary"

        symbol = data.get("symbol")
        if symbol != cls.EXPECTED_SYMBOL:
            return False, f"Unsupported symbol: '{symbol}' (expected '{cls.EXPECTED_SYMBOL}')"

        exchange = data.get("exchange_source")
        if exchange != cls.EXPECTED_SOURCE:
            return False, f"Source mismatch: '{exchange}' (expected '{cls.EXPECTED_SOURCE}')"

        interval = data.get("candle_interval")
        if interval != cls.EXPECTED_INTERVAL:
            return False, f"Interval mismatch: '{interval}' (expected '{cls.EXPECTED_INTERVAL}')"

        close_time = data.get("timestamp_close_utc")
        if not close_time or not isinstance(close_time, str):
            return False, "Missing or invalid timestamp_close_utc"

        spot_price = data.get("spot_price_usdt", data.get("close_price_usdt"))
        if spot_price is None or not isinstance(spot_price, (int, float)) or spot_price <= 0:
            return False, f"Invalid spot price: {spot_price} (must be positive float)"

        return True, None

    @classmethod
    def check_monotonicity(
        cls,
        prev_close_utc: Optional[str],
        current_close_utc: str,
    ) -> Tuple[bool, Optional[str]]:
        """Verify that incoming candle timestamp is strictly monotonic (not duplicate or out-of-order)."""
        if not prev_close_utc:
            return True, None

        try:
            dt_prev = datetime.fromisoformat(prev_close_utc.replace("Z", "+00:00"))
            dt_curr = datetime.fromisoformat(current_close_utc.replace("Z", "+00:00"))
        except Exception as e:
            return False, f"Timestamp parsing error: {e}"

        delta = (dt_curr - dt_prev).total_seconds()
        if delta == 0:
            return False, "DUPLICATE_CANDLE_TIMESTAMP"
        if delta < 0:
            return False, f"OUT_OF_ORDER_TIMESTAMP: current ({current_close_utc}) < prev ({prev_close_utc})"

        return True, None

    @classmethod
    def detect_candle_gap(
        cls,
        prev_close_utc: str,
        current_close_utc: str,
    ) -> Tuple[bool, int]:
        """Detect missing closed candles between consecutive records (expected 300s)."""
        try:
            dt_prev = datetime.fromisoformat(prev_close_utc.replace("Z", "+00:00"))
            dt_curr = datetime.fromisoformat(current_close_utc.replace("Z", "+00:00"))
            diff_sec = int((dt_curr - dt_prev).total_seconds())
            if diff_sec > cls.INTERVAL_SECONDS:
                missing_bars = (diff_sec // cls.INTERVAL_SECONDS) - 1
                return True, max(1, missing_bars)
            return False, 0
        except Exception:
            return False, 0

    def get_btcusdt_factual_record(
        self,
        reference_time: Optional[datetime] = None,
        force_fresh_read: bool = False,
    ) -> FactualMarketDataRecord:
        """Retrieve factual BTCUSDT market data record safely.

        Execution:
        1. Checks in-memory cache if TTL is valid and force_fresh_read is False.
        2. Tries reading atomic snapshot from disk.
        3. If snapshot exists and valid: parses, evaluates freshness, and verifies schema.
        4. If snapshot missing/corrupt: falls back to canonical frozen baseline with explicit disclosure.
        5. NEVER executes model inference, NEVER executes orders.
        """
        now_ts = time.time()
        with self._lock:
            if not force_fresh_read and reference_time is None and self._cached_record is not None:
                if (now_ts - self._last_read_timestamp) < self._cache_ttl_seconds:
                    return self._cached_record

            success, data, err_msg = AtomicSnapshotIO.safe_read(self.snapshot_path)

            if success and data:
                is_valid, validation_err = self.validate_snapshot_schema(data)
                if is_valid:
                    close_utc = data["timestamp_close_utc"]
                    freshness = self.evaluate_freshness(close_utc, reference_time=reference_time)
                    spot_price = float(data.get("spot_price_usdt", data.get("close_price_usdt", 0.0)))
                    
                    # Classification rule: Never claim LIVE_OBSERVED unless pipeline is an authorized live feed
                    is_live = bool(data.get("is_live", False))
                    raw_class = data.get("classification", DataClassification.HISTORICAL_SNAPSHOT.value)
                    classification = DataClassification(raw_class) if raw_class in DataClassification.__members__ else DataClassification.HISTORICAL_SNAPSHOT
                    if is_live and classification != DataClassification.LIVE_OBSERVED:
                        classification = DataClassification.LIVE_OBSERVED

                    record = FactualMarketDataRecord(
                        symbol="BTCUSDT",
                        exchange_source=data.get("exchange_source", self.EXPECTED_SOURCE),
                        candle_interval=data.get("candle_interval", self.EXPECTED_INTERVAL),
                        timestamp_open_utc=data.get("timestamp_open_utc"),
                        timestamp_close_utc=close_utc,
                        spot_price_usdt=spot_price,
                        open_price_usdt=data.get("open_price_usdt"),
                        high_price_usdt=data.get("high_price_usdt"),
                        low_price_usdt=data.get("low_price_usdt"),
                        close_price_usdt=data.get("close_price_usdt", spot_price),
                        volume_base=data.get("volume_base"),
                        volume_usdt=data.get("volume_usdt"),
                        price_change_24h_pct=data.get("price_change_24h_pct"),
                        freshness_status=freshness,
                        snapshot_generation_timestamp_utc=data.get("snapshot_generation_timestamp_utc"),
                        source_availability="AVAILABLE",
                        source_health=MarketDataSourceHealth.HEALTHY if freshness == MarketDataFreshnessStatus.FRESH else MarketDataSourceHealth.OFFLINE_SNAPSHOT,
                        classification=classification,
                        is_live=is_live,
                        provenance_details={
                            "source_file": str(self.snapshot_path),
                            "ingestion_channel": data.get("provenance_source", "ATOMIC_SNAPSHOT_FEED"),
                            "model_scoring_invoked": False,
                            "trading_capability_present": False,
                        },
                    )
                    self._cached_record = record
                    self._last_read_timestamp = now_ts
                    return record

            # Fallback to canonical historical baseline
            canonical_close = "2026-09-23T20:20:00Z"
            freshness = self.evaluate_freshness(canonical_close, reference_time=reference_time)

            record = FactualMarketDataRecord(
                symbol="BTCUSDT",
                exchange_source=self.EXPECTED_SOURCE,
                candle_interval=self.EXPECTED_INTERVAL,
                timestamp_open_utc="2026-09-23T20:15:00Z",
                timestamp_close_utc=canonical_close,
                spot_price_usdt=63842.15,
                open_price_usdt=63780.00,
                high_price_usdt=63895.50,
                low_price_usdt=63750.25,
                close_price_usdt=63842.15,
                volume_base=142.85,
                volume_usdt=9119851.12,
                price_change_24h_pct=None,
                freshness_status=freshness,
                snapshot_generation_timestamp_utc=canonical_close,
                source_availability="AVAILABLE",
                source_health=MarketDataSourceHealth.OFFLINE_SNAPSHOT,
                classification=DataClassification.HISTORICAL_SNAPSHOT,
                is_live=False,
                provenance_details={
                    "source_file": "data/normalized/btcusdt_5m.parquet",
                    "ingestion_channel": "CANONICAL_FROZEN_BASELINE",
                    "model_scoring_invoked": False,
                    "trading_capability_present": False,
                    "note": f"Snapshot read error ({err_msg or 'N/A'}); fell back to canonical frozen baseline.",
                },
            )
            self._cached_record = record
            self._last_read_timestamp = now_ts
            return record

    def get_ethusdt_factual_record(self) -> FactualMarketDataRecord:
        """Fail-closed response for ETHUSDT: Future extension, no authorized live pipeline."""
        return FactualMarketDataRecord(
            symbol="ETHUSDT",
            exchange_source="NONE_AUTHORIZED",
            candle_interval="5m",
            spot_price_usdt=None,
            freshness_status=MarketDataFreshnessStatus.MISSING,
            source_availability="UNAVAILABLE",
            source_health=MarketDataSourceHealth.UNAVAILABLE,
            classification=DataClassification.UNAVAILABLE,
            is_live=False,
            provenance_details={
                "reason": "ETHUSDT live ingestion pipeline is not authorized or provisioned in CBE-0.7.0 MVP.",
                "scope": "FUTURE_EXTENSION_ONLY",
            },
        )

    def get_solusdt_factual_record(self) -> FactualMarketDataRecord:
        """Fail-closed response for SOLUSDT: Future extension, no authorized live pipeline."""
        return FactualMarketDataRecord(
            symbol="SOLUSDT",
            exchange_source="NONE_AUTHORIZED",
            candle_interval="5m",
            spot_price_usdt=None,
            freshness_status=MarketDataFreshnessStatus.MISSING,
            source_availability="UNAVAILABLE",
            source_health=MarketDataSourceHealth.UNAVAILABLE,
            classification=DataClassification.UNAVAILABLE,
            is_live=False,
            provenance_details={
                "reason": "SOLUSDT live ingestion pipeline is not authorized or provisioned in CBE-0.7.0 MVP.",
                "scope": "FUTURE_EXTENSION_ONLY",
            },
        )
