"""Extensibility interfaces for non-OHLCV external market signals.

Defines schemas and zero-lookahead access guards for:
- Timestamped news and sentiment
- Economic calendar announcements (FOMC, CPI, NFP)
- Derivatives context (funding rates, liquidations, open interest)
- Bitcoin Spot ETF flows

Guarantees that external data is never incorporated before its
`available_timestamp_ms` relative to `decision_timestamp_ms`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence


class ExternalDataAvailabilityError(ValueError):
    """Raised when external data is accessed prior to its actual availability timestamp."""


@dataclass(frozen=True)
class TimestampedNewsItem:
    """Historical news or sentiment record with explicit availability timestamp."""

    news_id: str
    headline: str
    source: str
    published_timestamp_ms: int
    available_timestamp_ms: int  # Must be >= published_timestamp_ms
    sentiment_score: float  # -1.0 to +1.0
    impact_tier: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    related_symbols: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.available_timestamp_ms < self.published_timestamp_ms:
            raise ValueError(
                f"available_timestamp_ms ({self.available_timestamp_ms}) cannot be before "
                f"published_timestamp_ms ({self.published_timestamp_ms})"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EconomicAnnouncementItem:
    """Macro/Economic announcement (e.g. FOMC, CPI, NFP)."""

    event_id: str
    event_name: str
    country: str
    scheduled_timestamp_ms: int
    actual_release_timestamp_ms: int
    available_timestamp_ms: int
    actual_value: float | None
    forecast_value: float | None
    previous_value: float | None
    impact: str  # "HIGH", "MEDIUM", "LOW"

    def __post_init__(self) -> None:
        if self.available_timestamp_ms < self.actual_release_timestamp_ms:
            raise ValueError("available_timestamp_ms cannot precede actual_release_timestamp_ms")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DerivativesContextItem:
    """Perpetual futures context: funding rates, open interest, and liquidations."""

    symbol: str
    timestamp_ms: int
    available_timestamp_ms: int
    funding_rate: float
    open_interest_btc: float
    open_interest_usd: float
    long_liquidation_usd: float = 0.0
    short_liquidation_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.available_timestamp_ms < self.timestamp_ms:
            raise ValueError("available_timestamp_ms cannot precede timestamp_ms")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EtfFlowItem:
    """Spot ETF net inflow/outflow record."""

    flow_date: str  # YYYY-MM-DD
    report_timestamp_ms: int
    available_timestamp_ms: int  # When the 13F/vendor reported the flow
    net_inflow_usd: float
    cumulative_net_inflow_usd: float
    source_tickers: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.available_timestamp_ms < self.report_timestamp_ms:
            raise ValueError("available_timestamp_ms cannot precede report_timestamp_ms")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_available_signals(
    items: Sequence[Any],
    decision_timestamp_ms: int,
    fail_on_future: bool = True,
) -> list[Any]:
    """Filter external signal items that were available at or before decision_timestamp_ms.

    If fail_on_future is True and any item has available_timestamp_ms > decision_timestamp_ms,
    an ExternalDataAvailabilityError is raised to guarantee strict no-lookahead.
    """
    valid: list[Any] = []
    for it in items:
        avail_ts = getattr(it, "decision_available_timestamp_ms", None) or getattr(it, "available_timestamp_ms", None)
        if avail_ts is None:
            raise AttributeError(f"Item {it} lacks available_timestamp_ms or decision_available_timestamp_ms attribute")
        if avail_ts > decision_timestamp_ms:
            if fail_on_future:
                raise ExternalDataAvailabilityError(
                    f"Lookahead bias detected: signal available at {avail_ts} "
                    f"accessed at decision time {decision_timestamp_ms}"
                )
            continue
        valid.append(it)
    return valid


# =========================================================================
# Sprint 09.26: 4-Timestamp External Market Intelligence Readiness
# =========================================================================

@dataclass(frozen=True)
class TimestampedSignalEnvelope:
    """Formal 4-timestamp envelope guaranteeing strict point-in-time availability.

    Hierarchy:
        event_timestamp_ms <= publication_timestamp_ms <= ingestion_timestamp_ms <= decision_available_timestamp_ms
    """

    signal_id: str
    signal_type: str  # "NEWS", "MACRO", "FUNDING_RATE", "OPEN_INTEREST", "LIQUIDATION", "ETF_FLOW"
    source_name: str
    event_timestamp_ms: int
    publication_timestamp_ms: int
    ingestion_timestamp_ms: int
    decision_available_timestamp_ms: int
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.publication_timestamp_ms < self.event_timestamp_ms:
            raise ValueError(
                f"publication_timestamp_ms ({self.publication_timestamp_ms}) cannot precede "
                f"event_timestamp_ms ({self.event_timestamp_ms})"
            )
        if self.ingestion_timestamp_ms < self.publication_timestamp_ms:
            raise ValueError(
                f"ingestion_timestamp_ms ({self.ingestion_timestamp_ms}) cannot precede "
                f"publication_timestamp_ms ({self.publication_timestamp_ms})"
            )
        if self.decision_available_timestamp_ms < self.ingestion_timestamp_ms:
            raise ValueError(
                f"decision_available_timestamp_ms ({self.decision_available_timestamp_ms}) cannot precede "
                f"ingestion_timestamp_ms ({self.ingestion_timestamp_ms})"
            )

    @property
    def available_timestamp_ms(self) -> int:
        return self.decision_available_timestamp_ms

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExternalDataReadinessValidator:
    """Validates external dataset feeds for research integrity and lookahead prevention."""

    @staticmethod
    def validate_envelope_sequence(
        envelopes: Sequence[TimestampedSignalEnvelope],
        decision_timestamp_ms: int | None = None,
    ) -> dict[str, Any]:
        """Verify 4-timestamp consistency and optional point-in-time availability."""
        total = len(envelopes)
        violations = []

        for env in envelopes:
            # Check chronological ordering
            if not (env.event_timestamp_ms <= env.publication_timestamp_ms <= env.ingestion_timestamp_ms <= env.decision_available_timestamp_ms):
                violations.append(f"Timestamp ordering violation in signal {env.signal_id}")

            # Check point-in-time constraint if provided
            if decision_timestamp_ms is not None and env.decision_available_timestamp_ms > decision_timestamp_ms:
                violations.append(
                    f"Lookahead violation in signal {env.signal_id}: "
                    f"available at {env.decision_available_timestamp_ms} > decision {decision_timestamp_ms}"
                )

        return {
            "total_signals_audited": total,
            "violations_count": len(violations),
            "is_valid": len(violations) == 0,
            "violations": violations[:10],
            "authenticity_status": "CONTRACT_VERIFIED_WITHOUT_LOOKAHEAD" if len(violations) == 0 else "REJECTED_LOOKAHEAD_DETECTED",
        }

