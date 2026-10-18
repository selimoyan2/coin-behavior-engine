"""Domain contracts, data structures, and typed definitions for CBE Research Lab.

Sprint 11.03: Market Behavior Research Lab, Event Intelligence & Historical Simulation.
All data structures enforce strict temporal immutability and provenance tracking.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class Resolution(str, enum.Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class MarketRegimeType(str, enum.Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    HIGH_VOLATILITY_EXPANSION = "HIGH_VOLATILITY_EXPANSION"
    LOW_VOLATILITY_COMPRESSION = "LOW_VOLATILITY_COMPRESSION"
    MEAN_REVERTING = "MEAN_REVERTING"
    CASCADE_LIQUIDATION = "CASCADE_LIQUIDATION"
    UNCERTAIN = "UNCERTAIN"


class DecisionAction(str, enum.Enum):
    BUY_CANDIDATE = "BUY_CANDIDATE"
    SELL_CANDIDATE = "SELL_CANDIDATE"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class DecisionMode(str, enum.Enum):
    TECHNICAL_ONLY_RESEARCH = "TECHNICAL_ONLY_RESEARCH"
    CONTEXT_AWARE_RESEARCH = "CONTEXT_AWARE_RESEARCH"
    RISK_CONTROLLED_RESEARCH = "RISK_CONTROLLED_RESEARCH"


class TradeExitReason(str, enum.Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TIME_EXPIRY = "TIME_EXPIRY"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    END_OF_DATA = "END_OF_DATA"


class EventCategory(str, enum.Enum):
    MONETARY_POLICY = "MONETARY_POLICY"
    INFLATION = "INFLATION"
    EMPLOYMENT = "EMPLOYMENT"
    ECONOMIC_GROWTH = "ECONOMIC_GROWTH"
    GEOPOLITICS = "GEOPOLITICS"
    REGULATION = "REGULATION"
    EXCHANGE_OPERATIONS = "EXCHANGE_OPERATIONS"
    EXCHANGE_SECURITY = "EXCHANGE_SECURITY"
    CRYPTO_INDUSTRY = "CRYPTO_INDUSTRY"
    INSTITUTIONAL_ADOPTION = "INSTITUTIONAL_ADOPTION"
    ETF_FLOWS = "ETF_FLOWS"
    MARKET_LIQUIDITY = "MARKET_LIQUIDITY"
    LIQUIDATION_CASCADE = "LIQUIDATION_CASCADE"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    RUMOR_AND_CORRECTION = "RUMOR_AND_CORRECTION"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True)
class CandleData:
    """Immutable single candlestick representation."""
    timestamp_open: int  # Epoch ms
    timestamp_close: int  # Epoch ms
    datetime_open_utc: str
    datetime_close_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trades_count: int = 0
    taker_buy_base_volume: float = 0.0
    is_closed: bool = True
    symbol: str = "BTCUSDT"
    interval: str = "1m"
    provenance: str = "BINANCE_SPOT_REST"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarketBehaviorFeatures:
    """Market behavior and microstructure features computed with strict anti-leakage."""
    timestamp_open: int
    datetime_utc: str
    close_price: float
    return_1: float = 0.0
    return_3: float = 0.0
    return_5: float = 0.0
    return_12: float = 0.0
    return_24: float = 0.0
    momentum_12: float = 0.0
    momentum_24: float = 0.0
    volatility_realized_24: float = 0.0
    atr_14: float = 0.0
    relative_volume_20: float = 1.0
    price_volume_corr_20: float = 0.0
    rolling_high_24: float = 0.0
    rolling_low_24: float = 0.0
    swing_high: Optional[float] = None
    swing_low: Optional[float] = None
    support_zone: float = 0.0
    resistance_zone: float = 0.0
    distance_to_support_pct: float = 0.0
    distance_to_resistance_pct: float = 0.0
    drawdown_from_peak_pct: float = 0.0
    runup_from_trough_pct: float = 0.0
    regime: MarketRegimeType = MarketRegimeType.UNCERTAIN

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["regime"] = self.regime.value
        return d


@dataclass
class EventIntelligenceRecord:
    """Normalized, source-agnostic market event intelligence record."""
    event_id: str
    event_type: str
    category: EventCategory
    headline: str
    summary: str
    source_name: str
    source_url: str
    actor: str
    affected_assets: List[str]
    published_at_utc: str
    first_observed_at_utc: str
    ingested_at_utc: str
    verification_status: str  # "VERIFIED", "RUMOR", "OFFICIAL_CORRECTION", "UNVERIFIED"
    source_credibility: float  # 0.0 to 1.0
    event_direction_hypothesis: str  # "BULLISH", "BEARISH", "VOLATILE", "NEUTRAL"
    event_severity: float  # 0.0 (minor) to 1.0 (catastrophic)
    event_novelty: float = 1.0  # 0.0 (expected) to 1.0 (black swan)
    related_event_ids: List[str] = field(default_factory=list)
    correction_of_event_id: Optional[str] = None
    provenance: str = "HISTORICAL_EVENT_ARCHIVE"
    abnormal_return_5m_post: Optional[float] = None
    abnormal_return_60m_post: Optional[float] = None
    observed_market_impact: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass
class BehavioralPattern:
    """Interpretable pattern descriptor discovered from historical state transitions."""
    pattern_id: str
    pattern_name: str
    pattern_version: str
    entry_conditions: str
    market_regime: MarketRegimeType
    context_requirements: str
    historical_sample_count: int
    observation_window_bars: int
    prediction_horizon_bars: int
    probability_positive_outcome: float
    expected_return_pct: float
    confidence_interval: Tuple[float, float]
    failure_conditions: str
    risk_characteristics: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["market_regime"] = self.market_regime.value
        return d


@dataclass
class ProbabilisticPrediction:
    """Explainable multi-horizon prediction output."""
    symbol: str
    decision_timestamp: int
    datetime_utc: str
    prediction_horizon: str  # "5m", "15m", "60m", "4h"
    market_regime: MarketRegimeType
    probability_up: float
    probability_down: float
    probability_neutral: float
    expected_return_pct: float
    downside_risk_pct: float
    confidence_status: str  # "CALIBRATED", "UNCALIBRATED", "NO_PREDICTION"
    support_zones: List[float] = field(default_factory=list)
    resistance_zones: List[float] = field(default_factory=list)
    relevant_events: List[str] = field(default_factory=list)
    missing_context: List[str] = field(default_factory=list)
    explanation: str = ""
    model_version: str = "1.0.0-sprint11.03"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["market_regime"] = self.market_regime.value
        return d


@dataclass
class ResearchDecision:
    """Hypothetical research-only decision with explicit rationale."""
    decision_id: str
    symbol: str
    timestamp_open: int
    datetime_utc: str
    action: DecisionAction
    decision_mode: DecisionMode
    reason: str
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    max_holding_bars: int = 12
    position_size_pct: float = 0.0
    risk_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action"] = self.action.value
        d["decision_mode"] = self.decision_mode.value
        return d


@dataclass
class PaperTrade:
    """Simulated trade execution record."""
    trade_id: str
    strategy_name: str
    symbol: str
    side: str  # "BUY"
    entry_time_utc: str
    entry_price: float
    exit_time_utc: str
    exit_price: float
    exit_reason: TradeExitReason
    quantity: float
    gross_pnl: float
    fees_paid: float
    slippage_cost: float
    net_pnl: float
    return_pct: float
    holding_period_minutes: int
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["exit_reason"] = self.exit_reason.value
        return d


@dataclass
class SimulationRunResult:
    """Complete summary of a historical paper simulation run."""
    run_id: str
    strategy_name: str
    start_time_utc: str
    end_time_utc: str
    initial_capital: float
    final_capital: float
    total_net_pnl: float
    return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown_amount: float
    max_drawdown_pct: float
    turnover: float
    total_fees: float
    total_slippage: float
    sharpe_ratio: float
    sortino_ratio: float
    baseline_buy_and_hold_return_pct: float
    baseline_cash_return_pct: float = 0.0
    trades: List[PaperTrade] = field(default_factory=list)
    equity_series: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["trades"] = [t.to_dict() for t in self.trades]
        return d


@dataclass
class CaseStudyResult:
    """Formal market crash case study analysis."""
    study_id: str
    title: str
    event_start_utc: str
    event_end_utc: str
    pre_event_price: float
    trough_price: float
    max_drawdown_pct: float
    recovery_price: float
    volume_behavior: str
    volatility_behavior: str
    visible_support_resistance: str
    earliest_risk_signal_time: Optional[str]
    detection_delay_minutes: Optional[int]
    subsequent_price_behavior: str
    associated_events: List[str]
    technical_vs_context_comparison: str
    hypothetical_strategy_performance: Dict[str, Any]
    lessons_learned: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
