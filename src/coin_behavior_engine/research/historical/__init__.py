"""CBE Historical Market Research Foundation.

Sprint 09.20: Historical Market Research Foundation — Architecture Discovery & Safe Offline Implementation.

Provides:
- Historical dataset contract, validation, and provenance tracking.
- Bounded-memory chunked dataset reader and idempotent storage.
- Price action features (Support/Resistance, Breakout, Failed Breakout, Retest, Pullback, Momentum, Reversal).
- Market sessions framework (Asian, London, New York, Overlaps, Opening Ranges: 5/10/15/30/60m with timezone/DST).
- Market context (Trend/Range, Volatility Regimes, Relative Volume, OHLCV Liquidity Proxies).
- Extensibility interfaces (News, Macro, Derivatives, Funding, Liquidations with availability timestamps).
- Purged and embargoed walk-forward time-series splitter.
- Investment-oriented net-return evaluation engine (TP/SL, fees, spread, slippage, drawdown, independent trade counts).
"""

from __future__ import annotations

from coin_behavior_engine.research.historical.dataset_contract import (
    BINANCE_SPOT_BTCUSDT_GENESIS_MS,
    BINANCE_SPOT_BTCUSDT_GENESIS_UTC,
    HistoricalDataBoundaryError,
    HistoricalDataStorageError,
    HistoricalDatasetContract,
    HistoricalDatasetProvenance,
    HistoricalDatasetReader,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
)
from coin_behavior_engine.research.historical.validation import (
    HistoricalCandleValidator,
    HistoricalValidationReport,
)
from coin_behavior_engine.research.historical.price_action import (
    PriceActionFeatureExtractor,
    PriceActionSignals,
)
from coin_behavior_engine.research.historical.market_sessions import (
    MarketSession,
    MarketSessionConfig,
    MarketSessionDetector,
    OpeningRangeWindow,
)
from coin_behavior_engine.research.historical.market_context import (
    MarketContextExtractor,
    MarketContextFeatures,
)
from coin_behavior_engine.research.historical.extensibility_interfaces import (
    DerivativesContextItem,
    EconomicAnnouncementItem,
    EtfFlowItem,
    ExternalDataAvailabilityError,
    TimestampedNewsItem,
)
from coin_behavior_engine.research.historical.walkforward_purged import (
    PurgedEmbargoTimeSeriesSplitter,
    PurgedFold,
)
from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentEvaluator,
    InvestmentOpportunity,
    PortfolioEvaluationReport,
    SimulatedTradeResult,
    TradeCostModel,
    TradeDirection,
)
from coin_behavior_engine.research.historical.binance_archival_ingestion import (
    BinanceArchivalDownloader,
    IngestionResult,
)
from coin_behavior_engine.research.historical.experiments import (
    HypothesisEvaluationResult,
    HypothesisExperimentConfig,
    ScientificExperimentRunner,
)
from coin_behavior_engine.research.historical.timeframe_aggregator import (
    AggregationReport,
    HistoricalTimeframeAggregator,
)
from coin_behavior_engine.research.historical.execution_model import (
    ExecutionMode,
    ExecutionParameters,
    ExecutionResult,
    OrderFillStatus,
    RealisticExecutionSimulator,
)
from coin_behavior_engine.research.historical.regime_filters import (
    FilterEvaluationReport,
    RegimeFilterBank,
    RegimeFilterType,
)
from coin_behavior_engine.research.historical.provenance import (
    AuditableTradeLedger,
    AuditableTradeRecord,
    ExperimentProvenanceRecord,
)
from coin_behavior_engine.research.historical.new_hypotheses import (
    NewHypothesesGenerator,
)
from coin_behavior_engine.research.historical.market_regime_intelligence import (
    ConditionalReturnDistribution,
    MarketRegimeEngine,
    MarketRegimeState,
    MomentumRegime,
    RegimeTransitionReport,
    TrendRegime,
    VolatilityRegime,
    VolumeRegime,
)
from coin_behavior_engine.research.historical.h4_conditional_research import (
    H4ConditionalExperimentRunner,
    H4ConditionalVariantResult,
)
from coin_behavior_engine.research.historical.behavioral_discovery import (
    BehavioralDiscoveryAnalyzer,
    BehavioralDiscoveryFinding,
    BehavioralEvidenceStatus,
)
from coin_behavior_engine.research.historical.extensibility_interfaces import (
    ExternalDataReadinessValidator,
    TimestampedSignalEnvelope,
)
from coin_behavior_engine.research.historical.regime_audit import (
    CausalityAttribution,
    NullModelTransitionStats,
    RegimeCausalityAuditReport,
    RegimeClassificationAuditor,
    SensitivityVariationResult,
)
from coin_behavior_engine.research.historical.executable_behaviors import (
    B3StrategyConfig,
    B5StrategyConfig,
    ExecutableBehaviorSimulator,
    ExecutableStrategyMetrics,
)
from coin_behavior_engine.research.historical.behavioral_validation import (
    BehavioralDecisionVerdict,
    BehavioralValidationOrchestrator,
    ConfirmatoryHoldoutResult,
    MultipleTestingCorrectionReport,
    PreRegistrationGate,
    WalkForwardFoldResult,
)

