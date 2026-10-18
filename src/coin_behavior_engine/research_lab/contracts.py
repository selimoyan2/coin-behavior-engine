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


class EventVerificationStatus(str, enum.Enum):
    VERIFIED_EVENT = "VERIFIED_EVENT"
    REPORTED_UNCONFIRMED = "REPORTED_UNCONFIRMED"
    RUMOR = "RUMOR"
    DISPUTED = "DISPUTED"
    RETROSPECTIVE_INTERPRETATION = "RETROSPECTIVE_INTERPRETATION"
    UNSUPPORTED = "UNSUPPORTED"


class MarketContextImpact(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    AMBIGUOUS = "AMBIGUOUS"
    UNCERTAIN = "UNCERTAIN"
    POTENTIALLY_PRICED_IN = "POTENTIALLY_PRICED_IN"
    CONTRADICTED_BY_PRICE_ACTION = "CONTRADICTED_BY_PRICE_ACTION"
    SUPERSEDED_BY_LATER_EVENT = "SUPERSEDED_BY_LATER_EVENT"


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
    # Sprint 11.04 Multi-Timeframe and Regime Alignment
    htf_1h_regime: MarketRegimeType = MarketRegimeType.UNCERTAIN
    htf_4h_regime: MarketRegimeType = MarketRegimeType.UNCERTAIN
    htf_1h_trend_pct: float = 0.0
    htf_4h_trend_pct: float = 0.0
    volatility_compression_ratio: float = 1.0  # ATR14 / ATR100
    price_volume_divergence: str = "NONE"  # "BULLISH_DIV", "BEARISH_DIV", "NONE"
    is_htf_trend_aligned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["regime"] = self.regime.value
        d["htf_1h_regime"] = self.htf_1h_regime.value
        d["htf_4h_regime"] = self.htf_4h_regime.value
        return d


@dataclass
class EventIntelligenceRecord:
    """Normalized, source-agnostic market event intelligence record with audit verification."""
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
    verification_status: EventVerificationStatus = EventVerificationStatus.UNSUPPORTED
    source_credibility: float = 0.5  # 0.0 to 1.0
    source_reliability_class: str = "TIER_3_UNVERIFIED"
    exact_factual_claim: str = ""
    independent_corroboration: Optional[str] = None
    relationship_to_price_movement: str = "UNCORRELATED"
    is_pre_dataset_window: bool = False
    event_direction_hypothesis: str = "NEUTRAL"  # "BULLISH", "BEARISH", "VOLATILE", "NEUTRAL"
    event_severity: float = 0.5  # 0.0 (minor) to 1.0 (catastrophic)
    event_novelty: float = 1.0  # 0.0 (expected) to 1.0 (black swan)
    related_event_ids: List[str] = field(default_factory=list)
    correction_of_event_id: Optional[str] = None
    provenance: str = "HISTORICAL_EVENT_ARCHIVE"
    # Sprint 11.05 Market Context Engine Fields
    context_impact: MarketContextImpact = MarketContextImpact.UNCERTAIN
    freshness_half_life_hours: float = 12.0
    surprise_factor: Optional[float] = None
    relevance_score: float = 1.0  # 0.0 to 1.0
    retraction_history: Optional[str] = None
    first_observed_uncertainty_seconds: float = 0.0
    is_excluded_from_strict_prediction: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["verification_status"] = self.verification_status.value if isinstance(self.verification_status, EventVerificationStatus) else str(self.verification_status)
        d["context_impact"] = self.context_impact.value if isinstance(self.context_impact, MarketContextImpact) else str(self.context_impact)
        return d


@dataclass
class MarketContextTimelineRecord:
    """State of market context at a specific closed candlestick."""
    timestamp_open: int
    datetime_utc: str
    active_events_count: int
    net_sentiment_score: float  # -1.0 to +1.0
    dominant_impact: MarketContextImpact
    has_unabsorbed_negative_shock: bool
    has_positive_catalyst: bool
    contradiction_detected: bool
    priced_in_detected: bool
    primary_event_id: Optional[str] = None
    primary_headline: str = "NO_ACTIVE_EVENT"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dominant_impact"] = self.dominant_impact.value if isinstance(self.dominant_impact, MarketContextImpact) else str(self.dominant_impact)
        return d


@dataclass
class BehavioralPatternEvaluationRecord:
    """Empirical verification record for an event-conditioned market pattern."""
    pattern_id: str
    pattern_name: str
    sample_count: int
    sufficient_evidence: bool
    win_rate_15m: float
    expected_return_15m: float
    win_rate_1h: float
    expected_return_1h: float
    win_rate_4h: float
    expected_return_4h: float
    failure_rate: float
    risk_assessment: str
    empirical_status: str  # "VALIDATED", "INSUFFICIENT_SAMPLES", "FALSIFIED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BaselineComparisonRecord:
    """Evaluation comparing predictive model against statistical baselines."""
    horizon: str
    model_name: str
    accuracy_3class: float
    accuracy_binary: float
    balanced_accuracy: float
    brier_score: float
    majority_class_baseline_accuracy: float
    persistence_baseline_accuracy: float
    random_walk_baseline_accuracy: float
    momentum_baseline_accuracy: float
    edge_over_majority: float
    edge_over_random: float
    sample_count_overlapping: int
    sample_count_independent: int
    statistical_verdict: str  # "ADVANTAGE_PROVEN", "NO_EDGE", "INCONCLUSIVE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    baseline_buy_and_hold_drawdown_pct: float = 0.0
    baseline_buy_and_hold_fees: float = 0.0
    baseline_buy_and_hold_sharpe: float = 0.0
    baseline_cash_return_pct: float = 0.0
    abstention_count: int = 0
    fee_drag_pct: float = 0.0
    dataset_split: str = "FULL"
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


# ---------------------------------------------------------------------------
# Sprint 11.06 Contracts: Provenance, Ablation, Rejection Attribution & Regimes
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceAuditRecord:
    """Detailed audit record for historical news and market events."""
    event_id: str
    headline: str
    source_name: str
    source_url: str
    source_tier: str
    published_at_utc: str
    first_observed_at_utc: str
    earliest_defensible_decision_time_utc: str
    observation_latency_seconds: float
    page_type: str  # STATIC_ARTICLE, DYNAMIC_FEED, PUBLIC_CMS_API, PRICE_VOLUME_PROXY
    dynamic_update_limitations: str
    factual_claim_supported: str  # VERIFIED_ACCURATE, UNSUPPORTED_PROXY, IRRELEVANT_CLAIM
    relevance_classification: str  # DIRECT_BTC_MACRO, EXCHANGE_DIRECT_BTC, ALTCOIN_IRRELEVANT, EQUITY_NON_CRYPTO, DERIVATIVES_PRICE_PROXY
    is_genuine_external_news: bool
    strict_provenance_verdict: str  # PASS_STRICT_PROVENANCE, REJECT_ALTCOIN_NOISE, REJECT_NON_CRYPTO_EQUITY, REJECT_DERIVATIVES_PROXY
    rejection_reason: str
    trading_decision_impact: str  # FILTERED_TRADE, INERT_NOISE, BLOCKED_ENTRY

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContextAblationExperimentRecord:
    """Results from controlled ablation experiments across models A through G."""
    model_id: str
    description: str
    trade_count: int
    trade_count_mean: float
    trade_count_std: float
    net_pnl_usd: float
    net_pnl_mean: float
    net_pnl_std: float
    net_pnl_min: float
    net_pnl_max: float
    net_pnl_p5: float
    net_pnl_p95: float
    return_pct: float
    return_pct_mean: float
    return_pct_std: float
    win_rate_pct: float
    win_rate_mean: float
    win_rate_std: float
    max_drawdown_pct: float
    max_drawdown_mean: float
    max_drawdown_std: float
    profit_factor: float
    sharpe_ratio: float
    total_fees_usd: float
    seeds_evaluated: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RejectedTradeAttributionRecord:
    """Trade-by-trade attribution for signals filtered out by context or risk rules."""
    rejection_id: str
    trade_id_strat_a: str
    signal_datetime_utc: str
    signal_price: float
    signal_reason: str
    rejecting_event_id: Optional[str]
    rejecting_event_headline: Optional[str]
    event_published_at_utc: Optional[str]
    event_source: Optional[str]
    was_event_genuinely_available: bool
    hypothetical_exit_datetime_utc: str
    hypothetical_exit_price: float
    hypothetical_exit_reason: str
    hypothetical_net_pnl_usd: float
    hypothetical_return_pct: float
    hypothetical_outcome: str  # WIN, LOSS
    pnl_avoided_usd: float
    matched_non_event_pnl_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarketRegimeComparisonRecord:
    """Comparative performance breakdown across market regimes."""
    regime_id: str
    regime_name: str
    start_datetime_utc: str
    end_datetime_utc: str
    candle_count: int
    btc_price_change_pct: float
    strat_a_trades: int
    strat_a_net_pnl: float
    strat_a_win_rate: float
    strat_b_trades: int
    strat_b_net_pnl: float
    strat_b_win_rate: float
    random_c_net_pnl_mean: float
    model_e_vol_trades: int
    model_e_vol_net_pnl: float
    strat_c_trades: int
    strat_c_net_pnl: float
    context_advantage_over_random: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Sprint 11.07 Contracts: Behavioral State, Analogues & Walk-Forward
# ---------------------------------------------------------------------------

@dataclass
class MarketStateVector:
    """Causal, multi-timeframe market state representation."""
    timestamp_open: int
    datetime_utc: str
    close_price: float
    # Price Structure & Trends
    trend_5m_pct: float
    trend_15m_pct: float
    trend_1h_pct: float
    trend_4h_pct: float
    price_acceleration: float
    # Volatility & Liquidity
    realized_vol_24: float
    realized_vol_72: float
    volatility_compression_ratio: float  # ATR14 / ATR100
    relative_volume_20: float
    # Location within Range
    distance_to_support_pct: float
    distance_to_resistance_pct: float
    drawdown_from_peak_pct: float
    runup_from_trough_pct: float
    breakout_state: str  # "NONE", "BULLISH_BREAKOUT", "BEARISH_BREAKDOWN", "FAILED_BREAKOUT"
    regime: MarketRegimeType
    # News Context
    event_context_status: str  # "VERIFIED_RELEVANT", "NO_MATERIAL_EVENT", "FEED_UNAVAILABLE", "UNVERIFIED_RUMOR"
    event_sentiment_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["regime"] = self.regime.value
        return d


@dataclass
class HistoricalAnalogueRecord:
    """Historical analogue match and subsequent observed forward outcomes."""
    decision_timestamp: int
    decision_datetime_utc: str
    analogue_timestamp: int
    analogue_datetime_utc: str
    similarity_distance: float
    analogue_regime: str
    # Forward Outcomes
    fwd_ret_15m: float
    fwd_ret_1h: float
    fwd_ret_4h: float
    fwd_ret_24h: float
    max_favorable_excursion_pct: float
    max_adverse_excursion_pct: float
    hit_resistance_first: bool
    hit_support_first: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConditionalPredictionRecord:
    """Probabilistic prediction derived from historical analogues."""
    decision_timestamp: int
    datetime_utc: str
    horizon: str  # "15m", "1h", "4h", "24h"
    current_price: float
    analogue_count: int
    mean_similarity_distance: float
    prob_up: float
    prob_down: float
    prob_neutral: float
    expected_return_pct: float
    downside_risk_pct: float
    conf_interval_low_pct: float
    conf_interval_high_pct: float
    predicted_regime: str
    confidence_status: str  # "CALIBRATED", "UNCALIBRATED", "NO_PREDICTION"
    actual_return_pct: Optional[float] = None
    actual_direction: Optional[str] = None  # "UP", "DOWN", "NEUTRAL"
    brier_score: Optional[float] = None
    is_direction_correct: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WalkForwardFoldResult:
    """Performance metrics for an individual walk-forward validation fold."""
    fold_id: str
    train_start_utc: str
    train_end_utc: str
    test_start_utc: str
    test_end_utc: str
    train_candles: int
    test_candles: int
    directional_accuracy_pct: float
    brier_score: float
    strategy_trades: int
    strategy_win_rate_pct: float
    strategy_net_pnl_usd: float
    strategy_return_pct: float
    strategy_max_dd_pct: float
    strategy_profit_factor: float
    strategy_fees_usd: float
    bnh_return_pct: float
    outperformed_buy_and_hold: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


