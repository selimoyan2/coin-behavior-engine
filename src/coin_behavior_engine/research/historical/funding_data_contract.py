"""Canonical Data Contracts for Perpetual Funding, Basis & Market Alignment (Sprint 09.34).

Defines typed, immutable, versioned models for:
1. Authentic Funding Settlement Records.
2. Perpetual Futures Market Data (OHLCV, Trade metrics).
3. Spot vs Perpetual Aligned Basis Observations.
4. Descriptive Funding Diagnostics & Distribution Records.
5. Delta-Neutral Carry Strategy Accounting Specification (Design-only).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


class InstrumentType(str, Enum):
    SPOT = "SPOT"
    USDT_MARGINED_PERPETUAL = "USDT_MARGINED_PERPETUAL"
    COIN_MARGINED_PERPETUAL = "COIN_MARGINED_PERPETUAL"


class DatasetReadinessClassification(str, Enum):
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    DATA_INTEGRITY_FAILED = "DATA_INTEGRITY_FAILED"
    DATA_AUTHENTIC_BUT_LIMITED = "DATA_AUTHENTIC_BUT_LIMITED"
    DATA_RESEARCH_READY = "DATA_RESEARCH_READY"


@dataclass(frozen=True)
class FundingSettlementRecord:
    """Canonical model for a single realized perpetual funding rate settlement."""
    exchange: str
    instrument_symbol: str
    instrument_type: str
    settlement_asset: str
    funding_event_timestamp_ms: int
    funding_event_time_utc: str
    funding_rate: float
    funding_rate_bps: float
    funding_interval_hours: int
    source_identifier: str
    source_publication_status: str  # e.g. "SETTLED_AT_BOUNDARY"
    ingestion_timestamp_utc: str
    source_checksum: str
    verification_status: str  # "CHECKSUM_VERIFIED"
    data_quality_flags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerpetualCandleRecord:
    """Authentic perpetual futures OHLCV candle with trade and quote metrics."""
    symbol: str
    open_time_ms: int
    close_time_ms: int
    open_time_utc: str
    close_time_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades_count: int
    taker_buy_volume: float
    taker_buy_quote_volume: float
    source: str
    instrument_type: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpotPerpAlignedBasisRecord:
    """Point-in-time aligned Spot and Perpetual price observation with calculated basis."""
    timestamp_ms: int
    timestamp_utc: str
    spot_symbol: str
    perp_symbol: str
    spot_close_price: float
    perp_close_price: float
    absolute_basis_usdt: float
    relative_basis_bps: float
    annualized_basis_pct: float
    alignment_tolerance_ms: int
    source_spot: str
    source_perp: str
    lookahead_audit_passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FundingDescriptiveStatistics:
    """Purely descriptive statistical metrics across authentic historical funding settlements."""
    instrument_symbol: str
    total_settlements_count: int
    date_range_start_utc: str
    date_range_end_utc: str
    coverage_days: float
    expected_settlements_at_8h: int
    missing_settlements_count: int
    completeness_pct: float

    # Rate distributions (per 8h period)
    mean_funding_rate_bps: float
    median_funding_rate_bps: float
    std_funding_rate_bps: float
    min_funding_rate_bps: float
    max_funding_rate_bps: float
    interquartile_range_bps: float

    # Directional distribution
    positive_settlements_count: int
    positive_settlements_pct: float
    negative_settlements_count: int
    negative_settlements_pct: float
    zero_settlements_count: int
    zero_settlements_pct: float

    # Run lengths (persistence)
    max_consecutive_positive_settlements: int
    max_consecutive_negative_settlements: int

    # Basis metrics
    mean_spot_perp_basis_bps: float
    median_spot_perp_basis_bps: float
    std_spot_perp_basis_bps: float
    basis_10th_percentile_bps: float
    basis_90th_percentile_bps: float

    # Integrity verification
    checksum_verification_verdict: str
    point_in_time_compliance_verdict: str
    scientific_disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeltaNeutralAccountingSpec:
    """Design-only formal specification for a future delta-neutral carry simulator."""
    specification_id: str
    strategy_name: str
    hedging_architecture: str
    hedge_ratio_formula: str
    spot_position_formula: str
    perpetual_position_formula: str
    initial_margin_requirement_pct: float
    maintenance_margin_requirement_pct: float
    liquidation_buffer_rule: str
    funding_cash_flow_formula: str
    mark_to_market_formula: str
    spot_fee_schedule: str
    perpetual_fee_schedule: str
    slippage_and_spread_model: str
    rebalancing_trigger_conditions: List[str]
    negative_funding_regime_policy: str
    operational_and_counterparty_risks: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PerpetualFundingMasterReport:
    """Master research and integrity report for Sprint 09.34."""
    sprint_id: str
    baseline_commit: str
    official_data_source: str
    dataset_scope: str
    total_months_ingested: int
    total_funding_settlements: int
    total_perp_candles: int
    total_aligned_basis_bars: int
    readiness_classification: DatasetReadinessClassification
    readiness_rationale: str
    descriptive_statistics: FundingDescriptiveStatistics
    accounting_specification: DeltaNeutralAccountingSpec

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sprint_id": self.sprint_id,
            "baseline_commit": self.baseline_commit,
            "official_data_source": self.official_data_source,
            "dataset_scope": self.dataset_scope,
            "total_months_ingested": self.total_months_ingested,
            "total_funding_settlements": self.total_funding_settlements,
            "total_perp_candles": self.total_perp_candles,
            "total_aligned_basis_bars": self.total_aligned_basis_bars,
            "readiness_classification": self.readiness_classification.value,
            "readiness_rationale": self.readiness_rationale,
            "descriptive_statistics": self.descriptive_statistics.to_dict(),
            "accounting_specification": self.accounting_specification.to_dict(),
        }
