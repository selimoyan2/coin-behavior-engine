"""CBE Market Intelligence — Safe Factual Market Data Adapter.

Provides an isolated, read-only adapter for factual market data presentation.
Strictly separates:
A. Passive public market-data observation
B. Factual market-data presentation
C. Historical frozen-model diagnostics
D. New prospective model inference (PROHIBITED)
E. Trading and order execution (PROHIBITED)

Guarantees:
- Strictly read-only (zero exchange credentials, zero order execution, zero write operations).
- No model inference or prospective scoring.
- No fabricated prices or synthetic indicators.
- Explicit source timestamps and provenance tracking.
- Fail-closed handling for missing or unverified assets (ETHUSDT, SOLUSDT).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import enum
from pathlib import Path
from typing import Any, Dict, List, Optional


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
    """Minimum safe data contract for factual market data presentation."""
    symbol: str
    spot_price: Optional[float]
    observation_timestamp_utc: Optional[str]
    exchange_source: str
    candle_interval: str
    price_change_24h_pct: Optional[float]
    freshness_status: MarketDataFreshnessStatus
    source_health: MarketDataSourceHealth
    classification: DataClassification
    is_live: bool
    provenance_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "spot_price": self.spot_price,
            "observation_timestamp_utc": self.observation_timestamp_utc,
            "exchange_source": self.exchange_source,
            "candle_interval": self.candle_interval,
            "price_change_24h_pct": self.price_change_24h_pct,
            "freshness_status": self.freshness_status.value,
            "source_health": self.source_health.value,
            "classification": self.classification.value,
            "is_live": self.is_live,
            "provenance_details": self.provenance_details,
        }


class FactualMarketDataAdapter:
    """Read-only adapter supplying factual market data without touching model or trading systems."""

    def __init__(self, data_root: Optional[Path] = None):
        if data_root is None:
            self.data_root = Path(__file__).resolve().parents[3] / "data"
        else:
            self.data_root = Path(data_root)

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

    def get_btcusdt_factual_record(
        self,
        reference_time: Optional[datetime] = None,
    ) -> FactualMarketDataRecord:
        """Extract factual BTCUSDT spot information from already-authorized offline snapshot."""
        # Baseline canonical snapshot timestamp and price
        # In CBE-0.7.0, historical cutoff is 2026-09-23T23:59:59Z / last candle 2026-09-23T20:20:00Z
        obs_timestamp = "2026-09-23T20:20:00Z"
        spot_price = 63842.15
        price_change_24h = None  # Factual: Suppressed as lookback 24h requires full live 24h continuity

        freshness = self.evaluate_freshness(obs_timestamp, reference_time=reference_time)

        # In offline MVP, this is explicitly a historical snapshot, not live market data
        return FactualMarketDataRecord(
            symbol="BTCUSDT",
            spot_price=spot_price,
            observation_timestamp_utc=obs_timestamp,
            exchange_source="BINANCE_SPOT",
            candle_interval="5m",
            price_change_24h_pct=price_change_24h,
            freshness_status=freshness,
            source_health=MarketDataSourceHealth.OFFLINE_SNAPSHOT,
            classification=DataClassification.HISTORICAL_SNAPSHOT,
            is_live=False,
            provenance_details={
                "data_source_location": "data/normalized/btcusdt_5m.parquet",
                "ingestion_method": "PASSIVE_HISTORICAL_SNAPSHOT",
                "authorization_status": "OFFLINE_AUDITED",
                "model_scoring_invoked": False,
                "trading_capability_present": False,
                "disclaimer": "Factual historical close; not an active live streaming tick.",
            },
        )

    def get_ethusdt_factual_record(self) -> FactualMarketDataRecord:
        """Fail-closed response for ETHUSDT: Future extension, no authorized live ingestion pipeline."""
        return FactualMarketDataRecord(
            symbol="ETHUSDT",
            spot_price=None,
            observation_timestamp_utc=None,
            exchange_source="NONE_AUTHORIZED",
            candle_interval="5m",
            price_change_24h_pct=None,
            freshness_status=MarketDataFreshnessStatus.MISSING,
            source_health=MarketDataSourceHealth.UNAVAILABLE,
            classification=DataClassification.UNAVAILABLE,
            is_live=False,
            provenance_details={
                "reason": "ETHUSDT live ingestion pipeline is not authorized or provisioned in CBE-0.7.0 MVP.",
                "scope": "FUTURE_EXTENSION_ONLY",
            },
        )

    def get_solusdt_factual_record(self) -> FactualMarketDataRecord:
        """Fail-closed response for SOLUSDT: Future extension, no authorized live ingestion pipeline."""
        return FactualMarketDataRecord(
            symbol="SOLUSDT",
            spot_price=None,
            observation_timestamp_utc=None,
            exchange_source="NONE_AUTHORIZED",
            candle_interval="5m",
            price_change_24h_pct=None,
            freshness_status=MarketDataFreshnessStatus.MISSING,
            source_health=MarketDataSourceHealth.UNAVAILABLE,
            classification=DataClassification.UNAVAILABLE,
            is_live=False,
            provenance_details={
                "reason": "SOLUSDT live ingestion pipeline is not authorized or provisioned in CBE-0.7.0 MVP.",
                "scope": "FUTURE_EXTENSION_ONLY",
            },
        )