__all__ = [
    "BINANCE_SPOT_BTCUSDT_GENESIS_MS",
    "BINANCE_SPOT_BTCUSDT_GENESIS_UTC",
    "HistoricalMarketSpec",
    "HistoricalDatasetProvenance",
    "HistoricalDatasetContract",
    "HistoricalDatasetStore",
    "HistoricalDatasetReader",
    "HistoricalCandleValidator",
    "HistoricalValidationReport",
    "PriceActionFeatureExtractor",
    "PriceActionSignals",
    "MarketSession",
    "OpeningRangeWindow",
    "MarketSessionConfig",
    "MarketSessionDetector",
    "MarketContextExtractor",
    "MarketContextFeatures",
    "TimestampedNewsItem",
    "EconomicAnnouncementItem",
    "DerivativesContextItem",
    "EtfFlowItem",
    "ExternalDataAvailabilityError",
    "PurgedEmbargoTimeSeriesSplitter",
    "PurgedFold",
    "TradeDirection",
    "InvestmentOpportunity",
    "TradeCostModel",
    "SimulatedTradeResult",
    "PortfolioEvaluationReport",
    "InvestmentEvaluator",
    "BinanceArchivalDownloader",
    "IngestionResult",
    "ScientificExperimentRunner",
    "HypothesisEvaluationResult",
    "HypothesisExperimentConfig",
    "HistoricalTimeframeAggregator",
    "AggregationReport",
    "ExecutionMode",
    "ExecutionParameters",
    "ExecutionResult",
    "OrderFillStatus",
    "RealisticExecutionSimulator",
    "FilterEvaluationReport",
    "RegimeFilterBank",
    "RegimeFilterType",
    "AuditableTradeLedger",
    "AuditableTradeRecord",
    "ExperimentProvenanceRecord",
    "NewHypothesesGenerator",
    "TrendRegime",
    "VolatilityRegime",
    "VolumeRegime",
    "MomentumRegime",
    "MarketRegimeState",
    "RegimeTransitionReport",
    "ConditionalReturnDistribution",
    "MarketRegimeEngine",
    "H4ConditionalVariantResult",
    "H4ConditionalExperimentRunner",
    "BehavioralEvidenceStatus",
    "BehavioralDiscoveryFinding",
    "BehavioralDiscoveryAnalyzer",
    "TimestampedSignalEnvelope",
    "ExternalDataReadinessValidator",
    "CausalityAttribution",
    "NullModelTransitionStats",
    "SensitivityVariationResult",
    "RegimeCausalityAuditReport",
    "RegimeClassificationAuditor",
    "B3StrategyConfig",
    "B5StrategyConfig",
    "ExecutableBehaviorSimulator",
    "ExecutableStrategyMetrics",
    "BehavioralDecisionVerdict",
    "PreRegistrationGate",
    "MultipleTestingCorrectionReport",
    "WalkForwardFoldResult",
    "ConfirmatoryHoldoutResult",
    "BehavioralValidationOrchestrator",
]
